"""
charts/overlays/grid.py

Overlay responsable de dibujar el grid (rejilla) del gráfico:
- Líneas horizontales (niveles de precio)
- Líneas verticales (divisiones de tiempo)

Se alinea perfectamente con las velas gracias al TimeScale.
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
    """Estilo visual del grid del gráfico."""

    # ==================== LÍNEAS HORIZONTALES ====================
    show_horizontal: bool = True
    major_color: Tuple[float, float, float, float] = (0.10, 0.10, 0.10, 0.90)
    major_width: float = 1.0

    # ==================== LÍNEAS VERTICALES ====================
    show_vertical: bool = True
    vertical_min_spacing_px: float = 90.0          # Espaciado mínimo entre líneas verticales
    vertical_major_color: Tuple[float, float, float, float] = (0.10, 0.10, 0.10, 0.90)
    vertical_major_width: float = 1.0

    # Optimización visual
    crisp_vertical_lines: bool = True              # Usa round() + 0.5 para que queden nítidas


class GridOverlay:
    """
    Overlay que dibuja la rejilla del gráfico.

    Se encarga de:
    - Líneas horizontales alineadas con los ticks de precio
    - Líneas verticales alineadas exactamente con el centro de las velas
    """

    def __init__(
        self,
        overlay: ChartOverlay,
        price_scale: PriceScale,
        time_scale: TimeScale,
        style: GridStyle | None = None,
    ) -> None:
        """
        Inicializa el overlay del grid.

        Args:
            overlay: Referencia al ChartOverlay (para obtener el área de dibujo)
            price_scale: Escala de precios (para líneas horizontales)
            time_scale: Escala de tiempo (para líneas verticales)
            style: Configuración visual del grid (opcional)
        """
        self.overlay = overlay
        self.price_scale = price_scale
        self.time_scale = time_scale
        self.style = style or GridStyle()

    def _get_vertical_tick_indices(self) -> list[int]:
        """
        Devuelve los índices de las velas donde se deben dibujar las líneas verticales.

        Usa el TimeScale para respetar el espaciado mínimo configurado.
        """
        return self.time_scale.get_tick_indices(
            min_spacing_px=self.style.vertical_min_spacing_px,
            extend_by_one=False,
        )

    def draw(self, renderer: Renderer2D) -> None:
        """
        Dibuja el grid completo (horizontal + vertical) en el área del plot.

        Las líneas verticales se alinean perfectamente con el centro de cada vela
        gracias a `time_scale.get_aligned_x(..., crisp=True)`.
        """
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect

        # Si el área de dibujo es inválida, no hacemos nada
        if plot_w <= 0 or plot_h <= 0:
            return

        # ====================== LÍNEAS HORIZONTALES ======================
        if self.style.show_horizontal:
            # Obtenemos los ticks mayores de la escala de precios
            ticks = self.price_scale.get_ticks_ex(target_major=5, minor_divisions=0)
            for _, y in ticks.get("major", []):
                renderer.draw_line_px(
                    plot_x, y,
                    plot_x + plot_w, y,
                    color=self.style.major_color,
                    width=self.style.major_width,
                )
        
        # ====================== LÍNEAS VERTICALES ======================
        if self.style.show_vertical:
            tick_indices = self._get_vertical_tick_indices()

            for i in tick_indices:
                # Evitar índices fuera de rango
                if i >= len(self.time_scale._timestamps):
                    break

                # Obtenemos la posición X exacta (centro de la vela)
                x = self.time_scale.get_aligned_x(i, crisp=self.style.crisp_vertical_lines)

                renderer.draw_line_px(
                    x, plot_y,
                    x, plot_y + plot_h,
                    color=self.style.vertical_major_color,
                    width=self.style.vertical_major_width,
                )