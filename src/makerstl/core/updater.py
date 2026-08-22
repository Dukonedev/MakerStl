"""Check for application updates via GitHub Releases API."""

from __future__ import annotations

import re
from pathlib import Path


def _get_current_version() -> str:
    """Read version from __init__.py."""
    init = Path(__file__).parent.parent / "__init__.py"
    text = init.read_text()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else "0.0.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse version string into comparable tuple."""
    v = v.lstrip("v")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


_REPO = "Dukonedev/MakerStl"
_API_URL = f"https://api.github.com/repos/{_REPO}/releases/latest"
_DOWNLOAD_URL = f"https://github.com/{_REPO}/releases/latest"


class UpdateCheckResult:
    __slots__ = ("has_update", "current", "latest", "download_url", "release_notes")

    def __init__(
        self,
        has_update: bool,
        current: str,
        latest: str,
        download_url: str = "",
        release_notes: str = "",
    ) -> None:
        self.has_update = has_update
        self.current = current
        self.latest = latest
        self.download_url = download_url
        self.release_notes = release_notes


def check_for_update() -> UpdateCheckResult:
    """Synchronous check — call from a thread or at startup."""
    import urllib.request
    import json

    current = _get_current_version()
    result = UpdateCheckResult(False, current, current)

    try:
        req = urllib.request.Request(
            _API_URL,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        tag = data.get("tag_name", "")
        if not tag:
            return result

        latest = _parse_version(tag)
        cur = _parse_version(current)

        if latest > cur:
            body = data.get("body", "")[:500]
            result = UpdateCheckResult(
                has_update=True,
                current=current,
                latest=tag,
                download_url=_DOWNLOAD_URL,
                release_notes=body,
            )
    except Exception:
        pass

    return result
