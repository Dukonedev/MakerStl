"""3D OpenGL viewport for real-time mesh preview with transform gizmo.

Uses GLSL shaders exclusively — no fixed-function pipeline calls.
All geometry (meshes, grid, axes, gizmo) rendered via VBOs + shaders.
Compatible with macOS Core Profile OpenGL.
"""

from __future__ import annotations

import ctypes
import math
import numpy as np
from OpenGL.GL import *
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtCore import Qt, QPoint, Signal

from ..models.project import Project
from ..core.mesh_ops import compute_normals
from ..core.shader_manager import ShaderProgram


# ------------------------------------------------------------------
# Matrix utilities (pure numpy, no GLU dependency)
# ------------------------------------------------------------------

def _perspective_matrix(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    fov_rad = math.radians(fov_deg)
    f = 1.0 / math.tan(fov_rad / 2.0)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def _ortho_matrix(left: float, right: float, bottom: float, top: float,
                  near: float, far: float) -> np.ndarray:
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = 2.0 / (right - left)
    m[1, 1] = 2.0 / (top - bottom)
    m[2, 2] = -2.0 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    m[3, 3] = 1.0
    return m


def _translate_matrix(x: float, y: float, z: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float64)
    m[0, 3] = x
    m[1, 3] = y
    m[2, 3] = z
    return m


def _rotate_x_matrix(angle_deg: float) -> np.ndarray:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4, dtype=np.float64)
    m[1, 1] = c
    m[1, 2] = -s
    m[2, 1] = s
    m[2, 2] = c
    return m


def _rotate_z_matrix(angle_deg: float) -> np.ndarray:
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m


def _scale_matrix(sx: float, sy: float, sz: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = sx
    m[1, 1] = sy
    m[2, 2] = sz
    return m


def _glu_project(obj: np.ndarray, modelview: np.ndarray,
                 projection: np.ndarray, viewport: np.ndarray) -> np.ndarray:
    v = np.array([obj[0], obj[1], obj[2], 1.0], dtype=np.float64)
    eye = modelview @ v
    clip = projection @ eye
    if abs(clip[3]) < 1e-10:
        return np.zeros(3)
    ndc = clip[:3] / clip[3]
    x = viewport[0] + (ndc[0] + 1.0) * 0.5 * viewport[2]
    y = viewport[1] + (ndc[1] + 1.0) * 0.5 * viewport[3]
    z = (ndc[2] + 1.0) * 0.5
    return np.array([x, y, z])


def _glu_unproject(win: np.ndarray, modelview: np.ndarray,
                   projection: np.ndarray, viewport: np.ndarray) -> np.ndarray:
    x = (2.0 * (win[0] - viewport[0]) / viewport[2]) - 1.0
    y = (2.0 * (win[1] - viewport[1]) / viewport[3]) - 1.0
    z = 2.0 * win[2] - 1.0
    inv_pv = np.linalg.inv(projection @ modelview)
    v = np.array([x, y, z, 1.0], dtype=np.float64)
    world = inv_pv @ v
    if abs(world[3]) < 1e-10:
        return np.zeros(3)
    return world[:3] / world[3]


# ------------------------------------------------------------------
# Gizmo modes
# ------------------------------------------------------------------

GIZMO_TRANSLATE = 0
GIZMO_ROTATE = 1
GIZMO_SCALE = 2


# ------------------------------------------------------------------
# Color picking helpers
# ------------------------------------------------------------------

def _index_to_pick_color(idx: int) -> tuple[float, float, float]:
    r = ((idx + 1) >> 16 & 0xFF) / 255.0
    g = ((idx + 1) >> 8 & 0xFF) / 255.0
    b = ((idx + 1) & 0xFF) / 255.0
    return (r, g, b)


def _pick_color_to_index(r: int, g: int, b: int) -> int:
    idx = (r << 16) | (g << 8) | b
    return idx - 1


# ------------------------------------------------------------------
# VBO helpers
# ------------------------------------------------------------------

def _upload_flat_vbo(verts_colors: list) -> tuple[int, int, int]:
    """Upload interleaved position+color data and return (vao, vbo, count)."""
    data = np.array(verts_colors, dtype=np.float32)
    vao = glGenVertexArrays(1)
    vbo = glGenBuffers(1)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)
    stride = 6 * 4
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, False, stride, ctypes.c_void_p(0))
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 3, GL_FLOAT, False, stride, ctypes.c_void_p(12))
    glBindVertexArray(0)
    return vao, vbo, len(verts_colors)


