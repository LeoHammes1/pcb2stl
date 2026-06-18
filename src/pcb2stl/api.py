from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .domain import ConversionParams, JigParams, PenParams
from .parsing.base import UnsupportedFormatError
from .service import ConversionService, EmptyDrawingError, default_service

_WEB_DIR = Path(__file__).resolve().parent / "web"
_MAX_UPLOAD_BYTES = 16 * 1024 * 1024


def create_app(service: ConversionService | None = None) -> FastAPI:
    service = service or default_service()
    app = FastAPI(title="pcb2stl", version="0.1.0")

    @app.get("/api/formats")
    def formats() -> dict[str, list[str]]:
        return {"extensions": list(service.supported_extensions)}

    @app.post("/api/convert")
    async def convert(
        file: UploadFile = File(...),
        height_mm: float = Form(0.2),
        mirror: bool = Form(False),
    ) -> Response:
        params = _params(height_mm, mirror)
        _check_size(file)
        data = await file.read()
        stl = _map_errors(lambda: service.convert(file.filename or "", data, params))
        return _stl_response(stl, f"{Path(file.filename or 'board').stem}.stl")

    @app.post("/api/convert-double")
    async def convert_double(
        top: UploadFile = File(...),
        bottom: UploadFile = File(...),
        height_mm: float = Form(0.2),
    ) -> Response:
        params = _params(height_mm, mirror=False)
        _check_size(top)
        _check_size(bottom)
        top_data = await top.read()
        bottom_data = await bottom.read()
        top_stl, bottom_stl = _map_errors(
            lambda: service.convert_double_sided(
                (top.filename or "top", top_data),
                (bottom.filename or "bottom", bottom_data),
                params,
            )
        )
        archive = _zip({"top.stl": top_stl, "bottom-mirrored.stl": bottom_stl})
        return Response(
            content=archive,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="pcb2stl-double-sided.zip"'},
        )

    @app.post("/api/gcode")
    async def gcode(
        file: UploadFile = File(...),
        pen_width_mm: float = Form(0.4),
        perimeters: int = Form(2),
        fill: bool = Form(True),
        mirror: bool = Form(False),
        draw_z_mm: float = Form(0.0),
        travel_z_mm: float = Form(2.0),
        draw_feed: float = Form(1200.0),
        travel_feed: float = Form(3000.0),
        z_feed: float = Form(600.0),
        origin_x_mm: float = Form(10.0),
        origin_y_mm: float = Form(10.0),
        board_margin_mm: float = Form(3.0),
    ) -> Response:
        pen = _pen(
            pen_width_mm, perimeters, fill, mirror, draw_z_mm, travel_z_mm,
            draw_feed, travel_feed, z_feed, origin_x_mm, origin_y_mm, board_margin_mm,
        )
        _check_size(file)
        data = await file.read()
        text = _map_errors(lambda: service.convert_to_gcode(file.filename or "", data, pen))
        download = f"{Path(file.filename or 'board').stem}.gcode"
        return Response(
            content=text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{download}"'},
        )

    @app.post("/api/toolpaths")
    async def toolpaths(
        file: UploadFile = File(...),
        pen_width_mm: float = Form(0.4),
        perimeters: int = Form(2),
        fill: bool = Form(True),
        mirror: bool = Form(False),
        origin_x_mm: float = Form(10.0),
        origin_y_mm: float = Form(10.0),
        board_margin_mm: float = Form(3.0),
    ) -> dict:
        pen = _pen(
            pen_width_mm, perimeters, fill, mirror, 0.0, 2.0,
            1200.0, 3000.0, 600.0, origin_x_mm, origin_y_mm, board_margin_mm,
        )
        _check_size(file)
        data = await file.read()
        return _map_errors(lambda: service.toolpath_preview(file.filename or "", data, pen))

    @app.post("/api/jig")
    async def jig(
        file: UploadFile = File(...),
        board_thickness_mm: float = Form(1.6),
        board_margin_mm: float = Form(3.0),
    ) -> Response:
        params = _jig(board_thickness_mm, board_margin_mm)
        _check_size(file)
        data = await file.read()
        stl = _map_errors(lambda: service.make_jig(file.filename or "", data, params))
        return _stl_response(stl, f"{Path(file.filename or 'board').stem}-jig.stl")

    if _WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")

    return app


def _params(height_mm: float, mirror: bool) -> ConversionParams:
    try:
        return ConversionParams(height_mm=height_mm, mirror=mirror)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _pen(
    pen_width_mm: float,
    perimeters: int,
    fill: bool,
    mirror: bool,
    draw_z_mm: float,
    travel_z_mm: float,
    draw_feed: float,
    travel_feed: float,
    z_feed: float,
    origin_x_mm: float,
    origin_y_mm: float,
    board_margin_mm: float,
) -> PenParams:
    try:
        return PenParams(
            pen_width_mm=pen_width_mm,
            perimeters=perimeters,
            fill=fill,
            mirror=mirror,
            draw_z_mm=draw_z_mm,
            travel_z_mm=travel_z_mm,
            draw_feed=draw_feed,
            travel_feed=travel_feed,
            z_feed=z_feed,
            origin_x_mm=origin_x_mm,
            origin_y_mm=origin_y_mm,
            board_margin_mm=board_margin_mm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _jig(board_thickness_mm: float, board_margin_mm: float) -> JigParams:
    try:
        return JigParams(board_thickness_mm=board_thickness_mm, board_margin_mm=board_margin_mm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _check_size(file: UploadFile) -> None:
    if file.size is not None and file.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 16 MB)")


def _map_errors(action):
    try:
        return action()
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyDrawingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"could not parse input: {exc}") from exc


def _stl_response(stl: bytes, filename: str) -> Response:
    return Response(
        content=stl,
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


app = create_app()
