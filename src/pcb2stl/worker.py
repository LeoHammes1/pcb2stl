from __future__ import annotations

import time

from .domain import ConversionParams, JigParams, PenParams
from .service import ConversionService, default_service

_service: ConversionService | None = None


def sleep(seconds: float) -> float:
    """A trivial pool job, to warm workers and exercise the timeout path."""
    time.sleep(seconds)
    return seconds


def _svc() -> ConversionService:
    global _service
    if _service is None:
        _service = default_service()
    return _service


def convert_job(filename: str, data: bytes, params: ConversionParams) -> bytes:
    return _svc().convert(filename, data, params)


def double_job(
    top_name: str, top_data: bytes, bottom_name: str, bottom_data: bytes, params: ConversionParams
) -> tuple[bytes, bytes]:
    return _svc().convert_double_sided((top_name, top_data), (bottom_name, bottom_data), params)


def gcode_job(filename: str, data: bytes, pen: PenParams) -> str:
    return _svc().convert_to_gcode(filename, data, pen)


def toolpaths_job(filename: str, data: bytes, pen: PenParams) -> dict:
    return _svc().toolpath_preview(filename, data, pen)


def jig_job(filename: str, data: bytes, jig: JigParams) -> bytes:
    return _svc().make_jig(filename, data, jig)
