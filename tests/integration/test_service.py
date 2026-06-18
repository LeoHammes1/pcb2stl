import io
import re
from pathlib import Path

import pytest
import trimesh

from pcb2stl import config
from pcb2stl.domain import ConversionParams, JigParams, PenParams
from pcb2stl.parsing.base import UnsupportedFormatError
from pcb2stl.service import (
    ComplexityError,
    ConversionService,
    EmptyDrawingError,
    OutputTooLargeError,
    default_service,
)

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


def test_double_sided_makes_two_mirror_image_meshes_with_fiducials():
    service = default_service()
    params = ConversionParams(height_mm=0.2)
    top, bottom = service.convert_double_sided(("top.gbr", GERBER), ("bot.gbr", GERBER), params)
    top_mesh, bottom_mesh = _load(top), _load(bottom)
    assert top_mesh.is_watertight and bottom_mesh.is_watertight

    # the bottom is the X-mirror of the top, so it draws right on the flipped board
    assert bottom_mesh.bounds[0][0] == pytest.approx(-top_mesh.bounds[1][0], abs=0.01)
    assert bottom_mesh.bounds[1][0] == pytest.approx(-top_mesh.bounds[0][0], abs=0.01)
    assert bottom_mesh.bounds[:, 1].tolist() == pytest.approx(top_mesh.bounds[:, 1].tolist(), abs=0.01)

    # both carry the two ring fiducials on top of the bare copper
    plain = _load(service.convert("c.gbr", GERBER, params))
    assert top_mesh.body_count == plain.body_count + 2
    assert bottom_mesh.body_count == plain.body_count + 2


def test_gcode_from_gerber_has_no_extrusion_or_heating():
    text = default_service().convert_to_gcode("board.gbr", GERBER, PenParams(pen_width_mm=0.5))
    assert "G28" in text and text.strip().endswith("M84")
    assert re.search(r"[ \t]E-?\d", text) is None
    assert not any(code in text for code in ("M104", "M109", "M140", "M190", "M106"))


def test_toolpath_preview_places_strokes_at_the_work_origin():
    pen = PenParams(pen_width_mm=0.5, origin_x_mm=10.0, origin_y_mm=10.0, board_margin_mm=3.0)
    preview = default_service().toolpath_preview("board.gbr", GERBER, pen)
    assert preview["stats"]["strokes"] >= 1
    assert all(len(stroke) >= 2 for stroke in preview["strokes"])
    assert len(preview["kinds"]) == len(preview["strokes"])
    assert set(preview["kinds"]) <= {"perimeter", "fill"}
    assert preview["bounds"][0] == pytest.approx(13.0, abs=0.01)  # origin + margin
    assert preview["bounds"][1] == pytest.approx(13.0, abs=0.01)


def test_jig_for_a_board_is_a_watertight_solid():
    mesh = _load(default_service().make_jig("board.gbr", GERBER, JigParams()))
    assert mesh.is_watertight
    assert mesh.volume > 0.0
    assert mesh.bounds[1][2] == pytest.approx(1.6, abs=0.01)  # walls at board thickness


def test_complexity_cap_rejects_too_many_polygons(monkeypatch):
    monkeypatch.setattr(config, "MAX_POLYGONS", 1)
    with pytest.raises(ComplexityError):
        default_service().convert("board.gbr", GERBER, ConversionParams())


def test_complexity_cap_rejects_oversized_extent(monkeypatch):
    monkeypatch.setattr(config, "MAX_EXTENT_MM", 1.0)
    with pytest.raises(ComplexityError):
        default_service().convert("board.gbr", GERBER, ConversionParams())


def test_output_ceiling_rejects_huge_mesh(monkeypatch):
    monkeypatch.setattr(config, "MAX_OUTPUT_BYTES", 10)
    with pytest.raises(OutputTooLargeError):
        default_service().convert("board.gbr", GERBER, ConversionParams())


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
