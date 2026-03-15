# render/vector_bezier_text.py
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_DYNAMIC_DRAW,
    GL_FLOAT,
    GL_TRIANGLES,
    glBindBuffer,
    glBindVertexArray,
    glBufferData,
    glBufferSubData,
    glDrawArrays,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenVertexArrays,
    glGetUniformLocation,
    glUniform1f,
    glUniform1i,
    glUniform2f,
    glUniform4f,
    glUniform4fv,
    glUseProgram,
    glVertexAttribPointer,
    GL_VERTEX_SHADER,
    GL_FRAGMENT_SHADER,
)

from render.gl_utils import compile_shader, link_program


# ------------------------------------------------------------
# Style
# ------------------------------------------------------------

@dataclass
class VectorTextStyle:
    size_px: float = 15.0
    color: tuple[float, float, float, float] = (0.95, 0.95, 1.0, 1.0)

    # Peso visual / borde
    stroke_px: float = 0.1
    aa_px: float = 1.3

    # Layout
    letter_spacing_px: float = 2.0
    line_height: float = 1.2

    # Modo de render
    render_mode: str = "direct"   # "direct", "banded_direct", "distance", "splat"

    # Debug / calidad
    debug_draw_bounds: bool = False
    band_count: int = 8


# ------------------------------------------------------------
# Renderer
# ------------------------------------------------------------

