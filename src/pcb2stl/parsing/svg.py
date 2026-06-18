from __future__ import annotations

import io
import xml.etree.ElementTree as ElementTree
from functools import reduce

import defusedxml.ElementTree as DefusedET
import numpy as np
import svgelements as se
from defusedxml.common import DefusedXmlException
from shapely.geometry import LineString
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from ..domain import Drawing
from ..merge import merge

_MM_PER_INCH = 25.4
_CURVE_SAMPLES = 24

_CURVES = (se.QuadraticBezier, se.CubicBezier, se.Arc)


class SvgParser:
    """Parse an SVG whose filled shapes (and optionally strokes) are the copper.

    Coordinates are read in millimetres (``ppi=25.4`` maps physical/user units to
    mm); curves are flattened by sampling; each shape is filled even-odd."""

    def __init__(self, curve_samples: int = _CURVE_SAMPLES) -> None:
        self._samples = curve_samples

    def parse(self, data: bytes) -> Drawing:
        _reject_unsafe_xml(data)
        svg = se.SVG.parse(io.BytesIO(data), ppi=_MM_PER_INCH)
        geoms: list[BaseGeometry] = []
        for element in svg.elements():
            if isinstance(element, se.Shape):
                geoms.extend(self._shape_geometry(element))
        return merge(geoms)

    def _shape_geometry(self, shape: se.Shape) -> list[BaseGeometry]:
        subpaths = self._subpaths(shape)
        if not subpaths:
            return []
        out: list[BaseGeometry] = []
        if _is_filled(shape):
            rings = [ShapelyPolygon(s).buffer(0) for s in subpaths if len(s) >= 3]
            if rings:
                out.append(_even_odd(rings))
        width = float(shape.stroke_width or 0.0)
        if width > 0 and _is_stroked(shape):
            out.extend(LineString(s).buffer(width / 2.0) for s in subpaths)
        return [g for g in out if not g.is_empty]

    def _subpaths(self, shape: se.Shape) -> list[list[tuple[float, float]]]:
        subpaths: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        for seg in se.Path(shape):
            if isinstance(seg, se.Move):
                _flush(subpaths, current)
                current = [_xy(seg.end)]
            elif isinstance(seg, _CURVES):
                for t in np.linspace(0.0, 1.0, self._samples)[1:]:
                    current.append(_xy(seg.point(t)))
            else:  # Line, Close
                current.append(_xy(seg.end))
        _flush(subpaths, current)
        return subpaths


def _flush(subpaths: list, current: list) -> None:
    if len(current) >= 2:
        subpaths.append(current)


def _xy(point) -> tuple[float, float]:
    return (float(point.x), float(point.y))


def _even_odd(polygons: list[BaseGeometry]) -> BaseGeometry:
    return reduce(lambda a, b: a.symmetric_difference(b), polygons)


def _is_filled(shape: se.Shape) -> bool:
    return str(shape.values.get("fill", "")).lower() != "none"


def _is_stroked(shape: se.Shape) -> bool:
    stroke = str(shape.values.get("stroke", "")).lower()
    return stroke not in ("", "none")


def _reject_unsafe_xml(data: bytes) -> None:
    """Block XXE and entity-expansion (billion-laughs) before svgelements parses.
    Entities and external references are forbidden, but a plain DOCTYPE is allowed
    (KiCad and other tools emit the standard SVG 1.1 DTD reference)."""
    try:
        DefusedET.fromstring(data, forbid_dtd=False, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise ValueError("SVG with entities or external references is not allowed") from exc
    except ElementTree.ParseError as exc:
        raise ValueError("invalid SVG XML") from exc
