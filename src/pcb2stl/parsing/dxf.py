from __future__ import annotations

import io

import ezdxf
from ezdxf import path
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from ..domain import Drawing
from ..merge import merge

_FLATTEN_TOL_MM = 0.05

# $INSUNITS code -> millimetres per drawing unit (common values; default mm).
_MM_PER_UNIT = {0: 1.0, 1: 25.4, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 25.4e-6, 9: 0.0254}


class DxfParser:
    """Parse a DXF into millimetre polygons: closed entities become filled copper,
    polylines carrying a width become traces. Units follow the ``$INSUNITS`` header."""

    def __init__(self, flatten_tol_mm: float = _FLATTEN_TOL_MM) -> None:
        self._tol = flatten_tol_mm

    def parse(self, data: bytes) -> Drawing:
        doc = ezdxf.read(io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="replace"))
        scale = _MM_PER_UNIT.get(int(doc.header.get("$INSUNITS", 0)), 1.0)
        geoms: list[BaseGeometry] = []
        for entity in doc.modelspace():
            geom = self._entity_geometry(entity, scale)
            if geom is not None and not geom.is_empty:
                geoms.append(geom)
        return merge(geoms)

    def _entity_geometry(self, entity, scale: float) -> BaseGeometry | None:
        try:
            outline = path.make_path(entity)
        except (TypeError, ValueError):
            return None
        points = [(v.x * scale, v.y * scale) for v in outline.flattening(self._tol / scale)]
        if len(points) < 2:
            return None
        width = float(entity.dxf.const_width) if entity.dxf.hasattr("const_width") else 0.0
        if width > 0:
            return LineString(points).buffer(width * scale / 2.0)
        if outline.is_closed and len(points) >= 3:
            return ShapelyPolygon(points).buffer(0)
        return None
