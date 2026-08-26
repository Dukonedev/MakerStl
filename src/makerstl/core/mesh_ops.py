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
    """Ensure all face normals point outward using BFS flood-fill.

    Propagates consistent winding from a seed face through adjacent edges.
    Works correctly for concave shapes (donuts, keychains) where centroid-based
    approaches fail.
    """
    from collections import deque

    n_faces = len(faces)
    if n_faces == 0:
        return faces.copy()

    fixed_faces = faces.copy()

    # build edge-to-face adjacency
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for i, face in enumerate(fixed_faces):
        for j in range(3):
            a, b = int(face[j]), int(face[(j + 1) % 3])
            key = (min(a, b), max(a, b))
            edge_faces.setdefault(key, []).append(i)

    # pick seed: face with highest Z center (most likely top face, normal = +Z)
    face_centers_z = np.array([
        (verts[f[0], 2] + verts[f[1], 2] + verts[f[2], 2]) / 3.0
        for f in fixed_faces
    ])
    seed = int(np.argmax(face_centers_z))

    # check seed winding: normal should point up for highest-Z face
    v0, v1, v2 = verts[fixed_faces[seed][0]], verts[fixed_faces[seed][1]], verts[fixed_faces[seed][2]]
    normal = np.cross(v1 - v0, v2 - v0)
    if normal[2] < 0:
        fixed_faces[seed] = [fixed_faces[seed][0], fixed_faces[seed][2], fixed_faces[seed][1]]

    # BFS: propagate consistent winding to all adjacent faces
    visited = set()
    queue = deque([seed])
    visited.add(seed)

    while queue:
        fi = queue.popleft()
        face_a = fixed_faces[fi]

        for j in range(3):
            a, b = int(face_a[j]), int(face_a[(j + 1) % 3])
            key = (min(a, b), max(a, b))

            for neighbor in edge_faces.get(key, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)

                face_b = fixed_faces[neighbor]
                b_indices = [int(face_b[k]) for k in range(3)]
                try:
                    idx_a = b_indices.index(a)
                    idx_b = b_indices.index(b)
                except ValueError:
                    continue

                # same direction (a→b in both) = inconsistent winding → flip
                if (idx_b - idx_a) % 3 == 1:
                    fixed_faces[neighbor] = [face_b[0], face_b[2], face_b[1]]

                queue.append(neighbor)

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
