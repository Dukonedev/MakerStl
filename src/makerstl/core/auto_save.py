"""Auto-save: periodic snapshot + crash recovery.

Saves a `.makerstl.auto` file next to the project (or in ~/Documents/MakerStl/auto/)
every N minutes. On startup, detects orphaned auto-saves and offers recovery.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .project_io import save_project
from ..models.project import Project


AUTO_SAVE_INTERVAL_MS = 5 * 60 * 1000  # 5 minutes
AUTO_SAVE_SUFFIX = ".makerstl.auto"
AUTO_SAVE_DIR_NAME = "MakerStl"


def _auto_save_dir() -> Path:
    """Directory for auto-saves of untitled projects."""
    d = Path.home() / "Documents" / AUTO_SAVE_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def auto_save_path_for(project_path: Path | None) -> Path:
    """Return the auto-save file path for a given project path."""
    if project_path is not None:
        return project_path.with_suffix(AUTO_SAVE_SUFFIX)
    return _auto_save_dir() / f"untitled_{int(time.time())}{AUTO_SAVE_SUFFIX}"


def perform_auto_save(project: Project, project_path: Path | None) -> Path | None:
    """Save the project to its auto-save location. Returns the path or None on error."""
    try:
        target = auto_save_path_for(project_path)
        save_project(project, target)
        return target
    except Exception:
        return None


def cleanup_auto_save(project_path: Path | None) -> None:
    """Remove the auto-save file after a successful manual save."""
    try:
        target = auto_save_path_for(project_path)
        if target.exists():
            target.unlink()
    except Exception:
        pass


def find_orphaned_auto_saves() -> list[dict]:
    """Scan for .makerstl.auto files that have no corresponding main file.

    Returns a list of dicts with keys: auto_path, original_path, mtime, size.
    """
    results = []
    search_dirs = [
        _auto_save_dir(),
        Path.home() / "Documents",
        Path.home() / "Downloads",
    ]
    seen: set[Path] = set()
    for d in search_dirs:
        if not d.exists():
            continue
        try:
            for f in d.rglob(f"*{AUTO_SAVE_SUFFIX}"):
                if f in seen:
                    continue
                seen.add(f)
                # derive the original path
                original = f.with_suffix("")  # remove .auto
                if original.exists():
                    continue  # main file exists — not orphaned
                results.append({
                    "auto_path": f,
                    "original_path": original,
                    "mtime": f.stat().st_mtime,
                    "size": f.stat().st_size,
                })
        except Exception:
            continue

    # also scan the project directory itself if we have a recent import dir
    results.sort(key=lambda x: x["mtime"], reverse=True)
    return results
