from __future__ import annotations

from typing import Protocol

from .domain import PenParams
from .toolpaths import Polyline


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


def render_gcode(paths: list[Polyline], pen: PenParams, lift: PenLift | None = None) -> str:
    lift = lift or ZPenLift(pen.draw_z_mm, pen.travel_z_mm, pen.z_feed)
    paths = _place(paths, pen.origin_x_mm + pen.board_margin_mm, pen.origin_y_mm + pen.board_margin_mm)
    lines = [
        "; pcb2stl pen-plot gcode -- no extrusion, no heating",
        f"; jig corner at X{pen.origin_x_mm:.1f} Y{pen.origin_y_mm:.1f}; copper inset {pen.board_margin_mm:.1f} mm",
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


def _place(paths: list[Polyline], x0: float, y0: float) -> list[Polyline]:
    points = [point for path in paths for point in path]
    if not points:
        return paths
    dx = x0 - min(x for x, _ in points)
    dy = y0 - min(y for _, y in points)
    return [tuple((x + dx, y + dy) for x, y in path) for path in paths]
