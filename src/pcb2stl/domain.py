from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]
Ring = tuple[Point, ...]


@dataclass(frozen=True)
class Polygon2D:
    exterior: Ring
    holes: tuple[Ring, ...] = ()

    def __post_init__(self) -> None:
        if len(self.exterior) < 3:
            raise ValueError("polygon exterior needs at least 3 points")
        for hole in self.holes:
            if len(hole) < 3:
                raise ValueError("polygon hole needs at least 3 points")


@dataclass(frozen=True)
class Drawing:
    """Filled copper geometry, in millimetres."""

    polygons: tuple[Polygon2D, ...]

    @property
    def is_empty(self) -> bool:
        return len(self.polygons) == 0

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        if self.is_empty:
            raise ValueError("empty drawing has no bounds")
        xs = [x for p in self.polygons for x, _ in p.exterior]
        ys = [y for p in self.polygons for _, y in p.exterior]
        return (min(xs), min(ys), max(xs), max(ys))


@dataclass(frozen=True)
class ConversionParams:
    height_mm: float = 0.2
    mirror: bool = False

    def __post_init__(self) -> None:
        if self.height_mm <= 0:
            raise ValueError("height_mm must be positive")


@dataclass(frozen=True)
class PenParams:
    """Pen-plotter toolpath and motion settings (millimetres, mm/min)."""

    pen_width_mm: float = 0.4
    perimeters: int = 2
    fill: bool = True
    mirror: bool = False
    draw_z_mm: float = 0.0
    travel_z_mm: float = 2.0
    draw_feed: float = 1200.0
    travel_feed: float = 3000.0
    z_feed: float = 600.0

    def __post_init__(self) -> None:
        if self.pen_width_mm <= 0:
            raise ValueError("pen_width_mm must be positive")
        if self.perimeters < 1:
            raise ValueError("perimeters must be at least 1")
        if self.travel_z_mm <= self.draw_z_mm:
            raise ValueError("travel_z_mm must be above draw_z_mm")
        if min(self.draw_feed, self.travel_feed, self.z_feed) <= 0:
            raise ValueError("feed rates must be positive")
