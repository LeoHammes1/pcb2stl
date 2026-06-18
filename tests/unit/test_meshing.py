import io

import numpy as np
import pytest
import trimesh

from pcb2stl.domain import ConversionParams, Drawing, Polygon2D
from pcb2stl.meshing import ManifoldMesher


def _solid(stl_bytes):
    mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl")
    assert isinstance(stl_bytes, (bytes, bytearray))
    return mesh


def test_square_extrudes_to_watertight_solid_of_exact_volume():
    square = Polygon2D(((0, 0), (10, 0), (10, 10), (0, 10)))
    stl = ManifoldMesher().mesh(Drawing((square,)), ConversionParams(height_mm=0.2))
    mesh = _solid(stl)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(20.0, rel=1e-4)
    assert np.allclose(mesh.bounds, [[0, 0, 0], [10, 10, 0.2]], atol=1e-4)


def test_hole_is_subtracted_from_the_solid_volume():
    poly = Polygon2D(
        ((0, 0), (20, 0), (20, 20), (0, 20)),
        (((5, 5), (5, 15), (15, 15), (15, 5)),),
    )
    stl = ManifoldMesher().mesh(Drawing((poly,)), ConversionParams(height_mm=1.0))
    mesh = _solid(stl)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(300.0, rel=1e-4)  # (400 - 100) * 1


def test_two_polygons_yield_two_disjoint_bodies():
    a = Polygon2D(((0, 0), (1, 0), (1, 1), (0, 1)))
    b = Polygon2D(((5, 5), (6, 5), (6, 6), (5, 6)))
    stl = ManifoldMesher().mesh(Drawing((a, b)), ConversionParams(height_mm=0.5))
    mesh = _solid(stl)
    assert mesh.is_watertight
    assert mesh.body_count == 2
    assert mesh.volume == pytest.approx(1.0, rel=1e-4)


def test_mirror_reflects_geometry_across_x():
    square = Polygon2D(((0, 0), (4, 0), (4, 2), (0, 2)))
    stl = ManifoldMesher().mesh(Drawing((square,)), ConversionParams(height_mm=0.2, mirror=True))
    mesh = _solid(stl)
    assert mesh.bounds[0][0] == pytest.approx(-4.0, abs=1e-4)
    assert mesh.bounds[1][0] == pytest.approx(0.0, abs=1e-4)


def test_mirror_keeps_holes_and_volume():
    poly = Polygon2D(
        ((0, 0), (20, 0), (20, 20), (0, 20)),
        (((5, 5), (5, 15), (15, 15), (15, 5)),),
    )
    stl = ManifoldMesher().mesh(Drawing((poly,)), ConversionParams(height_mm=1.0, mirror=True))
    mesh = _solid(stl)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(300.0, rel=1e-4)  # hole survives the flip
    assert mesh.bounds[0][0] == pytest.approx(-20.0, abs=1e-4)


def test_empty_drawing_cannot_be_meshed():
    with pytest.raises(ValueError):
        ManifoldMesher().mesh(Drawing(()), ConversionParams())
