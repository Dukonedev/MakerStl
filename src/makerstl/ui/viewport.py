"""3D OpenGL viewport for real-time mesh preview with transform gizmo."""

from __future__ import annotations

import math
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QWheelEvent

from ..models.project import Project
from ..core.mesh_ops import compute_normals


# ------------------------------------------------------------------
# Gizmo modes
# ------------------------------------------------------------------

GIZMO_TRANSLATE = 0
GIZMO_ROTATE = 1
GIZMO_SCALE = 2


def _index_to_pick_color(idx: int) -> tuple[float, float, float]:
    """Convert a 0-based index to a unique RGB color for color picking."""
    r = ((idx + 1) >> 16 & 0xFF) / 255.0
    g = ((idx + 1) >> 8 & 0xFF) / 255.0
    b = ((idx + 1) & 0xFF) / 255.0
    return (r, g, b)


def _pick_color_to_index(r: int, g: int, b: int) -> int:
    """Convert an RGB color back to a 0-based index."""
    idx = (r << 16) | (g << 8) | b
    return idx - 1


class Viewport3D(QOpenGLWidget):
    """OpenGL 3D viewport with orbit camera and transform gizmo."""

    layer_clicked = Signal(str)
    transform_changed = Signal()  # emitted after gizmo drag completes

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self._project = project
        self._highlighted_layer: str | None = None

        # camera
        self._rotation_x = 30.0
        self._rotation_y = 45.0
        self._zoom = 50.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._far_clip = 10000.0
        self._grid_size = 50.0
        self._grid_step = 5.0

        # mouse tracking
        self._last_mouse = QPoint()
        self._mouse_button = Qt.MouseButton.NoButton
        self._press_pos = QPoint()

        # gizmo state
        self._gizmo_mode = GIZMO_TRANSLATE
        self._gizmo_active_axis: int | None = None  # 0=X, 1=Y, 2=Z, None
        self._gizmo_drag_start: np.ndarray | None = None
        self._gizmo_layer_start: np.ndarray | None = None

        # cached GL matrices for mouse hit-testing (updated each paintGL)
        self._cached_modelview = None
        self._cached_projection = None
        self._cached_viewport = None

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

    def set_project(self, project: Project) -> None:
        self._project = project
        self._highlighted_layer = None
        self.update()

    def initializeGL(self) -> None:
        glClearColor(0.18, 0.18, 0.22, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_NORMALIZE)
        glShadeModel(GL_SMOOTH)

        # light setup
        glLightfv(GL_LIGHT0, GL_POSITION, [5.0, 10.0, 10.0, 0.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)
        self._update_projection(w, h)

    def _update_projection(self, w: int, h: int) -> None:
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / max(h, 1)
        gluPerspective(45.0, aspect, max(0.1, self._zoom * 0.001), self._far_clip)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # camera transform
        glTranslatef(self._pan_x, self._pan_y, -self._zoom)
        glRotatef(self._rotation_x, 1.0, 0.0, 0.0)
        glRotatef(self._rotation_y, 0.0, 0.0, 1.0)

        # draw grid
        self._draw_grid()

        # draw parts
        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue

            part = layer.extruded_part
            is_highlighted = (layer.svg_layer.id == self._highlighted_layer)

            if is_highlighted:
                # highlight with brighter color
                r, g, b = part.color
                glColor3f(r / 255 * 1.3, g / 255 * 1.3, b / 255 * 1.3)
            else:
                r, g, b = part.color
                glColor3f(r / 255, g / 255, b / 255)

            self._draw_mesh(part.vertices, part.faces, part.normals)

        # draw gizmo if a layer is selected
        if self._highlighted_layer:
            self._draw_gizmo()

        # cache matrices for mouse hit-testing
        self._cached_modelview = glGetDoublev(GL_MODELVIEW_MATRIX).copy()
        self._cached_projection = glGetDoublev(GL_PROJECTION_MATRIX).copy()
        self._cached_viewport = glGetIntegerv(GL_VIEWPORT).copy()

    def _draw_mesh(self, verts: np.ndarray, faces: np.ndarray, normals: np.ndarray | None = None) -> None:
        """Draw a mesh using vertex arrays (batched, much faster than glBegin)."""
        if len(faces) == 0:
            return

        if normals is None:
            normals = compute_normals(verts, faces)

        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        glVertexPointer(3, GL_FLOAT, 0, verts.astype(np.float32))
        glNormalPointer(GL_FLOAT, 0, normals.astype(np.float32))

        glDrawElements(GL_TRIANGLES, faces.size, GL_UNSIGNED_INT, faces.astype(np.uint32))

        glDisableClientState(GL_NORMAL_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)

    def _draw_grid(self) -> None:
        """Draw a reference grid on the XY plane."""
        glDisable(GL_LIGHTING)
        glColor3f(0.3, 0.3, 0.3)
        glLineWidth(1.0)

        size = self._grid_size
        step = self._grid_step

        glBegin(GL_LINES)
        x = -size
        while x <= size:
            glVertex3f(x, -size, 0)
            glVertex3f(x, size, 0)
            x += step

        y = -size
        while y <= size:
            glVertex3f(-size, y, 0)
            glVertex3f(size, y, 0)
            y += step
        glEnd()

        glEnable(GL_LIGHTING)

    # --- Gizmo ---

    def _get_gizmo_position(self) -> np.ndarray | None:
        """Get the world-space position of the selected layer's bounding box center."""
        if not self._highlighted_layer:
            return None
        layer = self._project.get_layer_by_id(self._highlighted_layer)
        if not layer or layer.extruded_part is None:
            return None
        part = layer.extruded_part
        if len(part.vertices) == 0:
            return None
        # translate is already baked into extruded_part.vertices
        return (part.vertices.min(axis=0) + part.vertices.max(axis=0)) / 2.0

    def _draw_gizmo(self) -> None:
        """Draw translate/rotate/scale gizmo at selected layer position."""
        pos = self._get_gizmo_position()
        if pos is None:
            return

        glDisable(GL_LIGHTING)
        glDisable(GL_DEPTH_TEST)

        glPushMatrix()
        glTranslatef(pos[0], pos[1], pos[2])

        # gizmo size proportional to model, not zoom
        all_verts = []
        for layer in self._project.layers:
            if layer.effective_visible and layer.extruded_part and len(layer.extruded_part.vertices) > 0:
                all_verts.append(layer.extruded_part.vertices)
        if all_verts:
            combined = np.vstack(all_verts)
            model_size = max((combined.max(axis=0) - combined.min(axis=0)))
        else:
            model_size = 50.0
        scale = max(model_size * 0.03, 0.5)
        glScalef(scale, scale, scale)

        if self._gizmo_mode == GIZMO_TRANSLATE:
            self._draw_translate_gizmo()
        elif self._gizmo_mode == GIZMO_ROTATE:
            self._draw_rotate_gizmo()
        elif self._gizmo_mode == GIZMO_SCALE:
            self._draw_scale_gizmo()

        glPopMatrix()

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)

    def _draw_axis_arrow(self, axis: int, color: tuple[float, float, float],
                         is_active: bool = False) -> None:
        """Draw a single axis arrow. axis: 0=X, 1=Y, 2=Z."""
        r, g, b = color
        if is_active:
            r, g, b = min(1.0, r + 0.3), min(1.0, g + 0.3), min(1.0, b + 0.3)

        glColor3f(r, g, b)
        glLineWidth(3.0 if is_active else 2.0)

        glBegin(GL_LINES)
        if axis == 0:
            glVertex3f(0, 0, 0)
            glVertex3f(5, 0, 0)
        elif axis == 1:
            glVertex3f(0, 0, 0)
            glVertex3f(0, 5, 0)
        else:
            glVertex3f(0, 0, 0)
            glVertex3f(0, 0, 5)
        glEnd()

        # arrowhead
        glPushMatrix()
        if axis == 0:
            glTranslatef(5, 0, 0)
        elif axis == 1:
            glRotatef(90, 0, 0, 1)
            glTranslatef(5, 0, 0)
        else:
            glRotatef(-90, 1, 0, 0)
            glTranslatef(5, 0, 0)

        glBegin(GL_TRIANGLES)
        glVertex3f(0, 0, 1.5)
        glVertex3f(0, 0, -1.5)
        glVertex3f(2, 0, 0)
        glVertex3f(0, 0, -1.5)
        glVertex3f(0, 0, 1.5)
        glVertex3f(-2, 0, 0)
        glVertex3f(0, 1.5, 0)
        glVertex3f(0, -1.5, 0)
        glVertex3f(0, 0, 2)
        glVertex3f(0, -1.5, 0)
        glVertex3f(0, 1.5, 0)
        glVertex3f(0, 0, -2)
        glEnd()
        glPopMatrix()

        glLineWidth(1.0)

    def _draw_translate_gizmo(self) -> None:
        self._draw_axis_arrow(0, (1.0, 0.3, 0.3), self._gizmo_active_axis == 0)
        self._draw_axis_arrow(1, (0.3, 1.0, 0.3), self._gizmo_active_axis == 1)
        self._draw_axis_arrow(2, (0.3, 0.3, 1.0), self._gizmo_active_axis == 2)
        glColor3f(1.0, 1.0, 1.0)
        quad = gluNewQuadric()
        gluQuadricDrawStyle(quad, GLU_FILL)
        gluSphere(quad, 0.6, 12, 12)
        gluDeleteQuadric(quad)

    def _draw_rotate_gizmo(self) -> None:
        segments = 48
        radius = 4.0
        for axis, color in [(0, (1.0, 0.3, 0.3)), (1, (0.3, 1.0, 0.3)), (2, (0.3, 0.3, 1.0))]:
            is_active = self._gizmo_active_axis == axis
            r, g, b = color
            if is_active:
                r, g, b = min(1.0, r + 0.3), min(1.0, g + 0.3), min(1.0, b + 0.3)
            glColor3f(r, g, b)
            glLineWidth(3.0 if is_active else 2.0)
            glBegin(GL_LINE_LOOP)
            for i in range(segments):
                angle = 2.0 * math.pi * i / segments
                if axis == 0:
                    glVertex3f(0, radius * math.cos(angle), radius * math.sin(angle))
                elif axis == 1:
                    glVertex3f(radius * math.cos(angle), 0, radius * math.sin(angle))
                else:
                    glVertex3f(radius * math.cos(angle), radius * math.sin(angle), 0)
            glEnd()
        glLineWidth(1.0)

    def _draw_scale_gizmo(self) -> None:
        for axis, color in [(0, (1.0, 0.3, 0.3)), (1, (0.3, 1.0, 0.3)), (2, (0.3, 0.3, 1.0))]:
            is_active = self._gizmo_active_axis == axis
            r, g, b = color
            if is_active:
                r, g, b = min(1.0, r + 0.3), min(1.0, g + 0.3), min(1.0, b + 0.3)
            glColor3f(r, g, b)
            glLineWidth(3.0 if is_active else 2.0)
            glBegin(GL_LINES)
            if axis == 0:
                glVertex3f(0, 0, 0); glVertex3f(5, 0, 0)
            elif axis == 1:
                glVertex3f(0, 0, 0); glVertex3f(0, 5, 0)
            else:
                glVertex3f(0, 0, 0); glVertex3f(0, 0, 5)
            glEnd()
            glPushMatrix()
            if axis == 0:
                glTranslatef(5, 0, 0)
            elif axis == 1:
                glTranslatef(0, 5, 0)
            else:
                glTranslatef(0, 0, 5)
            glutSolidCube(1.0)
            glPopMatrix()
        glLineWidth(1.0)

    def _gizmo_hit_test(self, pos: QPoint) -> int | None:
        """Hit-test the gizmo axes. Returns 0=X, 1=Y, 2=Z, or None."""
        if not self._highlighted_layer or self._cached_modelview is None:
            return None
        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return None

        mv = self._cached_modelview
        proj = self._cached_projection
        vp = self._cached_viewport

        screen_x, screen_y, screen_z = gluProject(
            gizmo_pos[0], gizmo_pos[1], gizmo_pos[2],
            mv, proj, vp
        )

        dx = pos.x() - screen_x
        dy = (self.height() - pos.y()) - screen_y
        dist_center = math.sqrt(dx * dx + dy * dy)

        # model-based gizmo size (same as draw)
        all_verts = []
        for layer in self._project.layers:
            if layer.effective_visible and layer.extruded_part and len(layer.extruded_part.vertices) > 0:
                all_verts.append(layer.extruded_part.vertices)
        if all_verts:
            combined = np.vstack(all_verts)
            model_size = max(combined.max(axis=0) - combined.min(axis=0))
        else:
            model_size = 50.0

        scale = max(model_size * 0.03, 0.5)
        gizmo_screen_approx = scale * 5.0 * self._zoom / max(gizmo_pos[2] + self._zoom, 1.0) * self.height() * 0.005
        if dist_center > gizmo_screen_approx * 3.0:
            return None

        best_axis = None
        best_dist = 1e9
        for axis in range(3):
            end_world = gizmo_pos.copy()
            end_world[axis] += 5.0 * scale
            sx, sy, sz = gluProject(
                end_world[0], end_world[1], end_world[2],
                mv, proj, vp
            )
            adx = pos.x() - sx
            ady = (self.height() - pos.y()) - sy
            d = math.sqrt(adx * adx + ady * ady)
            if d < 40 and d < best_dist:
                best_dist = d
                best_axis = axis

        return best_axis

    def set_gizmo_mode(self, mode: int) -> None:
        self._gizmo_mode = mode
        self._gizmo_active_axis = None
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse = event.position().toPoint()
        self._press_pos = event.position().toPoint()
        self._mouse_button = event.button()

        # gizmo hit test on left click
        if event.button() == Qt.MouseButton.LeftButton and self._highlighted_layer:
            axis = self._gizmo_hit_test(self._press_pos)
            if axis is not None:
                self._gizmo_active_axis = axis
                gizmo_pos = self._get_gizmo_position()
                if gizmo_pos is not None:
                    self._gizmo_drag_start = self._screen_to_world(self._press_pos, gizmo_pos[2])
                    layer = self._project.get_layer_by_id(self._highlighted_layer)
                    if layer:
                        self._gizmo_layer_start = np.array([
                            layer.extrusion_params.translate_x,
                            layer.extrusion_params.translate_y,
                            layer.extrusion_params.scale_x if self._gizmo_mode == GIZMO_SCALE else 0.0,
                            layer.extrusion_params.scale_y if self._gizmo_mode == GIZMO_SCALE else 0.0,
                        ])
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._gizmo_active_axis is not None:
            self._gizmo_active_axis = None
            self._gizmo_drag_start = None
            self._gizmo_layer_start = None
            self.transform_changed.emit()
        elif (self._mouse_button == Qt.MouseButton.LeftButton
              and (pos - self._press_pos).manhattanLength() < 4):
            self._pick_layer(pos)
        self._mouse_button = Qt.MouseButton.NoButton
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        dx = event.position().toPoint().x() - self._last_mouse.x()
        dy = event.position().toPoint().y() - self._last_mouse.y()
        self._last_mouse = event.position().toPoint()

        if self._gizmo_active_axis is not None and self._highlighted_layer:
            self._handle_gizmo_drag(event.position().toPoint())
        elif self._mouse_button == Qt.MouseButton.LeftButton:
            self._rotation_y += dx * 0.5
            self._rotation_x += dy * 0.5
            self._rotation_x = max(-90, min(90, self._rotation_x))
        elif self._mouse_button == Qt.MouseButton.MiddleButton:
            self._pan_x += dx * 0.1
            self._pan_y -= dy * 0.1
        elif self._mouse_button == Qt.MouseButton.RightButton:
            self._zoom *= 1.0 + dy * 0.01
            self._zoom = max(1, min(5000, self._zoom))

        self.update()

    def _screen_to_world(self, screen_pos: QPoint, z_plane: float = 0.0) -> np.ndarray:
        """Approximate world-space position at the given screen point on a Z-plane."""
        if self._cached_modelview is None:
            return np.zeros(3)

        mv = self._cached_modelview
        proj = self._cached_projection
        vp = self._cached_viewport

        x = screen_pos.x()
        y = self.height() - screen_pos.y()

        near_pt = gluUnProject(x, y, 0.0, mv, proj, vp)
        far_pt = gluUnProject(x, y, 1.0, mv, proj, vp)

        near = np.array(near_pt)
        far = np.array(far_pt)
        direction = far - near
        if abs(direction[2]) < 1e-8:
            return near
        t = (z_plane - near[2]) / direction[2]
        return near + direction * t

    def _handle_gizmo_drag(self, pos: QPoint) -> None:
        """Update layer transform based on gizmo drag."""
        if self._gizmo_active_axis is None or self._gizmo_drag_start is None:
            return
        if self._gizmo_layer_start is None:
            return

        layer = self._project.get_layer_by_id(self._highlighted_layer)
        if not layer:
            return

        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return

        current_world = self._screen_to_world(pos, gizmo_pos[2])
        delta = current_world - self._gizmo_drag_start

        if self._gizmo_mode == GIZMO_TRANSLATE:
            if self._gizmo_active_axis == 0:
                layer.extrusion_params.translate_x = self._gizmo_layer_start[0] + delta[0]
            elif self._gizmo_active_axis == 1:
                layer.extrusion_params.translate_y = self._gizmo_layer_start[1] + delta[1]

        elif self._gizmo_mode == GIZMO_SCALE:
            # scale factor based on drag distance relative to gizmo center
            drag_dist = delta[0] if self._gizmo_active_axis == 0 else delta[1]
            scale_factor = 1.0 + drag_dist * 0.02
            scale_factor = max(0.01, scale_factor)
            base_sx = self._gizmo_layer_start[2]
            base_sy = self._gizmo_layer_start[3]
            if self._gizmo_active_axis == 0:
                layer.extrusion_params.scale_x = base_sx * scale_factor
            elif self._gizmo_active_axis == 1:
                layer.extrusion_params.scale_y = base_sy * scale_factor

        self._project.recompute_extrusions()
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        self._zoom *= 1.0 - delta * 0.001
        self._zoom = max(1, min(5000, self._zoom))
        self.update()

    # --- Public API ---

    def refresh(self) -> None:
        """Force re-render."""
        self.update()

    def fit_to_scene(self) -> None:
        """Adjust camera zoom and pan to fit all visible parts."""
        all_verts = []
        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue
            part = layer.extruded_part
            if len(part.vertices) > 0:
                all_verts.append(part.vertices)

        if not all_verts:
            return

        combined = np.vstack(all_verts)
        vmin = combined.min(axis=0)
        vmax = combined.max(axis=0)
        center = (vmin + vmax) / 2.0
        extent = vmax - vmin
        max_dim = max(extent[0], extent[1], extent[2])

        if max_dim < 1e-6:
            return

        # position camera: zoom based on bounding sphere, pan to center
        self._zoom = max_dim * 1.8
        self._pan_x = -center[0]
        self._pan_y = -center[1]
        self._rotation_x = 30.0
        self._rotation_y = 45.0

        # adaptive grid: nice round number around the model size
        self._grid_size = max_dim * 1.2
        # pick a step that gives ~20 grid lines
        raw_step = max_dim / 10.0
        # round to nearest nice value: 0.1, 0.5, 1, 2, 5, 10, 50, 100...
        magnitude = 10 ** int(np.floor(np.log10(max(raw_step, 0.01))))
        residual = raw_step / magnitude
        if residual < 1.5:
            self._grid_step = magnitude
        elif residual < 3.5:
            self._grid_step = 2 * magnitude
        elif residual < 7.5:
            self._grid_step = 5 * magnitude
        else:
            self._grid_step = 10 * magnitude

        # update far clip plane
        self._far_clip = max(10000.0, max_dim * 100)

        self.update()

    def highlight_layer(self, layer_id: str) -> None:
        """Highlight a specific layer."""
        self._highlighted_layer = layer_id
        self.update()

    # --- Color picking ---

    def _draw_pick_pass(self) -> None:
        """Render the scene with unique ID colors per layer for picking."""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(self._pan_x, self._pan_y, -self._zoom)
        glRotatef(self._rotation_x, 1.0, 0.0, 0.0)
        glRotatef(self._rotation_y, 0.0, 0.0, 1.0)

        glDisable(GL_LIGHTING)
        glDisable(GL_COLOR_MATERIAL)

        idx = 0
        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue
            part = layer.extruded_part
            if len(part.faces) == 0:
                continue

            r, g, b = _index_to_pick_color(idx)
            glColor3f(r, g, b)

            normals = part.normals if part.normals is not None else compute_normals(part.vertices, part.faces)

            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_NORMAL_ARRAY)
            glVertexPointer(3, GL_FLOAT, 0, part.vertices.astype(np.float32))
            glNormalPointer(GL_FLOAT, 0, normals.astype(np.float32))
            glDrawElements(GL_TRIANGLES, part.faces.size, GL_UNSIGNED_INT, part.faces.astype(np.uint32))
            glDisableClientState(GL_NORMAL_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)
            idx += 1

        glEnable(GL_LIGHTING)
        glEnable(GL_COLOR_MATERIAL)

    def _pick_layer(self, pos: QPoint) -> None:
        """Read the pixel under the cursor to find which layer was clicked."""
        # render pick pass into a separate framebuffer (use default, read after)
        self.makeCurrent()

        # save state
        old_viewport = glGetIntegerv(GL_VIEWPORT)

        self._draw_pick_pass()

        # read pixel at click position (Y is flipped)
        x = pos.x()
        y = self.height() - pos.y() - 1
        pixel = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
        r, g, b = pixel[0], pixel[1], pixel[2]

        self.doneCurrent()

        idx = _pick_color_to_index(r, g, b)

        # map index back to visible layer
        vis_idx = 0
        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue
            if len(layer.extruded_part.faces) == 0:
                continue
            if vis_idx == idx:
                self.layer_clicked.emit(layer.svg_layer.id)
                return
            vis_idx += 1

        # clicked on empty space
        self.layer_clicked.emit("")
