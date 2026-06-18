from __future__ import annotations

from dataclasses import replace

from . import config
from .domain import ConversionParams, Drawing, JigParams, PenParams
from .gcode import render_gcode
from .jig import build_jig_stl
from .meshing import ManifoldMesher, Mesher
from .parsing.base import ParserResolver
from .parsing.dxf import DxfParser
from .parsing.gerber import GerberParser
from .parsing.svg import SvgParser
from .registration import combined_bounds, registration_marks
from .toolpaths import generate_toolpaths, path_stats, place_paths

_GERBER_EXTENSIONS = ("gbr", "ger", "gtl", "gbl", "gto", "gbo", "gko", "gm1", "art")


class EmptyDrawingError(ValueError):
    def __init__(self, filename: str) -> None:
        super().__init__(f"no copper geometry found in {filename!r}")
        self.filename = filename


class ParseError(ValueError):
    def __init__(self, filename: str, cause: Exception) -> None:
        super().__init__(f"could not parse {filename!r}: {cause}")
        self.filename = filename


class ComplexityError(ValueError):
    """The parsed geometry exceeds the configured vertex/polygon/extent caps."""


class OutputTooLargeError(ValueError):
    """The produced mesh exceeds the configured output-size ceiling."""


class ConversionService:
    def __init__(self, resolver: ParserResolver, mesher: Mesher) -> None:
        self._resolver = resolver
        self._mesher = mesher

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self._resolver.extensions

    def convert(self, filename: str, data: bytes, params: ConversionParams) -> bytes:
        return _capped(self._mesher.mesh(self._parse(filename, data), params))

    def convert_double_sided(
        self,
        top: tuple[str, bytes],
        bottom: tuple[str, bytes],
        params: ConversionParams,
    ) -> tuple[bytes, bytes]:
        """Mesh both copper layers sharing one set of registration fiducials; the
        bottom is mirrored so it draws correctly once the board is flipped."""
        top_drawing = self._parse(*top)
        bottom_drawing = self._parse(*bottom)
        marks = registration_marks(combined_bounds(top_drawing, bottom_drawing))
        top_stl = self._mesher.mesh(_with(top_drawing, marks), replace(params, mirror=False))
        bottom_stl = self._mesher.mesh(_with(bottom_drawing, marks), replace(params, mirror=True))
        return _capped(top_stl), _capped(bottom_stl)

    def convert_to_gcode(self, filename: str, data: bytes, pen: PenParams) -> str:
        """Skip the slicer: emit pen-plotter G-code straight from the copper."""
        drawing = self._parse(filename, data)
        return render_gcode(generate_toolpaths(drawing, pen), pen)

    def toolpath_preview(self, filename: str, data: bytes, pen: PenParams) -> dict:
        """The placed pen strokes (bed coordinates) plus stats, for the 3D preview."""
        drawing = self._parse(filename, data)
        paths = generate_toolpaths(drawing, pen)
        placed = place_paths(
            paths, pen.origin_x_mm + pen.board_margin_mm, pen.origin_y_mm + pen.board_margin_mm
        )
        count, draw_mm, travel_mm = path_stats(placed)
        xs = [x for path in placed for x, _ in path]
        ys = [y for path in placed for _, y in path]
        bounds = [min(xs), min(ys), max(xs), max(ys)] if xs else [0.0, 0.0, 0.0, 0.0]
        return {
            "strokes": [[[round(x, 4), round(y, 4)] for x, y in path] for path in placed],
            "stats": {"strokes": count, "draw_mm": round(draw_mm, 1), "travel_mm": round(travel_mm, 1)},
            "bounds": [round(b, 4) for b in bounds],
            "origin": [round(pen.origin_x_mm, 4), round(pen.origin_y_mm, 4)],
        }

    def make_jig(self, filename: str, data: bytes, jig: JigParams) -> bytes:
        """A printable corner jig sized to the board, to seat it at the work origin."""
        minx, miny, maxx, maxy = self._parse(filename, data).bounds
        return _capped(build_jig_stl(maxx - minx, maxy - miny, jig))

    def _parse(self, filename: str, data: bytes) -> Drawing:
        parser = self._resolver.resolve(filename)
        try:
            drawing = parser.parse(data)
        except Exception as exc:
            raise ParseError(filename, exc) from exc
        if drawing.is_empty:
            raise EmptyDrawingError(filename)
        _check_complexity(drawing)
        return drawing


def _check_complexity(drawing: Drawing) -> None:
    vertices = sum(len(p.exterior) + sum(len(h) for h in p.holes) for p in drawing.polygons)
    if len(drawing.polygons) > config.MAX_POLYGONS or vertices > config.MAX_VERTICES:
        raise ComplexityError("geometry has too many polygons or vertices")
    minx, miny, maxx, maxy = drawing.bounds
    if max(maxx - minx, maxy - miny) > config.MAX_EXTENT_MM:
        raise ComplexityError("geometry extent exceeds the limit")


def _capped(stl: bytes) -> bytes:
    if len(stl) > config.MAX_OUTPUT_BYTES:
        raise OutputTooLargeError("produced mesh exceeds the output-size ceiling")
    return stl


def _with(drawing: Drawing, marks: tuple) -> Drawing:
    return Drawing(drawing.polygons + marks)


def default_service() -> ConversionService:
    gerber = GerberParser()
    parsers = {ext: gerber for ext in _GERBER_EXTENSIONS}
    parsers["svg"] = SvgParser()
    parsers["dxf"] = DxfParser()
    return ConversionService(ParserResolver(parsers), ManifoldMesher())
