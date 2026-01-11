# charts/series/candles.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional

from charts.scales.time_scale import TimeScale
from charts.scales.price_scale import PriceScale
from data.fake_ohlc import OHLC
from render.renderer import Renderer2D, Color


@dataclass
class CandleStyle:
    up_color: Tuple[float, float, float, float] = (0.10, 0.80, 0.35, 1.0)
    down_color: Tuple[float, float, float, float] = (0.90, 0.25, 0.25, 1.0)
    wick_width_px: float = 1.0


class CandleSeries:
    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()

    def __len__(self) -> int:
        return len(self.data)

    def get_high_low(self, i: int) -> Tuple[float, float]:
        d = self.data[i]
        return d.h, d.l

    def draw(self, renderer: Renderer2D, time_scale: TimeScale, price_scale: PriceScale, visible_start: int, visible_end: int) -> None:
        """
        Dibuja velas japonesas con ancho dinámico y gap mínimo para evitar overlapping en zoom máximo.
        """
        st = self.style

        # Constantes para evitar overlapping
        MIN_BAR_WIDTH = 4.0  # píxeles mínimos por vela
        MIN_GAP =1.0       # píxeles mínimos entre velas

        if visible_end < visible_start:
            return

        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]
            x_center = time_scale.index_to_x(i)

            y_o = price_scale.price_to_y(d.o)
            y_c = price_scale.price_to_y(d.c)
            y_h = price_scale.price_to_y(d.h)
            y_l = price_scale.price_to_y(d.l)

            is_up = d.c >= d.o
            color = st.up_color if is_up else st.down_color

            # Calcular ancho dinámico basado en bar_spacing del TimeScale
            bar_spacing = max(1.0, time_scale.bar_spacing)
            bar_width_raw = bar_spacing * 0.5  # 80% del spacing para dejar gap

            # Clamp con mínimos para evitar overlapping
            bar_width = max(MIN_BAR_WIDTH, bar_width_raw)
            gap = bar_spacing - bar_width
            if gap < MIN_GAP:
                bar_width = bar_spacing - MIN_GAP
                bar_width = max(MIN_BAR_WIDTH, bar_width)  # Asegurar mínimo

            # Posiciones del cuerpo
            left = x_center - bar_width / 2
            right = x_center + bar_width / 2

            # Wick (línea vertical)
            renderer.draw_line_px(
                x_center, y_h,
                x_center, y_l,
                color=color,
                width=st.wick_width_px,
            )

            # Body (rect)
            top = min(y_o, y_c)
            bot = max(y_o, y_c)
            h = max(1.0, bot - top)

            renderer.draw_rect_px(
                left, top,
                bar_width, h,
                color=color
            )