"""Photoshop-style welcome screen shown on app launch."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize, QUrl
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen, QPixmap, QDesktopServices


class WelcomeScreen(QWidget):
    """Dark welcome screen with logo, create/open buttons, and recent files."""

    create_new = Signal()
    open_project = Signal()
    open_recent = Signal(str)  # file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)
        self._recent_files: list[Path] = []
        self._setup_ui()
        self._load_recent_files()

    # ------------------------------------------------------------------
    # Banner
    # ------------------------------------------------------------------

    def _resolve_banner(self) -> Path | None:
        """Find the banner image."""
        # source tree — relative to this file (4 levels up to project root)
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        banner = project_root / "Banner.jpeg"
        if banner.exists():
            return banner
        # bundle Resources
        app_dir = Path(sys.argv[0]).resolve().parent.parent
        bundle = app_dir / "Resources" / "Banner.jpeg"
        if bundle.exists():
            return bundle
        return None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel#titleLabel {
                color: #ffffff;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            QLabel#subtitleLabel {
                color: #888888;
                font-size: 14px;
            }
            QLabel#sectionLabel {
                color: #aaaaaa;
                font-size: 13px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#actionBtn {
                background-color: #2680eb;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 14px 28px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton#actionBtn:hover {
                background-color: #3a90f5;
            }
            QPushButton#actionBtn:pressed {
                background-color: #1a6ad4;
            }
            QPushButton#secondaryBtn {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444444;
                border-radius: 6px;
                padding: 14px 28px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #383838;
                border-color: #555555;
            }
            QPushButton#secondaryBtn:pressed {
                background-color: #252525;
            }
            QPushButton#recentBtn {
                background-color: transparent;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 10px 14px;
                font-size: 13px;
                text-align: left;
            }
            QPushButton#recentBtn:hover {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QFrame#separator {
                background-color: #333333;
            }
            QLabel#recentName {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLabel#recentPath {
                color: #777777;
                font-size: 11px;
            }
            QLabel#recentDate {
                color: #666666;
                font-size: 11px;
            }
            QPushButton#donateBtn {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton#donateBtn:hover {
                color: #2680eb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Banner image ---
        banner_label = QLabel()
        banner_label.setAlignment(Qt.AlignCenter)
        banner_label.setStyleSheet("background-color: #1e1e1e;")
        banner_path = self._resolve_banner()
        if banner_path:
            pixmap = QPixmap(str(banner_path))
            if not pixmap.isNull():
                # scale to fit width, keep aspect ratio
                target_w = 900
                if pixmap.width() > target_w:
                    pixmap = pixmap.scaledToWidth(target_w, Qt.SmoothTransformation)
                banner_label.setPixmap(pixmap)
                banner_label.setFixedHeight(pixmap.height())
            else:
                banner_label.setFixedHeight(0)
        else:
            banner_label.setFixedHeight(0)
        layout.addWidget(banner_label)

        # --- Separator ---
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # --- Action buttons ---
        btn_container = QWidget()
        btn_container.setStyleSheet("background-color: #1e1e1e;")
        btn_row = QHBoxLayout(btn_container)
        btn_row.setContentsMargins(60, 30, 60, 30)
        btn_row.setSpacing(16)

        btn_new = QPushButton("Create New Project")
        btn_new.setObjectName("actionBtn")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self.create_new.emit)
        btn_row.addWidget(btn_new)

        btn_open = QPushButton("Open Project...")
        btn_open.setObjectName("secondaryBtn")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.clicked.connect(self.open_project.emit)
        btn_row.addWidget(btn_open)

        btn_row.addStretch()
        layout.addWidget(btn_container)

        # --- Separator ---
        sep2 = QFrame()
        sep2.setObjectName("separator")
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)

        # --- Recent files section ---
        recent_container = QWidget()
        recent_layout = QVBoxLayout(recent_container)
        recent_layout.setContentsMargins(60, 30, 60, 30)
        recent_layout.setSpacing(12)

        section_label = QLabel("RECENT PROJECTS")
        section_label.setObjectName("sectionLabel")
        recent_layout.addWidget(section_label)

        self._recent_list_layout = QVBoxLayout()
        self._recent_list_layout.setSpacing(2)
        self._recent_list_layout.setContentsMargins(0, 8, 0, 0)
        recent_layout.addLayout(self._recent_list_layout)
        recent_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(recent_container)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        layout.addWidget(scroll)

        # --- Donate link ---
        donate_row = QHBoxLayout()
        donate_row.setContentsMargins(60, 0, 60, 20)
        donate_row.addStretch()
        donate_btn = QPushButton("Support MakerStl — Donate via PayPal")
        donate_btn.setObjectName("donateBtn")
        donate_btn.setCursor(Qt.PointingHandCursor)
        donate_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://www.paypal.com/paypalme/DukoneDev")
        ))
        donate_row.addWidget(donate_btn)
        layout.addLayout(donate_row)

    def _paint_logo(self, label: QLabel) -> None:
        """Draw a circular logo with 'M' on the label."""
        size = min(label.width(), label.height())
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Circle background
        painter.setBrush(QColor("#2680eb"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # Letter "M"
        painter.setPen(QPen(QColor("#ffffff")))
        font = QFont("SF Pro Display", int(size * 0.45), QFont.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, size, size, Qt.AlignCenter, "M")
        painter.end()

        label.setPixmap(pixmap)

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------

    def _load_recent_files(self) -> None:
        """Scan common locations for .makerstl files."""
        search_dirs = [
            Path.home() / "Documents",
            Path.home() / "Downloads",
        ]
        found: list[tuple[Path, float]] = []
        seen: set[str] = set()

        for d in search_dirs:
            if not d.is_dir():
                continue
            for f in d.glob("**/*.makerstl"):
                key = str(f.resolve())
                if key in seen:
                    continue
                seen.add(key)
                try:
                    mtime = f.stat().st_mtime
                    found.append((f, mtime))
                except OSError:
                    continue

        # sort by modification time, newest first
        found.sort(key=lambda x: x[1], reverse=True)
        self._recent_files = [f for f, _ in found[:10]]
        self._rebuild_recent_list()

    def _rebuild_recent_list(self) -> None:
        """Repopulate the recent files list."""
        # clear existing
        while self._recent_list_layout.count():
            item = self._recent_list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._recent_files:
            empty = QLabel("No recent projects found")
            empty.setStyleSheet("color: #666666; font-size: 13px; padding: 20px;")
            empty.setAlignment(Qt.AlignCenter)
            self._recent_list_layout.addWidget(empty)
            return

        for path in self._recent_files:
            btn = self._make_recent_button(path)
            self._recent_list_layout.addWidget(btn)

    def _make_recent_button(self, path: Path) -> QPushButton:
        """Create a styled button for one recent file."""
        btn = QPushButton()
        btn.setObjectName("recentBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(56)

        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        date_str = mtime.strftime("%d %b %Y, %H:%M")

        btn.setText(f"  {path.stem}")
        btn.setToolTip(str(path))

        # we use a custom paint or just format text
        display = f"{path.stem}    {date_str}"
        btn.setText(f"  {display}")
        btn.clicked.connect(lambda checked, p=str(path): self.open_recent.emit(p))
        return btn
