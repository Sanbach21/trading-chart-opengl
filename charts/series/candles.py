# charts/series/candles.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional

from charts.scales.time_scale import TimeScale
from charts.scales.price_scale import PriceScale
from data.fake_ohlc import OHLC



@dataclass
class CandleStyle:
    body_width_px: float = 8.0
    wick_width_px: float = 1.0
    gap_px: float = 3.0  # espacio entre velas
    up_color: Tuple[float, float, float, float] = (0.10, 0.80, 0.35, 1.0)
    down_color: Tuple[float, float, float, float] = (0.90, 0.25, 0.25, 1.0)


class CandleSeries:
    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()

    def __len__(self) -> int:
        return len(self.data)

    def get_high_low(self, i: int) -> Tuple[float, float]:
        d = self.data[i]
        return d.h, d.l

    def draw(self, r, time_scale: TimeScale, price_scale: PriceScale, visible_start: int, visible_end: int) -> None:
        """
        r: Renderer2D (o adapter que tenga draw_rect_px / draw_line_px)
        visible_start/end: índices visibles
        """
        st = self.style

        # Para una primera versión, definimos el “step” (ancho + gap)
        step = st.body_width_px + st.gap_px

        # fallback si no hay nada visible
        if visible_end < visible_start:
            return

        # Dibujo: candle por candle
        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]
            x_center = time_scale.index_to_x(i)  # lo implementamos abajo si falta

            y_o = price_scale.price_to_y(d.o)
            y_c = price_scale.price_to_y(d.c)
            y_h = price_scale.price_to_y(d.h)
            y_l = price_scale.price_to_y(d.l)

            is_up = d.c >= d.o
            color = st.up_color if is_up else st.down_color

            # Wick (línea vertical)
            r.draw_line_px(
                x_center, y_h,
                x_center, y_l,
                color=color,
                width=st.wick_width_px,
            )

            # Body (rect)
            top = min(y_o, y_c)
            bot = max(y_o, y_c)
            h = max(1.0, bot - top)

            x0 = x_center - st.body_width_px * 0.5

            r.draw_rect_px(
                x0, top,
                st.body_width_px, h,
                color=color
            )
