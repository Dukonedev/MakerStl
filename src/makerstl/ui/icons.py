"""Programmatic icon generation for toolbar / UI actions.

All icons are drawn with QPainter on 16x16 or 20x20 Pixmaps so we
depend on zero external icon assets.
"""

from __future__ import annotations

from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygon
from PySide6.QtCore import Qt, QPoint, QRect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _px(size: int = 16) -> QPixmap:
    return QPixmap(size, size)


def _icon(pm: QPixmap) -> QIcon:
    return QIcon(pm)


def _pen(color: str = "#cccccc", width: int = 1) -> QPen:
    p = QPen(QColor(color), width)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


# ---------------------------------------------------------------------------
# Toolbar icons  (all drawn on 16x16)
# ---------------------------------------------------------------------------

def icon_new() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    p.setBrush(QColor("#4a4a4a"))
    # page with folded corner
    poly = QPolygon([QPoint(2, 1), QPoint(10, 1), QPoint(14, 5),
                     QPoint(14, 15), QPoint(2, 15)])
    p.drawPolygon(poly)
    # fold
    p.setBrush(QColor("#3c3c3c"))
    fold = QPolygon([QPoint(10, 1), QPoint(10, 5), QPoint(14, 5)])
    p.drawPolygon(fold)
    p.end()
    return _icon(pm)


def icon_import() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    # arrow down
    p.drawLine(8, 2, 8, 10)
    p.drawLine(5, 7, 8, 10)
    p.drawLine(11, 7, 8, 10)
    # tray
    p.drawRect(3, 11, 10, 4)
    p.end()
    return _icon(pm)


def icon_save() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    p.setBrush(QColor("#4a4a4a"))
    # floppy disk body
    p.drawRect(2, 1, 12, 14)
    # label area
    p.setBrush(QColor("#3c3c3c"))
    p.drawRect(4, 2, 8, 5)
    # slot
    p.setBrush(QColor("#555"))
    p.drawRect(5, 11, 6, 4)
    p.end()
    return _icon(pm)


def icon_undo() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    # curved arrow left
    p.drawArc(3, 2, 10, 10, 150 * 16, 240 * 16)
    p.drawLine(3, 5, 3, 8)
    p.drawLine(3, 5, 6, 5)
    p.end()
    return _icon(pm)


def icon_redo() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    # curved arrow right (mirror of undo)
    p.drawArc(3, 2, 10, 10, -60 * 16, 240 * 16)
    p.drawLine(13, 5, 13, 8)
    p.drawLine(13, 5, 10, 5)
    p.end()
    return _icon(pm)


def icon_export() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    # arrow up
    p.drawLine(8, 13, 8, 5)
    p.drawLine(5, 8, 8, 5)
    p.drawLine(11, 8, 8, 5)
    # tray
    p.drawRect(3, 1, 10, 4)
    p.end()
    return _icon(pm)


def icon_move() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # 4-way arrow
    p.setPen(_pen("#2680eb"))
    p.drawLine(8, 2, 8, 14)
    p.drawLine(2, 8, 14, 8)
    for cx, cy, dx, dy in [(8, 2, -2, 3), (8, 2, 2, 3),
                            (8, 14, -2, -3), (8, 14, 2, -3),
                            (2, 8, 3, -2), (2, 8, 3, 2),
                            (14, 8, -3, -2), (14, 8, -3, 2)]:
        p.drawLine(cx, cy, cx + dx, cy + dy)
    p.end()
    return _icon(pm)


def icon_rotate() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    # circular arrow
    p.drawArc(3, 3, 10, 10, 30 * 16, 280 * 16)
    # arrowhead
    p.drawLine(12, 3, 14, 1)
    p.drawLine(12, 3, 14, 5)
    p.end()
    return _icon(pm)


def icon_scale() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    p.setBrush(QColor("#4a4a4a"))
    # square with corner handles
    p.drawRect(4, 4, 8, 8)
    for cx, cy in [(4, 4), (12, 4), (4, 12), (12, 12)]:
        p.drawRect(cx - 1, cy - 1, 2, 2)
    p.end()
    return _icon(pm)


# ---------------------------------------------------------------------------
# Menu / layer-panel icons (small, used as QAction icon or delegate paint)
# ---------------------------------------------------------------------------

def icon_folder() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    p.setBrush(QColor("#d4a017"))
    p.drawRect(1, 4, 14, 10)
    p.drawRect(1, 2, 7, 3)
    p.end()
    return _icon(pm)


def icon_eye_open() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#cccccc"))
    # almond shape
    p.drawEllipse(QPoint(8, 8), 6, 4)
    # pupil
    p.setBrush(QColor("#cccccc"))
    p.drawEllipse(QPoint(8, 8), 2, 2)
    p.end()
    return _icon(pm)


def icon_eye_closed() -> QIcon:
    pm = _px()
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(_pen("#666666"))
    # closed eye (just a line)
    p.drawLine(2, 8, 14, 8)
    p.end()
    return _icon(pm)


# Convenience: fill missing icons in QAction
QActionRoles = None  # placeholder, not needed at runtime
