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
        right_padding_px: float = 50.0,
    ) -> None:
        self.bar_spacing = float(bar_spacing)
        self.min_bar_spacing = float(min_bar_spacing)
        self.max_bar_spacing = float(max_bar_spacing)
        self.right_offset = float(right_offset)

        self.max_right_offset = float(max_right_offset)
        self.right_padding_px = float(right_padding_px)
        self.min_right_offset = -1_000_000.0

        self.total_bars: int = 0
        self.view_x: float = 0.0
        self.view_w: float = 1.0
        self._timestamps: List[datetime] = []
        self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)

    def _clamp_right_offset(self) -> None:
        if self.total_bars <= 1:
            self.right_offset = max(0.0, self.right_offset)
            return

        self.right_offset = max(-(self.total_bars - 1) - 50, self.right_offset)
        self.right_offset = min(self.max_right_offset, self.right_offset)

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

    def set_view(self, x: float, w: float) -> None:
        self.view_x = float(x)
        self.view_w = max(1.0, float(w))
        self._recalc_visible()

    def get_visible_range(self) -> VisibleRange:
        return self._visible

    # ====================== ZOOM Y PAN ======================
    def zoom_at_x(self, mouse_x: float, delta: float) -> None:
        if self.total_bars <= 0:
            return

        old_spacing = self.bar_spacing
        old_float_index = self._float_index_at_x(mouse_x)

        factor_zoom = 1.21
        factor = factor_zoom if delta > 0 else 1.0 / factor_zoom

        new_spacing = old_spacing * factor
        self.bar_spacing = self._snap_to_nice_spacing(new_spacing)

        new_anchor = self.view_x + self.view_w - self.right_offset * self.bar_spacing
        bars_from_last = self._last_data_index - old_float_index
        target_x = new_anchor - bars_from_last * self.bar_spacing

        delta_px = float(mouse_x) - target_x
        self.right_offset -= delta_px / self.bar_spacing

        self._clamp_right_offset()
        self._recalc_visible()

    def pan_by_pixels(self, dx_px: float) -> None:
        if self.total_bars <= 0:
            return
        self.right_offset += dx_px / self.bar_spacing
        self._clamp_right_offset()
        self._recalc_visible()

    def _snap_to_nice_spacing(self, value: float) -> float:
        nice_values = [0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
                       1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0,
                       8.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0,
                       60.0, 80.0, 100.0, 120.0, 150.0, 200.0, 250.0, 300.0]
        closest = min(nice_values, key=lambda x: abs(x - value))
        return _clamp(closest, self.min_bar_spacing, self.max_bar_spacing)

    def get_tick_indices(self, min_spacing_px: float, extend_by_one: bool = False) -> List[int]:
        """Genera ticks en horarios redondos + continúa dibujando ticks en el espacio vacío a la derecha."""
        if not self._timestamps or self.total_bars == 0:
            return []

        vr = self.get_visible_range()
        vs = max(0, int(vr.start_idx))
        ve = min(self.total_bars - 1, int(vr.end_idx))

        if vs >= ve:
            return [vs]

        start_ts = self._timestamps[vs]
        last_real_ts = self._timestamps[ve]          # Última vela real (activa)

        visible_duration_sec = (last_real_ts - start_ts).total_seconds()

        # === 1. Determinar intervalo según zoom ===
        if visible_duration_sec < 900:          # < 15 minutos
            step_minutes = 1
        elif visible_duration_sec < 3600:       # < 1 hora
            step_minutes = 5
        elif visible_duration_sec < 10800:      # < 3 horas
            step_minutes = 10
        elif visible_duration_sec < 21600:      # < 6 horas
            step_minutes = 15
        else:
            step_minutes = 30

        # === 2. Generar ticks normales hasta la última vela real ===
        nice_ticks: List[datetime] = []
        current = start_ts.replace(second=0, microsecond=0)
        minute = (current.minute // step_minutes) * step_minutes
        current = current.replace(minute=minute, second=0, microsecond=0)

        while current <= last_real_ts + timedelta(minutes=step_minutes * 2):
            nice_ticks.append(current)
            current += timedelta(minutes=step_minutes)

        # Convertir a índices reales
        indices = []
        for ts in nice_ticks:
            idx = self._find_closest_index(ts)
            if 0 <= idx < self.total_bars:
                indices.append(idx)
                

        indices = sorted(set(indices))
        
        # === 3. LÓGICA EXTRA: Continuar ticks en el espacio vacío a la derecha ===
        if indices:
            last_idx = indices[-1]
            last_ts = self._timestamps[last_idx] if last_idx < len(self._timestamps) else last_real_ts

            # Posición de la última vela real
            last_x = self.get_aligned_x(last_idx)

            # Posición del borde derecho visible (respetando right_padding_px)
            right_edge_x = self.view_x + self.view_w - self.right_padding_px

            current_ts = last_ts
            current_idx = last_idx   # índice virtual

            while True:
                current_ts += timedelta(minutes=step_minutes)
                current_idx += 1

                x_pos = self.index_to_x(current_idx)   # calcula posición aunque no exista la vela

                # Si ya pasamos el borde derecho, paramos
                if x_pos > right_edge_x:
                    break

                # Solo agregamos si mantiene buena separación
                if x_pos - last_x >= min_spacing_px * 0.9:
                    indices.append(current_idx)
                    last_x = x_pos
                    last_ts = current_ts

        # === 4. Filtrado final por espaciado en píxeles ===
        if min_spacing_px > 0 and len(indices) > 1:
            filtered = [indices[0]]
            last_x = self.get_aligned_x(indices[0])

            for i in indices[1:]:
                x = self.get_aligned_x(i)
                if x - last_x >= min_spacing_px:
                    filtered.append(i)
                    last_x = x
            indices = filtered

        # === 5. Extend by one ===
        if extend_by_one and indices:
            if indices[0] > 0:
                indices.insert(0, indices[0] - 1)
            # Permitimos un poco más allá de la última vela real
            indices.append(indices[-1] + 1)

        
    
        return sorted(set(indices))

    def _find_closest_index(self, target_ts: datetime) -> int:
        """Busca el índice más cercano (permite extrapolación)"""
        if not self._timestamps:
            return 0

        left, right = 0, len(self._timestamps) - 1
        while left <= right:
            mid = (left + right) // 2
            if self._timestamps[mid] == target_ts:
                return mid
            elif self._timestamps[mid] < target_ts:
                left = mid + 1
            else:
                right = mid - 1

        if left >= len(self._timestamps):
            return len(self._timestamps) - 1
        if left == 0:
            return 0

        if abs((self._timestamps[left] - target_ts).total_seconds()) < \
           abs((self._timestamps[left - 1] - target_ts).total_seconds()):
            return left
        return left - 1

    # ====================== INTERNOS ======================
    @property
    def _last_data_index(self) -> float:
        return self.total_bars - 1.0

    def _right_anchor_x(self) -> float:
        return self.view_x + self.view_w - self.right_offset * self.bar_spacing

    def _float_index_at_x(self, x: float) -> float:
        if self.total_bars <= 0:
            return 0.0
        return self._last_data_index - ((self._right_anchor_x() - float(x)) / max(0.1, self.bar_spacing))

    def _recalc_visible(self) -> None:
        if self.total_bars <= 0 or not self._timestamps:
            self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)
            return

        self.bar_spacing = _clamp(self.bar_spacing, self.min_bar_spacing, self.max_bar_spacing)
        self._clamp_right_offset()

        left_float = self._float_index_at_x(self.view_x)
        right_float = self._float_index_at_x(self.view_x + self.view_w)

        start_idx = max(0, int(math.floor(min(left_float, right_float))) - 1)
        end_idx = min(self.total_bars - 1, int(math.ceil(max(left_float, right_float))) + 1)

        start_idx = min(start_idx, self.total_bars - 1)
        if end_idx < start_idx:
            end_idx = start_idx

        self._visible = VisibleRange(
            start_ts=self._timestamps[start_idx] if start_idx < len(self._timestamps) else datetime.min,
            end_ts=self._timestamps[end_idx] if end_idx < len(self._timestamps) else datetime.min,
            start_idx=start_idx,
            end_idx=end_idx,
        )

    def index_to_x(self, index: int | float) -> float:
        if self.total_bars <= 0:
            return self.view_x
        bars_from_last = self._last_data_index - float(index)
        x = self._right_anchor_x() - bars_from_last * self.bar_spacing
        x -= self.right_padding_px
        return x

    def x_to_index(self, x: float) -> int:
        if self.total_bars <= 0:
            return 0
        idx = round(self._float_index_at_x(x))
        return int(_clamp(idx, 0, self.total_bars - 1))

    def get_px_per_bar(self) -> float:
        return max(1.0, self.bar_spacing)

    def get_aligned_x(self, index: int | float, crisp: bool = True) -> float:
        x = float(self.index_to_x(index))
        if crisp:
            x = round(x) + 0.5
        return x