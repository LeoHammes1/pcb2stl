import io
import math
from pathlib import Path

import ezdxf
import pytest
from ezdxf import units
from shapely.geometry import Polygon as ShapelyPolygon

from pcb2stl.parsing.dxf import DxfParser

SAMPLE = (Path(__file__).resolve().parents[1] / "fixtures" / "sample.dxf").read_bytes()


def _areas(drawing):
    return sorted(ShapelyPolygon(p.exterior, p.holes).area for p in drawing.polygons)


def test_sample_dxf_yields_three_copper_shapes_in_mm():
    drawing = DxfParser().parse(SAMPLE)
    assert len(drawing.polygons) == 3
    assert drawing.bounds == pytest.approx((-0.5, 0.0, 23.0, 20.5), abs=0.05)


def test_closed_polyline_circle_and_width_trace_areas():
    areas = _areas(DxfParser().parse(SAMPLE))
    assert areas[0] == pytest.approx(10.0 + math.pi * 0.25, rel=0.05)  # 10mm trace, 1mm wide
    assert areas[1] == pytest.approx(math.pi * 9.0, rel=0.02)  # circle r=3 (flattened)
    assert areas[2] == pytest.approx(100.0, abs=0.01)  # 10x10 closed polyline


def test_inch_units_are_scaled_to_millimetres():
    doc = ezdxf.new()
    doc.units = units.IN
    doc.modelspace().add_lwpolyline([(0, 0), (1, 0), (1, 1), (0, 1)], close=True)
    buf = io.StringIO()
    doc.write(buf)
    drawing = DxfParser().parse(buf.getvalue().encode())
    assert len(drawing.polygons) == 1
    assert _areas(drawing)[0] == pytest.approx(25.4**2, rel=1e-3)  # 1 inch square -> 25.4 mm
