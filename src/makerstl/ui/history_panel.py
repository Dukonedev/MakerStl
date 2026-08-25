"""Undo/Redo history panel showing action names."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QAbstractItemView, QHBoxLayout, QToolButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor


class HistoryPanel(QWidget):
    """Compact undo/redo history list."""

    undo_requested = Signal()
    redo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._undo_names: list[str] = []
        self._redo_names: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # toolbar
        tb = QHBoxLayout()
        tb.setSpacing(4)

        self._undo_btn = QToolButton()
        self._undo_btn.setText("\u21a9")
        self._undo_btn.setToolTip("Undo")
        self._undo_btn.setFixedSize(26, 22)
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo_requested)

        self._redo_btn = QToolButton()
        self._redo_btn.setText("\u21aa")
        self._redo_btn.setToolTip("Redo")
        self._redo_btn.setFixedSize(26, 22)
        self._redo_btn.setEnabled(False)
        self._redo_btn.clicked.connect(self.redo_requested)

        title = QLabel("History")
        title.setStyleSheet("color: #999; font-size: 11px; font-weight: bold; border: none;")

        tb.addWidget(self._undo_btn)
        tb.addWidget(self._redo_btn)
        tb.addWidget(title)
        tb.addStretch()
        layout.addLayout(tb)

        # list
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._list.setStyleSheet("""
            QListWidget {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                font-size: 11px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 3px 6px;
                border: none;
            }
            QListWidget::item:alternate {
                background: #2e2e2e;
            }
        """)
        layout.addWidget(self._list)

    def update_history(self, undo_names: list[str], redo_names: list[str]) -> None:
        """Refresh the history list from UndoManager state."""
        self._undo_names = list(undo_names)
        self._redo_names = list(redo_names)
        self._undo_btn.setEnabled(len(self._undo_names) > 0)
        self._redo_btn.setEnabled(len(self._redo_names) > 0)

        self._list.clear()

        # redo items (future) — grayed out
        for name in reversed(self._redo_names):
            item = QListWidgetItem(f"  {name}")
            item.setForeground(QColor(100, 100, 100))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._list.addItem(item)

        # current marker
        marker = QListWidgetItem("  \u25cf current")
        marker.setForeground(QColor(38, 128, 235))
        marker.setFlags(marker.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        font = marker.font()
        font.setItalic(True)
        marker.setFont(font)
        self._list.addItem(marker)

        # undo items (past) — normal
        for name in self._undo_names:
            item = QListWidgetItem(f"  {name}")
            item.setForeground(QColor(200, 200, 200))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._list.addItem(item)

        # scroll to current marker
        current_row = len(self._redo_names)
        if current_row < self._list.count():
            self._list.scrollToItem(self._list.item(current_row))
