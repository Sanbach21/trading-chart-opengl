"""TimeScale (placeholder).

Objetivo:
- index_to_x(i)
- x_to_index(x)
- visible_range (bar index start/end)
- spacing/zoom centrado en cursor
"""

# python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VisibleRange:
    start: int
    end: int


class TimeScale:
    def __init__(self, bar_spacing: float = 10.0, right_offset: float = 0.0) -> None:
        self.bar_spacing = float(bar_spacing)
        self.right_offset = float(right_offset)

        self.total_bars: int = 0
        self.view_x: float = 0.0
        self.view_w: float = 1.0

        self._visible = VisibleRange(0, -1)

    def set_view(self, x: float, w: float) -> None:
        self.view_x = float(x)
        self.view_w = max(1.0, float(w))
        self._recalc_visible()

    def set_total_bars(self, n: int) -> None:
        self.total_bars = max(0, int(n))
        self._recalc_visible()

    def get_visible_range(self) -> VisibleRange:
        return self._visible

    def _recalc_visible(self) -> None:
        if self.total_bars <= 0:
            self._visible = VisibleRange(0, -1)
            return

        spacing = max(1.0, self.bar_spacing)
        bars_in_view = int(self.view_w / spacing) + 2

        last = self.total_bars - 1
        end_index = int(round(last - self.right_offset))
        end_index = max(0, min(last, end_index))

        start_index = end_index - (bars_in_view - 1)
        if start_index < 0:
            start_index = 0

        self._visible = VisibleRange(start_index, end_index)

    def index_to_x(self, index: int) -> float:
        vr = self._visible
        if vr.end < vr.start:
            return self.view_x

        dx_bars = index - vr.end
        x_right = self.view_x + self.view_w
        return float(x_right + dx_bars * self.bar_spacing)

    def x_to_index(self, x: float) -> int:
        if self.total_bars <= 0:
            return 0

        vr = self._visible
        x_right = self.view_x + self.view_w
        dx_px = float(x) - x_right
        dx_bars = dx_px / max(1.0, self.bar_spacing)

        idx = int(round(vr.end + dx_bars))
        return max(0, min(self.total_bars - 1, idx))

    def zoom_at_x(self, mouse_x: float, delta: float) -> None:
        factor = 1.0 + (0.10 if delta > 0 else -0.10)
        self.bar_spacing = float(max(3.0, min(40.0, self.bar_spacing * factor)))
        self._recalc_visible()

    def pan_by_pixels(self, dx_px: float) -> None:
        bars = dx_px / max(1.0, self.bar_spacing)
        self.right_offset += bars
        self.right_offset = float(max(-50.0, min(50000.0, self.right_offset)))
        self._recalc_visible()

    # dentro de charts/scales/time_scale.py (clase TimeScale)

def set_viewport(self, x: float, y: float, w: float, h: float) -> None:
    self.view_x = float(x)
    self.view_y = float(y)
    self.view_w = max(1.0, float(w))
    self.view_h = max(1.0, float(h))

def index_to_x(self, i: int) -> float:
    """
    Mapeo mínimo: cada bar ocupa (bar_px + gap_px) y se desplaza con scroll.
    Usamos el "center index" y un offset px.
    """
    # Si ya tenés bar_spacing_px / scroll_px / center_index, enchufalos acá.
    bar = getattr(self, "bar_width_px", 8.0)
    gap = getattr(self, "bar_gap_px", 3.0)
    step = float(bar + gap)

    center = getattr(self, "center_index", 0)
    pan = getattr(self, "pan_px", 0.0)

    # x del centro del plot
    x_mid = self.view_x + self.view_w * 0.5

    return x_mid + (i - center) * step + float(pan)
