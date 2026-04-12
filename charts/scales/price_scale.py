from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class PriceRange:
    low: float
    high: float


class PriceScale:
    def __init__(
        self,
        *,
        y_down: bool = True,
        top_padding_px: float = 12.0,
        bottom_padding_px: float = 12.0,
    ) -> None:
        self.view_x = 0.0
        self.view_y = 0.0
        self.view_w = 1.0
        self.view_h = 1.0

        self.y_down = y_down
        self.top_padding_px = top_padding_px
        self.bottom_padding_px = bottom_padding_px

        self._range = PriceRange(100.0, 200.0)
        self._manual_range: Optional[PriceRange] = None
        self.log_scale: bool = False

    # ==================== AUTOSCALE Y DRAG ====================
    def autoscale_from_provider(
        self, start_idx: int, end_idx: int,
        provider: Callable[[int], Tuple[float, float]],
        pad_ratio: float = 0.03,
    ) -> None:
        if start_idx > end_idx:
            return
        min_low = float("inf")
        max_high = float("-inf")
        for i in range(start_idx, end_idx + 1):
            h, l = provider(i)
            max_high = max(max_high, h)
            min_low = min(min_low, l)
        if max_high <= min_low:
            return
        padding = (max_high - min_low) * pad_ratio
        self.set_range(min_low - padding, max_high + padding)

    def clear_manual_range(self) -> None: self._manual_range = None
    def start_scale(self, y: float) -> None: self._manual_range = PriceRange(self._range.low, self._range.high)
    def scale_to(self, y: float) -> None: pass
    def end_scale(self) -> None: pass

    # ==================== TICKS (con minor ticks) ====================
    def get_ticks_ex(
        self, target_major: int = 10, minor_divisions: int = 4
    ) -> Dict[str, List[Tuple[float, float]]]:
        """Devuelve major + minor ticks (como antes)"""
        if self.log_scale:
            return self._get_log_ticks(target_major)
        return self._get_linear_ticks(target_major, minor_divisions)

    def _get_linear_ticks(self, target: int, minor_divisions: int):
        lo, hi = self._range.low, self._range.high
        step = (hi - lo) / max(2, target)
        major = [(lo + i * step, self.price_to_y(lo + i * step)) for i in range(target + 1)]

        minor = []
        if minor_divisions > 0:
            minor_step = step / (minor_divisions + 1)
            for i in range(target):
                base = lo + i * step
                for j in range(1, minor_divisions + 1):
                    price = base + j * minor_step
                    minor.append((price, self.price_to_y(price)))

        return {"major": major, "minor": minor}

    def _get_log_ticks(self, target: int):
        # (mantenemos simple por ahora)
        lo, hi = self._range.low, self._range.high
        if lo <= 0: lo = 0.000001
        log_lo = math.log10(lo)
        log_hi = math.log10(hi)
        ticks = []
        for exp in range(math.floor(log_lo), math.ceil(log_hi) + 1):
            for mult in [1, 2, 5]:
                price = mult * 10**exp
                if lo <= price <= hi:
                    ticks.append((price, self.price_to_y(price)))
        return {"major": ticks[:target*2], "minor": []}

    # ==================== Resto de métodos (sin cambios) ====================
    def set_viewport(self, x: float, y: float, w: float, h: float):
        self.view_x = float(x)
        self.view_y = float(y)
        self.view_w = max(1.0, float(w))
        self.view_h = max(1.0, float(h))

    def set_range(self, low: float, high: float):
        if self._manual_range is not None:
            return
        low = max(0.000001, float(low))
        high = max(low * 1.001, float(high))
        self._range = PriceRange(low, high)

    def price_to_y(self, price: float) -> float:
        p = float(price)
        lo, hi = self._range.low, self._range.high
        y0 = self.view_y + self.top_padding_px
        y1 = self.view_y + self.view_h - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)

        if self.log_scale:
            if p <= 0: p = 0.000001
            t = (math.log10(p) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
        else:
            t = (p - lo) / (hi - lo)
        t = 0.05 + t * 0.90
        return y1 - t * usable_h if self.y_down else y0 + t * usable_h

    def toggle_log_scale(self):
        self.log_scale = not self.log_scale
        if self.log_scale and self._range.low <= 0:
            self._range.low = max(0.000001, self._range.low)