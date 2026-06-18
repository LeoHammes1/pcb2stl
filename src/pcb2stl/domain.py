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
