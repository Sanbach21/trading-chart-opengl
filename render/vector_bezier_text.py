# render/vector_bezier_text.py
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_DYNAMIC_DRAW, GL_FLOAT, GL_TRIANGLES,
    glBindBuffer, glBindVertexArray, glBufferData, glBufferSubData,
    glDrawArrays, glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glUniform1f, glUniform1i, glUniform2f, glUniform4f,
    glUniform4fv, glUseProgram, glVertexAttribPointer,
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER,
)

from render.gl_utils import compile_shader, link_program


# ------------------------------------------------------------
# Style
# ------------------------------------------------------------

@dataclass
class VectorTextStyle:
    size_px: float = 32.0
    color: tuple[float, float, float, float] = (0.95, 0.95, 1.0, 1.0)
    stroke_px: float = 2.4
    aa_px: float = 1.25
    letter_spacing_px: float = 2.0
    line_height: float = 1.2


# ------------------------------------------------------------
# Renderer
# ------------------------------------------------------------

class VectorBezierTextRenderer:
    """
    Render de texto vectorial por curvas cuadráticas Bézier (TTF) en shader.
    Dibuja un quad por glyph y en fragment decide fill + AA usando las curvas.
    """

    MAX_CURVES = 64

    def __init__(self) -> None:
        self._program: Optional[int] = None
        self._vao: Optional[int] = None
        self._vbo: Optional[int] = None

        # Uniform locations
        self._uResolution = -1
        self._uColor = -1
        self._uGlyphPx = -1
        self._uAAPx = -1
        self._uCurveCount = -1
        self._uCurvesA = -1
        self._uCurvesB = -1

        self._init_gl()

    # ------------------------------------------------------------
    # OpenGL init
    # ------------------------------------------------------------

    def _init_gl(self) -> None:
        root = Path(__file__).resolve().parent  # render/
        vpath = root / "shaders" / "bezier_text.vert"
        fpath = root / "shaders" / "bezier_text.frag"

        vert_src = vpath.read_text(encoding="utf-8")
        frag_src = fpath.read_text(encoding="utf-8")

        vs = compile_shader(GL_VERTEX_SHADER, vert_src)
        fs = compile_shader(GL_FRAGMENT_SHADER, frag_src)
        self._program = link_program(vs, fs)

        # Quad buffer (6 vertices, cada uno: x,y,u,v = 4 floats)
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)

        glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)

        stride = 4 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, False, stride, ctypes.c_void_p(0))

        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, False, stride, ctypes.c_void_p(8))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        # Uniforms
        glUseProgram(self._program)
        self._uResolution = glGetUniformLocation(self._program, "uResolution")
        self._uColor = glGetUniformLocation(self._program, "uColor")
        self._uGlyphPx = glGetUniformLocation(self._program, "uGlyphPx")
        self._uAAPx = glGetUniformLocation(self._program, "uAAPx")
        self._uCurveCount = glGetUniformLocation(self._program, "uCurveCount")
        self._uCurvesA = glGetUniformLocation(self._program, "uCurvesA")
        self._uCurvesB = glGetUniformLocation(self._program, "uCurvesB")
        glUseProgram(0)

    # ------------------------------------------------------------
    # Low-level draw: 1 glyph
    # ------------------------------------------------------------

    def draw_glyph(
        self,
        x: float,
        y: float,
        outline,
        *,
        resolution: tuple[int, int],
        style: VectorTextStyle,
        scale: float = 1.0,
    ) -> float:
        """
        Dibuja un glyph y devuelve el avance recomendado en px para pen_x.
        Requiere que outline.beziers estén en coords locales del glyph:
        - x en 0..bbox_w
        - y en 0..bbox_h
        """

        curves = getattr(outline, "beziers", [])
        count = min(len(curves), self.MAX_CURVES)

        bbox_w = float(getattr(outline, "bbox_w", style.size_px))
        bbox_h = float(getattr(outline, "bbox_h", style.size_px))

        # Escala: si tu outline bbox ya está en px del face, esto lo puedes ajustar.
        # Mantener proporción real del glyph
        w = bbox_w * scale
        h = bbox_h * scale

        x0 = float(x)
        y0 = float(y) - h   # <-- SUBE el glyph al quad (baseline)
        x1 = x0 + w
        y1 = y0 + h

        verts = np.array(
            [
                [x0, y0, 0.0, 0.0],
                [x1, y0, 1.0, 0.0],
                [x1, y1, 1.0, 1.0],
                [x0, y0, 0.0, 0.0],
                [x1, y1, 1.0, 1.0],
                [x0, y1, 0.0, 1.0],
            ],
            dtype=np.float32,
        )

        glUseProgram(self._program)
        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferSubData(GL_ARRAY_BUFFER, 0, verts.nbytes, verts)

        glUniform2f(self._uResolution, float(resolution[0]), float(resolution[1]))
        glUniform4f(self._uColor, *style.color)
        glUniform2f(self._uGlyphPx, w, h)
        glUniform1f(self._uAAPx, float(style.aa_px))
        glUniform1i(self._uCurveCount, int(count))

        # Empaquetamos curvas a uniform arrays
        if count > 0:
            arrA = np.zeros((self.MAX_CURVES, 4), dtype=np.float32)
            arrB = np.zeros((self.MAX_CURVES, 4), dtype=np.float32)

            # OJO: si dibujas con escala, escala también puntos del glyph.
            for i in range(count):
                bz = curves[i]
                p0 = (bz.p0[0] * scale, bz.p0[1] * scale)
                p1 = (bz.p1[0] * scale, bz.p1[1] * scale)
                p2 = (bz.p2[0] * scale, bz.p2[1] * scale)
                arrA[i] = (p0[0], p0[1], p1[0], p1[1])
                arrB[i] = (p2[0], p2[1], 0.0, 0.0)

            glUniform4fv(self._uCurvesA, self.MAX_CURVES, arrA)
            glUniform4fv(self._uCurvesB, self.MAX_CURVES, arrB)

        glDrawArrays(GL_TRIANGLES, 0, 6)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        glUseProgram(0)

        # avance
        adv = float(getattr(outline, "advance_px", 0.6 * style.size_px))
        return adv * scale

    # ------------------------------------------------------------
    # Public: draw text
    # ------------------------------------------------------------

    def draw_text_ttf(
        self,
        x: float,
        y: float,
        text: str,
        *,
        font,  # VectorBezierFont
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> None:
        if not text:
            return

        pen_x = float(x)
        pen_y = float(y)

        # Si tu font fue creado con pixel_size, y style.size_px es distinto,
        # escalamos de forma simple:
        scale = style.size_px / float(font.pixel_size)

        for ch in text:
            if ch == "\n":
                pen_x = float(x)
                pen_y += style.size_px * style.line_height
                continue

            outline = font.load_glyph(ch)

            adv = self.draw_glyph(
                x=pen_x,
                y=pen_y,
                outline=outline,
                resolution=resolution,
                style=style,
                scale=scale,
            )

            pen_x += adv + float(style.letter_spacing_px)