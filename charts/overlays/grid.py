# charts/overlays/grid.py
"""
GridOverlay
===========

Responsabilidad:
- Dibujar la grilla horizontal (precios).
- Dibujar la grilla vertical (tiempo).

Corrección importante de esta versión:
- La grilla vertical YA NO calcula sus ticks por su cuenta.
- Ahora reutiliza la lógica centralizada de TimeScale:
    - get_tick_indices(...)
    - get_aligned_x(...)

Con esto las líneas verticales quedan alineadas con:
- ticks del TimeAxis
- labels del TimeAxis
- zoom/pan del chart
- centro X usado por CandleSeries
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from charts.overlays.chart_overlay import ChartOverlay
from charts.scales.price_scale import PriceScale
from charts.scales.time_scale import TimeScale
from render.renderer import Renderer2D


@dataclass
class GridStyle:
    """
    Estilo visual de la grilla.
    """
    show_horizontal: bool = True
    show_vertical: bool = True

    # Grilla horizontal (precios)
    major_color: Tuple[float, float, float, float] = (0.22, 0.22, 0.22, 0.45)
    major_width: float = 1.0

    # Grilla vertical (tiempo)
    vertical_min_spacing_px: float = 90.0
    vertical_major_color: Tuple[float, float, float, float] = (0.30, 0.30, 0.30, 0.40)
    vertical_major_width: float = 1.1

    # Si True, ajusta las líneas verticales a subpíxel para mayor nitidez
    crisp_vertical_lines: bool = True


class GridOverlay:
    """
    Overlay encargado de dibujar la grilla del chart.

    Nota:
    - Este overlay no dibuja labels.
    - Solo líneas horizontales y verticales.
    - La sincronización con el eje de tiempo depende de usar
      exactamente los mismos índices de tick que TimeAxisOverlay.
    """

    def __init__(
        self,
        overlay: ChartOverlay,
        price_scale: PriceScale,
        time_scale: TimeScale,
        style: GridStyle | None = None,
    ) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.time_scale = time_scale
        self.style = style or GridStyle()

    def _get_vertical_tick_indices(self) -> list[int]:
        """
        Pide a TimeScale la lista de índices que deben usarse para la
        grilla vertical.

        Esto garantiza que el grid vertical use la misma base lógica
        que el TimeAxisOverlay.
        """
        return self.time_scale.get_tick_indices(
            min_spacing_px=self.style.vertical_min_spacing_px,
            extend_by_one=False,
        )

    def draw(self, renderer: Renderer2D) -> None:
        """
        Dibuja la grilla completa dentro del área de plot.
        """
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect

        if plot_w <= 0 or plot_h <= 0:
            return

        # ============================================================
        # 1) Grilla horizontal
        # ============================================================
        if self.style.show_horizontal:
            ticks = self.price_scale.get_ticks_ex(target_major=12, minor_divisions=0)
            for _, y in ticks.get("major", []):
                renderer.draw_line_px(
                    plot_x, y,
                    plot_x + plot_w, y,
                    color=self.style.major_color,
                    width=self.style.major_width,
                )

        # ============================================================
        # 2) Grilla vertical sincronizada con el eje de tiempo
        # ============================================================
        if self.style.show_vertical:
            tick_indices = self._get_vertical_tick_indices()

            for i in tick_indices:
                if i >= len(self.time_scale._timestamps):
                    break

                x = self.time_scale.get_aligned_x(
                    i,
                    crisp=self.style.crisp_vertical_lines,
                )

                renderer.draw_line_px(
                    x, plot_y,
                    x, plot_y + plot_h,
                    color=self.style.vertical_major_color,
                    width=self.style.vertical_major_width,
                )