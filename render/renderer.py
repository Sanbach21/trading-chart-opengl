"""
Renderer 2D en pixeles (OpenGL 3.3 core).

A partir de ahora el Chart Engine trabajará en coordenadas de "app":
- x, y, w, h en PIXELES.

El renderer se encarga de:
- Convertir pixeles → NDC en el vertex shader usando uResolution.
- Batch simple por frame para líneas y rectángulos.
- Mantener el pipeline moderno (VAO/VBO + shaders).

IMPORTANTE:
- Este renderer NO sabe nada de trading, velas, escalas, etc.
- Solo dibuja primitivas 2D.
"""
from __future__ import annotations
import ctypes

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_DYNAMIC_DRAW,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_LINE_SMOOTH,
    GL_LINES,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_TRIANGLES,
    GL_VERTEX_SHADER,
    glBindBuffer,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glBufferSubData,
    glDeleteBuffers,
    glDeleteProgram,
    glDeleteVertexArrays,
    glDrawArrays,
    glEnable,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenVertexArrays,
    glGetUniformLocation,
    glLineWidth,
    glUseProgram,
    glUniform2f,
    glVertexAttribPointer,
)
from render.gl_utils import compile_shader, link_program


@dataclass(frozen=True)
class Color:
    """Color RGBA (0..1)."""
    r: float
    g: float
    b: float
    a: float = 1.0


class Renderer2D:
    """
    Renderer 2D por batches (mínimo pero sólido).

    Flujo recomendado por frame:
        renderer.begin_frame(width, height)
        renderer.draw_line_px(...)
        renderer.draw_rect_px(...)
        renderer.end_frame()

    Nota:
    - begin_frame limpia las listas internas de geometría.
    - end_frame sube todo al GPU y dibuja en 1-2 draw calls.
    """

    def __init__(self) -> None:
        # GL objects
        self._program: int | None = None
        self._vao: int | None = None
        self._vbo: int | None = None

        # Uniform location
        self._u_resolution: int | None = None

        # Frame state
        self._width: int = 1
        self._height: int = 1

        # Batches (listas de vértices)
        # Cada vértice: (x_px, y_px, r, g, b, a) => 6 floats
        self._line_verts: List[float] = []
        self._tri_verts: List[float] = []

    # -------------------------
    # Lifecycle
    # -------------------------
    def init(self) -> None:
        """
        Inicializa shaders y buffers.

        Se llama una sola vez luego de crear el contexto OpenGL.
        """
        vert_path = Path("render/shaders/basic2d.vert")
        frag_path = Path("render/shaders/basic2d.frag")

        vertex_src = vert_path.read_text(encoding="utf-8")
        fragment_src = frag_path.read_text(encoding="utf-8")

        vs = compile_shader(GL_VERTEX_SHADER, vertex_src)
        fs = compile_shader(GL_FRAGMENT_SHADER, fragment_src)
        self._program = link_program(vs, fs)

        self._u_resolution = glGetUniformLocation(self._program, "uResolution")

        # VAO/VBO únicos (reusamos para líneas y triángulos cambiando datos)
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        # Reservamos un buffer inicial (se ajusta dinámicamente si hace falta)
        glBufferData(GL_ARRAY_BUFFER, 1024 * 6 * 4, None, GL_DYNAMIC_DRAW)

        # layout(location=0) vec2 aPosPx
        glEnableVertexAttribArray(0)
        stride = 6 * 4  # 6 floats * 4 bytes
        glVertexAttribPointer(0, 2, GL_FLOAT, False, stride, ctypes.c_void_p(0))   # pos: offset 0

        # layout(location=1) vec4 aColor
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 4, GL_FLOAT, False, stride, ctypes.c_void_p(8))   # color: offset 2 floats = 8 bytes

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        # Estado útil 2D
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def shutdown(self) -> None:
        """Libera recursos GL."""
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
        """
        Inicia el frame.

        - Guarda resolución actual (para uResolution).
        - Limpia batches de geometría.
        """
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._line_verts.clear()
        self._tri_verts.clear()

    def end_frame(self) -> None:
        """
        Finaliza el frame: sube batches al GPU y dibuja.

        Para mantenerlo simple:
        - Primero dibujamos triángulos (rects)
        - Luego líneas
        """
        assert self._program is not None and self._vao is not None and self._vbo is not None
        assert self._u_resolution is not None

        glUseProgram(self._program)
        glUniform2f(self._u_resolution, float(self._width), float(self._height))
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        # Rects (triangles)
        if self._tri_verts:
            tri_arr = np.array(self._tri_verts, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, tri_arr.nbytes, tri_arr, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_TRIANGLES, 0, len(tri_arr) // 6)

        # Lines
        if self._line_verts:
            line_arr = np.array(self._line_verts, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, line_arr.nbytes, line_arr, GL_DYNAMIC_DRAW)
            glLineWidth(1.0)
            glDrawArrays(GL_LINES, 0, len(line_arr) // 6)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        glUseProgram(0)

    # -------------------------
    # Primitives
    # -------------------------
    def draw_line_px(self, x1: float, y1: float, x2: float, y2: float, color: Color) -> None:
        """
        Encola una línea en coordenadas pixel.

        Nota:
        - El origen (0,0) es arriba-izquierda (UI style).
        """
        self._push_vertex(self._line_verts, x1, y1, color)
        self._push_vertex(self._line_verts, x2, y2, color)

    def draw_rect_px(self, x: float, y: float, w: float, h: float, color: Color) -> None:
        """
        Encola un rectángulo relleno usando 2 triángulos.

        (x,y) es la esquina superior-izquierda.
        """
        x2 = x + w
        y2 = y + h

        # Tri 1: (x,y) (x2,y) (x2,y2)
        self._push_vertex(self._tri_verts, x,  y,  color)
        self._push_vertex(self._tri_verts, x2, y,  color)
        self._push_vertex(self._tri_verts, x2, y2, color)

        # Tri 2: (x,y) (x2,y2) (x,y2)
        self._push_vertex(self._tri_verts, x,  y,  color)
        self._push_vertex(self._tri_verts, x2, y2, color)
        self._push_vertex(self._tri_verts, x,  y2, color)

    # -------------------------
    # Internal helpers
    # -------------------------
    @staticmethod
    def _push_vertex(buf: List[float], x: float, y: float, c: Color) -> None:
        """Agrega un vértice al buffer destino."""
        buf.extend([float(x), float(y), float(c.r), float(c.g), float(c.b), float(c.a)])
