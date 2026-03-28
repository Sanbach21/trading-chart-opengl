from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.input import InputState
from charts.overlays.chart_overlay import ChartOverlay
from charts.series.candles import CandleSeries
from render.renderer import Color, Renderer2D


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
        self.snap_tolerance_px = 40.0

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

        snap_x = mx

        if self.snap_enabled and len(self.series.data) > 0:
            vr = self.overlay.time_scale.get_visible_range()
            vs = max(0, int(vr.start_idx))
            ve = min(len(self.series.data) - 1, int(vr.end_idx))

            if ve >= vs:
                closest_idx = None
                min_dist = float("inf")

                for i in range(vs, ve + 1):
                    cx = float(self.overlay.time_scale.index_to_x(i))

                    # ignorar centros completamente fuera del área visible
                    if cx < px - 100.0 or cx > px + pw + 100.0:
                        continue

                    d = abs(cx - mx)
                    if d < min_dist:
                        min_dist = d
                        closest_idx = i

                if closest_idx is not None and min_dist <= self.snap_tolerance_px:
                    snap_x = float(self.overlay.time_scale.index_to_x(closest_idx))
                    snap_x = max(px, min(px + pw, snap_x))

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