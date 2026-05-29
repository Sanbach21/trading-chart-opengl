"""
charts/overlays/crosshair.py
============================
Crosshair profesional para chart de trading.

Características
---------------
- Cruz con CÍRCULO central en la intersección del cursor
- Líneas punteadas (dashed) horizontales y verticales
- Snap automático al centro de la vela más cercana (eje X)
- Etiqueta de PRECIO flotante en el eje Y (badge con fondo)
- Etiqueta de TIEMPO flotante en el eje X (badge con fondo)
- Totalmente parametrizable via CrosshairStyle

Arquitectura B
--------------
Este overlay ya no depende conceptualmente del PriceScale clásico.
Debe recibir una escala compartida compatible con:

    price_to_y(price: float) -> float
    y_to_price(y: float) -> float

Uso básico
----------
    crosshair = CrosshairOverlay(overlay, input_state, candle_series)
    crosshair.text_renderer = my_text_renderer
    crosshair.price_scale   = my_local_price_scale

    # en el loop de render:
    crosshair.draw(renderer)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Tuple

from app.input import InputState
from charts.overlays.chart_overlay import ChartOverlay
from charts.series.candles import CandleSeries
from render.renderer import Color, Renderer2D


# ──────────────────────────────────────────────────────────────────────────────
# STYLE
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CrosshairStyle:
    """
    Parámetros visuales del crosshair.
    """

    # Líneas
    line_color: Tuple[float, float, float, float] = (0.85, 0.85, 0.85, 0.65)
    line_width: float = 1.0

    # Patrón dash
    dash_px: float = 6.0
    gap_px: float = 5.0
    center_gap_px: float = 10.0

    # Círculo central
    circle_radius: float = 5.0
    circle_width: float = 1.5
    circle_color: Optional[Tuple[float, float, float, float]] = None
    circle_fill: bool = True
    circle_fill_color: Tuple[float, float, float, float] = (0.85, 0.85, 0.85, 0.12)

    # Snap al eje X
    snap_to_bar: bool = True
    snap_tolerance_px: float = 40.0

    # Etiquetas flotantes
    show_price_label: bool = True
    show_time_label: bool = True

    label_bg_color: Tuple[float, float, float, float] = (0.15, 0.15, 0.18, 0.95)
    label_text_color: Tuple[float, float, float, float] = (0.92, 0.92, 0.92, 1.0)
    label_border_color: Optional[Tuple[float, float, float, float]] = (0.5, 0.5, 0.5, 0.6)

    label_padding_px: float = 5.0
    label_scale: float = 1.0
    label_decimals: int = 2
    time_format: str = "%I:%M %p"


# ──────────────────────────────────────────────────────────────────────────────
# OVERLAY
# ──────────────────────────────────────────────────────────────────────────────

class CrosshairOverlay:
    """
    Renderiza el crosshair profesional sobre el chart.

    Necesita que se le asignen externamente:
        crosshair.text_renderer = <TextRenderer>
        crosshair.price_scale   = <LocalPriceScale compatible>
    """

    def __init__(
        self,
        overlay: ChartOverlay,
        input_state: InputState,
        series: CandleSeries,
        style: Optional[CrosshairStyle] = None,
    ) -> None:
        self.overlay = overlay
        self.input = input_state
        self.series = series
        self.style = style or CrosshairStyle()

        # Asignados desde fuera (window.py)
        self.text_renderer = None
        self.price_scale: Any = None   # escala compartida compatible

    # ──────────────────────────────────────────────────────────────────────────
    # Punto de entrada principal
    # ──────────────────────────────────────────────────────────────────────────

    def draw(self, renderer: Renderer2D) -> None:
        """
        Dibuja el crosshair completo en el frame actual.
        """
        layout = self.overlay.get_layout()
        px, py, pw, ph = layout.plot_rect

        if pw <= 0 or ph <= 0:
            return

        mx = float(self.input.mouse.x)
        my = float(self.input.mouse.y)

        # Solo dentro del plot
        if not (px <= mx <= px + pw and py <= my <= py + ph):
            return

        # Snap X
        snap_x, snapped_idx = self._calc_snap_x(mx, px, pw)

        s = self.style
        line_col = Color(*s.line_color)
        circle_col = Color(*(s.circle_color if s.circle_color is not None else s.line_color))

        # Líneas punteadas
        self._draw_dashed_vertical(renderer, snap_x, py, py + ph, my, line_col)
        self._draw_dashed_horizontal(renderer, snap_x, my, line_col, px, px + pw)

        # Círculo central
        self._draw_circle(renderer, snap_x, my, circle_col)

        # Badge de precio
        if s.show_price_label and self.text_renderer is not None and self.price_scale is not None:
            self._draw_price_label(renderer, layout, my)

        # Badge de tiempo
        if s.show_time_label and self.text_renderer is not None and snapped_idx is not None:
            self._draw_time_label(renderer, layout, snap_x, snapped_idx)

    # ──────────────────────────────────────────────────────────────────────────
    # Snap X
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_snap_x(
        self,
        mx: float,
        plot_x: float,
        plot_w: float,
    ) -> Tuple[float, Optional[int]]:
        """
        Calcula la posición X final del crosshair y el índice de vela más cercano.
        """
        s = self.style

        if not s.snap_to_bar or len(self.series.data) == 0:
            return mx, None

        ts = self.overlay.time_scale
        vr = ts.get_visible_range()

        vs = max(0, int(vr.start_idx))
        ve = min(len(self.series.data) - 1, int(vr.end_idx))

        closest_idx: Optional[int] = None
        min_dist = float("inf")

        for i in range(vs, ve + 1):
            if hasattr(ts, "get_aligned_x"):
                cx = float(ts.get_aligned_x(i, crisp=True))
            else:
                cx = float(ts.index_to_x(i))

            if cx < plot_x - 100.0 or cx > plot_x + plot_w + 100.0:
                continue

            d = abs(cx - mx)
            if d < min_dist:
                min_dist = d
                closest_idx = i

        if closest_idx is not None and min_dist <= float(s.snap_tolerance_px):
            if hasattr(ts, "get_aligned_x"):
                raw_x = float(ts.get_aligned_x(closest_idx, crisp=True))
            else:
                raw_x = float(ts.index_to_x(closest_idx))

            snap_x = max(plot_x, min(plot_x + plot_w, raw_x))
            return snap_x, closest_idx

        return mx, None

    # ──────────────────────────────────────────────────────────────────────────
    # Líneas punteadas
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_dashed_vertical(
        self,
        r: Renderer2D,
        x: float,
        y_top: float,
        y_bot: float,
        cursor_y: float,
        color: Color,
    ) -> None:
        gap = float(self.style.center_gap_px)
        self._draw_dashed_segment_v(r, x, y_top, cursor_y - gap, color)
        self._draw_dashed_segment_v(r, x, cursor_y + gap, y_bot, color)

    def _draw_dashed_segment_v(
        self,
        r: Renderer2D,
        x: float,
        y_start: float,
        y_end: float,
        color: Color,
    ) -> None:
        if y_start >= y_end:
            return

        dash = float(self.style.dash_px)
        gap = float(self.style.gap_px)
        w = float(self.style.line_width)
        period = dash + gap

        y = y_start
        while y < y_end:
            y1 = y
            y2 = min(y + dash, y_end)
            r.draw_line_px(x, y1, x, y2, color=color, width=w)
            y += period

    def _draw_dashed_horizontal(
        self,
        r: Renderer2D,
        snap_x: float,
        y: float,
        color: Color,
        x_left: float,
        x_right: float,
    ) -> None:
        gap = float(self.style.center_gap_px)
        self._draw_dashed_segment_h(r, y, x_left, snap_x - gap, color)
        self._draw_dashed_segment_h(r, y, snap_x + gap, x_right, color)

    def _draw_dashed_segment_h(
        self,
        r: Renderer2D,
        y: float,
        x_start: float,
        x_end: float,
        color: Color,
    ) -> None:
        if x_start >= x_end:
            return

        dash = float(self.style.dash_px)
        gap = float(self.style.gap_px)
        w = float(self.style.line_width)
        period = dash + gap

        x = x_start
        while x < x_end:
            x1 = x
            x2 = min(x + dash, x_end)
            r.draw_line_px(x1, y, x2, y, color=color, width=w)
            x += period

    # ──────────────────────────────────────────────────────────────────────────
    # Círculo central
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_circle(
        self,
        r: Renderer2D,
        cx: float,
        cy: float,
        color: Color,
    ) -> None:
        s = self.style
        radius = float(s.circle_radius)
        width = float(s.circle_width)

        if s.circle_fill:
            fill_col = Color(*s.circle_fill_color)
            if hasattr(r, "draw_circle_filled_px"):
                r.draw_circle_filled_px(cx, cy, radius, color=fill_col)
            else:
                self._draw_filled_circle_fallback(r, cx, cy, radius, fill_col)

        if hasattr(r, "draw_circle_px"):
            r.draw_circle_px(cx, cy, radius, color=color, width=width)
        else:
            self._draw_circle_fallback(r, cx, cy, radius, color, width)

    def _draw_circle_fallback(
        self,
        r: Renderer2D,
        cx: float,
        cy: float,
        radius: float,
        color: Color,
        width: float,
        segments: int = 32,
    ) -> None:
        step = (2.0 * math.pi) / segments
        for i in range(segments):
            a0 = step * i
            a1 = step * (i + 1)
            x0 = cx + radius * math.cos(a0)
            y0 = cy + radius * math.sin(a0)
            x1 = cx + radius * math.cos(a1)
            y1 = cy + radius * math.sin(a1)
            r.draw_line_px(x0, y0, x1, y1, color=color, width=width)

    def _draw_filled_circle_fallback(
        self,
        r: Renderer2D,
        cx: float,
        cy: float,
        radius: float,
        color: Color,
        segments: int = 32,
    ) -> None:
        step = (2.0 * radius) / segments
        y = cy - radius
        while y <= cy + radius:
            half_chord = math.sqrt(max(0.0, radius ** 2 - (y - cy) ** 2))
            r.draw_line_px(cx - half_chord, y, cx + half_chord, y, color=color, width=1.0)
            y += step

    # ──────────────────────────────────────────────────────────────────────────
    # Badge de precio (eje Y)
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_price_label(
        self,
        r: Renderer2D,
        layout: Any,
        mouse_y: float,
    ) -> None:
        ax, ay, aw, ah = layout.price_axis_rect
        s = self.style

        try:
            price = float(self.price_scale.y_to_price(mouse_y))
        except Exception:
            return

        label = f"{price:.{int(s.label_decimals)}f}"

        text_w, text_h = self.text_renderer.measure_text(
            label,
            scale=float(s.label_scale),
        )

        pad = float(s.label_padding_px)
        bw = text_w + pad * 2.0
        bh = text_h + pad * 2.0

        b_y = mouse_y - bh * 0.5
        b_y = max(ay, min(b_y, ay + ah - bh))

        side = "right"
        try:
            side = (self.overlay.config["price_axis"].get("side", "right") or "right").lower()
        except Exception:
            pass

        if side == "left":
            b_x = ax + aw - bw
        else:
            b_x = ax

        bg_col = Color(*s.label_bg_color)
        if hasattr(r, "draw_rect_px"):
            r.draw_rect_px(b_x, b_y, bw, bh, color=bg_col)

        if s.label_border_color and hasattr(r, "draw_rect_outline_px"):
            border_col = Color(*s.label_border_color)
            r.draw_rect_outline_px(b_x, b_y, bw, bh, color=border_col, width=1.0)

        text_x = b_x + pad
        text_y = b_y + bh * 0.5 + text_h * 0.35

        self.text_renderer.render_text(
            label,
            text_x,
            text_y,
            scale=float(s.label_scale),
            color=s.label_text_color,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Badge de tiempo (eje X)
    # ──────────────────────────────────────────────────────────────────────────

    def _draw_time_label(
        self,
        r: Renderer2D,
        layout: Any,
        snap_x: float,
        bar_idx: int,
    ) -> None:
        tax, tay, taw, tah = layout.time_axis_rect
        s = self.style

        ts = self._resolve_timestamp(bar_idx)
        label = ts.strftime(s.time_format)

        text_w, text_h = self.text_renderer.measure_text(
            label,
            scale=float(s.label_scale),
        )

        pad = float(s.label_padding_px)
        bw = text_w + pad * 2.0
        bh = text_h + pad * 2.0

        b_x = snap_x - bw * 0.5
        b_x = max(tax, min(b_x, tax + taw - bw))
        b_y = tay

        bg_col = Color(*s.label_bg_color)
        if hasattr(r, "draw_rect_px"):
            r.draw_rect_px(b_x, b_y, bw, bh, color=bg_col)

        if s.label_border_color and hasattr(r, "draw_rect_outline_px"):
            border_col = Color(*s.label_border_color)
            r.draw_rect_outline_px(b_x, b_y, bw, bh, color=border_col, width=1.0)

        text_x = b_x + pad
        text_y = b_y + bh * 0.5 + text_h * 0.35

        self.text_renderer.render_text(
            label,
            text_x,
            text_y,
            scale=float(s.label_scale),
            color=s.label_text_color,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve_timestamp(self, index: int) -> datetime:
        timestamps = self.overlay.time_scale._timestamps

        if index < len(timestamps):
            return timestamps[index]

        last_ts = timestamps[-1]
        extra_minutes = index - (len(timestamps) - 1)
        return last_ts + timedelta(minutes=extra_minutes)