"""SVG parser: extracts 2D polygon contours from SVG files.

Uses lxml for full DOM parsing (CSS styles, inherited attributes, groups)
and svgpathtools for path discretization (Bézier curves, arcs).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyclipper
from lxml import etree
from shapely.geometry import Polygon
from svgpathtools import (
    Path as SvgPath,
    parse_path,
    svg2paths2,
)

SVG_NS = "http://www.w3.org/2000/svg"


@dataclass
class SvgLayer:
    """A single SVG path converted to 2D polygon vertices."""

    id: str
    name: str
    vertices: np.ndarray  # (N, 2) float64
    color: tuple[int, int, int] = (0, 0, 0)
    fill_opacity: float = 1.0
    closed: bool = True
    hole_verts: list[np.ndarray] = None  # list of (M, 2) hole rings

    def __post_init__(self):
        if self.hole_verts is None:
            self.hole_verts = []

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)


def _parse_length(raw: str | None, fallback: float = 100.0) -> float:
    """Parse SVG length value, stripping units."""
    if not raw:
        return fallback
    m = re.match(r"^([0-9]*\.?[0-9]+)", raw.strip())
    if m:
        return float(m.group(1))
    return fallback


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    """Convert HSL (h 0-360, s/l 0-100%) to RGB (0-255)."""
    s /= 100.0
    l /= 100.0
    c = (1.0 - abs(2.0 * l - 1.0)) * s
    x = c * (1.0 - abs((h / 60.0) % 2.0 - 1.0))
    m = l - c / 2.0
    if h < 60:
        r1, g1, b1 = c, x, 0
    elif h < 120:
        r1, g1, b1 = x, c, 0
    elif h < 180:
        r1, g1, b1 = 0, c, x
    elif h < 240:
        r1, g1, b1 = 0, x, c
    elif h < 300:
        r1, g1, b1 = x, 0, c
    else:
        r1, g1, b1 = c, 0, x
    return (
        max(0, min(255, round((r1 + m) * 255))),
        max(0, min(255, round((g1 + m) * 255))),
        max(0, min(255, round((b1 + m) * 255))),
    )


def _parse_color(raw: str | None, fallback: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
    """Parse CSS color string to (R, G, B).

    Supports: #hex (3/4/6/8), rgb(), rgba(), hsl(), hsla(), named colors.
    """
    if not raw or raw == "none" or raw == "transparent":
        return fallback

    raw = raw.strip().lower()

    if raw.startswith("url("):
        return fallback

    m = re.match(r"^#([0-9a-f]{8})$", raw)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    m = re.match(r"^#([0-9a-f]{6})$", raw)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    m = re.match(r"^#([0-9a-f]{4})$", raw)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))

    m = re.match(r"^#([0-9a-f]{3})$", raw)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))

    m = re.match(r"^rgba?\(\s*([\d.]+%?)\s*,\s*([\d.]+%?)\s*,\s*([\d.]+%?)", raw)
    if m:
        def _ch(v: str) -> int:
            if v.endswith("%"):
                return max(0, min(255, round(float(v[:-1]) * 2.55)))
            return max(0, min(255, round(float(v))))
        return (_ch(m.group(1)), _ch(m.group(2)), _ch(m.group(3)))

    m = re.match(r"^hsla?\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%", raw)
    if m:
        return _hsl_to_rgb(float(m.group(1)), float(m.group(2)), float(m.group(3)))

    named = {
        "red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255),
        "yellow": (255, 255, 0), "cyan": (0, 255, 255), "magenta": (255, 0, 255),
        "black": (0, 0, 0), "white": (255, 255, 255), "orange": (255, 165, 0),
        "purple": (128, 0, 128), "gray": (128, 128, 128), "grey": (128, 128, 128),
        "lime": (0, 255, 0), "maroon": (128, 0, 0), "navy": (0, 0, 128),
        "olive": (128, 128, 0), "teal": (0, 128, 128), "aqua": (0, 255, 255),
        "fuchsia": (255, 0, 255), "silver": (192, 192, 192),
        "darkred": (139, 0, 0), "darkgreen": (0, 100, 0), "darkblue": (0, 0, 139),
        "darkorange": (255, 140, 0), "darkgray": (169, 169, 169),
        "darkgrey": (169, 169, 169), "lightgray": (211, 211, 211),
        "lightgrey": (211, 211, 211), "brown": (165, 42, 42),
        "gold": (255, 215, 0), "pink": (255, 192, 203),
        "coral": (255, 127, 80), "crimson": (220, 20, 60),
        "salmon": (250, 128, 114), "khaki": (240, 230, 140),
        "indigo": (75, 0, 130), "violet": (238, 130, 238),
        "turquoise": (64, 224, 208), "tomato": (255, 99, 71),
        "wheat": (245, 222, 179), "plum": (221, 160, 221),
        "tan": (210, 180, 140), "beige": (245, 245, 220),
        "ivory": (255, 255, 240), "lavender": (230, 230, 250),
    }
    return named.get(raw, fallback)


def _discretize_segment(segment, max_step: float = 0.5) -> list[complex]:
    """Sample a single svgpathtools segment into a polyline."""
    length = segment.length()
    if length < 1e-9:
        return [segment.point(0)]
    n_steps = max(2, int(np.ceil(length / max_step)))
    t_values = np.linspace(0, 1, n_steps + 1)
    return [segment.point(float(t)) for t in t_values]


def _discretize_path(svg_path: SvgPath, max_step: float = 0.5) -> np.ndarray:
    """Convert an svgpathtools Path to (N, 2) numpy array."""
    points: list[complex] = []
    for i, seg in enumerate(svg_path):
        seg_pts = _discretize_segment(seg, max_step)
        if i > 0 and points:
            seg_pts = seg_pts[1:]
        points.extend(seg_pts)
    return np.array([[p.real, p.imag] for p in points], dtype=np.float64)


def _apply_transform(verts: np.ndarray, transform: str) -> np.ndarray:
    """Apply SVG transform string to vertices.

    Handles chained transforms (e.g. 'translate(10,20) rotate(45)')
    and both comma and space separated values in matrix().
    """
    result = verts.copy()

    # find all transform operations in order
    for op in re.finditer(
        r"(matrix|translate|scale|rotate)\(([^)]+)\)",
        transform,
    ):
        name = op.group(1)
        raw = op.group(2).replace(",", " ").split()
        vals = [float(x) for x in raw]

        if name == "matrix" and len(vals) >= 6:
            a, b, c, d, e, f = vals[:6]
            x = result[:, 0] * a + result[:, 1] * c + e
            y = result[:, 0] * b + result[:, 1] * d + f
            result = np.column_stack([x, y])

        elif name == "translate":
            tx = vals[0]
            ty = vals[1] if len(vals) > 1 else 0
            result += np.array([tx, ty])

        elif name == "scale":
            sx = vals[0]
            sy = vals[1] if len(vals) > 1 else sx
            result *= np.array([sx, sy])

        elif name == "rotate" and vals:
            angle_rad = np.radians(vals[0])
            cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
            cx = vals[1] if len(vals) > 2 else 0
            cy = vals[2] if len(vals) > 2 else 0
            if len(vals) > 2:
                result -= np.array([cx, cy])
            rx = result[:, 0] * cos_a - result[:, 1] * sin_a
            ry = result[:, 0] * sin_a + result[:, 1] * cos_a
            result = np.column_stack([rx, ry])
            if len(vals) > 2:
                result += np.array([cx, cy])

    return result


def _strip_ns(tag: str) -> str:
    """Remove namespace from tag."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_css_rules(style_text: str) -> dict[str, dict[str, str]]:
    """Parse CSS text into {selector: {property: value}}.

    Handles comma-separated selectors (e.g. ``.cls-2, .cls-3 { ... }``)
    by registering each individual selector separately.
    """
    rules: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"([^{]+)\{([^}]+)\}", style_text):
        raw_selector = m.group(1).strip()
        props: dict[str, str] = {}
        for decl in m.group(2).split(";"):
            kv = decl.split(":", 1)
            if len(kv) == 2:
                props[kv[0].strip()] = kv[1].strip()
        for sel in raw_selector.split(","):
            sel = sel.strip().lstrip(".")
            if sel:
                rules[sel] = props
    return rules


