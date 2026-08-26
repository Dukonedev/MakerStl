"""Properties panel: controls for extrusion, scale, and color.

Supports editing a single layer, multiple layers, or all layers in a group.
When values differ across selected layers, fields show a mixed indicator.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox,
    QPushButton, QColorDialog, QLabel, QGroupBox,
    QSizePolicy, QToolButton, QComboBox, QSpinBox,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ..models.project import Project, LayerState, LayerGroup
from ..core.quality import QualitySettings, PRESETS, PRESET_NAMES


class PropertiesPanel(QWidget):
    """Right panel showing dimensions (always) + layer properties (when selected)."""

    parameter_changed = Signal()
    dimensions_changed = Signal()

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self._selected_ids: list[str] = []
        self._updating_dims = False

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

        # ---- Dimensions group (always visible) ----
        dims_group = QGroupBox("Dimensions (mm)")
        dims_group.setCheckable(True)
        dims_group.setChecked(True)
        dims_form = QFormLayout()

        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(1.0, 10000.0)
        self._width_spin.setValue(100.0)
        self._width_spin.setSuffix(" mm")
        self._width_spin.setDecimals(2)
        self._width_spin.valueChanged.connect(self._on_width_changed)
        dims_form.addRow("Width (X):", self._width_spin)

        self._height_spin_dims = QDoubleSpinBox()
        self._height_spin_dims.setRange(1.0, 10000.0)
        self._height_spin_dims.setValue(100.0)
        self._height_spin_dims.setSuffix(" mm")
        self._height_spin_dims.setDecimals(2)
        self._height_spin_dims.valueChanged.connect(self._on_height_changed)
        dims_form.addRow("Height (Y):", self._height_spin_dims)

        self._lock_btn = QToolButton()
        self._lock_btn.setCheckable(True)
        self._lock_btn.setChecked(True)
        self._lock_btn.setText("\U0001F512")
        self._lock_btn.setToolTip("Lock proportions (ON)")
        self._lock_btn.setFixedWidth(30)
        self._lock_btn.clicked.connect(self._on_lock_toggle)
        dims_form.addRow("Proportional:", self._lock_btn)

        dims_group.setLayout(dims_form)
        layout.addWidget(dims_group)

        # ---- Quality group (always visible) ----
        quality_group = QGroupBox("Quality")
        quality_group.setCheckable(True)
        quality_group.setChecked(True)
        quality_form = QFormLayout()

        self._quality_preset_combo = QComboBox()
        self._quality_preset_combo.addItems(PRESET_NAMES + ["Custom"])
        self._quality_preset_combo.currentTextChanged.connect(self._on_quality_preset_changed)
        quality_form.addRow("Preset:", self._quality_preset_combo)

        self._quality_curve_spin = QDoubleSpinBox()
        self._quality_curve_spin.setRange(0.05, 5.0)
        self._quality_curve_spin.setValue(0.5)
        self._quality_curve_spin.setSuffix(" mm")
        self._quality_curve_spin.setDecimals(2)
        self._quality_curve_spin.setSingleStep(0.1)
        self._quality_curve_spin.valueChanged.connect(self._on_quality_param_changed)
        quality_form.addRow("Curve Resolution:", self._quality_curve_spin)

        self._quality_tolerance_spin = QDoubleSpinBox()
        self._quality_tolerance_spin.setRange(0.0, 2.0)
        self._quality_tolerance_spin.setValue(0.1)
        self._quality_tolerance_spin.setSuffix(" mm")
        self._quality_tolerance_spin.setDecimals(2)
        self._quality_tolerance_spin.setSingleStep(0.05)
        self._quality_tolerance_spin.valueChanged.connect(self._on_quality_param_changed)
        quality_form.addRow("Tolerance:", self._quality_tolerance_spin)

        self._quality_circle_spin = QSpinBox()
        self._quality_circle_spin.setRange(8, 128)
        self._quality_circle_spin.setValue(32)
        self._quality_circle_spin.setSingleStep(8)
        self._quality_circle_spin.valueChanged.connect(self._on_quality_param_changed)
        quality_form.addRow("Circle Segments:", self._quality_circle_spin)

        self._quality_dpi_spin = QSpinBox()
        self._quality_dpi_spin.setRange(72, 1200)
        self._quality_dpi_spin.setValue(300)
        self._quality_dpi_spin.setSingleStep(50)
        self._quality_dpi_spin.valueChanged.connect(self._on_quality_param_changed)
        quality_form.addRow("Text DPI:", self._quality_dpi_spin)

        self._quality_text_tol_spin = QDoubleSpinBox()
        self._quality_text_tol_spin.setRange(0.0, 2.0)
        self._quality_text_tol_spin.setValue(0.5)
        self._quality_text_tol_spin.setSuffix(" mm")
        self._quality_text_tol_spin.setDecimals(2)
        self._quality_text_tol_spin.setSingleStep(0.1)
        self._quality_text_tol_spin.valueChanged.connect(self._on_quality_param_changed)
        quality_form.addRow("Text Tolerance:", self._quality_text_tol_spin)

        quality_group.setLayout(quality_form)
        layout.addWidget(quality_group)
        self._quality_group = quality_group

        self._quality_updating = False

        # ---- Layer properties (below) ----
        # layer name
        self._name_label = QLabel("No layer selected")
        self._name_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px; color: #ddd;")
        layout.addWidget(self._name_label)

        # extrusion group
        ext_group = QGroupBox("Extrusion")
        ext_group.setCheckable(True)
        ext_group.setChecked(True)
        ext_form = QFormLayout()

        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(0.1, 1000.0)
        self._height_spin.setValue(5.0)
        self._height_spin.setSuffix(" mm")
        self._height_spin.setDecimals(2)
        self._height_spin.valueChanged.connect(self._on_param_changed)
        ext_form.addRow("Height (Z):", self._height_spin)

        self._chamfer_spin = QDoubleSpinBox()
        self._chamfer_spin.setRange(0.0, 100.0)
        self._chamfer_spin.setValue(0.0)
        self._chamfer_spin.setSuffix(" mm")
        self._chamfer_spin.setDecimals(2)
        self._chamfer_spin.valueChanged.connect(self._on_param_changed)
        ext_form.addRow("Chamfer:", self._chamfer_spin)

        self._bevel_radius_spin = QDoubleSpinBox()
        self._bevel_radius_spin.setRange(0.0, 10.0)
        self._bevel_radius_spin.setValue(0.0)
        self._bevel_radius_spin.setSuffix(" mm")
        self._bevel_radius_spin.setDecimals(2)
        self._bevel_radius_spin.setSingleStep(0.1)
        self._bevel_radius_spin.valueChanged.connect(self._on_param_changed)
        ext_form.addRow("Bevel Radius:", self._bevel_radius_spin)

        self._bevel_segments_spin = QSpinBox()
        self._bevel_segments_spin.setRange(2, 12)
        self._bevel_segments_spin.setValue(3)
        self._bevel_segments_spin.valueChanged.connect(self._on_param_changed)
        ext_form.addRow("Bevel Segments:", self._bevel_segments_spin)

        self._tx_spin = QDoubleSpinBox()
        self._tx_spin.setRange(-5000.0, 5000.0)
        self._tx_spin.setValue(0.0)
        self._tx_spin.setSuffix(" mm")
        self._tx_spin.setDecimals(2)
        self._tx_spin.valueChanged.connect(self._on_param_changed)
        ext_form.addRow("Translate X:", self._tx_spin)

        self._ty_spin = QDoubleSpinBox()
        self._ty_spin.setRange(-5000.0, 5000.0)
        self._ty_spin.setValue(0.0)
        self._ty_spin.setSuffix(" mm")
        self._ty_spin.setDecimals(2)
        self._ty_spin.valueChanged.connect(self._on_param_changed)
        ext_form.addRow("Translate Y:", self._ty_spin)

        ext_group.setLayout(ext_form)
        layout.addWidget(ext_group)
        self._ext_group = ext_group
        self._ext_form = ext_form
        self._tx_row_label = ext_form.labelForField(self._tx_spin)
        self._ty_row_label = ext_form.labelForField(self._ty_spin)

        # ---- Ring group (only for ring layers) ----
        self._ring_group = QGroupBox("Ring")
        self._ring_group.setCheckable(True)
        self._ring_group.setChecked(True)
        ring_form = QFormLayout()

        self._ring_outer_spin = QDoubleSpinBox()
        self._ring_outer_spin.setRange(1.0, 1000.0)
        self._ring_outer_spin.setValue(14.0)
        self._ring_outer_spin.setSuffix(" mm")
        self._ring_outer_spin.setDecimals(2)
        self._ring_outer_spin.valueChanged.connect(self._on_ring_param_changed)
        ring_form.addRow("Outer Diameter:", self._ring_outer_spin)

        self._ring_thickness_spin = QDoubleSpinBox()
        self._ring_thickness_spin.setRange(0.1, 500.0)
        self._ring_thickness_spin.setValue(3.0)
        self._ring_thickness_spin.setSuffix(" mm")
        self._ring_thickness_spin.setDecimals(2)
        self._ring_thickness_spin.valueChanged.connect(self._on_ring_param_changed)
        ring_form.addRow("Thickness:", self._ring_thickness_spin)

        self._ring_group.setLayout(ring_form)
        layout.addWidget(self._ring_group)
        self._ring_group.setVisible(False)

        # scale group
        scale_group = QGroupBox("Scale")
        scale_group.setCheckable(True)
        scale_group.setChecked(True)
        scale_form = QFormLayout()

        self._scale_x_spin = QDoubleSpinBox()
        self._scale_x_spin.setRange(0.01, 100.0)
        self._scale_x_spin.setValue(1.0)
        self._scale_x_spin.setDecimals(3)
        self._scale_x_spin.valueChanged.connect(self._on_param_changed)
        scale_form.addRow("Scale X:", self._scale_x_spin)

        self._scale_y_spin = QDoubleSpinBox()
        self._scale_y_spin.setRange(0.01, 100.0)
        self._scale_y_spin.setValue(1.0)
        self._scale_y_spin.setDecimals(3)
        self._scale_y_spin.valueChanged.connect(self._on_param_changed)
        scale_form.addRow("Scale Y:", self._scale_y_spin)

        scale_group.setLayout(scale_form)
        layout.addWidget(scale_group)
        self._scale_group = scale_group

        # color group
        color_group = QGroupBox("Color")
        color_group.setCheckable(True)
        color_group.setChecked(True)
        color_layout = QVBoxLayout()

        self._color_preview = QLabel()
        self._color_preview.setFixedHeight(24)
        self._color_preview.setStyleSheet("background-color: #C8C8C8; border: 1px solid #555; border-radius: 3px;")
        color_layout.addWidget(self._color_preview)

        self._color_btn = QPushButton("Choose Color...")
        self._color_btn.clicked.connect(self._on_color_picker)
        color_layout.addWidget(self._color_btn)

        self._hex_label = QLabel("HEX: #C8C8C8")
        self._hex_label.setStyleSheet("color: #888; font-size: 11px;")
        color_layout.addWidget(self._hex_label)

        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        layout.addStretch()

        self._set_enabled(False)

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _set_enabled(self, enabled: bool) -> None:
        for child in self.findChildren(QWidget):
            if child != self._name_label and child is not self._quality_group:
                child.setEnabled(enabled)

    def _get_target_layers(self) -> list[LayerState]:
        """Return the layers targeted by the current selection."""
        layers = []
        for lid in self._selected_ids:
            layer = self._project.get_layer_by_id(lid)
            if layer:
                layers.append(layer)
        return layers

    def set_layers(self, layer_ids: list[str]) -> None:
        """Load properties for the given layer IDs (single, multi, or group)."""
        self._selected_ids = list(layer_ids)
        layers = self._get_target_layers()

        if not layers:
            self._name_label.setText("No layer selected")
            self._set_enabled(False)
            self._ext_group.setVisible(False)
            self._scale_group.setVisible(False)
            self._ring_group.setVisible(False)
            return

        # check if any selected layer is locked
        any_locked = any(l.locked for l in layers)

        self._set_enabled(True)
        if any_locked:
            self._set_enabled(False)
            self._name_label.setText(layers[0].svg_layer.name + "  (locked)")
        else:
            self._set_enabled(True)

        # block signals during update
        for w in [self._height_spin, self._chamfer_spin,
                  self._bevel_radius_spin, self._bevel_segments_spin,
                  self._scale_x_spin, self._scale_y_spin,
                  self._tx_spin, self._ty_spin]:
            w.blockSignals(True)

        # name label
        if len(layers) == 1:
            self._name_label.setText(layers[0].svg_layer.name)
        else:
            self._name_label.setText(f"{len(layers)} layers selected")

        # determine context
        first = layers[0]
        is_ring = first.is_ring and len(layers) == 1
        is_single = len(layers) == 1

        # --- context-based visibility ---
        # Extrusion group: always visible when layer selected
        self._ext_group.setVisible(True)
        # Translate rows: only for ring layers
        self._tx_row_label.setVisible(is_ring)
        self._tx_spin.setVisible(is_ring)
        self._ty_row_label.setVisible(is_ring)
        self._ty_spin.setVisible(is_ring)
        # Scale group: only for non-base, non-ring single layers
        self._scale_group.setVisible(is_single and not is_ring)

        # Ring group: only for ring layers
        self._ring_group.setVisible(is_ring)

        # show values from first layer; mark mixed values
        self._height_spin.setValue(first.extrusion_params.height)
        self._chamfer_spin.setValue(first.extrusion_params.chamfer)
        self._bevel_radius_spin.setValue(first.extrusion_params.bevel_radius)
        self._bevel_segments_spin.setValue(first.extrusion_params.bevel_segments)
        self._scale_x_spin.setValue(first.extrusion_params.scale_x)
        self._scale_y_spin.setValue(first.extrusion_params.scale_y)
        self._tx_spin.setValue(first.extrusion_params.translate_x)
        self._ty_spin.setValue(first.extrusion_params.translate_y)

        if is_ring:
            self._ring_outer_spin.blockSignals(True)
            self._ring_thickness_spin.blockSignals(True)
            self._ring_outer_spin.setValue(first.ring_outer_d)
            self._ring_thickness_spin.setValue(first.ring_thickness)
            self._ring_outer_spin.blockSignals(False)
            self._ring_thickness_spin.blockSignals(False)

        # color: use first layer's color
        r, g, b = first.color
        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        self._color_preview.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #555; border-radius: 3px;"
        )
        self._hex_label.setText(f"HEX: {hex_color}")

        for w in [self._height_spin, self._chamfer_spin,
                  self._bevel_radius_spin, self._bevel_segments_spin,
                  self._scale_x_spin, self._scale_y_spin,
                  self._tx_spin, self._ty_spin]:
            w.blockSignals(False)

    def _on_param_changed(self) -> None:
        layers = self._get_target_layers()
        if not layers:
            return

        for layer in layers:
            layer.update_height(self._height_spin.value())
            layer.extrusion_params.chamfer = self._chamfer_spin.value()
            layer.extrusion_params.bevel_radius = self._bevel_radius_spin.value()
            layer.extrusion_params.bevel_segments = self._bevel_segments_spin.value()
            layer.update_scale(self._scale_x_spin.value(), self._scale_y_spin.value())
            layer.extrusion_params.translate_x = self._tx_spin.value()
            layer.extrusion_params.translate_y = self._ty_spin.value()

        self.parameter_changed.emit()

    def _on_ring_param_changed(self) -> None:
        layers = self._get_target_layers()
        if not layers or len(layers) != 1:
            return
        layer = layers[0]
        if not layer.is_ring:
            return
        outer_d = self._ring_outer_spin.value()
        thickness = self._ring_thickness_spin.value()
        self._project.regenerate_ring(layer.svg_layer.id, outer_d, thickness)
        self.parameter_changed.emit()

    def _on_color_picker(self) -> None:
        layers = self._get_target_layers()
        if not layers:
            return

        first = layers[0]
        r, g, b = first.color
        color = QColorDialog.getColor(QColor(r, g, b), self, "Choose Layer Color")
        if color.isValid():
            for layer in layers:
                layer.update_color(color.red(), color.green(), color.blue())
            hex_color = f"#{color.red():02X}{color.green():02X}{color.blue():02X}"
            self._color_preview.setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #555; border-radius: 3px;"
            )
            self._hex_label.setText(f"HEX: {hex_color}")
            self.parameter_changed.emit()

    def set_project(self, project: Project) -> None:
        self._project = project
        self._selected_ids.clear()
        self._ext_group.setVisible(False)
        self._scale_group.setVisible(False)
        self._ring_group.setVisible(False)
        self.load_quality()
        self.refresh_dimensions()

    # ------------------------------------------------------------------
    # Dimensions (global)
    # ------------------------------------------------------------------

    def refresh_dimensions(self) -> None:
        """Update the Width/Height fields from project base_size and global_scale."""
        self._updating_dims = True
        w = self._project.base_size_x * self._project.global_scale
        h = self._project.base_size_y * self._project.global_scale
        self._width_spin.setValue(w)
        self._height_spin_dims.setValue(h)
        self._updating_dims = False

    def _on_width_changed(self) -> None:
        if self._updating_dims:
            return
        self._updating_dims = True
        new_w = self._width_spin.value()
        if self._lock_btn.isChecked() and self._project.base_size_x > 0:
            ratio = new_w / self._project.base_size_x
            self._project.global_scale = ratio
            new_h = self._project.base_size_y * ratio
            self._height_spin_dims.setValue(new_h)
        else:
            if self._project.base_size_x > 0:
                self._project.global_scale = new_w / self._project.base_size_x
        self._updating_dims = False
        self.dimensions_changed.emit()

    def _on_height_changed(self) -> None:
        if self._updating_dims:
            return
        self._updating_dims = True
        new_h = self._height_spin_dims.value()
        if self._lock_btn.isChecked() and self._project.base_size_y > 0:
            ratio = new_h / self._project.base_size_y
            self._project.global_scale = ratio
            new_w = self._project.base_size_x * ratio
            self._width_spin.setValue(new_w)
        else:
            if self._project.base_size_y > 0:
                self._project.global_scale = new_h / self._project.base_size_y
        self._updating_dims = False
        self.dimensions_changed.emit()

    def _on_lock_toggle(self) -> None:
        if self._lock_btn.isChecked():
            self._lock_btn.setText("\U0001F512")
            self._lock_btn.setToolTip("Lock proportions (ON)")
        else:
            self._lock_btn.setText("\U0001F513")
            self._lock_btn.setToolTip("Lock proportions (OFF)")

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    def load_quality(self) -> None:
        """Load quality settings from project into the UI."""
        self._quality_updating = True
        q = self._project.quality
        self._quality_curve_spin.setValue(q.curve_resolution)
        self._quality_tolerance_spin.setValue(q.tolerance)
        self._quality_circle_spin.setValue(q.circle_segments)
        self._quality_dpi_spin.setValue(q.text_dpi)
        self._quality_text_tol_spin.setValue(q.text_tolerance)

        # select preset if it matches
        idx = self._quality_preset_combo.findText(q.preset)
        if idx >= 0:
            self._quality_preset_combo.setCurrentIndex(idx)
        else:
            self._quality_preset_combo.setCurrentText("Custom")
        self._quality_updating = False

    def _on_quality_preset_changed(self, name: str) -> None:
        if self._quality_updating:
            return
        self._quality_updating = True
        if name in PRESETS:
            p = PRESETS[name]
            self._quality_curve_spin.setValue(p.curve_resolution)
            self._quality_tolerance_spin.setValue(p.tolerance)
            self._quality_circle_spin.setValue(p.circle_segments)
            self._quality_dpi_spin.setValue(p.text_dpi)
            self._quality_text_tol_spin.setValue(p.text_tolerance)
            self._project.quality.apply_preset(name)
        self._quality_updating = False
        self.parameter_changed.emit()

    def _on_quality_param_changed(self) -> None:
        if self._quality_updating:
            return
        self._quality_updating = True
        q = self._project.quality
        q.curve_resolution = self._quality_curve_spin.value()
        q.tolerance = self._quality_tolerance_spin.value()
        q.circle_segments = self._quality_circle_spin.value()
        q.text_dpi = self._quality_dpi_spin.value()
        q.text_tolerance = self._quality_text_tol_spin.value()
        q.preset = "Custom"
        idx = self._quality_preset_combo.findText("Custom")
        if idx >= 0:
            self._quality_preset_combo.setCurrentIndex(idx)
        self._quality_updating = False
        self.parameter_changed.emit()
