from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from pcb2stl.domain import Drawing, PenParams, Polygon2D
from pcb2stl.toolpaths import generate_toolpaths


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


def test_mirror_negates_x():
    paths = generate_toolpaths(_square(10), PenParams(pen_width_mm=1.0, perimeters=1, fill=False, mirror=True))
    assert all(x <= 1e-4 for p in paths for x, _ in p)
