from __future__ import annotations

from typing import Iterable

from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.collection import GeometryCollection
from shapely.ops import unary_union

from .domain import Drawing, Polygon2D, Ring


def merge(dark: Iterable[BaseGeometry], clear: Iterable[BaseGeometry] = ()) -> Drawing:
    """Union the additive ``dark`` copper, subtract the ``clear`` regions, and
    normalise the result into non-overlapping :class:`Polygon2D` records."""
    solid = unary_union([g for g in dark if not g.is_empty])
    clear_union = unary_union([g for g in clear if not g.is_empty])
    if not clear_union.is_empty:
        solid = solid.difference(clear_union)
    return Drawing(tuple(_normalise(solid)))


def _normalise(geom: BaseGeometry) -> list[Polygon2D]:
    if isinstance(geom, ShapelyPolygon):
        return [] if geom.is_empty else [_to_polygon2d(geom)]
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        out: list[Polygon2D] = []
        for part in geom.geoms:
            out.extend(_normalise(part))
        return out
    return []


def _to_polygon2d(poly: ShapelyPolygon) -> Polygon2D:
    return Polygon2D(
        _ring(poly.exterior.coords),
        tuple(_ring(interior.coords) for interior in poly.interiors),
    )


def _ring(coords: Iterable[tuple[float, float]]) -> Ring:
    pts = [(float(x), float(y)) for x, y in coords]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return tuple(pts)
