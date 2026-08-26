"""Keychain generator panel: parametric controls for keychain creation.

Provides a full parameter interface for the keychain generator,
producing LayerState objects via the standard pipeline.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox,
    QPushButton, QLabel, QGroupBox, QComboBox, QSpinBox,
    QLineEdit, QColorDialog, QCheckBox, QSizePolicy, QScrollArea,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor

from ..core.keychain import KeychainConfig, generate_keychain
from ..core.extruder import extrude_layer
from ..core.quality import QualitySettings
from ..core.text import list_available_fonts
from ..models.project import LayerState


class KeychainPanel(QWidget):
    """Panel for parametric keychain generation."""

    generate_requested = Signal(object)  # emits list[LayerState]
    preview_requested = Signal(object)  # emits list[ExtrudedPart] for live preview
    preview_cleared = Signal()          # emitted when preview should be removed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(400)
        self._preview_timer.timeout.connect(self._do_preview)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ---- Text section ----
        text_group = QGroupBox("Testo")
        text_group.setCheckable(True)
        text_group.setChecked(True)
        text_form = QFormLayout()

        self._text_edit = QLineEdit("HELLO")
        text_form.addRow("Text:", self._text_edit)

        self._font_combo = QComboBox()
        fonts = list_available_fonts()
        self._font_combo.addItems(fonts[:20] if fonts else ["Arial"])
        text_form.addRow("Font:", self._font_combo)

        self._font_size_spin = QDoubleSpinBox()
        self._font_size_spin.setRange(2.0, 50.0)
        self._font_size_spin.setValue(10.0)
        self._font_size_spin.setSuffix(" mm")
        self._font_size_spin.setDecimals(1)
        text_form.addRow("Font Size:", self._font_size_spin)

        self._font_scale_x_spin = QDoubleSpinBox()
        self._font_scale_x_spin.setRange(0.3, 3.0)
        self._font_scale_x_spin.setValue(1.0)
        self._font_scale_x_spin.setDecimals(2)
        self._font_scale_x_spin.setSingleStep(0.1)
        text_form.addRow("Scale X:", self._font_scale_x_spin)

        self._letter_spacing_spin = QDoubleSpinBox()
        self._letter_spacing_spin.setRange(-5.0, 20.0)
        self._letter_spacing_spin.setValue(0.0)
        self._letter_spacing_spin.setSuffix(" mm")
        self._letter_spacing_spin.setDecimals(1)
        text_form.addRow("Letter Spacing:", self._letter_spacing_spin)

        self._text_depth_spin = QDoubleSpinBox()
        self._text_depth_spin.setRange(0.1, 10.0)
        self._text_depth_spin.setValue(0.8)
        self._text_depth_spin.setSuffix(" mm")
        self._text_depth_spin.setDecimals(1)
        text_form.addRow("Text Depth:", self._text_depth_spin)

        self._text_color_btn = QPushButton()
        self._text_color_btn.setFixedSize(60, 24)
        self._text_color = QColor(0, 0, 0)
        self._update_color_btn(self._text_color_btn, self._text_color)
        self._text_color_btn.clicked.connect(self._pick_text_color)
        text_form.addRow("Text Color:", self._text_color_btn)

        text_group.setLayout(text_form)
        layout.addWidget(text_group)

        # ---- Base section ----
        base_group = QGroupBox("Base")
        base_group.setCheckable(True)
        base_group.setChecked(True)
        base_form = QFormLayout()

        self._base_shape_combo = QComboBox()
        self._base_shape_combo.addItems(["Outline Contour", "Capsule"])
        base_form.addRow("Shape:", self._base_shape_combo)

        self._base_thickness_spin = QDoubleSpinBox()
        self._base_thickness_spin.setRange(0.5, 20.0)
        self._base_thickness_spin.setValue(2.0)
        self._base_thickness_spin.setSuffix(" mm")
        self._base_thickness_spin.setDecimals(1)
        base_form.addRow("Thickness:", self._base_thickness_spin)

        self._outline_size_spin = QDoubleSpinBox()
        self._outline_size_spin.setRange(0.5, 15.0)
        self._outline_size_spin.setValue(2.0)
        self._outline_size_spin.setSuffix(" mm")
        self._outline_size_spin.setDecimals(1)
        base_form.addRow("Outline Size:", self._outline_size_spin)

        self._edge_bevel_spin = QDoubleSpinBox()
        self._edge_bevel_spin.setRange(0.0, 3.0)
        self._edge_bevel_spin.setValue(0.3)
        self._edge_bevel_spin.setSuffix(" mm")
        self._edge_bevel_spin.setDecimals(2)
        self._edge_bevel_spin.setSingleStep(0.1)
        base_form.addRow("Edge Bevel:", self._edge_bevel_spin)

        self._bevel_segments_spin = QSpinBox()
        self._bevel_segments_spin.setRange(2, 12)
        self._bevel_segments_spin.setValue(3)
        base_form.addRow("Bevel Segments:", self._bevel_segments_spin)

        self._base_color_btn = QPushButton()
        self._base_color_btn.setFixedSize(60, 24)
        self._base_color = QColor(200, 200, 200)
        self._update_color_btn(self._base_color_btn, self._base_color)
        self._base_color_btn.clicked.connect(self._pick_base_color)
        base_form.addRow("Base Color:", self._base_color_btn)

        base_group.setLayout(base_form)
        layout.addWidget(base_group)

        # ---- Ring section ----
        ring_group = QGroupBox("Anello")
        ring_group.setCheckable(True)
        ring_group.setChecked(True)
        ring_form = QFormLayout()

        self._show_ring_check = QCheckBox("Mostra Anello")
        self._show_ring_check.setChecked(True)
        ring_form.addRow(self._show_ring_check)

        self._ring_diameter_spin = QDoubleSpinBox()
        self._ring_diameter_spin.setRange(3.0, 30.0)
        self._ring_diameter_spin.setValue(8.0)
        self._ring_diameter_spin.setSuffix(" mm")
        self._ring_diameter_spin.setDecimals(1)
        ring_form.addRow("Outer Diameter:", self._ring_diameter_spin)

        self._ring_thickness_spin = QDoubleSpinBox()
        self._ring_thickness_spin.setRange(0.5, 10.0)
        self._ring_thickness_spin.setValue(2.0)
        self._ring_thickness_spin.setSuffix(" mm")
        self._ring_thickness_spin.setDecimals(1)
        ring_form.addRow("Thickness:", self._ring_thickness_spin)

        self._ring_position_spin = QDoubleSpinBox()
        self._ring_position_spin.setRange(0.0, 1.0)
        self._ring_position_spin.setValue(0.0)
        self._ring_position_spin.setDecimals(2)
        self._ring_position_spin.setSingleStep(0.05)
        ring_form.addRow("Position (0-1):", self._ring_position_spin)

        self._ring_overlap_spin = QDoubleSpinBox()
        self._ring_overlap_spin.setRange(0.0, 5.0)
        self._ring_overlap_spin.setValue(1.5)
        self._ring_overlap_spin.setSuffix(" mm")
        self._ring_overlap_spin.setDecimals(1)
        ring_form.addRow("Overlap:", self._ring_overlap_spin)

        self._ring_color_btn = QPushButton()
        self._ring_color_btn.setFixedSize(60, 24)
        self._ring_color = QColor(180, 180, 180)
        self._update_color_btn(self._ring_color_btn, self._ring_color)
        self._ring_color_btn.clicked.connect(self._pick_ring_color)
        ring_form.addRow("Ring Color:", self._ring_color_btn)

        ring_group.setLayout(ring_form)
        layout.addWidget(ring_group)

        # ---- Second Outline section ----
        second_group = QGroupBox("Seconda Outline (Stepped Base)")
        second_group.setCheckable(True)
        second_group.setChecked(False)
        second_form = QFormLayout()

        self._second_offset_spin = QDoubleSpinBox()
        self._second_offset_spin.setRange(0.5, 20.0)
        self._second_offset_spin.setValue(3.0)
        self._second_offset_spin.setSuffix(" mm")
        self._second_offset_spin.setDecimals(1)
        second_form.addRow("Offset:", self._second_offset_spin)

        self._second_height_spin = QDoubleSpinBox()
        self._second_height_spin.setRange(0.2, 10.0)
        self._second_height_spin.setValue(1.0)
        self._second_height_spin.setSuffix(" mm")
        self._second_height_spin.setDecimals(1)
        second_form.addRow("Height:", self._second_height_spin)

        self._second_color_btn = QPushButton()
        self._second_color_btn.setFixedSize(60, 24)
        self._second_color = QColor(160, 160, 160)
        self._update_color_btn(self._second_color_btn, self._second_color)
        self._second_color_btn.clicked.connect(self._pick_second_color)
        second_form.addRow("Color:", self._second_color_btn)

        second_group.setLayout(second_form)
        layout.addWidget(second_group)
        self._second_group = second_group

        # ---- Generate button ----
        self._generate_btn = QPushButton("  Genera Portachiavi  ")
        self._generate_btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; "
            "font-weight: bold; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self._generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self._generate_btn)

        # ---- Auto-preview toggle ----
        self._auto_preview_check = QCheckBox("Anteprima automatica")
        self._auto_preview_check.setChecked(True)
        self._auto_preview_check.toggled.connect(self._on_auto_preview_toggled)
        layout.addWidget(self._auto_preview_check)

        layout.addStretch()

        # Connect all parameter widgets to debounced preview
        self._connect_preview_signals()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _update_color_btn(self, btn: QPushButton, color: QColor):
        btn.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #888; border-radius: 3px;"
        )

    def _pick_text_color(self):
        c = QColorDialog.getColor(self._text_color, self, "Text Color")
        if c.isValid():
            self._text_color = c
            self._update_color_btn(self._text_color_btn, c)

    def _pick_base_color(self):
        c = QColorDialog.getColor(self._base_color, self, "Base Color")
        if c.isValid():
            self._base_color = c
            self._update_color_btn(self._base_color_btn, c)

    def _pick_ring_color(self):
        c = QColorDialog.getColor(self._ring_color, self, "Ring Color")
        if c.isValid():
            self._ring_color = c
            self._update_color_btn(self._ring_color_btn, c)

    def _pick_second_color(self):
        c = QColorDialog.getColor(self._second_color, self, "Second Outline Color")
        if c.isValid():
            self._second_color = c
            self._update_color_btn(self._second_color_btn, c)

    def _build_config(self) -> KeychainConfig:
        base_shape = "capsule" if self._base_shape_combo.currentIndex() == 1 else "outline"
        return KeychainConfig(
            text=self._text_edit.text(),
            font_name=self._font_combo.currentText(),
            font_size=self._font_size_spin.value(),
            font_scale_x=self._font_scale_x_spin.value(),
            letter_spacing=self._letter_spacing_spin.value(),
            text_depth=self._text_depth_spin.value(),
            text_color=(self._text_color.red(), self._text_color.green(), self._text_color.blue()),
            base_shape=base_shape,
            base_thickness=self._base_thickness_spin.value(),
            outline_size=self._outline_size_spin.value(),
            edge_bevel=self._edge_bevel_spin.value(),
            bevel_segments=self._bevel_segments_spin.value(),
            base_color=(self._base_color.red(), self._base_color.green(), self._base_color.blue()),
            show_ring=self._show_ring_check.isChecked(),
            ring_outer_diameter=self._ring_diameter_spin.value(),
            ring_thickness=self._ring_thickness_spin.value(),
            ring_position=self._ring_position_spin.value(),
            ring_overlap=self._ring_overlap_spin.value(),
            ring_color=(self._ring_color.red(), self._ring_color.green(), self._ring_color.blue()),
            show_second_outline=self._second_group.isChecked(),
            second_outline_offset=self._second_offset_spin.value(),
            second_outline_height=self._second_height_spin.value(),
            second_outline_color=(self._second_color.red(), self._second_color.green(), self._second_color.blue()),
        )

    def _on_generate(self):
        self._preview_timer.stop()
        self.preview_cleared.emit()
        config = self._build_config()
        layers = generate_keychain(config)
        if layers:
            self.generate_requested.emit(layers)

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _connect_preview_signals(self) -> None:
        """Connect all parameter widgets to the debounced preview timer."""
        widgets = [
            self._text_edit,
            self._font_size_spin,
            self._font_scale_x_spin,
            self._letter_spacing_spin,
            self._text_depth_spin,
            self._base_shape_combo,
            self._base_thickness_spin,
            self._outline_size_spin,
            self._edge_bevel_spin,
            self._bevel_segments_spin,
            self._show_ring_check,
            self._ring_diameter_spin,
            self._ring_thickness_spin,
            self._ring_position_spin,
            self._ring_overlap_spin,
            self._second_offset_spin,
            self._second_height_spin,
        ]
        for w in widgets:
            if isinstance(w, QCheckBox):
                w.toggled.connect(self._schedule_preview)
            elif isinstance(w, QComboBox):
                w.currentIndexChanged.connect(self._schedule_preview)
            elif isinstance(w, QLineEdit):
                w.textChanged.connect(self._schedule_preview)
            else:
                w.valueChanged.connect(self._schedule_preview)

        # group boxes use toggled (checkable groups)
        self._second_group.toggled.connect(self._schedule_preview)

    def _on_auto_preview_toggled(self, checked: bool) -> None:
        if not checked:
            self._preview_timer.stop()
            self.preview_cleared.emit()

    def _schedule_preview(self, *args) -> None:
        """Restart the debounce timer on any parameter change."""
        if not self._auto_preview_check.isChecked():
            return
        self._preview_timer.start()

    def _do_preview(self) -> None:
        """Generate keychain and emit preview parts."""
        config = self._build_config()
        layers = generate_keychain(config)
        if not layers:
            self.preview_cleared.emit()
            return
        parts = []
        for ls in layers:
            if ls.triangulated_mesh is None:
                continue
            part = extrude_layer(
                ls.triangulated_mesh,
                ls.extrusion_params,
                ls.svg_layer.id,
                ls.svg_layer.name,
                ls.color,
            )
            parts.append(part)
        if parts:
            self.preview_requested.emit(parts)
        else:
            self.preview_cleared.emit()
