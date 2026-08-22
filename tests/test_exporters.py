"""Tests for exporters module."""

import tempfile
import zipfile
from pathlib import Path

import numpy as np

from makerstl.core.extruder import ExtrudedPart
from makerstl.core.exporters import export_stl, export_obj, export_3mf


def _make_test_part() -> ExtrudedPart:
    """Create a simple cube for testing."""
    verts = np.array([
        # bottom
        [0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0],
        # top
        [0, 0, 5], [10, 0, 5], [10, 10, 5], [0, 10, 5],
    ], dtype=np.float64)

    faces = np.array([
        # bottom
        [0, 2, 1], [0, 3, 2],
        # top
        [4, 5, 6], [4, 6, 7],
        # front
        [0, 1, 5], [0, 5, 4],
        # back
        [2, 3, 7], [2, 7, 6],
        # left
        [0, 4, 7], [0, 7, 3],
        # right
        [1, 2, 6], [1, 6, 5],
    ], dtype=np.int32)

    return ExtrudedPart(
        id="test_cube",
        vertices=verts,
        faces=faces,
        color=(255, 0, 0),
        name="Test Cube",
    )


class TestSTLExport:
    def test_binary_stl(self):
        part = _make_test_part()
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            path = Path(f.name)

        result = export_stl([part], path, binary=True)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_ascii_stl(self):
        part = _make_test_part()
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as f:
            path = Path(f.name)

        result = export_stl([part], path, binary=False)
        assert result.exists()
        content = result.read_text()
        assert "solid MakerStl" in content


class TestOBJExport:
    def test_obj_with_mtl(self):
        part = _make_test_part()
        with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as f:
            path = Path(f.name)

        result = export_obj([part], path)
        assert result.exists()
        mtl_path = result.with_suffix(".mtl")
        assert mtl_path.exists()


class Test3MFExport:
    def test_3mf_zip_structure(self):
        part = _make_test_part()
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as f:
            path = Path(f.name)

        result = export_3mf([part], path)
        assert result.exists()

        with zipfile.ZipFile(result) as zf:
            names = zf.namelist()
            assert "[Content_Types].xml" in names
            assert "_rels/.rels" in names
            assert "3D/3dmodel.model" in names

    def test_3mf_has_colors(self):
        part = _make_test_part()
        with tempfile.NamedTemporaryFile(suffix=".3mf", delete=False) as f:
            path = Path(f.name)

        export_3mf([part], path)

        with zipfile.ZipFile(path) as zf:
            model = zf.read("3D/3dmodel.model").decode()
            assert "basematerials" in model
            assert "#FF0000" in model
