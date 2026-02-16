# charts/overlays/axis.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional


Rect = Tuple[float, float, float, float]


# -----------------------------
# Mini "font" 7-seg (sin texturas)
# -----------------------------
@dataclass
class SevenSegStyle:
    size_px: float = 14.0
    thickness_px: float = 2.0
    spacing_px: float = 2.0
    color: Tuple[float, float, float, float] = (1, 1, 1, 1)
    bg_color: Optional[Tuple[float, float, float, float]] = None


class SevenSegFont:
    """
    Dibuja texto numérico usando segmentos (tipo display digital).
    Soporta: 0-9, '.', '-', espacios.
    """

    # Segmentos: a,b,c,d,e,f,g
    DIGITS = {
        "0": (1, 1, 1, 1, 1, 1, 0),
        "1": (0, 1, 1, 0, 0, 0, 0),
        "2": (1, 1, 0, 1, 1, 0, 1),
        "3": (1, 1, 1, 1, 0, 0, 1),
        "4": (0, 1, 1, 0, 0, 1, 1),
        "5": (1, 0, 1, 1, 0, 1, 1),
        "6": (1, 0, 1, 1, 1, 1, 1),
        "7": (1, 1, 1, 0, 0, 0, 0),
        "8": (1, 1, 1, 1, 1, 1, 1),
        "9": (1, 1, 1, 1, 0, 1, 1),
        "-": (0, 0, 0, 0, 0, 0, 1),
        " ": (0, 0, 0, 0, 0, 0, 0),
        ":": (0, 0, 0, 0, 0, 0, 0),  # se dibuja aparte si querés
    }

    def measure_text(self, text: str, style: SevenSegStyle) -> Tuple[float, float]:
        h = float(style.size_px)
        w_char = 0.6 * h
        w = 0.0
        for ch in text:
            if ch == ".":
                w += 0.25 * h + style.spacing_px
            else:
                w += w_char + style.spacing_px
        return w, h

    def draw_text(self, r, x: float, y: float, text: str, style: SevenSegStyle) -> None:
        x = float(x)
        y = float(y)
        h = float(style.size_px)
        t = max(1.0, float(style.thickness_px))
        col = style.color

        if style.bg_color is not None:
            w, hh = self.measure_text(text, style)
            r.draw_rect_px(x, y, w, hh, color=style.bg_color)

        cursor_x = x
        for ch in text:
            if ch == ".":
                dot = 0.18 * h
                r.draw_rect_px(cursor_x, y + h - dot, dot, dot, color=col)
                cursor_x += 0.25 * h + style.spacing_px
                continue

            if ch == ":":
                # dos puntos simples
                dot = 0.18 * h
                r.draw_rect_px(cursor_x, y + 0.35 * h, dot, dot, color=col)
                r.draw_rect_px(cursor_x, y + 0.70 * h, dot, dot, color=col)
                cursor_x += 0.25 * h + style.spacing_px
                continue

            self._draw_char(r, cursor_x, y, ch, h, t, col)
            cursor_x += 0.6 * h + style.spacing_px

    def _draw_char(self, r, x: float, y: float, ch: str, h: float, thick: float, col) -> None:
        seg = self.DIGITS.get(ch, self.DIGITS[" "])
        w = 0.6 * h

        if seg[0]:  # a
            r.draw_rect_px(x + thick, y, w - 2 * thick, thick, color=col)
        if seg[1]:  # b
            r.draw_rect_px(x + w - thick, y + thick, thick, (h * 0.5) - 1.5 * thick, color=col)
        if seg[2]:  # c
            r.draw_rect_px(x + w - thick, y + (h * 0.5) + 0.5 * thick, thick, (h * 0.5) - 1.5 * thick, color=col)
        if seg[3]:  # d
            r.draw_rect_px(x + thick, y + h - thick, w - 2 * thick, thick, color=col)
        if seg[4]:  # e
            r.draw_rect_px(x, y + (h * 0.5) + 0.5 * thick, thick, (h * 0.5) - 1.5 * thick, color=col)
        if seg[5]:  # f
            r.draw_rect_px(x, y + thick, thick, (h * 0.5) - 1.5 * thick, color=col)
        if seg[6]:  # g
            r.draw_rect_px(x + thick, y + (h * 0.5) - 0.5 * thick, w - 2 * thick, thick, color=col)


