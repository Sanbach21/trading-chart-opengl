# charts/overlays/crosshair.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from render.renderer import Renderer2D, Color
from charts.overlays.chart_overlay import ChartOverlay, Rect


@dataclass
class CrosshairStyle:
    color: Tuple[float, float, float, float] = (0.9, 0.9, 0.9, 0.6)
    width: float = 1.0
    snap_to_bar: bool = False  # futura fase: alinear a centro de barra


class CrosshairOverlay:
    def __init__(
        self,
        overlay: ChartOverlay,
        input_state,           # app.input.InputState
        style: CrosshairStyle | None = None
    ) -> None:
        self.overlay = overlay
        self.input = input_state
        self.style = style or CrosshairStyle()

    def draw(self, renderer: Renderer2D) -> None:
        layout = self.overlay.get_layout()
        plot_rect = layout.plot_rect  # (x, y, w, h)
        px, py, pw, ph = plot_rect

        if pw <= 0 or ph <= 0:
            return

        mx = self.input.mouse.x
        my = self.input.mouse.y

        # ¿Está el ratón dentro del área de plot?
        inside = (px <= mx <= px + pw) and (py <= my <= py + ph)
        if not inside:
            return

        col = Color(*self.style.color)

        # Línea vertical
        renderer.draw_line_px(
            mx, py,           # desde arriba del plot
            mx, py + ph,      # hasta abajo del plot
            color=col,
            width=self.style.width
        )

        # Línea horizontal
        renderer.draw_line_px(
            px, my,           # desde izquierda del plot
            px + pw, my,      # hasta derecha del plot
            color=col,
            width=self.style.width
        )