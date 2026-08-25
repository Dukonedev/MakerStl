"""
Scan textures/ subfolders and generate:
  1. 80×80 WebP thumbnails  (textures/<Category>/thumbs/<stem>.webp)
  2. textures/manifest.json  (consumed by the web app at runtime)

Usage:
  python generate_manifest.py

To add a new category, simply create a folder inside textures/ and drop
image files into it.  Then re-run this script.
"""

import json
from pathlib import Path
from PIL import Image

THUMB = 80
TEXTURES_DIR = Path(__file__).parent / "textures"
MANIFEST_PATH = TEXTURES_DIR / "manifest.json"

# Image extensions we recognise
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tga", ".tiff"}

# Default scale applied when no config override exists
DEFAULT_SCALE = 0.5

# Optional per-folder config: place a `config.json` inside the category
# folder with entries like:
#   { "dots.png": { "name": "Dots", "defaultScale": 0.1 } }
# Keys not present will be auto-generated from the filename.


def human_name(stem: str) -> str:
    """Turn a filename stem like 'carbonFiber' or 'weave_02' into a nice label."""
    # Replace underscores and split camelCase
    import re
    s = stem.replace("_", " ").replace("-", " ")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    # Capitalize each word
    return " ".join(w.capitalize() for w in s.split())


def cover_crop_thumb(img: Image.Image) -> Image.Image:
    """Resize to cover THUMB×THUMB and center-crop."""
    scale = max(THUMB / img.width, THUMB / img.height)
    w, h = round(img.width * scale), round(img.height * scale)
    img = img.resize((w, h), Image.LANCZOS)
    left = (w - THUMB) // 2
    top = (h - THUMB) // 2
    return img.crop((left, top, left + THUMB, top + THUMB))


def process_category(cat_dir: Path):
    """Process a single category folder.  Returns a manifest entry or None."""
    images = sorted(
        f for f in cat_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMG_EXTS
    )
    if not images:
        return None

    # Read optional per-folder overrides
    config_path = cat_dir / "config.json"
    overrides = {}
    if config_path.exists():
        try:
            overrides = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ Could not parse {config_path}: {e}")

    thumb_dir = cat_dir / "thumbs"
    thumb_dir.mkdir(exist_ok=True)

    textures = []
    total_bytes = 0

    for img_path in images:
        fname = img_path.name
        stem = img_path.stem
        ov = overrides.get(fname, {})

        # Generate thumbnail
        try:
            pil = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"  ⚠ Skipping {fname}: {e}")
            continue

        thumb = cover_crop_thumb(pil)
        thumb_out = thumb_dir / (stem + ".webp")
        thumb.save(thumb_out, "WEBP", quality=80)
        size = thumb_out.stat().st_size
        total_bytes += size

        label = ov.get("name", human_name(stem))
        scale = ov.get("defaultScale", DEFAULT_SCALE)

        textures.append({
            "name": label,
            "file": fname,
            "thumb": f"thumbs/{stem}.webp",
            "defaultScale": scale,
        })
        print(f"    {thumb_out.name:30s} {size:>6,} bytes  →  {label}")

    if not textures:
        return None

    cat_label = cat_dir.name  # folder name IS the label
    print(f"  📁 {cat_label}: {len(textures)} textures, {total_bytes:,} bytes thumbs")
    return {
        "id": cat_dir.name.lower(),
        "label": cat_label,
        "textures": textures,
    }


def main():
    print(f"Scanning {TEXTURES_DIR} …\n")

    categories = []
    for child in sorted(TEXTURES_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.lower() in ("thumbs",):   # skip legacy thumbs folder
            continue
        if child.name.startswith("."):
            continue
        entry = process_category(child)
        if entry:
            categories.append(entry)

    manifest = {"categories": categories}
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    total_tex = sum(len(c["textures"]) for c in categories)
    print(f"\n✅ manifest.json written with {len(categories)} categories, {total_tex} textures total")
    print(f"   {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