# -----------------------------
# Price Axis Overlay (Ninja-like major/minor)
# -----------------------------
@dataclass
class PriceAxisStyle:
    font_size_px: float = 13.0
    font_thickness_px: float = 2.0
    font_color: Tuple[float, float, float, float] = (0.78, 0.78, 0.78, 1.0)
    label_bg: Optional[Tuple[float, float, float, float]] = None
    padding_px: float = 6.0

    # gridlines
    grid_major_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.35)
    grid_minor_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.15)
    grid_major_width: float = 1.0
    grid_minor_width: float = 1.0

    # ticks in axis
    tick_major_len: float = 7.0
    tick_minor_len: float = 4.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.60, 0.60, 0.60, 0.9)

    decimals: int = 2
    target_major_ticks: int = 8
    minor_divisions: int = 4  # Ninja-like: 4 subdivisiones
    label_minor: bool = True
    min_label_gap_px: float = 10.0  # evita que se monten textos



class PriceAxisOverlay:
    def __init__(self, overlay, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.font = SevenSegFont()

        self.style = PriceAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect
        if aw <= 0 or ah <= 0 or plot_w <= 0 or plot_h <= 0:
            return

        side = (self.overlay.config["price_axis"].get("side", "right") or "right").lower()

        # Ticks: majors + minors (si PriceScale soporta get_ticks_ex)
        majors: List[Tuple[float, float]] = []
        minors: List[Tuple[float, float]] = []

        if hasattr(self.price_scale, "get_ticks_ex"):
            out = self.price_scale.get_ticks_ex(
                target_major=self.style.target_major_ticks,
                minor_divisions=self.style.minor_divisions,
            )
            majors = out.get("major", []) or []
            minors = out.get("minor", []) or []
        else:
            majors = self.price_scale.get_ticks(target_count=self.style.target_major_ticks)

        # estilo fuente
        fstyle = SevenSegStyle(
            size_px=float(self.style.font_size_px),
            thickness_px=float(self.style.font_thickness_px),
            spacing_px=2.0,
            color=self.style.font_color,
            bg_color=self.style.label_bg,
        )
        pad = float(self.style.padding_px)

        # 1) minor gridlines (suaves)
        for price, yy in minors:
            y = float(yy)
            # ////   r.draw_line_px(plot_x, y, plot_x + plot_w, y, color=self.style.grid_minor_color, width=float(self.style.grid_minor_width))

            # tick minor
            if side == "left":
                x1 = ax + aw - self.style.tick_minor_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_minor_len
            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=float(self.style.tick_width))

            # --- label en minor (si querés precio en cada tick) ---
            if self.style.label_minor:
                label = f"{float(price):.{int(self.style.decimals)}f}"
                tw, th = self.font.measure_text(label, fstyle)

                ty = y - th * 0.5
                if side == "left":
                    tx = ax + pad
                else:
                    tx = (ax + aw) - pad - tw

                # clamp dentro del eje
                if ty < ay:
                    ty = ay
                if ty + th > ay + ah:
                    ty = (ay + ah) - th

                # anti-overlap vertical simple
                if not hasattr(self, "_last_label_y"):
                    self._last_label_y = -1e9
                if abs(ty - self._last_label_y) >= (th + self.style.min_label_gap_px):
                    self.font.draw_text(r, tx, ty, label, fstyle)
                    self._last_label_y = ty

            

        # 2) major gridlines + labels
        for price, yy in majors:
            y = float(yy)

            # major gridline
            r.draw_line_px(plot_x, y, plot_x + plot_w, y, color=self.style.grid_major_color, width=float(self.style.grid_major_width))

            # tick major
            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len
            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=float(self.style.tick_width))

            # label (solo major)
            label = f"{float(price):.{int(self.style.decimals)}f}"
            tw, th = self.font.measure_text(label, fstyle)

            ty = y - th * 0.5
            if side == "left":
                tx = ax + pad
            else:
                tx = (ax + aw) - pad - tw

            # clamp dentro del eje
            if ty < ay:
                ty = ay
            if ty + th > ay + ah:
                ty = (ay + ah) - th

            self.font.draw_text(r, tx, ty, label, fstyle)


