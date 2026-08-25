"""Convert text strings to 2D polygon vertices using Pillow font rendering.

Renders text at high resolution, then extracts contours for clean outlines
that match the actual font appearance including hinting.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union


def _find_font(name: str = "Arial") -> str | None:
    """Find a system font by name, fallback to any available font."""
    search_dirs = [
        "/System/Library/Fonts/Supplemental",
        "/System/Library/Fonts",
        "/Library/Fonts",
        str(Path.home() / "Library/Fonts"),
    ]
    name_lower = name.lower()

    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith((".ttf", ".otf")) and name_lower in f.lower():
                return os.path.join(d, f)

    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith((".ttf", ".otf")):
                return os.path.join(d, f)
    return None


def _get_contour(mask: np.ndarray, tolerance: float = 0.5) -> np.ndarray | None:
    """Get ordered boundary contour using Moore neighborhood tracing (Suzuki & Abe)."""
    h, w = mask.shape

    # find boundary pixels (mask pixels with at least one non-mask 4-neighbor)
    boundary = np.zeros_like(mask, dtype=bool)
    boundary[:, :-1] |= mask[:, :-1] & ~mask[:, 1:]
    boundary[:, 1:] |= mask[:, 1:] & ~mask[:, :-1]
    boundary[:-1, :] |= mask[:-1, :] & ~mask[1:, :]
    boundary[1:, :] |= mask[1:, :] & ~mask[:-1, :]

    ys, xs = np.where(boundary)
    if len(ys) < 3:
        return None

    # start from topmost-leftmost boundary pixel
    start_idx = np.lexsort((xs, ys))[0]
    sx, sy = int(xs[start_idx]), int(ys[start_idx])

    # Moore neighborhood offsets (clockwise from right)
    # 0=E, 1=SE, 2=S, 3=SW, 4=W, 5=NW, 6=N, 7=NE
    dx = [1, 1, 0, -1, -1, -1, 0, 1]
    dy = [0, 1, 1, 1, 0, -1, -1, -1]

    # direction from current to previous pixel (reversed initial direction)
    # start: previous is to the left (W), so we search starting from N (dir=6)
    prev_x, prev_y = sx - 1, sy
    curr_x, curr_y = sx, sy

    points = [(float(sx), float(sy))]
    max_iter = len(ys) * 4
    first = True

    for _ in range(max_iter):
        # find direction from current to previous
        pdx = prev_x - curr_x
        pdy = prev_y - curr_y
        # map to Moore direction index
        pdir = -1
        for d in range(8):
            if dx[d] == pdx and dy[d] == pdy:
                pdir = d
                break

        if pdir == -1:
            pdir = 4  # default to W

        # search clockwise starting from (pdir+1)%8
        found = False
        for i in range(8):
            d = (pdir + 1 + i) % 8
            nx, ny = curr_x + dx[d], curr_y + dy[d]
            if 0 <= nx < w and 0 <= ny < h and mask[ny, nx]:
                prev_x, prev_y = curr_x, curr_y
                curr_x, curr_y = nx, ny
                points.append((float(nx), float(ny)))
                found = True
                break

        if not found:
            break

        if not first and curr_x == sx and curr_y == sy:
            break

        first = False

    if len(points) < 3:
        return None

    # remove closing point (Moore tracing ends at start)
    if len(points) > 1 and points[-1] == points[0]:
        points = points[:-1]

    if len(points) < 3:
        return None

    # Douglas-Peucker simplification on open curve
    pts = np.array(points, dtype=np.float64)
    pts = _douglas_peucker(pts, tolerance)
    return pts


def _render_text_to_image(
    text: str,
    font_path: str,
    font_size: float,
    dpi: int = 300,
) -> tuple[Image.Image, float]:
    """Render text to a high-res black-on-white image.

    Returns (image, scale_factor) where scale_factor converts pixels to mm.
    """
    render_size = int(font_size * dpi / 25.4)
    font = ImageFont.truetype(font_path, render_size)

    dummy = Image.new("L", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0] + 4
    text_h = bbox[3] - bbox[1] + 4

    if text_w <= 0 or text_h <= 0:
        img = Image.new("L", (1, 1), 0)
        return img, 1.0

    img = Image.new("L", (text_w, text_h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((-bbox[0] + 2, -bbox[1] + 2), text, fill=255, font=font)

    scale = 25.4 / dpi
    return img, scale


def _label_connected(binary: np.ndarray) -> tuple[np.ndarray, int]:
    """Connected components labeling (4-connectivity) via scipy."""
    from scipy import ndimage
    labeled, num = ndimage.label(binary.astype(np.int32))
    return labeled, num


def _douglas_peucker(points: np.ndarray, tolerance: float) -> np.ndarray:
    """Douglas-Peucker line simplification."""
    if len(points) < 3:
        return points

    # find point farthest from line between first and last
    start, end = points[0], points[-1]
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)
    if line_len < 1e-10:
        return points[:1]

    line_unit = line_vec / line_len
    diffs = points - start
    projections = diffs @ line_unit
    perp_dists = np.abs(diffs[:, 0] * line_unit[1] - diffs[:, 1] * line_unit[0])

    max_idx = np.argmax(perp_dists)
    max_dist = perp_dists[max_idx]

    if max_dist > tolerance:
        left = _douglas_peucker(points[:max_idx + 1], tolerance)
        right = _douglas_peucker(points[max_idx:], tolerance)
        return np.vstack([left[:-1], right])
    else:
        return np.array([start, end], dtype=np.float64)


def _find_holes_in_mask(mask: np.ndarray, tolerance: float = 0.5) -> list[np.ndarray]:
    """Find holes (interior empty regions) within a binary mask."""
    h, w = mask.shape
    inverted = ~mask

    # find regions that don't touch the border
    visited = np.zeros_like(inverted, dtype=bool)
    holes = []

    # border pixels of inverted = not holes
    if inverted.any():
        # flood fill from all border non-mask pixels
        border_queue = []
        for x in range(w):
            if inverted[0, x]:
                border_queue.append((x, 0))
            if inverted[h-1, x]:
                border_queue.append((x, h-1))
        for y in range(h):
            if inverted[y, 0]:
                border_queue.append((0, y))
            if inverted[y, w-1]:
                border_queue.append((w-1, y))

        visited_border = np.zeros_like(inverted, dtype=bool)
        while border_queue:
            cx, cy = border_queue.pop()
            if cx < 0 or cx >= w or cy < 0 or cy >= h:
                continue
            if visited_border[cy, cx] or not inverted[cy, cx]:
                continue
            visited_border[cy, cx] = True
            border_queue.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])

        # holes are non-visited inverted pixels
        hole_mask = inverted & ~visited_border
        labeled, n = _label_connected(hole_mask)

        for i in range(1, n + 1):
            region_mask = labeled == i
            contour = _get_contour(region_mask, tolerance)
            if contour is not None and len(contour) >= 3:
                holes.append(contour)

    return holes


def text_to_vertices(
    text: str,
    font_name: str = "Arial",
    font_size: float = 100.0,
    spacing: float = 0.0,
    tolerance: float = 0.3,
    dpi: int = 300,
    text_tolerance: float = 0.5,
) -> list[tuple[np.ndarray, list[np.ndarray]]]:
    """Convert text to a list of (outer_verts, [hole_verts]) tuples.

    Uses Pillow for font rendering (includes hinting), then extracts contours.
    Each element represents one character shape.
    """
    font_path = _find_font(font_name)
    if font_path is None:
        raise FileNotFoundError(f"No system font found matching '{font_name}'")

    results: list[tuple[np.ndarray, list[np.ndarray]]] = []
    x_offset = 0.0

    for char in text:
        if char == ' ':
            try:
                f = ImageFont.truetype(font_path, int(font_size * dpi / 25.4))
                bbox = f.getbbox("M")
                x_offset += (bbox[2] - bbox[0]) * 0.35 * 25.4 / dpi
            except Exception:
                x_offset += font_size * 0.35
            continue

        img, scale = _render_text_to_image(char, font_path, font_size, dpi=dpi)
        binary = np.array(img) > 128

        if not binary.any():
            img_w = img.width * scale
            x_offset += img_w + spacing
            continue

        # find connected components
        labeled, n = _label_connected(binary)

        for feature_id in range(1, n + 1):
            mask = labeled == feature_id
            region_pixels = mask.sum()
            if region_pixels < 20:
                continue

            # get outer contour
            outer = _get_contour(mask, text_tolerance)
            if outer is None or len(outer) < 3:
                continue

            # convert to mm: flip Y so text is upright
            outer[:, 0] = outer[:, 0] * scale + x_offset
            outer[:, 1] = (binary.shape[0] - outer[:, 1]) * scale

            # find holes
            holes = []
            hole_contours = _find_holes_in_mask(mask, text_tolerance)
            for hole in hole_contours:
                hole[:, 0] = hole[:, 0] * scale + x_offset
                hole[:, 1] = (binary.shape[0] - hole[:, 1]) * scale
                if len(hole) >= 3:
                    holes.append(hole)

            results.append((outer, holes))

        # advance
        char_width = img.width * scale
        x_offset += char_width + spacing

    return results


def list_available_fonts() -> list[str]:
    """List available system font names."""
    fonts = set()
    search_dirs = [
        "/System/Library/Fonts",
        "/System/Library/Fonts/Supplemental",
        "/Library/Fonts",
        str(Path.home() / "Library/Fonts"),
    ]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith((".ttf", ".otf")):
                fonts.add(Path(f).stem)
    return sorted(fonts)
