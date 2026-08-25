"""Debug logging to file — GUI apps on macOS swallow stdout/stderr."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


_LOG_PATH: Path | None = None


def _log_path() -> Path:
    global _LOG_PATH
    if _LOG_PATH is None:
        _LOG_PATH = Path.home() / "Documents" / "MakerStl" / "makerstl_debug.log"
        try:
            _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            _LOG_PATH = Path(os.path.join(os.path.expanduser("~"), "makerstl_debug.log"))
    return _LOG_PATH


def log(msg: str) -> None:
    """Append a timestamped line to the debug log file."""
    try:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(_log_path(), "a") as f:
            f.write(f"[{ts}] {msg}\n")
            f.flush()
    except Exception:
        pass


def log_exception(context: str, exc: Exception) -> None:
    """Log an exception with full traceback."""
    try:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(_log_path(), "a") as f:
            f.write(f"[{ts}] {context}: {exc}\n")
            f.write(traceback.format_exc())
            f.write("\n")
            f.flush()
    except Exception:
        pass
