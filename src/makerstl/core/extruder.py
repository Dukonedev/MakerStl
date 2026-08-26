"""Extruder: creates 3D meshes by extruding 2D triangulated layers.

Supports:
- Parametric extrusion height per layer
- Uniform Z offset for multi-layer stacking
- Chamfer (legacy) and multi-segment bevel/fillet on edges
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
    chamfer: float = 0.0  # legacy chamfer depth (centroid inset)
    bevel_radius: float = 0.0  # multi-segment bevel radius on boundary edges
    bevel_segments: int = 3  # number of segments in the bevel arc
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
    """Legacy chamfer: offsets top vertices toward centroid (deprecated)."""
    if chamfer_size <= 0:
        return verts, faces

    n = len(verts) // 2
    bottom = verts[:n]
    top = verts[n:]

    centroid = bottom.mean(axis=0)
    directions = top - centroid
    dists = np.linalg.norm(directions, axis=1, keepdims=True)
    dists = np.maximum(dists, 1e-9)
    normalized = directions / dists
    offset_top = top - normalized * chamfer_size

    new_verts = np.vstack([bottom, offset_top, top])
    m = len(faces)
    new_faces = np.empty((m * 2, 3), dtype=np.int32)
    for i, f in enumerate(faces):
        new_faces[i] = [f[0], f[1], f[2]]
    for i, f in enumerate(faces):
        new_faces[m + i] = [f[0] + n, f[1] + n, f[2] + n]

    return new_verts, new_faces


def _find_boundary_edges(faces: np.ndarray) -> list[tuple[int, int]]:
    """Return edges that appear in exactly one face (boundary)."""
    edge_count: dict[tuple[int, int], int] = {}
    for f in faces:
        for i in range(3):
            a, b = int(f[i]), int(f[(i + 1) % 3])
            key = (min(a, b), max(a, b))
            edge_count[key] = edge_count.get(key, 0) + 1
    return [(a, b) for (a, b), cnt in edge_count.items() if cnt == 1]


def _find_boundary_loops(
    boundary_edges: list[tuple[int, int]],
) -> list[np.ndarray]:
    """Order boundary edges into connected loops."""
    adj: dict[int, list[int]] = {}
    for a, b in boundary_edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    visited: set[int] = set()
    loops: list[np.ndarray] = []

    for start, _ in boundary_edges:
        if start in visited:
            continue
        ordered = [start]
        visited.add(start)
        current = start
        while True:
            nxt = None
            for nb in adj.get(current, []):
                if nb not in visited:
                    nxt = nb
                    break
            if nxt is None:
                break
            ordered.append(nxt)
            visited.add(nxt)
            current = nxt
        loops.append(np.array(ordered, dtype=np.int32))

    return loops


def _compute_inset_directions(
    verts: np.ndarray,
    boundary_loop: np.ndarray,
    centroid: np.ndarray,
) -> np.ndarray:
    """Compute per-vertex inset direction for boundary vertices.

    For each boundary vertex, the inset direction is the average of the
    inward-facing edge normals, projected into XY. Falls back to centroid
    direction when the normal is degenerate.
    """
    n = len(boundary_loop)
    directions = np.zeros((len(verts), 3), dtype=np.float64)

    for i in range(n):
        idx = int(boundary_loop[i])
        prev_idx = int(boundary_loop[(i - 1) % n])
        next_idx = int(boundary_loop[(i + 1) % n])

        v = verts[idx]
        v_prev = verts[prev_idx]
        v_next = verts[next_idx]

        edge_prev = v - v_prev
        edge_next = v_next - v

        # 2D edge normals (perpendicular, pointing inward)
        n1 = np.array([-edge_prev[1], edge_prev[0]], dtype=np.float64)
        n2 = np.array([-edge_next[1], edge_next[0]], dtype=np.float64)

        # normalize
        len1 = np.linalg.norm(n1)
        len2 = np.linalg.norm(n2)
        if len1 > 1e-9:
            n1 /= len1
        if len2 > 1e-9:
            n2 /= len2

        avg_normal = (n1 + n2) * 0.5
        avg_len = np.linalg.norm(avg_normal)
        if avg_len < 1e-9:
            # fallback: direction toward centroid
            to_center = centroid[:2] - v[:2]
            to_center_len = np.linalg.norm(to_center)
            if to_center_len > 1e-9:
                avg_normal = to_center / to_center_len
            else:
                avg_normal = np.array([1.0, 0.0])
        else:
            avg_normal /= avg_len

        # ensure inward: dot with centroid direction should be positive
        to_center = centroid[:2] - v[:2]
        if np.dot(avg_normal, to_center) < 0:
            avg_normal = -avg_normal

        directions[idx] = np.array([avg_normal[0], avg_normal[1], 0.0])

    return directions


def _bevel_edges(
    verts: np.ndarray,
    faces: np.ndarray,
    bevel_radius: float,
    bevel_segments: int,
    all_boundary_indices: list[np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply multi-segment bevel (fillet) on boundary edges.

    Creates smooth rounded edges by interpolating between the original
    boundary and an inset copy, following a quarter-circle profile.
    Works on both top and bottom edges of the extruded solid.

    Args:
        verts: (N, 3) vertices — bottom half in [0:n], top half in [n:2n].
        faces: (M, 3) face indices.
        bevel_radius: maximum inset distance in mm.
        bevel_segments: number of arc segments (2 = flat chamfer, >2 = round).
        all_boundary_indices: optional pre-computed boundary loops.

    Returns:
        New (verts, faces) with bevel geometry inserted.
    """
    if bevel_radius <= 0:
        return verts, faces

    n = len(verts) // 2
    bottom = verts[:n].copy()
    top = verts[n:].copy()

    if all_boundary_indices is None:
        b_edges = _find_boundary_edges(faces)
        if not b_edges:
            return verts, faces
        all_boundary_indices = _find_boundary_loops(b_edges)

    centroid = bottom.mean(axis=0)

    boundary_vertex_set: set[int] = set()
    for loop in all_boundary_indices:
        for idx in loop:
            boundary_vertex_set.add(int(idx))

    inset_dirs = np.zeros_like(bottom)
    for loop in all_boundary_indices:
        dirs = _compute_inset_directions(bottom, loop, centroid)
        for idx in loop:
            inset_dirs[int(idx)] = dirs[int(idx)]

    all_new_verts = [bottom, top]
    all_new_faces = [faces.copy()]

    for half in ("top", "bottom"):
        base_verts = bottom if half == "bottom" else top
        # bottom edge bevel: rounds upward (z_dir=+1)
        # top edge bevel: rounds downward (z_dir=-1)
        z_dir = 1.0 if half == "bottom" else -1.0

        # quarter-circle arc: segments from original boundary inward
        prev_ring_indices = np.arange(n) if half == "bottom" else np.arange(n, 2 * n)

        for seg in range(bevel_segments):
            t = (seg + 1) / bevel_segments
            angle = t * np.pi / 2.0
            inset_frac = np.sin(angle)
            z_off = (1.0 - np.cos(angle)) * bevel_radius * z_dir

            ring = base_verts.copy()
            for vi in boundary_vertex_set:
                ring[vi] = base_verts[vi] + inset_dirs[vi] * bevel_radius * inset_frac
                ring[vi, 2] = base_verts[vi, 2] + z_off

            ring_start = len(all_new_verts[0]) + seg * n
            all_new_verts.append(ring)

            # connect this ring to previous ring (strip along boundary)
            for loop in all_boundary_indices:
                loop_len = len(loop)
                for i in range(loop_len):
                    idx_a = int(loop[i])
                    idx_b = int(loop[(i + 1) % loop_len])

                    pa = prev_ring_indices[idx_a]
                    pb = prev_ring_indices[idx_b]
                    ca = ring_start + idx_a
                    cb = ring_start + idx_b

                    all_new_faces.append(np.array([[pa, pb, cb], [pa, cb, ca]], dtype=np.int32))

            prev_ring_indices = np.arange(ring_start, ring_start + n)

    all_new_verts_arr = np.vstack(all_new_verts)
    all_new_faces_arr = np.vstack(all_new_faces)

    valid = (
        (all_new_faces_arr[:, 0] != all_new_faces_arr[:, 1])
        & (all_new_faces_arr[:, 1] != all_new_faces_arr[:, 2])
        & (all_new_faces_arr[:, 0] != all_new_faces_arr[:, 2])
    )
    all_new_faces_arr = all_new_faces_arr[valid]

    return all_new_verts_arr, all_new_faces_arr


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

    # pre-compute boundary loops once (used by side walls + bevel)
    b_edges = _find_boundary_edges(mesh.faces)
    boundary_loops = _find_boundary_loops(b_edges) if b_edges else []

    verts_3d, faces = _extrude_face_set(
        verts_2d,
        mesh.faces,
        height=params.height,
        z_offset=params.z_offset,
        scale_x=params.scale_x,
        scale_y=params.scale_y,
    )

    # apply multi-segment bevel (preferred over legacy chamfer)
    if params.bevel_radius > 0 and params.bevel_segments >= 2:
        verts_3d, faces = _bevel_edges(
            verts_3d, faces,
            params.bevel_radius, params.bevel_segments,
            all_boundary_indices=boundary_loops,
        )
    elif params.chamfer > 0:
        # legacy chamfer fallback
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
