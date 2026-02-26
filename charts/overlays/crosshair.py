# charts/overlays/crosshair.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from render.renderer import Renderer2D, Color
from app.input import InputState
from charts.series.candles import CandleSeries
from charts.overlays.chart_overlay import ChartOverlay
from render.text.msdf_text import MsdfTextStyle


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
        style: CrosshairStyle | None = None
    ) -> None:
        self.overlay = overlay
        self.input = input_state
        self.series = series
        self.style = style or CrosshairStyle()

        self.snap_enabled = True
        self.snap_tolerance_px = 30.0

        self.font = None  # se asigna desde window.run()

    def draw(self, renderer: Renderer2D) -> None:
        if self.font is None:
            return

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

        # SNAP: vela más cercana
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

        # líneas
        renderer.draw_line_px(snap_x, py, snap_x, py + ph, color=col, width=float(self.style.width))
        renderer.draw_line_px(px, my, px + pw, my, color=col, width=float(self.style.width))

        # etiquetas
        price = self.overlay.price_scale.y_to_price(my)
        price_str = f"{price:,.2f}"

        time_ts = self.overlay.time_scale.x_to_time(snap_x)
        time_str = time_ts.strftime("%Y-%m-%d %H:%M")

        tag_style = MsdfTextStyle(
            size_px=13.0,
            color=(1, 1, 1, 1),
            letter_spacing_px=1.0,
            edge=0.5,
            smoothing=0.08,
        )

        # precio (a la derecha del plot)
        pw_txt, ph_txt = self.font.measure_text(price_str, tag_style)
        renderer.draw_rect_px(px + pw + 5, my - ph_txt / 2, pw_txt + 10, ph_txt + 4, Color(0.1, 0.1, 0.15, 0.9))
        self.font.draw_text(renderer, px + pw + 10, my - ph_txt / 2 + 2, price_str, tag_style)

        # tiempo (abajo del plot)
        tw_txt, th_txt = self.font.measure_text(time_str, tag_style)
        renderer.draw_rect_px(snap_x - tw_txt / 2 - 5, py + ph + 5, tw_txt + 10, th_txt + 4, Color(0.1, 0.1, 0.15, 0.9))
        self.font.draw_text(renderer, snap_x - tw_txt / 2, py + ph + 7, time_str, tag_style)