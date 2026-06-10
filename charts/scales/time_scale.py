from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    """TimeScale profesional inspirada en TradingView / NinjaTrader."""

    def __init__(
        self,
        bar_spacing: float = 12.0,
        right_offset: float = 12.0,
        min_bar_spacing: float = 0.15,
        max_bar_spacing: float = 300.0,
        max_right_offset: float = 500.0,
        right_padding_px: float = 0.0,
    ) -> None:

        self.bar_spacing = float(bar_spacing)
        self.min_bar_spacing = float(min_bar_spacing)
        self.max_bar_spacing = float(max_bar_spacing)

        self.right_offset = float(right_offset)
        self.max_right_offset = float(max_right_offset)

        # ⚠️ Padding NO se usa para posicionar velas
        self.right_padding_px = float(right_padding_px)

        self.total_bars: int = 0
        self.view_x: float = 0.0
        self.view_w: float = 1.0

        self._timestamps: List[datetime] = []
        self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)

    # -------------------------------------------------------------------------
    # CLAMP CORREGIDO — evita que la primera vela desaparezca
    # -------------------------------------------------------------------------
    def _clamp_right_offset(self, soft: bool = False) -> None:
        if self.total_bars <= 1:
            self.right_offset = max(0.0, self.right_offset)
            return

        # ❗ La primera vela (índice 0) debe ser visible SIEMPRE
        min_offset = -(self.total_bars - 1)

        if soft:
            self.right_offset = max(min_offset, self.right_offset)
        else:
            self.right_offset = max(min_offset, self.right_offset)

        self.right_offset = min(self.max_right_offset, self.right_offset)

    # -------------------------------------------------------------------------
    # TIMESTAMPS
    # -------------------------------------------------------------------------
    def set_timestamps(self, ts_list: List[datetime]) -> None:
        self._timestamps = ts_list[:]
        self.total_bars = len(ts_list)
        self._clamp_right_offset()
        self._recalc_visible()

    def append_timestamp(self, ts: datetime) -> None:
        self._timestamps.append(ts)
        self.total_bars = len(self._timestamps)
        self._clamp_right_offset()
        self._recalc_visible()

    def update_last_timestamp(self, ts: datetime) -> None:
        if self._timestamps:
            self._timestamps[-1] = ts
        self._clamp_right_offset()
        self._recalc_visible()

    # -------------------------------------------------------------------------
    # VIEWPORT
    # -------------------------------------------------------------------------
    def set_view(self, x: float, w: float) -> None:
        self.view_x = float(x)
        self.view_w = max(1.0, float(w))
        self._recalc_visible()

    def get_visible_range(self) -> VisibleRange:
        return self._visible

    # -------------------------------------------------------------------------
    # ZOOM ESTILO TRADINGVIEW — ANCLADO AL MOUSE
    # -------------------------------------------------------------------------
    def zoom_by_drag(self, anchor_x: float, dx_px: float) -> None:
        if self.total_bars < 2 or abs(dx_px) < 0.5:
            return

        zoom_factor = 1.0 + dx_px * 0.011
        zoom_factor = max(0.35, min(zoom_factor, 3.5))

        old_spacing = self.bar_spacing
        new_spacing = _clamp(old_spacing * zoom_factor, self.min_bar_spacing, self.max_bar_spacing)

        if abs(new_spacing - old_spacing) < 0.005:
            return

        # índice bajo el mouse ANTES del zoom
        idx_before = self._float_index_at_x(anchor_x)

        # aplicar spacing
        self.bar_spacing = new_spacing

        # índice bajo el mouse DESPUÉS del zoom
        idx_after = self._float_index_at_x(anchor_x)

        # corregir offset
        self.right_offset += (idx_after - idx_before)

        self._clamp_right_offset()
        self._recalc_visible()

    # -------------------------------------------------------------------------
    # PAN
    # -------------------------------------------------------------------------
    def pan_by_pixels(self, dx_px: float) -> None:
        if self.total_bars <= 0:
            return

        self.right_offset += dx_px / self.bar_spacing
        self._clamp_right_offset()
        self._recalc_visible()

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------
    @property
    def _last_data_index(self) -> float:
        return self.total_bars - 1.0

    def _right_anchor_x(self):
        return self.view_x + self.view_w


    def _float_index_at_x(self, x: float) -> float:
        if self.total_bars <= 0:
            return 0.0

        return self._last_data_index - (
            (self._right_anchor_x() - float(x)) / max(0.1, self.bar_spacing)
        )

    # -------------------------------------------------------------------------
    # RECALC VISIBLE RANGE (CON FIX DE INDEXERROR)
    # -------------------------------------------------------------------------
    def _recalc_visible(self) -> None:
        if self.total_bars <= 0 or not self._timestamps:
            self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)
            return

        self.bar_spacing = _clamp(self.bar_spacing, self.min_bar_spacing, self.max_bar_spacing)
        self._clamp_right_offset()

        left_float = self._float_index_at_x(self.view_x)
        right_float = self._float_index_at_x(self.view_x + self.view_w)

        start_idx = int(math.floor(min(left_float, right_float)))
        end_idx   = int(math.ceil(max(left_float, right_float)))

        # Clamp duro
        start_idx = max(0, min(start_idx, self.total_bars - 1))
        end_idx   = max(0, min(end_idx,   self.total_bars - 1))

        if end_idx < start_idx:
            end_idx = start_idx

        self._visible = VisibleRange(
            start_ts=self._timestamps[start_idx],
            end_ts=self._timestamps[end_idx],
            start_idx=start_idx,
            end_idx=end_idx,
        )

    # -------------------------------------------------------------------------
    # POSICIÓN DE VELAS
    # -------------------------------------------------------------------------
    def index_to_x(self, index: int | float) -> float:
        if self.total_bars <= 0:
            return self.view_x

        bars_from_last = self._last_data_index - float(index)
        x = self._right_anchor_x() - bars_from_last * self.bar_spacing

        return x  # ❗ No restar padding

    def x_to_index(self, x: float) -> int:
        if self.total_bars <= 0:
            return 0

        idx = round(self._float_index_at_x(x))
        return int(_clamp(idx, 0, self.total_bars - 1))

    # -------------------------------------------------------------------------
    # TICKS (RESTORED — Opción 1)
    # -------------------------------------------------------------------------
    def _snap_to_nice_spacing(self, value: float) -> float:
        nice_values = [
            0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
            1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0,
            8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0,
            60.0, 80.0, 100.0, 120.0, 150.0, 200.0, 250.0, 300.0,
        ]
        closest = min(nice_values, key=lambda x: abs(x - value))
        return _clamp(closest, self.min_bar_spacing, self.max_bar_spacing)

    def get_tick_indices(
        self,
        min_spacing_px: float,
        extend_by_one: bool = False,
    ) -> List[int]:

        if not self._timestamps or self.total_bars == 0:
            return []

        vr = self.get_visible_range()
        vs = max(0, int(vr.start_idx))
        ve = min(self.total_bars - 1, int(vr.end_idx))

        if vs >= ve:
            return [vs]

        start_ts = self._timestamps[vs]
        last_visible_real_ts = self._timestamps[ve]

        visible_duration_sec = max(0.0, (last_visible_real_ts - start_ts).total_seconds())
        step_minutes = self._choose_tick_step_minutes(visible_duration_sec)

        indices: List[int] = []
        current = self._floor_time_to_step(start_ts, step_minutes)

        right_edge_x = (self.view_x + self.view_w - self.right_padding_px) + (self.bar_spacing * 1.8)

        safety_steps = 500

        for _ in range(safety_steps):
            idx = self._time_to_virtual_index(current)
            x = self.get_aligned_x(idx)

            if x > right_edge_x:
                break

            if x >= self.view_x - min_spacing_px * 1.5:
                indices.append(idx)

            current += timedelta(minutes=step_minutes)

        indices = sorted(set(indices))
        indices = self._filter_indices_by_spacing(indices, min_spacing_px)

        if extend_by_one and indices:
            indices = self._extend_ticks_safely(indices, step_minutes, min_spacing_px, right_edge_x)

        return indices

    def _extend_ticks_safely(
        self,
        indices: List[int],
        step_minutes: int,
        min_spacing_px: float,
        right_edge_x: float,
    ) -> List[int]:

        if not indices:
            return indices

        result = indices[:]

        first_time = self._index_to_virtual_time(result[0])
        left_time = first_time - timedelta(minutes=step_minutes)
        left_idx = self._time_to_virtual_index(left_time)

        if left_idx >= 0:
            x_first = self.get_aligned_x(result[0])
            x_left = self.get_aligned_x(left_idx)
            if abs(x_first - x_left) >= min_spacing_px:
                result.insert(0, left_idx)

        last_time = self._index_to_virtual_time(result[-1])
        right_time = last_time + timedelta(minutes=step_minutes)
        right_idx = self._time_to_virtual_index(right_time)

        x_last = self.get_aligned_x(result[-1])
        x_right = self.get_aligned_x(right_idx)

        if x_right <= right_edge_x + (self.bar_spacing * 1.2) and abs(x_right - x_last) >= min_spacing_px:
            result.append(right_idx)

        return result

    def _choose_tick_step_minutes(self, visible_duration_sec: float) -> int:
        if visible_duration_sec < 900:
            return 1
        if visible_duration_sec < 3600:
            return 5
        if visible_duration_sec < 10800:
            return 10
        if visible_duration_sec < 21600:
            return 15
        return 30

    def _floor_time_to_step(self, ts: datetime, step_minutes: int) -> datetime:
        clean = ts.replace(second=0, microsecond=0)
        minute = (clean.minute // step_minutes) * step_minutes
        return clean.replace(minute=minute)

    def _infer_seconds_per_bar(self) -> float:
        if len(self._timestamps) < 2:
            return 60.0
        diffs = []
        start = max(1, len(self._timestamps) - 50)
        for i in range(start, len(self._timestamps)):
            diff = (self._timestamps[i] - self._timestamps[i - 1]).total_seconds()
            if diff > 0:
                diffs.append(diff)
        if not diffs:
            return 60.0
        diffs.sort()
        return diffs[len(diffs) // 2]

    def _time_to_virtual_index(self, ts: datetime) -> int:
        if not self._timestamps:
            return 0
        last_ts = self._timestamps[-1]
        if ts <= last_ts:
            return self._find_closest_index(ts)
        seconds_per_bar = max(1.0, self._infer_seconds_per_bar())
        extra_seconds = (ts - last_ts).total_seconds()
        extra_bars = int(round(extra_seconds / seconds_per_bar))
        return (self.total_bars - 1) + extra_bars

    def _index_to_virtual_time(self, index: int) -> datetime:
        if not self._timestamps:
            return datetime.min
        if 0 <= index < self.total_bars:
            return self._timestamps[index]
        seconds_per_bar = max(1.0, self._infer_seconds_per_bar())
        extra_bars = index - (self.total_bars - 1)
        return self._timestamps[-1] + timedelta(seconds=extra_bars * seconds_per_bar)

    def _filter_indices_by_spacing(self, indices: List[int], min_spacing_px: float) -> List[int]:
        if min_spacing_px <= 0 or len(indices) <= 1:
            return indices
        filtered: List[int] = []
        last_x: float | None = None
        for i in indices:
            x = self.get_aligned_x(i)
            if last_x is None or abs(x - last_x) >= min_spacing_px:
                filtered.append(i)
                last_x = x
        return filtered

    def _find_closest_index(self, target_ts: datetime) -> int:
        if not self._timestamps:
            return 0
        left, right = 0, len(self._timestamps) - 1
        while left <= right:
            mid = (left + right) // 2
            if self._timestamps[mid] == target_ts:
                return mid
            if self._timestamps[mid] < target_ts:
                left = mid + 1
            else:
                right = mid - 1
        if left >= len(self._timestamps):
            return len(self._timestamps) - 1
        if left == 0:
            return 0
        before = self._timestamps[left - 1]
        after = self._timestamps[left]
        if abs((after - target_ts).total_seconds()) < abs((before - target_ts).total_seconds()):
            return left
        return left - 1
    def get_px_per_bar(self) -> float:
        return max(1.0, self.bar_spacing)

    def get_right_draw_limit(self) -> float:
        return self.view_x + self.view_w - self.right_padding_px

    def get_aligned_x(self, index: int | float, crisp: bool = True) -> float:
        x = float(self.index_to_x(index))
        if crisp:
            x = round(x) + 1.0
        return x
