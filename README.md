# MakerStl

SVG to 3D model converter with color 3MF export, compatible with Bambu Studio / AMS.

## Features

- Import SVG files with automatic color grouping
- Parametric extrusion (height, scale, chamfer, translate)
- Photoshop-style layer management with groups, visibility, drag-drop
- Boolean operations: merge, subtract, duplicate
- Ring layers with parametric outer diameter / thickness
- Transform gizmo (translate, scale) in 3D viewport
- Text-to-3D using system fonts (Pillow rendering)
- Export: STL, OBJ+MTL, color 3MF (Bambu Studio compatible)
- Undo/redo with snapshot history
- Save/load `.makerstl` project files

## Download

Go to [Releases](../../releases) and download:

- **macOS**: `MakerStl.dmg` — drag to Applications, no install needed
- **Windows**: `MakerStl-windows.zip` — extract, run `MakerStl.exe`

No Python or dependencies required — everything is bundled.

## Run from source

```bash
pip install -r requirements.txt
python3 run.py
```

## Build locally

**macOS:**
```bash
pip install -r requirements.txt pyinstaller
./build_macos.sh
# → builds/MakerStl.dmg
```

**Windows:**
```cmd
pip install -r requirements.txt pyinstaller
build_windows.bat
# → builds\MakerStl-win\MakerStl\MakerStl.exe
```

## Architecture

```
src/makerstl/
├── core/        # Pure geometry (zero Qt) — SVG parse, triangulation, extrusion, export
├── models/      # State dataclasses — Project, LayerGroup, LayerState
└── ui/          # PySide6/OpenGL — viewport, panels, gizmo, undo
```

Data flow: SVG → SvgParser → triangulate → extrude → ExtrudedPart → exporter
