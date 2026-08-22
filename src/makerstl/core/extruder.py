"""Extruder: creates 3D meshes by extruding 2D triangulated layers.

Supports:
- Parametric extrusion height per layer
- Uniform Z offset for multi-layer stacking
- Chamfer/fillet bevel on edges
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import ConvexHull

from .triangulator import TriangulatedMesh


@dataclass
class ExtrusionParams:
    """Parameters for extruding a single layer."""

    height: float = 5.0
    z_offset: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    chamfer: float = 0.0  # chamfer depth in mm
    translate_x: float = 0.0
    translate_y: float = 0.0


@dataclass
class ExtrudedPart:
    """A fully extruded 3D part."""

    id: str
    vertices: np.ndarray  # (N, 3)
    faces: np.ndarray     # (M, 3)
    color: tuple[int, int, int] = (0, 0, 0)
    name: str = ""
    normals: np.ndarray | None = None  # (N, 3) cached per-vertex normals

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)


def _extrude_face_set(
    verts_2d: np.ndarray,
    faces: np.ndarray,
    height: float,
    z_offset: float,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Extrude a triangulated 2D mesh into a solid 3D object.

    Creates top face, bottom face, and side walls.
    """
    n_base = len(verts_2d)

    # apply scale
    scaled = verts_2d.copy()
    scaled[:, 0] *= scale_x
    scaled[:, 1] *= scale_y

    # bottom face (Z = z_offset)
    bottom = np.column_stack([
        scaled[:, 0],
        scaled[:, 1],
        np.full(n_base, z_offset),
    ])

    # top face (Z = z_offset + height)
    top = np.column_stack([
        scaled[:, 0],
        scaled[:, 1],
        np.full(n_base, z_offset + height),
    ])

    # combine vertices
    verts_3d = np.vstack([bottom, top])

    # bottom faces (reversed winding for outward normals pointing down)
    bottom_faces = faces[:, ::-1].copy()

    # top faces (original winding)
    top_faces = faces.copy() + n_base

    # side walls: find boundary edges
    side_faces = _build_side_walls(verts_2d, n_base, z_offset, height, faces=faces)

    all_faces = np.vstack([bottom_faces, top_faces, side_faces])

    # remove degenerate faces
    valid = (all_faces[:, 0] != all_faces[:, 1]) & \
            (all_faces[:, 1] != all_faces[:, 2]) & \
            (all_faces[:, 0] != all_faces[:, 2])
    all_faces = all_faces[valid]

    return verts_3d, all_faces


def _build_side_walls(
    verts_2d: np.ndarray,
    n_base: int,
    z_offset: float,
    height: float,
    faces: np.ndarray | None = None,
) -> np.ndarray:
    """Build quad walls along actual boundary edges.

    Handles multiple disconnected boundary loops (e.g. polygon with holes).
    """
    if faces is not None and len(faces) > 0:
        edge_count: dict[tuple[int, int], int] = {}
        for f in faces:
            for i in range(3):
                a = int(f[i])
                b = int(f[(i + 1) % 3])
                key = (min(a, b), max(a, b))
                edge_count[key] = edge_count.get(key, 0) + 1

        boundary_edges = [(a, b) for (a, b), cnt in edge_count.items() if cnt == 1]

        if boundary_edges:
            adjacency: dict[int, list[int]] = {}
            for a, b in boundary_edges:
                adjacency.setdefault(a, []).append(b)
                adjacency.setdefault(b, []).append(a)

            all_boundary_indices: list[np.ndarray] = []
            visited: set[int] = set()

            for edge_start, _ in boundary_edges:
                if edge_start in visited:
                    continue
                start = edge_start
                ordered = [start]
                visited.add(start)
                current = start
                while True:
                    nxt = None
                    for neighbor in adjacency.get(current, []):
                        if neighbor not in visited:
                            nxt = neighbor
                            break
                    if nxt is None:
                        break
                    ordered.append(nxt)
                    visited.add(nxt)
                    current = nxt
                all_boundary_indices.append(np.array(ordered, dtype=np.int32))
        else:
            all_boundary_indices = [np.arange(n_base, dtype=np.int32)]
    else:
        try:
            hull = ConvexHull(verts_2d)
            all_boundary_indices = [hull.vertices.astype(np.int32)]
        except Exception:
            all_boundary_indices = [np.arange(n_base, dtype=np.int32)]

    side_faces = []
    for boundary_indices in all_boundary_indices:
        n_boundary = len(boundary_indices)
        for i in range(n_boundary):
            idx_a = boundary_indices[i]
            idx_b = boundary_indices[(i + 1) % n_boundary]

            a_bot = idx_a
            b_bot = idx_b
            b_top = idx_b + n_base
            a_top = idx_a + n_base

            side_faces.append([a_bot, b_bot, b_top])
            side_faces.append([a_bot, b_top, a_top])

    if not side_faces:
        return np.zeros((0, 3), dtype=np.int32)

    return np.array(side_faces, dtype=np.int32)


