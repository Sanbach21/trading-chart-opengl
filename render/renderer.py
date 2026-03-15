from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_DYNAMIC_DRAW,
    GL_FALSE,
    GL_FLOAT,
    GL_LINES,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_TRIANGLES,
    GL_VERTEX_SHADER,
    GL_FRAGMENT_SHADER,
    glBindBuffer,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glDeleteBuffers,
    glDeleteProgram,
    glDeleteVertexArrays,
    glDrawArrays,
    glEnable,
    glEnableVertexAttribArray,
    glGetUniformLocation,
    glUseProgram,
    glGenBuffers,
    glGenVertexArrays,
    glUniform2f,
    glVertexAttribPointer,
)

from render.gl_utils import compile_shader, link_program


@dataclass(frozen=True)
class Color:
    """Color RGBA en rango 0..1."""
    r: float
    g: float
    b: float
    a: float = 1.0


class Renderer2D:
    """
    Renderer 2D simple por batches.

    Flujo por frame:
        begin_frame(w, h)
        draw_line_px(...)
        draw_rect_px(...)
        end_frame()
    """

    def __init__(self) -> None:
        # Objetos OpenGL básicos
        self._program: int | None = None
        self._vao: int | None = None
        self._vbo: int | None = None
        self._u_resolution: int | None = None

        # Estado del frame
        self._width: int = 1
        self._height: int = 1

        # Batches: cada vértice = x, y, r, g, b, a
        self._line_verts: List[float] = []
        self._tri_verts: List[float] = []

    # -------------------------
    # Lifecycle
    # -------------------------
    def init(self) -> None:
        vert_path = Path("render/shaders/basic2d.vert")
        frag_path = Path("render/shaders/basic2d.frag")

        vertex_src = vert_path.read_text(encoding="utf-8")
        fragment_src = frag_path.read_text(encoding="utf-8")

        vs = compile_shader(GL_VERTEX_SHADER, vertex_src)
        fs = compile_shader(GL_FRAGMENT_SHADER, fragment_src)
        self._program = link_program(vs, fs)

        self._u_resolution = glGetUniformLocation(self._program, "uResolution")

        # VAO/VBO para aPosPx(vec2) + aColor(vec4) => 6 floats
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        glBufferData(GL_ARRAY_BUFFER, 1024 * 6 * 4, None, GL_DYNAMIC_DRAW)

        stride = 6 * 4

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))

        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def shutdown(self) -> None:
        if self._program is not None:
            glDeleteProgram(self._program)
            self._program = None

        if self._vbo is not None:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = None

        if self._vao is not None:
            glDeleteVertexArrays(1, [self._vao])
            self._vao = None

    # -------------------------
    # Frame API
    # -------------------------
    def begin_frame(self, width: int, height: int) -> None:
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._line_verts.clear()
        self._tri_verts.clear()

    def end_frame(self) -> None:
        self.flush()

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _to_color(c: Any) -> Color:
        if isinstance(c, Color):
            return c

        if isinstance(c, (tuple, list)) and 3 <= len(c) <= 4:
            r = float(c[0])
            g = float(c[1])
            b = float(c[2])
            a = float(c[3]) if len(c) == 4 else 1.0
            return Color(r, g, b, a)

        return Color(1.0, 1.0, 1.0, 1.0)

    @staticmethod
    def _push_vertex(buf: List[float], x: float, y: float, c: Color) -> None:
        buf.extend([float(x), float(y), float(c.r), float(c.g), float(c.b), float(c.a)])

    # -------------------------
    # Primitives
    # -------------------------
    def draw_line_px(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: Any,
        width: float = 1.0,
        **_,
    ) -> None:
        col = self._to_color(color)
        w = max(1.0, float(width))

        x1 = float(x1)
        y1 = float(y1)
        x2 = float(x2)
        y2 = float(y2)

        # Horizontal
        if abs(y2 - y1) < 1e-6:
            x_min, x_max = (x1, x2) if x1 <= x2 else (x2, x1)
            y_top = y1 - (w - 1.0) * 0.5
            self.draw_rect_px(x_min, y_top, x_max - x_min, w, col)
            return

        # Vertical
        if abs(x2 - x1) < 1e-6:
            y_min, y_max = (y1, y2) if y1 <= y2 else (y2, y1)
            x_left = x1 - (w - 1.0) * 0.5
            self.draw_rect_px(x_left, y_min, w, y_max - y_min, col)
            return

        # Diagonal
        self._push_quad_line(x1, y1, x2, y2, w, col)

    def draw_rect_px(self, x: float, y: float, w: float, h: float, color: Any, **_) -> None:
        col = self._to_color(color)

        x2 = x + w
        y2 = y + h

        self._push_vertex(self._tri_verts, x, y, col)
        self._push_vertex(self._tri_verts, x2, y, col)
        self._push_vertex(self._tri_verts, x2, y2, col)

        self._push_vertex(self._tri_verts, x, y, col)
        self._push_vertex(self._tri_verts, x2, y2, col)
        self._push_vertex(self._tri_verts, x, y2, col)

    def _push_quad_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width: float,
        col: Color,
    ) -> None:
        import math

        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)

        if length <= 0.0:
            return

        nx = -dy / length
        ny = dx / length
        half = (width - 1.0) * 0.5

        ox = nx * half
        oy = ny * half

        x1a, y1a = x1 - ox, y1 - oy
        x1b, y1b = x1 + ox, y1 + oy
        x2b, y2b = x2 + ox, y2 + oy
        x2a, y2a = x2 - ox, y2 - oy

        self._push_vertex(self._tri_verts, x1a, y1a, col)
        self._push_vertex(self._tri_verts, x1b, y1b, col)
        self._push_vertex(self._tri_verts, x2b, y2b, col)

        self._push_vertex(self._tri_verts, x1a, y1a, col)
        self._push_vertex(self._tri_verts, x2b, y2b, col)
        self._push_vertex(self._tri_verts, x2a, y2a, col)

    # -------------------------
    # Flush
    # -------------------------
    def flush(self) -> None:
        """Dibuja lo acumulado en los batches y luego los limpia."""
        if not self._tri_verts and not self._line_verts:
            return

        assert self._program is not None
        assert self._vao is not None
        assert self._vbo is not None
        assert self._u_resolution is not None

        glUseProgram(self._program)
        glUniform2f(self._u_resolution, float(self._width), float(self._height))

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        if self._tri_verts:
            tri_arr = np.array(self._tri_verts, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, tri_arr.nbytes, tri_arr, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_TRIANGLES, 0, len(tri_arr) // 6)

        if self._line_verts:
            line_arr = np.array(self._line_verts, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, line_arr.nbytes, line_arr, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_LINES, 0, len(line_arr) // 6)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        glUseProgram(0)

        self._tri_verts.clear()
        self._line_verts.clear()