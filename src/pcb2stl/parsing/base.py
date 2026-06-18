from __future__ import annotations

from typing import Mapping, Protocol

from ..domain import Drawing


class Parser(Protocol):
    """Turn input bytes into a normalised :class:`Drawing` in millimetres —
    implementations funnel their raw geometry through ``merge`` so the result is
    always non-overlapping polygons with holes."""

    def parse(self, data: bytes) -> Drawing: ...


class UnsupportedFormatError(ValueError):
    def __init__(self, extension: str) -> None:
        super().__init__(f"unsupported input format: {extension!r}")
        self.extension = extension


class ParserResolver:
    """Selects a :class:`Parser` from a filename extension (the open/closed seam:
    new formats are added by registering a parser, nothing here changes)."""

    def __init__(self, parsers: Mapping[str, Parser]) -> None:
        self._parsers = {ext.lower().lstrip("."): p for ext, p in parsers.items()}

    @property
    def extensions(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers))

    def resolve(self, filename: str) -> Parser:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        try:
            return self._parsers[ext]
        except KeyError:
            raise UnsupportedFormatError(ext) from None
