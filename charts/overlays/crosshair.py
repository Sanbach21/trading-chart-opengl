from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from render.renderer import Renderer2D, Color
from app.input import InputState
from charts.series.candles import CandleSeries
from charts.overlays.chart_overlay import ChartOverlay


@dataclass
class CrosshairStyle:
    color: Tuple[float, float, float, float] = (0.9, 0.9, 0.9, 0.9)
    width: float = 1.0
    snap_to_bar: bool = False


class CrosshairOverlay:
    def __init__(
        self,
        overlay: ChartOverlay,
        input_state: InputState,
        series: CandleSeries,
        style: CrosshairStyle | None = None,
    ) -> None:
        self.overlay = overlay
        self.input = input_state
        self.series = series
        self.style = style or CrosshairStyle()

        self.snap_enabled = True
        self.snap_tolerance_px = 30.0

    def draw(self, renderer: Renderer2D) -> None:
        layout = self.overlay.get_layout()
        px, py, pw, ph = layout.plot_rect
        if pw <= 0 or ph <= 0:
            return

        mx = float(self.input.mouse.x)
        my = float(self.input.mouse.y)

        inside = (px <= mx <= px + pw) and (py <= my <= py + ph)
        if not inside:
            return

        col = Color(*self.style.color)

        # Snap a la vela más cercana
        snap_x = mx
        if self.snap_enabled:
            vr = self.overlay.time_scale.get_visible_range()
            vs = max(0, int(vr.start_idx))
            ve = min(len(self.series.data) - 1, int(vr.end_idx))

            if ve >= vs:
                closest_idx = None
                min_dist = 1e18

                for i in range(vs, ve + 1):
                    cx = float(self.overlay.time_scale.index_to_x(i))
                    d = abs(cx - mx)
                    if d < min_dist:
                        min_dist = d
                        closest_idx = i

                if closest_idx is not None and min_dist <= self.snap_tolerance_px:
                    snap_x = float(self.overlay.time_scale.index_to_x(closest_idx))

        # Líneas del crosshair
        renderer.draw_line_px(
            snap_x,
            py,
            snap_x,
            py + ph,
            color=col,
            width=float(self.style.width),
        )

        renderer.draw_line_px(
            px,
            my,
            px + pw,
            my,
            color=col,
            width=float(self.style.width),
        )