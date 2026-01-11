# charts/scales/time_scale.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List


@dataclass
class VisibleRange:
    start_ts: datetime
    end_ts: datetime
    start_idx: int
    end_idx: int


class TimeScale:
    def __init__(self, bar_spacing: float = 10.0, right_offset: float = 0.0) -> None:
        self.bar_spacing = float(bar_spacing)
        self.right_offset = float(right_offset)
        self.total_bars: int = 0
        self.view_x: float = 0.0
        self.view_w: float = 1.0
        self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)
        self._timestamps: List[datetime] = []

    def set_timestamps(self, ts_list: List[datetime]) -> None:
        self._timestamps = ts_list[:]
        self.total_bars = len(ts_list)
        self._recalc_visible()

    def set_view(self, x: float, w: float) -> None:
        """Actualiza el viewport horizontal del plot (llamado cada frame)"""
        self.view_x = float(x)
        self.view_w = max(1.0, float(w))
        self._recalc_visible()

    def get_visible_range(self) -> VisibleRange:
        return self._visible

    def _recalc_visible(self) -> None:
        if self.total_bars <= 0 or not self._timestamps:
            self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)
            return

        spacing = max(1.0, self.bar_spacing)
        bars_in_view = int(self.view_w / spacing) + 2

        last = self.total_bars - 1
        end_idx = int(round(last - self.right_offset))
        end_idx = max(0, min(last, end_idx))

        start_idx = max(0, end_idx - (bars_in_view - 1))

        start_ts = self._timestamps[start_idx]
        end_ts = self._timestamps[end_idx]

        self._visible = VisibleRange(start_ts, end_ts, start_idx, end_idx)

    def index_to_x(self, index: int) -> float:
        vr = self._visible
        if vr.end_idx <= vr.start_idx:
            return self.view_x

        t = (index - vr.start_idx) / (vr.end_idx - vr.start_idx)
        t = max(0.0, min(1.0, t))
        return self.view_x + t * self.view_w

    def time_to_x(self, ts: datetime) -> float:
        vr = self._visible
        if vr.end_ts <= vr.start_ts:
            return self.view_x

        delta_total = (vr.end_ts - vr.start_ts).total_seconds()
        if delta_total <= 0:
            return self.view_x

        delta = (ts - vr.start_ts).total_seconds()
        t = delta / delta_total
        t = max(0.0, min(1.0, t))
        return self.view_x + t * self.view_w

    def x_to_time(self, x: float) -> datetime:
        vr = self._visible
        t = (x - self.view_x) / self.view_w
        t = max(0.0, min(1.0, t))

        delta_total = (vr.end_ts - vr.start_ts).total_seconds()
        delta = t * delta_total
        return vr.start_ts + timedelta(seconds=delta)

    def zoom_at_x(self, mouse_x: float, delta: float) -> None:
        factor = 1.0 + (0.12 if delta > 0 else -0.12)
        old_spacing = self.bar_spacing
        self.bar_spacing = max(3.0, min(60.0, self.bar_spacing * factor))
        # Ajustar offset para que el zoom sea centrado en el mouse
        if old_spacing != self.bar_spacing:
            ratio = mouse_x / self.view_w if self.view_w > 0 else 0.5
            self.right_offset += (self.total_bars * ratio) * (1 / factor - 1)
        self._recalc_visible()

    def pan_by_pixels(self, dx_px: float) -> None:
        bars = dx_px / max(1.0, self.bar_spacing)
        self.right_offset += bars
        self.right_offset = max(-100.0, min(100000.0, self.right_offset))
        self._recalc_visible()