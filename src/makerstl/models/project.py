"""Project data model: holds all state for the current SVG-to-3D project.

Supports hierarchical layer groups (Photoshop-style) with:
- Nested groups containing layers and sub-groups
- Visibility propagation (group off = all children hidden)
- Drag-and-drop reordering
- Lock per layer/group
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

from ..core.svg_parser import SvgLayer
from ..core.triangulator import TriangulatedMesh
from ..core.extruder import ExtrudedPart, ExtrusionParams
from ..core.quality import QualitySettings


# ---------------------------------------------------------------------------
# Tree node types
# ---------------------------------------------------------------------------

@dataclass
class LayerState:
    """Complete state for one SVG layer/path."""

    svg_layer: SvgLayer
    triangulated_mesh: TriangulatedMesh | None = None
    extrusion_params: ExtrusionParams = field(default_factory=ExtrusionParams)
    color: tuple[int, int, int] = (0, 0, 0)
    visible: bool = True
    locked: bool = False
    extruded_part: ExtrudedPart | None = None
    is_ring: bool = False  # ring sits at base level (z_offset=0)
    ring_outer_d: float = 14.0  # ring outer diameter (used to regenerate)
    ring_thickness: float = 3.0  # ring wall thickness

    # tree navigation (set when inserted into a group)
    _parent: LayerGroup | None = field(default=None, repr=False)

    @property
    def effective_visible(self) -> bool:
        """True only if this layer AND all ancestor groups are visible."""
        if not self.visible:
            return False
        node = self._parent
        while node is not None:
            if not node.visible:
                return False
            node = node._parent
        return True

    def update_color(self, r: int, g: int, b: int) -> None:
        self.color = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        if self.extruded_part:
            self.extruded_part.color = self.color

    def update_height(self, height: float) -> None:
        self.extrusion_params.height = max(0.1, height)

    def update_scale(self, sx: float, sy: float) -> None:
        self.extrusion_params.scale_x = max(0.01, sx)
        self.extrusion_params.scale_y = max(0.01, sy)


@dataclass
class LayerGroup:
    """A folder/group that contains layers and sub-groups."""

    name: str = "Group"
    visible: bool = True
    locked: bool = False
    expanded: bool = True  # UI expand/collapse state
    children: list[LayerState | LayerGroup] = field(default_factory=list)
    color: tuple[int, int, int] = (180, 180, 180)

    _parent: LayerGroup | None = field(default=None, repr=False)

    @property
    def effective_visible(self) -> bool:
        if not self.visible:
            return False
        node = self._parent
        while node is not None:
            if not node.visible:
                return False
            node = node._parent
        return True

    def flat_layers(self) -> Iterator[LayerState]:
        """Yield all LayerState nodes in this group (depth-first)."""
        for child in self.children:
            if isinstance(child, LayerState):
                yield child
            elif isinstance(child, LayerGroup):
                yield from child.flat_layers()

    def all_nodes(self) -> Iterator[LayerState | LayerGroup]:
        """Yield this group and all descendants."""
        yield self
        for child in self.children:
            if isinstance(child, LayerGroup):
                yield from child.all_nodes()
            else:
                yield child


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

@dataclass
class Project:
    """Root project state."""

    svg_path: Path | None = None
    name: str = "Untitled"

    # root group — all top-level items live here
    root: LayerGroup = field(default_factory=lambda: LayerGroup(name="Root"))

    # legacy flat list kept in sync for backward compat — prefer root traversal
    layers: list[LayerState] = field(default_factory=list)

    global_scale: float = 1.0
    global_z_offset: float = 0.0
    base_height: float = 2.0  # height of the base plate layer
    quality: QualitySettings = field(default_factory=QualitySettings)

    # original bounding box after normalization (in normalized units)
    base_size_x: float = 100.0
    base_size_y: float = 100.0

    # last import folder — used as default for import/export dialogs
    _last_import_dir: Path | None = None

    # ------------------------------------------------------------------
    # Tree helpers
    # ------------------------------------------------------------------

    def _rebuild_flat_list(self) -> None:
        """Regenerate self.layers from root tree."""
        self.layers = list(self.root.flat_layers())

    @property
    def layer_count(self) -> int:
        return len(self.layers)

    @property
    def visible_layers(self) -> list[LayerState]:
        return [l for l in self.layers if l.effective_visible]

    def get_layer_by_id(self, layer_id: str) -> LayerState | None:
        for layer in self.layers:
            if layer.svg_layer.id == layer_id:
                return layer
        return None

    def find_parent_group(self, layer_id: str) -> LayerGroup | None:
        """Return the direct parent group of a layer."""
        layer = self.get_layer_by_id(layer_id)
        if layer:
            return layer._parent
        return None

    # ------------------------------------------------------------------
    # Group operations
    # ------------------------------------------------------------------

    def create_group(
        self,
        name: str = "Group",
        parent: LayerGroup | None = None,
    ) -> LayerGroup:
        """Create a new empty group and add it to parent (default: root)."""
        g = LayerGroup(name=name)
        target = parent or self.root
        g._parent = target
        target.children.append(g)
        return g

    def add_layer_to_group(self, layer_id: str, group: LayerGroup) -> None:
        """Move a layer from its current position into the given group."""
        layer = self.get_layer_by_id(layer_id)
        if layer is None:
            return
        # remove from old parent
        old_parent = layer._parent or self.root
        if layer in old_parent.children:
            old_parent.children.remove(layer)
        # insert into new group
        layer._parent = group
        group.children.append(layer)
        self._rebuild_flat_list()

    def group_selected(self, layer_ids: list[str], name: str = "Group") -> LayerGroup:
        """Wrap the given layers in a new group, preserving order."""
        if not layer_ids:
            return self.create_group(name)

        # determine common parent (use first item's parent)
        first = self.get_layer_by_id(layer_ids[0])
        parent = first._parent if first else self.root

        new_group = LayerGroup(name=name, _parent=parent)

        # collect layers in order
        ordered = []
        for lid in layer_ids:
            l = self.get_layer_by_id(lid)
            if l:
                ordered.append(l)

        # compute insertion index BEFORE removing
        idx = parent.children.index(ordered[0]) if ordered[0] in parent.children else len(parent.children)

        # remove all from parent, then insert as group
        for l in ordered:
            p = l._parent or self.root
            if l in p.children:
                p.children.remove(l)

        # insert group at position of first item
        new_group.children = ordered
        for l in ordered:
            l._parent = new_group
        parent.children.insert(idx, new_group)

        self._rebuild_flat_list()
        return new_group

    def ungroup(self, group: LayerGroup) -> None:
        """Dissolve a group, moving its children up to the parent."""
        parent = group._parent or self.root
        idx = parent.children.index(group) if group in parent.children else len(parent.children)

        # reparent children
        for child in group.children:
            child._parent = parent
        parent.children[idx:idx + 1] = group.children

        self._rebuild_flat_list()

    def move_layer(self, layer_id: str, direction: int) -> None:
        """Move a layer up (direction=+1) or down (direction=-1) within its parent."""
        layer = self.get_layer_by_id(layer_id)
        if not layer:
            return
        parent = layer._parent or self.root
        idx = parent.children.index(layer)
        new_idx = idx - direction  # -1 because list order = top-to-bottom in UI
        if 0 <= new_idx < len(parent.children):
            parent.children[idx], parent.children[new_idx] = (
                parent.children[new_idx], parent.children[idx],
            )
            self._rebuild_flat_list()

    def delete_layer(self, layer_id: str) -> None:
        """Remove a layer from the project."""
        layer = self.get_layer_by_id(layer_id)
        if not layer:
            return
        parent = layer._parent or self.root
        if layer in parent.children:
            parent.children.remove(layer)
        self._rebuild_flat_list()

    def duplicate_layer(self, layer_id: str) -> LayerState | None:
        """Duplicate a layer, inserting the copy right after the original."""
        import copy as _copy
        from ..core.svg_parser import SvgLayer as _SvgLayer

        layer = self.get_layer_by_id(layer_id)
        if not layer:
            return None

        parent = layer._parent or self.root
        idx = parent.children.index(layer) if layer in parent.children else len(parent.children)

        # deep copy the svg_layer (vertices, hole_verts)
        new_svg = _SvgLayer(
            id=f"{layer.svg_layer.id}_copy",
            name=f"{layer.svg_layer.name} copy",
            vertices=layer.svg_layer.vertices.copy(),
            color=layer.svg_layer.color,
            fill_opacity=layer.svg_layer.fill_opacity,
            closed=layer.svg_layer.closed,
            hole_verts=[hv.copy() for hv in layer.svg_layer.hole_verts],
        )

        new_ls = LayerState(
            svg_layer=new_svg,
            triangulated_mesh=_copy.deepcopy(layer.triangulated_mesh) if layer.triangulated_mesh else None,
            extrusion_params=_copy.deepcopy(layer.extrusion_params),
            color=layer.color,
            visible=layer.visible,
            locked=False,
            is_ring=layer.is_ring,
            ring_outer_d=layer.ring_outer_d,
            ring_thickness=layer.ring_thickness,
        )
        new_ls._parent = parent
        parent.children.insert(idx + 1, new_ls)
        self._rebuild_flat_list()
        return new_ls

    def move_node(self, node: LayerState | LayerGroup, new_parent: LayerGroup, index: int = -1) -> bool:
        """Move a node (layer or group) into new_parent at index.

        Rejects the move if new_parent is a descendant of node (prevents cycles).
        Returns True if the move succeeded.
        """
        if node is new_parent:
            return False

        # reject cycles: new_parent must not be a descendant of node
        if isinstance(node, LayerGroup):
            for desc in node.all_nodes():
                if desc is new_parent:
                    return False

        # remove from old parent
        old_parent = node._parent or self.root
        if node in old_parent.children:
            old_parent.children.remove(node)

        # insert into new parent
        node._parent = new_parent
        if 0 <= index <= len(new_parent.children):
            new_parent.children.insert(index, node)
        else:
            new_parent.children.append(node)

        self._rebuild_flat_list()
        return True

    def rename_group(self, group: LayerGroup, new_name: str) -> None:
        group.name = new_name

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def merge_layers(
        self,
        layer_ids: list[str],
        color: tuple[int, int, int] | None = None,
        name: str | None = None,
    ) -> LayerState | None:
        """Merge multiple layers into one via Shapely boolean union.

        The merged layer is inserted at the position of the first selected
        layer.  Returns the new LayerState or None on failure.
        """
        from shapely.ops import unary_union
        from shapely.geometry import Polygon, MultiPolygon
        from ..core.svg_parser import SvgLayer
        from ..core.triangulator import triangulate_layer

        layers = [self.get_layer_by_id(lid) for lid in layer_ids]
        layers = [l for l in layers if l is not None]
        if len(layers) < 2:
            return None

        # build Shapely geometries from each layer (with holes)
        geoms = []
        for ls in layers:
            verts = ls.svg_layer.vertices.copy()
            # apply translate offset so merge respects positioned rings
            tx = ls.extrusion_params.translate_x
            ty = ls.extrusion_params.translate_y
            if tx != 0.0 or ty != 0.0:
                verts[:, 0] += tx
                verts[:, 1] += ty
            if len(verts) < 3:
                continue
            ring = verts
            if not np.allclose(ring[0], ring[-1]):
                ring = np.vstack([ring, ring[0:1]])
            interiors = []
            for hv in ls.svg_layer.hole_verts:
                if len(hv) < 3:
                    continue
                hv_copy = hv.copy()
                if tx != 0.0 or ty != 0.0:
                    hv_copy[:, 0] += tx
                    hv_copy[:, 1] += ty
                hr = hv_copy
                if not np.allclose(hr[0], hr[-1]):
                    hr = np.vstack([hr, hr[0:1]])
                interiors.append(Polygon(hr).exterior)
            try:
                poly = Polygon(ring, interiors)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if not poly.is_empty:
                    geoms.append(poly)
            except Exception:
                continue

        if not geoms:
            return None

        merged_geom = unary_union(geoms)
        if merged_geom.is_empty:
            return None

        # extract polygon(s) for triangulation
        polygons = []
        if isinstance(merged_geom, Polygon):
            polygons.append(merged_geom)
        elif isinstance(merged_geom, MultiPolygon):
            polygons.extend(p for p in merged_geom.geoms if not p.is_empty)

        if not polygons:
            return None

        # triangulate each polygon and merge
        all_v2d = []
        all_faces = []
        offset = 0
        for poly in polygons:
            from ..core.triangulator import _earcut_single_polygon
            v2d, f = _earcut_single_polygon(poly)
            if len(f) == 0:
                continue
            all_v2d.append(v2d)
            all_faces.append(f + offset)
            offset += len(v2d)

        if not all_v2d:
            return None

        verts_2d = np.vstack(all_v2d)
        faces = np.vstack(all_faces)

        verts_3d = np.column_stack([
            verts_2d[:, 0], verts_2d[:, 1], np.zeros(len(verts_2d))
        ])

        mesh = TriangulatedMesh(vertices=verts_3d, faces=faces)

        # build merged polygon exterior + holes for SvgLayer data
        if len(polygons) == 1:
            poly = polygons[0]
            merged_exterior = np.array(poly.exterior.coords[:-1], dtype=np.float64)
            merged_holes = [
                np.array(interior.coords[:-1], dtype=np.float64)
                for interior in poly.interiors
            ]
        else:
            # MultiPolygon: use convex hull as exterior, no holes for SvgLayer
            from shapely.geometry import MultiPoint
            all_pts = MultiPoint(np.vstack([np.array(p.exterior.coords) for p in polygons]))
            hull = all_pts.convex_hull
            merged_exterior = np.array(hull.exterior.coords[:-1], dtype=np.float64) if isinstance(hull, Polygon) else verts_2d
            merged_holes = []

        # create new SvgLayer
        merged_id = f"merged_{'_'.join(layer_ids)}"
        merged_name = name or " + ".join(l.svg_layer.name for l in layers)
        merged_color = color or layers[0].color
        svg_layer = SvgLayer(
            id=merged_id,
            name=merged_name,
            vertices=merged_exterior,
            color=merged_color,
            hole_verts=merged_holes,
        )

        # determine insertion position (where the first selected layer was)
        first_parent = layers[0]._parent or self.root
        try:
            idx = first_parent.children.index(layers[0])
        except ValueError:
            idx = len(first_parent.children)

        # remove originals from their parents
        for ls in layers:
            p = ls._parent or self.root
            if ls in p.children:
                p.children.remove(ls)

        # create new LayerState
        new_ls = LayerState(
            svg_layer=svg_layer,
            triangulated_mesh=mesh,
            color=merged_color,
        )
        new_ls._parent = first_parent
        first_parent.children.insert(idx, new_ls)

        self._rebuild_flat_list()
        return new_ls

    def subtract_layers(
        self,
        base_id: str,
        cutter_ids: list[str],
    ) -> LayerState | None:
        """Subtract cutter layers from the base layer using Shapely difference.

        The base layer keeps its position; cutters are subtracted from it.
        Returns the modified base LayerState or None on failure.
        """
        from shapely.geometry import Polygon
        from ..core.svg_parser import SvgLayer

        base = self.get_layer_by_id(base_id)
        if not base:
            return None

        def _to_polygon(ls: LayerState) -> Polygon | None:
            verts = ls.svg_layer.vertices.copy()
            tx = ls.extrusion_params.translate_x
            ty = ls.extrusion_params.translate_y
            if tx != 0.0 or ty != 0.0:
                verts[:, 0] += tx
                verts[:, 1] += ty
            if len(verts) < 3:
                return None
            ring = verts
            if not np.allclose(ring[0], ring[-1]):
                ring = np.vstack([ring, ring[0:1]])
            interiors = []
            for hv in ls.svg_layer.hole_verts:
                if len(hv) < 3:
                    continue
                hv_copy = hv.copy()
                if tx != 0.0 or ty != 0.0:
                    hv_copy[:, 0] += tx
                    hv_copy[:, 1] += ty
                hr = hv_copy
                if not np.allclose(hr[0], hr[-1]):
                    hr = np.vstack([hr, hr[0:1]])
                interiors.append(Polygon(hr).exterior)
            try:
                poly = Polygon(ring, interiors)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                return poly if not poly.is_empty else None
            except Exception:
                return None

        base_poly = _to_polygon(base)
        if base_poly is None:
            return None

        # subtract each cutter
        result = base_poly
        for cid in cutter_ids:
            cutter = self.get_layer_by_id(cid)
            if cutter is None or cutter is base:
                continue
            cutter_poly = _to_polygon(cutter)
            if cutter_poly is None:
                continue
            result = result.difference(cutter_poly)
            if result.is_empty:
                return None

        if result.is_empty:
            return None

        # triangulate result
        from ..core.triangulator import _earcut_single_polygon, TriangulatedMesh

        polygons = []
        if isinstance(result, Polygon):
            polygons.append(result)
        elif hasattr(result, 'geoms'):
            from shapely.geometry import MultiPolygon
            if isinstance(result, MultiPolygon):
                polygons.extend(p for p in result.geoms if not p.is_empty)

        all_v2d = []
        all_faces = []
        offset = 0
        for poly in polygons:
            v2d, f = _earcut_single_polygon(poly)
            if len(f) == 0:
                continue
            all_v2d.append(v2d)
            all_faces.append(f + offset)
            offset += len(v2d)

        if not all_v2d:
            return None

        verts_2d = np.vstack(all_v2d)
        faces = np.vstack(all_faces)
        verts_3d = np.column_stack([verts_2d[:, 0], verts_2d[:, 1], np.zeros(len(verts_2d))])
        mesh = TriangulatedMesh(vertices=verts_3d, faces=faces)

        # update base's svg_layer with new geometry
        if isinstance(result, Polygon):
            new_exterior = np.array(result.exterior.coords[:-1], dtype=np.float64)
            new_holes = [
                np.array(interior.coords[:-1], dtype=np.float64)
                for interior in result.interiors
            ]
        else:
            new_exterior = verts_2d
            new_holes = []

        base.svg_layer = SvgLayer(
            id=base.svg_layer.id,
            name=base.svg_layer.name,
            vertices=new_exterior,
            color=base.svg_layer.color,
            hole_verts=new_holes,
            fill_opacity=base.svg_layer.fill_opacity,
            closed=base.svg_layer.closed,
        )
        base.triangulated_mesh = mesh

        # remove cutter layers
        for cid in cutter_ids:
            self.delete_layer(cid)

        self._rebuild_flat_list()
        return base

    # ------------------------------------------------------------------
    # Extrusion
    # ------------------------------------------------------------------

    def recompute_extrusions(self, dirty_layer_ids: list[str] | None = None) -> list[ExtrudedPart]:
        """Rebuild extruded parts, respecting group visibility.

        Args:
            dirty_layer_ids: If provided, only re-extrude these layers.
                If None, re-extrude all visible layers (full recompute).

        The base layer is the last visible layer in tree order.
        global_scale is applied ONLY to the base layer.
        Each layer keeps its own scale_x/scale_y via ExtrusionParams.
        """
        from ..core.extruder import extrude_layer

        parts = []

        # base = last visible layer in tree order
        visible = [l for l in self.layers if l.effective_visible and l.triangulated_mesh is not None]
        base_layer = visible[-1] if visible else None

        for layer in self.layers:
            if not layer.effective_visible or layer.triangulated_mesh is None:
                continue

            # incremental mode: skip layers not in the dirty set
            if dirty_layer_ids is not None and layer.svg_layer.id not in dirty_layer_ids:
                # still collect existing parts for the return value
                if layer.extruded_part is not None:
                    parts.append(layer.extruded_part)
                continue

            params = layer.extrusion_params

            if layer is base_layer or layer.is_ring:
                params.z_offset = self.global_z_offset
            else:
                base_h = base_layer.extrusion_params.height if base_layer else self.base_height
                params.z_offset = self.global_z_offset + base_h

            part = extrude_layer(
                layer.triangulated_mesh,
                params,
                layer.svg_layer.id,
                layer.svg_layer.name,
                layer.color,
            )

            # apply global_scale ONLY to base layer
            if layer is base_layer and self.global_scale != 1.0:
                part.vertices[:, 0] *= self.global_scale
                part.vertices[:, 1] *= self.global_scale
                from ..core.mesh_ops import compute_normals
                part.normals = compute_normals(part.vertices, part.faces)

            layer.extruded_part = part
            parts.append(part)

        return parts

    # ------------------------------------------------------------------
    # Ring regeneration
    # ------------------------------------------------------------------

    def regenerate_ring(self, layer_id: str, outer_d: float, thickness: float) -> None:
        """Rebuild a ring layer's geometry from new outer diameter and thickness."""
        layer = self.get_layer_by_id(layer_id)
        if layer is None or not layer.is_ring:
            return

        from ..core.shapes import make_ring
        from ..core.triangulator import triangulate_layer

        layer.ring_outer_d = outer_d
        layer.ring_thickness = thickness

        outer_verts, inner_hole = make_ring(outer_diameter=outer_d, thickness=thickness)
        hole_verts = [inner_hole]

        layer.svg_layer.vertices = outer_verts
        layer.svg_layer.hole_verts = hole_verts
        layer.triangulated_mesh = triangulate_layer(outer_verts, tolerance=self.quality.tolerance,
                                                     hole_verts=hole_verts)

        self.recompute_extrusions()