class VectorBezierTextRenderer:
    """
    Render de texto vectorial por curvas Bézier en shader.

    En esta fase:
    - direct: backend principal
    - banded_direct: stub que reutiliza direct
    - distance: pendiente
    - splat: pendiente

    Importante:
    Esta versión asume que el outline viene en font units.
    La conversión a píxeles se hace usando:
        glyph_scale = style.size_px / units_per_em
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
        self._uStrokePx = -1

        self._init_gl()

    # ------------------------------------------------------------
    # Public dispatcher
    # ------------------------------------------------------------

    def draw_glyph(
        self,
        x: float,
        y: float,
        outline,
        *,
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> float:
        """
        Dispatcher principal por modo de render.
        """
        mode = style.render_mode

        if mode == "direct":
            return self._draw_glyph_direct(
                x=x,
                y=y,
                outline=outline,
                resolution=resolution,
                style=style,
            )

        if mode == "banded_direct":
            return self._draw_glyph_banded(
                x=x,
                y=y,
                outline=outline,
                resolution=resolution,
                style=style,
            )

        if mode == "distance":
            return self._draw_glyph_distance(
                x=x,
                y=y,
                outline=outline,
                resolution=resolution,
                style=style,
            )

        if mode == "splat":
            return self._draw_glyph_splat(
                x=x,
                y=y,
                outline=outline,
                resolution=resolution,
                style=style,
            )

        raise ValueError(f"render_mode no soportado: {mode}")

    # ------------------------------------------------------------
    # OpenGL init
    # ------------------------------------------------------------

    def _init_gl(self) -> None:
        root = Path(__file__).resolve().parent
        vpath = root / "shaders" / "bezier_text.vert"
        fpath = root / "shaders" / "bezier_text.frag"

        vert_src = vpath.read_text(encoding="utf-8")
        frag_src = fpath.read_text(encoding="utf-8")

        vs = compile_shader(GL_VERTEX_SHADER, vert_src)
        fs = compile_shader(GL_FRAGMENT_SHADER, frag_src)
        self._program = link_program(vs, fs)

        # Quad buffer: 6 vertices, cada uno con x, y, u, v
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
        self._uStrokePx = glGetUniformLocation(self._program, "uStrokePx")
        glUseProgram(0)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _glyph_scale(self, outline, style: VectorTextStyle) -> float:
        units_per_em = float(getattr(outline, "units_per_em", 2048.0))
        units_per_em = max(1.0, units_per_em)
        return float(style.size_px) / units_per_em

    # ------------------------------------------------------------
    # Backend: direct
    # ------------------------------------------------------------

    def _draw_glyph_direct(
        self,
        x: float,
        y: float,
        outline,
        *,
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> float:
        """
        Dibuja un glyph y devuelve el avance recomendado en px para pen_x.

        Se espera que outline.beziers esté en font units.
        La conversión a píxeles se hace aquí con units_per_em.
        """
        print("ADV:", outline.advance_px, "bbox:", outline.bbox_w)
        curves = getattr(outline, "beziers", [])
        count = min(len(curves), self.MAX_CURVES)

        glyph_scale = self._glyph_scale(outline, style)

        # bbox en píxeles finales
        bbox_w = float(getattr(outline, "bbox_w", 0.0)) * glyph_scale
        bbox_h = float(getattr(outline, "bbox_h", 0.0)) * glyph_scale

        w = bbox_w
        h = bbox_h

        # bearings en píxeles finales
        bearing_x = float(getattr(outline, "bearing_x", 0.0)) * glyph_scale
        bearing_y = float(getattr(outline, "bearing_y", 0.0)) * glyph_scale

        # Posición del quad en pantalla
        x0 = float(x) + bearing_x
        y0 = float(y) - bearing_y
        x1 = x0 + w
        y1 = y0 + h

        verts = np.array(
            [
                [x0, y0, 0.0, 1.0],
                [x1, y0, 1.0, 1.0],
                [x1, y1, 1.0, 0.0],
                [x0, y0, 0.0, 1.0],
                [x1, y1, 1.0, 0.0],
                [x0, y1, 0.0, 0.0],
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
        glUniform1f(self._uStrokePx, float(style.stroke_px))
        glUniform1i(self._uCurveCount, int(count))

        if count > 0:
            arrA = np.zeros((self.MAX_CURVES, 4), dtype=np.float32)
            arrB = np.zeros((self.MAX_CURVES, 4), dtype=np.float32)

            for i in range(count):
                bz = curves[i]

                # Curvas en píxeles finales
                p0 = (float(bz.p0[0]) * glyph_scale, float(bz.p0[1]) * glyph_scale)
                p1 = (float(bz.p1[0]) * glyph_scale, float(bz.p1[1]) * glyph_scale)
                p2 = (float(bz.p2[0]) * glyph_scale, float(bz.p2[1]) * glyph_scale)

                arrA[i] = (p0[0], p0[1], p1[0], p1[1])
                arrB[i] = (p2[0], p2[1], 0.0, 0.0)

            glUniform4fv(self._uCurvesA, self.MAX_CURVES, arrA)
            glUniform4fv(self._uCurvesB, self.MAX_CURVES, arrB)

        glDrawArrays(GL_TRIANGLES, 0, 6)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        glUseProgram(0)

        # advance en píxeles finales
        font_pixel_size = float(getattr(outline, "font_pixel_size", 128.0))
        font_pixel_size = max(1.0, font_pixel_size)

        adv_px = float(getattr(outline, "advance_px", 0.0))
        adv_units = float(getattr(outline, "advance_px", 0.0))
        adv = adv_units * glyph_scale

        # DEBUG
        print(
        repr(outline.char if hasattr(outline, "char") else "?"),
        "advance_raw=", adv_units,
        "glyph_scale=", glyph_scale,
        "advance_final=", adv,
        "bearing_x=", getattr(outline, "bearing_x", None),
        "bbox_w=", getattr(outline, "bbox_w", None),
        )

        return adv
    # ------------------------------------------------------------
    # Backend: banded_direct
    # ------------------------------------------------------------

    def _draw_glyph_banded(
        self,
        x: float,
        y: float,
        outline,
        *,
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> float:
        
        
        """
        Stub temporal.

        Más adelante aquí meteremos subdivisión por bandas para reducir
        el número de curvas consultadas por zona del glyph.
        """
        return self._draw_glyph_direct(
            x=x,
            y=y,
            outline=outline,
            resolution=resolution,
            style=style,
        )

    # ------------------------------------------------------------
    # Backend: distance
    # ------------------------------------------------------------

    def _draw_glyph_distance(
        self,
        x: float,
        y: float,
        outline,
        *,
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> float:
        raise NotImplementedError("Modo distance todavía no implementado")

    # ------------------------------------------------------------
    # Backend: splat
    # ------------------------------------------------------------

    def _draw_glyph_splat(
        self,
        x: float,
        y: float,
        outline,
        *,
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> float:
        raise NotImplementedError("Modo splat todavía no implementado")

    # ------------------------------------------------------------
    # Public: draw text
    # ------------------------------------------------------------

    def draw_text_ttf(
        self,
        x: float,
        y: float,
        text: str,
        *,
        font,
        resolution: tuple[int, int],
        style: VectorTextStyle,
    ) -> None:
        if not text:
            return

        pen_x = float(x)
        pen_y = float(y)

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
            )

            pen_x += adv + float(style.letter_spacing_px)