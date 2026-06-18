from __future__ import annotations

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from .domain import Drawing, PenParams

Polyline = tuple[tuple[float, float], ...]


def generate_toolpaths(drawing: Drawing, pen: PenParams) -> list[Polyline]:
    """Turn filled copper into pen strokes: concentric perimeters plus a zig-zag
    fill, so the drawn resist covers each region solidly."""
    paths: list[Polyline] = []
    for polygon in drawing.polygons:
        shape = ShapelyPolygon(polygon.exterior, polygon.holes)
        paths.extend(_paths_for(shape, pen))
    return [_mirror(p) for p in paths] if pen.mirror else paths


def _paths_for(shape: ShapelyPolygon, pen: PenParams) -> list[Polyline]:
    out: list[Polyline] = []
    for index in range(pen.perimeters):
        ring = shape.buffer(-pen.pen_width_mm * (index + 0.5))
        if ring.is_empty:
            break
        out.extend(_rings(ring))
    if pen.fill:
        interior = shape.buffer(-pen.pen_width_mm * pen.perimeters)
        out.extend(_fill(interior, pen.pen_width_mm))
    if not out:  # too thin to inset -- trace the outline so the feature is not dropped
        out.extend(_rings(shape))
    return out


def _rings(geom: BaseGeometry) -> list[Polyline]:
    rings: list[Polyline] = []
    for polygon in _polygons(geom):
        rings.append(tuple(polygon.exterior.coords))
        rings.extend(tuple(interior.coords) for interior in polygon.interiors)
    return rings


def _fill(region: BaseGeometry, spacing: float) -> list[Polyline]:
    out: list[Polyline] = []
    for polygon in _polygons(region):
        minx, miny, maxx, maxy = polygon.bounds
        y = miny + spacing / 2.0
        row = 0
        while y < maxy:
            scan = LineString([(minx - 1.0, y), (maxx + 1.0, y)])
            for segment in _segments(scan.intersection(polygon)):
                out.append(segment if row % 2 == 0 else segment[::-1])
            y += spacing
            row += 1
    return out


def _polygons(geom: BaseGeometry) -> list[ShapelyPolygon]:
    if isinstance(geom, ShapelyPolygon):
        return [] if geom.is_empty else [geom]
    if isinstance(geom, MultiPolygon):
        return [p for p in geom.geoms if not p.is_empty]
    return []


def _segments(geom: BaseGeometry) -> list[Polyline]:
    if geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [tuple(geom.coords)] if len(geom.coords) >= 2 else []
    if isinstance(geom, (MultiLineString, GeometryCollection)):
        segments: list[Polyline] = []
        for part in geom.geoms:
            segments.extend(_segments(part))
        return segments
    return []


def _mirror(path: Polyline) -> Polyline:
    return tuple((-x, y) for x, y in path)
