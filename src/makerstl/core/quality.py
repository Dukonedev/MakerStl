"""Quality settings for mesh generation.

Controls tessellation resolution, triangulation simplification,
and text rendering quality. Four presets (Bassa/Media/Alta/Ultra)
plus individual slider overrides.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualitySettings:
    """All quality-related parameters for mesh generation."""

    curve_resolution: float = 0.5       # mm between sampled points on SVG curves
    tolerance: float = 0.1              # mm — Shapely simplification before triangulation
    circle_segments: int = 32           # polygon segments for circles/ellipses
    text_dpi: int = 300                 # Pillow rasterization resolution
    text_tolerance: float = 0.5         # Douglas-Peucker tolerance for text contours

    # preset name (informational, not used for computation)
    preset: str = "Alta"

    def apply_preset(self, name: str) -> None:
        """Apply a named preset, updating all fields."""
        p = PRESETS.get(name)
        if p is None:
            return
        self.curve_resolution = p.curve_resolution
        self.tolerance = p.tolerance
        self.circle_segments = p.circle_segments
        self.text_dpi = p.text_dpi
        self.text_tolerance = p.text_tolerance
        self.preset = name

    def to_dict(self) -> dict:
        return {
            "curve_resolution": self.curve_resolution,
            "tolerance": self.tolerance,
            "circle_segments": self.circle_segments,
            "text_dpi": self.text_dpi,
            "text_tolerance": self.text_tolerance,
            "preset": self.preset,
        }

    @classmethod
    def from_dict(cls, d: dict) -> QualitySettings:
        return cls(
            curve_resolution=d.get("curve_resolution", 0.5),
            tolerance=d.get("tolerance", 0.1),
            circle_segments=d.get("circle_segments", 32),
            text_dpi=d.get("text_dpi", 300),
            text_tolerance=d.get("text_tolerance", 0.5),
            preset=d.get("preset", "Alta"),
        )


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, QualitySettings] = {
    "Bassa": QualitySettings(
        curve_resolution=2.0,
        tolerance=0.5,
        circle_segments=16,
        text_dpi=150,
        text_tolerance=1.0,
        preset="Bassa",
    ),
    "Media": QualitySettings(
        curve_resolution=1.0,
        tolerance=0.2,
        circle_segments=24,
        text_dpi=200,
        text_tolerance=0.7,
        preset="Media",
    ),
    "Alta": QualitySettings(
        curve_resolution=0.5,
        tolerance=0.1,
        circle_segments=32,
        text_dpi=300,
        text_tolerance=0.5,
        preset="Alta",
    ),
    "Ultra": QualitySettings(
        curve_resolution=0.2,
        tolerance=0.05,
        circle_segments=64,
        text_dpi=600,
        text_tolerance=0.2,
        preset="Ultra",
    ),
}

PRESET_NAMES = list(PRESETS.keys())
