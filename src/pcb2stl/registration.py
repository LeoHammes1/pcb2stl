from __future__ import annotations

from shapely.geometry import Point

from .domain import Drawing, Polygon2D
from .merge import merge

_MARGIN_MM = 4.0
_OUTER_RADIUS_MM = 1.2
_INNER_RADIUS_MM = 0.5


def registration_marks(bounds: tuple[float, float, float, float]) -> tuple[Polygon2D, ...]:
    """Two ring fiducials in the side margins, level with the board centre. Drawn on
    both faces so that, drilled through and pinned, the flipped board stays aligned."""
    minx, miny, maxx, maxy = bounds
    mid_y = (miny + maxy) / 2.0
    centers = ((minx - _MARGIN_MM, mid_y), (maxx + _MARGIN_MM, mid_y))
    rings = [
        Point(cx, cy).buffer(_OUTER_RADIUS_MM).difference(Point(cx, cy).buffer(_INNER_RADIUS_MM))
        for cx, cy in centers
    ]
    return merge(rings).polygons


def combined_bounds(*drawings: Drawing) -> tuple[float, float, float, float]:
    boxes = [d.bounds for d in drawings if not d.is_empty]
    if not boxes:
        raise ValueError("no geometry to bound")
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
