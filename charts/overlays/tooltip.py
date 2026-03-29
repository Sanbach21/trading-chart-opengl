from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


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


class TooltipOverlay:
    def __init__(
        self,
        overlay,
        input_state,
        series,
        text_renderer,
        style: Optional[TooltipStyle] = None,
    ) -> None:
        self.overlay = overlay
        self.input = input_state
        self.series = series
        self.text = text_renderer
        self.style = style or TooltipStyle()

    def draw(self, renderer) -> None:
        if self.text is None:
            return

        layout = self.overlay.get_layout()
        px, py, pw, ph = layout.plot_rect

        if pw <= 0 or ph <= 0:
            return

        mx = float(self.input.mouse.x)
        my = float(self.input.mouse.y)

        if not (px <= mx <= px + pw and py <= my <= py + ph):
            return

        # Mejor forma: usar el TimeScale directamente
        idx = self.overlay.time_scale.x_to_index(mx)

        if not (0 <= idx < len(self.series.data)):
            return

        d = self.series.data[idx]

        label = f"O:{d.o:.2f}  H:{d.h:.2f}  L:{d.l:.2f}  C:{d.c:.2f}"

        text_w, text_h = self.text.measure_text(label, scale=self.style.label_scale)

        box_w = text_w + self.style.padding_x * 2.0
        box_h = text_h + self.style.padding_y * 2.0

        box_x = mx + self.style.offset_x
        box_y = my + self.style.offset_y

        if box_x + box_w > px + pw:
            box_x = mx - self.style.offset_x - box_w
        if box_y + box_h > py + ph:
            box_y = my - self.style.offset_y - box_h

        box_x = max(px + 2.0, box_x)
        box_y = max(py + 2.0, box_y)

        renderer.draw_rect_px(box_x, box_y, box_w, box_h, self.style.bg_color)

        bw = float(self.style.border_width)
        bc = self.style.border_color
        renderer.draw_line_px(box_x, box_y, box_x + box_w, box_y, bc, bw)
        renderer.draw_line_px(box_x, box_y + box_h, box_x + box_w, box_y + box_h, bc, bw)
        renderer.draw_line_px(box_x, box_y, box_x, box_y + box_h, bc, bw)
        renderer.draw_line_px(box_x + box_w, box_y, box_x + box_w, box_y + box_h, bc, bw)

        renderer.flush()

        self.text.render_text(
            label,
            box_x + self.style.padding_x,
            box_y + self.style.padding_y + text_h,
            scale=self.style.label_scale,
            color=self.style.text_color,
        )