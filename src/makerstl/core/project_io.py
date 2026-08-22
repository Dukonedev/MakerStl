"""Project save/load as .makerstl JSON files."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..models.project import Project, LayerState, LayerGroup
from ..core.svg_parser import SvgLayer
from ..core.triangulator import TriangulatedMesh
from ..core.extruder import ExtrusionParams


def _serialize_svg_layer(sl: SvgLayer) -> dict:
    return {
        "id": sl.id,
        "name": sl.name,
        "vertices": sl.vertices.tolist(),
        "color": list(sl.color),
        "hole_verts": [hv.tolist() for hv in sl.hole_verts],
        "fill_opacity": sl.fill_opacity,
        "closed": sl.closed,
    }


def _serialize_mesh(mesh: TriangulatedMesh | None) -> dict | None:
    if mesh is None:
        return None
    return {
        "vertices": mesh.vertices.tolist(),
        "faces": mesh.faces.tolist(),
    }


def _serialize_params(p: ExtrusionParams) -> dict:
    return {
        "height": p.height,
        "z_offset": p.z_offset,
        "scale_x": p.scale_x,
        "scale_y": p.scale_y,
        "chamfer": p.chamfer,
        "translate_x": p.translate_x,
        "translate_y": p.translate_y,
    }


def _serialize_layer(ls: LayerState) -> dict:
    return {
        "_type": "layer",
        "svg_layer": _serialize_svg_layer(ls.svg_layer),
        "mesh": _serialize_mesh(ls.triangulated_mesh),
        "params": _serialize_params(ls.extrusion_params),
        "color": list(ls.color),
        "visible": ls.visible,
        "locked": ls.locked,
        "is_ring": ls.is_ring,
        "ring_outer_d": ls.ring_outer_d,
        "ring_thickness": ls.ring_thickness,
    }


def _serialize_group(grp: LayerGroup) -> dict:
    return {
        "_type": "group",
        "name": grp.name,
        "visible": grp.visible,
        "locked": grp.locked,
        "expanded": grp.expanded,
        "color": list(grp.color),
        "children": [_serialize_node(child) for child in grp.children],
    }


def _serialize_node(node: LayerState | LayerGroup) -> dict:
    if isinstance(node, LayerGroup):
        return _serialize_group(node)
    return _serialize_layer(node)


def save_project(project: Project, path: str | Path) -> None:
    """Save the full project state to a .makerstl JSON file."""
    data = {
        "version": 1,
        "name": project.name,
        "svg_path": str(project.svg_path) if project.svg_path else None,
        "global_scale": project.global_scale,
        "global_z_offset": project.global_z_offset,
        "base_height": project.base_height,
        "base_size_x": project.base_size_x,
        "base_size_y": project.base_size_y,
        "root": _serialize_group(project.root),
    }

    path = Path(path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ------------------------------------------------------------------
# Deserialization
# ------------------------------------------------------------------

def _deserialize_svg_layer(d: dict) -> SvgLayer:
    return SvgLayer(
        id=d["id"],
        name=d["name"],
        vertices=np.array(d["vertices"], dtype=np.float64),
        color=tuple(d["color"]),
        hole_verts=[np.array(hv, dtype=np.float64) for hv in d.get("hole_verts", [])],
        fill_opacity=d.get("fill_opacity", 1.0),
        closed=d.get("closed", True),
    )


def _deserialize_mesh(d: dict | None) -> TriangulatedMesh | None:
    if d is None:
        return None
    return TriangulatedMesh(
        vertices=np.array(d["vertices"], dtype=np.float64),
        faces=np.array(d["faces"], dtype=np.int32),
    )


def _deserialize_params(d: dict) -> ExtrusionParams:
    return ExtrusionParams(
        height=d.get("height", 5.0),
        z_offset=d.get("z_offset", 0.0),
        scale_x=d.get("scale_x", 1.0),
        scale_y=d.get("scale_y", 1.0),
        chamfer=d.get("chamfer", 0.0),
        translate_x=d.get("translate_x", 0.0),
        translate_y=d.get("translate_y", 0.0),
    )


def _deserialize_layer(d: dict) -> LayerState:
    svg_layer = _deserialize_svg_layer(d["svg_layer"])
    mesh = _deserialize_mesh(d.get("mesh"))
    params = _deserialize_params(d.get("params", {}))
    color = tuple(d.get("color", [0, 0, 0]))
    return LayerState(
        svg_layer=svg_layer,
        triangulated_mesh=mesh,
        extrusion_params=params,
        color=color,
        visible=d.get("visible", True),
        locked=d.get("locked", False),
        is_ring=d.get("is_ring", False),
        ring_outer_d=d.get("ring_outer_d", 14.0),
        ring_thickness=d.get("ring_thickness", 3.0),
    )


def _deserialize_group(d: dict) -> LayerGroup:
    grp = LayerGroup(
        name=d.get("name", "Group"),
        visible=d.get("visible", True),
        locked=d.get("locked", False),
        expanded=d.get("expanded", True),
        color=tuple(d.get("color", [180, 180, 180])),
    )
    for child_d in d.get("children", []):
        child = _deserialize_node(child_d)
        if child is not None:
            child._parent = grp
            grp.children.append(child)
    return grp


def _deserialize_node(d: dict) -> LayerState | LayerGroup | None:
    t = d.get("_type", "layer")
    if t == "group":
        return _deserialize_group(d)
    elif t == "layer":
        return _deserialize_layer(d)
    return None


def load_project(path: str | Path) -> Project:
    """Load a project from a .makerstl JSON file."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    project = Project()
    project.name = data.get("name", "Untitled")
    svg_str = data.get("svg_path")
    project.svg_path = Path(svg_str) if svg_str else None
    project.global_scale = data.get("global_scale", 1.0)
    project.global_z_offset = data.get("global_z_offset", 0.0)
    project.base_height = data.get("base_height", 2.0)
    project.base_size_x = data.get("base_size_x", 100.0)
    project.base_size_y = data.get("base_size_y", 100.0)

    root_d = data.get("root", {})
    project.root = _deserialize_group(root_d)
    project.root.name = "Root"
    project._rebuild_flat_list()

    # recompute extrusions for all layers
    project.recompute_extrusions()

    return project
