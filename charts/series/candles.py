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
    """
    Estilo visual y comportamiento de las velas japonesas.
    
    Todos los valores están en píxeles y son configurables.
    """
    # Colores
    up_color: Tuple[float, float, float, float] = (0.15, 0.80, 0.15, 1.0)   # Vela alcista (verde)
    down_color: Tuple[float, float, float, float] = (1.0, 0.10, 0.10, 1.0) # Vela bajista (rojo)

    # Grosor de líneas
    wick_width_px: float = 1.0      # Grosor de las mechas (wick)
    border_width_px: float = 1.0    # Grosor del borde del cuerpo

    # Tamaño de la vela
    min_width_px: float = 0.8
    max_width_px: float = 120.0

    # Espaciado entre velas
    min_gap_px: float = 1.2
    max_gap_px: float = 50.0
    gap_extra_px: float = 0.0           # Espacio extra fijo
    candle_width_extra_px: float = 0.0  # Ancho extra fijo

    # Control dinámico del gap según el zoom
    gap_base_px: float = 2.0
    gap_growth_per_px: float = 0.04
    gap_transition_start_px: float = 20.0
    gap_transition_softness_px: float = 25.0

    min_body_height_px: float = 1.0     # Altura mínima del cuerpo (evita velas invisibles)

    # Opciones de dibujo
    draw_borders: bool = True
    clip_to_plot: bool = False

    # ←←← NUEVO: Desplazamiento horizontal de las velas
    # Útil para alinear mejor el centro de la vela con las líneas verticales del grid.
    # Valor recomendado: 0.5 o 1.0
    x_offset_px: float = 0.0

class CandleSeries:
    """Serie principal de velas japonesas (OHLC)."""

    def __init__(self, data: List[OHLC], style: Optional[CandleStyle] = None) -> None:
        self.data = data
        self.style = style or CandleStyle()

    def __len__(self) -> int:
        return len(self.data)

    def get_high_low(self, i: int) -> Tuple[float, float]:
        """Devuelve el high y low de la vela en el índice i (usado por autoscale)."""
        d = self.data[i]
        return d.h, d.l

    def _compute_bar_width_and_gap(self, bar_spacing: float) -> Tuple[float, float]:
        """
        Calcula el ancho real de la vela y el gap entre velas.
        
        Este cálculo es dinámico según el zoom (bar_spacing).
        """
        st = self.style

        # Gap dinámico con transición suave
        if bar_spacing <= st.gap_transition_start_px:
            gap = st.gap_base_px
        else:
            softness = max(1.0, st.gap_transition_softness_px)
            t = min(1.0, (bar_spacing - st.gap_transition_start_px) / softness)
            extra = (bar_spacing - st.gap_transition_start_px) * st.gap_growth_per_px
            gap = st.gap_base_px * (1.0 - t) + (st.gap_base_px + extra) * t

        # Aplicar límites y extras
        gap = max(st.min_gap_px, min(st.max_gap_px, gap + st.gap_extra_px))

        bar_width = bar_spacing - gap
        bar_width += st.candle_width_extra_px
        bar_width = max(st.min_width_px, min(st.max_width_px, bar_width))

        # Redondeo a medio píxel para máxima nitidez y sincronía con el grid
        bar_width = math.floor(bar_width * 2.0) / 2.0

        return bar_width, gap

    def draw(
        self,
        renderer: Renderer2D,
        time_scale: TimeScale,
        price_scale: PriceScale,
        visible_start: int,
        visible_end: int,
    ) -> None:
        """
        Dibuja todas las velas visibles en el gráfico.
        
        Aquí se realiza el posicionamiento completo de cada vela:
        - Posición X → TimeScale
        - Posición Y → PriceScale
        - Ancho     → _compute_bar_width_and_gap()
        """
        if visible_end < visible_start or not self.data:
            return

        st = self.style
        bar_spacing = time_scale.bar_spacing

        # Calculamos ancho y gap una sola vez por frame
        bar_width, _ = self._compute_bar_width_and_gap(bar_spacing)

        # Límites horizontales de la vista (para optimizar)
        view_left = time_scale.view_x
        view_right = time_scale.view_x + time_scale.view_w

        for i in range(visible_start, visible_end + 1):
            if i < 0 or i >= len(self.data):
                continue

            d = self.data[i]

            # ====================== POSICIONAMIENTO HORIZONTAL ======================
            # Obtenemos la posición X centrada de la vela (ya alineada con el grid)
            x_center = time_scale.get_aligned_x(i, crisp=True)

            # ←←← APLICAMOS EL OFFSET PARA MOVER LAS VELAS A LA DERECHA
            # Esto es exactamente lo que pediste: mover la vela un poquito a la derecha
            # para que quede mejor alineada con las líneas verticales del grid.
            x_center += st.x_offset_px

            # ====================== VISIBILIDAD ======================
            half = bar_width / 2.0
            if x_center + half < view_left or x_center - half > view_right:
                continue

            # ====================== POSICIONAMIENTO VERTICAL ======================
            y_o = price_scale.price_to_y(d.o)
            y_c = price_scale.price_to_y(d.c)
            y_h = price_scale.price_to_y(d.h)
            y_l = price_scale.price_to_y(d.l)

            # ====================== DIBUJO ======================
            is_up = d.c >= d.o
            color = st.up_color if is_up else st.down_color

            left = x_center - bar_width / 2.0
            body_top = min(y_o, y_c)
            body_bottom = max(y_o, y_c)
            body_height = max(st.min_body_height_px, body_bottom - body_top)

            # Mecha (wick)
            renderer.draw_line_px(
                x_center, y_h,
                x_center, y_l,
                color=color,
                width=st.wick_width_px,
            )

            # Cuerpo de la vela
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

                renderer.draw_rect_px(
                    left, body_top,
                    bar_width, body_height,
                    color
                )