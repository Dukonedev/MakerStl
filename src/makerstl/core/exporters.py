"""Exporters: STL, OBJ (with MTL), and color 3MF for Bambu Studio.

The 3MF exporter creates a valid 3MF package compatible with Bambu Studio:
- Separate object parts per SVG layer
- Colors via Bambu-specific model_settings.config (extruder mapping)
- filament_colour in project_settings.config
"""

from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from .extruder import ExtrudedPart
from .mesh_ops import merge_parts, compute_normals, fix_normals_direction


def export_stl(
    parts: list[ExtrudedPart],
    output_path: str | Path,
    binary: bool = True,
) -> Path:
    """Export parts as a single STL file."""
    output_path = Path(output_path)
    if binary:
        return _export_stl_binary(parts, output_path)
    else:
        return _export_stl_ascii(parts, output_path)


def _export_stl_binary(parts: list[ExtrudedPart], path: Path) -> Path:
    verts, faces = merge_parts(parts)
    if len(faces) == 0:
        raise ValueError("No faces to export")
    faces = fix_normals_direction(verts, faces)
    normals = compute_normals(verts, faces)
    with open(path, "wb") as f:
        header = b"MakerStl Export" + b"\x00" * (80 - 15)
        f.write(header)
        f.write(struct.pack("<I", len(faces)))
        for i, face in enumerate(faces):
            normal = normals[face[0]]
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]
            f.write(struct.pack("<fff", *normal))
            f.write(struct.pack("<fff", *v0))
            f.write(struct.pack("<fff", *v1))
            f.write(struct.pack("<fff", *v2))
            f.write(struct.pack("<H", 0))
    return path