def _collect_styles(root) -> dict[str, dict[str, str]]:
    """Collect all <style> blocks and return parsed CSS rules."""
    all_rules = {}
    for style_el in root.iter(f"{{{SVG_NS}}}style"):
        if style_el.text:
            all_rules.update(_parse_css_rules(style_el.text))
    return all_rules


def _resolve_fill(element, css_rules: dict, inherited_fill: str | None = None) -> str | None:
    """Resolve the fill color for an element, checking attributes, CSS, and inheritance."""
    def _is_valid_fill(val: str) -> bool:
        return bool(val) and val != "none" and val != "inherit" and not val.startswith("url(")

    # 1. Direct inline style
    style = element.get("style", "")
    for part in style.split(";"):
        kv = part.split(":", 1)
        if len(kv) == 2 and kv[0].strip() == "fill":
            val = kv[1].strip()
            if _is_valid_fill(val):
                return val

    # 2. Direct fill attribute
    fill = element.get("fill")
    if _is_valid_fill(fill):
        return fill

    # 3. CSS class
    cls = element.get("class", "")
    for c in cls.split():
        if c in css_rules and "fill" in css_rules[c]:
            val = css_rules[c]["fill"]
            if _is_valid_fill(val):
                return val

    # 4. Inherited from parent
    if inherited_fill and inherited_fill != "none":
        return inherited_fill

    return None


