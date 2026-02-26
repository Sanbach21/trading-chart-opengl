# render/text/msdf_text.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from render.renderer import Renderer2D, Color

Vec4 = Tuple[float, float, float, float]


# -----------------------------
# Style
# -----------------------------
@dataclass
class MsdfTextStyle:
    size_px: float = 14.0
    color: Vec4 = (1, 1, 1, 1)
    bg_color: Optional[Vec4] = None

    # parámetros del shader MSDF
    edge: float = 0.5
    smoothing: float = 0.08

    # espaciado extra (en px)
    letter_spacing_px: float = 0.0


# -----------------------------
# Glyph
# -----------------------------
@dataclass
class MsdfGlyph:
    # UVs (0..1)
    u0: float
    v0: float
    u1: float
    v1: float

    # --- MODO CORRECTO (EM units) ---
    plane_left: Optional[float] = None
    plane_right: Optional[float] = None
    plane_top: Optional[float] = None
    plane_bottom: Optional[float] = None
    advance_em: Optional[float] = None

    # --- BACKCOMPAT (si ya venían en px “base”) ---
    w: Optional[float] = None
    h: Optional[float] = None
    xoff: Optional[float] = None
    yoff: Optional[float] = None
    xadv: Optional[float] = None


@dataclass
class MsdfFontMetrics:
    line_height: float
    ascent: float
    descent: float


class MsdfFont:
    """
    Fuente MSDF. Dibuja usando Renderer2D.begin_msdf_text / draw_textured_quad_px / end_msdf_text.

    - Si glyphs tienen planeBounds + advance => EM units (correcto).
      style.size_px significa “pixels per em”.
    - Si glyphs tienen w/h/xoff/yoff/xadv => px a base_size_px (compat).
    """

    def __init__(
        self,
        atlas_texture_id: int,
        glyphs: Dict[int, MsdfGlyph],
        metrics: MsdfFontMetrics,
        base_size_px: float,
    ):
        self.texture_id = int(atlas_texture_id)
        self.glyphs = glyphs
        self.metrics = metrics
        self.base_size_px = float(base_size_px)

    # -------------------------
    # Helpers
    # -------------------------
    def _glyph_is_em(self, g: MsdfGlyph) -> bool:
        return (
            g.plane_left is not None
            and g.plane_right is not None
            and g.plane_top is not None
            and g.plane_bottom is not None
            and g.advance_em is not None
        )

    # -------------------------
    # API
    # -------------------------
    def measure_text(self, text: str, style: MsdfTextStyle) -> Tuple[float, float]:
        size_px = max(1e-6, float(style.size_px))

        # detectar modo por primer glyph existente
        em_mode: Optional[bool] = None
        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is not None:
                em_mode = self._glyph_is_em(g)
                break
        if em_mode is None:
            em_mode = True

        # altura
        if em_mode:
            max_h = float(self.metrics.line_height) * size_px
        else:
            s = size_px / self.base_size_px
            max_h = float(self.metrics.line_height) * s

        # ancho
        x = 0.0
        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is None:
                x += (size_px * 0.33) + float(style.letter_spacing_px)
                continue

            if self._glyph_is_em(g):
                x += float(g.advance_em) * size_px + float(style.letter_spacing_px)
            else:
                s = size_px / self.base_size_px
                adv = float(g.xadv) if g.xadv is not None else (self.base_size_px * 0.33)
                x += adv * s + float(style.letter_spacing_px)

        return float(x), float(max_h)

    def draw_text(self, r: Renderer2D, x: float, y: float, text: str, style: MsdfTextStyle) -> None:
        x = float(x)
        y = float(y)
        size_px = max(1e-6, float(style.size_px))
        if size_px < 16.0:
            x = float(int(x))
            y = float(int(y))

        # fondo opcional
        if style.bg_color is not None:
            w, h = self.measure_text(text, style)
            r.draw_rect_px(x, y, w, h, Color(*style.bg_color))

        # detectar modo
        em_mode: Optional[bool] = None
        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is not None:
                em_mode = self._glyph_is_em(g)
                break
        if em_mode is None:
            em_mode = True

        # baseline (y es top-left del bloque)
        if em_mode:
            baseline_y = y + float(self.metrics.ascent) * size_px
        else:
            s = size_px / self.base_size_px
            baseline_y = y + float(self.metrics.ascent) * s

        cursor_x = x
        col = Color(*style.color)

        # si existe flush (para no mezclar pipeline)
        if hasattr(r, "flush"):
            r.flush()

        r.begin_msdf_text(
            texture_id=self.texture_id,
            edge=float(style.edge),
            smoothing=float(style.smoothing),
            color=col,
        )

        for ch in text:
            g = self.glyphs.get(ord(ch))
            if g is None:
                cursor_x += (size_px * 0.33) + float(style.letter_spacing_px)
                continue

            if self._glyph_is_em(g):
                w = (float(g.plane_right) - float(g.plane_left)) * size_px
                h = (float(g.plane_top) - float(g.plane_bottom)) * size_px

                xoff = float(g.plane_left) * size_px
                yoff = -float(g.plane_top) * size_px

                qx = cursor_x + xoff
                qy = baseline_y + yoff

                r.draw_textured_quad_px(qx, qy, w, h, g.u0, g.v0, g.u1, g.v1)
                cursor_x += float(g.advance_em) * size_px + float(style.letter_spacing_px)

            else:
                s = size_px / self.base_size_px
                gw = (float(g.w) if g.w is not None else 0.0) * s
                gh = (float(g.h) if g.h is not None else 0.0) * s
                xoff = (float(g.xoff) if g.xoff is not None else 0.0) * s
                yoff = (float(g.yoff) if g.yoff is not None else 0.0) * s
                adv = (float(g.xadv) if g.xadv is not None else (self.base_size_px * 0.33)) * s

                qx = cursor_x + xoff
                qy = baseline_y + yoff

                r.draw_textured_quad_px(qx, qy, gw, gh, g.u0, g.v0, g.u1, g.v1)
                cursor_x += adv + float(style.letter_spacing_px)

        r.end_msdf_text()


# -----------------------------
# Font Manager
# -----------------------------
class MsdfFontManager:
    def __init__(self) -> None:
        self._fonts: Dict[str, MsdfFont] = {}

    def register(self, name: str, font: MsdfFont) -> None:
        self._fonts[str(name)] = font

    def get(self, name: str) -> MsdfFont:
        key = str(name)
        if key not in self._fonts:
            raise KeyError(f"MSDF font '{key}' not registered")
        return self._fonts[key]