def _chamfer_edges(
    verts: np.ndarray,
    faces: np.ndarray,
    chamfer_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply chamfer to top edges of an extruded part.

    This is a simplified chamfer that offsets the top face vertices inward
    and connects them to the original top vertices with bevel triangles.
    """
    if chamfer_size <= 0:
        return verts, faces

    n = len(verts) // 2  # bottom half / top half split
    bottom = verts[:n]
    top = verts[n:]

    # compute centroid
    centroid = bottom.mean(axis=0)

    # offset top vertices toward centroid
    directions = top - centroid
    dists = np.linalg.norm(directions, axis=1, keepdims=True)
    dists = np.maximum(dists, 1e-9)
    normalized = directions / dists

    offset_top = top - normalized * chamfer_size

    # new vertex set: bottom + offset_top + original_top
    new_verts = np.vstack([bottom, offset_top, top])

    m = len(faces)
    new_faces = np.empty((m * 2, 3), dtype=np.int32)

    # original faces (pointing to offset_top)
    for i, f in enumerate(faces):
        new_faces[i] = [f[0], f[1], f[2]]

    # bevel faces connecting offset_top to original_top
    for i, f in enumerate(faces):
        a, b, c = f
        new_faces[m + i] = [a + n, b + n, c + n]

    return new_verts, new_faces


def extrude_layer(
    mesh: TriangulatedMesh,
    params: ExtrusionParams,
    layer_id: str = "",
    layer_name: str = "",
    color: tuple[int, int, int] = (0, 0, 0),
) -> ExtrudedPart:
    """Extrude a single triangulated layer into a 3D part.

    Args:
        mesh: The triangulated 2D mesh.
        params: Extrusion parameters.
        layer_id: Identifier for this layer.
        layer_name: Display name.
        color: RGB color tuple.

    Returns:
        ExtrudedPart with full 3D geometry.
    """
    verts_2d = mesh.vertices[:, :2]  # strip Z=0

    verts_3d, faces = _extrude_face_set(
        verts_2d,
        mesh.faces,
        height=params.height,
        z_offset=params.z_offset,
        scale_x=params.scale_x,
        scale_y=params.scale_y,
    )

    # apply chamfer if requested
    if params.chamfer > 0:
        verts_3d, faces = _chamfer_edges(verts_3d, faces, params.chamfer)

    # apply translation
    if params.translate_x != 0.0 or params.translate_y != 0.0:
        verts_3d[:, 0] += params.translate_x
        verts_3d[:, 1] += params.translate_y

    from .mesh_ops import compute_normals
    normals = compute_normals(verts_3d, faces)

    return ExtrudedPart(
        id=layer_id,
        vertices=verts_3d,
        faces=faces,
        color=color,
        name=layer_name,
        normals=normals,
    )


def extrude_layers(
    meshes: dict[str, TriangulatedMesh],
    params: dict[str, ExtrusionParams],
    colors: dict[str, tuple[int, int, int]],
    names: dict[str, str] | None = None,
) -> list[ExtrudedPart]:
    """Extrude multiple layers into separate 3D parts.

    Args:
        meshes: Dict mapping layer_id to TriangulatedMesh.
        params: Dict mapping layer_id to ExtrusionParams.
        colors: Dict mapping layer_id to RGB color.
        names: Optional dict mapping layer_id to display name.

    Returns:
        List of ExtrudedPart objects.
    """
    parts = []
    for layer_id, mesh in meshes.items():
        layer_params = params.get(layer_id, ExtrusionParams())
        color = colors.get(layer_id, (0, 0, 0))
        name = (names or {}).get(layer_id, layer_id)

        part = extrude_layer(mesh, layer_params, layer_id, name, color)
        parts.append(part)

    return parts
