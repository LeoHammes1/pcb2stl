from __future__ import annotations

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
        try:
            params = ConversionParams(height_mm=height_mm, mirror=mirror)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if file.size is not None and file.size > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="file too large (max 16 MB)")
        data = await file.read()
        stl = _run(service, file.filename or "", data, params)
        download = f"{Path(file.filename or 'board').stem}.stl"
        return Response(
            content=stl,
            media_type="model/stl",
            headers={"Content-Disposition": f'attachment; filename="{download}"'},
        )

    if _WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")

    return app


def _run(service: ConversionService, filename: str, data: bytes, params: ConversionParams) -> bytes:
    try:
        return service.convert(filename, data, params)
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except EmptyDrawingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"could not parse input: {exc}") from exc


app = create_app()
