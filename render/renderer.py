# render/renderer.py
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List

import numpy as np
from OpenGL.GL import (
    # --- basic pipeline ---
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_COMPILE_STATUS,
    GL_DYNAMIC_DRAW,
    GL_FALSE,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_LINES,
    GL_LINK_STATUS,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TRIANGLES,
    GL_VERTEX_SHADER,
    glActiveTexture,
    glAttachShader,
    glBindBuffer,
    glBindTexture,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glBufferSubData,
    glCompileShader,
    glCreateProgram,
    glCreateShader,
    glDeleteBuffers,
    glDeleteProgram,
    glDeleteShader,
    glDeleteVertexArrays,
    glDrawArrays,
    glEnable,
    glEnableVertexAttribArray,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    glGetUniformLocation,
    glLinkProgram,
    glShaderSource,
    glUniform1f,
    glUniform1i,
    glUniform2f,
    glUniform4f,
    glUseProgram,
    glGenBuffers,
    glGenVertexArrays,
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
    Renderer 2D por batches (mínimo pero sólido) + MSDF text.

    Flujo por frame:
        begin_frame(w,h)
        draw_line_px(...), draw_rect_px(...)
        (MSDF text puede dibujar en medio del frame)
        end_frame()
    """

    def __init__(self) -> None:
        # Basic GL objects
        self._program: int | None = None
        self._vao: int | None = None
        self._vbo: int | None = None
        self._u_resolution: int | None = None

        # Frame state
        self._width: int = 1
        self._height: int = 1

        # Batches: cada vértice = x, y, r, g, b, a
        self._line_verts: List[float] = []  # GL_LINES
        self._tri_verts: List[float] = []   # GL_TRIANGLES

        # MSDF pipeline
        self._msdf_prog: int | None = None
        self._msdf_vao: int | None = None
        self._msdf_vbo: int | None = None

        self._u_msdf_res: int | None = None
        self._u_msdf_tex: int | None = None
        self._u_msdf_color: int | None = None
        self._u_msdf_edge: int | None = None
        self._u_msdf_smooth: int | None = None

        self._msdf_active: bool = False
        self._msdf_tex_id: int = 0

    # -------------------------
    # Lifecycle
    # -------------------------
    def init(self) -> None:
        # Basic 2D shader
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

        # Blend
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # MSDF pipeline
        self._init_msdf_pipeline()

    def shutdown(self) -> None:
        # basic
        if self._program is not None:
            glDeleteProgram(self._program)
            self._program = None
        if self._vbo is not None:
            glDeleteBuffers(1, [self._vbo])
            self._vbo = None
        if self._vao is not None:
            glDeleteVertexArrays(1, [self._vao])
            self._vao = None

        # msdf
        if self._msdf_prog is not None:
            glDeleteProgram(self._msdf_prog)
            self._msdf_prog = None
        if self._msdf_vbo is not None:
            glDeleteBuffers(1, [self._msdf_vbo])
            self._msdf_vbo = None
        if self._msdf_vao is not None:
            glDeleteVertexArrays(1, [self._msdf_vao])
            self._msdf_vao = None

    # -------------------------
    # Frame API
    # -------------------------
    def begin_frame(self, width: int, height: int) -> None:
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._line_verts.clear()
        self._tri_verts.clear()

    def end_frame(self) -> None:
        # al final, dibujamos lo que quede en batch
        self.flush()

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _to_color(c: Any) -> Color:
        if isinstance(c, Color):
            return c
        if isinstance(c, (tuple, list)) and (3 <= len(c) <= 4):
            r = float(c[0]); g = float(c[1]); b = float(c[2])
            a = float(c[3]) if len(c) == 4 else 1.0
            return Color(r, g, b, a)
        return Color(1.0, 1.0, 1.0, 1.0)

    @staticmethod
    def _push_vertex(buf: List[float], x: float, y: float, c: Color) -> None:
        buf.extend([float(x), float(y), float(c.r), float(c.g), float(c.b), float(c.a)])

    # -------------------------
    # Primitives
    # -------------------------
    def draw_line_px(self, x1: float, y1: float, x2: float, y2: float,
                     color: Any, width: float = 1.0, **_) -> None:
        col = self._to_color(color)
        w = max(1.0, float(width))
        x1 = float(x1); y1 = float(y1); x2 = float(x2); y2 = float(y2)

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

        # Diagonal -> quad
        self._push_quad_line(x1, y1, x2, y2, w, col)

    def draw_rect_px(self, x: float, y: float, w: float, h: float, color: Any, **_) -> None:
        col = self._to_color(color)
        x2 = x + w
        y2 = y + h

        self._push_vertex(self._tri_verts, x,  y,  col)
        self._push_vertex(self._tri_verts, x2, y,  col)
        self._push_vertex(self._tri_verts, x2, y2, col)

        self._push_vertex(self._tri_verts, x,  y,  col)
        self._push_vertex(self._tri_verts, x2, y2, col)
        self._push_vertex(self._tri_verts, x,  y2, col)

    def _push_quad_line(self, x1: float, y1: float, x2: float, y2: float,
                        width: float, col: Color) -> None:
        import math
        dx = x2 - x1
        dy = y2 - y1
        L = math.hypot(dx, dy)
        if L <= 0.0:
            return

        nx = -dy / L
        ny = dx / L
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
    # Flush (IMPORTANT)
    # -------------------------
    def flush(self) -> None:
        """Dibuja lo acumulado en _tri_verts/_line_verts y limpia los buffers."""
        if not self._tri_verts and not self._line_verts:
            return

        assert self._program is not None and self._vao is not None and self._vbo is not None
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

    # -------------------------------------------------
    # MSDF TEXT
    # -------------------------------------------------
    def _compile_shader_msdf(self, shader_type, src: str) -> int:
        sid = glCreateShader(shader_type)
        glShaderSource(sid, src)
        glCompileShader(sid)

        ok = glGetShaderiv(sid, GL_COMPILE_STATUS)
        if not ok:
            err = glGetShaderInfoLog(sid).decode("utf-8", "ignore")
            glDeleteShader(sid)
            raise RuntimeError(f"MSDF shader compile error:\n{err}")
        return sid

    def _link_program_msdf(self, vs_src: str, fs_src: str) -> int:
        vs = self._compile_shader_msdf(GL_VERTEX_SHADER, vs_src)
        fs = self._compile_shader_msdf(GL_FRAGMENT_SHADER, fs_src)

        pid = glCreateProgram()
        glAttachShader(pid, vs)
        glAttachShader(pid, fs)
        glLinkProgram(pid)

        ok = glGetProgramiv(pid, GL_LINK_STATUS)
        glDeleteShader(vs)
        glDeleteShader(fs)

        if not ok:
            err = glGetProgramInfoLog(pid).decode("utf-8", "ignore")
            glDeleteProgram(pid)
            raise RuntimeError(f"MSDF program link error:\n{err}")
        return pid

    def _init_msdf_pipeline(self) -> None:
        vs_src = r"""
        #version 330 core
        layout(location=0) in vec2 aPosPx;
        layout(location=1) in vec2 aUV;

        uniform vec2 uResolution;
        out vec2 vUV;

        void main() {
            float x = (aPosPx.x / uResolution.x) * 2.0 - 1.0;
            float y = 1.0 - (aPosPx.y / uResolution.y) * 2.0;
            gl_Position = vec4(x, y, 0.0, 1.0);
            vUV = aUV;
        }
        """

        fs_src = r"""
        #version 330 core
        in vec2 vUV;
        out vec4 FragColor;

        uniform sampler2D uTex;
        uniform vec4 uColor;
        uniform float uEdge;
        uniform float uSmoothing;

        float median(float r, float g, float b) {
            return max(min(r, g), min(max(r, g), b));
        }

        void main() {
            vec3 smp = texture(uTex, vUV).rgb;
            float sd = median(smp.r, smp.g, smp.b);
            float alpha = smoothstep(uEdge - uSmoothing, uEdge + uSmoothing, sd);
            FragColor = vec4(uColor.rgb, uColor.a * alpha);
        }
        """

        self._msdf_prog = self._link_program_msdf(vs_src, fs_src)

        self._u_msdf_res = glGetUniformLocation(self._msdf_prog, "uResolution")
        self._u_msdf_tex = glGetUniformLocation(self._msdf_prog, "uTex")
        self._u_msdf_color = glGetUniformLocation(self._msdf_prog, "uColor")
        self._u_msdf_edge = glGetUniformLocation(self._msdf_prog, "uEdge")
        self._u_msdf_smooth = glGetUniformLocation(self._msdf_prog, "uSmoothing")

        self._msdf_vao = glGenVertexArrays(1)
        self._msdf_vbo = glGenBuffers(1)

        glBindVertexArray(self._msdf_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._msdf_vbo)

        glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)

        stride = 4 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(8))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def begin_msdf_text(self, texture_id: int, edge: float, smoothing: float, color: Any) -> None:
        """
        IMPORTANT:
        - Flushea el batch 2D antes de dibujar texto, así el texto NO queda tapado.
        """
        if self._msdf_prog is None or self._msdf_vao is None:
            return

        # 🔥 clave para que se vean los números
        self.flush()

        self._msdf_active = True
        self._msdf_tex_id = int(texture_id)

        glUseProgram(self._msdf_prog)

        assert self._u_msdf_res is not None
        assert self._u_msdf_edge is not None
        assert self._u_msdf_smooth is not None
        assert self._u_msdf_color is not None
        assert self._u_msdf_tex is not None

        glUniform2f(self._u_msdf_res, float(self._width), float(self._height))
        glUniform1f(self._u_msdf_edge, float(edge))
        glUniform1f(self._u_msdf_smooth, float(smoothing))

        col = self._to_color(color)
        glUniform4f(self._u_msdf_color, col.r, col.g, col.b, col.a)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self._msdf_tex_id)
        glUniform1i(self._u_msdf_tex, 0)

        glBindVertexArray(self._msdf_vao)

    def draw_textured_quad_px(self, x: float, y: float, w: float, h: float,
                              u0: float, v0: float, u1: float, v1: float) -> None:
        if not self._msdf_active or self._msdf_vbo is None or self._msdf_vao is None:
            return

        # seguridad: aseguramos VAO correcto
        glBindVertexArray(self._msdf_vao)

        x = float(x); y = float(y); w = float(w); h = float(h)
        u0 = float(u0); v0 = float(v0); u1 = float(u1); v1 = float(v1)

        verts = (ctypes.c_float * (6 * 4))(
            x,     y,     u0, v0,
            x + w, y,     u1, v0,
            x + w, y + h, u1, v1,

            x,     y,     u0, v0,
            x + w, y + h, u1, v1,
            x,     y + h, u0, v1,
        )

        glBindBuffer(GL_ARRAY_BUFFER, self._msdf_vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, ctypes.sizeof(verts), verts)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

        glDrawArrays(GL_TRIANGLES, 0, 6)

    def end_msdf_text(self) -> None:
        if not self._msdf_active:
            return
        self._msdf_active = False
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)