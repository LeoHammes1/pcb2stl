from __future__ import annotations

from dataclasses import replace

from .domain import ConversionParams, Drawing, JigParams, PenParams
from .gcode import render_gcode
from .jig import build_jig_stl
from .meshing import ManifoldMesher, Mesher
from .parsing.base import ParserResolver
from .parsing.dxf import DxfParser
from .parsing.gerber import GerberParser
from .parsing.svg import SvgParser
from .registration import combined_bounds, registration_marks
from .toolpaths import generate_toolpaths

_GERBER_EXTENSIONS = ("gbr", "ger", "gtl", "gbl", "gto", "gbo", "gko", "gm1", "art")


class EmptyDrawingError(ValueError):
    def __init__(self, filename: str) -> None:
        super().__init__(f"no copper geometry found in {filename!r}")
        self.filename = filename


class ParseError(ValueError):
    def __init__(self, filename: str, cause: Exception) -> None:
        super().__init__(f"could not parse {filename!r}: {cause}")
        self.filename = filename


class ConversionService:
    def __init__(self, resolver: ParserResolver, mesher: Mesher) -> None:
        self._resolver = resolver
        self._mesher = mesher

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self._resolver.extensions

    def convert(self, filename: str, data: bytes, params: ConversionParams) -> bytes:
        return self._mesher.mesh(self._parse(filename, data), params)

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
        return top_stl, bottom_stl

    def convert_to_gcode(self, filename: str, data: bytes, pen: PenParams) -> str:
        """Skip the slicer: emit pen-plotter G-code straight from the copper."""
        drawing = self._parse(filename, data)
        return render_gcode(generate_toolpaths(drawing, pen), pen)

    def make_jig(self, filename: str, data: bytes, jig: JigParams) -> bytes:
        """A printable corner jig sized to the board, to seat it at the work origin."""
        minx, miny, maxx, maxy = self._parse(filename, data).bounds
        return build_jig_stl(maxx - minx, maxy - miny, jig)

    def _parse(self, filename: str, data: bytes) -> Drawing:
        parser = self._resolver.resolve(filename)
        try:
            drawing = parser.parse(data)
        except Exception as exc:
            raise ParseError(filename, exc) from exc
        if drawing.is_empty:
            raise EmptyDrawingError(filename)
        return drawing


def _with(drawing: Drawing, marks: tuple) -> Drawing:
    return Drawing(drawing.polygons + marks)


def default_service() -> ConversionService:
    gerber = GerberParser()
    parsers = {ext: gerber for ext in _GERBER_EXTENSIONS}
    parsers["svg"] = SvgParser()
    parsers["dxf"] = DxfParser()
    return ConversionService(ParserResolver(parsers), ManifoldMesher())
