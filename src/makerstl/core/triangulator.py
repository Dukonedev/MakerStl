"""Triangulator: converts 2D polygon contours to triangulated meshes.

Uses Mapbox Earcut for clean ear-clipping triangulation.
No interior Steiner points — only boundary vertices are used.
Handles MultiPolygon (self-intersecting paths, evenodd fill-rule).
"""

from __future__ import annotations

from dataclasses import dataclass

import mapbox_earcut as earcut
import numpy as np
from shapely.geometry import Polygon, MultiPolygon


@dataclass
class TriangulatedMesh:
    """Result of triangulating a 2D contour."""

    vertices: np.ndarray  # (N, 3) float64 — Z=0 for flat mesh
    faces: np.ndarray     # (M, 3) int32 — triangle indices
    vertex_normals: np.ndarray | None = None  # (N, 3) optional


def _clean_geometry(verts: np.ndarray) -> Polygon | MultiPolygon | None:
    """Create clean Shapely geometry, resolving self-intersections."""
    if len(verts) < 3:
        return None
    try:
        ring = verts
        if not np.allclose(ring[0], ring[-1]):
            ring = np.vstack([ring, ring[0:1]])
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return None
        if isinstance(poly, (Polygon, MultiPolygon)):
            return poly
        return None
    except Exception:
        return None


def _earcut_single_polygon(polygon: Polygon) -> tuple[np.ndarray, np.ndarray]:
    """Triangulate a single Polygon using earcut.

    Returns vertices (N,2) and faces (M,3).
    Only boundary vertices are used — no interior points added.
    """
    exterior = np.array(polygon.exterior.coords[:-1], dtype=np.float64)
    n_ext = len(exterior)

    # Build flat vertex array: [exterior_ring, hole1_ring, hole2_ring, ...]
    rings = [exterior]
    ring_end_indices = [n_ext]

    for interior in polygon.interiors:
        hole = np.array(interior.coords[:-1], dtype=np.float64)
        rings.append(hole)
        ring_end_indices.append(ring_end_indices[-1] + len(hole))

    vertices = np.vstack(rings)

    # earcut.triangulate_float64 returns flat triangle index list
    rings_arr = np.array(ring_end_indices, dtype=np.uint32)
    triangles = earcut.triangulate_float64(vertices, rings_arr)

    if triangles is None or len(triangles) == 0:
        return vertices, np.zeros((0, 3), dtype=np.int32)

    faces = np.array(triangles, dtype=np.int32).reshape(-1, 3)
    return vertices, faces


def _merge_triangulations(
    parts: list[tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray]:
    """Merge multiple triangulated parts into one mesh."""
    all_verts = []
    all_faces = []
    offset = 0

    for verts, faces in parts:
        all_verts.append(verts)
        all_faces.append(faces + offset)
        offset += len(verts)

    if not all_verts:
        return np.zeros((0, 2)), np.zeros((0, 3), dtype=np.int32)

    return np.vstack(all_verts), np.vstack(all_faces)


def _triangulate_geometry(
    geom,
) -> tuple[np.ndarray, np.ndarray]:
    """Triangulate a Polygon or MultiPolygon."""
    if isinstance(geom, MultiPolygon):
        parts = []
        for poly in geom.geoms:
            if poly.is_empty:
                continue
            v, f = _earcut_single_polygon(poly)
            if len(f) > 0:
                parts.append((v, f))
        if not parts:
            return np.zeros((0, 2)), np.zeros((0, 3), dtype=np.int32)
        return _merge_triangulations(parts)

    elif isinstance(geom, Polygon):
        return _earcut_single_polygon(geom)

    return np.zeros((0, 2)), np.zeros((0, 3), dtype=np.int32)


def triangulate_layer(
    layer_verts: np.ndarray,
    quality: float = 20.0,
    max_area: float | None = None,
    tolerance: float = 0.1,
    hole_verts: list[np.ndarray] | None = None,
) -> TriangulatedMesh | None:
    """Triangulate a single 2D layer.

    Uses earcut for clean triangulation with no interior Steiner points.
    Handles compound paths with holes via hole_verts parameter.
    """
    if len(layer_verts) < 3:
        return None

    # build Shapely polygon with holes if provided
    if hole_verts:
        ring = layer_verts
        if not np.allclose(ring[0], ring[-1]):
            ring = np.vstack([ring, ring[0:1]])
        interior_rings = []
        for hv in hole_verts:
            hr = hv
            if not np.allclose(hr[0], hr[-1]):
                hr = np.vstack([hr, hr[0:1]])
            interior_rings.append(hr)
        geom = Polygon(ring, interior_rings)
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            return None
    else:
        geom = _clean_geometry(layer_verts)
        if geom is None:
            return None
        if tolerance > 0:
            simplified = geom.simplify(tolerance, preserve_topology=True)
            if not simplified.is_empty and isinstance(simplified, (Polygon, MultiPolygon)):
                geom = simplified

    verts_2d, faces = _triangulate_geometry(geom)

    if len(faces) == 0:
        return None

    verts_3d = np.column_stack([
        verts_2d[:, 0],
        verts_2d[:, 1],
        np.zeros(len(verts_2d)),
    ])

    return TriangulatedMesh(
        vertices=verts_3d,
        faces=faces,
    )


def triangulate_layers(
    layers: list[tuple[str, np.ndarray]],
    quality: float = 20.0,
    max_area: float | None = None,
    tolerance: float = 0.1,
    hole_data: dict[str, list[np.ndarray]] | None = None,
) -> dict[str, TriangulatedMesh]:
    """Triangulate multiple layers."""
    results = {}
    for layer_id, verts in layers:
        holes = hole_data.get(layer_id) if hole_data else None
        mesh = triangulate_layer(layer_verts=verts, tolerance=tolerance, hole_verts=holes)
        if mesh is not None:
            results[layer_id] = mesh
    return results
