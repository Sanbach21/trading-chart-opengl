# charts/overlays/crosshair.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

from render.renderer import Renderer2D, Color
from app.input import InputState
from charts.series.candles import CandleSeries
from charts.overlays.chart_overlay import ChartOverlay, Rect
from charts.overlays.axis import SevenSegStyle, SevenSegFont


@dataclass
class CrosshairStyle:
    color: Tuple[float, float, float, float] = (0.9, 0.9, 0.9, 0.6)
    width: float = 1.0
    snap_to_bar: bool = False  # futura fase: alinear a centro de barra


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


    def draw(self, renderer: Renderer2D) -> None:
        layout = self.overlay.get_layout()
        plot_rect = layout.plot_rect  # (x, y, w, h)
        px, py, pw, ph = plot_rect

        if pw <= 0 or ph <= 0:
            return

        mx = self.input.mouse.x
        my = self.input.mouse.y

        inside = (px <= mx <= px + pw) and (py <= my <= py + ph)
        if not inside:
            return

        col = Color(*self.style.color)

        # SNAP: encontrar la vela más cercana
        snap_x = mx
        if self.snap_enabled:
            vr = self.overlay.time_scale.get_visible_range()
            vs = max(0, vr.start_idx)
            ve = min(len(self.series.data) - 1, vr.end_idx)

            if ve >= vs:
                closest_idx = None
                min_dist = float('inf')

                for i in range(vs, ve + 1):
                    candle_x = self.overlay.time_scale.index_to_x(i)
                    dist = abs(candle_x - mx)
                    if dist < min_dist:
                        min_dist = dist
                        closest_idx = i

                if closest_idx is not None and min_dist <= self.snap_tolerance_px:
                    snap_x = self.overlay.time_scale.index_to_x(closest_idx)

        # Línea vertical (con snap)
        renderer.draw_line_px(
            snap_x, py,
            snap_x, py + ph,
            color=col,
            width=self.style.width
        )

        # Línea horizontal (sigue el mouse en Y)
        renderer.draw_line_px(
            px, my,
            px + pw, my,
            color=col,
            width=self.style.width
        )

        # Etiquetas flotantes
        # Precio en Y (derecha del eje)
        price_y = my
        # Nota: si PriceScale no tiene y_to_price, debes agregarlo (ver abajo)
        price = self.overlay.price_scale.y_to_price(price_y)
        price_str = f"{price:,.2f}"

        # Tiempo en X (abajo del eje)
        time_x = snap_x
        time_ts = self.overlay.time_scale.x_to_time(time_x)
        time_str = time_ts.strftime("%Y-%m-%d %H:%M")

        # Dibujar etiqueta precio (derecha del eje)
        price_font = SevenSegStyle(size_px=13.0, thickness_px=1.8, color=(1,1,1,1))
        price_w, price_h = SevenSegFont().measure_text(price_str, price_font)
        renderer.draw_rect_px(
            px + pw + 5, price_y - price_h / 2,
            price_w + 10, price_h + 4,
            Color(0.1, 0.1, 0.15, 0.9)
        )
        SevenSegFont().draw_text(
            renderer,
            px + pw + 10, price_y - price_h / 2 + 2,
            price_str,
            price_font
        )

        # Dibujar etiqueta tiempo (abajo del eje)
        time_font = SevenSegStyle(size_px=13.0, thickness_px=1.8, color=(1,1,1,1))
        time_w, time_h = SevenSegFont().measure_text(time_str, time_font)
        renderer.draw_rect_px(
            time_x - time_w / 2 - 5, py + ph + 5,
            time_w + 10, time_h + 4,
            Color(0.1, 0.1, 0.15, 0.9)
        )
        SevenSegFont().draw_text(
            renderer,
            time_x - time_w / 2, py + ph + 7,
            time_str,
            time_font
        )