import math
from collections import Counter

import pytest
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from pcb2stl.domain import Drawing, PenParams, Polygon2D
from pcb2stl.toolpaths import (
    generate_toolpaths,
    optimize_order,
    path_stats,
    place_paths,
    tagged_toolpaths,
)


def _travel(paths):
    cursor = (0.0, 0.0)
    total = 0.0
    for path in paths:
        total += math.dist(cursor, path[0])
        cursor = path[-1]
    return total


def _endpoint_pairs(paths):
    return Counter(frozenset((path[0], path[-1])) for path in paths)


def _square(side=10.0):
    return Drawing((Polygon2D(((0, 0), (side, 0), (side, side), (0, side))),))


def _covered_area(paths, pen_width):
    strokes = [LineString(p).buffer(pen_width / 2.0) for p in paths if len(p) >= 2]
    return unary_union(strokes).area if strokes else 0.0


def test_perimeters_and_fill_cover_the_copper():
    paths = generate_toolpaths(_square(10), PenParams(pen_width_mm=1.0, perimeters=1, fill=True))
    assert _covered_area(paths, 1.0) >= 0.9 * 100.0


def test_paths_stay_within_the_shape():
    paths = generate_toolpaths(_square(10), PenParams(pen_width_mm=1.0, perimeters=1, fill=True))
    square = ShapelyPolygon([(0, 0), (10, 0), (10, 10), (0, 10)]).buffer(0.02)
    assert all(square.contains(LineString(p)) for p in paths if len(p) >= 2)


def test_holes_are_not_drawn():
    poly = Polygon2D(((0, 0), (20, 0), (20, 20), (0, 20)), (((8, 8), (8, 12), (12, 12), (12, 8)),))
    paths = generate_toolpaths(Drawing((poly,)), PenParams(pen_width_mm=1.0, perimeters=1, fill=True))
    hole = ShapelyPolygon([(8.5, 8.5), (11.5, 8.5), (11.5, 11.5), (8.5, 11.5)])
    assert all(not hole.intersects(LineString(p)) for p in paths if len(p) >= 2)


def test_thin_trace_narrower_than_the_pen_is_still_drawn():
    trace = Drawing((Polygon2D(((0, 0), (10, 0), (10, 0.3), (0, 0.3))),))
    paths = generate_toolpaths(trace, PenParams(pen_width_mm=0.4, perimeters=2, fill=True))
    assert paths  # not silently dropped
    assert _covered_area(paths, 0.4) >= 0.3 * 10 * 0.8  # the pen still covers the trace


def test_thin_trace_draws_near_its_centreline_not_its_outline():
    trace = Drawing((Polygon2D(((0, 0), (10, 0), (10, 0.4), (0, 0.4))),))
    paths = generate_toolpaths(trace, PenParams(pen_width_mm=1.0, perimeters=1, fill=True))
    ys = [y for p in paths for _, y in p]
    assert ys
    assert min(ys) > 0.05 and max(ys) < 0.35  # hugs the centre (~0.2), not the 0/0.4 edges


def test_mirror_negates_x():
    paths = generate_toolpaths(_square(10), PenParams(pen_width_mm=1.0, perimeters=1, fill=False, mirror=True))
    assert all(x <= 1e-4 for p in paths for x, _ in p)


def test_tagged_toolpaths_label_perimeter_and_fill():
    pen = PenParams(pen_width_mm=1.0, perimeters=2, fill=True)
    tagged = tagged_toolpaths(_square(20), pen)
    kinds = {kind for kind, _ in tagged}
    assert kinds == {"perimeter", "fill"}
    assert [points for _, points in tagged] == generate_toolpaths(_square(20), pen)


def test_convex_fill_is_chained_into_few_strokes():
    paths = generate_toolpaths(_square(20), PenParams(pen_width_mm=1.0, perimeters=2, fill=True))
    assert len(paths) <= 6  # 2 perimeter rings + a chained boustrophedon, not ~16 separate rows


def test_optimize_order_cuts_travel_and_preserves_strokes():
    paths = [((0, 0), (1, 0)), ((100, 0), (101, 0)), ((2, 0), (3, 0)), ((101, 0), (102, 0))]
    optimized = optimize_order(paths)
    assert _travel(optimized) < _travel(paths)
    assert _endpoint_pairs(optimized) == _endpoint_pairs(paths)  # same strokes, maybe reversed


def test_place_paths_moves_bottom_left_to_origin():
    placed = place_paths([((5.0, 5.0), (7.0, 9.0))], 10.0, 20.0)
    assert min(x for p in placed for x, _ in p) == pytest.approx(10.0)
    assert min(y for p in placed for _, y in p) == pytest.approx(20.0)
    assert placed[0][1] == pytest.approx((12.0, 24.0))  # (7,9) shifted by (+5,+15)


def test_path_stats_measures_draw_and_travel():
    count, draw, travel = path_stats([((0.0, 0.0), (3.0, 4.0)), ((10.0, 0.0), (12.0, 0.0))])
    assert count == 2
    assert draw == pytest.approx(5.0 + 2.0)  # 3-4-5 stroke plus a 2 mm stroke
    assert travel == pytest.approx(math.hypot(7.0, 4.0))  # hop from (3,4) to (10,0)
