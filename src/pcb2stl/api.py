from __future__ import annotations

import io
import logging
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, runner, worker
from .domain import ConversionParams, JigParams, PenParams
from .parsing.base import UnsupportedFormatError
from .runner import ConversionTimeout, OverloadError, offload
from .service import (
    ComplexityError,
    ConversionService,
    EmptyDrawingError,
    OutputTooLargeError,
    default_service,
)

_WEB_DIR = Path(__file__).resolve().parent / "web"
_log = logging.getLogger("pcb2stl")

_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)
_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    runner.start_pool()
    try:
        yield
    finally:
        runner.stop_pool()


def create_app(service: ConversionService | None = None) -> FastAPI:
    service = service or default_service()
    app = FastAPI(title="pcb2stl", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def _headers(request, call_next):
        response = await call_next(request)
        response.headers.update(_SECURITY_HEADERS)
        return response

    @app.exception_handler(Exception)
    async def _unhandled(request, exc):
        _log.exception("unhandled error")
        return JSONResponse(status_code=500, content={"detail": "internal error"})

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
        data = await _read(file)
        stl = await _run(worker.convert_job, file.filename or "", data, params)
        return _stl_response(stl, f"{Path(file.filename or 'board').stem}.stl")

    @app.post("/api/convert-double")
    async def convert_double(
        top: UploadFile = File(...),
        bottom: UploadFile = File(...),
        height_mm: float = Form(0.2),
    ) -> Response:
        params = _params(height_mm, mirror=False)
        top_data = await _read(top)
        bottom_data = await _read(bottom)
        top_stl, bottom_stl = await _run(
            worker.double_job,
            top.filename or "top", top_data, bottom.filename or "bottom", bottom_data, params,
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
        lift_mode: str = Form("z"),
        servo_up_deg: float = Form(90.0),
        servo_down_deg: float = Form(40.0),
        servo_dwell_ms: float = Form(300.0),
    ) -> Response:
        pen = _pen(
            pen_width_mm, perimeters, fill, mirror, draw_z_mm, travel_z_mm,
            draw_feed, travel_feed, z_feed, origin_x_mm, origin_y_mm, board_margin_mm,
            lift_mode, servo_up_deg, servo_down_deg, servo_dwell_ms,
        )
        data = await _read(file)
        text = await _run(worker.gcode_job, file.filename or "", data, pen)
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
        data = await _read(file)
        return await _run(worker.toolpaths_job, file.filename or "", data, pen)

    @app.post("/api/jig")
    async def jig(
        file: UploadFile = File(...),
        board_thickness_mm: float = Form(1.6),
        board_margin_mm: float = Form(3.0),
    ) -> Response:
        params = _jig(board_thickness_mm, board_margin_mm)
        data = await _read(file)
        stl = await _run(worker.jig_job, file.filename or "", data, params)
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
    lift_mode: str = "z",
    servo_up_deg: float = 90.0,
    servo_down_deg: float = 40.0,
    servo_dwell_ms: float = 300.0,
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
            lift_mode=lift_mode,
            servo_up_deg=servo_up_deg,
            servo_down_deg=servo_down_deg,
            servo_dwell_ms=servo_dwell_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _jig(board_thickness_mm: float, board_margin_mm: float) -> JigParams:
    try:
        return JigParams(board_thickness_mm=board_thickness_mm, board_margin_mm=board_margin_mm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _read(file: UploadFile) -> bytes:
    if file.size is not None and file.size > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large")
    if b"\x00" in data[:8192]:
        raise HTTPException(status_code=400, detail="unrecognized file content")
    return data


async def _run(fn, *args):
    try:
        return await offload(fn, *args)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=415, detail="unsupported file format") from exc
    except EmptyDrawingError as exc:
        raise HTTPException(status_code=422, detail="no copper geometry found in the file") from exc
    except ComplexityError as exc:
        raise HTTPException(status_code=422, detail="the design is too large or complex to process") from exc
    except OutputTooLargeError as exc:
        raise HTTPException(status_code=413, detail="the generated model is too large") from exc
    except OverloadError as exc:
        raise HTTPException(status_code=503, detail="server busy, retry shortly", headers={"Retry-After": "5"}) from exc
    except ConversionTimeout as exc:
        raise HTTPException(status_code=504, detail="conversion timed out") from exc
    except ValueError as exc:
        _log.warning("rejected upload: %s", exc)
        raise HTTPException(status_code=400, detail="could not read the file - is it a valid Gerber, SVG or DXF?") from exc


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