def _resolve_stroke(element, css_rules: dict, inherited_stroke: str | None = None) -> str | None:
    """Resolve the stroke color for an element (same cascade as fill)."""
    def _is_valid_stroke(val: str) -> bool:
        return bool(val) and val != "none" and val != "inherit" and not val.startswith("url(")

    # 1. Direct inline style
    style = element.get("style", "")
    for part in style.split(";"):
        kv = part.split(":", 1)
        if len(kv) == 2 and kv[0].strip() == "stroke":
            val = kv[1].strip()
            if _is_valid_stroke(val):
                return val

    # 2. Direct stroke attribute
    stroke = element.get("stroke")
    if _is_valid_stroke(stroke):
        return stroke

    # 3. CSS class
    cls = element.get("class", "")
    for c in cls.split():
        if c in css_rules and "stroke" in css_rules[c]:
            val = css_rules[c]["stroke"]
            if _is_valid_stroke(val):
                return val

    # 4. Inherited from parent
    if inherited_stroke and inherited_stroke != "none":
        return inherited_stroke

    return None


def _walk_elements(element, css_rules, inherited_fill=None, inherited_fill_rule=None,
                    inherited_stroke=None, circle_segments=32):
    """Recursively walk SVG DOM, tracking inherited fill/stroke colors and fill-rules."""
    tag = _strip_ns(element.tag)

    # resolve fill for this element
    current_fill = _resolve_fill(element, css_rules, inherited_fill)

    # the effective fill to pass to children: use current if found, else inherit parent's
    effective_fill = current_fill if current_fill else inherited_fill

    # resolve stroke for this element
    current_stroke = _resolve_stroke(element, css_rules, inherited_stroke)
    effective_stroke = current_stroke if current_stroke else inherited_stroke

    # resolve fill-rule (nonzero is SVG default)
    current_fill_rule = element.get("fill-rule", inherited_fill_rule) or "nonzero"

    if tag == "path":
        d = element.get("d", "")
        eid = element.get("id", "")
        transform = element.get("transform", "")
        opacity = element.get("fill-opacity", element.get("opacity"))
        fill_opacity = float(opacity) if opacity else 1.0

        yield {
            "d": d,
            "id": eid,
            "fill": current_fill,
            "stroke": current_stroke,
            "transform": transform,
            "fill_opacity": fill_opacity,
            "fill_rule": current_fill_rule,
        }

    elif tag == "rect":
        x = float(element.get("x", 0))
        y = float(element.get("y", 0))
        w = float(element.get("width", 0))
        h = float(element.get("height", 0))
        eid = element.get("id", "")
        transform = element.get("transform", "")
        opacity = element.get("fill-opacity", element.get("opacity"))
        fill_opacity = float(opacity) if opacity else 1.0

        # convert rect to path d
        d = f"M{x},{y} L{x+w},{y} L{x+w},{y+h} L{x},{y+h} Z"
        yield {
            "d": d,
            "id": eid,
            "fill": current_fill,
            "stroke": current_stroke,
            "transform": transform,
            "fill_opacity": fill_opacity,
            "fill_rule": current_fill_rule,
        }

    elif tag == "circle":
        cx = float(element.get("cx", 0))
        cy = float(element.get("cy", 0))
        r = float(element.get("r", 0))
        eid = element.get("id", "")
        transform = element.get("transform", "")
        opacity = element.get("fill-opacity", element.get("opacity"))
        fill_opacity = float(opacity) if opacity else 1.0

        # approximate circle as polygon
        pts = []
        for i in range(circle_segments):
            angle = 2 * np.pi * i / circle_segments
            pts.append(f"{cx + r * np.cos(angle):.2f},{cy + r * np.sin(angle):.2f}")
        d = "M" + " L".join(pts) + " Z"
        yield {
            "d": d,
            "id": eid,
            "fill": current_fill,
            "stroke": current_stroke,
            "transform": transform,
            "fill_opacity": fill_opacity,
            "fill_rule": current_fill_rule,
        }

    elif tag == "ellipse":
        cx = float(element.get("cx", 0))
        cy = float(element.get("cy", 0))
        rx = float(element.get("rx", 0))
        ry = float(element.get("ry", 0))
        eid = element.get("id", "")
        transform = element.get("transform", "")
        opacity = element.get("fill-opacity", element.get("opacity"))
        fill_opacity = float(opacity) if opacity else 1.0

        pts = []
        for i in range(circle_segments):
            angle = 2 * np.pi * i / circle_segments
            pts.append(f"{cx + rx * np.cos(angle):.2f},{cy + ry * np.sin(angle):.2f}")
        d = "M" + " L".join(pts) + " Z"
        yield {
            "d": d,
            "id": eid,
            "fill": current_fill,
            "stroke": current_stroke,
            "transform": transform,
            "fill_opacity": fill_opacity,
            "fill_rule": current_fill_rule,
        }

    elif tag == "polyline" or tag == "polygon":
        points_str = element.get("points", "")
        eid = element.get("id", "")
        transform = element.get("transform", "")
        opacity = element.get("fill-opacity", element.get("opacity"))
        fill_opacity = float(opacity) if opacity else 1.0

        # parse points
        nums = re.findall(r"[-+]?[0-9]*\.?[0-9]+", points_str)
        coords = [float(n) for n in nums]
        if len(coords) >= 4:
            pairs = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
            d_parts = [f"{pairs[0][0]},{pairs[0][1]}"]
            for p in pairs[1:]:
                d_parts.append(f"{p[0]},{p[1]}")
            if tag == "polygon":
                d_parts.append(f"{pairs[0][0]},{pairs[0][1]}")
            d = "M" + " L".join(d_parts)
            if tag == "polygon":
                d += " Z"
            yield {
                "d": d,
                "id": eid,
                "fill": current_fill,
                "stroke": current_stroke,
                "transform": transform,
                "fill_opacity": fill_opacity,
                "fill_rule": current_fill_rule,
            }

    # recurse into children (groups, etc.)
    for child in element:
        yield from _walk_elements(child, css_rules, effective_fill, current_fill_rule,
                                  effective_stroke, circle_segments)


