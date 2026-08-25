"""Main application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QDesktopServices
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QSurfaceFormat

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
    from .core.debug_log import log
    log("main() starting")

    gl_fmt = QSurfaceFormat()
    gl_fmt.setVersion(3, 3)
    gl_fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    gl_fmt.setDepthBufferSize(24)
    gl_fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(gl_fmt)

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

    def _check_crash_recovery():
        """Check for orphaned auto-saves and offer recovery."""
        from .core.auto_save import find_orphaned_auto_saves
        orphans = find_orphaned_auto_saves()
        if not orphans:
            return
        # show recovery dialog
        from PySide6.QtWidgets import QMessageBox as _MB
        msg = _MB()
        msg.setWindowTitle("Crash Recovery")
        msg.setIcon(_MB.Warning)
        msg.setText(f"Found {len(orphans)} unsaved project(s) from a previous session.")
        details = "\n".join(
            f"  {o['original_path'].name}  ({o['mtime']:.0f})"
            for o in orphans[:5]
        )
        msg.setInformativeText(
            "MakerStl closed without saving last time.\n"
            f"Auto-saves found:\n{details}\n\n"
            "Recover now?"
        )
        rec_btn = msg.addButton("Recover", _MB.AcceptRole)
        msg.addButton("Skip", _MB.RejectRole)
        msg.exec()
        if msg.clickedButton() == rec_btn and orphans:
            _recover_auto_save(orphans[0]["auto_path"], orphans[0]["original_path"])

    def _recover_auto_save(auto_path, original_path):
        """Load an auto-save and optionally save it to the original location."""
        nonlocal window
        _open_main()
        if window is None:
            return
        try:
            from .core.project_io import load_project
            project = load_project(auto_path)
            window._apply_new_project(project, original_path)
            window._mark_dirty()  # mark as unsaved so user saves explicitly
            window._statusbar.showMessage(
                f"Recovered: {original_path.name} (auto-save)", 8000
            )
        except Exception:
            pass

    def _show_welcome():
        if splash:
            splash.finish(welcome)
        welcome.show()
        welcome.raise_()
        welcome.activateWindow()
        QTimer.singleShot(500, _check_crash_recovery)

    def _open_main(activate_fn=None):
        from .core.debug_log import log_exception
        nonlocal window
        if window is None:
            try:
                window = MainWindow()
                window.setWindowIcon(QIcon(str(icon)) if icon else QIcon())
            except Exception as e:
                log_exception("MainWindow CRASHED", e)
                return
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

    def _on_import_svg(svg_path: str):
        def _trigger(w: MainWindow):
            w._import_svg_path(Path(svg_path))
        _open_main(activate_fn=_trigger)

    welcome.create_new.connect(_on_create_new)
    welcome.open_project.connect(_on_open_project)
    welcome.open_recent.connect(_on_open_recent)
    welcome.import_svg.connect(_on_import_svg)

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
