"""Main application window with 3D viewport, layer panel, and properties."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QMenuBar, QToolBar,
    QStatusBar, QMessageBox, QVBoxLayout, QWidget, QSplitter,
    QColorDialog,
)
from PySide6.QtCore import Qt, Slot, QUrl
from PySide6.QtGui import QAction, QKeySequence, QColor, QDesktopServices

from ..core.svg_parser import SvgParser
from ..core.triangulator import triangulate_layers
from ..core.exporters import export_stl, export_obj, export_3mf
from ..core.undo import UndoManager
from ..core.project_io import save_project, load_project
from ..models.project import Project, LayerState, LayerGroup
from .viewport import Viewport3D
from .layer_panel import LayerPanel
from .properties import PropertiesPanel
from .shapes_panel import ShapesPanel


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

        self._setup_menus()
        self._setup_toolbar()
        self._setup_panels()
        self._setup_statusbar()

    def _setup_menus(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        import_action = QAction("&Import SVG...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._on_import_svg)
        file_menu.addAction(import_action)

        import_add_action = QAction("Import SVG (&Add)...", self)
        import_add_action.setShortcut(QKeySequence("Ctrl+Shift+I"))
        import_add_action.triggered.connect(self._on_import_svg_add)
        file_menu.addAction(import_add_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_stl_action = QAction("Export &STL...", self)
        export_stl_action.triggered.connect(self._on_export_stl)
        file_menu.addAction(export_stl_action)

        export_obj_action = QAction("Export &OBJ...", self)
        export_obj_action.triggered.connect(self._on_export_obj)
        file_menu.addAction(export_obj_action)

        export_3mf_action = QAction("Export &3MF (Color)...", self)
        export_3mf_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_3mf_action.triggered.connect(self._on_export_3mf)
        file_menu.addAction(export_3mf_action)

        export_sel_action = QAction("Export 3MF Selection...", self)
        export_sel_action.setShortcut(QKeySequence("Ctrl+Alt+E"))
        export_sel_action.triggered.connect(self._on_export_3mf_selection)
        file_menu.addAction(export_sel_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

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

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_btn = QAction("New", self)
        new_btn.setShortcut(QKeySequence.StandardKey.New)
        new_btn.triggered.connect(self._on_new_project)
        toolbar.addAction(new_btn)

        import_btn = QAction("Import SVG", self)
        import_btn.triggered.connect(self._on_import_svg)
        toolbar.addAction(import_btn)

        import_add_btn = QAction("Add SVG", self)
        import_add_btn.triggered.connect(self._on_import_svg_add)
        toolbar.addAction(import_add_btn)

        self._save_btn = QAction("Save", self)
        self._save_btn.setShortcut(QKeySequence.StandardKey.Save)
        self._save_btn.triggered.connect(self._on_save)
        toolbar.addAction(self._save_btn)

        self._save_as_btn = QAction("Save As", self)
        self._save_as_btn.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._save_as_btn.triggered.connect(self._on_save_as)
        toolbar.addAction(self._save_as_btn)

        toolbar.addSeparator()

        self._undo_action = QAction("Undo", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self._undo)
        toolbar.addAction(self._undo_action)

        self._redo_action = QAction("Redo", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.setEnabled(False)
        self._redo_action.triggered.connect(self._redo)
        toolbar.addAction(self._redo_action)

        toolbar.addSeparator()

        export_3mf_btn = QAction("Export 3MF", self)
        export_3mf_btn.triggered.connect(self._on_export_3mf)
        toolbar.addAction(export_3mf_btn)

        toolbar.addSeparator()

        # gizmo mode buttons
        self._gizmo_translate_btn = QAction("Move", self)
        self._gizmo_translate_btn.setCheckable(True)
        self._gizmo_translate_btn.setChecked(True)
        self._gizmo_translate_btn.triggered.connect(lambda: self._set_gizmo_mode(0))
        toolbar.addAction(self._gizmo_translate_btn)

        self._gizmo_rotate_btn = QAction("Rotate", self)
        self._gizmo_rotate_btn.setCheckable(True)
        self._gizmo_rotate_btn.triggered.connect(lambda: self._set_gizmo_mode(1))
        toolbar.addAction(self._gizmo_rotate_btn)

        self._gizmo_scale_btn = QAction("Scale", self)
        self._gizmo_scale_btn.setCheckable(True)
        self._gizmo_scale_btn.triggered.connect(lambda: self._set_gizmo_mode(2))
        toolbar.addAction(self._gizmo_scale_btn)

    def _setup_panels(self) -> None:
        # 3D Viewport (central widget)
        self._viewport = Viewport3D(self._project)
        self._viewport.layer_clicked.connect(self._on_viewport_click)
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
        self._layer_panel.undo_needed.connect(self._push_undo)

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

        right_dock = QDockWidget("Properties", self)
        right_dock.setWidget(right_widget)
        right_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)

        # Left dock: Shapes panel
        self._shapes_panel = ShapesPanel()
        self._shapes_panel.shape_requested.connect(self._on_shape_requested)
        self._shapes_panel.text_requested.connect(self._on_text_requested)
        shapes_dock = QDockWidget("Shapes", self)
        shapes_dock.setWidget(self._shapes_panel)
        shapes_dock.setMinimumWidth(140)
        shapes_dock.setMaximumWidth(160)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, shapes_dock)

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready — Import an SVG file to begin")

    # --- Undo / Redo ---

    def _push_undo(self) -> None:
        """Save current state to undo stack (lazy: one per batch)."""
        if self._undo_pending:
            return
        self._undo_mgr.push(self._undo_mgr.snapshot(self._project))
        self._undo_pending = True
        self._undo_action.setEnabled(self._undo_mgr.can_undo)
        self._redo_action.setEnabled(self._undo_mgr.can_redo)

    def _flush_undo(self) -> None:
        """Mark batch as complete so next change creates a new undo state."""
        self._undo_pending = False

    def _undo(self) -> None:
        # save current state to redo before restoring
        current = self._undo_mgr.snapshot(self._project)
        snap = self._undo_mgr.undo()
        if snap is None:
            return
        # push current to redo stack
        self._undo_mgr._redo_stack.append(current)
        self._undo_mgr.restore(self._project, snap)
        self._refresh_after_undo()
        self._undo_action.setEnabled(self._undo_mgr.can_undo)
        self._redo_action.setEnabled(self._undo_mgr.can_redo)

    def _redo(self) -> None:
        current = self._undo_mgr.snapshot(self._project)
        snap = self._undo_mgr.redo()
        if snap is None:
            return
        self._undo_mgr._undo_stack.append(current)
        self._undo_mgr.restore(self._project, snap)
        self._refresh_after_undo()
        self._undo_action.setEnabled(self._undo_mgr.can_undo)
        self._redo_action.setEnabled(self._undo_mgr.can_redo)

    def _refresh_after_undo(self) -> None:
        """Refresh all panels after an undo/redo operation."""
        self._project._rebuild_flat_list()
        self._project.recompute_extrusions()
        self._layer_panel.refresh()
        self._viewport.refresh()
        self._properties_panel.refresh_dimensions()
        self._viewport.fit_to_scene()
        self._statusbar.showMessage("Undone" if not self._undo_mgr.can_redo else "Redone")

    def _set_gizmo_mode(self, mode: int) -> None:
        """Switch gizmo mode and update toolbar button states."""
        from ..ui.viewport import GIZMO_TRANSLATE, GIZMO_ROTATE, GIZMO_SCALE
        self._viewport.set_gizmo_mode(mode)
        self._gizmo_translate_btn.setChecked(mode == GIZMO_TRANSLATE)
        self._gizmo_rotate_btn.setChecked(mode == GIZMO_ROTATE)
        self._gizmo_scale_btn.setChecked(mode == GIZMO_SCALE)

    # --- Slots ---

    @Slot()
    def _on_about(self) -> None:
        from .. import __version__
        QMessageBox.about(
            self,
            "About MakerStl",
            f"<h2>MakerStl</h2>"
            f"<p>Version {__version__}</p>"
            f"<p>SVG to 3D model converter<br>"
            f"with color 3MF export for Bambu Studio.</p>"
            f"<p>GitHub: <a href='https://github.com/Dukonedev/MakerStl'>"
            f"github.com/Dukonedev/MakerStl</a></p>",
        )

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
        self._push_undo()
        self._project = Project()
        self._current_project_path = None
        self._undo_mgr.clear()
        self._undo_action.setEnabled(False)
        self._redo_action.setEnabled(False)
        self.setWindowTitle("MakerStl — Untitled")
        self._viewport.set_project(self._project)
        self._layer_panel.set_project(self._project)
        self._properties_panel.set_project(self._project)
        self._refresh_after_undo()
        self._statusbar.showMessage("New empty project")

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

        self._push_undo()

        try:
            parser = SvgParser(path)
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
            meshes = triangulate_layers(layer_data, hole_data=hole_data)

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
            self.setWindowTitle(f"MakerStl — {self._project.name}")

            total_verts = sum(p.vertex_count for p in parts)
            total_faces = sum(p.face_count for p in parts)
            self._statusbar.showMessage(
                f"Loaded {len(svg_layers)} layers | "
                f"{total_verts} vertices, {total_faces} faces | "
                f"Document: {doc_w:.1f} × {doc_h:.1f} mm"
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

        self._push_undo()

        try:
            parser = SvgParser(path)
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
            meshes = triangulate_layers(layer_data, hole_data=hole_data)

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
                f"Total: {total_verts} vertices, {total_faces} faces"
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
            self._statusbar.showMessage(f"Exported STL: {path}")
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
            self._statusbar.showMessage(f"Exported OBJ: {path}")
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
            self._statusbar.showMessage(f"Exported 3MF: {path}")
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
            self._statusbar.showMessage(f"Exported selection ({len(selected_parts)} parts): {path}")
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

    def _save_to(self, path: Path) -> None:
        try:
            save_project(self._project, path)
            self._current_project_path = path
            self.setWindowTitle(f"MakerStl — {path.stem}")
            self._statusbar.showMessage(f"Saved: {path}")
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
            self._statusbar.showMessage(f"Loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{e}")

    def _load_project_file(self, path: Path) -> None:
        """Load a project from a given path (used by welcome screen recent files)."""
        try:
            project = load_project(path)
            self._apply_new_project(project, path)
            self._statusbar.showMessage(f"Loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Failed to open project:\n{e}")

    def _apply_new_project(self, project: 'Project', path: Path) -> None:
        """Replace the current project and update all panels."""
        self._project = project
        self._current_project_path = path
        self._undo_mgr.clear()
        self._undo_action.setEnabled(False)
        self._redo_action.setEnabled(False)
        self.setWindowTitle(f"MakerStl — {path.stem}")
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
        self._push_undo()
        layer = self._project.get_layer_by_id(layer_id)
        if layer:
            layer.visible = visible
            self._project.recompute_extrusions()
            self._viewport.refresh()
        self._flush_undo()

    @Slot(object, bool)
    def _on_group_visibility(self, group: LayerGroup, visible: bool) -> None:
        self._push_undo()
        group.visible = visible
        self._project.recompute_extrusions()
        self._viewport.refresh()
        self._flush_undo()

    @Slot()
    def _on_parameter_changed(self) -> None:
        self._push_undo()
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
        self._push_undo()
        rgb = (color.red(), color.green(), color.blue())
        self._project.merge_layers(layer_ids, color=rgb)
        self._project.recompute_extrusions()
        self._layer_panel.refresh()
        self._viewport.refresh()
        self._flush_undo()

    @Slot(str, list)
    def _on_subtract_layers(self, base_id: str, cutter_ids: list[str]) -> None:
        self._push_undo()
        result = self._project.subtract_layers(base_id, cutter_ids)
        if result:
            self._project.recompute_extrusions()
            self._layer_panel.refresh()
            self._viewport.refresh()
            self._statusbar.showMessage(f"Subtracted {len(cutter_ids)} layer(s) from base")
        else:
            self._statusbar.showMessage("Subtract failed — no geometry remaining")
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
            kwargs = {"rx": w / 2, "ry": h / 2}
        elif shape_key == "ring":
            outer_verts, inner_hole = func(outer_diameter=w, thickness=h)
            verts = outer_verts
            hole_verts = [inner_hole]
            ring_outer_d = w
            ring_thickness = h
        else:
            kwargs = {"radius": w / 2}

        if shape_key != "ring":
            verts = func(**kwargs)

        # ask for color
        color = QColorDialog.getColor(QColor(128, 128, 128), self, "Shape Color")
        if not color.isValid():
            return
        self._push_undo()
        rgb = (color.red(), color.green(), color.blue())

        mesh = triangulate_layer(verts, hole_verts=hole_verts if hole_verts else None)
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
            shapes = text_to_vertices(text, font_name=font_name, font_size=font_size)
        except Exception as e:
            QMessageBox.critical(self, "Text Error", f"Failed to generate text:\n{e}")
            return

        if not shapes:
            QMessageBox.information(self, "Text", "No text geometry generated.")
            return

        color = QColorDialog.getColor(QColor(128, 128, 128), self, "Text Color")
        if not color.isValid():
            return

        self._push_undo()
        rgb = (color.red(), color.green(), color.blue())

        # create a group for the text
        text_group = self._project.create_group(f"Text: {text[:20]}")

        for i, (outer, holes) in enumerate(shapes):
            mesh = triangulate_layer(outer, hole_verts=holes if holes else None)
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
        self._statusbar.showMessage(f"Added text: \"{text}\" ({len(shapes)} characters)")
        self._flush_undo()
