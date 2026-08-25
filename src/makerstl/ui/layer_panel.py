"""Layer panel: Photoshop-style tree with groups, visibility, lock, and indentation.

Features:
- Dedicated eye column for visibility toggle
- Dedicated lock column for lock toggle
- Expand/collapse chevrons for groups
- Color swatches
- Right-click context menu
- Double-click to rename
- Drag-and-drop with proper model sync
- Locked layers: no gizmo, no drag, no delete
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QLabel, QMenu, QInputDialog, QToolBar,
    QAbstractItemView, QStyledItemDelegate, QStyle, QToolButton,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import (
    QColor, QIcon, QPainter, QPixmap, QAction, QFont, QPen, QPalette,
)

from ..models.project import Project, LayerState, LayerGroup

# ------------------------------------------------------------------
# Icon helpers — lazy init (need QApplication first)
# ------------------------------------------------------------------

EYE_OPEN = "\u25C9"   # ◉
EYE_CLOSED = "\u25CB" # ○


def _make_eye_icon(opening: bool) -> QIcon:
    """Create a reliable eye icon using QPixmap painting."""
    size = 32
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx, cy = size // 2, size // 2
    if opening:
        p.setPen(QPen(QColor(180, 180, 180), 2))
        p.setBrush(QColor(180, 180, 180))
        p.drawEllipse(cx - 12, cy - 7, 24, 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(40, 40, 40))
        p.drawEllipse(cx - 5, cy - 5, 10, 10)
        p.setBrush(QColor(255, 255, 255))
        p.drawEllipse(cx - 2, cy - 3, 4, 4)
    else:
        p.setPen(QPen(QColor(100, 100, 100), 2))
        p.setBrush(QColor(100, 100, 100))
        p.drawEllipse(cx - 12, cy - 7, 24, 14)
        p.setPen(QPen(QColor(220, 50, 50), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(cx - 9, cy + 5, cx + 9, cy - 5)
    p.end()
    return QIcon(pm)


def _make_folder_icon(color: QColor) -> QIcon:
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(color.darker(130))
    p.setBrush(color)
    p.drawRoundedRect(1, 5, 14, 9, 1, 1)
    p.drawRect(1, 3, 6, 3)
    p.end()
    return QIcon(pm)


# ------------------------------------------------------------------
# Custom delegate — draws eye icon in column 0, bypassing macOS native
# tree decoration that clips icons for child items.
# ------------------------------------------------------------------

class _EyeColumnDelegate(QStyledItemDelegate):
    """Paints the eye icon centered in column 0, ignoring the item's icon.
    This avoids macOS native tree decoration clipping child item icons."""

    def __init__(self, panel: "LayerPanel", parent=None):
        super().__init__(parent)
        self._panel = panel

    def paint(self, painter, option, index):
        # Draw background (selection highlight, hover, etc.)
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        # Draw everything EXCEPT the icon via the base class on a copy
        # Then paint the icon ourselves at the correct position.
        # First, draw the full item (background, text, icon)
        # but we'll overlay our own icon position.

        # Let the base class handle background, selection, text, etc.
        super().paint(painter, option, index)

        # Now get the item and paint our eye icon at the left edge
        tree = option.widget
        if not tree or not hasattr(tree, "itemFromIndex"):
            return
        item = tree.itemFromIndex(index)
        if not item or not hasattr(item, "node"):
            return

        node = item.node
        if isinstance(node, LayerGroup):
            visible = node.visible
        elif isinstance(node, LayerState):
            visible = node.effective_visible
        else:
            return

        # Draw eye icon at a fixed position in column 0
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Position: centered vertically, 8px from left edge
        rect = option.rect
        cx = rect.left() + 12
        cy = rect.center().y()
        s = 7  # half-size of eye

        if visible:
            # Open eye
            painter.setPen(QPen(QColor(180, 180, 180), 1.5))
            painter.setBrush(QColor(180, 180, 180))
            painter.drawEllipse(cx - s, cy - s // 2, s * 2, s)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(40, 40, 40))
            painter.drawEllipse(cx - 3, cy - 3, 6, 6)
            painter.setBrush(QColor(255, 255, 255))
            painter.drawEllipse(cx - 1, cy - 2, 3, 3)
        else:
            # Closed eye with red slash
            painter.setPen(QPen(QColor(100, 100, 100), 1.5))
            painter.setBrush(QColor(100, 100, 100))
            painter.drawEllipse(cx - s, cy - s // 2, s * 2, s)
            painter.setPen(QPen(QColor(220, 50, 50), 2.5))
            painter.drawLine(cx - 5, cy + 3, cx + 5, cy - 3)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Toggle visibility on click in column 0."""
        if event.type() == event.Type.MouseButtonRelease:
            tree = option.widget
            if tree and hasattr(tree, "itemFromIndex"):
                item = tree.itemFromIndex(index)
                if item and hasattr(item, "node"):
                    node = item.node
                    if isinstance(node, LayerGroup):
                        node.visible = not node.visible
                        self._panel.group_visibility_changed.emit(node, node.visible)
                    elif isinstance(node, LayerState):
                        node.visible = not node.visible
                        self._panel.layer_visibility_changed.emit(node.svg_layer.id, node.visible)
                    self._panel.refresh()
                    return True
        if event.type() == event.Type.MouseButtonPress:
            return True  # consume press to prevent selection
        return super().editorEvent(event, model, option, index)