def _split_compound_path(d: str) -> list[str]:
    """Split a compound SVG path d-string into individual sub-paths.

    Splits at each M/m command (moveto) that starts a new sub-path.
    Uses lookbehind to avoid splitting at M inside commands like 'cm'.
    """
    if not d or not d.strip():
        return []

    # split at M/m that are at start or after another command
    parts = re.split(r'(?<=[ZzCcSsQqTtHhVvLlAa0-9.])\s*(?=[Mm])', d.strip())
    # also split at very start if it begins with M
    result = []
    for part in parts:
        part = part.strip()
        if part:
            result.append(part)
    return result if result else [d.strip()]


_CLIPPER_SCALE = 10000


def _resolve_evenodd(sub_paths_verts: list[np.ndarray]) -> list[np.ndarray]:
    """Resolve compound sub-paths using Clipper evenodd fill-rule.

    Takes a list of 2D vertex arrays (one per sub-path), feeds them to
    Clipper as subjects with evenodd fill, and returns the resolved
    polygons as a list of vertex arrays.
    """
    if len(sub_paths_verts) == 1:
        return sub_paths_verts

    pc = pyclipper.Pyclipper()
    for verts in sub_paths_verts:
        path_int = [(int(x * _CLIPPER_SCALE), int(y * _CLIPPER_SCALE)) for x, y in verts]
        if len(path_int) >= 3:
            pc.AddPath(path_int, pyclipper.PT_SUBJECT, True)

    try:
        result_paths = pc.Execute(
            pyclipper.CT_UNION,
            pyclipper.PFT_EVENODD,
            pyclipper.PFT_EVENODD,
        )
    except pyclipper.ClipperError:
        return sub_paths_verts

    resolved = []
    for rp in result_paths:
        coords = np.array(
            [(x / _CLIPPER_SCALE, y / _CLIPPER_SCALE) for x, y in rp],
            dtype=np.float64,
        )
        if len(coords) >= 3:
            resolved.append(coords)

    return resolved if resolved else sub_paths_verts


