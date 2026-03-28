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

    # GAP
    min_gap_px: float = 1.0
    max_gap_px: float = 40.0
    gap_extra_px: float = 0.0

    # ancho extra inicial de la vela
    candle_width_extra_px: float = 0.0

    # transición del gap con zoom
    gap_base_px: float = 2.0
    gap_growth_per_px: float = 0.02
    gap_transition_start_px: float = 14.0
    gap_transition_softness_px: float = 8.0

    min_body_height_px: float = 1.0

    snap_x_to_half_pixel: bool = True
    draw_borders: bool = True
    debug: bool = False


class CandleSeries:
    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()

    def __len__(self) -> int:
        return len(self.data)

    def get_high_low(self, i: int) -> Tuple[float, float]:
        d = self.data[i]
        return d.h, d.l

    def _smoothstep(self, t: float) -> float:
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    def _compute_zoom_gap(self, bar_spacing: float) -> float:
        st = self.style

        softness = max(1.0, st.gap_transition_softness_px)
        start = st.gap_transition_start_px
        end = start + softness

        if bar_spacing <= start:
            gap = st.gap_base_px
        elif bar_spacing >= end:
            extra_spacing = bar_spacing - start
            gap = st.gap_base_px + extra_spacing * st.gap_growth_per_px
        else:
            t = (bar_spacing - start) / softness
            blend = self._smoothstep(t)

            gap_before = st.gap_base_px
            extra_spacing = bar_spacing - start
            gap_after = st.gap_base_px + extra_spacing * st.gap_growth_per_px

            gap = gap_before * (1.0 - blend) + gap_after * blend

        gap = max(st.min_gap_px, min(st.max_gap_px, gap))
        return gap

    def _compute_bar_width(self, bar_spacing: float) -> float:
        st = self.style

        zoom_gap = self._compute_zoom_gap(bar_spacing)

        # el gap extra escala con el zoom para evitar el "colapso" visual
        gap_scale = max(1.0, bar_spacing / max(1.0, st.gap_transition_start_px))
        scaled_gap_extra = st.gap_extra_px * gap_scale

        target_gap = zoom_gap + scaled_gap_extra
        target_gap = max(st.min_gap_px, min(st.max_gap_px, target_gap))

        # ancho base
        base_width = bar_spacing - target_gap

        # ancho extra manual
        desired_width = base_width + st.candle_width_extra_px

        # respetar gap mínimo real
        max_width_allowed = bar_spacing - st.min_gap_px
        bar_width = min(desired_width, max_width_allowed)

        bar_width = max(st.min_width_px, min(st.max_width_px, bar_width))

        # snap visual
        bar_width = math.floor(bar_width * 2.0) / 2.0

        if st.debug:
            real_gap = max(0.0, bar_spacing - bar_width)
            print(
                "[CandleSeries] "
                f"bar_spacing={bar_spacing:.3f} "
                f"zoom_gap={zoom_gap:.3f} "
                f"gap_extra={st.gap_extra_px:.3f} "
                f"scaled_gap_extra={scaled_gap_extra:.3f} "
                f"target_gap={target_gap:.3f} "
                f"candle_extra={st.candle_width_extra_px:.3f} "
                f"real_gap={real_gap:.3f} "
                f"final_bar_width={bar_width:.3f}"
            )

        return bar_width

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

            is_up = d.c >= d.o
            color = st.up_color if is_up else st.down_color

            if st.snap_x_to_half_pixel:
                x_center = math.floor(x_center) + 0.5

            left = x_center - bar_width / 2.0
            top = min(y_o, y_c)
            bottom = max(y_o, y_c)
            body_height = max(st.min_body_height_px, bottom - top)

            # 1) borde primero
            if st.draw_borders and st.border_width_px > 0:
                border_color = (0.0, 0.0, 0.0, 0.9) if is_up else (0.2, 0.2, 0.2, 0.9)
                renderer.draw_rect_px(
                    left - st.border_width_px,
                    top - st.border_width_px,
                    bar_width + 2.0 * st.border_width_px,
                    body_height + 2.0 * st.border_width_px,
                    color=border_color,
                )

            # 2) mecha
            renderer.draw_line_px(
                x1=x_center,
                y1=y_h,
                x2=x_center,
                y2=y_l,
                color=color,
                width=st.wick_width_px,
            )

            # 3) cuerpo
            renderer.draw_rect_px(
                left,
                top,
                bar_width,
                body_height,
                color=color,
            )

            if st.debug:
                print(
                    "[CandleSeries.draw] "
                    f"i={i} x_center={x_center:.2f} "
                    f"bar_spacing={bar_spacing:.2f} "
                    f"bar_width={bar_width:.2f}"
                )