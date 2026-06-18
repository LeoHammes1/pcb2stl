import io
import re
import zipfile
from pathlib import Path

import pytest
import trimesh
from fastapi.testclient import TestClient

from pcb2stl.api import create_app

GERBER = (Path(__file__).resolve().parents[1] / "fixtures" / "sample.gbr").read_bytes()
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" '
    b'viewBox="0 0 20 10"><rect x="2" y="2" width="6" height="4" fill="black"/></svg>'
)
EMPTY_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"></svg>'

client = TestClient(create_app())


def test_convert_gerber_returns_a_watertight_stl_attachment():
    response = client.post(
        "/api/convert",
        files={"file": ("board.gbr", GERBER, "application/octet-stream")},
        data={"height_mm": "0.2"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "model/stl"
    assert "board.stl" in response.headers["content-disposition"]
    mesh = trimesh.load(io.BytesIO(response.content), file_type="stl")
    assert mesh.is_watertight


def test_convert_svg_respects_height():
    response = client.post(
        "/api/convert",
        files={"file": ("art.svg", SVG, "image/svg+xml")},
        data={"height_mm": "0.3"},
    )
    assert response.status_code == 200
    mesh = trimesh.load(io.BytesIO(response.content), file_type="stl")
    assert mesh.bounds[1][2] - mesh.bounds[0][2] == pytest.approx(0.3, abs=1e-5)


def test_convert_double_returns_a_zip_of_two_watertight_stls():
    response = client.post(
        "/api/convert-double",
        files={
            "top": ("top.gbr", GERBER, "application/octet-stream"),
            "bottom": ("bottom.gbr", GERBER, "application/octet-stream"),
        },
        data={"height_mm": "0.2"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert set(archive.namelist()) == {"top.stl", "bottom-mirrored.stl"}
    for name in archive.namelist():
        mesh = trimesh.load(io.BytesIO(archive.read(name)), file_type="stl")
        assert mesh.is_watertight


def test_gcode_endpoint_returns_pen_plotter_program():
    response = client.post(
        "/api/gcode",
        files={"file": ("board.gbr", GERBER, "application/octet-stream")},
        data={"pen_width_mm": "0.5", "perimeters": "2"},
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "board.gcode" in response.headers["content-disposition"]
    body = response.text
    assert "G28" in body and "M84" in body
    assert re.search(r"[ \t]E-?\d", body) is None


def test_toolpaths_endpoint_returns_json_strokes_and_stats():
    response = client.post(
        "/api/toolpaths",
        files={"file": ("board.gbr", GERBER, "application/octet-stream")},
        data={"pen_width_mm": "0.5"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stats"]["strokes"] >= 1
    assert len(body["strokes"]) >= 1
    assert len(body["bounds"]) == 4


def test_jig_endpoint_returns_a_watertight_stl():
    response = client.post(
        "/api/jig",
        files={"file": ("board.gbr", GERBER, "application/octet-stream")},
        data={"board_thickness_mm": "1.6", "board_margin_mm": "3"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "model/stl"
    assert "board-jig.stl" in response.headers["content-disposition"]
    mesh = trimesh.load(io.BytesIO(response.content), file_type="stl")
    assert mesh.is_watertight


def test_gcode_endpoint_rejects_invalid_pen_width():
    response = client.post(
        "/api/gcode",
        files={"file": ("board.gbr", GERBER, "application/octet-stream")},
        data={"pen_width_mm": "0"},
    )
    assert response.status_code == 400


def test_unsupported_format_returns_415():
    response = client.post(
        "/api/convert", files={"file": ("board.pdf", b"junk", "application/octet-stream")}
    )
    assert response.status_code == 415


def test_input_without_copper_returns_422():
    response = client.post(
        "/api/convert", files={"file": ("empty.svg", EMPTY_SVG, "image/svg+xml")}
    )
    assert response.status_code == 422


def test_nonpositive_height_returns_400():
    response = client.post(
        "/api/convert",
        files={"file": ("board.gbr", GERBER, "application/octet-stream")},
        data={"height_mm": "0"},
    )
    assert response.status_code == 400


def test_formats_endpoint_lists_inputs():
    body = client.get("/api/formats").json()
    assert "svg" in body["extensions"] and "gbr" in body["extensions"]


MALFORMED_GERBER = b"%FSLAX46Y46*%\n%MOMM*%\n%ADD10R*%\nM02*\n"


def test_malformed_gerber_returns_400():
    response = client.post(
        "/api/convert", files={"file": ("board.gbr", MALFORMED_GERBER, "application/octet-stream")}
    )
    assert response.status_code == 400


def test_binary_garbage_returns_400():
    response = client.post(
        "/api/convert", files={"file": ("board.gbr", bytes(range(256)), "application/octet-stream")}
    )
    assert response.status_code == 400


def test_oversized_upload_is_rejected_with_413(monkeypatch):
    import pcb2stl.api as api_module

    monkeypatch.setattr(api_module, "_MAX_UPLOAD_BYTES", 8)
    response = client.post(
        "/api/convert", files={"file": ("board.gbr", GERBER, "application/octet-stream")}
    )
    assert response.status_code == 413


def test_root_serves_the_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "pcb2stl" in response.text and 'id="viewer"' in response.text


def test_frontend_module_is_served():
    response = client.get("/app.js")
    assert response.status_code == 200
    assert "Viewer" in response.text
