from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Any


@dataclass
class TooltipStyle:
    text_color: Tuple[float, float, float, float] = (0.95, 0.95, 0.95, 1.0)
    bg_color: Tuple[float, float, float, float] = (0.12, 0.12, 0.12, 0.92)
    border_color: Tuple[float, float, float, float] = (0.45, 0.45, 0.45, 0.95)

    padding_x: float = 8.0
    padding_y: float = 6.0
    offset_x: float = 12.0
    offset_y: float = 12.0

    label_scale: float = 1.0
    border_width: float = 1.0

    # Opcional: mostrar timestamp si existe
    show_timestamp: bool = False
    time_format: str = "%Y-%m-%d %I:%M %p"


class TooltipOverlay:
    """
    Tooltip flotante OHLC.

    Arquitectura B:
    - No depende de PriceScale clásico
    - Usa TimeScale para resolver la barra bajo el mouse
    - Usa CandleSeries para obtener O/H/L/C
    """

    def __init__(
        self,
        overlay: Any,
        input_state: Any,
        series: Any,
        text_renderer: Any,
        style: Optional[TooltipStyle] = None,
    ) -> None:
        self.overlay = overlay
        self.input = input_state
        self.series = series
        self.text = text_renderer
        self.style = style or TooltipStyle()

    def draw(self, renderer: Any) -> None:
        if self.text is None:
            return

        layout = self.overlay.get_layout()
        px, py, pw, ph = layout.plot_rect

        if pw <= 0 or ph <= 0:
            return

        mx = float(self.input.mouse.x)
        my = float(self.input.mouse.y)

        # Solo cuando el mouse está dentro del plot
        if not (px <= mx <= px + pw and py <= my <= py + ph):
            return

        # Resolver índice usando TimeScale
        ts = self.overlay.time_scale
        try:
            idx = int(ts.x_to_index(mx))
        except Exception:
            return

        if not (0 <= idx < len(self.series.data)):
            return

        d = self.series.data[idx]

        # Contenido principal
        lines = [
            f"O: {d.o:.2f}",
            f"H: {d.h:.2f}",
            f"L: {d.l:.2f}",
            f"C: {d.c:.2f}",
        ]

        # Timestamp opcional
        if self.style.show_timestamp:
            try:
                label_ts = d.ts.strftime(self.style.time_format)
                lines.insert(0, label_ts)
            except Exception:
                pass

        # Medir bloque multilínea
        text_sizes = [
            self.text.measure_text(line, scale=float(self.style.label_scale))
            for line in lines
        ]

        max_text_w = max((w for w, _ in text_sizes), default=0.0)
        text_h = max((h for _, h in text_sizes), default=0.0)

        line_gap = 4.0
        total_text_h = len(lines) * text_h + max(0, len(lines) - 1) * line_gap

        box_w = max_text_w + self.style.padding_x * 2.0
        box_h = total_text_h + self.style.padding_y * 2.0

        # Posición inicial al lado del mouse
        box_x = mx + self.style.offset_x
        box_y = my + self.style.offset_y

        # Clamp para no salirse por derecha/abajo
        if box_x + box_w > px + pw:
            box_x = mx - self.style.offset_x - box_w

        if box_y + box_h > py + ph:
            box_y = my - self.style.offset_y - box_h

        # Clamp final dentro del plot
        box_x = max(px + 2.0, min(box_x, px + pw - box_w - 2.0))
        box_y = max(py + 2.0, min(box_y, py + ph - box_h - 2.0))

        # Fondo
        renderer.draw_rect_px(
            box_x,
            box_y,
            box_w,
            box_h,
            self.style.bg_color,
        )

        # Borde
        bw = float(self.style.border_width)
        bc = self.style.border_color

        renderer.draw_line_px(box_x, box_y, box_x + box_w, box_y, bc, bw)
        renderer.draw_line_px(box_x, box_y + box_h, box_x + box_w, box_y + box_h, bc, bw)
        renderer.draw_line_px(box_x, box_y, box_x, box_y + box_h, bc, bw)
        renderer.draw_line_px(box_x + box_w, box_y, box_x + box_w, box_y + box_h, bc, bw)

        # Texto multilínea
        text_x = box_x + self.style.padding_x
        cursor_y = box_y + self.style.padding_y + text_h

        for line in lines:
            self.text.render_text(
                line,
                text_x,
                cursor_y,
                scale=float(self.style.label_scale),
                color=self.style.text_color,
            )
            cursor_y += text_h + line_gap