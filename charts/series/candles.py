from __future__ import annotations
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

    # ==================== PARÁMETROS PRINCIPALES ====================
    base_candle_width_px: float = 18.0
    base_gap_px: float = 8.0

    # Límites de seguridad
    min_width_px: float = 0.8
    max_width_px: float = 120.0
    min_gap_px: float = 1.0
    max_gap_px: float = 60.0

    # Comportamiento al hacer zoom
    width_growth_factor: float = 0.45
    gap_growth_factor: float = 0.55

    # Colores opcionales para mechas
    wick_up_color: Optional[Tuple[float, float, float, float]] = None
    wick_down_color: Optional[Tuple[float, float, float, float]] = None

    # ==================== COLOR DEL BORDE Y MECHA ====================
    border_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.98)

    # Parámetros legacy
    candle_body_ratio: float = 0.72
    draw_borders: bool = True
    clip_to_plot: bool = True
    x_offset_px: float = 0.0
    thin_candle_threshold_px: float = 2.8


class CandleSeries:
    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()
        self._initial_bar_spacing: Optional[float] = None

    def reset_initial_spacing(self) -> None:
        self._initial_bar_spacing = None

    def get_high_low(self, i: int) -> Tuple[float, float]:
        d = self.data[i]
        return d.h, d.l

    def _compute_gap(self, bar_spacing: float) -> float:
        if self._initial_bar_spacing is None:
            self._initial_bar_spacing = bar_spacing
        ratio = bar_spacing / max(self._initial_bar_spacing, 1.0)
        gap = self.style.base_gap_px * (1.0 + self.style.gap_growth_factor * (ratio - 1.0))
        return max(self.style.min_gap_px, min(gap, self.style.max_gap_px))

    def _compute_bar_width(self, bar_spacing: float) -> float:
        if self._initial_bar_spacing is None:
            self._initial_bar_spacing = bar_spacing
        ratio = bar_spacing / max(self._initial_bar_spacing, 1.0)
        width = self.style.base_candle_width_px * (1.0 + self.style.width_growth_factor * (ratio - 1.0))

        gap = self._compute_gap(bar_spacing)
        max_possible = max(self.style.min_width_px, bar_spacing - gap - 2.0)
        width = max(self.style.min_width_px, min(width, self.style.max_width_px, max_possible))
        return width

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

            # Centro perfectamente alineado
            x_center = time_scale.get_aligned_x(i, crisp=True) + st.x_offset_px

            half = bar_width / 2.0
            left = x_center - half
            right = left + bar_width                     # ← Cálculo exacto para cerrar el borde derecho

            y_o = price_scale.price_to_y(d.o)
            y_c = price_scale.price_to_y(d.c)
            y_h = price_scale.price_to_y(d.h)
            y_l = price_scale.price_to_y(d.l)

            is_up = d.c >= d.o
            body_color = st.up_color if is_up else st.down_color

            # ==================== COLOR DE LA MECHA ====================
            if st.draw_borders:
                wick_color = st.border_color
            else:
                wick_color = body_color
                if is_up and st.wick_up_color is not None:
                    wick_color = st.wick_up_color
                elif not is_up and st.wick_down_color is not None:
                    wick_color = st.wick_down_color

            # MECHA
            renderer.draw_line_px(x_center+0.002, y_h, x_center, y_l, color=wick_color, width=st.wick_width_px)

            # CUERPO
            body_top = min(y_o, y_c)
            body_bottom = max(y_o, y_c)
            body_h = max(1.0, body_bottom - body_top)

            if body_h > 0.0 and bar_width >= st.thin_candle_threshold_px:
                renderer.draw_rect_px(left, body_top, bar_width, body_h, body_color)

                # ==================== BORDE DEL CUERPO ====================
                if st.draw_borders and bar_width > 1.2:
                    bw = st.border_width_px
                    # Bordes horizontales (arriba y abajo)
                    renderer.draw_line_px(left, body_top, right, body_top, st.border_color, bw)
                    renderer.draw_line_px(left, body_bottom, right, body_bottom, st.border_color, bw)
                    # Bordes verticales (izquierda y derecha) — ahora siempre se dibujan cuando hay borde
                    renderer.draw_line_px(left, body_top, left, body_bottom, st.border_color, bw)
                    renderer.draw_line_px(right, body_top, right, body_bottom+1.0, st.border_color, bw)