import pytest

from pcb2stl.domain import ConversionParams, Drawing, Polygon2D

SQUARE = ((0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (0.0, 2.0))


def test_polygon_rejects_degenerate_exterior():
    with pytest.raises(ValueError):
        Polygon2D(((0.0, 0.0), (1.0, 1.0)))


def test_polygon_rejects_degenerate_hole():
    with pytest.raises(ValueError):
        Polygon2D(SQUARE, (((1.0, 1.0), (2.0, 2.0)),))


def test_drawing_bounds_span_every_polygon():
    drawing = Drawing(
        (
            Polygon2D(SQUARE),
            Polygon2D(((10.0, 10.0), (12.0, 10.0), (12.0, 13.0), (10.0, 13.0))),
        )
    )
    assert drawing.bounds == (0.0, 0.0, 12.0, 13.0)


def test_empty_drawing_has_no_bounds():
    with pytest.raises(ValueError):
        Drawing(()).bounds


def test_params_reject_nonpositive_height():
    with pytest.raises(ValueError):
        ConversionParams(height_mm=0.0)
