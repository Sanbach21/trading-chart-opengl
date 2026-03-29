from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any, List

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_DYNAMIC_DRAW, GL_FALSE, GL_FLOAT,
    GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, GL_TRIANGLES, GL_LINES,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
    glBindBuffer, glBindVertexArray, glBlendFunc, glBufferData,
    glDeleteBuffers, glDeleteProgram, glDeleteVertexArrays,
    glDrawArrays, glEnable, glEnableVertexAttribArray,
    glGenBuffers, glGenVertexArrays, glGetUniformLocation,
    glUniform2f, glUseProgram, glVertexAttribPointer,
)

from render.gl_utils import compile_shader, link_program


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0


class Renderer2D:
    """
    Renderer 2D optimizado con batches separados.
    """

    def __init__(self) -> None:
        self._program: int | None = None
        self._vao: int | None = None
        self._vbo: int | None = None
        self._u_resolution: int | None = None

        self._width = 1
        self._height = 1

        # Batches separados para mejor performance
        self._tri_verts: List[float] = []   # Rects y cuerpos de velas
        self._line_verts: List[float] = []  # Wicks, grids, crosshair, etc.

    def init(self) -> None:
        """Inicializa shaders y buffers."""
        vert_path = "render/shaders/basic2d.vert"
        frag_path = "render/shaders/basic2d.frag"

        with open(vert_path, "r", encoding="utf-8") as f:
            vertex_src = f.read()
        with open(frag_path, "r", encoding="utf-8") as f:
            fragment_src = f.read()

        vs = compile_shader(GL_VERTEX_SHADER, vertex_src)
        fs = compile_shader(GL_FRAGMENT_SHADER, fragment_src)
        self._program = link_program(vs, fs)

        self._u_resolution = glGetUniformLocation(self._program, "uResolution")

        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        # Reservamos memoria inicial grande
        glBufferData(GL_ARRAY_BUFFER, 1024 * 1024 * 6 * 4, None, GL_DYNAMIC_DRAW)

        stride = 6 * 4  # x, y, r, g, b, a

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))

        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def shutdown(self) -> None:
        if self._program:
            glDeleteProgram(self._program)
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
        if self._vao:
            glDeleteVertexArrays(1, [self._vao])

    def begin_frame(self, width: int, height: int) -> None:
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._tri_verts.clear()
        self._line_verts.clear()

    def end_frame(self) -> None:
        self.flush()

    # ====================== PRIMITIVAS ======================

    @staticmethod
    def _to_color(c: Any) -> Color:
        if isinstance(c, Color):
            return c
        if isinstance(c, (tuple, list)):
            r, g, b = map(float, c[:3])
            a = float(c[3]) if len(c) >= 4 else 1.0
            return Color(r, g, b, a)
        return Color(1.0, 1.0, 1.0, 1.0)

    @staticmethod
    def _push_vertex(buf: List[float], x: float, y: float, col: Color):
        buf.extend((float(x), float(y), col.r, col.g, col.b, col.a))

    def draw_rect_px(self, x: float, y: float, w: float, h: float, color: Any):
        """Dibuja rectángulo relleno (usado por velas y fondos)"""
        col = self._to_color(color)
        x2, y2 = x + w, y + h

        self._push_vertex(self._tri_verts, x, y, col)
        self._push_vertex(self._tri_verts, x2, y, col)
        self._push_vertex(self._tri_verts, x2, y2, col)

        self._push_vertex(self._tri_verts, x, y, col)
        self._push_vertex(self._tri_verts, x2, y2, col)
        self._push_vertex(self._tri_verts, x, y2, col)

    def draw_line_px(self, x1: float, y1: float, x2: float, y2: float, color: Any, width: float = 1.0):
        """Línea con grosor (mejorado)"""
        col = self._to_color(color)
        w = max(1.0, float(width))

        # Optimización: líneas horizontales y verticales como rects
        if abs(y2 - y1) < 0.5:   # horizontal
            y_top = y1 - (w - 1.0) * 0.5
            self.draw_rect_px(min(x1, x2), y_top, abs(x2 - x1), w, col)
            return

        if abs(x2 - x1) < 0.5:   # vertical
            x_left = x1 - (w - 1.0) * 0.5
            self.draw_rect_px(x_left, min(y1, y2), w, abs(y2 - y1), col)
            return

        # Diagonal → quad
        self._push_thick_line(x1, y1, x2, y2, w, col)

    def _push_thick_line(self, x1, y1, x2, y2, width: float, col: Color):
        import math
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 0.001:
            return

        nx = -dy / length
        ny = dx / length
        half = (width - 1.0) * 0.5

        x1a = x1 - nx * half
        y1a = y1 - ny * half
        x1b = x1 + nx * half
        y1b = y1 + ny * half
        x2a = x2 - nx * half
        y2a = y2 - ny * half
        x2b = x2 + nx * half
        y2b = y2 + ny * half

        self._push_vertex(self._tri_verts, x1a, y1a, col)
        self._push_vertex(self._tri_verts, x1b, y1b, col)
        self._push_vertex(self._tri_verts, x2b, y2b, col)

        self._push_vertex(self._tri_verts, x1a, y1a, col)
        self._push_vertex(self._tri_verts, x2b, y2b, col)
        self._push_vertex(self._tri_verts, x2a, y2a, col)

    # ====================== FLUSH ======================

    def flush(self) -> None:
        if not self._tri_verts and not self._line_verts:
            return

        glUseProgram(self._program)
        glUniform2f(self._u_resolution, float(self._width), float(self._height))

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        if self._tri_verts:
            arr = np.array(self._tri_verts, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, arr.nbytes, arr, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_TRIANGLES, 0, len(self._tri_verts) // 6)

        if self._line_verts:
            arr = np.array(self._line_verts, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, arr.nbytes, arr, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_LINES, 0, len(self._line_verts) // 6)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        glUseProgram(0)

        self._tri_verts.clear()
        self._line_verts.clear()