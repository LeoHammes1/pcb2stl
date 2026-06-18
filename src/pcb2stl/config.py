from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


# Upload + output size ceilings (bytes).
MAX_UPLOAD_BYTES = _int("PCB2STL_MAX_UPLOAD_BYTES", 16 * 1024 * 1024)
MAX_OUTPUT_BYTES = _int("PCB2STL_MAX_OUTPUT_BYTES", 64 * 1024 * 1024)

# Conversion process pool: workers per pod, max simultaneous jobs, hard wall-clock.
POOL_WORKERS = _int("PCB2STL_POOL_WORKERS", 2)
MAX_CONCURRENT = _int("PCB2STL_MAX_CONCURRENT", 2)
CONVERT_TIMEOUT_S = _float("PCB2STL_CONVERT_TIMEOUT_S", 25.0)

# Geometry-complexity caps (DoS guard the byte cap misses).
MAX_VERTICES = _int("PCB2STL_MAX_VERTICES", 500_000)
MAX_POLYGONS = _int("PCB2STL_MAX_POLYGONS", 50_000)
MAX_EXTENT_MM = _float("PCB2STL_MAX_EXTENT_MM", 1000.0)

# CORS: which origins may call the API from a browser.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "PCB2STL_ALLOWED_ORIGINS",
        "https://pcb2stl.online,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]

# Run conversions inline instead of in the pool (tests only).
INLINE = os.environ.get("PCB2STL_INLINE") == "1"
