import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from pcb2stl.parsing.gerber import GerberParser

SAMPLE = (Path(__file__).resolve().parents[1] / "fixtures" / "sample.gbr").read_bytes()


def _polys(drawing):
    return [ShapelyPolygon(p.exterior, p.holes) for p in drawing.polygons]


def test_sample_gerber_yields_four_disjoint_copper_shapes():
    drawing = GerberParser().parse(SAMPLE)
    assert len(drawing.polygons) == 4


def test_geometry_is_in_millimetres_with_expected_extent():
    drawing = GerberParser().parse(SAMPLE)
    # trace 0.5mm wide from (1,1) to (9,1) sets the left/bottom and right extent
    minx, miny, maxx, maxy = drawing.bounds
    assert (minx, miny) == pytest.approx((0.75, 0.75), abs=0.02)
    assert maxx == pytest.approx(9.25, abs=0.02)  # trace end + half width
    assert maxy == pytest.approx(8.5, abs=0.02)  # 2x1 rect pad flashed at y=8


def test_circle_pad_area_matches_aperture():
    drawing = GerberParser().parse(SAMPLE)
    circle = next(
        p for p in _polys(drawing) if p.contains(ShapelyPolygon([(4.8, 4.8), (5.2, 4.8), (5.0, 5.2)]))
    )
    assert circle.area == pytest.approx(math.pi * 0.5**2, rel=0.02)  # 1mm dia aperture


def test_rectangle_pad_area_matches_aperture():
    drawing = GerberParser().parse(SAMPLE)
    rect = next(p for p in _polys(drawing) if p.contains(ShapelyPolygon([(7.6, 7.8), (8.4, 7.8), (8.0, 8.2)])))
    assert rect.area == pytest.approx(2.0, rel=0.01)  # 2.0 x 1.0


CLEAR_POLARITY = b"""%FSLAX46Y46*%
%MOMM*%
%ADD10R,10.0X10.0*%
%ADD11C,4.0*%
D10*
X5000000Y5000000D03*
%LPC*%
D11*
X5000000Y5000000D03*
M02*
"""

ROTATED_RECT = b"""%FSLAX46Y46*%
%MOMM*%
%AMRECT30*
21,1,4,1,0,0,30*%
%ADD10RECT30*%
D10*
X5000000Y5000000D03*
M02*
"""

ARC_REGION = b"""%FSLAX46Y46*%
%MOMM*%
G36*
X0Y0D02*
X10000000Y0D01*
G75*
G03*
X0Y10000000I-10000000J0D01*
G01*
X0Y0D01*
G37*
M02*
"""


def test_clear_polarity_punches_a_hole():
    drawing = GerberParser().parse(CLEAR_POLARITY)
    assert len(drawing.polygons) == 1
    assert len(drawing.polygons[0].holes) == 1
    assert _polys(drawing)[0].area == pytest.approx(100.0 - math.pi * 2.0**2, rel=0.02)


def test_rotated_rectangle_keeps_area_and_rotates_counterclockwise():
    drawing = GerberParser().parse(ROTATED_RECT)
    poly = _polys(drawing)[0]
    assert poly.area == pytest.approx(4.0, rel=1e-3)  # 4 x 1, area is rotation invariant
    # gerbonara rotation is counter-clockwise (y-up); corner (7,5.5) maps to (6.482,6.433)
    corners = list(poly.exterior.coords)
    nearest = min(math.hypot(x - 6.482, y - 6.433) for x, y in corners)
    assert nearest < 0.03


def test_arc_region_follows_the_arc_not_the_chord():
    drawing = GerberParser().parse(ARC_REGION)
    area = _polys(drawing)[0].area
    assert area == pytest.approx(math.pi * 100.0 / 4.0, rel=0.01)  # quarter disc ~78.5
    assert area > 60.0  # a straight-chord triangle would be only 50