def _export_stl_ascii(parts: list[ExtrudedPart], path: Path) -> Path:
    verts, faces = merge_parts(parts)
    if len(faces) == 0:
        raise ValueError("No faces to export")
    faces = fix_normals_direction(verts, faces)
    normals = compute_normals(verts, faces)
    with open(path, "w") as f:
        f.write("solid MakerStl\n")
        for face in faces:
            normal = normals[face[0]]
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]
            f.write(f"  facet normal {normal[0]:.6e} {normal[1]:.6e} {normal[2]:.6e}\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {v0[0]:.6e} {v0[1]:.6e} {v0[2]:.6e}\n")
            f.write(f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n")
            f.write(f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write("endsolid MakerStl\n")
    return path


def export_obj(
    parts: list[ExtrudedPart],
    output_path: str | Path,
) -> Path:
    """Export parts as OBJ + MTL files with per-material colors."""
    output_path = Path(output_path)
    mtl_path = output_path.with_suffix(".mtl")
    _write_mtl(parts, mtl_path)
    verts_offset = 0
    with open(output_path, "w") as f:
        f.write(f"# MakerStl OBJ Export\n")
        f.write(f"mtllib {mtl_path.name}\n\n")
        for part in parts:
            f.write(f"o {part.name or part.id}\n")
            f.write(f"usemtl {part.id}\n")
            for v in part.vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            normals = compute_normals(part.vertices, part.faces)
            for n in normals:
                f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
            for face in part.faces:
                f.write(f"f {face[0]+1+verts_offset}//{face[0]+1+verts_offset} "
                        f"{face[1]+1+verts_offset}//{face[1]+1+verts_offset} "
                        f"{face[2]+1+verts_offset}//{face[2]+1+verts_offset}\n")
            f.write("\n")
            verts_offset += len(part.vertices)
    return output_path


def _write_mtl(parts: list[ExtrudedPart], path: Path) -> None:
    with open(path, "w") as f:
        f.write("# MakerStl MTL Export\n\n")
        for part in parts:
            r, g, b = part.color
            f.write(f"newmtl {part.id}\n")
            f.write(f"Kd {r/255:.4f} {g/255:.4f} {b/255:.4f}\n")
            f.write(f"Ka 0.1 0.1 0.1\n")
            f.write(f"Ks 0.5 0.5 0.5\n")
            f.write(f"Ns 100.0\n")
            f.write(f"d 1.0\n")
            f.write("\n")


def export_3mf(
    parts: list[ExtrudedPart],
    output_path: str | Path,
    title: str = "MakerStl Export",
) -> Path:
    """Export parts as a color 3MF file compatible with Bambu Studio.

    Creates a valid OPC package with Bambu-specific metadata for color support.
    """
    output_path = Path(output_path)

    # build unique color -> extruder mapping
    color_to_extruder: dict[tuple[int, int, int], int] = {}
    for part in parts:
        c = tuple(part.color)
        if c not in color_to_extruder:
            color_to_extruder[c] = len(color_to_extruder) + 1

    # fix winding order on all parts before export (without mutating originals)
    fixed_parts = []
    for part in parts:
        fixed = ExtrudedPart(
            id=part.id,
            vertices=part.vertices,
            faces=_ensure_ccw_winding(part.vertices, part.faces),
            color=part.color,
            name=part.name,
        )
        fixed_parts.append(fixed)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _build_content_types())
        zf.writestr("_rels/.rels", _build_rels())

        model_xml = _build_3d_model(fixed_parts, title)
        zf.writestr("3D/3dmodel.model", model_xml)

        model_settings = _build_model_settings(fixed_parts, color_to_extruder)
        zf.writestr("Metadata/model_settings.config", model_settings)

        project_settings = _build_project_settings(fixed_parts, color_to_extruder)
        zf.writestr("Metadata/project_settings.config", project_settings)

    return output_path


def _build_content_types() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="config" ContentType="application/xml"/>
  <Default Extension="json" ContentType="application/json"/>
</Types>"""


def _build_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""


def _build_3d_model(parts: list[ExtrudedPart], title: str) -> str:
    """Build the3MF 3dmodel.model XML.

    Each part is a plain <object> with mesh. No basematerials needed —
    colors are handled by Bambu-specific model_settings.config.
    """
    ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    model = ET.Element("model", xmlns=ns)
    model.set("unit", "millimeter")

    metadata = ET.SubElement(model, "metadata", name="Title")
    metadata.text = title

    resources = ET.SubElement(model, "resources")

    for i, part in enumerate(parts):
        obj_id = str(i + 1)
        obj = ET.SubElement(resources, "object", id=obj_id, type="model")

        mesh = ET.SubElement(obj, "mesh")
        vertices = ET.SubElement(mesh, "vertices")
        for v in part.vertices:
            vt = ET.SubElement(vertices, "vertex")
            vt.set("x", f"{v[0]:.6f}")
            vt.set("y", f"{v[1]:.6f}")
            vt.set("z", f"{v[2]:.6f}")

        triangles = ET.SubElement(mesh, "triangles")
        for face in part.faces:
            tri = ET.SubElement(triangles, "triangle")
            tri.set("v1", str(face[0]))
            tri.set("v2", str(face[1]))
            tri.set("v3", str(face[2]))

    build = ET.SubElement(model, "build")
    for i in range(len(parts)):
        ET.SubElement(build, "item", objectid=str(i + 1))

    ET.indent(model, space=" ")
    xml_str = ET.tostring(model, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str


def _ensure_ccw_winding(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Ensure all triangles are CCW when viewed from +Z direction.

    3MF uses right-hand rule: vertices ordered CCW = normal pointing toward viewer.
    For top faces (Z=height), normal must point up (+Z).
    For bottom faces (Z=0), winding is already reversed by extruder.
    This function ensures consistent winding for correct slicer interpretation.
    """
    fixed_faces = faces.copy()
    for i, face in enumerate(fixed_faces):
        v0, v1, v2 = verts[face[0]], verts[face[1]], verts[face[2]]
        # cross product Z component: positive = CCW from +Z view
        cross_z = (v1[0] - v0[0]) * (v2[1] - v0[1]) - (v1[1] - v0[1]) * (v2[0] - v0[0])
        if cross_z < 0:
            # flip winding to make CCW
            fixed_faces[i] = [face[0], face[2], face[1]]
    return fixed_faces


def _build_model_settings(
    parts: list[ExtrudedPart],
    color_to_extruder: dict[tuple[int, int, int], int],
) -> str:
    """Build Bambu Studio model_settings.config XML.

    Maps each object to an extruder number for color assignment.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<config>',
    ]

    for i, part in enumerate(parts):
        obj_id = str(i + 1)
        extruder = color_to_extruder[tuple(part.color)]
        lines.append(f'  <object id="{obj_id}">')
        lines.append(f'    <metadata key="name" value="{part.name or part.id}"/>')
        lines.append(f'    <metadata key="extruder" value="{extruder}"/>')
        lines.append(f'    <metadata face_count="{len(part.faces)}"/>')
        lines.append(f'  </object>')

    lines.append('</config>')
    return '\n'.join(lines) + '\n'


def _build_project_settings(
    parts: list[ExtrudedPart],
    color_to_extruder: dict[tuple[int, int, int], int],
) -> str:
    """Build Bambu Studio project_settings.config JSON.

    Maps extruder numbers to filament colors.
    """
    # build filament_colour array indexed by extruder number
    max_ext = max(color_to_extruder.values()) if color_to_extruder else 1
    filament_colour = [""] * max_ext
    for color, ext_num in color_to_extruder.items():
        r, g, b = color
        filament_colour[ext_num - 1] = f"#{r:02X}{g:02X}{b:02X}"

    settings = {
        "filament_colour": filament_colour,
        "filament_type": ["PLA"] * max_ext,
        "filament_diameter": ["1.75"] * max_ext,
        "filament_density": ["1.24"] * max_ext,
        "nozzle_diameter": ["0.4"],
        "printer_extruder_id": ["1"] * max_ext,
        "printer_extruder_variant": ["Direct Drive Standard"] * max_ext,
        "extruder_colour": ["#018001"] * max_ext,
    }

    return json.dumps(settings, indent=2) + "\n"
