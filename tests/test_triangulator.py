"""Tests for triangulator module."""

import numpy as np

from makerstl.core.triangulator import triangulate_layer, _clean_geometry


class TestPolygonCleaning:
    def test_simple_triangle(self):
        verts = np.array([[0, 0], [1, 0], [0.5, 1]], dtype=np.float64)
        poly = _clean_geometry(verts)
        assert poly is not None
        assert poly.is_valid

    def test_closed_ring(self):
        verts = np.array([[0, 0], [1, 0], [1, 1], [0, 0]], dtype=np.float64)
        poly = _clean_geometry(verts)
        assert poly is not None

    def test_too_few_verts(self):
        verts = np.array([[0, 0], [1, 0]], dtype=np.float64)
        poly = _clean_geometry(verts)
        assert poly is None


class TestTriangulation:
    def test_simple_square(self):
        verts = np.array([
            [0, 0], [10, 0], [10, 10], [0, 10]
        ], dtype=np.float64)
        mesh = triangulate_layer(verts, tolerance=0)
        assert mesh is not None
        assert len(mesh.faces) >= 2  # at least 2 triangles for a quad
        assert mesh.vertices.shape[1] == 3  # 3D vertices

    def test_degenerate_input(self):
        verts = np.array([[0, 0]], dtype=np.float64)
        mesh = triangulate_layer(verts)
        assert mesh is None
