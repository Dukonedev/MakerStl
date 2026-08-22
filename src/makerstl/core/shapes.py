"""Shape generators: create 2D polygon vertices for basic geometric shapes."""

from __future__ import annotations

import numpy as np


def make_rect(
    width: float = 10.0,
    height: float = 10.0,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Rectangle centered at (cx, cy)."""
    hw, hh = width / 2, height / 2
    return np.array([
        [cx - hw, cy - hh],
        [cx + hw, cy - hh],
        [cx + hw, cy + hh],
        [cx - hw, cy + hh],
    ], dtype=np.float64)


def make_circle(
    radius: float = 5.0,
    segments: int = 32,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Regular polygon approximating a circle."""
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    return np.column_stack([
        cx + radius * np.cos(angles),
        cy + radius * np.sin(angles),
    ])


def make_ellipse(
    rx: float = 6.0,
    ry: float = 4.0,
    segments: int = 32,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Ellipse centered at (cx, cy)."""
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    return np.column_stack([
        cx + rx * np.cos(angles),
        cy + ry * np.sin(angles),
    ])


def make_triangle(
    size: float = 10.0,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Equilateral triangle centered at (cx, cy), pointing up."""
    h = size * np.sqrt(3) / 2
    return np.array([
        [cx, cy + h * 2 / 3],
        [cx - size / 2, cy - h / 3],
        [cx + size / 2, cy - h / 3],
    ], dtype=np.float64)


def make_star(
    outer_r: float = 5.0,
    inner_r: float = 2.5,
    points: int = 5,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Star shape centered at (cx, cy)."""
    n = points * 2
    angles = np.linspace(-np.pi / 2, -np.pi / 2 + 2 * np.pi, n, endpoint=False)
    radii = np.where(np.arange(n) % 2 == 0, outer_r, inner_r)
    return np.column_stack([
        cx + radii * np.cos(angles),
        cy + radii * np.sin(angles),
    ])


def make_pentagon(
    radius: float = 5.0,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Regular pentagon."""
    angles = np.linspace(-np.pi / 2, -np.pi / 2 + 2 * np.pi, 6, endpoint=True)
    return np.column_stack([
        cx + radius * np.cos(angles),
        cy + radius * np.sin(angles),
    ])


def make_hexagon(
    radius: float = 5.0,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Regular hexagon."""
    angles = np.linspace(0, 2 * np.pi, 7, endpoint=True)
    return np.column_stack([
        cx + radius * np.cos(angles),
        cy + radius * np.sin(angles),
    ])


def make_diamond(
    width: float = 8.0,
    height: float = 12.0,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Diamond/rhombus centered at (cx, cy)."""
    hw, hh = width / 2, height / 2
    return np.array([
        [cx, cy + hh],
        [cx + hw, cy],
        [cx, cy - hh],
        [cx - hw, cy],
    ], dtype=np.float64)


def make_cross(
    arm: float = 3.0,
    length: float = 10.0,
    cx: float = 0.0,
    cy: float = 0.0,
) -> np.ndarray:
    """Plus/cross shape centered at (cx, cy)."""
    hl = length / 2
    ha = arm / 2
    return np.array([
        # top bar
        [cx - ha, cy + hl],
        [cx + ha, cy + hl],
        [cx + ha, cy + ha],
        # right arm
        [cx + hl, cy + ha],
        [cx + hl, cy - ha],
        [cx + ha, cy - ha],
        # bottom bar
        [cx + ha, cy - hl],
        [cx - ha, cy - hl],
        [cx - ha, cy - ha],
        # left arm
        [cx - hl, cy - ha],
        [cx - hl, cy + ha],
        [cx - ha, cy + ha],
    ], dtype=np.float64)


def make_ring(
    outer_diameter: float = 14.0,
    thickness: float = 3.0,
    segments: int = 48,
    cx: float = 0.0,
    cy: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Ring/donut shape for keychains. Returns (outer_verts, inner_hole)."""
    outer_r = outer_diameter / 2
    inner_r = (outer_diameter - thickness) / 2

    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    outer = np.column_stack([cx + outer_r * np.cos(angles), cy + outer_r * np.sin(angles)])
    inner = np.column_stack([cx + inner_r * np.cos(angles), cy + inner_r * np.sin(angles)])
    return outer, inner


SHAPES = {
    "rect": ("Rectangle", make_rect),
    "circle": ("Circle", make_circle),
    "ellipse": ("Ellipse", make_ellipse),
    "triangle": ("Triangle", make_triangle),
    "star": ("Star", make_star),
    "pentagon": ("Pentagon", make_pentagon),
    "hexagon": ("Hexagon", make_hexagon),
    "diamond": ("Diamond", make_diamond),
    "cross": ("Cross", make_cross),
    "ring": ("Ring", make_ring),
}
