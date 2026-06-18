from __future__ import annotations

from typing import Protocol

from .domain import PenParams
from .toolpaths import Polyline, path_stats, place_paths


class PenLift(Protocol):
    def up(self) -> str: ...
    def down(self) -> str: ...


class ZPenLift:
    """Raise and lower the pen with the Z axis (pen adapter, no servo)."""

    def __init__(self, draw_z: float, travel_z: float, z_feed: float) -> None:
        self._draw_z = draw_z
        self._travel_z = travel_z
        self._z_feed = z_feed

    def up(self) -> str:
        return f"G1 Z{self._travel_z:.3f} F{self._z_feed:.0f}"

    def down(self) -> str:
        return f"G1 Z{self._draw_z:.3f} F{self._z_feed:.0f}"


class ServoPenLift:
    """Raise and lower the pen with a hobby servo on M280 channel 0, plus a settle dwell."""

    def __init__(self, up_deg: float, down_deg: float, dwell_ms: float) -> None:
        self._up = up_deg
        self._down = down_deg
        self._dwell = dwell_ms

    def up(self) -> str:
        return f"M280 P0 S{self._up:.0f}\nG4 P{self._dwell:.0f}"

    def down(self) -> str:
        return f"M280 P0 S{self._down:.0f}\nG4 P{self._dwell:.0f}"


def _lift_for(pen: PenParams) -> PenLift:
    if pen.lift_mode == "servo":
        return ServoPenLift(pen.servo_up_deg, pen.servo_down_deg, pen.servo_dwell_ms)
    return ZPenLift(pen.draw_z_mm, pen.travel_z_mm, pen.z_feed)


def render_gcode(paths: list[Polyline], pen: PenParams, lift: PenLift | None = None) -> str:
    lift = lift or _lift_for(pen)
    paths = place_paths(paths, pen.origin_x_mm + pen.board_margin_mm, pen.origin_y_mm + pen.board_margin_mm)
    strokes, draw_mm, travel_mm = path_stats(paths)
    lines = [
        "; pcb2stl pen-plot gcode -- no extrusion, no heating",
        f"; jig corner at X{pen.origin_x_mm:.1f} Y{pen.origin_y_mm:.1f}; copper inset {pen.board_margin_mm:.1f} mm",
        f"; strokes {strokes}, draw {draw_mm:.0f} mm, travel {travel_mm:.0f} mm",
        "; calibrate Z so the pen meets the board at the draw height",
        "G21",
        "G90",
        "G28",
        lift.up(),
    ]
    for path in paths:
        if len(path) < 2:
            continue
        x0, y0 = path[0]
        lines.append(f"G0 X{x0:.3f} Y{y0:.3f} F{pen.travel_feed:.0f}")
        lines.append(lift.down())
        for x, y in path[1:]:
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{pen.draw_feed:.0f}")
        lines.append(lift.up())
    lines.append(lift.up())
    lines.append(f"G0 X0 Y0 F{pen.travel_feed:.0f}")
    lines.append("M84")
    return "\n".join(lines) + "\n"
