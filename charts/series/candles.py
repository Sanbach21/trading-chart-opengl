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
   # ============================================================
    # ANCHO DINÁMICO DE VELA (con zonas A, B, C)
    # ============================================================
    def _compute_bar_width(self, bar_spacing: float) -> float:
        if self._initial_bar_spacing is None:
            self._initial_bar_spacing = bar_spacing

        st = self.style
        base = max(self._initial_bar_spacing, 1.0)
        ratio = bar_spacing / base

        # ─────────────────────────────────────────────
        # ZONA A — Zoom-out extremo
        # ─────────────────────────────────────────────
        if ratio < 0.55:
            width = max(1.0, bar_spacing * 0.35)

        # ─────────────────────────────────────────────
        # ZONA B — Zoom normal
        # ─────────────────────────────────────────────
        elif ratio < 1.40:
            smooth = ratio ** 0.85
            width = st.base_candle_width_px * smooth

        # ─────────────────────────────────────────────
        # ZONA C — Zoom-in extremo
        # ─────────────────────────────────────────────
        else:
            smooth = ratio ** 1.22
            width = st.base_candle_width_px * smooth

        # Limitar según gap
        gap = self._compute_gap(bar_spacing)
        max_possible = max(st.min_width_px, bar_spacing - gap - 2.0)

        width = max(
            st.min_width_px,
            min(width, st.max_width_px, max_possible),
        )

        # ─────────────────────────────────────────────
        # CORRECCIÓN PROFESIONAL: ancho PAR (even)
        # ─────────────────────────────────────────────
        w = int(round(width))
        if w % 2 != 0:
            w += 1  # forzar par
        w = max(2, w)

        return float(w) 

    def _compute_gap(self, bar_spacing: float) -> float:
        """
        Gap dinámico entre velas según el zoom horizontal.
        """

        if self._initial_bar_spacing is None:
            self._initial_bar_spacing = bar_spacing

        st = self.style
        base = max(self._initial_bar_spacing, 1.0)
        ratio = bar_spacing / base

        # ─────────────────────────────────────────────
        # ZONA A — Zoom-out extremo
        # ─────────────────────────────────────────────
        if ratio < 0.55:
            return max(0.0, bar_spacing * 0.15)

        # ─────────────────────────────────────────────
        # ZONA B — Zoom normal
        # ─────────────────────────────────────────────
        elif ratio < 1.40:
            smooth = ratio ** 0.65
            gap = st.base_gap_px * smooth
            return max(st.min_gap_px, min(gap, st.max_gap_px))

        # ─────────────────────────────────────────────
        # ZONA C — Zoom-in extremo (CORREGIDA)
        # ─────────────────────────────────────────────
        else:
            # Gap reducido para evitar huecos exagerados
            # ratio=1.4 → gap ~ base_gap * 0.8
            # ratio=2.0 → gap ~ base_gap * 0.55
            # ratio=3.0 → gap ~ base_gap * 0.40
            smooth = ratio ** -0.55
            gap = st.base_gap_px * smooth
            return max(st.min_gap_px, min(gap, st.max_gap_px))


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

        if visible_end < visible_start or not self.data:
            return

        st = self.style
        bar_spacing = float(time_scale.bar_spacing)
        bar_width = self._compute_bar_width(bar_spacing)

        right_limit = time_scale.get_right_draw_limit()

        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]

            # ============================================================
            # CENTRO REAL DE LA VELA (sin jitter)
            # ============================================================
            x_center = float(time_scale.index_to_x(i)) + float(st.x_offset_px)

            # Alineamiento suave estilo TradingView
            x_center = float(int(x_center) + 0.5)

            # Si está fuera por la derecha, cortar
            if x_center > right_limit + 2.0:
                break

            # ============================================================
            # CÁLCULO DE LADOS CENTRADOS
            # ============================================================
            half = bar_width * 0.5
            left = x_center - half
            right = x_center + half

            # ============================================================
            # CONVERSIÓN DE PRECIOS A Y
            # ============================================================
            y_o = float(price_scale.price_to_y(float(d.o)))
            y_c = float(price_scale.price_to_y(float(d.c)))
            y_h = float(price_scale.price_to_y(float(d.h)))
            y_l = float(price_scale.price_to_y(float(d.l)))

            # clipping vertical
            if st.clip_to_plot:
                try:
                    plot_x, plot_y, plot_w, plot_h = price_scale.get_viewport()
                except Exception:
                    plot_y = 0.0
                    plot_h = 10_000.0

                if not self._is_candle_visible_vertically(y_h, y_l, plot_y, plot_h):
                    continue

            # ============================================================
            # COLORES
            # ============================================================
            is_up = d.c >= d.o
            body_color = st.up_color if is_up else st.down_color

            wick_color = st.border_color if st.draw_borders else body_color
            if is_up and st.wick_up_color is not None:
                wick_color = st.wick_up_color
            elif (not is_up) and st.wick_down_color is not None:
                wick_color = st.wick_down_color

            # ============================================================
            # MECHA (siempre centrada)
            # ============================================================
            renderer.draw_line_px(
                x_center,
                y_h,
                x_center,
                y_l,
                color=wick_color,
                width=float(st.wick_width_px),
            )

            # ============================================================
            # CUERPO
            # ============================================================
            body_top = min(y_o, y_c)
            body_bottom = max(y_o, y_c)
            body_h = max(1.0, body_bottom - body_top)

            if bar_width < float(st.thin_candle_threshold_px):
                # vela muy fina → línea vertical centrada
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

            # ============================================================
            # BORDES (centrados correctamente)
            # ============================================================
            if st.draw_borders and bar_width > 1.2:
                bw = float(st.border_width_px)

                # horizontal superior / inferior
                renderer.draw_line_px(left, body_top, right, body_top, st.border_color, bw)
                renderer.draw_line_px(left, body_bottom, right + 1.0, body_bottom, st.border_color, bw)

                # vertical izquierdo / derecho
                renderer.draw_line_px(left, body_top, left, body_bottom, st.border_color, bw)
                renderer.draw_line_px(right, body_top, right, body_bottom, st.border_color, bw)
