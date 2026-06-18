from __future__ import annotations

from .domain import ConversionParams
from .meshing import ManifoldMesher, Mesher
from .parsing.base import ParserResolver
from .parsing.gerber import GerberParser
from .parsing.svg import SvgParser

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
        parser = self._resolver.resolve(filename)
        try:
            drawing = parser.parse(data)
        except Exception as exc:
            raise ParseError(filename, exc) from exc
        if drawing.is_empty:
            raise EmptyDrawingError(filename)
        return self._mesher.mesh(drawing, params)


def default_service() -> ConversionService:
    gerber, svg = GerberParser(), SvgParser()
    parsers = {ext: gerber for ext in _GERBER_EXTENSIONS}
    parsers["svg"] = svg
    return ConversionService(ParserResolver(parsers), ManifoldMesher())
