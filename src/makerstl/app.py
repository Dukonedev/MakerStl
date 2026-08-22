"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QDesktopServices
from PySide6.QtCore import Qt, QTimer, QUrl

from .ui.main_window import MainWindow
from .ui.welcome import WelcomeScreen
from .ui.theme import DARK_THEME


def _resolve_icon() -> Path | None:
    """Find the app icon, checking bundle Resources first, then source tree."""
    app_dir = Path(sys.argv[0]).resolve().parent.parent
    bundle_icon = app_dir / "Resources" / "app-icon.icns"
    if bundle_icon.exists():
        return bundle_icon
    src_icon = Path(__file__).parent.parent.parent / "resources" / "icon.png"
    if src_icon.exists():
        return src_icon
    return None


def _resolve_splash_image() -> Path | None:
    """Find the splash screen image."""
    app_dir = Path(sys.argv[0]).resolve().parent.parent
    bundle_splash = app_dir / "Resources" / "splash_screen.jpeg"
    if bundle_splash.exists():
        return bundle_splash
    src_splash = Path(__file__).parent.parent.parent / "splash_screen.jpeg"
    if src_splash.exists():
        return src_splash
    return None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MakerStl")
    app.setOrganizationName("MakerStl")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_THEME)

    icon = _resolve_icon()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))

    # --- Splash screen ---
    splash = None
    splash_path = _resolve_splash_image()
    if splash_path:
        pixmap = QPixmap(str(splash_path))
        if not pixmap.isNull():
            target_w = 800
            if pixmap.width() > target_w:
                pixmap = pixmap.scaledToWidth(target_w, Qt.SmoothTransformation)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            bar_h = 50
            bar_y = pixmap.height() - bar_h
            painter.fillRect(0, bar_y, pixmap.width(), bar_h, QColor(0, 0, 0, 180))
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("SF Pro Display", 16)
            painter.setFont(font)
            painter.drawText(0, bar_y, pixmap.width(), bar_h,
                             Qt.AlignCenter, "Loading MakerStl...")
            painter.end()

            splash = QSplashScreen(pixmap)
            splash.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            splash.show()
            app.processEvents()

    # --- Welcome screen (shown after splash) ---
    welcome = WelcomeScreen()
    window: MainWindow | None = None

    def _show_welcome():
        if splash:
            splash.finish(welcome)
        welcome.show()
        welcome.raise_()
        welcome.activateWindow()

    def _open_main(activate_fn=None):
        nonlocal window
        if window is None:
            window = MainWindow()
            window.setWindowIcon(QIcon(str(icon)) if icon else QIcon())
        welcome.hide()
        window.show()
        window.raise_()
        window.activateWindow()
        if activate_fn:
            activate_fn(window)

    def _on_create_new():
        _open_main()

    def _on_open_project():
        def _trigger(w: MainWindow):
            w._on_open_project()
        _open_main(activate_fn=_trigger)

    def _on_open_recent(path: str):
        def _trigger(w: MainWindow):
            w._load_project_file(Path(path))
        _open_main(activate_fn=_trigger)

    welcome.create_new.connect(_on_create_new)
    welcome.open_project.connect(_on_open_project)
    welcome.open_recent.connect(_on_open_recent)

    # show splash for 1200ms, then transition to welcome
    QTimer.singleShot(1200, _show_welcome)

    # --- Check for updates (background, non-blocking) ---
    _update_thread = None  # prevent GC

    def _on_update_check():
        nonlocal _update_thread
        try:
            from .core.updater import check_for_update
            from PySide6.QtCore import QThread, Signal as _Signal

            class _UpdateThread(QThread):
                _result_ready = _Signal(object)

                def run(self):
                    try:
                        result = check_for_update()
                        self._result_ready.emit(result)
                    except Exception:
                        pass

            def _on_done(result):
                if result.has_update:
                    msg = QMessageBox()
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
                    msg.addButton("Later", QMessageBox.RejectRole)
                    msg.exec()
                    if msg.clickedButton() == dl_btn:
                        QDesktopServices.openUrl(QUrl(result.download_url))

            _update_thread = _UpdateThread()
            _update_thread._result_ready.connect(_on_done)
            _update_thread.finished.connect(_update_thread.deleteLater)
            _update_thread.start()
        except Exception:
            pass

    QTimer.singleShot(2000, _on_update_check)

    return app.exec()
