import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from pcb2stl.domain import Drawing, Polygon2D
from pcb2stl.registration import combined_bounds, registration_marks


def _centroid(mark):
    return ShapelyPolygon(mark.exterior, mark.holes).centroid


def test_two_marks_sit_in_the_side_margins_at_board_mid_height():
    cents = sorted((_centroid(m).x, _centroid(m).y) for m in registration_marks((0, 0, 100, 60)))
    assert cents[0] == pytest.approx((-4.0, 30.0), abs=0.01)  # left of the board
    assert cents[1] == pytest.approx((104.0, 30.0), abs=0.01)  # right of the board


def test_each_mark_is_a_ring_with_a_drill_hole():
    marks = registration_marks((0, 0, 10, 10))
    assert len(marks) == 2
    assert all(len(m.holes) == 1 for m in marks)


def test_combined_bounds_spans_both_drawings():
    a = Drawing((Polygon2D(((0, 0), (10, 0), (10, 10), (0, 10))),))
    b = Drawing((Polygon2D(((20, 20), (30, 20), (30, 30), (20, 30))),))
    assert combined_bounds(a, b) == (0.0, 0.0, 30.0, 30.0)