def _assemble_compound_paths(
    sub_paths_verts: list[np.ndarray],
) -> list[tuple[np.ndarray, list[np.ndarray]]]:
    """Assemble multiple sub-paths into polygons with proper holes.

    Returns list of (exterior_verts, [hole1_verts, hole2_verts]) tuples.
    """
    if len(sub_paths_verts) == 1:
        verts = sub_paths_verts[0]
        ring = verts
        if not np.allclose(ring[0], ring[-1]):
            ring = np.vstack([ring, ring[0:1]])
        try:
            p = Polygon(ring)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty and p.area > 0:
                return [(verts, [])]
        except Exception:
            pass
        return [(verts, [])]

    indexed: list[tuple[int, Polygon, float]] = []
    for i, verts in enumerate(sub_paths_verts):
        ring = verts
        if not np.allclose(ring[0], ring[-1]):
            ring = np.vstack([ring, ring[0:1]])
        try:
            p = Polygon(ring)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty and p.area > 0:
                indexed.append((i, p, p.area))
        except Exception:
            continue

    if not indexed:
        return [(sub_paths_verts[0], [])]

    indexed.sort(key=lambda x: -x[2])

    n = len(indexed)
    children: dict[int, list[int]] = {i: [] for i in range(n)}
    root_indices: list[int] = []

    for i in range(n):
        bi = indexed[i][1].bounds
        contained = False
        for j in range(i):
            bj = indexed[j][1].bounds
            if bj[0] > bi[0] or bj[1] > bi[1] or bj[2] < bi[2] or bj[3] < bi[3]:
                continue
            if indexed[j][1].contains(indexed[i][1]):
                children[j].append(i)
                contained = True
                break
        if not contained:
            root_indices.append(i)

    result: list[tuple[np.ndarray, list[np.ndarray]]] = []

    def _build(idx: int, depth: int) -> None:
        if depth % 2 == 0:
            exterior = sub_paths_verts[indexed[idx][0]]
            holes: list[np.ndarray] = []
            for ci in children[idx]:
                holes.append(sub_paths_verts[indexed[ci][0]])
            result.append((exterior, holes))
        for ci in children[idx]:
            _build(ci, depth + 1)

    for ri in root_indices:
        _build(ri, 0)

    if not result:
        return [(sub_paths_verts[0], [])]

    return result


