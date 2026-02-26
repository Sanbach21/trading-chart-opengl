# render/text/bitmap_font.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Protocol

import freetype
from OpenGL.GL import (
    GL_CLAMP_TO_EDGE,
    GL_LINEAR,
    GL_NEAREST,
    GL_RED,
    GL_R8,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_UNPACK_ALIGNMENT,
    GL_UNSIGNED_BYTE,
    glBindTexture,
    glDeleteTextures,
    glGenTextures,
    glPixelStorei,
    glTexImage2D,
    glTexParameteri,
)

Vec4 = Tuple[float, float, float, float]


class _TextStyleLike(Protocol):
    size_px: float
    color: Vec4
    bg_color: Optional[Vec4]
    letter_spacing_px: float


@dataclass(frozen=True)
class BitmapGlyph:
    tex_id: int
    w: int
    h: int
    bearing_x: int
    bearing_y: int
    advance_px: float


class BitmapFont:
    def __init__(
        self,
        ttf_path: str,
        pixel_size: int = 24,
        *,
        face_index: int = 0,
        char_range: Tuple[int, int] = (32, 126),
        letter_spacing_px: float = 0.0,
        linear_filter: bool = True,
    ) -> None:
        self.ttf_path = str(ttf_path)
        self.pixel_size = int(pixel_size)
        self.face_index = int(face_index)
        self.char_range = (int(char_range[0]), int(char_range[1]))
        self.default_letter_spacing_px = float(letter_spacing_px)
        self.linear_filter = bool(linear_filter)

        self._face = freetype.Face(self.ttf_path, index=self.face_index)
        self._face.set_pixel_sizes(0, self.pixel_size)

        self.glyphs: Dict[int, BitmapGlyph] = {}
        self._owned_tex_ids: list[int] = []

        self.ascent_px = self._face.size.ascender / 64.0
        self.descent_px = self._face.size.descender / 64.0
        self.line_height_px = self._face.size.height / 64.0

        # Lazy: se crea en el primer draw_text (con contexto ya listo)
        self._text_renderer = None

        self._build_glyphs()

    def draw_text(self, renderer: Any, x: float, y: float, text: str, style: Any) -> None:
        """API compatible con MsdfFont.draw_text(...) para TooltipOverlay."""
        # flush del batch 2D
        try:
            renderer.flush()
        except Exception:
            pass

        # lazy init (ya con contexto)
        if self._text_renderer is None:
            from render.text.bitmap_text import BitmapTextRenderer
            self._text_renderer = BitmapTextRenderer()

        size_px = float(getattr(style, "size_px", 16.0))
        color = getattr(style, "color", (1.0, 1.0, 1.0, 1.0))
        spacing = float(getattr(style, "letter_spacing_px", 0.0))

        # requiere que Renderer2D guarde width/height en begin_frame
        w = int(getattr(renderer, "width"))
        h = int(getattr(renderer, "height"))

        self._text_renderer.draw_text(
            self,
            text,
            float(x),
            float(y),
            size_px,
            color,
            (w, h),
            letter_spacing_px=spacing,
        )

    def destroy(self) -> None:
        if self._owned_tex_ids:
            glDeleteTextures(self._owned_tex_ids)
            self._owned_tex_ids.clear()
        self.glyphs.clear()

    def _build_glyphs(self) -> None:
        start, end = self.char_range
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        for code in range(start, end + 1):
            ch = chr(code)
            self._face.load_char(ch, freetype.FT_LOAD_RENDER)
            g = self._face.glyph

            bmp = g.bitmap
            w = int(bmp.width)
            h = int(bmp.rows)

            tex_id = int(glGenTextures(1))
            self._owned_tex_ids.append(tex_id)

            glBindTexture(GL_TEXTURE_2D, tex_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

            if self.linear_filter:
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            else:
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)

            if w > 0 and h > 0:
                glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, w, h, 0, GL_RED, GL_UNSIGNED_BYTE, bmp.buffer)
            else:
                glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, 1, 1, 0, GL_RED, GL_UNSIGNED_BYTE, b"\x00")

            glBindTexture(GL_TEXTURE_2D, 0)

            self.glyphs[code] = BitmapGlyph(
                tex_id=tex_id,
                w=w,
                h=h,
                bearing_x=int(g.bitmap_left),
                bearing_y=int(g.bitmap_top),
                advance_px=float(g.advance.x) / 64.0,
            )

    def get_glyph(self, ch: str) -> Optional[BitmapGlyph]:
        return self.glyphs.get(ord(ch))

    def measure_text(self, text: str, style: _TextStyleLike) -> Tuple[float, float]:
        size_px = max(1e-6, float(style.size_px))
        s = size_px / float(self.pixel_size)
        spacing = float(getattr(style, "letter_spacing_px", self.default_letter_spacing_px))

        x = 0.0
        for ch in text:
            g = self.get_glyph(ch)
            if g is None:
                x += (size_px * 0.33) + spacing
            else:
                x += (g.advance_px * s) + spacing

        h = float(self.line_height_px) * s
        return float(x), float(h)