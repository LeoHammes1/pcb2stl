from __future__ import annotations

import math

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry

from .domain import Drawing, PenParams

Polyline = tuple[tuple[float, float], ...]
Stroke = tuple[str, Polyline]  # ('perimeter' | 'fill', points)


def generate_toolpaths(drawing: Drawing, pen: PenParams) -> list[Polyline]:
    """Turn filled copper into pen strokes: concentric perimeters plus a zig-zag
    fill, so the drawn resist covers each region solidly."""
    return [points for _, points in tagged_toolpaths(drawing, pen)]


def tagged_toolpaths(drawing: Drawing, pen: PenParams) -> list[Stroke]:
    """Strokes that keep their kind ('perimeter'/'fill'), for the coloured preview."""
    strokes: list[Stroke] = []
    for polygon in drawing.polygons:
        shape = ShapelyPolygon(polygon.exterior, polygon.holes)
        strokes.extend(_paths_for(shape, pen))
    if pen.mirror:
        strokes = [(kind, _mirror(points)) for kind, points in strokes]
    return _nearest_neighbour(strokes, lambda s: s[1], lambda s: (s[0], s[1][::-1]))


def optimize_order(paths: list[Polyline]) -> list[Polyline]:
    """Greedy nearest-neighbour ordering with per-stroke direction, to cut the
    pen-up travel between strokes. Drawn geometry is unchanged."""
    return _nearest_neighbour(paths, lambda path: path, lambda path: path[::-1])


def _nearest_neighbour(items, points_of, reverse_of):
    remaining = list(items)
    ordered = []
    cursor = (0.0, 0.0)
    while remaining:
        index, do_reverse, best = 0, False, float("inf")
        for i, item in enumerate(remaining):
            points = points_of(item)
            to_start = _dist2(cursor, points[0])
            to_end = _dist2(cursor, points[-1])
            if to_start < best:
                index, do_reverse, best = i, False, to_start
            if to_end < best:
                index, do_reverse, best = i, True, to_end
        item = remaining.pop(index)
        chosen = reverse_of(item) if do_reverse else item
        ordered.append(chosen)
        cursor = points_of(chosen)[-1]
    return ordered


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def place_paths(paths: list[Polyline], x0: float, y0: float) -> list[Polyline]:
    """Translate the paths so their bottom-left corner sits at (x0, y0)."""
    points = [point for path in paths for point in path]
    if not points:
        return paths
    dx = x0 - min(x for x, _ in points)
    dy = y0 - min(y for _, y in points)
    return [tuple((x + dx, y + dy) for x, y in path) for path in paths]


def path_stats(paths: list[Polyline]) -> tuple[int, float, float]:
    """Return (stroke count, drawn length mm, pen-up travel length mm)."""
    cursor = (0.0, 0.0)
    draw = travel = 0.0
    for path in paths:
        travel += math.hypot(path[0][0] - cursor[0], path[0][1] - cursor[1])
        for a, b in zip(path, path[1:]):
            draw += math.hypot(b[0] - a[0], b[1] - a[1])
        cursor = path[-1]
    return len(paths), draw, travel


def _paths_for(shape: ShapelyPolygon, pen: PenParams) -> list[Stroke]:
    out: list[Stroke] = []
    for index in range(pen.perimeters):
        ring = shape.buffer(-pen.pen_width_mm * (index + 0.5))
        if ring.is_empty:
            break
        out.extend(("perimeter", r) for r in _rings(ring))
    if pen.fill:
        interior = shape.buffer(-pen.pen_width_mm * pen.perimeters)
        out.extend(("fill", f) for f in _fill(interior, pen.pen_width_mm))
    if not out:  # thinner than the pen -- trace the centre line, not the outline (less overdraw)
        out.extend(("perimeter", r) for r in _rings(_spine(shape, pen.pen_width_mm)))
    return out


def _spine(shape: BaseGeometry, pen_width: float) -> BaseGeometry:
    """Largest inward offset that still leaves geometry: a sliver hugging the medial
    axis, so the pen traces the centre line rather than both edges of a thin feature."""
    distance, step = 0.0, pen_width / 2.0
    while step > 0.02:
        if not shape.buffer(-(distance + step)).is_empty:
            distance += step
        step /= 2.0
    inset = shape.buffer(-distance)
    return shape if inset.is_empty else inset


def _rings(geom: BaseGeometry) -> list[Polyline]:
    rings: list[Polyline] = []
    for polygon in _polygons(geom):
        rings.append(tuple(polygon.exterior.coords))
        rings.extend(tuple(interior.coords) for interior in polygon.interiors)
    return rings


def _fill(region: BaseGeometry, spacing: float) -> list[Polyline]:
    out: list[Polyline] = []
    for polygon in _polygons(region):
        out.extend(_chain(_scan_rows(polygon, spacing), polygon))
    return out


def _scan_rows(polygon: ShapelyPolygon, spacing: float) -> list[Polyline]:
    minx, miny, maxx, maxy = polygon.bounds
    rows: list[Polyline] = []
    y = miny + spacing / 2.0
    row = 0
    while y < maxy:
        scan = LineString([(minx - 1.0, y), (maxx + 1.0, y)])
        for segment in _segments(scan.intersection(polygon)):
            rows.append(segment if row % 2 == 0 else segment[::-1])
        y += spacing
        row += 1
    return rows


def _chain(segments: list[Polyline], region: ShapelyPolygon) -> list[Polyline]:
    field = region.buffer(1e-6)
    chains: list[Polyline] = []
    current: list[tuple[float, float]] = []
    for segment in segments:
        link_stays_on_copper = current and field.covers(LineString([current[-1], segment[0]]))
        if link_stays_on_copper:
            current.extend(segment)
        else:
            if current:
                chains.append(tuple(current))
            current = list(segment)
    if current:
        chains.append(tuple(current))
    return chains


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
