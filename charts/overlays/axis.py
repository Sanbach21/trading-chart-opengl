from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional, Set

import math


Rect = Tuple[float, float, float, float]


# ============================================================
# PRICE AXIS
# ============================================================
@dataclass
class PriceAxisStyle:
    padding_px: float = 6.0
    tick_major_len: float = 7.0
    tick_minor_len: float = 4.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    decimals: int = 2
    target_major_ticks: int = 12
    label_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    label_scale: float = 1.0
    min_label_gap_px: float = 5.0


class PriceAxisOverlay:
    def __init__(self, overlay, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.text_renderer = None
        self.style = PriceAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def _get_side(self) -> str:
        return (self.overlay.config["price_axis"].get("side", "right") or "right").lower()

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect

        if aw <= 0 or ah <= 0:
            return

        side = self._get_side()
        ticks = self.price_scale.get_ticks_ex(target_major=self.style.target_major_ticks)

        for price, y in ticks.get("major", []):
            y = float(y)
            if not (plot_y <= y <= plot_y + plot_h):
                continue

            # Tick
            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len

            r.draw_line_px(x1, y, x2, y,
                           color=self.style.tick_color,
                           width=float(self.style.tick_width))

            # Label
            if self.text_renderer is not None:
                label = f"{price:.{self.style.decimals}f}"
                text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
                text_y = y + text_h * 0.3

                if side == "left":
                    text_x = ax + aw - self.style.padding_px - text_w
                else:
                    text_x = ax + self.style.tick_major_len + self.style.padding_px

                text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))
                self.text_renderer.render_text(
                    label, text_x, text_y,
                    scale=self.style.label_scale,
                    color=self.style.label_color
                )


# ============================================================
# TIME AXIS
# ============================================================
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
    def __init__(self, overlay, time_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.time_scale = time_scale
        self.text_renderer = None
        self.style = TimeAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        ax, ay, aw, ah = layout.time_axis_rect

        if aw <= 0 or ah <= 0:
            return

        # Usamos extend_by_one=True para que las etiquetas entren/salgan suavemente
        tick_indices = self.time_scale.get_tick_indices(
            min_spacing_px=self.style.min_label_spacing_px,
            extend_by_one=True
        )

        # Adaptamos el formato según el zoom (velas muy pequeñas → mostramos segundos)
        bar_spacing = self.time_scale.bar_spacing
        show_seconds = bar_spacing < 9.0

        for i in tick_indices:
            if i >= len(self.time_scale._timestamps):
                continue

            # Misma posición exacta que velas y grid
            x = self.time_scale.get_aligned_x(i, crisp=True)

            # Tick
            y1 = ay
            y2 = ay + self.style.tick_len
            r.draw_line_px(x, y1, x, y2,
                           color=self.style.tick_color,
                           width=float(self.style.tick_width))

            # Label
            if self.text_renderer is not None:
                ts = self.time_scale._timestamps[i]
                label = ts.strftime("%H:%M:%S" if show_seconds else "%H:%M")

                text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
                text_x = x - text_w * 0.5
                text_y = ay + ah - 6.0

                # Clipping muy permisivo → las etiquetas aparecen/desaparecen suavemente
                label_center = text_x + text_w * 0.5
                if ax - 50 <= label_center <= ax + aw + 50:
                    self.text_renderer.render_text(
                        label, text_x, text_y,
                        scale=self.style.label_scale,
                        color=self.style.label_color
                    )