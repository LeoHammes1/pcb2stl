from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .domain import ConversionParams
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

    if _WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")

    return app


def _params(height_mm: float, mirror: bool) -> ConversionParams:
    try:
        return ConversionParams(height_mm=height_mm, mirror=mirror)
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
