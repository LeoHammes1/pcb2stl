import re

from pcb2stl.domain import PenParams
from pcb2stl.gcode import render_gcode

PATHS = [((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), ((2.0, 2.0), (8.0, 2.0))]


def test_no_extrusion_no_heating_no_fan():
    text = render_gcode(PATHS, PenParams())
    assert re.search(r"[ \t]E-?\d", text) is None  # never an extrusion argument
    for forbidden in ("M104", "M109", "M140", "M190", "M106", "M107"):
        assert forbidden not in text


def test_preamble_units_home_and_motor_disable():
    text = render_gcode(PATHS, PenParams())
    assert "G21" in text and "G90" in text and "G28" in text
    assert text.strip().endswith("M84")


def test_pen_lowers_to_draw_and_raises_to_travel():
    text = render_gcode(PATHS, PenParams(draw_z_mm=0.0, travel_z_mm=2.0))
    assert "Z0.000" in text  # pen down
    assert "Z2.000" in text  # pen up


def test_travel_is_g0_and_drawing_is_g1():
    text = render_gcode([((0.0, 0.0), (5.0, 0.0))], PenParams())
    assert "G0 X0.000 Y0.000" in text  # rapid to the start with the pen up
    assert "G1 X5.000 Y0.000" in text  # drawing stroke