# -----------------------------
# Time Axis Overlay (compact + densidad)
# -----------------------------
@dataclass
class TimeAxisStyle:
    font_size_px: float = 13.0
    font_thickness_px: float = 2.0
    font_color: Tuple[float, float, float, float] = (0.78, 0.78, 0.78, 1.0)
    label_bg: Optional[Tuple[float, float, float, float]] = None
    padding_px: float = 6.0

    tick_len: float = 6.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.60, 0.60, 0.60, 0.9)

    # gridlines verticales opcionales
    gridline_in_plot: bool = True
    grid_major_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)
    grid_major_width: float = 1.0

    # densidad
    min_label_spacing_px: float = 90.0  # evita amontonamiento
    format_compact: bool = True         # Ninja-like


class TimeAxisOverlay:
    def __init__(self, overlay, time_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.time_scale = time_scale
        self.font = SevenSegFont()

        self.style = TimeAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.time_axis_rect
        if aw <= 0 or ah <= 0 or plot_w <= 0:
            return

        vr = self.time_scale.get_visible_range()
        vs = int(vr.start_idx)
        ve = int(vr.end_idx)
        if ve <= vs:
            return

        fstyle = SevenSegStyle(
            size_px=float(self.style.font_size_px),
            thickness_px=float(self.style.font_thickness_px),
            spacing_px=2.0,
            color=self.style.font_color,
            bg_color=self.style.label_bg,
        )
        pad = float(self.style.padding_px)

        # Step basado en píxeles: que no se solapen
        # usamos index_to_x para estimar spacing promedio
        x0 = self.time_scale.index_to_x(vs)
        x1 = self.time_scale.index_to_x(min(vs + 1, ve))
        px_per_bar = max(1.0, abs(x1 - x0))
        step = max(1, int(self.style.min_label_spacing_px / px_per_bar))

        last_label_right = -1e9
        for i in range(vs, ve + 1, step):
            if i >= len(self.time_scale._timestamps):
                break

            x = float(self.time_scale.index_to_x(i))
            ts = self.time_scale._timestamps[i]

            # gridline vertical major
            if self.style.gridline_in_plot:
                r.draw_line_px(x, plot_y, x, plot_y + plot_h, color=self.style.grid_major_color, width=float(self.style.grid_major_width))

            # tick en eje
            y1 = ay
            y2 = ay + self.style.tick_len
            r.draw_line_px(x, y1, x, y2, color=self.style.tick_color, width=float(self.style.tick_width))

            # label
            label = self._format_time(ts)
            tw, th = self.font.measure_text(label, fstyle)
            tx = x - tw * 0.5
            ty = (ay + ah) - pad - th

            # clamp dentro del rect del eje
            if tx < ax + pad:
                tx = ax + pad
            if tx + tw > ax + aw - pad:
                tx = ax + aw - pad - tw

            # anti-overlap adicional
            if tx < last_label_right + 6.0:
                continue
            last_label_right = tx + tw

            self.font.draw_text(r, tx, ty, label, fstyle)

    def _format_time(self, ts: datetime) -> str:
        if self.style.format_compact:
            # Ninja-like: solo hora/minuto (y cambia a fecha cuando haga falta más adelante)
            return ts.strftime("%I:%M %p").lstrip("0")  # "2:31 AM"
        return ts.strftime("%Y-%m-%d %H:%M")
