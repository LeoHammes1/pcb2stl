from shapely.geometry import Polygon as ShapelyPolygon

from pcb2stl.merge import merge


def _square(x, y, s):
    return ShapelyPolygon([(x, y), (x + s, y), (x + s, y + s), (x, y + s)])


def _area(polygon2d):
    return ShapelyPolygon(polygon2d.exterior, polygon2d.holes).area


def test_overlapping_squares_become_one_polygon_with_merged_area():
    drawing = merge([_square(0, 0, 10), _square(5, 5, 10)])
    assert len(drawing.polygons) == 1
    assert _area(drawing.polygons[0]) == 175.0  # 100 + 100 - 25


def test_disjoint_squares_stay_separate():
    drawing = merge([_square(0, 0, 1), _square(5, 5, 1)])
    assert len(drawing.polygons) == 2


def test_interior_ring_is_preserved_as_hole():
    ring = ShapelyPolygon(
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        [[(3, 3), (3, 7), (7, 7), (7, 3)]],
    )
    drawing = merge([ring])
    assert len(drawing.polygons) == 1
    assert len(drawing.polygons[0].holes) == 1
    assert _area(drawing.polygons[0]) == 84.0  # 100 - 16


def test_clear_region_is_subtracted():
    drawing = merge([_square(0, 0, 10)], clear=[_square(0, 0, 4)])
    assert len(drawing.polygons) == 1
    assert _area(drawing.polygons[0]) == 84.0  # 100 - 16
