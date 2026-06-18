from __future__ import annotations

import numpy as np
from gerbonara import GerberFile
from gerbonara.graphic_primitives import Arc, ArcPoly, Circle, Line, Rectangle
from gerbonara.utils import MM
from shapely.affinity import rotate
from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from ..domain import Drawing
from ..merge import merge

_ARC_SAMPLES = 24


class GerberParser:
    """Parse a Gerber copper layer into millimetre polygons via gerbonara's
    flattened graphic primitives, honouring dark/clear polarity."""

    def parse(self, data: bytes) -> Drawing:
        gerber = GerberFile.from_string(data.decode("utf-8"))
        dark: list[BaseGeometry] = []
        clear: list[BaseGeometry] = []
        for obj in gerber.objects:
            for primitive in obj.to_primitives(unit=MM):
                geom = _to_shapely(primitive)
                if geom is None or geom.is_empty:
                    continue
                (dark if primitive.polarity_dark else clear).append(geom)
        return merge(dark, clear)


def _to_shapely(primitive) -> BaseGeometry | None:
    if isinstance(primitive, Circle):
        return Point(primitive.x, primitive.y).buffer(primitive.r)
    if isinstance(primitive, Rectangle):
        return _rectangle(primitive)
    if isinstance(primitive, Line):
        return LineString(
            [(primitive.x1, primitive.y1), (primitive.x2, primitive.y2)]
        ).buffer(primitive.width / 2.0)
    if isinstance(primitive, Arc):
        return _arc(primitive).buffer(primitive.width / 2.0)
    if isinstance(primitive, ArcPoly):
        return _arcpoly(primitive)
    return None


def _arcpoly(primitive) -> BaseGeometry:
    points: list[tuple[float, float]] = []
    for start, end, (clockwise, center) in primitive.segments:
        points.append((float(start[0]), float(start[1])))
        if clockwise is not None:
            points.extend(_arc_points(start, end, center, clockwise))
    return ShapelyPolygon(points).buffer(0)


def _arc_points(start, end, center, clockwise) -> list[tuple[float, float]]:
    cx, cy = float(center[0]), float(center[1])
    a0 = np.arctan2(start[1] - cy, start[0] - cx)
    a1 = np.arctan2(end[1] - cy, end[0] - cx)
    if clockwise and a1 >= a0:
        a1 -= 2 * np.pi
    elif not clockwise and a1 <= a0:
        a1 += 2 * np.pi
    radius = float(np.hypot(start[0] - cx, start[1] - cy))
    angles = np.linspace(a0, a1, _ARC_SAMPLES)[1:-1]
    return [(cx + radius * np.cos(a), cy + radius * np.sin(a)) for a in angles]


def _rectangle(primitive) -> BaseGeometry:
    hw, hh = primitive.w / 2.0, primitive.h / 2.0
    box = ShapelyPolygon(
        [
            (primitive.x - hw, primitive.y - hh),
            (primitive.x + hw, primitive.y - hh),
            (primitive.x + hw, primitive.y + hh),
            (primitive.x - hw, primitive.y + hh),
        ]
    )
    angle = float(getattr(primitive, "rotation", 0.0) or 0.0)
    if angle:
        box = rotate(box, np.degrees(angle), origin=(primitive.x, primitive.y))
    return box


def _arc(primitive) -> LineString:
    cx, cy = primitive.cx, primitive.cy
    a0 = np.arctan2(primitive.y1 - cy, primitive.x1 - cx)
    a1 = np.arctan2(primitive.y2 - cy, primitive.x2 - cx)
    radius = float(np.hypot(primitive.x1 - cx, primitive.y1 - cy))
    angles = np.linspace(a0, a1, _ARC_SAMPLES)
    return LineString([(cx + radius * np.cos(a), cy + radius * np.sin(a)) for a in angles])
