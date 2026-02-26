# charts/overlays/tooltip.py
from __future__ import annotations

from typing import Optional
from render.renderer import Renderer2D, Color
from app.input import InputState
from charts.scales.time_scale import TimeScale
from charts.series.candles import CandleSeries
from render.text.msdf_text import MsdfTextStyle


class TooltipOverlay:
    """
    Overlay que muestra tooltip con OHLC + fecha cuando el mouse está cerca de una vela.
    Modular e independiente.
    """

    def __init__(
        self,
        overlay,
        time_scale: TimeScale,
        input_state: InputState,
        series: CandleSeries,
        max_distance_px: float = 20.0,
    ) -> None:
        self.overlay = overlay
        self.time_scale = time_scale
        self.input = input_state
        self.series = series

        self.font = None  # se asigna desde window.run()

        self.style = MsdfTextStyle(
            size_px=16.0,
            color=(0.95, 0.95, 1.0, 1.0),
            letter_spacing_px=1.5,
            edge=0.5,
            smoothing=0.08,
        )

        self.padding = 8.0
        self.max_distance_px = float(max_distance_px)

    def draw(self, renderer: Renderer2D) -> None:
        if self.font is None:
            return

        mx = float(self.input.mouse.x)
        my = float(self.input.mouse.y)

        vr = self.time_scale.get_visible_range()
        vs = max(0, int(vr.start_idx))
        ve = min(len(self.series.data) - 1, int(vr.end_idx))
        if ve < vs:
            return

        closest_idx: Optional[int] = None
        min_dist = 1e18

        for i in range(vs, ve + 1):
            candle_x = float(self.time_scale.index_to_x(i))
            dist = abs(candle_x - mx)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        if closest_idx is None or min_dist > self.max_distance_px:
            return

        bar = self.series.data[closest_idx]
        prev_close = self.series.data[closest_idx - 1].c if closest_idx > 0 else bar.c
        change_pct = ((bar.c - prev_close) / prev_close * 100.0) if prev_close != 0 else 0.0

        is_bullish = bar.c >= bar.o
        tooltip_bg = Color(0.04, 0.15, 0.08, 0.92) if is_bullish else Color(0.15, 0.04, 0.04, 0.92)
        tooltip_border = Color(0.3, 0.9, 0.3, 0.75) if is_bullish else Color(0.9, 0.3, 0.3, 0.75)
        text_color = (0.7, 1.0, 0.7, 1.0) if is_bullish else (1.0, 0.7, 0.7, 1.0)

        lines = [
            bar.ts.strftime("%Y-%m-%d %H:%M"),
            f"O: {bar.o:,.2f}",
            f"H: {bar.h:,.2f}",
            f"L: {bar.l:,.2f}",
            f"C: {bar.c:,.2f}",
            f"Chg: {change_pct:+.2f}%",
        ]

        temp_style = MsdfTextStyle(
            size_px=self.style.size_px,
            color=text_color,
            letter_spacing_px=self.style.letter_spacing_px,
            edge=self.style.edge,
            smoothing=self.style.smoothing,
        )

        # medir
        max_w = 0.0
        line_h = 16.0  # aproximado
        for line in lines:
            w, _ = self.font.measure_text(line, temp_style)
            max_w = max(max_w, float(w))

        tooltip_w = max_w + 2.0 * self.padding
        tooltip_h = len(lines) * line_h + 2.0 * self.padding

        # posición cerca del mouse
        tx = mx + 20.0
        ty = my - tooltip_h - 15.0

        # clamp simple (si querés: usar self.overlay.get_layout() para width/height reales)
        if tx + tooltip_w > 1280:
            tx = mx - tooltip_w - 20.0
        if ty < 0:
            ty = my + 30.0

        # fondo + borde
        renderer.draw_rect_px(tx - 2, ty - 2, tooltip_w + 4, tooltip_h + 4, tooltip_border)
        renderer.draw_rect_px(tx, ty, tooltip_w, tooltip_h, tooltip_bg)

        # texto
        cy = ty + self.padding
        for line in lines:
            self.font.draw_text(renderer, tx + self.padding, cy, line, temp_style)
            cy += line_h