import io

import pytest
import trimesh

from pcb2stl.domain import JigParams
from pcb2stl.jig import build_jig_stl


def _mesh(stl):
    return trimesh.load(io.BytesIO(stl), file_type="stl")


def test_jig_is_watertight_and_sized_to_board_plus_margin():
    jig = JigParams(board_thickness_mm=1.6, board_margin_mm=3.0, wall_mm=2.5, flange_mm=6.0)
    mesh = _mesh(build_jig_stl(40.0, 20.0, jig))  # copper 40 x 20 -> board 46 x 26
    assert mesh.is_watertight
    (minx, miny, _), (maxx, maxy, maxz) = mesh.bounds
    assert maxx == pytest.approx(46.0, abs=0.01)  # board width spanned by the walls
    assert maxy == pytest.approx(26.0, abs=0.01)
    assert minx == pytest.approx(-(2.5 + 6.0), abs=0.01)  # flange reaches past the wall
    assert miny == pytest.approx(-(2.5 + 6.0), abs=0.01)
    assert maxz == pytest.approx(1.6, abs=0.01)  # walls stand at board height


def test_zero_margin_jig_matches_copper_extent():
    jig = JigParams(board_margin_mm=0.0)
    mesh = _mesh(build_jig_stl(30.0, 15.0, jig))
    assert mesh.bounds[1][0] == pytest.approx(30.0, abs=0.01)
    assert mesh.bounds[1][1] == pytest.approx(15.0, abs=0.01)