class SvgParser:
    """Parse SVG file and return structured layers."""

    def __init__(self, svg_path: str | Path, max_step: float = 0.5,
                 circle_segments: int = 32):
        self.svg_path = Path(svg_path)
        self.max_step = max_step
        self.circle_segments = circle_segments
        self._doc_width: float = 0
        self._doc_height: float = 0

    def parse(self) -> list[SvgLayer]:
        """Parse SVG using full DOM traversal for correct color resolution."""
        tree = etree.parse(str(self.svg_path))
        root = tree.getroot()

        # collect CSS rules from <style> blocks
        css_rules = _collect_styles(root)

        # extract document dimensions
        self._doc_width = _parse_length(root.get("width"), 100)
        self._doc_height = _parse_length(root.get("height"), 100)

        # compute viewBox scale — uniform to preserve aspect ratio
        vb = root.get("viewBox", "")
        scale_x, scale_y = 1.0, 1.0
        if vb:
            vb_parts = vb.replace(",", " ").split()
            if len(vb_parts) == 4:
                vb_w = float(vb_parts[2])
                vb_h = float(vb_parts[3])
                if vb_w > 0 and vb_h > 0:
                    sx = self._doc_width / vb_w
                    sy = self._doc_height / vb_h
                    uniform = min(sx, sy)
                    scale_x = uniform
                    scale_y = uniform

        layers: list[SvgLayer] = []
        idx = 0

        for item in _walk_elements(root, css_rules, circle_segments=self.circle_segments):
            d = item["d"]
            if not d:
                continue

            fill_rule = item.get("fill_rule", "nonzero")
            color = _parse_color(item["fill"]) if item["fill"] else (0, 0, 0)

            # Fallback: if fill is black (default), try stroke color
            if color == (0, 0, 0) and item.get("stroke"):
                stroke_color = _parse_color(item["stroke"])
                if stroke_color != (0, 0, 0):
                    color = stroke_color

            # Always split compound paths into individual sub-paths
            sub_paths = _split_compound_path(d)

            sub_verts_list: list[np.ndarray] = []
            for sub_d in sub_paths:
                try:
                    svg_path = parse_path(sub_d)
                except Exception:
                    continue

                if not svg_path:
                    continue

                try:
                    verts = _discretize_path(svg_path, self.max_step)
                except Exception:
                    continue

                if len(verts) < 3:
                    continue

                # normalize coordinates
                verts[:, 0] *= scale_x
                verts[:, 1] *= scale_y

                # apply transform
                if item["transform"]:
                    verts = _apply_transform(verts, item["transform"])

                sub_verts_list.append(verts)

            if not sub_verts_list:
                continue

            if len(sub_verts_list) > 1:
                if fill_rule == "evenodd":
                    resolved_vs = _resolve_evenodd(sub_verts_list)
                    if len(resolved_vs) > 1:
                        resolved = _assemble_compound_paths(resolved_vs)
                    else:
                        resolved = [(resolved_vs[0], [])]
                else:
                    resolved = _assemble_compound_paths(sub_verts_list)
                for exterior, holes in resolved:
                    layer_id = f"path_{idx}"
                    layer_name = item["id"] or f"Layer {idx + 1}"
                    layers.append(SvgLayer(
                        id=layer_id,
                        name=layer_name,
                        vertices=exterior,
                        color=color,
                        fill_opacity=item["fill_opacity"],
                        hole_verts=holes,
                    ))
                    idx += 1
            else:
                verts = sub_verts_list[0]
                layer_id = item["id"] or f"path_{idx}"
                layer_name = item["id"] or f"Layer {idx + 1}"
                layers.append(SvgLayer(
                    id=layer_id,
                    name=layer_name,
                    vertices=verts,
                    color=color,
                    fill_opacity=item["fill_opacity"],
                ))
                idx += 1

        return layers

    @property
    def document_size(self) -> tuple[float, float]:
        return (self._doc_width, self._doc_height)
