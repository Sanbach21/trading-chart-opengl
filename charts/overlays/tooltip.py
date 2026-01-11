# charts/overlays/tooltip.py
from __future__ import annotations

from typing import Optional, Tuple
from datetime import datetime

from render.renderer import Renderer2D, Color
from app.input import InputState
from charts.scales.time_scale import TimeScale
from charts.series.candles import CandleSeries
from charts.overlays.axis import SevenSegStyle, SevenSegFont


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

        self.font = SevenSegFont()

        self.style = SevenSegStyle(
            size_px=13.0,
            thickness_px=1.8,
            spacing_px=1.5,
            color=(0.95, 0.95, 1.0, 1.0),  # blanco-azulado suave
        )

        self.bg_color = Color(0.05, 0.05, 0.08, 0.92)      # negro muy oscuro semi-transparente
        self.border_color = Color(0.5, 0.6, 0.8, 0.7)      # borde gris-azulado sutil
        self.padding = 8.0
        self.max_distance_px = max_distance_px

    def draw(self, renderer: Renderer2D) -> None:
        mx = self.input.mouse.x
        my = self.input.mouse.y

        # Obtenemos el rectángulo del área de plot (para saber si estamos dentro)
        # Nota: asumimos que el ChartOverlay tiene get_plot_rect()
        # Si no lo tiene, podemos pasarlo como parámetro en __init__
        from charts.overlays.chart_overlay import ChartOverlay
        # Temporal: necesitamos el layout → lo ideal es pasarlo como parámetro o tener una referencia
        # Por ahora, asumimos que se puede acceder desde otro lugar o lo pasamos después

        # Buscar la vela más cercana
        vr = self.time_scale.get_visible_range()
        vs = max(0, vr.start_idx)
        ve = min(len(self.series.data) - 1, vr.end_idx)

        if ve < vs:
            return

        closest_idx: Optional[int] = None
        min_dist = float('inf')

        for i in range(vs, ve + 1):
            candle_x = self.time_scale.index_to_x(i)
            dist = abs(candle_x - mx)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        if closest_idx is None or min_dist > self.max_distance_px:
            return

        # Obtenemos la vela
        bar = self.series.data[closest_idx]
        prev_close = self.series.data[closest_idx - 1].c if closest_idx > 0 else bar.c
        change_pct = ((bar.c - prev_close) / prev_close * 100) if prev_close != 0 else 0.0
                # Colores dinámicos según vela alcista/bajista
        is_bullish = bar.c >= bar.o
        tooltip_bg = Color(0.04, 0.15, 0.08, 0.92) if is_bullish else Color(0.15, 0.04, 0.04, 0.92)
        tooltip_border = Color(0.3, 0.9, 0.3, 0.75) if is_bullish else Color(0.9, 0.3, 0.3, 0.75)
        text_color = (0.7, 1.0, 0.7, 1.0) if is_bullish else (1.0, 0.7, 0.7, 1.0)

                # Determinar color según vela alcista/bajista
        is_bullish = bar.c >= bar.o
        tooltip_bg_color = Color(0.05, 0.12, 0.08, 0.92) if is_bullish else Color(0.12, 0.05, 0.05, 0.92)
        tooltip_border_color = Color(0.4, 0.8, 0.4, 0.7) if is_bullish else Color(0.8, 0.4, 0.4, 0.7)

        # Preparar las líneas del tooltip
        lines = [
            bar.ts.strftime("%Y-%m-%d %H:%M"),
            f"O: {bar.o:,.2f}",
            f"H: {bar.h:,.2f}",
            f"L: {bar.l:,.2f}",
            f"C: {bar.c:,.2f}",
            f"Chg: {change_pct:+.2f}%",
        ]

        # Calcular dimensiones
        max_width = 0.0
        line_height = 16.0  # aproximado, puedes medirlo
        total_height = len(lines) * line_height + 2 * self.padding

        for line in lines:
            w, _ = self.font.measure_text(line, self.style)
            max_width = max(max_width, w)

        tooltip_width = max_width + 2 * self.padding
        tooltip_height = total_height

        # Posición relativa al mouse
        tx = mx + 20
        ty = my - tooltip_height - 15

        # Ajustar si se sale de pantalla (muy básico, puedes mejorarlo)
        if tx + tooltip_width > 1280:  # ancho aproximado ventana
            tx = mx - tooltip_width - 20
        if ty < 0:
            ty = my + 30

                    # Dibujar borde + fondo con colores dinámicos
        renderer.draw_rect_px(
            tx - 2, ty - 2,
            tooltip_width + 4, tooltip_height + 4,
            tooltip_border
        )
        renderer.draw_rect_px(
            tx, ty,
            tooltip_width, tooltip_height,
            tooltip_bg
        )   

                # Dibujar texto línea por línea con color dinámico según vela
        text_color = (0.6, 1.0, 0.6, 1.0) if is_bullish else (1.0, 0.6, 0.6, 1.0)
        temp_style = SevenSegStyle(
            size_px=self.style.size_px,
            thickness_px=self.style.thickness_px,
            spacing_px=self.style.spacing_px,
            color=text_color
        )

                # Texto con color dinámico
        temp_style = SevenSegStyle(
            size_px=self.style.size_px,
            thickness_px=self.style.thickness_px,
            spacing_px=self.style.spacing_px,
            color=text_color
        )

        cursor_y = ty + self.padding
        for line in lines:
            self.font.draw_text(
                renderer,
                tx + self.padding,
                cursor_y,
                line,
                temp_style  # ← Cambiado: usamos temp_style
            )
            cursor_y += line_height