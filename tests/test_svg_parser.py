"""Tests for SVG parser module."""

import numpy as np
import tempfile
from pathlib import Path

from makerstl.core.svg_parser import SvgParser, SvgLayer, _parse_color


class TestColorParsing:
    def test_hex6(self):
        assert _parse_color("#FF0000") == (255, 0, 0)

    def test_hex3(self):
        assert _parse_color("#F0F") == (255, 0, 255)

    def test_rgb(self):
        assert _parse_color("rgb(100, 200, 50)") == (100, 200, 50)

    def test_named(self):
        assert _parse_color("red") == (255, 0, 0)

    def test_none_fallback(self):
        assert _parse_color("none", (10, 20, 30)) == (10, 20, 30)

    def test_unknown_fallback(self):
        assert _parse_color("notacolor", (50, 50, 50)) == (50, 50, 50)


class TestSvgLayer:
    def test_vertex_count(self):
        verts = np.array([[0, 0], [1, 0], [1, 1]], dtype=np.float64)
        layer = SvgLayer(id="test", name="Test", vertices=verts)
        assert layer.vertex_count == 3
