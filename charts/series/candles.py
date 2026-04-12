from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from charts.scales.price_scale import PriceScale
from charts.scales.time_scale import TimeScale
from data.fake_ohlc import OHLC
from render.renderer import Renderer2D


@dataclass
class CandleStyle:
    """Acepta todos los parámetros que window.py le pasa"""
    up_color: Tuple[float, float, float, float] = (0.15, 0.80, 0.15, 1.0)
    down_color: Tuple[float, float, float, float] = (1.0, 0.10, 0.10, 1.0)

    wick_width_px: float = 1.2
    border_width_px: float = 1.0

    min_width_px: float = 0.8
    max_width_px: float = 120.0

    gap_extra_px: float = 5.5
    candle_width_extra_px: float = 4.0
    gap_base_px: float = 1.6
    gap_growth_per_px: float = 0.055
    gap_transition_start_px: float = 24.0
    gap_transition_softness_px: float = 38.0
    min_gap_px: float = 1.1
    max_gap_px: float = 45.0

    candle_body_ratio: float = 0.72
    draw_borders: bool = False
    clip_to_plot: bool = True
    x_offset_px: float = 0.0


class CandleSeries:
    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()

    def get_high_low(self, i: int) -> Tuple[float, float]:
        d = self.data[i]
        return d.h, d.l

    def _compute_bar_width(self, bar_spacing: float) -> float:
        st = self.style
        width = bar_spacing * st.candle_body_ratio + st.candle_width_extra_px
        width = max(st.min_width_px, min(width, bar_spacing * 0.95))
        return math.floor(width * 2.0) / 2.0

    def draw(
        self,
        renderer: Renderer2D,
        time_scale: TimeScale,
        price_scale: PriceScale,
        visible_start: int,
        visible_end: int,
    ) -> None:
        if visible_end < visible_start or not self.data:
            return

        st = self.style
        bar_spacing = time_scale.bar_spacing
        bar_width = self._compute_bar_width(bar_spacing)

        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]

            # ←←← CENTRO EXACTO (misma posición que la línea del grid)
            x_center = time_scale.get_aligned_x(i, crisp=True) + st.x_offset_px

            half = bar_width / 2.0
            left = math.floor(x_center - half)          # snap idéntico al grid

            # Clip rápido
            if left + bar_width < time_scale.view_x or left > time_scale.view_x + time_scale.view_w:
                continue

            y_o = price_scale.price_to_y(d.o)
            y_c = price_scale.price_to_y(d.c)
            y_h = price_scale.price_to_y(d.h)
            y_l = price_scale.price_to_y(d.l)

            is_up = d.c >= d.o
            color = st.up_color if is_up else st.down_color

            # Mecha (siempre centrada)
            renderer.draw_line_px(x_center, y_h, x_center, y_l, color, st.wick_width_px)

            # Cuerpo de la vela
            body_top = min(y_o, y_c)
            body_bottom = max(y_o, y_c)
            body_h = max(1.0, body_bottom - body_top)

            if body_h > 0.0:
                renderer.draw_rect_px(left, body_top, bar_width, body_h, color)

            if st.draw_borders:
                border_col = (0.0, 0.0, 0.0, 0.9) if is_up else (0.3, 0.3, 0.3, 0.9)
                renderer.draw_line_px(left, body_top, left + bar_width, body_top, border_col, 1.0)
                renderer.draw_line_px(left, body_bottom, left + bar_width, body_bottom, border_col, 1.0)