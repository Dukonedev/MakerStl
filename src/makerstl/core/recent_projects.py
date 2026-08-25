"""Recent projects manager with thumbnail generation.

Stores recent project metadata in a JSON file and generates
lightweight color-grid thumbnails from project layer colors.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtCore import Qt

MAX_RECENT = 12
METADATA_FILE = ".makerstl_recent.json"


def _metadata_path() -> Path:
    return Path.home() / "Documents" / "MakerStl" / METADATA_FILE


def _thumbnails_dir() -> Path:
    d = Path.home() / "Documents" / "MakerStl" / "thumbnails"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _thumbnail_path(project_path: Path) -> Path:
    safe_name = str(project_path.resolve()).replace("/", "_").replace(" ", "_")
    return _thumbnails_dir() / f"{safe_name}.png"


def load_recent() -> list[dict]:
    """Load the recent projects list from disk."""
    p = _metadata_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # filter out entries whose main file no longer exists
        entries = []
        for e in data:
            pp = Path(e["path"])
            if pp.exists():
                entries.append(e)
        return entries[:MAX_RECENT]
    except Exception:
        return []


def save_recent(entries: list[dict]) -> None:
    """Persist the recent projects list."""
    p = _metadata_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries[:MAX_RECENT], indent=1), encoding="utf-8")


def add_recent(project_path: Path) -> None:
    """Add or move a project to the top of the recent list."""
    entries = load_recent()
    path_str = str(project_path.resolve())
    # remove existing entry for this path
    entries = [e for e in entries if e.get("path") != path_str]
    entries.insert(0, {
        "path": path_str,
        "name": project_path.stem,
        "timestamp": time.time(),
    })
    save_recent(entries)


def remove_recent(project_path: Path) -> None:
    """Remove a project from the recent list."""
    entries = load_recent()
    path_str = str(project_path.resolve())
    entries = [e for e in entries if e.get("path") != path_str]
    save_recent(entries)


def generate_thumbnail(project, project_path: Path, screenshot: QImage | None = None) -> Path | None:
    """Generate a 160x100 thumbnail.

    If *screenshot* (a QImage from the viewport) is provided it is used directly;
    otherwise a synthetic color-grid is painted from layer colours.
    Returns the thumbnail file path, or None on error.
    """
    try:
        if screenshot is not None and not screenshot.isNull():
            img = screenshot.scaled(160, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            from ..models.project import LayerState
            layers = [l for l in project.layers if l.effective_visible]
            if not layers:
                return None

            img = QImage(160, 100, QImage.Format.Format_ARGB32)
            img.fill(QColor(42, 42, 42))

            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            cols = min(len(layers), 6)
            rows = (len(layers) + cols - 1) // cols
            cell_w = 160 // max(cols, 1)
            cell_h = 100 // max(rows, 1)

            for i, layer in enumerate(layers):
                r, g, b = layer.color
                col = i % cols
                row = i // cols
                x = col * cell_w
                y = row * cell_h
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(r, g, b))
                painter.drawRect(x, y, cell_w, cell_h)

            painter.end()

        tp = _thumbnail_path(project_path)
        img.save(str(tp), "PNG")
        return tp
    except Exception:
        return None


def get_thumbnail_path(project_path: Path) -> Path | None:
    """Return the thumbnail path if it exists."""
    tp = _thumbnail_path(project_path)
    return tp if tp.exists() else None