# ------------------------------------------------------------------
# Lock column delegate — paints padlock icon, toggles lock on click
# ------------------------------------------------------------------

class _LockColumnDelegate(QStyledItemDelegate):
    """Paints a padlock icon in column 1, toggles lock on click."""

    def __init__(self, panel: "LayerPanel", parent=None):
        super().__init__(parent)
        self._panel = panel

    def paint(self, painter, option, index):
        painter.save()

        # draw background manually (selection highlight, hover, etc.)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(38, 128, 235))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(58, 58, 58))

        tree = option.widget
        if not tree or not hasattr(tree, "itemFromIndex"):
            painter.restore()
            return
        item = tree.itemFromIndex(index)
        if not item or not hasattr(item, "node"):
            painter.restore()
            return

        node = item.node
        if isinstance(node, LayerGroup):
            locked = node.locked
        elif isinstance(node, LayerState):
            locked = node.locked
        else:
            painter.restore()
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        cx = rect.left() + rect.width() // 2
        cy = rect.center().y()

        if locked:
            painter.setPen(QPen(QColor(220, 180, 50), 2))
            painter.setBrush(QColor(220, 180, 50))
            painter.drawArc(cx - 4, cy - 9, 8, 8, 0, 180 * 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(220, 180, 50))
            painter.drawRoundedRect(cx - 5, cy - 2, 10, 8, 1, 1)
            painter.setBrush(QColor(60, 50, 20))
            painter.drawEllipse(cx - 1, cy + 1, 3, 3)
        else:
            painter.setPen(QPen(QColor(70, 70, 70), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(cx - 4, cy - 9, 8, 8, 0, 180 * 16)
            painter.drawRect(cx - 5, cy - 2, 10, 8)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == event.Type.MouseButtonRelease:
            tree = option.widget
            if tree and hasattr(tree, "itemFromIndex"):
                item = tree.itemFromIndex(index)
                if item and hasattr(item, "node"):
                    node = item.node
                    if isinstance(node, LayerGroup):
                        node.locked = not node.locked
                    elif isinstance(node, LayerState):
                        node.locked = not node.locked
                    self._panel.refresh()
                    return True
        if event.type() == event.Type.MouseButtonPress:
            return True
        return super().editorEvent(event, model, option, index)


# ------------------------------------------------------------------
# Custom tree item
# ------------------------------------------------------------------

ROLE_NODE_TYPE = Qt.ItemDataRole.UserRole
ROLE_NODE_ID = Qt.ItemDataRole.UserRole + 1


class LayerTreeItem(QTreeWidgetItem):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self._is_group = isinstance(node, LayerGroup)

        if self._is_group:
            self.setData(0, ROLE_NODE_TYPE, "group")
            self.setData(0, ROLE_NODE_ID, id(node))
        else:
            self.setData(0, ROLE_NODE_TYPE, "layer")
            self.setData(0, ROLE_NODE_ID, node.svg_layer.id)

    def __lt__(self, other):
        return False


# ------------------------------------------------------------------
# Custom tree with drop-based model sync
# ------------------------------------------------------------------

class _LayerTree(QTreeWidget):
    """QTreeWidget subclass that syncs the Project model on drag-and-drop."""

    model_changed = Signal()

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project

    def dropEvent(self, event):
        dropped_item = self.currentItem()
        if not dropped_item or not hasattr(dropped_item, "node"):
            super().dropEvent(event)
            return

        dropped_node = dropped_item.node

        # refuse to move locked items
        if isinstance(dropped_node, LayerGroup) and dropped_node.locked:
            event.ignore()
            return
        if isinstance(dropped_node, LayerState) and dropped_node.locked:
            event.ignore()
            return
        target_item = self.itemAt(event.position().toPoint())
        if target_item is None or not hasattr(target_item, "node"):
            # dropped on empty space -> reparent to root
            target_node = self._project.root
            insert_idx = -1
        elif isinstance(target_item.node, LayerGroup):
            target_node = target_item.node
            insert_idx = len(target_node.children)
        else:
            # dropped on a layer -> insert after it in its parent
            target_node = target_item.node._parent or self._project.root
            try:
                insert_idx = target_node.children.index(target_item.node) + 1
            except ValueError:
                insert_idx = -1

        # don't drop into self (prevent cycles)
        if isinstance(dropped_node, LayerGroup):
            for desc in dropped_node.all_nodes():
                if desc is target_node:
                    super().dropEvent(event)
                    return

        self._project.move_node(dropped_node, target_node, insert_idx)
        # rebuild tree from model (replaces Qt's default move)
        self.model_changed.emit()


# ------------------------------------------------------------------
# Main panel
# ------------------------------------------------------------------

class LayerPanel(QWidget):
    """Photoshop-style layer tree panel."""

    layers_selected = Signal(list)  # list[str] — layer IDs (single, multi, or group contents)
    layer_visibility_changed = Signal(str, bool)
    group_visibility_changed = Signal(object, bool)
    request_refresh = Signal()
    merge_requested = Signal(list)  # list[str] — layer IDs to merge
    subtract_requested = Signal(str, list)  # base_id, list[str] — cutter layer IDs
    undo_needed = Signal()  # emit before any state-changing action

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self._icon_open = _make_eye_icon(True)
        self._icon_closed = _make_eye_icon(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- tree ---
        # 4 columns: Eye(0) | Lock(1) | Name(2) | Color(3)
        self._tree = _LayerTree(self._project)
        self._tree.setHeaderLabels(["", "", "Name", ""])
        self._tree.setColumnCount(4)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(20)
        self._tree.setIconSize(QSize(20, 20))
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.setColumnWidth(0, 40)   # eye column
        self._tree.setColumnWidth(1, 36)   # lock column
        self._tree.setColumnWidth(2, 160)  # name column
        self._tree.setColumnWidth(3, 24)   # color column
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.model_changed.connect(self._on_drop_sync)
        self._tree.setItemDelegateForColumn(0, _EyeColumnDelegate(self, self._tree))
        self._tree.setItemDelegateForColumn(1, _LockColumnDelegate(self, self._tree))
        layout.addWidget(self._tree)

        # --- bottom toolbar (Photoshop-style) ---
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet("background: #353535; border-top: 1px solid #222;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(4, 2, 4, 2)
        bottom_layout.setSpacing(2)

        btn_style = (
            "QToolButton { border: none; border-radius: 3px; padding: 4px; }"
            "QToolButton:hover { background: #505050; }"
            "QToolButton:pressed { background: #606060; }"
        )

        def _make_btn(icon_text: str, tooltip: str, slot) -> QToolButton:
            b = QToolButton()
            b.setText(icon_text)
            b.setToolTip(tooltip)
            b.setFixedSize(28, 24)
            b.setStyleSheet(btn_style)
            b.clicked.connect(slot)
            return b

        bottom_layout.addWidget(_make_btn("\u2795", "New Group", self._on_new_group))
        bottom_layout.addWidget(_make_btn("\u2796", "Ungroup", self._on_ungroup))
        bottom_layout.addWidget(_make_btn("\u2b06", "Move Up", lambda: self._on_move(-1)))
        bottom_layout.addWidget(_make_btn("\u2b07", "Move Down", lambda: self._on_move(1)))
        bottom_layout.addWidget(_make_btn("\u2702", "Delete", self._on_delete))
        bottom_layout.addWidget(_make_btn("\u2398", "Duplicate", self._on_duplicate))
        bottom_layout.addWidget(_make_btn("\u2299", "Subtract", self._on_subtract))
        bottom_layout.addWidget(_make_btn("\U0001F512", "Lock", self._on_toggle_lock_selected))
        bottom_layout.addStretch()
        bottom_layout.addWidget(_make_btn("\u2b1a", "Merge", self._on_merge))
        layout.addWidget(bottom_bar)

    def set_project(self, project: Project) -> None:
        self._project = project
        self._tree._project = project
        self.refresh()

    # ------------------------------------------------------------------
    # Rebuild
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._tree.blockSignals(True)
        self._tree.clear()

        for node in self._project.root.children:
            self._add_node(node, None)

        self._tree.blockSignals(False)

    def _on_drop_sync(self) -> None:
        """Called when a drag-and-drop operation completes."""
        self.refresh()
        self.request_refresh.emit()

    def select_layer_by_id(self, layer_id: str) -> None:
        """Select and scroll to a layer by its SVG ID."""
        self._tree.blockSignals(True)
        self._tree.clearSelection()
        stack = list(self._tree.topLevelItems())
        while stack:
            item = stack.pop()
            if hasattr(item, "node") and isinstance(item.node, LayerState):
                if item.node.svg_layer.id == layer_id:
                    self._tree.setCurrentItem(item)
                    self._tree.scrollToItem(item)
                    self._tree.blockSignals(False)
                    self.layers_selected.emit([layer_id])
                    return
            for i in range(item.childCount()):
                stack.append(item.child(i))
        self._tree.blockSignals(False)

    def _add_node(self, node, parent_item):
        item = LayerTreeItem(node)

        is_locked = node.locked if isinstance(node, LayerGroup) else node.locked

        if isinstance(node, LayerGroup):
            # column 2: name
            item.setText(2, node.name)
            # column 3: color swatch
            r, g, b = node.color
            item.setBackground(3, QColor(r, g, b))
            if not node.visible or is_locked:
                for col in (2, 3):
                    item.setForeground(col, QColor(120, 120, 120))
            else:
                for col in (2, 3):
                    item.setForeground(col, QColor(230, 230, 230))
        else:
            # column 2: name
            item.setText(2, node.svg_layer.name)
            # column 3: color swatch
            r, g, b = node.color
            item.setBackground(3, QColor(r, g, b))
            if not node.effective_visible or is_locked:
                for col in (2, 3):
                    item.setForeground(col, QColor(120, 120, 120))
            else:
                for col in (2, 3):
                    item.setForeground(col, QColor(230, 230, 230))

        if parent_item:
            parent_item.addChild(item)
        else:
            self._tree.addTopLevelItem(item)

        # expand groups
        if isinstance(node, LayerGroup):
            item.setExpanded(node.expanded)
            for child in node.children:
                self._add_node(child, item)

    # ------------------------------------------------------------------
    # Click handling — eye column toggles, name column selects
    # ------------------------------------------------------------------

    def _collect_layer_ids(self, node) -> list[str]:
        """Recursively collect all layer IDs from a node or group."""
        ids = []
        if isinstance(node, LayerState):
            ids.append(node.svg_layer.id)
        elif isinstance(node, LayerGroup):
            for child in node.children:
                ids.extend(self._collect_layer_ids(child))
        return ids

    def get_selected_layer_ids(self) -> list[str]:
        """Return all layer IDs from currently selected items."""
        ids = []
        for item in self._tree.selectedItems():
            if hasattr(item, "node"):
                ids.extend(self._collect_layer_ids(item.node))
        return ids

    def _emit_selection(self) -> None:
        """Collect IDs from all selected items and emit."""
        ids = []
        for item in self._tree.selectedItems():
            if hasattr(item, "node"):
                ids.extend(self._collect_layer_ids(item.node))
        self.layers_selected.emit(ids)

    def _on_item_clicked(self, item: LayerTreeItem, column: int) -> None:
        if column in (0, 1):
            return  # handled by delegates
        self._emit_selection()

    def _on_selection_changed(self) -> None:
        self._emit_selection()

    def _on_item_double_clicked(self, item: LayerTreeItem, column: int) -> None:
        if column in (0, 1):
            return  # don't rename on eye/lock click
        node = item.node
        name = node.name if isinstance(node, LayerGroup) else node.svg_layer.name
        new_name, ok = QInputDialog.getText(self, "Rename", "Name:", text=name)
        if ok and new_name.strip():
            self.undo_needed.emit()
            if isinstance(node, LayerGroup):
                self._project.rename_group(node, new_name.strip())
            else:
                node.svg_layer.name = new_name.strip()
            self.refresh()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        menu = QMenu(self)

        act_new_group = QAction("New Group", self)
        act_new_group.triggered.connect(self._on_new_group)
        menu.addAction(act_new_group)

        if item and isinstance(item.node, LayerState):
            act_group = QAction("Group Selected", self)
            act_group.triggered.connect(self._on_group_selected)
            menu.addAction(act_group)

            act_merge_ctx = QAction("Merge Selected", self)
            act_merge_ctx.triggered.connect(self._on_merge)
            menu.addAction(act_merge_ctx)

        if item and isinstance(item.node, LayerGroup):
            act_ungroup = QAction("Ungroup", self)
            act_ungroup.triggered.connect(self._on_ungroup)
            menu.addAction(act_ungroup)

        menu.addSeparator()

        # Lock / Unlock
        if item and hasattr(item, "node"):
            node = item.node
            is_locked = node.locked
            act_lock = QAction("Unlock" if is_locked else "Lock", self)
            act_lock.triggered.connect(lambda: self._on_toggle_lock(node))
            menu.addAction(act_lock)

        act_rename = QAction("Rename", self)
        act_rename.triggered.connect(
            lambda: self._on_item_double_clicked(item, 2) if item else None
        )
        menu.addAction(act_rename)

        if item:
            act_delete = QAction("Delete", self)
            act_delete.triggered.connect(self._on_delete)
            menu.addAction(act_delete)

        menu.addSeparator()

        act_up = QAction("Move Up", self)
        act_up.triggered.connect(lambda: self._on_move(-1))
        menu.addAction(act_up)

        act_down = QAction("Move Down", self)
        act_down.triggered.connect(lambda: self._on_move(1))
        menu.addAction(act_down)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _is_any_locked(self, items=None) -> bool:
        """Return True if any selected item is locked (or has a locked ancestor)."""
        if items is None:
            items = self._tree.selectedItems()
        for item in items:
            if not hasattr(item, "node"):
                continue
            node = item.node
            if isinstance(node, LayerGroup) and node.locked:
                return True
            if isinstance(node, LayerState):
                n = node
                while n is not None:
                    if isinstance(n, LayerGroup) and n.locked:
                        return True
                    if isinstance(n, LayerState) and n.locked:
                        return True
                    n = getattr(n, "_parent", None)
        return False

    def _on_new_group(self) -> None:
        self.undo_needed.emit()
        self._project.create_group("Group")
        self.refresh()

    def _on_group_selected(self) -> None:
        item = self._tree.currentItem()
        if not item or not isinstance(item.node, LayerState):
            return
        self.undo_needed.emit()
        self._project.group_selected([item.node.svg_layer.id])
        self.refresh()

    def _on_toggle_lock(self, node) -> None:
        self.undo_needed.emit()
        node.locked = not node.locked
        self.refresh()

    def _on_toggle_lock_selected(self) -> None:
        """Toggle lock on all selected items."""
        items = self._tree.selectedItems()
        if not items:
            return
        self.undo_needed.emit()
        for item in items:
            if hasattr(item, "node"):
                node = item.node
                node.locked = not node.locked
        self.refresh()

    def _on_ungroup(self) -> None:
        item = self._tree.currentItem()
        if not item or not isinstance(item.node, LayerGroup):
            return
        self.undo_needed.emit()
        self._project.ungroup(item.node)
        self.refresh()

    def _on_delete(self) -> None:
        item = self._tree.currentItem()
        if not item:
            return
        if self._is_any_locked():
            return
        self.undo_needed.emit()
        if isinstance(item.node, LayerState):
            self._project.delete_layer(item.node.svg_layer.id)
        elif isinstance(item.node, LayerGroup):
            parent = item.node._parent or self._project.root
            parent.children.remove(item.node)
            self._project._rebuild_flat_list()
        self.refresh()
        self.request_refresh.emit()

    def _on_duplicate(self) -> None:
        item = self._tree.currentItem()
        if not item:
            return
        if self._is_any_locked():
            return
        if isinstance(item.node, LayerState):
            self.undo_needed.emit()
            new_layer = self._project.duplicate_layer(item.node.svg_layer.id)
            if new_layer:
                self.refresh()
                self.request_refresh.emit()
                self.select_layer_by_id(new_layer.svg_layer.id)

    def _on_subtract(self) -> None:
        """Subtract selected layers from the first selected (base)."""
        items = self._tree.selectedItems()
        if len(items) < 2:
            return
        if self._is_any_locked(items):
            return
        # first selected is the base
        base_item = items[0]
        if not isinstance(base_item.node, LayerState):
            return
        cutter_ids = []
        for item in items[1:]:
            if isinstance(item.node, LayerState):
                cutter_ids.append(item.node.svg_layer.id)
        if not cutter_ids:
            return
        self.undo_needed.emit()
        self.subtract_requested.emit(base_item.node.svg_layer.id, cutter_ids)

    def _on_move(self, direction: int) -> None:
        item = self._tree.currentItem()
        if not item:
            return
        if self._is_any_locked():
            return
        self.undo_needed.emit()
        node = item.node
        parent = getattr(node, "_parent", None) or self._project.root
        idx = parent.children.index(node) if node in parent.children else -1
        if idx < 0:
            return
        new_idx = idx + direction
        if 0 <= new_idx < len(parent.children):
            parent.children[idx], parent.children[new_idx] = (
                parent.children[new_idx], parent.children[idx],
            )
            self._project._rebuild_flat_list()
            self.refresh()

    def _on_merge(self) -> None:
        ids = []
        for item in self._tree.selectedItems():
            if hasattr(item, "node"):
                ids.extend(self._collect_layer_ids(item.node))
        if len(ids) >= 2:
            if self._is_any_locked():
                return
            self.merge_requested.emit(ids)
