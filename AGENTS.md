# AGENTS.md — MakerStl

## What this is
SVG-to-3D model desktop app. PySide6/OpenGL frontend, Python geometry pipeline, exports color 3MF (Bambu Studio compatible).

## Quick start
```bash
python3 run.py            # run from repo root
./launch.sh               # same, via shell wrapper
```

## Run single test
```bash
PYTHONPATH=src python3 -m pytest tests/ -x
# or individual file:
PYTHONPATH=src python3 -m pytest tests/test_triangulator.py -x
```

## Build DMG
```bash
./build_macos.sh
```
Output: `builds/MakerStl.dmg` (~107 MB)

## Build Windows
```cmd
build_windows.bat
```
Output: `builds\MakerStl-win\MakerStl\MakerStl.exe`
To zip: `powershell Compress-Archive -Path builds\MakerStl-win\MakerStl -DestinationPath builds\MakerStl-win.zip`

**Windows must be built on a Windows machine** (PyInstaller cannot cross-compile). Install deps first:
```
pip install -r requirements.txt pyinstaller
```

## Architecture

### Three-layer separation
- `src/makerstl/core/` — pure geometry, zero Qt imports (testable alone)
- `src/makerstl/models/` — state dataclasses (Project, LayerState, LayerGroup)
- `src/makerstl/ui/` — PySide6 widgets, signals drive data flow

### Data flow
SVG → `SvgParser` → `triangulate_layers` → `extrude_layer` → `ExtrudedPart` → exporter

### Key modules
| Module | Role |
|--------|------|
| `core/svg_parser.py` | lxml DOM parse, CSS/class fill inheritance, compound path nesting, pyclipper evenodd |
| `core/triangulator.py` | mapbox-earcut (zero interior points, boundary-only vertices) |
| `core/extruder.py` | Parametric extrusion with multi-loop boundary detection, translate_x/y |
| `core/exporters.py` | STL, OBJ+MTL, 3MF (Bambu-specific: `model_settings.config` + `filament_colour`) |
| `core/shapes.py` | Parametric shape generators (SHAPES registry) |
| `core/text.py` | Pillow font rendering → bitmap → contour tracing → polygons |
| `core/undo.py` | Snapshot-based UndoManager (deepcopy, max 50) |
| `core/project_io.py` | Save/load `.makerstl` JSON (full tree + mesh + params) |
| `models/project.py` | Project/LayerGroup/LayerState, merge, subtract, duplicate, ring regeneration |
| `ui/main_window.py` | Orchestrator: wires all panels, import/export, gizmo, undo |
| `ui/viewport.py` | QOpenGLWidget, batch vertex arrays, color-picking, transform gizmo |
| `ui/layer_panel.py` | Photoshop-style tree, drag-drop, multi-select, _EyeColumnDelegate |
| `ui/properties.py` | Context-sensitive panels (base/ring/normal layers), ring parametric editing |
| `ui/welcome.py` | Welcome screen with recent .makerstl files |

## Conventions
- `from __future__ import annotations` everywhere
- numpy arrays for all geometry; `np.float64`
- `_`-prefixed private methods/classes
- `SvgLayer.hole_verts: list[np.ndarray]` for compound path holes
- `ExtrusionParams` stored on `LayerState` (height, z_offset, scale_x/y, chamfer, translate_x/y)
- `is_ring` flag on LayerState → sits at base z-level, has `ring_outer_d`/`ring_thickness` for parametric regeneration
- Dual resource resolution: bundle `Resources/` first, source tree fallback (supports dev + frozen runs)
- `_push_undo()` / `_flush_undo()` lazy batching in MainWindow

## Gotchas
- No `.git`, no CI, no linting/formatting tools configured
- `fontTools` and `PIL` are undeclared runtime deps (used by `core/text.py`)
- 3MF export is hand-built XML + zip (not trimesh despite trimesh being a dep)
- PyInstaller `MakerStl.spec` lists extensive `hiddenimports` — update if adding new deps
- `Project._rebuild_flat_list()` must be called after any tree mutation
- Base layer = last visible layer in tree order; `global_scale` applies only to base
- Test fixtures (`.svg`, `.3mf`) live at repo root, not in a fixtures dir
- Python 3.13 required (uses `X | None` union syntax, `from __future__ import annotations`)
