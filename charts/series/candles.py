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
    up_color: Tuple[float, float, float, float] = (0.15, 0.80, 0.15, 1.0)
    down_color: Tuple[float, float, float, float] = (1.0, 0.10, 0.10, 1.0)

    wick_width_px: float = 1.0
    border_width_px: float = 1.0

    min_width_px: float = 1.0
    max_width_px: float = 120.0

    min_gap_px: float = 1.0
    max_gap_px: float = 40.0

    # === PARÁMETROS FÁCILES ===
    candle_body_ratio: float = 0.72      # ← 0.68 = gap más grande | 0.78 = gap más pequeño
    candle_width_extra_px: float = 4.0

    clip_to_plot: bool = True
    snap_x_to_half_pixel: bool = True
    draw_borders: bool = False


class CandleSeries:
    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()

    def __len__(self) -> int:
        return len(self.data)

    def get_high_low(self, i: int) -> Tuple[float, float]:
        d = self.data[i]
        return d.h, d.l

    def _compute_bar_width(self, bar_spacing: float) -> float:
        """Fórmula proporcional profesional (evita solapamiento en zoom in)"""
        st = self.style

        # Ancho de la vela proporcional al espacio total
        candle_width = bar_spacing * st.candle_body_ratio
        candle_width += st.candle_width_extra_px

        # Seguridad: nunca puede ser más ancho que el espacio disponible
        candle_width = min(candle_width, bar_spacing * 0.95)
        candle_width = max(st.min_width_px, candle_width)

        # Gap = resto
        gap = bar_spacing - candle_width
        gap = max(st.min_gap_px, min(st.max_gap_px, gap))

        final_width = candle_width

        if st.snap_x_to_half_pixel:
            final_width = math.floor(final_width * 2.0) / 2.0

        return final_width

    def _get_vertical_clip(self, price_scale: PriceScale) -> Tuple[float, float]:
        if hasattr(price_scale, "_usable_bounds"):
            y0, y1, _ = price_scale._usable_bounds()
            return min(y0, y1), max(y0, y1)
        return price_scale.view_y, price_scale.view_y + price_scale.view_h

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

        view_left = time_scale.view_x
        view_right = time_scale.view_x + time_scale.view_w
        clip_top, clip_bottom = self._get_vertical_clip(price_scale)

        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]
            x_center = time_scale.index_to_x(i)

            half = bar_width / 2.0 + 2.0
            if x_center + half < view_left or x_center - half > view_right:
                continue

            y_o = price_scale.price_to_y(d.o)
            y_c = price_scale.price_to_y(d.c)
            y_h = price_scale.price_to_y(d.h)
            y_l = price_scale.price_to_y(d.l)

            candle_top = min(y_h, y_l, y_o, y_c)
            candle_bottom = max(y_h, y_l, y_o, y_c)

            if candle_bottom < clip_top or candle_top > clip_bottom:
                continue

            if st.clip_to_plot:
                y_o = max(clip_top, min(clip_bottom, y_o))
                y_c = max(clip_top, min(clip_bottom, y_c))
                y_h = max(clip_top, min(clip_bottom, y_h))
                y_l = max(clip_top, min(clip_bottom, y_l))

            is_up = d.c >= d.o
            color = st.up_color if is_up else st.down_color

            if st.snap_x_to_half_pixel:
                x_center = math.floor(x_center) + 0.5

            left = x_center - bar_width / 2.0
            body_top = min(y_o, y_c)
            body_bottom = max(y_o, y_c)
            body_height = max(1.0, body_bottom - body_top)

            renderer.draw_line_px(x_center, y_h, x_center, y_l, color, st.wick_width_px)

            if body_height > 0.0:
                if st.draw_borders and st.border_width_px > 0:
                    border_color = (0.0, 0.0, 0.0, 0.9) if is_up else (0.2, 0.2, 0.2, 0.9)
                    renderer.draw_rect_px(
                        left - st.border_width_px,
                        body_top - st.border_width_px,
                        bar_width + 2 * st.border_width_px,
                        body_height + 2 * st.border_width_px,
                        border_color,
                    )
                renderer.draw_rect_px(left, body_top, bar_width, body_height, color)