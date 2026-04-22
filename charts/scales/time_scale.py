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
    """TimeScale profesional inspirada en TradingView Lightweight Charts."""

    def __init__(
        self,
        bar_spacing: float = 12.0,
        right_offset: float = 8.0,
        min_bar_spacing: float = 3.0,
        max_bar_spacing: float = 300.0,
    ) -> None:
        self.bar_spacing = float(bar_spacing)
        self.min_bar_spacing = float(min_bar_spacing)
        self.max_bar_spacing = float(max_bar_spacing)
        self.right_offset = float(right_offset)

        self.max_right_offset = 50.0
        self.min_right_offset = -1_000_000.0

        self.total_bars: int = 0
        self.view_x: float = 0.0
        self.view_w: float = 1.0
        self._timestamps: List[datetime] = []
        self._visible = VisibleRange(datetime.min, datetime.min, 0, -1)

    # ====================== API PÚBLICA ======================
    def _clamp_right_offset(self) -> None:
        if self.total_bars <= 1:
            self.right_offset = max(0.0, self.right_offset)
            return

        self.right_offset = max(-(self.total_bars - 1), self.right_offset)
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

    def scroll_to_realtime(self) -> None:
        if self.total_bars <= 0:
            return
        self.right_offset = 0.0
        self._recalc_visible()

    def fit_content(self, padding_right_bars: float = 3.0) -> None:
        if self.total_bars <= 0:
            return
        self.right_offset = padding_right_bars
        self._recalc_visible()

    # ====================== INTERACCIÓN ======================
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

        self._clamp_right_offset()
        self._recalc_visible()

    def pan_by_pixels(self, dx_px: float) -> None:
        if self.total_bars <= 0:
            return
        self.right_offset += dx_px / self.bar_spacing
        self._clamp_right_offset()
        self._recalc_visible()

    # ====================== MÉTODOS INTERNOS ======================
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

    # ====================== MÉTODOS PARA DIBUJO ======================
    def index_to_x(self, index: int | float) -> float:
        if self.total_bars <= 0:
            return self.view_x
        bars_from_last = self._last_data_index - float(index)
        return self._right_anchor_x() - bars_from_last * self.bar_spacing

    def x_to_index(self, x: float) -> int:
        if self.total_bars <= 0:
            return 0
        idx = round(self._float_index_at_x(x))
        return int(_clamp(idx, 0, self.total_bars - 1))

    def get_px_per_bar(self) -> float:
        return max(1.0, self.bar_spacing)

    def get_tick_indices(self, min_spacing_px: float, extend_by_one: bool = False) -> List[int]:
        """Versión mejorada: etiquetas más estables y suaves al panear en TODOS los zooms"""
        vr = self.get_visible_range()
        vs = int(vr.start_idx)
        ve = int(vr.end_idx)

        if self.total_bars <= 0 or ve < vs:
            return []

        px_per_bar = self.get_px_per_bar()
        # Calculamos step de forma más inteligente
        step = max(1, math.ceil(min_spacing_px / px_per_bar))

        # Alineamos el primer tick para que las etiquetas se sientan "pegadas" y no salten al panear
        offset = vs % step
        start_idx = vs + (step - offset) % step
        if start_idx > ve:
            start_idx = vs

        indices = list(range(start_idx, ve + 1, step))

        # Incluimos un tick extra en los bordes para que aparezcan/desaparezcan suavemente
        if extend_by_one and indices:
            if indices[0] > 0:
                indices.insert(0, indices[0] - step)
            if indices[-1] < self.total_bars - 1:
                indices.append(indices[-1] + step)

        # Filtramos solo índices válidos
        return [i for i in indices if 0 <= i < self.total_bars]
    
    def get_aligned_x(self, index: int | float, crisp: bool = True) -> float:
        """VERSIÓN FUERTE: usa round() + 0.5 para alineación perfecta en TODOS los zooms"""
        x = float(self.index_to_x(index))
        if crisp:
            x = round(x) + 0.5          # ← cambio clave
        return x