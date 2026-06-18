import io
from pathlib import Path

import pytest
import trimesh

from pcb2stl.domain import ConversionParams
from pcb2stl.parsing.base import UnsupportedFormatError
from pcb2stl.service import ConversionService, EmptyDrawingError, default_service

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
GERBER = (FIXTURES / "sample.gbr").read_bytes()
DXF = (FIXTURES / "sample.dxf").read_bytes()
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" '
    b'viewBox="0 0 20 10"><rect x="2" y="2" width="6" height="4" fill="black"/></svg>'
)


def _load(stl: bytes):
    return trimesh.load(io.BytesIO(stl), file_type="stl")


def test_gerber_round_trips_to_a_watertight_solid():
    stl = default_service().convert("board.gbr", GERBER, ConversionParams(height_mm=0.2))
    mesh = _load(stl)
    assert mesh.is_watertight
    assert mesh.bounds[1][2] == pytest.approx(0.2, abs=1e-4)
    assert mesh.volume > 0.0


def test_svg_round_trips_to_a_solid_of_expected_volume():
    stl = default_service().convert("art.svg", SVG, ConversionParams(height_mm=0.5))
    mesh = _load(stl)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(24.0 * 0.5, rel=1e-3)  # 6x4 rect at 0.5 tall


def test_dxf_round_trips_to_a_watertight_solid():
    stl = default_service().convert("board.dxf", DXF, ConversionParams(height_mm=0.2))
    mesh = _load(stl)
    assert mesh.is_watertight
    assert mesh.volume > 0.0


def test_unsupported_extension_is_rejected():
    with pytest.raises(UnsupportedFormatError):
        default_service().convert("board.pdf", b"junk", ConversionParams())


def test_input_without_copper_is_rejected():
    empty = b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"></svg>'
    with pytest.raises(EmptyDrawingError):
        default_service().convert("empty.svg", empty, ConversionParams())


def test_supported_extensions_include_all_parsers():
    service: ConversionService = default_service()
    assert {"svg", "gbr", "dxf"} <= set(service.supported_extensions)
