"""Shapes panel: toolbar of geometric shapes to add as new layers."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QToolButton, QGroupBox,
    QGridLayout, QInputDialog, QFormLayout, QDoubleSpinBox,
    QDialog, QLineEdit, QComboBox, QDialogButtonBox, QLabel,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush

from ..core.shapes import SHAPES


def _make_shape_icon(shape_key: str, color: QColor = QColor(180, 180, 180)) -> QIcon:
    """Generate a small preview icon for a shape."""
    pm = QPixmap(28, 28)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(color, 1.5))
    p.setBrush(QBrush(color.lighter(130)))

    m = 3  # margin
    w = 28 - 2 * m

    if shape_key == "rect":
        p.drawRoundedRect(m, m, w, w, 2, 2)
    elif shape_key == "circle":
        p.drawEllipse(m, m, w, w)
    elif shape_key == "ellipse":
        p.drawEllipse(m, m + 4, w, w - 8)
    elif shape_key == "triangle":
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        pts = QPolygon([QPoint(14, m), QPoint(28 - m, 28 - m), QPoint(m, 28 - m)])
        p.drawPolygon(pts)
    elif shape_key == "star":
        import numpy as np
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        n = 10
        angles = np.linspace(-np.pi / 2, -np.pi / 2 + 2 * np.pi, n, endpoint=False)
        radii = [11 if i % 2 == 0 else 5 for i in range(n)]
        pts = QPolygon([QPoint(int(14 + r * np.cos(a)), int(14 + r * np.sin(a)))
                        for a, r in zip(angles, radii)])
        p.drawPolygon(pts)
    elif shape_key == "pentagon":
        import numpy as np
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        angles = np.linspace(-np.pi / 2, -np.pi / 2 + 2 * np.pi, 6, endpoint=True)
        pts = QPolygon([QPoint(int(14 + 11 * np.cos(a)), int(14 + 11 * np.sin(a)))
                        for a in angles])
        p.drawPolygon(pts)
    elif shape_key == "hexagon":
        import numpy as np
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        angles = np.linspace(0, 2 * np.pi, 7, endpoint=True)
        pts = QPolygon([QPoint(int(14 + 11 * np.cos(a)), int(14 + 11 * np.sin(a)))
                        for a in angles])
        p.drawPolygon(pts)
    elif shape_key == "diamond":
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        pts = QPolygon([QPoint(14, m), QPoint(28 - m, 14), QPoint(14, 28 - m), QPoint(m, 14)])
        p.drawPolygon(pts)
    elif shape_key == "cross":
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        pts = QPolygon([
            QPoint(10, m), QPoint(18, m), QPoint(18, 10),
            QPoint(28 - m, 10), QPoint(28 - m, 18), QPoint(18, 18),
            QPoint(18, 28 - m), QPoint(10, 28 - m), QPoint(10, 18),
            QPoint(m, 18), QPoint(m, 10), QPoint(10, 10),
        ])
        p.drawPolygon(pts)
    elif shape_key == "ring":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(m, m, w, w)
        inner_m = m + 6
        inner_w = w - 12
        p.drawEllipse(inner_m, inner_m, inner_w, inner_w)
    else:
        p.drawRect(m, m, w, w)

    p.end()
    return QIcon(pm)


class ShapesPanel(QWidget):
    """Left panel with shape buttons to insert geometric shapes as new layers."""

    shape_requested = Signal(str, float, float)  # shape_key, width, height
    text_requested = Signal(str, str, float)  # text, font_name, font_size

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # shapes grid — compact 2-column layout
        grid = QGridLayout()
        grid.setSpacing(3)
        grid.setContentsMargins(0, 0, 0, 0)

        btn_style = (
            "QToolButton { border: none; border-radius: 3px; padding: 2px; text-align: center; }"
            "QToolButton:hover { background: #505050; }"
            "QToolButton:pressed { background: #606060; }"
        )

        items = list(SHAPES.items())
        cols = 2
        for i, (key, (label, _func)) in enumerate(items):
            row, col = divmod(i, cols)
            btn = QToolButton()
            btn.setIcon(_make_shape_icon(key))
            btn.setText(label)
            btn.setIconSize(QSize(24, 24))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setFixedSize(56, 52)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked=False, k=key: self._on_shape(k))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        # Text button
        text_btn_style = (
            "QToolButton { border: none; border-radius: 3px; padding: 4px; text-align: center; font-weight: bold; }"
            "QToolButton:hover { background: #505050; }"
            "QToolButton:pressed { background: #606060; }"
        )
        text_btn = QToolButton()
        text_btn.setText("T  Text")
        text_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        text_btn.setFixedHeight(32)
        text_btn.setStyleSheet(text_btn_style)
        text_btn.clicked.connect(self._on_text)
        layout.addWidget(text_btn)

        layout.addStretch()

    def _on_shape(self, key: str) -> None:
        from PySide6.QtWidgets import QInputDialog
        if key == "ring":
            d, ok = QInputDialog.getDouble(
                self, "Ring Size", "Outer diameter (mm):", 14.0, 10.0, 500.0, 1,
            )
            if ok:
                self.shape_requested.emit(key, d, 3.0)
        elif key in ("rect", "diamond"):
            w, ok = QInputDialog.getDouble(
                self, "Shape Size", "Width (mm):", 20.0, 0.5, 500.0, 1,
            )
            if not ok:
                return
            h, ok = QInputDialog.getDouble(
                self, "Shape Size", "Height (mm):", 20.0, 0.5, 500.0, 1,
            )
            if not ok:
                return
            self.shape_requested.emit(key, w, h)
        else:
            size, ok = QInputDialog.getDouble(
                self, "Shape Size", "Size (mm):", 20.0, 0.5, 500.0, 1,
            )
            if ok:
                self.shape_requested.emit(key, size, size)

    def _on_text(self) -> None:
        """Open text input dialog."""
        from ..core.text import list_available_fonts

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Text")
        dialog.setMinimumWidth(350)

        form = QFormLayout(dialog)

        text_input = QLineEdit()
        text_input.setPlaceholderText("Enter text...")
        text_input.setText("Hello")
        form.addRow("Text:", text_input)

        font_combo = QComboBox()
        fonts = list_available_fonts()
        for f in fonts:
            font_combo.addItem(f)
        # select Arial if available
        idx = fonts.index("Arial") if "Arial" in fonts else 0
        font_combo.setCurrentIndex(idx)
        form.addRow("Font:", font_combo)

        size_spin = QDoubleSpinBox()
        size_spin.setRange(5.0, 500.0)
        size_spin.setValue(50.0)
        size_spin.setSuffix(" mm")
        size_spin.setDecimals(1)
        form.addRow("Size:", size_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            text = text_input.text().strip()
            if text:
                font_name = font_combo.currentText()
                font_size = size_spin.value()
                self.text_requested.emit(text, font_name, font_size)
