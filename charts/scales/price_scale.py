# charts/scales/price_scale.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple


@dataclass
class PriceRange:
    low: float
    high: float

    @property
    def length(self) -> float:
        return self.high - self.low


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

        self.log_scale: bool = False   # ← Modo logarítmico

    def toggle_log_scale(self):
        """Cambia entre escala lineal y logarítmica"""
        self.log_scale = not self.log_scale
        if self.log_scale and self._range.low <= 0:
            self._range.low = max(0.000001, self._range.low)

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
            if p <= 0:
                p = 0.000001
            t = (math.log10(p) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
        else:
            t = (p - lo) / (hi - lo)

        t = 0.05 + t * 0.90  # margen visual

        return y1 - t * usable_h if self.y_down else y0 + t * usable_h

    def y_to_price(self, y: float) -> float:
        y0 = self.view_y + self.top_padding_px
        y1 = self.view_y + self.view_h - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)

        if self.y_down:
            t = (y1 - float(y)) / usable_h
        else:
            t = (float(y) - y0) / usable_h
        t = max(0.0, min(1.0, t))

        if self.log_scale:
            lo_log = math.log10(self._range.low)
            hi_log = math.log10(self._range.high)
            return 10 ** (lo_log + t * (hi_log - lo_log))
        else:
            return self._range.low + t * (self._range.high - self._range.low)

    # Toggle con tecla (se llamará desde window.py)
    def get_ticks_ex(self, target_major: int = 10) -> Dict[str, List[Tuple[float, float]]]:
        if self.log_scale:
            return self._get_log_ticks(target_major)
        return self._get_linear_ticks(target_major)

    def _get_linear_ticks(self, target: int):
        lo, hi = self._range.low, self._range.high
        step = (hi - lo) / max(2, target)
        ticks = [(lo + i*step, self.price_to_y(lo + i*step)) for i in range(target+1)]
        return {"major": ticks, "minor": []}

    def _get_log_ticks(self, target: int):
        lo, hi = self._range.low, self._range.high
        if lo <= 0:
            lo = 0.000001
        log_lo = math.log10(lo)
        log_hi = math.log10(hi)

        ticks = []
        for exp in range(math.floor(log_lo), math.ceil(log_hi) + 1):
            for mult in [1, 2, 5]:
                price = mult * 10**exp
                if lo <= price <= hi:
                    ticks.append((price, self.price_to_y(price)))
        return {"major": ticks[:target*2], "minor": []}