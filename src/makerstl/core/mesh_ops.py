"""Mesh operations: merge, validate, and optimize meshes."""

from __future__ import annotations

import numpy as np

from .extruder import ExtrudedPart


def merge_parts(parts: list[ExtrudedPart]) -> tuple[np.ndarray, np.ndarray]:
    """Merge multiple parts into a single mesh (for STL export without colors)."""
    all_verts = []
    all_faces = []
    vertex_offset = 0

    for part in parts:
        all_verts.append(part.vertices)
        all_faces.append(part.faces + vertex_offset)
        vertex_offset += len(part.vertices)

    if not all_verts:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int32)

    return np.vstack(all_verts), np.vstack(all_faces)


def compute_normals(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Compute per-vertex normals by averaging face normals (vectorized)."""
    normals = np.zeros_like(verts)

    if len(faces) == 0:
        return normals

    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]

    edge1 = v1 - v0
    edge2 = v2 - v0
    face_normals = np.cross(edge1, edge2)
    lengths = np.linalg.norm(face_normals, axis=1, keepdims=True)
    lengths = np.maximum(lengths, 1e-12)
    face_normals /= lengths

    # accumulate per-vertex using np.add.at
    np.add.at(normals, faces[:, 0], face_normals)
    np.add.at(normals, faces[:, 1], face_normals)
    np.add.at(normals, faces[:, 2], face_normals)

    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.maximum(lengths, 1e-12)
    normals /= lengths

    return normals


def fix_normals_direction(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Ensure all face normals point outward (away from centroid)."""
    centroid = verts.mean(axis=0)
    fixed_faces = faces.copy()

    for i, face in enumerate(fixed_faces):
        v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
        face_center = (v0 + v1 + v2) / 3.0
        normal = np.cross(v1 - v0, v2 - v0)

        # if normal points toward centroid, flip
        if np.dot(normal, face_center - centroid) < 0:
            fixed_faces[i] = [face[0], face[2], face[1]]

    return fixed_faces


def scale_mesh(
    verts: np.ndarray,
    faces: np.ndarray,
    sx: float = 1.0,
    sy: float = 1.0,
    sz: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Scale mesh by given factors."""
    scaled = verts.copy()
    scaled[:, 0] *= sx
    scaled[:, 1] *= sy
    scaled[:, 2] *= sz
    return scaled, faces


def center_mesh(verts: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Center mesh at origin."""
    centroid = verts.mean(axis=0)
    return verts - centroid, faces


def bounding_box(verts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (min_corner, max_corner) of bounding box."""
    return verts.min(axis=0), verts.max(axis=0)


def mesh_stats(verts: np.ndarray, faces: np.ndarray) -> dict:
    """Compute mesh statistics."""
    vmin, vmax = bounding_box(verts)
    dimensions = vmax - vmin
    return {
        "vertex_count": len(verts),
        "face_count": len(faces),
        "dimensions_mm": tuple(dimensions),
        "volume_mm3": _estimate_volume(verts, faces),
        "surface_area_mm2": _estimate_surface_area(verts, faces),
    }


def _estimate_volume(verts: np.ndarray, faces: np.ndarray) -> float:
    """Estimate signed volume using divergence theorem."""
    volume = 0.0
    for face in faces:
        v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
        volume += np.dot(v0, np.cross(v1, v2)) / 6.0
    return abs(volume)


def _estimate_surface_area(verts: np.ndarray, faces: np.ndarray) -> float:
    """Estimate total surface area."""
    area = 0.0
    for face in faces:
        v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
        area += 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0))
    return area
