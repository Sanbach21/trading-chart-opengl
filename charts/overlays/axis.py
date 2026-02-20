# charts/overlays/axis.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional

from render.text.msdf_text import MsdfTextStyle


Rect = Tuple[float, float, float, float]


@dataclass
class PriceAxisStyle:
    font_size_px: float = 13.0
    font_color: Tuple[float, float, float, float] = (0.78, 0.78, 0.78, 1.0)
    label_bg: Optional[Tuple[float, float, float, float]] = None
    padding_px: float = 6.0

    edge: float = 0.5
    smoothing: float = 0.08
    letter_spacing_px: float = 0.0

    grid_major_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.35)
    grid_minor_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.15)
    grid_major_width: float = 1.0
    grid_minor_width: float = 1.0

    tick_major_len: float = 7.0
    tick_minor_len: float = 4.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.60, 0.60, 0.60, 0.9)

    decimals: int = 2
    target_major_ticks: int = 8
    minor_divisions: int = 4
    label_minor: bool = True
    min_label_gap_px: float = 10.0


class PriceAxisOverlay:
    def __init__(self, overlay, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.font = None  # set desde window.run()

        self.style = PriceAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        if self.font is None:
            return

        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect
        if aw <= 0 or ah <= 0 or plot_w <= 0 or plot_h <= 0:
            return

        side = (self.overlay.config["price_axis"].get("side", "right") or "right").lower()

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

        fstyle = MsdfTextStyle(
            size_px=float(self.style.font_size_px),
            color=self.style.font_color,
            bg_color=self.style.label_bg,
            edge=float(self.style.edge),
            smoothing=float(self.style.smoothing),
            letter_spacing_px=float(self.style.letter_spacing_px),
        )
        pad = float(self.style.padding_px)

        # minor ticks + labels
        self._last_label_y = -1e9
        for price, yy in minors:
            y = float(yy)

            if side == "left":
                x1 = ax + aw - self.style.tick_minor_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_minor_len
            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=float(self.style.tick_width))

            if self.style.label_minor:
                label = f"{float(price):.{int(self.style.decimals)}f}"
                tw, th = self.font.measure_text(label, fstyle)

                ty = y - th * 0.5
                tx = (ax + pad) if side == "left" else (ax + aw) - pad - tw

                if ty < ay:
                    ty = ay
                if ty + th > ay + ah:
                    ty = (ay + ah) - th

                if abs(ty - self._last_label_y) >= (th + self.style.min_label_gap_px):
                    self.font.draw_text(r, tx, ty, label, fstyle)
                    self._last_label_y = ty

        # major ticks + labels + grid
        for price, yy in majors:
            y = float(yy)

            r.draw_line_px(plot_x, y, plot_x + plot_w, y, color=self.style.grid_major_color, width=float(self.style.grid_major_width))

            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len
            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=float(self.style.tick_width))

            label = f"{float(price):.{int(self.style.decimals)}f}"
            tw, th = self.font.measure_text(label, fstyle)

            ty = y - th * 0.5
            tx = (ax + pad) if side == "left" else (ax + aw) - pad - tw

            if ty < ay:
                ty = ay
            if ty + th > ay + ah:
                ty = (ay + ah) - th

            self.font.draw_text(r, tx, ty, label, fstyle)


@dataclass
class TimeAxisStyle:
    font_size_px: float = 13.0
    font_color: Tuple[float, float, float, float] = (0.78, 0.78, 0.78, 1.0)
    label_bg: Optional[Tuple[float, float, float, float]] = None
    padding_px: float = 6.0

    edge: float = 0.5
    smoothing: float = 0.08
    letter_spacing_px: float = 0.0

    tick_len: float = 6.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.60, 0.60, 0.60, 0.9)

    gridline_in_plot: bool = True
    grid_major_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)
    grid_major_width: float = 1.0

    min_label_spacing_px: float = 90.0
    format_compact: bool = True


class TimeAxisOverlay:
    def __init__(self, overlay, time_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.time_scale = time_scale
        self.font = None  # set desde window.run()

        self.style = TimeAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        if self.font is None:
            return

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

        fstyle = MsdfTextStyle(
            size_px=float(self.style.font_size_px),
            color=self.style.font_color,
            bg_color=self.style.label_bg,
            edge=float(self.style.edge),
            smoothing=float(self.style.smoothing),
            letter_spacing_px=float(self.style.letter_spacing_px),
        )
        pad = float(self.style.padding_px)

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

            if self.style.gridline_in_plot:
                r.draw_line_px(x, plot_y, x, plot_y + plot_h, color=self.style.grid_major_color, width=float(self.style.grid_major_width))

            y1 = ay
            y2 = ay + self.style.tick_len
            r.draw_line_px(x, y1, x, y2, color=self.style.tick_color, width=float(self.style.tick_width))

            label = self._format_time(ts)
            tw, th = self.font.measure_text(label, fstyle)
            tx = x - tw * 0.5
            ty = (ay + ah) - pad - th

            if tx < ax + pad:
                tx = ax + pad
            if tx + tw > ax + aw - pad:
                tx = ax + aw - pad - tw

            if tx < last_label_right + 6.0:
                continue
            last_label_right = tx + tw

            self.font.draw_text(r, tx, ty, label, fstyle)

    def _format_time(self, ts: datetime) -> str:
        if self.style.format_compact:
            return ts.strftime("%I:%M %p").lstrip("0")
        return ts.strftime("%Y-%m-%d %H:%M")