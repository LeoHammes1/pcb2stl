import math

import pytest
from shapely.geometry import Polygon as ShapelyPolygon

from pcb2stl.parsing.svg import SvgParser

FILLED = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" '
    'viewBox="0 0 20 10">'
    '<rect x="2" y="2" width="6" height="4" fill="black"/>'
    '<circle cx="14" cy="5" r="3" fill="black"/>'
    "</svg>"
)

STROKED = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" '
    'viewBox="0 0 20 10">'
    '<path d="M2 5 L18 5" fill="none" stroke="black" stroke-width="1"/>'
    "</svg>"
)

EVENODD_HOLE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="20mm" '
    'viewBox="0 0 20 20">'
    '<path fill="black" fill-rule="evenodd" '
    'd="M2 2 H18 V18 H2 Z M7 7 H13 V13 H7 Z"/>'
    "</svg>"
)


def _area(polygon2d):
    return ShapelyPolygon(polygon2d.exterior, polygon2d.holes).area


def test_filled_shapes_become_polygons_in_millimetres():
    drawing = SvgParser().parse(FILLED.encode())
    assert len(drawing.polygons) == 2
    assert drawing.bounds == pytest.approx((2.0, 2.0, 17.0, 8.0), abs=0.1)
    areas = sorted(_area(p) for p in drawing.polygons)
    assert areas[0] == pytest.approx(24.0, abs=0.01)  # rect 6x4
    assert areas[1] == pytest.approx(math.pi * 9.0, rel=0.02)  # circle r=3 (flattened)


def test_stroke_is_buffered_to_its_width():
    drawing = SvgParser().parse(STROKED.encode())
    assert len(drawing.polygons) == 1
    # 16 mm long, 1 mm wide line -> ~16 plus two semicircular caps
    assert _area(drawing.polygons[0]) == pytest.approx(16.0 + math.pi * 0.25, rel=0.05)


def test_evenodd_subpath_is_a_hole():
    drawing = SvgParser().parse(EVENODD_HOLE.encode())
    assert len(drawing.polygons) == 1
    assert len(drawing.polygons[0].holes) == 1
    assert _area(drawing.polygons[0]) == pytest.approx(256.0 - 36.0, abs=0.01)


def test_empty_svg_yields_empty_drawing():
    empty = '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"></svg>'
    assert SvgParser().parse(empty.encode()).is_empty


def test_svg_without_physical_size_treats_user_units_as_mm():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10">'
        '<rect x="2" y="2" width="6" height="4" fill="black"/></svg>'
    )
    drawing = SvgParser().parse(svg.encode())
    assert drawing.bounds == pytest.approx((2.0, 2.0, 8.0, 6.0), abs=0.01)


def test_billion_laughs_svg_is_rejected():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        '<!ENTITY lol2 "&lol;&lol;">]><svg xmlns="http://www.w3.org/2000/svg">&lol2;</svg>'
    )
    with pytest.raises(ValueError):
        SvgParser().parse(bomb.encode())


def test_xxe_external_entity_svg_is_rejected():
    xxe = (
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<svg xmlns="http://www.w3.org/2000/svg">&xxe;</svg>'
    )
    with pytest.raises(ValueError):
        SvgParser().parse(xxe.encode())


def test_standard_svg_doctype_is_accepted():
    # KiCad and other tools emit the standard SVG 1.1 DTD reference -- it must parse
    svg = (
        '<?xml version="1.0" standalone="no"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10">'
        '<rect x="2" y="2" width="6" height="4" fill="black"/></svg>'
    )
    drawing = SvgParser().parse(svg.encode())
    assert not drawing.is_empty
