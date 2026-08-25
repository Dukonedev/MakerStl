"""GLSL shader compilation, linking, and uniform management.

Provides a simple ShaderProgram class that compiles vertex + fragment
shaders, links them, and exposes typed uniform setters.
"""

from __future__ import annotations

from pathlib import Path

from OpenGL.GL import (
    glCreateProgram, glCreateShader, glShaderSource, glCompileShader,
    glGetShaderiv, glGetShaderInfoLog,
    glAttachShader, glLinkProgram, glGetProgramiv, glGetProgramInfoLog,
    glDeleteShader, glUseProgram,
    glGetUniformLocation, glUniform1f, glUniform3f, glUniform1i,
    glUniformMatrix3fv, glUniformMatrix4fv,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    GL_COMPILE_STATUS, GL_LINK_STATUS,
)


def _load_shader_source(filename: str) -> str:
    """Load GLSL source from the shaders/ package directory.

    Supports both source-tree and frozen (PyInstaller) layouts.
    """
    import sys
    base = Path(__file__).resolve().parent.parent
    # frozen bundle: shaders are next to the executable
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    shader_dir = base / "shaders"
    path = shader_dir / filename
    if not path.exists():
        # fallback: try source tree relative to this file
        shader_dir = Path(__file__).resolve().parent.parent / "shaders"
        path = shader_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Shader not found: {path}")
    return path.read_text(encoding="utf-8")


class ShaderProgram:
    """Compiles and links a vertex + fragment shader pair."""

    def __init__(self, vertex_file: str, fragment_file: str):
        self._program = 0
        self._uniform_cache: dict[str, int] = {}
        self._compile(vertex_file, fragment_file)

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    def _compile(self, vert_file: str, frag_file: str) -> None:
        vert_src = _load_shader_source(vert_file)
        frag_src = _load_shader_source(frag_file)

        vert_id = self._compile_shader(vert_src, GL_VERTEX_SHADER, vert_file)
        frag_id = self._compile_shader(frag_src, GL_FRAGMENT_SHADER, frag_file)

        self._program = glCreateProgram()
        glAttachShader(self._program, vert_id)
        glAttachShader(self._program, frag_id)
        glLinkProgram(self._program)

        if not glGetProgramiv(self._program, GL_LINK_STATUS):
            info = glGetProgramInfoLog(self._program).decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader link error ({vert_file}+{frag_file}):\n{info}")

        glDeleteShader(vert_id)
        glDeleteShader(frag_id)

    @staticmethod
    def _compile_shader(source: str, shader_type, label: str) -> int:
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)

        if not glGetShaderiv(shader, GL_COMPILE_STATUS):
            info = glGetShaderInfoLog(shader).decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader compile error ({label}):\n{info}")
        return shader

    # ------------------------------------------------------------------
    # Usage
    # ------------------------------------------------------------------

    def use(self) -> None:
        glUseProgram(self._program)

    @property
    def program_id(self) -> int:
        return self._program

    # ------------------------------------------------------------------
    # Uniform helpers
    # ------------------------------------------------------------------

    def _loc(self, name: str) -> int:
        if name not in self._uniform_cache:
            self._uniform_cache[name] = glGetUniformLocation(self._program, name)
        return self._uniform_cache[name]

    def set_float(self, name: str, value: float) -> None:
        glUniform1f(self._loc(name), value)

    def set_int(self, name: str, value: int) -> None:
        glUniform1i(self._loc(name), value)

    def set_vec3(self, name: str, x: float, y: float, z: float) -> None:
        glUniform3f(self._loc(name), x, y, z)

    def set_mat4(self, name: str, matrix, transpose: bool = True) -> None:
        glUniformMatrix4fv(self._loc(name), 1, transpose, matrix)

    def set_mat3(self, name: str, matrix, transpose: bool = True) -> None:
        glUniformMatrix3fv(self._loc(name), 1, transpose, matrix)

    def set_light(self, index: int, direction: tuple[float, float, float],
                  color: tuple[float, float, float], intensity: float) -> None:
        prefix = f"uLights[{index}]"
        self.set_vec3(f"{prefix}.direction", *direction)
        self.set_vec3(f"{prefix}.color", *color)
        self.set_float(f"{prefix}.intensity", intensity)