def _free_flat_vbo(vao: int, vbo: int) -> None:
    """Delete a flat VBO pair."""
    glDeleteVertexArrays(1, [vao])
    glDeleteBuffers(1, [vbo])


# ------------------------------------------------------------------
# Viewport
# ------------------------------------------------------------------

class Viewport3D(QOpenGLWidget):
    """OpenGL 3D viewport with orbit camera and transform gizmo."""

    layer_clicked = Signal(str)
    transform_changed = Signal()
    gizmo_drag_started = Signal()

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

        # mouse
        self._last_mouse = QPoint()
        self._mouse_button = Qt.MouseButton.NoButton
        self._press_pos = QPoint()

        # gizmo
        self._gizmo_mode = GIZMO_TRANSLATE
        self._gizmo_active_axis: int | None = None
        self._gizmo_drag_start: np.ndarray | None = None
        self._gizmo_layer_start: np.ndarray | None = None

        # cached matrices (updated each paintGL)
        self._cached_modelview: np.ndarray | None = None
        self._cached_projection: np.ndarray | None = None
        self._cached_viewport: np.ndarray | None = None

        # shader programs (compiled in initializeGL)
        self._mesh_shader: ShaderProgram | None = None
        self._bg_shader: ShaderProgram | None = None
        self._flat_shader: ShaderProgram | None = None
        self._pick_shader: ShaderProgram | None = None

        # VAOs / VBOs
        self._bg_vao = 0
        self._bg_vbo = 0
        self._grid_vao = 0
        self._grid_vbo = 0

        # mesh VBO cache: layer_id -> (vao, index_count)
        self._mesh_vaos: dict[str, tuple[int, int]] = {}

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Matrix helpers
    # ------------------------------------------------------------------

    def _compute_projection(self, aspect: float) -> np.ndarray:
        return _perspective_matrix(45.0, aspect,
                                   max(0.1, self._zoom * 0.001), self._far_clip)

    def _compute_modelview(self) -> np.ndarray:
        mv = _translate_matrix(self._pan_x, self._pan_y, -self._zoom)
        mv = mv @ _rotate_x_matrix(self._rotation_x)
        mv = mv @ _rotate_z_matrix(self._rotation_y)
        return mv

    def _compute_mvp(self, aspect: float) -> np.ndarray:
        return self._compute_projection(aspect) @ self._compute_modelview()

    # ------------------------------------------------------------------
    # Set project / public API
    # ------------------------------------------------------------------

    def set_project(self, project: Project) -> None:
        self._project = project
        self._highlighted_layer = None
        self._mesh_vaos.clear()
        self.update()

    def refresh(self) -> None:
        self._mesh_vaos.clear()
        self.update()

    def fit_to_scene(self) -> None:
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

        self._zoom = max_dim * 1.8
        self._pan_x = -center[0]
        self._pan_y = -center[1]
        self._rotation_x = 30.0
        self._rotation_y = 45.0

        self._grid_size = max_dim * 1.2
        raw_step = max_dim / 10.0
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

        self._far_clip = max(10000.0, max_dim * 100)
        self.update()

    def highlight_layer(self, layer_id: str) -> None:
        self._highlighted_layer = layer_id
        self.update()

    def set_gizmo_mode(self, mode: int) -> None:
        self._gizmo_mode = mode
        self._gizmo_active_axis = None
        self.update()

    # ------------------------------------------------------------------
    # OpenGL initialization
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:
        from ..core.debug_log import log
        from OpenGL.GL import glGetString, GL_VERSION, GL_RENDERER
        gl_version = glGetString(GL_VERSION)
        gl_renderer = glGetString(GL_RENDERER)
        log(f"initializeGL — GL_VERSION: {gl_version}, GL_RENDERER: {gl_renderer}")
        glClearColor(0.18, 0.18, 0.22, 1.0)
        glEnable(GL_DEPTH_TEST)

        try:
            self._mesh_shader = ShaderProgram("mesh.vert", "mesh.frag")
        except Exception as e:
            log(f"mesh shader FAILED: {e}")
            self._mesh_shader = None
        try:
            self._bg_shader = ShaderProgram("background.vert", "background.frag")
        except Exception as e:
            log(f"bg shader FAILED: {e}")
            self._bg_shader = None
        try:
            self._flat_shader = ShaderProgram("flat.vert", "flat.frag")
        except Exception as e:
            log(f"flat shader FAILED: {e}")
            self._flat_shader = None
        try:
            self._pick_shader = ShaderProgram("pick.vert", "pick.frag")
        except Exception as e:
            log(f"pick shader FAILED: {e}")
            self._pick_shader = None

        # background quad
        if self._bg_shader:
            quad = np.array([-1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, 1], dtype=np.float32)
            self._bg_vao = glGenVertexArrays(1)
            self._bg_vbo = glGenBuffers(1)
            glBindVertexArray(self._bg_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._bg_vbo)
            glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
            glBindVertexArray(0)

    def resizeGL(self, w: int, h: int) -> None:
        glViewport(0, 0, w, h)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintGL(self) -> None:
        try:
            self._paintGL_impl()
        except Exception as e:
            from ..core.debug_log import log_exception
            log_exception("paintGL CRASHED", e)
    def _paintGL_impl(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return
        aspect = w / max(h, 1)

        projection = self._compute_projection(aspect)
        modelview = self._compute_modelview()
        mvp = projection @ modelview

        self._cached_modelview = modelview.copy()
        self._cached_projection = projection.copy()
        self._cached_viewport = np.array([0, 0, w, h], dtype=np.float64)

        self._draw_background()
        self._draw_grid(mvp)

        if self._mesh_shader:
            self._draw_meshes_shader(projection, modelview)
        elif self._flat_shader:
            self._draw_meshes_flat(mvp)

        if self._highlighted_layer:
            self._draw_gizmo(mvp, projection, modelview)

        self._draw_axes_indicator(w, h)

    # ------------------------------------------------------------------
    # Background gradient
    # ------------------------------------------------------------------

    def _draw_background(self) -> None:
        if not self._bg_shader:
            return
        glDisable(GL_DEPTH_TEST)
        self._bg_shader.use()
        self._bg_shader.set_vec3("uColorTop", 0.22, 0.22, 0.28)
        self._bg_shader.set_vec3("uColorBottom", 0.10, 0.10, 0.13)
        glBindVertexArray(self._bg_vao)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    # ------------------------------------------------------------------
    # Grid (flat shader)
    # ------------------------------------------------------------------

    def _draw_grid(self, mvp: np.ndarray) -> None:
        if not self._flat_shader:
            return

        size = self._grid_size
        step = self._grid_step
        verts = []

        n = int(size / step)
        for i in range(-n, n + 1):
            x = i * step
            verts.extend([(x, -size, 0, 0.3, 0.3, 0.3),
                          (x, size, 0, 0.3, 0.3, 0.3)])
        for i in range(-n, n + 1):
            y = i * step
            verts.extend([(-size, y, 0, 0.3, 0.3, 0.3),
                          ( size, y, 0, 0.3, 0.3, 0.3)])

        if not verts:
            return

        data = np.array(verts, dtype=np.float32)
        if self._grid_vao == 0:
            self._grid_vao = glGenVertexArrays(1)
            self._grid_vbo = glGenBuffers(1)
        glBindVertexArray(self._grid_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._grid_vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)
        stride = 6 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, False, stride, ctypes.c_void_p(12))
        glBindVertexArray(0)

        self._flat_shader.use()
        self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
        glBindVertexArray(self._grid_vao)
        glDrawArrays(GL_LINES, 0, len(verts))
        glBindVertexArray(0)

    # ------------------------------------------------------------------
    # Meshes — PBR shader
    # ------------------------------------------------------------------

    def _draw_meshes_shader(self, projection: np.ndarray, modelview: np.ndarray) -> None:
        mv3 = modelview[:3, :3].copy()
        try:
            normal_mat = np.linalg.inv(mv3).T.astype(np.float32)
        except np.linalg.LinAlgError:
            normal_mat = np.eye(3, dtype=np.float32)

        self._mesh_shader.use()
        self._mesh_shader.set_mat4("uModel", np.eye(4, dtype=np.float32))
        self._mesh_shader.set_mat4("uView", modelview.astype(np.float32))
        self._mesh_shader.set_mat4("uProjection", projection.astype(np.float32))
        self._mesh_shader.set_mat3("uNormalMatrix", normal_mat)

        self._mesh_shader.set_int("uNumLights", 3)
        self._mesh_shader.set_light(0, (0.6, -0.8, 0.5), (1.0, 1.0, 1.0), 1.4)
        self._mesh_shader.set_light(1, (-0.5, 0.3, -0.7), (0.6, 0.7, 0.9), 0.5)
        self._mesh_shader.set_light(2, (0.0, 0.0, -1.0), (0.8, 0.8, 1.0), 0.3)
        self._mesh_shader.set_vec3("uAmbientColor", 0.15, 0.15, 0.18)
        self._mesh_shader.set_float("uAmbientIntensity", 1.0)
        self._mesh_shader.set_float("uRoughness", 0.55)
        self._mesh_shader.set_float("uMetalness", 0.05)

        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue
            part = layer.extruded_part
            if len(part.faces) == 0:
                continue

            is_highlighted = (layer.svg_layer.id == self._highlighted_layer)
            r, g, b = part.color
            if is_highlighted:
                self._mesh_shader.set_vec3("uBaseColor", r / 255 * 1.3, g / 255 * 1.3, b / 255 * 1.3)
            else:
                self._mesh_shader.set_vec3("uBaseColor", r / 255, g / 255, b / 255)

            self._draw_mesh_vbo(layer.svg_layer.id, part.vertices, part.faces, part.normals)

    def _draw_mesh_vbo(self, layer_id: str, verts: np.ndarray,
                       faces: np.ndarray, normals: np.ndarray | None = None) -> None:
        if len(faces) == 0:
            return
        if normals is None:
            normals = compute_normals(verts, faces)

        if layer_id not in self._mesh_vaos:
            vao = glGenVertexArrays(1)
            pos_vbo = glGenBuffers(1)
            norm_vbo = glGenBuffers(1)
            ebo = glGenBuffers(1)

            glBindVertexArray(vao)

            glBindBuffer(GL_ARRAY_BUFFER, pos_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.astype(np.float32).nbytes,
                         verts.astype(np.float32), GL_STATIC_DRAW)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, False, 0, None)

            glBindBuffer(GL_ARRAY_BUFFER, norm_vbo)
            glBufferData(GL_ARRAY_BUFFER, normals.astype(np.float32).nbytes,
                         normals.astype(np.float32), GL_STATIC_DRAW)
            glEnableVertexAttribArray(1)
            glVertexAttribPointer(1, 3, GL_FLOAT, False, 0, None)

            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, faces.astype(np.uint32).nbytes,
                         faces.astype(np.uint32), GL_STATIC_DRAW)

            glBindVertexArray(0)
            self._mesh_vaos[layer_id] = (vao, len(faces) * 3)

        vao, index_count = self._mesh_vaos[layer_id]
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, index_count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def _draw_meshes_flat(self, mvp: np.ndarray) -> None:
        """Fallback: render meshes with flat shader (no lighting)."""
        if not self._flat_shader:
            return
        self._flat_shader.use()
        self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue
            part = layer.extruded_part
            if len(part.faces) == 0:
                continue
            r, g, b = part.color
            flat_verts = []
            for tri in part.faces:
                for idx in tri:
                    flat_verts.extend(part.vertices[idx].tolist())
                    flat_verts.extend([r / 255, g / 255, b / 255])
            if flat_verts:
                vao, vbo, count = _upload_flat_vbo(flat_verts)
                glBindVertexArray(vao)
                glDrawArrays(GL_TRIANGLES, 0, count)
                glBindVertexArray(0)
                _free_flat_vbo(vao, vbo)

    # ------------------------------------------------------------------
    # Axes indicator (flat shader, ortho overlay)
    # ------------------------------------------------------------------

    def _draw_axes_indicator(self, w: int, h: int) -> None:
        if not self._flat_shader:
            return

        size = min(80, w // 6, h // 6)
        margin = 16

        rotation_mv = _translate_matrix(margin + size // 2, margin + size // 2, 0)
        rotation_mv = rotation_mv @ _rotate_x_matrix(self._rotation_x)
        rotation_mv = rotation_mv @ _rotate_z_matrix(self._rotation_y)
        ortho = _ortho_matrix(0, w, 0, h, -1, 1)
        mvp = ortho @ rotation_mv

        half = size / 2.0
        verts = []
        for axis, color in [(0, (1.0, 0.3, 0.3)), (1, (0.3, 1.0, 0.3)), (2, (0.3, 0.3, 1.0))]:
            end = [0.0, 0.0, 0.0]
            end[axis] = half
            verts.extend([(0, 0, 0, *color), (*end, *color)])

        vao, vbo, count = _upload_flat_vbo(verts)

        glDisable(GL_DEPTH_TEST)
        self._flat_shader.use()
        self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
        glBindVertexArray(vao)
        glDrawArrays(GL_LINES, 0, count)
        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

        _free_flat_vbo(vao, vbo)

    # ------------------------------------------------------------------
    # Gizmo (flat shader)
    # ------------------------------------------------------------------

    def _get_gizmo_position(self) -> np.ndarray | None:
        if not self._highlighted_layer:
            return None
        layer = self._project.get_layer_by_id(self._highlighted_layer)
        if not layer or layer.extruded_part is None:
            return None
        part = layer.extruded_part
        if len(part.vertices) == 0:
            return None
        return (part.vertices.min(axis=0) + part.vertices.max(axis=0)) / 2.0

    def _gizmo_scale(self) -> float:
        all_verts = []
        for layer in self._project.layers:
            if layer.effective_visible and layer.extruded_part and len(layer.extruded_part.vertices) > 0:
                all_verts.append(layer.extruded_part.vertices)
        if all_verts:
            combined = np.vstack(all_verts)
            model_size = float(max(combined.max(axis=0) - combined.min(axis=0)))
        else:
            model_size = 50.0
        return max(model_size * 0.03, 0.5)

    def _draw_gizmo(self, mvp: np.ndarray, projection: np.ndarray, modelview: np.ndarray) -> None:
        pos = self._get_gizmo_position()
        if pos is None or not self._flat_shader:
            return

        scale = self._gizmo_scale()
        model = _translate_matrix(*pos) @ _scale_matrix(scale, scale, scale)
        gizmo_mvp = projection @ modelview @ model

        if self._gizmo_mode == GIZMO_TRANSLATE:
            self._draw_translate_gizmo(gizmo_mvp)
        elif self._gizmo_mode == GIZMO_ROTATE:
            self._draw_rotate_gizmo(gizmo_mvp)
        elif self._gizmo_mode == GIZMO_SCALE:
            self._draw_scale_gizmo(gizmo_mvp)

    def _draw_axis_arrows(self, mvp: np.ndarray, length: float = 5.0) -> None:
        verts = []
        for axis, color in [(0, (1.0, 0.3, 0.3)), (1, (0.3, 1.0, 0.3)), (2, (0.3, 0.3, 1.0))]:
            is_active = self._gizmo_active_axis == axis
            r, g, b = color
            if is_active:
                r, g, b = min(1.0, r + 0.3), min(1.0, g + 0.3), min(1.0, b + 0.3)

            end = [0.0, 0.0, 0.0]
            end[axis] = length
            verts.extend([(0, 0, 0, r, g, b), (*end, r, g, b)])

            # arrowhead
            tip = end[:]
            if axis == 0:
                p1 = (tip[0] - 1.5, tip[1] + 0.8, tip[2])
                p2 = (tip[0] - 1.5, tip[1] - 0.8, tip[2])
            elif axis == 1:
                p1 = (tip[0] + 0.8, tip[1] - 1.5, tip[2])
                p2 = (tip[0] - 0.8, tip[1] - 1.5, tip[2])
            else:
                p1 = (tip[0] + 0.8, tip[1], tip[2] - 1.5)
                p2 = (tip[0] - 0.8, tip[1], tip[2] - 1.5)
            verts.extend([(*tip, r, g, b), (*p1, r, g, b)])
            verts.extend([(*tip, r, g, b), (*p2, r, g, b)])

        if verts:
            vao, vbo, count = _upload_flat_vbo(verts)
            self._flat_shader.use()
            self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
            glBindVertexArray(vao)
            glDrawArrays(GL_LINES, 0, count)
            glBindVertexArray(0)
            _free_flat_vbo(vao, vbo)

    def _draw_translate_gizmo(self, mvp: np.ndarray) -> None:
        self._draw_axis_arrows(mvp)
        self._draw_sphere(mvp, radius=0.6, color=(1.0, 1.0, 1.0))

    def _draw_rotate_gizmo(self, mvp: np.ndarray) -> None:
        segments = 48
        radius = 4.0
        verts = []
        for axis, color in [(0, (1.0, 0.3, 0.3)), (1, (0.3, 1.0, 0.3)), (2, (0.3, 0.3, 1.0))]:
            is_active = self._gizmo_active_axis == axis
            r, g, b = color
            if is_active:
                r, g, b = min(1.0, r + 0.3), min(1.0, g + 0.3), min(1.0, b + 0.3)
            for i in range(segments):
                a1 = 2.0 * math.pi * i / segments
                a2 = 2.0 * math.pi * (i + 1) / segments
                if axis == 0:
                    p1 = (0, radius * math.cos(a1), radius * math.sin(a1))
                    p2 = (0, radius * math.cos(a2), radius * math.sin(a2))
                elif axis == 1:
                    p1 = (radius * math.cos(a1), 0, radius * math.sin(a1))
                    p2 = (radius * math.cos(a2), 0, radius * math.sin(a2))
                else:
                    p1 = (radius * math.cos(a1), radius * math.sin(a1), 0)
                    p2 = (radius * math.cos(a2), radius * math.sin(a2), 0)
                verts.extend([(*p1, r, g, b), (*p2, r, g, b)])

        if verts:
            vao, vbo, count = _upload_flat_vbo(verts)
            self._flat_shader.use()
            self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
            glBindVertexArray(vao)
            glDrawArrays(GL_LINES, 0, count)
            glBindVertexArray(0)
            _free_flat_vbo(vao, vbo)

    def _draw_scale_gizmo(self, mvp: np.ndarray) -> None:
        verts = []
        for axis, color in [(0, (1.0, 0.3, 0.3)), (1, (0.3, 1.0, 0.3)), (2, (0.3, 0.3, 1.0))]:
            is_active = self._gizmo_active_axis == axis
            r, g, b = color
            if is_active:
                r, g, b = min(1.0, r + 0.3), min(1.0, g + 0.3), min(1.0, b + 0.3)
            end = [0.0, 0.0, 0.0]
            end[axis] = 5.0
            verts.extend([(0, 0, 0, r, g, b), (*end, r, g, b)])
            # small cube at end (wireframe)
            s = 0.4
            cx, cy, cz = end
            edges = [
                (cx - s, cy - s, cz - s, cx + s, cy - s, cz - s),
                (cx + s, cy - s, cz - s, cx + s, cy + s, cz - s),
                (cx + s, cy + s, cz - s, cx - s, cy + s, cz - s),
                (cx - s, cy + s, cz - s, cx - s, cy - s, cz - s),
                (cx - s, cy - s, cz + s, cx + s, cy - s, cz + s),
                (cx + s, cy - s, cz + s, cx + s, cy + s, cz + s),
                (cx + s, cy + s, cz + s, cx - s, cy + s, cz + s),
                (cx - s, cy + s, cz + s, cx - s, cy - s, cz + s),
                (cx - s, cy - s, cz - s, cx - s, cy - s, cz + s),
                (cx + s, cy - s, cz - s, cx + s, cy - s, cz + s),
                (cx + s, cy + s, cz - s, cx + s, cy + s, cz + s),
                (cx - s, cy + s, cz - s, cx - s, cy + s, cz + s),
            ]
            for e in edges:
                verts.extend([(e[0], e[1], e[2], r, g, b), (e[3], e[4], e[5], r, g, b)])

        if verts:
            vao, vbo, count = _upload_flat_vbo(verts)
            self._flat_shader.use()
            self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
            glBindVertexArray(vao)
            glDrawArrays(GL_LINES, 0, count)
            glBindVertexArray(0)
            _free_flat_vbo(vao, vbo)

    def _draw_sphere(self, mvp: np.ndarray, radius: float,
                     color: tuple[float, float, float],
                     slices: int = 12, stacks: int = 12) -> None:
        r, g, b = color
        verts = []
        for i in range(stacks):
            phi1 = math.pi * i / stacks
            phi2 = math.pi * (i + 1) / stacks
            for j in range(slices):
                theta1 = 2 * math.pi * j / slices
                theta2 = 2 * math.pi * (j + 1) / slices
                for (p1, t1, p2, t2) in [
                    (phi1, theta1, phi1, theta2),
                    (phi1, theta1, phi2, theta1),
                ]:
                    x1 = radius * math.sin(p1) * math.cos(t1)
                    y1 = radius * math.sin(p1) * math.sin(t1)
                    z1 = radius * math.cos(p1)
                    x2 = radius * math.sin(p2) * math.cos(t2)
                    y2 = radius * math.sin(p2) * math.sin(t2)
                    z2 = radius * math.cos(p2)
                    verts.extend([
                        (x1, y1, z1, r, g, b),
                        (x2, y2, z2, r, g, b),
                    ])

        if verts:
            vao, vbo, count = _upload_flat_vbo(verts)
            self._flat_shader.use()
            self._flat_shader.set_mat4("uMVP", mvp.astype(np.float32))
            glBindVertexArray(vao)
            glDrawArrays(GL_LINES, 0, count)
            glBindVertexArray(0)
            _free_flat_vbo(vao, vbo)

    # ------------------------------------------------------------------
    # Gizmo hit testing
    # ------------------------------------------------------------------

    def _is_layer_locked(self, layer) -> bool:
        from ..models.project import LayerGroup, LayerState
        node = layer
        while node is not None:
            if isinstance(node, LayerState) and node.locked:
                return True
            if isinstance(node, LayerGroup) and node.locked:
                return True
            node = getattr(node, "_parent", None)
        return False

    def _gizmo_hit_test(self, pos: QPoint) -> int | None:
        if not self._highlighted_layer or self._cached_modelview is None:
            return None
        gizmo_pos = self._get_gizmo_position()
        if gizmo_pos is None:
            return None

        mv = self._cached_modelview
        proj = self._cached_projection
        vp = self._cached_viewport

        screen = _glu_project(gizmo_pos, mv, proj, vp)
        screen_x, screen_y = screen[0], screen[1]

        dx = pos.x() - screen_x
        dy = (self.height() - pos.y()) - screen_y
        dist_center = math.sqrt(dx * dx + dy * dy)

        scale = self._gizmo_scale()
        gizmo_screen_approx = (scale * 5.0 * self._zoom
                               / max(gizmo_pos[2] + self._zoom, 1.0)
                               * self.height() * 0.005)
        if dist_center > gizmo_screen_approx * 3.0:
            return None

        best_axis = None
        best_dist = 1e9
        for axis in range(3):
            end_world = gizmo_pos.copy()
            end_world[axis] += 5.0 * scale
            sx, sy, _sz = _glu_project(end_world, mv, proj, vp)
            adx = pos.x() - sx
            ady = (self.height() - pos.y()) - sy
            d = math.sqrt(adx * adx + ady * ady)
            if d < 40 and d < best_dist:
                best_dist = d
                best_axis = axis

        return best_axis

    def _screen_to_world(self, screen_pos: QPoint, z_plane: float = 0.0) -> np.ndarray:
        if self._cached_modelview is None:
            return np.zeros(3)

        mv = self._cached_modelview
        proj = self._cached_projection
        vp = self._cached_viewport

        x = screen_pos.x()
        y = self.height() - screen_pos.y()

        near_pt = _glu_unproject(np.array([x, y, 0.0]), mv, proj, vp)
        far_pt = _glu_unproject(np.array([x, y, 1.0]), mv, proj, vp)

        direction = far_pt - near_pt
        if abs(direction[2]) < 1e-8:
            return near_pt
        t = (z_plane - near_pt[2]) / direction[2]
        return near_pt + direction * t

    # ------------------------------------------------------------------
    # Gizmo drag handling
    # ------------------------------------------------------------------

    def _handle_gizmo_drag(self, pos: QPoint) -> None:
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

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse = event.position().toPoint()
        self._press_pos = event.position().toPoint()
        self._mouse_button = event.button()

        if event.button() == Qt.MouseButton.LeftButton and self._highlighted_layer:
            layer = self._project.get_layer_by_id(self._highlighted_layer)
            if layer and self._is_layer_locked(layer):
                event.ignore()
                return
            axis = self._gizmo_hit_test(self._press_pos)
            if axis is not None:
                self._gizmo_active_axis = axis
                gizmo_pos = self._get_gizmo_position()
                if gizmo_pos is not None:
                    self._gizmo_drag_start = self._screen_to_world(self._press_pos, gizmo_pos[2])
                    if layer:
                        self._gizmo_layer_start = np.array([
                            layer.extrusion_params.translate_x,
                            layer.extrusion_params.translate_y,
                            layer.extrusion_params.scale_x if self._gizmo_mode == GIZMO_SCALE else 0.0,
                            layer.extrusion_params.scale_y if self._gizmo_mode == GIZMO_SCALE else 0.0,
                        ])
                self.gizmo_drag_started.emit()
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

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        self._zoom *= 1.0 - delta * 0.001
        self._zoom = max(1, min(5000, self._zoom))
        self.update()

    # ------------------------------------------------------------------
    # Color picking
    # ------------------------------------------------------------------

    def _draw_pick_pass(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        w, h = self.width(), self.height()
        aspect = w / max(h, 1)
        projection = self._compute_projection(aspect)
        modelview = self._compute_modelview()
        mvp = projection @ modelview

        if not self._pick_shader:
            return

        self._pick_shader.use()
        self._pick_shader.set_mat4("uMVP", mvp.astype(np.float32))

        idx = 0
        for layer in self._project.layers:
            if not layer.effective_visible or layer.extruded_part is None:
                continue
            part = layer.extruded_part
            if len(part.faces) == 0:
                continue

            r, g, b = _index_to_pick_color(idx)
            self._pick_shader.set_vec3("uPickColor", r, g, b)

            self._draw_pick_mesh(part.vertices, part.faces)
            idx += 1

    def _draw_pick_mesh(self, verts: np.ndarray, faces: np.ndarray) -> None:
        if len(faces) == 0:
            return

        vao = glGenVertexArrays(1)
        pos_vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)

        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, pos_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.astype(np.float32).nbytes,
                     verts.astype(np.float32), GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, 0, None)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, faces.astype(np.uint32).nbytes,
                     faces.astype(np.uint32), GL_STATIC_DRAW)
        glBindVertexArray(0)

        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, len(faces) * 3, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

        glDeleteVertexArrays(1, [vao])
        glDeleteBuffers(1, [pos_vbo])
        glDeleteBuffers(1, [ebo])

    def _pick_layer(self, pos: QPoint) -> None:
        self.makeCurrent()
        self._draw_pick_pass()

        x = pos.x()
        y = self.height() - pos.y() - 1
        pixel = glReadPixels(x, y, 1, 1, GL_RGB, GL_UNSIGNED_BYTE)
        r, g, b = pixel[0], pixel[1], pixel[2]

        self.doneCurrent()

        idx = _pick_color_to_index(r, g, b)

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

        self.layer_clicked.emit("")
