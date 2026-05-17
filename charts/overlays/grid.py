"""
charts/overlays/grid.py
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
    show_horizontal: bool = True

    major_color: Tuple[float, float, float, float] = (
        0.10, 0.10, 0.10, 0.90,
    )
    major_width: float = 1.0

    show_vertical: bool = True

    vertical_min_spacing_px: float = 90.0

    vertical_major_color: Tuple[float, float, float, float] = (
        0.10, 0.10, 0.10, 0.90,
    )
    vertical_major_width: float = 1.0

    crisp_vertical_lines: bool = True


class GridOverlay:
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
        Incluye ticks reales + virtuales del future space.
        """

        tick_indices = self.time_scale.get_tick_indices(
            min_spacing_px=self.style.vertical_min_spacing_px,
            extend_by_one=True,
        )

        vr = self.time_scale.get_visible_range()

        visible_start = int(vr.start_idx) - 2
        visible_end = int(vr.end_idx) + 30

        return [
            i for i in tick_indices
            if visible_start <= i <= visible_end
        ]

    def draw(self, renderer: Renderer2D) -> None:
        
        layout = self.overlay.get_layout()

        plot_x, plot_y, plot_w, plot_h = layout.plot_rect

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

            tick_indices = self.time_scale.get_tick_indices(
                        min_spacing_px=self.style.vertical_min_spacing_px,
                        extend_by_one=True,
                    )
            right_limit = plot_x + plot_w 

            for i in tick_indices:

                x = self.time_scale.get_aligned_x(
                    i,
                    crisp=self.style.crisp_vertical_lines,
                )

                # fuera del área visible izquierda
                if x < plot_x - 20:
                    continue

                # fuera del chart derecho real
                if x > right_limit:
                    continue

                renderer.draw_line_px(
                    x,
                    plot_y,
                    x,
                    plot_y + plot_h,
                    color=self.style.vertical_major_color,
                    width=self.style.vertical_major_width,
                )