from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import math

Rect = Tuple[float, float, float, float]


# ──────────────────────────────────────────────────────────────────────────────
# STYLE
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PriceAxisStyle:
    padding_px: float = 6.0

    tick_major_len: float = 9.0
    tick_major_width: float = 1.0
    tick_major_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)

    show_minor: bool = True
    minor_divisions: int = 4
    tick_minor_len: float = 6.0
    tick_minor_width: float = 1.0
    tick_minor_color: Tuple[float, float, float, float] = (0.62, 0.62, 0.62, 0.75)

    decimals: int = 2
    target_major_ticks: int = 5

    label_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    label_scale: float = 1.0
    min_label_gap_px: float = 8.0

    show_minor_labels: bool = True
    minor_label_scale: float = 0.90
    minor_label_color: Tuple[float, float, float, float] = (0.55, 0.55, 0.55, 0.90)
    minor_label_decimals: Optional[int] = None
    minor_label_gap_px: float = 6.0
    minor_label_avoid_major_px: float = 4.0


# ──────────────────────────────────────────────────────────────────────────────
# PRICE AXIS (usa escala externa)
# ──────────────────────────────────────────────────────────────────────────────

class PriceAxisOverlay:

    def __init__(
        self,
        overlay: Any,
        price_scale: Any,   # 👈 ahora recibe LocalPriceScale
        time_scale: Any,
        data_provider: Any,  # para obtener rangos visibles
        config: Optional[Dict[str, Any]] = None,
    ) -> None:

        self.overlay = overlay
        self.scale = price_scale          # 👈 única fuente de verdad
        self.time_scale = time_scale
        self.data_provider = data_provider

        self.text_renderer = None
        self.style = PriceAxisStyle()

        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    # ─────────────────────────────────────────────

    def _get_side(self) -> str:
        try:
            return (self.overlay.config["price_axis"].get("side", "right") or "right").lower()
        except Exception:
            return "right"

    def _nice_step(self, raw_step: float) -> float:
        exp = math.floor(math.log10(raw_step))
        frac = raw_step / (10 ** exp)

        if frac < 1.5:
            nice = 1
        elif frac < 3:
            nice = 2
        elif frac < 7:
            nice = 5
        else:
            nice = 10

        return nice * (10 ** exp)

    def _generate_ticks(self, plot_y, plot_h):
        min_p = self.scale._min_price
        max_p = self.scale._max_price

        rng = max_p - min_p
        if rng <= 1e-12:
            return [], []

        step = self._nice_step(rng / self.style.target_major_ticks)

        start = math.floor(min_p / step) * step
        end = math.ceil(max_p / step) * step

        majors = []
        minors = []

        p = start
        while p <= end:
            y = self.scale.price_to_y(p)
            majors.append((p, y))

            for j in range(1, self.style.minor_divisions + 1):
                mp = p + j * step / (self.style.minor_divisions + 1)
                my = self.scale.price_to_y(mp)
                minors.append((mp, my))

            p += step

        return majors, minors

    def _draw_label(self, price, y, side, ax, aw, scale, color, decimals):
        if not self.text_renderer:
            return

        label = f"{price:.{decimals}f}"
        tw, th = self.text_renderer.measure_text(label, scale=scale)

        ty = y + th * 0.35

        if side == "left":
            tx = ax + aw - self.style.padding_px - tw
        else:
            tx = ax + self.style.tick_major_len + self.style.padding_px

        tx = max(ax + 2.0, min(tx, ax + aw - tw - 2.0))

        self.text_renderer.render_text(label, tx, ty, scale=scale, color=color)

    # ─────────────────────────────────────────────
    # DRAW
    # ─────────────────────────────────────────────

    def draw(self, r):
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect

        if aw <= 0 or ah <= 0:
            return

        side = self._get_side()

        majors, minors = self._generate_ticks(plot_y, plot_h)

        if side == "left":
            mx1, mx2 = ax + aw - self.style.tick_major_len, ax + aw
            mn1, mn2 = ax + aw - self.style.tick_minor_len, ax + aw
        else:
            mx1, mx2 = ax, ax + self.style.tick_major_len
            mn1, mn2 = ax, ax + self.style.tick_minor_len

        major_ys = []

        # MAJOR
        for p, y in majors:
            if not (plot_y <= y <= plot_y + plot_h):
                continue

            if major_ys and abs(y - major_ys[-1]) < self.style.min_label_gap_px:
                continue

            r.draw_line_px(mx1, y, mx2, y, self.style.tick_major_color, self.style.tick_major_width)

            self._draw_label(
                p, y, side, ax, aw,
                self.style.label_scale,
                self.style.label_color,
                self.style.decimals
            )

            major_ys.append(y)

        # MINOR TICKS
        if self.style.show_minor:
            for _, y in minors:
                if not (plot_y <= y <= plot_y + plot_h):
                    continue

                r.draw_line_px(mn1, y, mn2, y, self.style.tick_minor_color, self.style.tick_minor_width)

        # MINOR LABELS
        if self.style.show_minor_labels:
            minor_ys = []

            dec = self.style.minor_label_decimals or (self.style.decimals + 1)

            for p, y in minors:
                if not (plot_y <= y <= plot_y + plot_h):
                    continue

                if any(abs(y - my) < self.style.minor_label_avoid_major_px for my in major_ys):
                    continue

                if minor_ys and abs(y - minor_ys[-1]) < self.style.minor_label_gap_px:
                    continue

                self._draw_label(
                    p, y, side, ax, aw,
                    self.style.minor_label_scale,
                    self.style.minor_label_color,
                    dec
                )

                minor_ys.append(y)
