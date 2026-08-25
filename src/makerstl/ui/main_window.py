"""Main application window with 3D viewport, layer panel, and properties."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QMenuBar, QToolBar,
    QStatusBar, QMessageBox, QVBoxLayout, QWidget, QSplitter,
    QColorDialog, QLabel,
)
from PySide6.QtCore import Qt, Slot, QUrl, QMimeData, QTimer
from PySide6.QtGui import QAction, QKeySequence, QColor, QDesktopServices, QDragEnterEvent, QDropEvent

from ..core.svg_parser import SvgParser
from ..core.triangulator import triangulate_layers
from ..core.exporters import export_stl, export_obj, export_3mf
from ..core.undo import UndoManager
from ..core.project_io import save_project, load_project
from ..core.auto_save import perform_auto_save, cleanup_auto_save, AUTO_SAVE_INTERVAL_MS
from ..core.recent_projects import add_recent, generate_thumbnail
from ..models.project import Project, LayerState, LayerGroup
from .viewport import Viewport3D
from .layer_panel import LayerPanel
from .properties import PropertiesPanel
from .shapes_panel import ShapesPanel
from . import icons


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MakerStl — SVG to 3D")
        self.setMinimumSize(1200, 800)

        self._project = Project()
        self._undo_mgr = UndoManager()
        self._undo_pending = False  # lazy push: one undo state per batch
        self._current_project_path: Path | None = None
        self._is_dirty = False

        self._setup_menus()
        self._setup_toolbar()
        self._setup_panels()
        self._setup_statusbar()

        self.setAcceptDrops(True)

        # auto-save timer
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save)
        self._auto_save_timer.start(AUTO_SAVE_INTERVAL_MS)

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------

    def _auto_save(self) -> None:
        if not self._is_dirty:
            return
        result = perform_auto_save(self._project, self._current_project_path)
        if result:
            if self._current_project_path:
                try:
                    screenshot = self._viewport.grabFramebuffer()
                    generate_thumbnail(self._project, self._current_project_path, screenshot=screenshot)
                except Exception:
                    pass
            self._statusbar.showMessage("Auto-saved", 2000)

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith(".svg") or path.endswith(".makerstl"):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".svg"):
                if self._is_dirty or self._project.layers:
                    # add to existing project
                    self._import_svg_add_path(Path(path))
                else:
                    # empty project — import as new
                    self._import_svg_path(Path(path))
                return
            elif path.lower().endswith(".makerstl"):
                try:
                    project = load_project(Path(path))
                    self._apply_new_project(project, Path(path))
                    add_recent(Path(path))
                    self._refresh_thumbnail(Path(path))
                    self._statusbar.showMessage(f"Loaded: {path}", 4000)
                except Exception as e:
                    QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{e}")
                return

    # Palette for assigning visible colors when SVG has no fill info
    _DEFAULT_PALETTE: list[tuple[int, int, int]] = [
        (231, 76, 60),    # red
        (46, 204, 113),   # green
        (52, 152, 219),   # blue
        (241, 196, 15),   # yellow
        (155, 89, 182),   # purple
        (230, 126, 34),   # orange
        (26, 188, 156),   # teal
        (236, 64, 122),   # pink
        (0, 200, 83),     # emerald
        (100, 100, 220),  # cornflower
        (255, 140, 0),    # dark orange
        (0, 191, 255),    # sky blue
        (186, 85, 211),   # medium orchid
        (60, 179, 113),   # medium sea green
        (219, 112, 147),  # pale violet red
        (127, 255, 0),    # chartreuse
    ]

    def _import_svg_path(self, path: Path) -> None:
        """Import SVG as a new project (replaces current)."""
        self._push_undo("Import SVG")
        try:
            parser = SvgParser(str(path),
                               max_step=self._project.quality.curve_resolution,
                               circle_segments=self._project.quality.circle_segments)
            svg_layers = parser.parse()
            doc_w, doc_h = parser.document_size
            self._project._last_import_dir = path.parent
            self._project.svg_path = path
            self._project.name = path.stem
            self._project.root = LayerGroup(name="Root")
            self._project.layers = []
            self._current_project_path = None

            all_verts = np.vstack([sl.vertices for sl in svg_layers if len(sl.vertices) > 0])
            vmin = all_verts.min(axis=0)
            vmax = all_verts.max(axis=0)
            extent = vmax - vmin
            max_extent = max(extent[0], extent[1])
            if max_extent > 0:
                target_size = 100.0
                norm_scale = target_size / max_extent
                norm_offset = vmin.copy()
                for sl in svg_layers:
                    sl.vertices = (sl.vertices - norm_offset) * norm_scale
                    sl.hole_verts = [(hv - norm_offset) * norm_scale for hv in sl.hole_verts]
                for sl in svg_layers:
                    sl.vertices[:, 1] = extent[1] * norm_scale - sl.vertices[:, 1]
                    for i in range(len(sl.hole_verts)):
                        sl.hole_verts[i][:, 1] = extent[1] * norm_scale - sl.hole_verts[i][:, 1]
                self._project.base_size_x = extent[0] * norm_scale
                self._project.base_size_y = extent[1] * norm_scale
                self._project.global_scale = 1.0

            layer_data = [(sl.id, sl.vertices) for sl in svg_layers]
            hole_data = {sl.id: sl.hole_verts for sl in svg_layers if sl.hole_verts}
            meshes = triangulate_layers(layer_data, tolerance=self._project.quality.tolerance,
                                        hole_data=hole_data)

            # If ALL layers are (0,0,0) — SVG had no fill/stroke info —
            # assign a visible palette so the user can see the shapes.
            non_bg = [sl for sl in svg_layers
                      if not (sl.color == (255, 255, 255)
                              or (sl.color == (0, 0, 0) and sl.fill_opacity < 1.0))]
            if non_bg and all(sl.color == (0, 0, 0) for sl in non_bg):
                for i, sl in enumerate(non_bg):
                    pal = self._DEFAULT_PALETTE[i % len(self._DEFAULT_PALETTE)]
                    sl.color = pal

            color_groups: dict[tuple[int, int, int], LayerGroup] = {}
            for sl in svg_layers:
                ls = LayerState(svg_layer=sl, triangulated_mesh=meshes.get(sl.id), color=sl.color)
                c = sl.color
                is_background = c == (255, 255, 255) or c == (0, 0, 0) and sl.fill_opacity < 1.0
                if is_background:
                    ls._parent = self._project.root
                    self._project.root.children.append(ls)
                else:
                    if c not in color_groups:
                        hex_name = f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                        g = self._project.create_group(hex_name)
                        g.color = c
                        color_groups[c] = g
                    group = color_groups[c]
                    ls._parent = group
                    group.children.append(ls)

            self._project._rebuild_flat_list()
            if self._project.layers:
                best = max(self._project.layers, key=lambda l: (
                    (l.svg_layer.vertices.max(axis=0) - l.svg_layer.vertices.min(axis=0)).prod()
                    if len(l.svg_layer.vertices) >= 3 else 0
                ))
                root = self._project.root
                best_group = best._parent
                if best_group is not None and best_group is not root:
                    if best_group in root.children:
                        root.children.remove(best_group)
                    best_group._parent = root
                    root.children.append(best_group)
                elif best in root.children:
                    root.children.remove(best)
                    root.children.append(best)
                self._project._rebuild_flat_list()

            parts = self._project.recompute_extrusions()
            self._layer_panel.refresh()
            self._properties_panel.refresh_dimensions()
            self._viewport.refresh()
            self._viewport.fit_to_scene()
            self._update_title()
            self._mark_dirty()
            total_verts = sum(p.vertex_count for p in parts)
            total_faces = sum(p.face_count for p in parts)
            from ..core.debug_log import log
            log(f"Import SVG done: {len(svg_layers)} layers, {total_verts} verts, {total_faces} faces")
            for i, layer in enumerate(self._project.layers[:5]):
                ep = layer.extruded_part
                vis = layer.effective_visible
                has_mesh = layer.triangulated_mesh is not None
                has_part = ep is not None
                nv = len(ep.vertices) if ep else 0
                nf = len(ep.faces) if ep else 0
                log(f"  layer[{i}] id={layer.svg_layer.id} vis={vis} mesh={has_mesh} part={has_part} v={nv} f={nf} color={layer.color}")
            self._statusbar.showMessage(
                f"Loaded {len(svg_layers)} layers | "
                f"{total_verts} vertices, {total_faces} faces | "
                f"Document: {doc_w:.1f} × {doc_h:.1f} mm", 8000,
            )
            self._flush_undo()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse SVG:\n{e}")

    def _import_svg_add_path(self, path: Path) -> None:
        """Import SVG and add to existing project."""
        self._push_undo("Add SVG")
        try:
            parser = SvgParser(str(path),
                               max_step=self._project.quality.curve_resolution,
                               circle_segments=self._project.quality.circle_segments)
            svg_layers = parser.parse()
            if not svg_layers:
                return
            self._project._last_import_dir = path.parent

            all_verts = np.vstack([sl.vertices for sl in svg_layers if len(sl.vertices) > 0])
            vmin = all_verts.min(axis=0)
            vmax = all_verts.max(axis=0)
            extent = vmax - vmin
            max_extent = max(extent[0], extent[1])
            if max_extent > 0:
                target_size = max(self._project.base_size_x, self._project.base_size_y, 100.0)
                norm_scale = target_size / max_extent
                norm_offset = vmin.copy()
                for sl in svg_layers:
                    sl.vertices = (sl.vertices - norm_offset) * norm_scale
                    sl.hole_verts = [(hv - norm_offset) * norm_scale for hv in sl.hole_verts]
                for sl in svg_layers:
                    sl.vertices[:, 1] = extent[1] * norm_scale - sl.vertices[:, 1]
                    for i in range(len(sl.hole_verts)):
                        sl.hole_verts[i][:, 1] = extent[1] * norm_scale - sl.hole_verts[i][:, 1]

            layer_data = [(sl.id, sl.vertices) for sl in svg_layers]
            hole_data = {sl.id: sl.hole_verts for sl in svg_layers if sl.hole_verts}
            meshes = triangulate_layers(layer_data, tolerance=self._project.quality.tolerance,
                                        hole_data=hole_data)

            non_bg = [sl for sl in svg_layers
                      if not (sl.color == (255, 255, 255)
                              or (sl.color == (0, 0, 0) and sl.fill_opacity < 1.0))]
            if non_bg and all(sl.color == (0, 0, 0) for sl in non_bg):
                for i, sl in enumerate(non_bg):
                    pal = self._DEFAULT_PALETTE[i % len(self._DEFAULT_PALETTE)]
                    sl.color = pal

            svg_name = path.stem
            svg_group = self._project.create_group(svg_name)
            color_groups: dict[tuple[int, int, int], LayerGroup] = {}
            for sl in svg_layers:
                ls = LayerState(svg_layer=sl, triangulated_mesh=meshes.get(sl.id), color=sl.color)
                c = sl.color
                is_background = c == (255, 255, 255) or (c == (0, 0, 0) and sl.fill_opacity < 1.0)
                if is_background:
                    ls._parent = svg_group
                    svg_group.children.append(ls)
                else:
                    if c not in color_groups:
                        hex_name = f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                        g = self._project.create_group(hex_name, parent=svg_group)
                        g.color = c
                        color_groups[c] = g
                    group = color_groups[c]
                    ls._parent = group
                    group.children.append(ls)

            self._project._rebuild_flat_list()
            parts = self._project.recompute_extrusions()
            self._layer_panel.refresh()
            self._properties_panel.refresh_dimensions()
            self._viewport.refresh()
            total_verts = sum(p.vertex_count for p in parts)
            total_faces = sum(p.face_count for p in parts)
            self._statusbar.showMessage(
                f"Added '{svg_name}' ({len(svg_layers)} layers) | "
                f"Total: {total_verts} vertices, {total_faces} faces", 8000,
            )
            self._flush_undo()
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse SVG:\n{e}")

    # ------------------------------------------------------------------
    # Dirty state & close
    # ------------------------------------------------------------------

    def _mark_dirty(self) -> None:
        if not self._is_dirty:
            self._is_dirty = True
            self.setWindowModified(True)
            self._update_title()

    def _mark_clean(self) -> None:
        self._is_dirty = False
        self.setWindowModified(False)
        self._update_title()

    def _update_title(self) -> None:
        if self._current_project_path:
            name = self._current_project_path.stem
        else:
            name = self._project.name if self._project.name else "Untitled"
        dirty = "•" if self._is_dirty else ""
        self.setWindowTitle(f"{dirty}{name} — MakerStl")
        self.setWindowFilePath(str(self._current_project_path) if self._current_project_path else "")

    def closeEvent(self, event) -> None:
        if not self._is_dirty:
            event.accept()
            return

        name = self._current_project_path.stem if self._current_project_path else "Untitled"
        ret = QMessageBox.question(
            self,
            "Unsaved Changes",
            f'Do you want to save changes to "{name}"?',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if ret == QMessageBox.Save:
            self._on_save()
            if self._is_dirty:
                event.ignore()
            else:
                event.accept()
        elif ret == QMessageBox.Discard:
            event.accept()
        else:
            event.ignore()

    def _setup_menus(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setIcon(icons.icon_new())
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.setStatusTip("Create a new empty project")
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        import_action = QAction("&Import SVG...", self)
        import_action.setIcon(icons.icon_import())
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.setStatusTip("Import an SVG file (replaces current project)")
        import_action.triggered.connect(self._on_import_svg)
        file_menu.addAction(import_action)

        import_add_action = QAction("Import SVG (&Add)...", self)
        import_add_action.setIcon(icons.icon_import())
        import_add_action.setShortcut(QKeySequence("Ctrl+Shift+I"))
        import_add_action.setStatusTip("Import an SVG file and add layers to current project")
        import_add_action.triggered.connect(self._on_import_svg_add)
        file_menu.addAction(import_add_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setIcon(icons.icon_save())
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setStatusTip("Save project to disk")
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setIcon(icons.icon_save())
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.setStatusTip("Save project to a new location")
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.setStatusTip("Open a previously saved project")
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_stl_action = QAction("Export &STL...", self)
        export_stl_action.setIcon(icons.icon_export())
        export_stl_action.setStatusTip("Export 3D model as STL (no color)")
        export_stl_action.triggered.connect(self._on_export_stl)
        file_menu.addAction(export_stl_action)

        export_obj_action = QAction("Export &OBJ...", self)
        export_obj_action.setIcon(icons.icon_export())
        export_obj_action.setStatusTip("Export 3D model as OBJ with MTL material file")
        export_obj_action.triggered.connect(self._on_export_obj)
        file_menu.addAction(export_obj_action)

        export_3mf_action = QAction("Export &3MF (Color)...", self)
        export_3mf_action.setIcon(icons.icon_export())
        export_3mf_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_3mf_action.setStatusTip("Export color 3MF compatible with Bambu Studio / AMS")
        export_3mf_action.triggered.connect(self._on_export_3mf)
        file_menu.addAction(export_3mf_action)

        export_sel_action = QAction("Export 3MF Selection...", self)
        export_sel_action.setShortcut(QKeySequence("Ctrl+Alt+E"))
        export_sel_action.setStatusTip("Export only the selected layers as 3MF")
        export_sel_action.triggered.connect(self._on_export_3mf_selection)
        file_menu.addAction(export_sel_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menu_bar.addMenu("&Edit")

        self._menu_undo = QAction("&Undo", self)
        self._menu_undo.setIcon(icons.icon_undo())
        self._menu_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._menu_undo.setEnabled(False)
        self._menu_undo.triggered.connect(self._undo)
        edit_menu.addAction(self._menu_undo)

        self._menu_redo = QAction("&Redo", self)
        self._menu_redo.setIcon(icons.icon_redo())
        self._menu_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._menu_redo.setEnabled(False)
        self._menu_redo.triggered.connect(self._redo)
        edit_menu.addAction(self._menu_redo)

        # View menu
        view_menu = menu_bar.addMenu("&View")

        self._view_properties = QAction("&Properties Panel", self)
        self._view_properties.setCheckable(True)
        self._view_properties.setChecked(True)
        self._view_properties.setShortcut(QKeySequence("Ctrl+1"))
        view_menu.addAction(self._view_properties)

        self._view_shapes = QAction("&Shapes Panel", self)
        self._view_shapes.setCheckable(True)
        self._view_shapes.setChecked(True)
        self._view_shapes.setShortcut(QKeySequence("Ctrl+2"))
        view_menu.addAction(self._view_shapes)

        self._view_history = QAction("&History Panel", self)
        self._view_history.setCheckable(True)
        self._view_history.setChecked(True)
        self._view_history.setShortcut(QKeySequence("Ctrl+3"))
        view_menu.addAction(self._view_history)

        view_menu.addSeparator()

        self._view_gizmo_translate = QAction("Gizmo: &Move", self)
        self._view_gizmo_translate.setCheckable(True)
        self._view_gizmo_translate.setChecked(True)
        self._view_gizmo_translate.setShortcut(QKeySequence("Q"))
        self._view_gizmo_translate.triggered.connect(lambda: self._set_gizmo_mode(0))
        view_menu.addAction(self._view_gizmo_translate)

        self._view_gizmo_rotate = QAction("Gizmo: &Rotate", self)
        self._view_gizmo_rotate.setCheckable(True)
        self._view_gizmo_rotate.setShortcut(QKeySequence("W"))
        self._view_gizmo_rotate.triggered.connect(lambda: self._set_gizmo_mode(1))
        view_menu.addAction(self._view_gizmo_rotate)

        self._view_gizmo_scale = QAction("Gizmo: &Scale", self)
        self._view_gizmo_scale.setCheckable(True)
        self._view_gizmo_scale.setShortcut(QKeySequence("E"))
        self._view_gizmo_scale.triggered.connect(lambda: self._set_gizmo_mode(2))
        view_menu.addAction(self._view_gizmo_scale)

        view_menu.addSeparator()

        fit_action = QAction("&Fit to Scene", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.setStatusTip("Frame all geometry in the viewport")
        fit_action.triggered.connect(lambda: self._viewport.fit_to_scene())
        view_menu.addAction(fit_action)

        # Help menu (rightmost on macOS)
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About MakerStl", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

        help_menu.addSeparator()

        update_action = QAction("Check for &Updates...", self)
        update_action.triggered.connect(self._on_check_updates)
        help_menu.addAction(update_action)

        help_menu.addSeparator()

        donate_action = QAction("Support on &PayPal", self)
        donate_action.triggered.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://www.paypal.com/paypalme/DukoneDev")
        ))
        help_menu.addAction(donate_action)

        bug_action = QAction("Report a &Bug...", self)
        bug_action.triggered.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/Dukonedev/MakerStl/issues/new")
        ))
        help_menu.addAction(bug_action)

        # Wire dock toggle actions
        self._properties_dock = None  # will be set in _setup_panels
        self._shapes_dock = None
        self._view_properties.triggered.connect(self._toggle_properties_dock)
        self._view_shapes.triggered.connect(self._toggle_shapes_dock)
        self._view_history.triggered.connect(self._toggle_history_dock)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_btn = QAction(icons.icon_new(), "New", self)
        new_btn.setShortcut(QKeySequence.StandardKey.New)
        new_btn.setStatusTip("New project (Ctrl+N)")
        new_btn.triggered.connect(self._on_new_project)
        toolbar.addAction(new_btn)

        import_btn = QAction(icons.icon_import(), "Import SVG", self)
        import_btn.setStatusTip("Import SVG — replaces current project (Ctrl+I)")
        import_btn.triggered.connect(self._on_import_svg)
        toolbar.addAction(import_btn)

        import_add_btn = QAction(icons.icon_import(), "Add SVG", self)
        import_add_btn.setStatusTip("Import SVG and add layers to current project (Ctrl+Shift+I)")
        import_add_btn.triggered.connect(self._on_import_svg_add)
        toolbar.addAction(import_add_btn)

        self._save_btn = QAction(icons.icon_save(), "Save", self)
        self._save_btn.setShortcut(QKeySequence.StandardKey.Save)
        self._save_btn.setStatusTip("Save project (Ctrl+S)")
        self._save_btn.triggered.connect(self._on_save)
        toolbar.addAction(self._save_btn)

        self._save_as_btn = QAction(icons.icon_save(), "Save As", self)
        self._save_as_btn.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._save_as_btn.setStatusTip("Save project to a new location")
        self._save_as_btn.triggered.connect(self._on_save_as)
        toolbar.addAction(self._save_as_btn)

        toolbar.addSeparator()

        self._undo_action = QAction(icons.icon_undo(), "Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.setEnabled(False)
        self._undo_action.setStatusTip("Undo last action (Ctrl+Z)")
        self._undo_action.triggered.connect(self._undo)
        toolbar.addAction(self._undo_action)

        self._redo_action = QAction(icons.icon_redo(), "Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.setEnabled(False)
        self._redo_action.setStatusTip("Redo last undone action (Ctrl+Shift+Z)")
        self._redo_action.triggered.connect(self._redo)
        toolbar.addAction(self._redo_action)

        toolbar.addSeparator()

        export_3mf_btn = QAction(icons.icon_export(), "Export 3MF", self)
        export_3mf_btn.setStatusTip("Export color 3MF for Bambu Studio (Ctrl+Shift+E)")
        export_3mf_btn.triggered.connect(self._on_export_3mf)
        toolbar.addAction(export_3mf_btn)

        toolbar.addSeparator()

        # gizmo mode buttons
        self._gizmo_translate_btn = QAction(icons.icon_move(), "Move", self)
        self._gizmo_translate_btn.setCheckable(True)
        self._gizmo_translate_btn.setChecked(True)
        self._gizmo_translate_btn.setStatusTip("Move gizmo — drag to translate selected layer (Q)")
        self._gizmo_translate_btn.triggered.connect(lambda: self._set_gizmo_mode(0))
        toolbar.addAction(self._gizmo_translate_btn)

        self._gizmo_rotate_btn = QAction(icons.icon_rotate(), "Rotate", self)
        self._gizmo_rotate_btn.setCheckable(True)
        self._gizmo_rotate_btn.setStatusTip("Rotate gizmo — drag to rotate selected layer (W)")
        self._gizmo_rotate_btn.triggered.connect(lambda: self._set_gizmo_mode(1))
        toolbar.addAction(self._gizmo_rotate_btn)

        self._gizmo_scale_btn = QAction(icons.icon_scale(), "Scale", self)
        self._gizmo_scale_btn.setCheckable(True)
        self._gizmo_scale_btn.setStatusTip("Scale gizmo — drag to scale selected layer (E)")
        self._gizmo_scale_btn.triggered.connect(lambda: self._set_gizmo_mode(2))
        toolbar.addAction(self._gizmo_scale_btn)

    def _setup_panels(self) -> None:
        # 3D Viewport (central widget)
        self._viewport = Viewport3D(self._project)
        self._viewport.layer_clicked.connect(self._on_viewport_click)
        self._viewport.gizmo_drag_started.connect(lambda: self._push_undo("Transform"))
        self._viewport.transform_changed.connect(self._on_gizmo_transform)
        self.setCentralWidget(self._viewport)

        # Properties Panel
        self._properties_panel = PropertiesPanel(self._project)
        self._properties_panel.parameter_changed.connect(self._on_parameter_changed)
        self._properties_panel.dimensions_changed.connect(self._on_parameter_changed)

        # Layer Panel
        self._layer_panel = LayerPanel(self._project)
        self._layer_panel.layers_selected.connect(self._on_layers_selected)
        self._layer_panel.layer_visibility_changed.connect(self._on_layer_visibility)
        self._layer_panel.group_visibility_changed.connect(self._on_group_visibility)
        self._layer_panel.request_refresh.connect(self._on_refresh_viewport)
        self._layer_panel.merge_requested.connect(self._on_merge_layers)
        self._layer_panel.subtract_requested.connect(self._on_subtract_layers)
        self._layer_panel.undo_needed.connect(lambda: self._push_undo("Layer Edit"))

        # Combined right panel: properties on top, layers below
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._properties_panel)
        splitter.addWidget(self._layer_panel)
        splitter.setStretchFactor(0, 1)  # properties gets 1/3
        splitter.setStretchFactor(1, 2)  # layers gets 2/3
        right_layout.addWidget(splitter)

        self._properties_dock = QDockWidget("Properties", self)
        self._properties_dock.setWidget(right_widget)
        self._properties_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._properties_dock)

        # Left dock: Shapes panel
        self._shapes_panel = ShapesPanel()
        self._shapes_panel.shape_requested.connect(self._on_shape_requested)
        self._shapes_panel.text_requested.connect(self._on_text_requested)
        self._shapes_dock = QDockWidget("Shapes", self)
        self._shapes_dock.setWidget(self._shapes_panel)
        self._shapes_dock.setMinimumWidth(140)
        self._shapes_dock.setMaximumWidth(160)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._shapes_dock)

        # Bottom dock: History panel
        from .history_panel import HistoryPanel
        self._history_panel = HistoryPanel()
        self._history_panel.undo_requested.connect(self._undo)
        self._history_panel.redo_requested.connect(self._redo)
        self._history_dock = QDockWidget("History", self)
        self._history_dock.setWidget(self._history_panel)
        self._history_dock.setMinimumHeight(80)
        self._history_dock.setMaximumHeight(160)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._history_dock)

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — Import an SVG file to begin")
        # permanent info widget
        self._info_label = QLabel()
        self._info_label.setStyleSheet("color: #999; font-size: 11px; padding: 0 8px;")
        self._statusbar.addPermanentWidget(self._info_label)
        self._update_info_bar()

    def _update_info_bar(self) -> None:
        """Refresh the info bar with model statistics."""
        import numpy as np
        all_verts = []
        total_faces = 0
        for layer in self._project.layers:
            if layer.effective_visible and layer.extruded_part:
                part = layer.extruded_part
                if len(part.vertices) > 0:
                    all_verts.append(part.vertices)
                    total_faces += len(part.faces)
        if all_verts:
            combined = np.vstack(all_verts)
            extent = combined.max(axis=0) - combined.min(axis=0)
            dims = f"{extent[0]:.1f} x {extent[1]:.1f} x {extent[2]:.1f}"
            area = self._project.base_size_x * self._project.base_size_y
            self._info_label.setText(
                f"  {dims}  |  {total_faces:,} triangles  |  Base: {area:.0f} mm²  |  "
                f"{len(self._project.layers)} layer(s)"
            )
        else:
            self._info_label.setText("")

    def _toggle_properties_dock(self, checked: bool) -> None:
        if self._properties_dock:
            self._properties_dock.setVisible(checked)

    def _toggle_shapes_dock(self, checked: bool) -> None:
        if self._shapes_dock:
            self._shapes_dock.setVisible(checked)

    def _toggle_history_dock(self, checked: bool) -> None:
        if self._history_dock:
            self._history_dock.setVisible(checked)

    # --- Undo / Redo ---

    def _push_undo(self, action: str = "Edit") -> None:
        """Save current state to undo stack (lazy: one per batch)."""
        if self._undo_pending:
            return
        self._undo_mgr.push(self._undo_mgr.snapshot(self._project), action=action)
        self._undo_pending = True
        self._update_undo_ui()
        self._mark_dirty()

    def _flush_undo(self) -> None:
        """Mark batch as complete so next change creates a new undo state."""
        self._undo_pending = False

    def _undo(self) -> None:
        current = self._undo_mgr.snapshot(self._project)
        result = self._undo_mgr.undo()
        if result is None:
            return
        name, snap = result
        self._undo_mgr._redo_stack.append((name, current))
        self._undo_mgr.restore(self._project, snap)
        self._refresh_after_undo()

    def _redo(self) -> None:
        current = self._undo_mgr.snapshot(self._project)
        result = self._undo_mgr.redo()
        if result is None:
            return
        name, snap = result
        self._undo_mgr._undo_stack.append((name, current))
        self._undo_mgr.restore(self._project, snap)
        self._refresh_after_undo()

    def _refresh_after_undo(self) -> None:
        """Refresh all panels after an undo/redo operation."""
        self._project._rebuild_flat_list()
        self._project.recompute_extrusions()
        self._layer_panel.refresh()
        self._viewport.refresh()
        self._properties_panel.refresh_dimensions()
        self._viewport.fit_to_scene()
        self._update_undo_ui()
        self._update_info_bar()

    def _update_undo_ui(self) -> None:
        """Update undo/redo buttons and history panel."""
        self._undo_action.setEnabled(self._undo_mgr.can_undo)
        self._redo_action.setEnabled(self._undo_mgr.can_redo)
        self._menu_undo.setEnabled(self._undo_mgr.can_undo)
        self._menu_redo.setEnabled(self._undo_mgr.can_redo)
        self._history_panel.update_history(
            self._undo_mgr.undo_names, self._undo_mgr.redo_names
        )

    def _set_gizmo_mode(self, mode: int) -> None:
        """Switch gizmo mode and update toolbar button states."""
        from ..ui.viewport import GIZMO_TRANSLATE, GIZMO_ROTATE, GIZMO_SCALE
        self._viewport.set_gizmo_mode(mode)
        self._gizmo_translate_btn.setChecked(mode == GIZMO_TRANSLATE)
        self._gizmo_rotate_btn.setChecked(mode == GIZMO_ROTATE)
        self._gizmo_scale_btn.setChecked(mode == GIZMO_SCALE)
        self._view_gizmo_translate.setChecked(mode == GIZMO_TRANSLATE)
        self._view_gizmo_rotate.setChecked(mode == GIZMO_ROTATE)
        self._view_gizmo_scale.setChecked(mode == GIZMO_SCALE)

    # --- Slots ---

    @Slot()
    def _on_about(self) -> None:
        from .. import __version__
        msg = QMessageBox(self)
        msg.setWindowTitle("About MakerStl")
        msg.setIconPixmap(icons.icon_new().pixmap(64, 64))
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            f"<h2 style='margin-bottom:4px'>MakerStl</h2>"
            f"<p style='color:#888; margin-top:0'>Version {__version__}</p>"
            f"<p>SVG to 3D model converter<br>"
            f"with color 3MF export for Bambu Studio / AMS.</p>"
            f"<hr style='border-color:#555'>"
            f"<p><a href='https://github.com/Dukonedev/MakerStl'>GitHub Repository</a></p>"
            f"<p><a href='https://github.com/Dukonedev/MakerStl/releases'>Releases</a></p>"
            f"<p><a href='https://makerworld.com/it/@VirtuPrinto/upload'>Support VirtuPrinto on Makerworld</a></p>"
            f"<p style='color:#888; font-size:11px; margin-top:12px'>"
            f"Copyright &copy; 2026 DukoneDev</p>"
        )
        msg.exec()

    @Slot()
    def _on_check_updates(self) -> None:
        from ..core.updater import check_for_update
        from PySide6.QtGui import QDesktopServices as _QDS
        from PySide6.QtCore import QUrl as _QUrl

        result = check_for_update()
        if result.has_update:
            msg = QMessageBox(self)
            msg.setWindowTitle("Update Available")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"MakerStl {result.latest} is available!")
            msg.setInformativeText(
                f"You are running version {result.current}.\n"
                f"Version {result.latest} is ready to download."
            )
            if result.release_notes:
                msg.setDetailedText(result.release_notes)
            dl_btn = msg.addButton("Download", QMessageBox.AcceptRole)
            msg.addButton("OK", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() == dl_btn:
                _QDS.openUrl(_QUrl(result.download_url))
        else:
            QMessageBox.information(
                self, "No Updates",
                f"You are running the latest version ({result.current}).",
            )

    @Slot()
    def _on_new_project(self) -> None:
        """Create a new empty project."""
        self._push_undo("New Project")
        self._project = Project()
        self._current_project_path = None
        self._undo_mgr.clear()
        self._update_undo_ui()
        self._update_title()
        self._viewport.set_project(self._project)
        self._layer_panel.set_project(self._project)
        self._properties_panel.set_project(self._project)
        self._refresh_after_undo()
        self._statusbar.showMessage("New empty project", 4000)

    @Slot()
    def _on_import_svg(self) -> None:
        # start from last import dir, or ~/Downloads, or home
        start_dir = ""
        if self._project._last_import_dir and self._project._last_import_dir.is_dir():
            start_dir = str(self._project._last_import_dir)
        else:
            downloads = Path.home() / "Downloads"
            start_dir = str(downloads) if downloads.is_dir() else str(Path.home())

        path, _ = QFileDialog.getOpenFileName(
            self, "Import SVG File", start_dir,
            "SVG Files (*.svg);;All Files (*)"
        )
        if not path:
            return

        self._push_undo("Import SVG")

        try:
            parser = SvgParser(path,
                               max_step=self._project.quality.curve_resolution,
                               circle_segments=self._project.quality.circle_segments)
            svg_layers = parser.parse()
            doc_w, doc_h = parser.document_size

            # save import folder for export default
            self._project._last_import_dir = Path(path).parent

            # reset project
            self._project.svg_path = Path(path)
            self._project.name = Path(path).stem
            self._project.root = LayerGroup(name="Root")
            self._project.layers = []
            self._current_project_path = None  # clear save path on new import

            # normalize: fit all geometry into a reasonable bounding box
            all_verts = np.vstack([sl.vertices for sl in svg_layers if len(sl.vertices) > 0])
            vmin = all_verts.min(axis=0)
            vmax = all_verts.max(axis=0)
            extent = vmax - vmin
            max_extent = max(extent[0], extent[1])
            if max_extent > 0:
                target_size = 100.0
                norm_scale = target_size / max_extent
                norm_offset = vmin.copy()
                for sl in svg_layers:
                    sl.vertices = (sl.vertices - norm_offset) * norm_scale
                    sl.hole_verts = [
                        (hv - norm_offset) * norm_scale for hv in sl.hole_verts
                    ]
                # flip Y axis: SVG Y-down -> OpenGL Y-up
                for sl in svg_layers:
                    sl.vertices[:, 1] = extent[1] * norm_scale - sl.vertices[:, 1]
                    for i in range(len(sl.hole_verts)):
                        sl.hole_verts[i][:, 1] = extent[1] * norm_scale - sl.hole_verts[i][:, 1]

                # store normalized extents for the dimensions panel
                self._project.base_size_x = extent[0] * norm_scale
                self._project.base_size_y = extent[1] * norm_scale
                self._project.global_scale = 1.0

            # triangulate all layers
            layer_data = [(sl.id, sl.vertices) for sl in svg_layers]
            hole_data = {sl.id: sl.hole_verts for sl in svg_layers if sl.hole_verts}
            meshes = triangulate_layers(layer_data, tolerance=self._project.quality.tolerance,
                                        hole_data=hole_data)

            # If ALL layers are (0,0,0), assign visible palette colors
            non_bg = [sl for sl in svg_layers
                      if not (sl.color == (255, 255, 255)
                              or (sl.color == (0, 0, 0) and sl.fill_opacity < 1.0))]
            if non_bg and all(sl.color == (0, 0, 0) for sl in non_bg):
                for i, sl in enumerate(non_bg):
                    pal = self._DEFAULT_PALETTE[i % len(self._DEFAULT_PALETTE)]
                    sl.color = pal

            # create layer states and group by color
            color_groups: dict[tuple[int, int, int], LayerGroup] = {}
            for sl in svg_layers:
                ls = LayerState(
                    svg_layer=sl,
                    triangulated_mesh=meshes.get(sl.id),
                    color=sl.color,
                )

                # auto-group by color (skip white/transparent background)
                c = sl.color
                is_background = c == (255, 255, 255) or c == (0, 0, 0) and sl.fill_opacity < 1.0
                if is_background:
                    # background stays in root
                    ls._parent = self._project.root
                    self._project.root.children.append(ls)
                else:
                    if c not in color_groups:
                        # name group from hex color
                        hex_name = f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                        g = self._project.create_group(hex_name)
                        g.color = c
                        color_groups[c] = g
                    group = color_groups[c]
                    ls._parent = group
                    group.children.append(ls)

            self._project._rebuild_flat_list()

            # move the largest layer's group to root's bottom → it becomes the base
            if self._project.layers:
                best = max(
                    self._project.layers,
                    key=lambda l: (
                        (l.svg_layer.vertices.max(axis=0) - l.svg_layer.vertices.min(axis=0))
                        .prod() if len(l.svg_layer.vertices) >= 3 else 0
                    ),
                )
                root = self._project.root
                best_group = best._parent
                if best_group is not None and best_group is not root:
                    # layer is inside a group — move the whole group
                    if best_group in root.children:
                        root.children.remove(best_group)
                    best_group._parent = root
                    root.children.append(best_group)
                elif best in root.children:
                    # layer is directly in root
                    root.children.remove(best)
                    root.children.append(best)
                self._project._rebuild_flat_list()

            # recompute
            parts = self._project.recompute_extrusions()

            # update UI
            self._layer_panel.refresh()
            self._properties_panel.refresh_dimensions()
            self._viewport.fit_to_scene()
            self._update_title()
            self._mark_dirty()

            total_verts = sum(p.vertex_count for p in parts)
            total_faces = sum(p.face_count for p in parts)
            self._statusbar.showMessage(
                f"Loaded {len(svg_layers)} layers | "
                f"{total_verts} vertices, {total_faces} faces | "
                f"Document: {doc_w:.1f} × {doc_h:.1f} mm",
                8000,
            )
            self._flush_undo()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse SVG:\n{e}")

    @Slot()
    def _on_import_svg_add(self) -> None:
        """Import an SVG file and add its layers to the current project."""
        start_dir = ""
        if self._project._last_import_dir and self._project._last_import_dir.is_dir():
            start_dir = str(self._project._last_import_dir)
        else:
            downloads = Path.home() / "Downloads"
            start_dir = str(downloads) if downloads.is_dir() else str(Path.home())

        path, _ = QFileDialog.getOpenFileName(
            self, "Import SVG (Add to Project)", start_dir,
            "SVG Files (*.svg);;All Files (*)"
        )
        if not path:
            return

        self._push_undo("Add SVG")

        try:
            parser = SvgParser(path,
                               max_step=self._project.quality.curve_resolution,
                               circle_segments=self._project.quality.circle_segments)
            svg_layers = parser.parse()
            doc_w, doc_h = parser.document_size

            if not svg_layers:
                QMessageBox.information(self, "Import SVG", "No layers found in SVG.")
                return

            self._project._last_import_dir = Path(path).parent

            # normalize new SVG into the same coordinate space
            all_verts = np.vstack([sl.vertices for sl in svg_layers if len(sl.vertices) > 0])
            vmin = all_verts.min(axis=0)
            vmax = all_verts.max(axis=0)
            extent = vmax - vmin
            max_extent = max(extent[0], extent[1])
            if max_extent > 0:
                # use the project's existing base_size as target
                target_size = max(self._project.base_size_x, self._project.base_size_y, 100.0)
                norm_scale = target_size / max_extent
                norm_offset = vmin.copy()
                for sl in svg_layers:
                    sl.vertices = (sl.vertices - norm_offset) * norm_scale
                    sl.hole_verts = [
                        (hv - norm_offset) * norm_scale for hv in sl.hole_verts
                    ]
                # flip Y axis
                for sl in svg_layers:
                    sl.vertices[:, 1] = extent[1] * norm_scale - sl.vertices[:, 1]
                    for i in range(len(sl.hole_verts)):
                        sl.hole_verts[i][:, 1] = extent[1] * norm_scale - sl.hole_verts[i][:, 1]

            # triangulate
            layer_data = [(sl.id, sl.vertices) for sl in svg_layers]
            hole_data = {sl.id: sl.hole_verts for sl in svg_layers if sl.hole_verts}
            meshes = triangulate_layers(layer_data, tolerance=self._project.quality.tolerance,
                                        hole_data=hole_data)

            # If ALL layers are (0,0,0), assign visible palette colors
            non_bg = [sl for sl in svg_layers
                      if not (sl.color == (255, 255, 255)
                              or (sl.color == (0, 0, 0) and sl.fill_opacity < 1.0))]
            if non_bg and all(sl.color == (0, 0, 0) for sl in non_bg):
                for i, sl in enumerate(non_bg):
                    pal = self._DEFAULT_PALETTE[i % len(self._DEFAULT_PALETTE)]
                    sl.color = pal

            # create a new group for this SVG
            svg_name = Path(path).stem
            svg_group = self._project.create_group(svg_name)

            # create layer states and add to the group
            color_groups: dict[tuple[int, int, int], LayerGroup] = {}
            for sl in svg_layers:
                ls = LayerState(
                    svg_layer=sl,
                    triangulated_mesh=meshes.get(sl.id),
                    color=sl.color,
                )
                c = sl.color
                is_background = c == (255, 255, 255) or (c == (0, 0, 0) and sl.fill_opacity < 1.0)
                if is_background:
                    ls._parent = svg_group
                    svg_group.children.append(ls)
                else:
                    if c not in color_groups:
                        hex_name = f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
                        g = self._project.create_group(hex_name, parent=svg_group)
                        g.color = c
                        color_groups[c] = g
                    group = color_groups[c]
                    ls._parent = group
                    group.children.append(ls)

            self._project._rebuild_flat_list()
            parts = self._project.recompute_extrusions()

            # update UI
            self._layer_panel.refresh()
            self._properties_panel.refresh_dimensions()
            self._viewport.refresh()

            total_verts = sum(p.vertex_count for p in parts)
            total_faces = sum(p.face_count for p in parts)
            self._statusbar.showMessage(
                f"Added '{svg_name}' ({len(svg_layers)} layers) | "
                f"Total: {total_verts} vertices, {total_faces} faces",
                8000,
            )
            self._flush_undo()

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to parse SVG:\n{e}")

    @Slot()
    def _on_export_stl(self) -> None:
        start_dir = str(self._project._last_import_dir) if self._project._last_import_dir else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export STL", f"{start_dir}/{self._project.name}.stl",
            "STL Files (*.stl)"
        )
        if not path:
            return

        parts = self._project.recompute_extrusions()
        try:
            export_stl(parts, path)
            self._statusbar.showMessage(f"Exported STL: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export STL:\n{e}")

    @Slot()
    def _on_export_obj(self) -> None:
        start_dir = str(self._project._last_import_dir) if self._project._last_import_dir else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export OBJ", f"{start_dir}/{self._project.name}.obj",
            "OBJ Files (*.obj)"
        )
        if not path:
            return

        parts = self._project.recompute_extrusions()
        try:
            export_obj(parts, path)
            self._statusbar.showMessage(f"Exported OBJ: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export OBJ:\n{e}")

    @Slot()
    def _on_export_3mf(self) -> None:
        start_dir = str(self._project._last_import_dir) if self._project._last_import_dir else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export 3MF (Color)", f"{start_dir}/{self._project.name}.3mf",
            "3MF Files (*.3mf)"
        )
        if not path:
            return

        parts = self._project.recompute_extrusions()
        try:
            export_3mf(parts, path, title=self._project.name)
            self._statusbar.showMessage(f"Exported 3MF: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export 3MF:\n{e}")

    @Slot()
    def _on_export_3mf_selection(self) -> None:
        """Export only the currently selected layers as 3MF."""
        selected_ids = self._layer_panel.get_selected_layer_ids()
        if not selected_ids:
            QMessageBox.information(self, "Export Selection",
                                    "No layers selected. Select one or more layers first.")
            return

        start_dir = str(self._project._last_import_dir) if self._project._last_import_dir else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Selection 3MF", f"{start_dir}/{self._project.name}_selection.3mf",
            "3MF Files (*.3mf)"
        )
        if not path:
            return

        all_parts = self._project.recompute_extrusions()
        # filter to only selected parts
        selected_parts = [p for p in all_parts if p.svg_layer.id in selected_ids]
        if not selected_parts:
            QMessageBox.information(self, "Export Selection",
                                    "Selected layers have no geometry to export.")
            return

        try:
            export_3mf(selected_parts, path, title=f"{self._project.name} (selection)")
            self._statusbar.showMessage(f"Exported selection ({len(selected_parts)} parts): {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export selection:\n{e}")

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        if self._current_project_path is not None:
            self._save_to(self._current_project_path)
        else:
            self._on_save_as()

    def _on_save_as(self) -> None:
        if self._project._last_import_dir and self._project._last_import_dir.is_dir():
            start_dir = str(self._project._last_import_dir)
        else:
            start_dir = str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", f"{start_dir}/{self._project.name}.makerstl",
            "MakerStl Project (*.makerstl)"
        )
        if not path:
            return
        self._save_to(Path(path))

    def _refresh_thumbnail(self, path: Path) -> None:
        """Regenerate the viewport thumbnail for *path* after a short delay."""
        from PySide6.QtCore import QTimer
        QTimer.singleShot(300, lambda p=path: self._do_refresh_thumbnail(p))

    def _do_refresh_thumbnail(self, path: Path) -> None:
        try:
            screenshot = self._viewport.grabFramebuffer()
            generate_thumbnail(self._project, path, screenshot=screenshot)
        except Exception:
            pass

    def _save_to(self, path: Path) -> None:
        try:
            save_project(self._project, path)
            self._current_project_path = path
            cleanup_auto_save(path)
            add_recent(path)
            screenshot = self._viewport.grabFramebuffer()
            generate_thumbnail(self._project, path, screenshot=screenshot)
            self._mark_clean()
            self._statusbar.showMessage(f"Saved: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save project:\n{e}")

    def _on_open_project(self) -> None:
        start_dir = str(self._project._last_import_dir) if self._project._last_import_dir else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", start_dir,
            "MakerStl Project (*.makerstl)"
        )
        if not path:
            return
        try:
            project = load_project(Path(path))
            self._apply_new_project(project, Path(path))
            add_recent(Path(path))
            self._refresh_thumbnail(Path(path))
            self._statusbar.showMessage(f"Loaded: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{e}")

    def _load_project_file(self, path: Path) -> None:
        """Load a project from a given path (used by welcome screen recent files)."""
        try:
            project = load_project(path)
            self._apply_new_project(project, path)
            add_recent(path)
            self._refresh_thumbnail(path)
            self._statusbar.showMessage(f"Loaded: {path}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{e}")

    def _apply_new_project(self, project: 'Project', path: Path) -> None:
        """Replace the current project and update all panels."""
        self._project = project
        self._current_project_path = path
        self._undo_mgr.clear()
        self._update_undo_ui()
        self._mark_clean()
        # re-point all panels to the new project
        self._viewport.set_project(project)
        self._layer_panel.set_project(project)
        self._properties_panel.set_project(project)
        self._refresh_after_undo()

    @Slot(str)
    def _on_layer_selected(self, layer_id: str) -> None:
        self._properties_panel.set_layers([layer_id])
        self._viewport.highlight_layer(layer_id)

    @Slot(list)
    def _on_layers_selected(self, layer_ids: list[str]) -> None:
        self._properties_panel.set_layers(layer_ids)
        if len(layer_ids) == 1:
            self._viewport.highlight_layer(layer_ids[0])
        else:
            self._viewport.highlight_layer("")

    @Slot(str, bool)
    def _on_layer_visibility(self, layer_id: str, visible: bool) -> None:
        self._push_undo("Visibility")
        layer = self._project.get_layer_by_id(layer_id)
        if layer:
            layer.visible = visible
            self._project.recompute_extrusions()
            self._viewport.refresh()
        self._flush_undo()

    @Slot(object, bool)
    def _on_group_visibility(self, group: LayerGroup, visible: bool) -> None:
        self._push_undo("Visibility")
        group.visible = visible
        self._project.recompute_extrusions()
        self._viewport.refresh()
        self._flush_undo()

    @Slot()
    def _on_parameter_changed(self) -> None:
        self._push_undo("Parameter Change")
        self._project.recompute_extrusions()
        self._viewport.refresh()
        self._flush_undo()

    @Slot()
    def _on_refresh_viewport(self) -> None:
        self._project.recompute_extrusions()
        self._viewport.refresh()

    @Slot(str)
    def _on_viewport_click(self, layer_id: str) -> None:
        if not layer_id:
            return
        self._properties_panel.set_layers([layer_id])
        self._viewport.highlight_layer(layer_id)

    @Slot()
    def _on_gizmo_transform(self) -> None:
        """Gizmo drag completed — refresh panels and push undo."""
        self._properties_panel.refresh_dimensions()
        self._layer_panel.refresh()
        self._update_info_bar()
        self._statusbar.showMessage("Transform applied", 3000)

    @Slot(list)
    def _on_merge_layers(self, layer_ids: list[str]) -> None:
        if len(layer_ids) < 2:
            return
        # pre-fill color from first layer
        first = self._project.get_layer_by_id(layer_ids[0])
        initial = QColor(*first.color) if first else QColor(0, 0, 0)
        color = QColorDialog.getColor(initial, self, "Merge — Choose Color")
        if not color.isValid():
            return
        self._push_undo("Merge Layers")
        rgb = (color.red(), color.green(), color.blue())
        self._project.merge_layers(layer_ids, color=rgb)
        self._project.recompute_extrusions()
        self._layer_panel.refresh()
        self._viewport.refresh()
        self._flush_undo()

    @Slot(str, list)
    def _on_subtract_layers(self, base_id: str, cutter_ids: list[str]) -> None:
        self._push_undo("Subtract Layers")
        result = self._project.subtract_layers(base_id, cutter_ids)
        if result:
            self._project.recompute_extrusions()
            self._layer_panel.refresh()
            self._viewport.refresh()
            self._statusbar.showMessage(f"Subtracted {len(cutter_ids)} layer(s) from base", 4000)
        else:
            self._statusbar.showMessage("Subtract failed — no geometry remaining", 4000)
        self._flush_undo()

    @Slot(str, float, float)
    def _on_shape_requested(self, shape_key: str, w: float, h: float) -> None:
        from ..core.shapes import SHAPES
        from ..core.svg_parser import SvgLayer
        from ..core.triangulator import triangulate_layer
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor

        _, func = SHAPES[shape_key]
        kwargs = {}
        hole_verts = []
        if shape_key == "star":
            kwargs = {"outer_r": w / 2, "inner_r": w / 4}
        elif shape_key in ("rect", "diamond"):
            kwargs = {"width": w, "height": h}
        elif shape_key == "triangle":
            kwargs = {"size": w}
        elif shape_key == "cross":
            kwargs = {"arm": w / 4, "length": w}
        elif shape_key == "ellipse":
            kwargs = {"rx": w / 2, "ry": h / 2, "segments": self._project.quality.circle_segments}
        elif shape_key == "ring":
            outer_verts, inner_hole = func(outer_diameter=w, thickness=h,
                                           segments=self._project.quality.circle_segments)
            verts = outer_verts
            hole_verts = [inner_hole]
            ring_outer_d = w
            ring_thickness = h
        else:
            kwargs = {"radius": w / 2, "segments": self._project.quality.circle_segments}

        if shape_key != "ring":
            verts = func(**kwargs)

        # ask for color
        color = QColorDialog.getColor(QColor(128, 128, 128), self, "Shape Color")
        if not color.isValid():
            return
        self._push_undo("Add Shape")
        rgb = (color.red(), color.green(), color.blue())

        mesh = triangulate_layer(verts, tolerance=self._project.quality.tolerance,
                                 hole_verts=hole_verts if hole_verts else None)
        svg_layer = SvgLayer(
            id=f"shape_{shape_key}_{id(verts)}",
            name=shape_key.capitalize(),
            vertices=verts,
            color=rgb,
            hole_verts=hole_verts,
        )

        ls = LayerState(svg_layer=svg_layer, triangulated_mesh=mesh, color=rgb,
                        is_ring=(shape_key == "ring"),
                        ring_outer_d=ring_outer_d if shape_key == "ring" else 14.0,
                        ring_thickness=ring_thickness if shape_key == "ring" else 3.0)

        if shape_key == "ring":
            # insert at same level as the base (last visible layer)
            visible = [l for l in self._project.layers if l.effective_visible]
            base = visible[-1] if visible else None
            if base:
                base_parent = base._parent or self._project.root
                try:
                    idx = base_parent.children.index(base)
                except ValueError:
                    idx = len(base_parent.children)
                ls._parent = base_parent
                base_parent.children.insert(idx, ls)
            else:
                ls._parent = self._project.root
                self._project.root.children.append(ls)
        else:
            ls._parent = self._project.root
            self._project.root.children.append(ls)
        self._project._rebuild_flat_list()

        self._project.recompute_extrusions()
        self._layer_panel.refresh()
        self._properties_panel.refresh_dimensions()
        self._viewport.fit_to_scene()
        self._layer_panel.select_layer_by_id(svg_layer.id)
        self._flush_undo()

    @Slot(str, str, float)
    def _on_text_requested(self, text: str, font_name: str, font_size: float) -> None:
        from ..core.text import text_to_vertices
        from ..core.svg_parser import SvgLayer
        from ..core.triangulator import triangulate_layer
        from PySide6.QtWidgets import QColorDialog, QMessageBox
        from PySide6.QtGui import QColor

        try:
            shapes = text_to_vertices(text, font_name=font_name, font_size=font_size,
                                       dpi=self._project.quality.text_dpi,
                                       text_tolerance=self._project.quality.text_tolerance)
        except Exception as e:
            QMessageBox.critical(self, "Text Error", f"Failed to generate text:\n{e}")
            return

        if not shapes:
            QMessageBox.information(self, "Text", "No text geometry generated.")
            return

        color = QColorDialog.getColor(QColor(128, 128, 128), self, "Text Color")
        if not color.isValid():
            return

        self._push_undo("Add Text")
        rgb = (color.red(), color.green(), color.blue())

        # create a group for the text
        text_group = self._project.create_group(f"Text: {text[:20]}")

        for i, (outer, holes) in enumerate(shapes):
            mesh = triangulate_layer(outer, tolerance=self._project.quality.tolerance,
                                     hole_verts=holes if holes else None)
            svg_layer = SvgLayer(
                id=f"text_{text[:10]}_{i}_{id(outer)}",
                name=f"{text[:15]}_{i}" if len(shapes) > 1 else text[:20],
                vertices=outer,
                color=rgb,
                hole_verts=holes,
            )
            ls = LayerState(svg_layer=svg_layer, triangulated_mesh=mesh, color=rgb)
            ls._parent = text_group
            text_group.children.append(ls)

        self._project._rebuild_flat_list()
        self._project.recompute_extrusions()
        self._layer_panel.refresh()
        self._properties_panel.refresh_dimensions()
        self._viewport.fit_to_scene()
        self._statusbar.showMessage(f"Added text: \"{text}\" ({len(shapes)} characters)", 4000)
        self._flush_undo()
