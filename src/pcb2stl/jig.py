from __future__ import annotations

from manifold3d import Manifold

from .domain import JigParams
from .meshing import solid_to_stl


def build_jig_stl(copper_width_mm: float, copper_height_mm: float, jig: JigParams) -> bytes:
    """An L-corner holder sized to the board (copper plus margin on every side).
    Walls hug the bottom-left corner at board height; flat flanges tape it down."""
    margin = jig.board_margin_mm
    board_w = copper_width_mm + 2 * margin
    board_h = copper_height_mm + 2 * margin
    wall = jig.wall_mm
    flange = jig.flange_mm
    wall_h = jig.board_thickness_mm

    parts = [
        _box(wall, board_h + wall, wall_h, -wall, -wall),
        _box(board_w + wall, wall, wall_h, -wall, -wall),
        _box(flange, board_h + wall + flange, jig.base_mm, -wall - flange, -wall - flange),
        _box(board_w + wall + flange, flange, jig.base_mm, -wall - flange, -wall - flange),
    ]
    solid = parts[0]
    for part in parts[1:]:
        solid = solid + part
    return solid_to_stl(solid)


def _box(size_x: float, size_y: float, size_z: float, x: float, y: float) -> Manifold:
    return Manifold.cube([size_x, size_y, size_z]).translate([x, y, 0.0])
