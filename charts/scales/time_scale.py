# charts/scales/time_scale.py
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import List


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass
class VisibleRange:
    start_ts: datetime
    end_ts: datetime
    start_idx: int
    end_idx: int


class TimeScale:
    def __init__(
        self,
        bar_spacing: float = 10.0,
        right_offset: float = 2.0,
        min_bar_spacing: float = 3.0,
        max_bar_spacing: float = 300.0,
        min_right_offset: float = 0.0,
    ) -> None:
        self.bar_spacing = float(bar_spacing)
        self.min_bar_spacing = float(min_bar_spacing)
        self.max_bar_spacing = float(max_bar_spacing)

        self.right_offset = float(right_offset)
        self.min_right_offset = float(min_right_offset)

        self.total_bars: int = 0
        self.view_x: float = 0.0
        self.view_w: float = 1.0

        self._timestamps: List[datetime] = []
        self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)

    def set_timestamps(self, ts_list: List[datetime]) -> None:
        """Usar solo al cargar datos iniciales"""
        self._timestamps = ts_list[:]
        self.total_bars = len(ts_list)
        self.right_offset = max(self.min_right_offset, self.right_offset)
        self._recalc_visible()

    def append_timestamp(self, ts: datetime) -> None:
        """Agregar una sola vela nueva (optimizado para live)"""
        self._timestamps.append(ts)
        self.total_bars = len(self._timestamps)
        self._recalc_visible()

    def update_last_timestamp(self, ts: datetime) -> None:
        """Actualizar la vela actual (la que está formando)"""
        if self._timestamps:
            self._timestamps[-1] = ts
        self._recalc_visible()

    def set_view(self, x: float, w: float) -> None:
        self.view_x = float(x)
        self.view_w = max(1.0, float(w))
        self._recalc_visible()

    def get_visible_range(self) -> VisibleRange:
        return self._visible

    @property
    def _last_data_index(self) -> int:
        return self.total_bars - 1

    def _right_anchor_x(self) -> float:
        return self.view_x + self.view_w - self.right_offset * self.bar_spacing

    def _float_index_at_x(self, x: float) -> float:
        if self.total_bars <= 0:
            return 0.0
        return self._last_data_index - ((self._right_anchor_x() - float(x)) / self.bar_spacing)

    def _recalc_visible(self) -> None:
        if self.total_bars <= 0 or not self._timestamps:
            self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)
            return

        self.bar_spacing = _clamp(self.bar_spacing, self.min_bar_spacing, self.max_bar_spacing)
        self.right_offset = max(self.min_right_offset, self.right_offset)

        left_float = self._float_index_at_x(self.view_x)
        right_float = self._float_index_at_x(self.view_x + self.view_w)

        start_idx = max(0, int(math.floor(min(left_float, right_float))) - 1)
        end_idx = min(self._last_data_index, int(math.ceil(max(left_float, right_float))) + 1)

        self._visible = VisibleRange(
            start_ts=self._timestamps[start_idx],
            end_ts=self._timestamps[end_idx],
            start_idx=start_idx,
            end_idx=end_idx,
        )

    # === Métodos existentes (sin cambios) ===
    def index_to_x(self, index: int) -> float:
        if self.total_bars <= 0:
            return self.view_x
        bars_from_last = self._last_data_index - int(index)
        return self._right_anchor_x() - bars_from_last * self.bar_spacing

    def x_to_index(self, x: float) -> int:
        if self.total_bars <= 0:
            return 0
        idx = round(self._float_index_at_x(x))
        return int(_clamp(idx, 0, self._last_data_index))

    def zoom_at_x(self, mouse_x: float, delta: float) -> None:
        if self.total_bars <= 0:
            return
        old_spacing = self.bar_spacing
        old_float_index = self._float_index_at_x(mouse_x)

        factor = 1.18 if delta > 0 else (1.0 / 1.18)
        self.bar_spacing = _clamp(old_spacing * factor, self.min_bar_spacing, self.max_bar_spacing)

        new_anchor = self.view_x + self.view_w - self.right_offset * self.bar_spacing
        bars_from_last = self._last_data_index - old_float_index
        target_x = new_anchor - bars_from_last * self.bar_spacing

        delta_px = float(mouse_x) - target_x
        self.right_offset -= delta_px / self.bar_spacing
        self.right_offset = max(self.min_right_offset, self.right_offset)

        self._recalc_visible()

    def pan_by_pixels(self, dx_px: float) -> None:
        if self.total_bars <= 0:
            return
        self.right_offset += dx_px / self.bar_spacing
        self.right_offset = max(self.min_right_offset, self.right_offset)
        self._recalc_visible()