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

    major_color: Tuple[float, float, float, float] = (
        0.10,
        0.10,
        0.10,
        0.90,
    )

    major_width: float = 1.0

    # ==================== LÍNEAS VERTICALES ====================
    show_vertical: bool = True

    vertical_min_spacing_px: float = 90.0

    vertical_major_color: Tuple[float, float, float, float] = (
        0.10,
        0.10,
        0.10,
        0.90,
    )

    vertical_major_width: float = 1.0

    # Mejora visual subpixel
    crisp_vertical_lines: bool = True


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
        self.overlay = overlay
        self.price_scale = price_scale
        self.time_scale = time_scale
        self.style = style or GridStyle()

    # ==========================================================
    # TICKS VERTICALES VISIBLES
    # ==========================================================
    def _get_vertical_tick_indices(self) -> list[int]:
        """
        Devuelve únicamente ticks realmente visibles.
        """

        vr = self.time_scale.get_visible_range()

        visible_start = max(0, int(vr.start_idx))
        visible_end = int(vr.end_idx)

        tick_indices = self.time_scale.get_tick_indices(
            min_spacing_px=self.style.vertical_min_spacing_px,
            extend_by_one=False,
        )

        return [
            i for i in tick_indices
            if visible_start <= i <= visible_end
        ]

    # ==========================================================
    # DRAW
    # ==========================================================
    def draw(self, renderer: Renderer2D) -> None:
        layout = self.overlay.get_layout()

        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        price_axis_x, _, _, _ = layout.price_axis_rect

        if plot_w <= 0 or plot_h <= 0:
            return

        # ======================================================
        # GRID HORIZONTAL
        # ======================================================
        if self.style.show_horizontal:

            ticks = self.price_scale.get_ticks_ex(
                target_major=5,
                minor_divisions=0,
            )

            for _, y in ticks.get("major", []):

                # Evitar líneas fuera del área visible
                if y < plot_y or y > plot_y + plot_h:
                    continue

                renderer.draw_line_px(
                    plot_x,
                    y,
                    plot_x + plot_w,
                    y,
                    color=self.style.major_color,
                    width=self.style.major_width,
                )

        # ======================================================
        # GRID VERTICAL
        # ======================================================
        if self.style.show_vertical:

            tick_indices = self._get_vertical_tick_indices()

            # Límite derecho real del área visible
            # evitando invadir el price axis
            max_x_allowed = price_axis_x - 2.0

            for i in tick_indices:

                if i >= len(self.time_scale._timestamps):
                    continue

                # Centro exacto de la vela
                x = self.time_scale.get_aligned_x(
                    i,
                    crisp=self.style.crisp_vertical_lines,
                )

                # Clip izquierdo
                if x < plot_x:
                    continue

                # Clip derecho
                max_x_allowed = price_axis_x - 2.0

                if x < plot_x:
                    continue

                if x > max_x_allowed:
                    continue

                renderer.draw_line_px(
                    x,
                    plot_y,
                    x,
                    plot_y + plot_h,
                    color=self.style.vertical_major_color,
                    width=self.style.vertical_major_width,
                )