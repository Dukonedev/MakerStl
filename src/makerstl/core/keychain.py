"""Keychain generator: produces LayerState objects from parametric config.

Pure geometry module — zero Qt imports. Generates multi-layer keychains
(capsule or outline contour base, text, ring) as standard LayerState objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import Polygon

from ..core.extruder import ExtrusionParams
from ..core.quality import QualitySettings
from ..core.shapes import make_capsule, make_outline_contour, make_ring
from ..core.svg_parser import SvgLayer
from ..core.text import text_to_vertices, _signed_area_2d
from ..core.triangulator import TriangulatedMesh, triangulate_layer
from ..models.project import LayerState


@dataclass
class KeychainConfig:
    """All parameters for keychain generation."""

    text: str = "HELLO"
    font_name: str = "Arial"
    font_size: float = 10.0
    font_scale_x: float = 1.0
    letter_spacing: float = 0.0
    text_depth: float = 0.8
    text_color: tuple[int, int, int] = (0, 0, 0)

    base_shape: str = "outline"  # "outline" | "capsule"
    base_thickness: float = 2.0
    base_color: tuple[int, int, int] = (200, 200, 200)
    outline_size: float = 2.0
    edge_bevel: float = 0.3
    bevel_segments: int = 3

    show_ring: bool = True
    ring_outer_diameter: float = 8.0
    ring_thickness: float = 2.0
    ring_position: float = 0.0  # 0-1 along perimeter (0 = top center)
    ring_overlap: float = 1.5
    ring_color: tuple[int, int, int] = (180, 180, 180)

    show_second_outline: bool = False
    second_outline_offset: float = 3.0
    second_outline_height: float = 1.0
    second_outline_color: tuple[int, int, int] = (160, 160, 160)


def _perimeter_position(
    verts: np.ndarray,
    t: float,
) -> tuple[float, float, float, float]:
    """Get position and tangent at parameter t (0-1) along polygon perimeter.

    Returns (px, py, tx, ty) — position and unit tangent direction.
    """
    # close the polygon
    closed = np.vstack([verts, verts[0:1]])
    diffs = np.diff(closed, axis=0)
    seg_lens = np.linalg.norm(diffs, axis=1)
    total_len = seg_lens.sum()

    if total_len < 1e-9:
        cx, cy = verts.mean(axis=0)
        return cx, cy + verts[:, 1].max(), 1.0, 0.0

    target_dist = t * total_len
    cumulative = 0.0

    for i in range(len(seg_lens)):
        if cumulative + seg_lens[i] >= target_dist:
            frac = (target_dist - cumulative) / seg_lens[i] if seg_lens[i] > 1e-9 else 0.0
            px = closed[i, 0] + diffs[i, 0] * frac
            py = closed[i, 1] + diffs[i, 1] * frac
            tx = diffs[i, 0] / seg_lens[i]
            ty = diffs[i, 1] / seg_lens[i]
            return px, py, tx, ty
        cumulative += seg_lens[i]

    px, py = closed[-2]
    tx, ty = diffs[-1]
    length = np.sqrt(tx * tx + ty * ty)
    if length > 1e-9:
        tx /= length
        ty /= length
    return px, py, tx, ty


def generate_keychain(
    config: KeychainConfig,
    quality: QualitySettings | None = None,
) -> list[LayerState]:
    """Generate a keychain as a list of LayerState objects.

    Each returned LayerState has a populated svg_layer, triangulated_mesh,
    and extrusion_params — ready for the standard extrusion pipeline.
    """
    if quality is None:
        quality = QualitySettings()

    result: list[LayerState] = []

    # --- Step 1: render text to 2D polygons ---
    text_polys = text_to_vertices(
        config.text,
        font_name=config.font_name,
        font_size=config.font_size,
        spacing=config.letter_spacing,
        tolerance=quality.tolerance,
        dpi=quality.text_dpi,
        text_tolerance=quality.text_tolerance,
        font_scale_x=config.font_scale_x,
    )

    if not text_polys:
        return result

    # compute text bounding box
    all_x, all_y = [], []
    for outer, _ in text_polys:
        all_x.extend([outer[:, 0].min(), outer[:, 0].max()])
        all_y.extend([outer[:, 1].min(), outer[:, 1].max()])
    text_min_x, text_max_x = min(all_x), max(all_x)
    text_min_y, text_max_y = min(all_y), max(all_y)
    text_w = text_max_x - text_min_x
    text_h = text_max_y - text_min_y
    text_cx = (text_min_x + text_max_x) / 2
    text_cy = (text_min_y + text_max_y) / 2

    # --- Step 2: create base shape ---
    margin = config.outline_size + 2.0
    base_outer: np.ndarray | None = None
    base_holes: list[np.ndarray] = []

    if config.base_shape == "capsule":
        cap_w = text_w + margin * 2
        cap_h = text_h + margin * 2
        cap_w = max(cap_w, cap_h * 1.2)
        base_outer = make_capsule(
            width=cap_w,
            height=cap_h,
            segments=quality.circle_segments,
            cx=text_cx,
            cy=text_cy,
        )
    else:
        # outline contour: merge text polygons, then buffer
        all_outers = [o for o, _ in text_polys]
        all_holes = [h for _, h in text_polys]
        base_outer, base_holes = make_outline_contour(
            all_outers,
            hole_verts_list=all_holes if any(all_holes) else None,
            outline_size=config.outline_size,
            resolution=quality.circle_segments,
        )

    if base_outer is None or len(base_outer) < 3:
        return result

    # --- Step 3: ring (optional, added FIRST so base is last = z=0) ---
    if config.show_ring and config.ring_outer_diameter > 0:
        px, py, tx, ty = _perimeter_position(base_outer, config.ring_position)

        # normal outward (perpendicular to tangent, pointing away from centroid)
        nx, ny = -ty, tx
        base_cx = base_outer[:, 0].mean()
        base_cy = base_outer[:, 1].mean()
        to_center_x = base_cx - px
        to_center_y = base_cy - py
        if nx * to_center_x + ny * to_center_y > 0:
            nx, ny = -nx, -ny

        ring_cx = px + nx * (config.ring_outer_diameter / 2 - config.ring_overlap)
        ring_cy = py + ny * (config.ring_outer_diameter / 2 - config.ring_overlap)

        ring_outer, ring_inner = make_ring(
            outer_diameter=config.ring_outer_diameter,
            thickness=config.ring_thickness,
            segments=quality.circle_segments,
            cx=ring_cx,
            cy=ring_cy,
        )

        ring_svg = SvgLayer(
            id="keychain_ring",
            name="Ring",
            vertices=ring_outer,
            color=config.ring_color,
            hole_verts=[ring_inner],
        )
        ring_mesh = triangulate_layer(
            ring_outer,
            tolerance=quality.tolerance,
            hole_verts=[ring_inner],
        )
        ring_params = ExtrusionParams(
            height=config.base_thickness,
            bevel_radius=config.edge_bevel,
            bevel_segments=config.bevel_segments,
        )
        result.append(LayerState(
            svg_layer=ring_svg,
            triangulated_mesh=ring_mesh,
            extrusion_params=ring_params,
            color=config.ring_color,
            is_ring=True,
            ring_outer_d=config.ring_outer_diameter,
            ring_thickness=config.ring_thickness,
        ))

    # --- Step 4: second outline / border rim (optional) ---
    if config.show_second_outline:
        from shapely.geometry import Polygon as ShapelyPolygon

        try:
            base_poly = ShapelyPolygon(base_outer.tolist())
            if not base_poly.is_valid:
                base_poly = base_poly.buffer(0)
            # inset inward to create the inner edge of the border
            inner_contour = base_poly.buffer(
                -config.second_outline_offset,
                resolution=quality.circle_segments,
                join_style=1,
            )
            if inner_contour.is_empty:
                inner_contour = None
            else:
                from shapely.geometry import MultiPolygon as MP
                if isinstance(inner_contour, MP):
                    inner_contour = max(inner_contour.geoms, key=lambda p: p.area)
        except Exception:
            inner_contour = None

        if inner_contour is not None and not inner_contour.is_empty:
            # outline = base minus inner contour = border ring along base edge
            outline_poly = base_poly.difference(inner_contour)
            if outline_poly.is_empty:
                outline_poly = None
        else:
            outline_poly = None

        if outline_poly is not None and not outline_poly.is_empty:
            # extract exterior + holes from the outline polygon
            from shapely.geometry import MultiPolygon as MP
            if isinstance(outline_poly, MP):
                # take the largest piece
                outline_poly = max(outline_poly.geoms, key=lambda p: p.area)

            second_outer = np.array(
                outline_poly.exterior.coords[:-1], dtype=np.float64
            )
            if _signed_area_2d(second_outer) < 0:
                second_outer = second_outer[::-1].copy()

            second_holes = []
            for interior in outline_poly.interiors:
                hole_pts = np.array(interior.coords[:-1], dtype=np.float64)
                if len(hole_pts) >= 3:
                    if _signed_area_2d(hole_pts) > 0:
                        hole_pts = hole_pts[::-1].copy()
                    second_holes.append(hole_pts)

            second_svg = SvgLayer(
                id="keychain_second_outline",
                name="Second Outline",
                vertices=second_outer,
                color=config.second_outline_color,
                hole_verts=second_holes,
            )
            second_mesh = triangulate_layer(
                second_outer,
                tolerance=quality.tolerance,
                hole_verts=second_holes if second_holes else None,
            )
            second_params = ExtrusionParams(
                height=config.second_outline_height,
                z_offset=config.base_thickness,
                bevel_radius=config.edge_bevel * 0.5,
                bevel_segments=config.bevel_segments,
            )
            result.append(LayerState(
                svg_layer=second_svg,
                triangulated_mesh=second_mesh,
                extrusion_params=second_params,
                color=config.second_outline_color,
            ))

    # --- Step 5: text layer(s) ---
    text_z = config.base_thickness
    if config.show_second_outline:
        text_z += config.second_outline_height

    for i, (outer, holes) in enumerate(text_polys):
        text_svg = SvgLayer(
            id=f"keychain_text_{i}",
            name=f"Text {i}",
            vertices=outer,
            color=config.text_color,
            hole_verts=holes,
        )
        text_mesh = triangulate_layer(
            outer,
            tolerance=quality.tolerance,
            hole_verts=holes if holes else None,
        )
        text_params = ExtrusionParams(
            height=config.text_depth,
            z_offset=text_z,
        )
        result.append(LayerState(
            svg_layer=text_svg,
            triangulated_mesh=text_mesh,
            extrusion_params=text_params,
            color=config.text_color,
        ))

    # --- Step 6: base layer (LAST — must be last visible for z=0) ---
    base_svg = SvgLayer(
        id="keychain_base",
        name="Base",
        vertices=base_outer,
        color=config.base_color,
        hole_verts=base_holes,
    )
    base_mesh = triangulate_layer(
        base_outer,
        tolerance=quality.tolerance,
        hole_verts=base_holes if base_holes else None,
    )
    base_params = ExtrusionParams(
        height=config.base_thickness,
        bevel_radius=config.edge_bevel,
        bevel_segments=config.bevel_segments,
    )
    result.append(LayerState(
        svg_layer=base_svg,
        triangulated_mesh=base_mesh,
        extrusion_params=base_params,
        color=config.base_color,
    ))

    return result
