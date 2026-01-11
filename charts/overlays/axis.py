from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple, List
from datetime import datetime  # ← ¡IMPORTANTE! Agregado aquí

# Rect = (x, y, w, h)
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
    bg_color: Tuple[float, float, float, float] | None = None


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
# Price Axis Overlay
# -----------------------------
@dataclass
class PriceAxisStyle:
    font_size_px: float = 14.0
    font_thickness_px: float = 2.0
    font_color: Tuple[float, float, float, float] = (1, 1, 1, 1)
    label_bg: Tuple[float, float, float, float] | None = None
    padding_px: float = 8.0

    gridline_in_plot: bool = True
    gridline_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.45)
    gridline_width: float = 1.0

    tick_in_axis: bool = True
    tick_length_px: float = 8.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.65, 0.65, 0.65, 0.9)

    decimals: int = 2
    target_ticks: int = 8


class PriceAxisOverlay:
    def __init__(self, overlay, price_scale, config: Dict[str, Any] | None = None) -> None:
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

        if aw <= 0 or ah <= 0:
            return

        ticks = self.price_scale.get_ticks(target_count=self.style.target_ticks)
        if not ticks:
            return

        side = "right"
        try:
            side = (self.overlay.config["price_axis"].get("side", "right") or "right").lower()
        except Exception:
            pass

        fstyle = SevenSegStyle(
            size_px=float(self.style.font_size_px),
            thickness_px=float(self.style.font_thickness_px),
            spacing_px=2.0,
            color=self.style.font_color,
            bg_color=self.style.label_bg,
        )
        pad = float(self.style.padding_px)

        for price, y in ticks:
            yy = float(y)

            if self.style.gridline_in_plot:
                r.draw_line_px(
                    plot_x, yy,
                    plot_x + plot_w, yy,
                    color=self.style.gridline_color,
                    width=float(self.style.gridline_width),
                )

            if self.style.tick_in_axis:
                if side == "left":
                    x1 = ax + aw - self.style.tick_length_px
                    x2 = ax + aw
                else:
                    x1 = ax
                    x2 = ax + self.style.tick_length_px

                r.draw_line_px(
                    x1, yy,
                    x2, yy,
                    color=self.style.tick_color,
                    width=float(self.style.tick_width),
                )

            label = f"{float(price):.{int(self.style.decimals)}f}"
            tw, th = self.font.measure_text(label, fstyle)

            ty = yy - th * 0.5
            if side == "left":
                tx = ax + pad
            else:
                tx = (ax + aw) - pad - tw

            if ty < ay:
                ty = ay
            if ty + th > ay + ah:
                ty = (ay + ah) - th

            self.font.draw_text(r, tx, ty, label, fstyle)


# -----------------------------
# Time Axis Overlay (versión completa y corregida)
# -----------------------------
@dataclass
class TimeAxisStyle:
    font_size_px: float = 14.0
    font_thickness_px: float = 2.0
    font_color: Tuple[float, float, float, float] = (1, 1, 1, 1)
    label_bg: Tuple[float, float, float, float] | None = None
    padding_px: float = 8.0

    tick_in_axis: bool = True
    tick_length_px: float = 8.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.65, 0.65, 0.65, 0.9)

    gridline_in_plot: bool = False
    gridline_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.35)
    gridline_width: float = 1.0

    target_ticks: int = 8


class TimeAxisOverlay:
    def __init__(self, overlay, time_scale, config: Dict[str, Any] | None = None) -> None:
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

        if aw <= 0 or ah <= 0:
            return

        vr = self.time_scale.get_visible_range()
        vs = vr.start_idx
        ve = vr.end_idx

        if ve <= vs:
            return

        target = max(2, int(self.style.target_ticks))
        step = max(1, int((ve - vs) / (target - 1)) or 1)

        fstyle = SevenSegStyle(
            size_px=float(self.style.font_size_px),
            thickness_px=float(self.style.font_thickness_px),
            spacing_px=2.0,
            color=self.style.font_color,
            bg_color=self.style.label_bg,
        )
        pad = float(self.style.padding_px)

        for i in range(vs, ve + 1, step):
            if i >= len(self.time_scale._timestamps):
                continue

            x = self.time_scale.index_to_x(i)
            ts = self.time_scale._timestamps[i]

            if self.style.gridline_in_plot:
                r.draw_line_px(
                    x, plot_y,
                    x, plot_y + plot_h,
                    color=self.style.gridline_color,
                    width=float(self.style.gridline_width),
                )

            if self.style.tick_in_axis:
                y1 = ay
                y2 = ay + self.style.tick_length_px
                r.draw_line_px(
                    x, y1,
                    x, y2,
                    color=self.style.tick_color,
                    width=float(self.style.tick_width),
                )

            # Label con fecha real
            label = self._format_time(ts)
            tw, th = self.font.measure_text(label, fstyle)

            tx = x - tw * 0.5
            ty = (ay + ah) - pad - th

            # Evitar que se salga del área
            if tx < ax + pad:
                tx = ax + pad
            if tx + tw > ax + aw - pad:
                tx = ax + aw - pad - tw

            self.font.draw_text(r, tx, ty, label, fstyle)

    def _format_time(self, ts: datetime) -> str:
        # Puedes hacer esto configurable después
        return ts.strftime("%Y-%m-%d %H:%M")