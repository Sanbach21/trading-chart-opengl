"""
charts/overlays/grid.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Any, List
import math

from charts.overlays.chart_overlay import ChartOverlay
from charts.scales.time_scale import TimeScale
from render.renderer import Renderer2D


@dataclass
class GridStyle:
    # Horizontal (precio)
    show_horizontal: bool = True
    major_color: Tuple[float, float, float, float] = (0.18, 0.18, 0.18, 0.40)
    major_width: float = 1.0

    # Vertical (tiempo)
    show_vertical: bool = True
    vertical_min_spacing_px: float = 90.0
    vertical_major_color: Tuple[float, float, float, float] = (0.18, 0.18, 0.18, 0.40)
    vertical_major_width: float = 1.0
    crisp_vertical_lines: bool = True


class GridOverlay:
    """
    Grid independiente alineado con el LocalPriceScale.
    """

    def __init__(
        self,
        overlay: ChartOverlay,
        price_scale: Any,            # 👈 ahora acepta LocalPriceScale
        time_scale: TimeScale,
        style: GridStyle | None = None,
    ) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.time_scale = time_scale
        self.style = style or GridStyle()

    # ─────────────────────────────────────────────
    # NICE STEP (MISMO QUE AXIS)
    # ─────────────────────────────────────────────

    def _nice_step(self, raw_step: float) -> float:
        if raw_step <= 0.0 or not math.isfinite(raw_step):
            return 1.0

        exp = math.floor(math.log10(raw_step))
        frac = raw_step / (10 ** exp)

        if frac < 1.5:
            nice = 1.0
        elif frac < 3.0:
            nice = 2.0
        elif frac < 7.0:
            nice = 5.0
        else:
            nice = 10.0

        return nice * (10 ** exp)

    # ─────────────────────────────────────────────
    # HORIZONTAL GRID (PRECIO)
    # ─────────────────────────────────────────────

    def _generate_price_lines(self, plot_y: float, plot_h: float) -> List[float]:
        """
        Genera líneas horizontales usando la MISMA lógica que el axis.
        """
        min_p = float(self.price_scale._min_price)
        max_p = float(self.price_scale._max_price)

        rng = max_p - min_p
        if rng <= 1e-12:
            return []

        step = self._nice_step(rng / 5.0)

        start = math.floor(min_p / step) * step
        end = math.ceil(max_p / step) * step

        ys = []

        p = start
        safety = 0
        while p <= end + step * 0.5:
            y = self.price_scale.price_to_y(p)
            ys.append(float(y))

            p += step
            safety += 1
            if safety > 200:
                break

        return ys

    # ─────────────────────────────────────────────
    # DRAW
    # ─────────────────────────────────────────────

    def draw(self, renderer: Renderer2D) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect

        if plot_w <= 0 or plot_h <= 0:
            return

        # ======================================================
        # GRID HORIZONTAL (PRECIO)
        # ======================================================

        if self.style.show_horizontal:
            ys = self._generate_price_lines(plot_y, plot_h)

            for y in ys:
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
        # GRID VERTICAL (TIEMPO)
        # ======================================================

        if self.style.show_vertical:
            tick_indices = self.time_scale.get_tick_indices(
                min_spacing_px=self.style.vertical_min_spacing_px,
                extend_by_one=False,
            )

            for i in tick_indices:
                x = self.time_scale.get_aligned_x(
                    i,
                    crisp=bool(self.style.crisp_vertical_lines),
                )

                if x > self.time_scale.get_right_draw_limit() + 1.0:
                    break

                renderer.draw_line_px(
                    x,
                    plot_y,
                    x,
                    plot_y + plot_h,
                    color=self.style.vertical_major_color,
                    width=self.style.vertical_major_width,
                )