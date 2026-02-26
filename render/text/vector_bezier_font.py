import freetype
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class QuadBezier:
    p0: Tuple[float, float]
    p1: Tuple[float, float]
    p2: Tuple[float, float]


@dataclass
class GlyphOutline:
    beziers: List[QuadBezier]
    advance_px: float
    bbox_w: float
    bbox_h: float
    bearing_x: float
    bearing_y: float


class VectorBezierFont:
    """
    Extrae outlines TTF como curvas cuadráticas Bézier (FreeType).

    Devuelve puntos en coordenadas LOCALES del glyph:
      x: 0..bbox_w
      y: 0..bbox_h
    (sin flip extra, para no romper el inside/outside)
    """

    def __init__(self, path: str, pixel_size: int = 64):
        self.face = freetype.Face(path)
        self.face.set_pixel_sizes(0, pixel_size)
        self.pixel_size = pixel_size

    @staticmethod
    def _is_on(tag: int) -> bool:
        return (tag & 1) == 1

    @staticmethod
    def _midpoint(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
        return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)

    def load_glyph(self, char: str) -> GlyphOutline:
        self.face.load_char(char, freetype.FT_LOAD_NO_BITMAP)
        outline = self.face.glyph.outline

        pts = [(float(x), float(y)) for (x, y) in outline.points]
        tags = list(outline.tags)
        contours = list(outline.contours)

        advance_px = self.face.glyph.advance.x / 64.0
        bearing_x = self.face.glyph.metrics.horiBearingX / 64.0
        bearing_y = self.face.glyph.metrics.horiBearingY / 64.0

        if not pts:
            return GlyphOutline([], advance_px, 1.0, 1.0, bearing_x, bearing_y)

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)

        bbox_w = max(1.0, maxx - minx)
        bbox_h = max(1.0, maxy - miny)

        def to_local(p: Tuple[float, float]) -> Tuple[float, float]:
            # 0..bbox (sin flip)
            return (p[0] - minx, p[1] - miny)

        beziers: List[QuadBezier] = []

        start = 0
        for end in contours:
            cpts = pts[start:end + 1]
            ctags = tags[start:end + 1]
            start = end + 1

            if not cpts:
                continue

            p = list(cpts)
            t = [self._is_on(x) for x in ctags]

            # Fix si empieza off-curve
            if not t[0]:
                if not t[-1]:
                    p0 = self._midpoint(p[-1], p[0])
                    p.insert(0, p0)
                    t.insert(0, True)
                else:
                    p = [p[-1]] + p[:-1]
                    t = [t[-1]] + t[:-1]

            i = 0
            n = len(p)
            while i < n:
                p0 = p[i]
                on0 = t[i]
                p1 = p[(i + 1) % n]
                on1 = t[(i + 1) % n]

                if on0 and on1:
                    c = self._midpoint(p0, p1)
                    beziers.append(QuadBezier(to_local(p0), to_local(c), to_local(p1)))
                    i += 1
                    continue

                if on0 and not on1:
                    p2 = p[(i + 2) % n]
                    on2 = t[(i + 2) % n]

                    if on2:
                        beziers.append(QuadBezier(to_local(p0), to_local(p1), to_local(p2)))
                        i += 2
                    else:
                        mid = self._midpoint(p1, p2)
                        beziers.append(QuadBezier(to_local(p0), to_local(p1), to_local(mid)))
                        p.insert(i + 2, mid)
                        t.insert(i + 2, True)
                        n += 1
                        i += 2
                    continue

                i += 1

        return GlyphOutline(beziers, advance_px, bbox_w, bbox_h, bearing_x, bearing_y)