# ──────────────────────────────────────────────────────────────────────────────
# TIME AXIS (se mantiene usando TimeScale)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TimeAxisStyle:
    padding_px: float = 6.0
    tick_len: float = 6.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)

    min_label_spacing_px: float = 90.0

    label_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    label_scale: float = 1.0

    crisp_ticks: bool = True


class TimeAxisOverlay:

    def __init__(
        self,
        overlay: Any,
        time_scale: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.overlay = overlay
        self.time_scale = time_scale
        self.text_renderer = None

        self.style = TimeAxisStyle()

        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r: Any) -> None:
        layout = self.overlay.get_layout()
        ax, ay, aw, ah = layout.time_axis_rect
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect

        if aw <= 0 or ah <= 0:
            return

        tick_indices = self.time_scale.get_tick_indices(
            min_spacing_px=float(self.style.min_label_spacing_px),
            extend_by_one=False,
        )

        max_allowed_x = plot_x + plot_w

        for i in tick_indices:
            if i < 0:
                continue

            x = self.time_scale.get_aligned_x(
                i,
                crisp=bool(self.style.crisp_ticks),
            )

            if x > self.time_scale.get_right_draw_limit() + 1.0:
                break

            if x < plot_x - 40.0 or x > max_allowed_x + 20.0:
                continue

            # Tick
            r.draw_line_px(
                x, ay,
                x, ay + float(self.style.tick_len),
                color=self.style.tick_color,
                width=float(self.style.tick_width),
            )

            # Label
            if self.text_renderer is not None:

                if i < len(self.time_scale._timestamps):
                    ts: datetime = self.time_scale._timestamps[i]
                else:
                    last_ts = self.time_scale._timestamps[-1]
                    minutes_extra = i - (len(self.time_scale._timestamps) - 1)
                    ts = last_ts + timedelta(minutes=minutes_extra)

                label = ts.strftime("%I:%M %p")

                text_w, text_h = self.text_renderer.measure_text(
                    label,
                    scale=float(self.style.label_scale),
                )

                text_x = x - text_w * 0.5
                text_y = ay + ah - 6.0

                if text_x + text_w > max_allowed_x:
                    text_x = max_allowed_x - text_w

                self.text_renderer.render_text(
                    label,
                    text_x,
                    text_y,
                    scale=float(self.style.label_scale),
                    color=self.style.label_color,
                )
