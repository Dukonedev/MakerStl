"""
AlphaApp Dev Server
Serves static files + exposes /api/regenerate to rebuild manifest.json.

Usage:
  python3 server.py [port]      (default: 8090)

Then open http://localhost:8090/ in your browser.
Hit http://localhost:8090/api/regenerate to rebuild textures/manifest.json.
"""

import http.server
import json
import os
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("⚠ Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
ROOT = Path(__file__).parent
TEXTURES_DIR = ROOT / "textures"
MANIFEST_PATH = TEXTURES_DIR / "manifest.json"

THUMB = 80
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga", ".tiff"}
DEFAULT_SCALE = 0.5


def human_name(stem: str) -> str:
    s = stem.replace("_", " ").replace("-", " ")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return " ".join(w.capitalize() for w in s.split())


def cover_crop_thumb(img):
    scale = max(THUMB / img.width, THUMB / img.height)
    w, h = round(img.width * scale), round(img.height * scale)
    img = img.resize((w, h), Image.LANCZOS)
    left = (w - THUMB) // 2
    top = (h - THUMB) // 2
    return img.crop((left, top, left + THUMB, top + THUMB))


def regenerate_manifest():
    """Scan textures/ subfolders, generate thumbs + manifest.json."""
    categories = []

    for child in sorted(TEXTURES_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name.lower() == "thumbs":
            continue

        images = sorted(
            f for f in child.iterdir()
            if f.is_file() and f.suffix.lower() in IMG_EXTS
        )
        if not images:
            continue

        # Read optional config.json
        config_path = child / "config.json"
        overrides = {}
        if config_path.exists():
            try:
                overrides = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        thumb_dir = child / "thumbs"
        thumb_dir.mkdir(exist_ok=True)

        textures = []
        for img_path in images:
            fname = img_path.name
            stem = img_path.stem
            ov = overrides.get(fname, {})

            try:
                pil = Image.open(img_path).convert("RGB")
            except Exception:
                continue

            thumb = cover_crop_thumb(pil)
            thumb_out = thumb_dir / (stem + ".webp")
            thumb.save(thumb_out, "WEBP", quality=80)

            textures.append({
                "name": ov.get("name", human_name(stem)),
                "file": fname,
                "thumb": f"thumbs/{stem}.webp",
                "defaultScale": ov.get("defaultScale", DEFAULT_SCALE),
            })

        if textures:
            categories.append({
                "id": child.name.lower(),
                "label": child.name,
                "textures": textures,
            })

    manifest = {"categories": categories}
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    total = sum(len(c["textures"]) for c in categories)
    return {
        "ok": True,
        "categories": len(categories),
        "textures": total,
        "details": [
            {"name": c["label"], "count": len(c["textures"])} for c in categories
        ],
    }


class AlphaHandler(http.server.SimpleHTTPRequestHandler):
    """Extends SimpleHTTPRequestHandler with /api/regenerate."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        print(f"DEBUG: Received GET request for {self.path}")
        if self.path == "/api/regenerate":
            print("DEBUG: Handling /api/regenerate")
            try:
                result = regenerate_manifest()
                body = json.dumps(result, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                print("DEBUG: /api/regenerate successful")
            except Exception as e:
                print(f"DEBUG: /api/regenerate failed: {e}")
                body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return
        super().do_GET()


if __name__ == "__main__":
    print(f"🚀 AlphaApp server on http://localhost:{PORT}/")
    print(f"   Regenerate: http://localhost:{PORT}/api/regenerate")
    print()
    with http.server.HTTPServer(("", PORT), AlphaHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped.")
