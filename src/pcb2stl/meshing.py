from __future__ import annotations

from typing import Protocol

import numpy as np
import trimesh
from manifold3d import CrossSection, FillRule

from .domain import ConversionParams, Drawing


class Mesher(Protocol):
    def mesh(self, drawing: Drawing, params: ConversionParams) -> bytes: ...


def solid_to_stl(solid) -> bytes:
    """Convert a manifold3d solid into watertight binary STL bytes."""
    mesh = solid.to_mesh()
    vertices = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    faces = np.asarray(mesh.tri_verts).astype(np.int64)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False).export(file_type="stl")


class ManifoldMesher:
    """Extrude a 2D drawing into a watertight binary STL via the Manifold kernel."""

    def mesh(self, drawing: Drawing, params: ConversionParams) -> bytes:
        if drawing.is_empty:
            raise ValueError("cannot mesh an empty drawing")
        section = CrossSection(self._contours(drawing, params.mirror), FillRule.EvenOdd)
        return solid_to_stl(section.extrude(params.height_mm))

    @staticmethod
    def _contours(drawing: Drawing, mirror: bool) -> list[list[tuple[float, float]]]:
        flip = -1.0 if mirror else 1.0
        contours: list[list[tuple[float, float]]] = []
        for poly in drawing.polygons:
            contours.append([(flip * x, y) for x, y in poly.exterior])
            for hole in poly.holes:
                contours.append([(flip * x, y) for x, y in hole])
        return contours
