"""Dark Photoshop-like theme for MakerStl."""

DARK_THEME = """
/* ---- Global ---- */
QMainWindow, QDialog, QWidget {
    background-color: #303030;
    color: #cccccc;
    font-size: 12px;
}

/* ---- Menu bar ---- */
QMenuBar {
    background-color: #3c3c3c;
    color: #cccccc;
    border-bottom: 1px solid #222;
    padding: 1px;
}
QMenuBar::item:selected {
    background-color: #505050;
}
QMenu {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555;
}
QMenu::item:selected {
    background-color: #2680eb;
}
QMenu::separator {
    height: 1px;
    background: #555;
    margin: 4px 8px;
}

/* ---- Toolbar ---- */
QToolBar {
    background-color: #3c3c3c;
    border-bottom: 1px solid #222;
    spacing: 4px;
    padding: 2px;
}
QToolBar::separator {
    width: 1px;
    background: #555;
    margin: 4px 2px;
}
QToolBar QToolButton {
    background: transparent;
    color: #ccc;
    border: none;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 12px;
}
QToolBar QToolButton:hover {
    background-color: #505050;
}
QToolBar QToolButton:pressed {
    background-color: #606060;
}
QToolBar QToolButton:disabled {
    color: #666;
}

/* ---- Dock widgets ---- */
QDockWidget {
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}
QDockWidget::title {
    background-color: #3c3c3c;
    color: #aaa;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid #222;
}

/* ---- Tab widget (for dock tabs) ---- */
QTabWidget::pane {
    border: none;
    background: #303030;
}
QTabBar::tab {
    background: #3c3c3c;
    color: #aaa;
    padding: 6px 12px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 11px;
}
QTabBar::tab:selected {
    color: #fff;
    border-bottom: 2px solid #2680eb;
}
QTabBar::tab:hover {
    color: #ddd;
}

/* ---- Splitter ---- */
QSplitter::handle {
    background: #222;
    height: 2px;
}
QSplitter::handle:hover {
    background: #2680eb;
}

/* ---- Group boxes ---- */
QGroupBox {
    font-weight: bold;
    font-size: 11px;
    color: #aaa;
    border: 1px solid #444;
    border-radius: 3px;
    margin-top: 8px;
    padding: 8px 4px 4px 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    top: 2px;
    padding: 0 4px;
    background: #303030;
}

/* ---- Form layouts / labels ---- */
QLabel {
    color: #bbb;
}
QFormLayout QLabel {
    color: #999;
    font-size: 11px;
}

/* ---- Spin boxes ---- */
QDoubleSpinBox, QSpinBox {
    background-color: #3c3c3c;
    color: #ddd;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 12px;
    selection-background-color: #2680eb;
}
QDoubleSpinBox:focus, QSpinBox:focus {
    border: 1px solid #2680eb;
}
QDoubleSpinBox::up-button, QSpinBox::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button {
    background: #4a4a4a;
    border: none;
    width: 16px;
}
QDoubleSpinBox::up-button:hover, QSpinBox::up-button:hover,
QDoubleSpinBox::down-button:hover, QSpinBox::down-button:hover {
    background: #5a5a5a;
}

/* ---- Buttons ---- */
QPushButton {
    background-color: #3c3c3c;
    color: #ccc;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #4a4a4a;
    border-color: #666;
}
QPushButton:pressed {
    background-color: #555;
}
QPushButton:disabled {
    color: #666;
    background: #383838;
}
QPushButton:checkable {
    border: 1px solid #555;
}
QPushButton:checked {
    background-color: #2680eb;
    color: #fff;
    border-color: #2680eb;
}

/* ---- Tool buttons ---- */
QToolButton {
    background: transparent;
    color: #ccc;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 3px;
}
QToolButton:hover {
    background-color: #505050;
    border-color: #555;
}
QToolButton:pressed {
    background-color: #606060;
}

/* ---- Tree widget ---- */
QTreeWidget {
    background-color: #2a2a2a;
    color: #ccc;
    border: none;
    outline: none;
    font-size: 12px;
}
QTreeWidget::item {
    padding: 2px 0;
    border: none;
}
QTreeWidget::item:selected {
    background-color: #2680eb;
    color: #fff;
}
QTreeWidget::item:hover:!selected {
    background-color: #3a3a3a;
}
QTreeWidget::branch {
    background: #2a2a2a;
}
QTreeWidget::branch:hover {
    background: #3a3a3a;
}
QHeaderView::section {
    background-color: #353535;
    color: #888;
    border: none;
    border-bottom: 1px solid #222;
    padding: 3px 6px;
    font-size: 11px;
    font-weight: bold;
}

/* ---- Scroll bars ---- */
QScrollBar:vertical {
    background: #2a2a2a;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #555;
    min-height: 20px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #2a2a2a;
    height: 8px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #555;
    min-width: 20px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #777;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ---- Status bar ---- */
QStatusBar {
    background-color: #3c3c3c;
    color: #888;
    border-top: 1px solid #222;
    font-size: 11px;
}

/* ---- Input dialog ---- */
QInputDialog {
    background: #3c3c3c;
}
QInputDialog QLabel {
    color: #ccc;
}

/* ---- Color dialog ---- */
QColorDialog {
    background: #3c3c3c;
}
"""
