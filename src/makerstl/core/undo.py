"""Snapshot-based undo/redo manager."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field


@dataclass
class UndoManager:
    """Maintains undo/redo stacks of project snapshots with action names."""

    _undo_stack: list[tuple[str, dict]] = field(default_factory=list, repr=False)
    _redo_stack: list[tuple[str, dict]] = field(default_factory=list, repr=False)
    _max_depth: int = 50

    def push(self, snapshot: dict, action: str = "Edit") -> None:
        """Save current state to undo stack, clear redo."""
        self._undo_stack.append((action, snapshot))
        if len(self._undo_stack) > self._max_depth:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> tuple[str, dict] | None:
        """Return (action_name, previous state), push current to redo. None if empty."""
        if not self._undo_stack:
            return None
        return self._undo_stack.pop()

    def redo(self) -> tuple[str, dict] | None:
        """Return (action_name, next state), push current to undo. None if empty."""
        if not self._redo_stack:
            return None
        return self._redo_stack.pop()

    def snapshot(self, project) -> dict:
        """Deep-copy the full project state into a dict."""
        return copy.deepcopy({
            "root": project.root,
            "layers": project.layers,
            "global_scale": project.global_scale,
            "global_z_offset": project.global_z_offset,
            "base_height": project.base_height,
            "base_size_x": project.base_size_x,
            "base_size_y": project.base_size_y,
            "svg_path": project.svg_path,
            "name": project.name,
            "_last_import_dir": project._last_import_dir,
        })

    def restore(self, project, snap: dict) -> None:
        """Restore project state from a snapshot dict."""
        project.root = snap["root"]
        project.layers = snap["layers"]
        project.global_scale = snap["global_scale"]
        project.global_z_offset = snap["global_z_offset"]
        project.base_height = snap["base_height"]
        project.base_size_x = snap["base_size_x"]
        project.base_size_y = snap["base_size_y"]
        project.svg_path = snap["svg_path"]
        project.name = snap["name"]
        project._last_import_dir = snap["_last_import_dir"]

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_names(self) -> list[str]:
        return [name for name, _ in reversed(self._undo_stack)]

    @property
    def redo_names(self) -> list[str]:
        return [name for name, _ in self._redo_stack]

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
