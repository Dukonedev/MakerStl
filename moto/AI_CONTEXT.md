# AI Project Context - AlphaApp

This file provides the necessary technical context for an AI assistant to resume work on this repository.

## Project Overview
AlphaApp is a browser-based STL texturizer that applies displacement maps to 3D meshes using Three.js. It performs all processing (subdivision, displacement, decimation) locally in the browser.

## Tech Stack
- **Core**: HTML5, Vanilla JavaScript (ES Modules), CSS3.
- **3D Engine**: Three.js (v0.170.0).
- **Libraries**: fflate (for 3MF/ZIP support), standard Three.js addons (OrbitControls, STLLoader, OBJLoader).
- **Server**: `server.py` (Python 3) for static serving and manifest regeneration.

## Architecture & Key Modules
- `js/main.js`: Main entry point, UI event wiring, and global state management.
- `js/viewer.js`: 3D scene setup, viewport logic, and secondary rendering hooks.
- `js/viewNavigator.js`: Camera transition utilities and 'Home' button logic (3D cube removed).
- `js/previewMaterial.js`: custom ShaderMaterial for real-time bump/displacement preview.
- `js/stlLoader.js`: Geometry parsing (STL, OBJ, 3MF).
- `js/displacement.js`: Core baking logic for geometry displacement.
- `js/i18n.js`: Internationalization system (JSON-based).

## Recent Custom Modifications (Session Summary)

### 1. UI Refinement (Left Sidebar & Accordion)
- **Sidebar Swapped**: The settings panel is now on the left side, and the 3D viewport is on the right.
- **Accordion Style**: Implemented in `main.js`.
- Sections "Model" and "Export" are locked open.
- Integrated `localStorage` persistence for collapsed states.
- Auto-expansion of "Displacement Map" section upon model load.

### 2. Visual Aesthetics (Mesh Color)
- Default mesh color changed from teal/bluish to a neutral "Classic Grey" (`0x999999`).
- Shader updated in `previewMaterial.js` (`greyBase`) to ensure consistent appearance during texturing.
- Lights in `viewer.js` adjusted to remove blue tints.

### 3. Navigation & Home Button
- **ViewCube Removed**: The 3D navigation cube was removed to simplify the interface and reduce overhead.
- **Home Button**: Retained as a single action button in the top-right of the viewport for resetting the view.
- **Coordination Fix**: Aligned the navigator camera transition logic to the project's Z-up coordinate system.
- **UI Stability**: Restored missing IDs (`projection-toggle`, `texture-smoothing`, `wireframe-toggle`) that were causing JS initialization crashes.

### 4. DOM Sanitation & Structural Integrity
- **Restructuring**: Performed a complete cleanup of `index.html` to resolve menu duplication issues.
- **Single Instance**: Removed redundant section blocks that were present in both the sidebar and the viewport area.
- **Balanced Tags**: Fixed HTML nesting errors (e.g., double `</main>` tags) to ensure proper browser rendering.
- **Viewport Footer**: Consolidated viewport controls (wireframe, model info) into a dedicated `#viewport-footer`.

## Critical Technical Notes
- **Coordination Space**: The project uses Z-up orientation.
- **Module Imports**: Some modules use cache-busting parameters (`?v=3`) in `index.html` to avoid serving stale code.
- **JS Resilience**: Ensure all IDs referenced in `main.js` exist in `index.html` to prevent startup crashes.

## How to Resume
1. Run `python3 server.py` and open `http://localhost:8090`.
2. Check the browser console for `[ViewNavigator] Initialising Home Button logic...` to verify the module load.
3. The main UI wiring is located in the middle-to-bottom sections of `main.js`.
