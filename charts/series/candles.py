from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from charts.scales.time_scale import TimeScale
from data.fake_ohlc import OHLC
from render.renderer import Renderer2D


@dataclass
class CandleStyle:
    up_color: Tuple[float, float, float, float] = (0.15, 0.80, 0.15, 1.0)
    down_color: Tuple[float, float, float, float] = (1.0, 0.10, 0.10, 1.0)

    wick_width_px: float = 1.0
    border_width_px: float = 1.0

    base_candle_width_px: float = 8.0
    base_gap_px: float = 2.0

    min_width_px: float = 1.40
    max_width_px: float = 220.0
    min_gap_px: float = 0.0
    max_gap_px: float = 60.0

    width_growth_factor: float = 0.45
    gap_growth_factor: float = 0.55

    wick_up_color: Optional[Tuple[float, float, float, float]] = None
    wick_down_color: Optional[Tuple[float, float, float, float]] = None

    border_color: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.98)

    candle_body_ratio: float = 0.72
    draw_borders: bool = True
    clip_to_plot: bool = True
    x_offset_px: float = 0.0
    thin_candle_threshold_px: float = 1.2


class CandleSeries:
    """
    Serie de velas OHLC.

    Esta versión queda desacoplada de PriceScale clásico.
    Espera recibir en draw() una escala compartida que implemente:

        price_to_y(price: float) -> float

    Idealmente esa escala será tu nuevo LocalPriceScale compartido
    por axis/grid/crosshair/candles.
    """

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
        """
        Gap dinámico entre velas.

        - Zoom normal / zoom out: gap crece moderadamente.
        - Zoom in fuerte: gap cae mucho e incluso puede solaparse un poco.
        """
        if self._initial_bar_spacing is None:
            self._initial_bar_spacing = bar_spacing

        base = max(self._initial_bar_spacing, 1.0)

        if bar_spacing >= base * 0.9:
            ratio = bar_spacing / base
            gap = self.style.base_gap_px * (
                1.0 + self.style.gap_growth_factor * (ratio - 1.0)
            )
            return max(self.style.min_gap_px, min(gap, self.style.max_gap_px))

        progress = bar_spacing / base
        gap = self.style.base_gap_px * (progress ** 1.6) * 2.5

        # Permitimos un poco de solapamiento para zoom in extremo
        return max(-2.0, gap)

    def _compute_bar_width(self, bar_spacing: float) -> float:
        """
        Ancho dinámico de la vela según el zoom horizontal.
        """
        if self._initial_bar_spacing is None:
            self._initial_bar_spacing = bar_spacing

        base = max(self._initial_bar_spacing, 1.0)
        ratio = bar_spacing / base

        width = self.style.base_candle_width_px * (
            1.0 + self.style.width_growth_factor * (ratio - 1.0)
        )

        gap = self._compute_gap(bar_spacing)
        max_possible = max(self.style.min_width_px, bar_spacing - gap - 2.0)

        width = max(
            self.style.min_width_px,
            min(width, self.style.max_width_px, max_possible),
        )

        # Redondeo fuerte para estabilidad visual
        return float(round(width))

    def _is_candle_visible_vertically(
        self,
        y_h: float,
        y_l: float,
        plot_y: float,
        plot_h: float,
    ) -> bool:
        """
        Determina si la vela toca visualmente el rectángulo del plot.
        """
        top = min(y_h, y_l)
        bottom = max(y_h, y_l)
        plot_bottom = plot_y + plot_h

        return not (bottom < plot_y or top > plot_bottom)

    def draw(
        self,
        renderer: Renderer2D,
        time_scale: TimeScale,
        price_scale: Any,
        visible_start: int,
        visible_end: int,
    ) -> None:
        """
        Dibuja las velas visibles.

        Parámetros:
        - renderer: Renderer2D
        - time_scale: TimeScale del chart
        - price_scale: CUALQUIER escala que exponga price_to_y(price)
        - visible_start / visible_end: rango visible de índices
        """
        if visible_end < visible_start or not self.data:
            return

        st = self.style
        bar_spacing = float(time_scale.bar_spacing)
        bar_width = self._compute_bar_width(bar_spacing)

        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]

            x_center = float(time_scale.get_aligned_x(i, crisp=True)) + float(st.x_offset_px)

            # cortar si ya nos pasamos del límite de dibujo
            if x_center > time_scale.get_right_draw_limit() + 2.0:
                break

            half = bar_width / 2.0
            left = float(round(x_center - half))
            right = left + bar_width

            # Conversión Y usando la escala compartida
            y_o = float(price_scale.price_to_y(float(d.o)))
            y_c = float(price_scale.price_to_y(float(d.c)))
            y_h = float(price_scale.price_to_y(float(d.h)))
            y_l = float(price_scale.price_to_y(float(d.l)))

            # Clipping vertical simple
            if st.clip_to_plot:
                try:
                    plot_x, plot_y, plot_w, plot_h = price_scale.get_viewport()
                except Exception:
                    plot_y = 0.0
                    plot_h = 10_000.0

                if not self._is_candle_visible_vertically(y_h, y_l, plot_y, plot_h):
                    continue

            is_up = d.c >= d.o
            body_color = st.up_color if is_up else st.down_color

            # Color de la mecha
            wick_color = st.border_color if st.draw_borders else body_color
            if is_up and st.wick_up_color is not None:
                wick_color = st.wick_up_color
            elif (not is_up) and st.wick_down_color is not None:
                wick_color = st.wick_down_color

            # ─────────────────────────────
            # Mecha
            # ─────────────────────────────
            renderer.draw_line_px(
                x_center,
                y_h,
                x_center,
                y_l,
                color=wick_color,
                width=float(st.wick_width_px),
            )

            # ─────────────────────────────
            # Cuerpo
            # ─────────────────────────────
            body_top = min(y_o, y_c)
            body_bottom = max(y_o, y_c)
            body_h = max(1.0, body_bottom - body_top)

            # Para velas muy finas, dibuja línea vertical en vez de rectángulo
            if bar_width < float(st.thin_candle_threshold_px):
                renderer.draw_line_px(
                    x_center,
                    body_top,
                    x_center,
                    body_bottom,
                    color=body_color,
                    width=max(1.0, bar_width),
                )
            else:
                renderer.draw_rect_px(
                    left,
                    body_top,
                    right - left,
                    body_h,
                    body_color,
                )

            # ─────────────────────────────
            # Bordes
            # ─────────────────────────────
            if st.draw_borders and bar_width > 1.2:
                bw = float(st.border_width_px)
                border_right = right + (1.0 if bar_width >= 3.0 else 0.0)

                # horizontal superior / inferior
                renderer.draw_line_px(
                    left, body_top,
                    border_right, body_top,
                    st.border_color, bw
                )
                renderer.draw_line_px(
                    left, body_bottom,
                    border_right, body_bottom,
                    st.border_color, bw
                )

                # vertical izquierdo / derecho
                renderer.draw_line_px(
                    left, body_top,
                    left, body_bottom,
                    st.border_color, bw
                )
                renderer.draw_line_px(
                    right, body_top,
                    right, body_bottom,
                    st.border_color, bw
                )