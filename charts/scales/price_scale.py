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

        self._drag_anchor_y: float = 0.0
        self._drag_anchor_price: float = 0.0
        self._drag_start_range: Optional[PriceRange] = None

    def autoscale_from_provider(
        self,
        start_idx: int,
        end_idx: int,
        provider: Callable[[int], Tuple[float, float]],
        pad_ratio: float = 0.03,
    ) -> None:
        if start_idx > end_idx or self._manual_range is not None:
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

    def clear_manual_range(self) -> None:
        self._manual_range = None

    def start_scale(self, y: float) -> None:
        self._manual_range = PriceRange(self._range.low, self._range.high)
        self._drag_anchor_y = float(y)
        self._drag_anchor_price = self.y_to_price(y)
        self._drag_start_range = PriceRange(self._range.low, self._range.high)

    def scale_to(self, y: float) -> None:
        if self._manual_range is None or self._drag_start_range is None:
            return

        dy = float(y) - self._drag_anchor_y
        zoom_factor = 1.0 - (dy / 280.0)
        zoom_factor = max(0.15, zoom_factor)

        anchor = self._drag_anchor_price
        old_low = self._drag_start_range.low
        old_high = self._drag_start_range.high

        new_low = anchor - (anchor - old_low) * zoom_factor
        new_high = anchor + (old_high - anchor) * zoom_factor

        self.set_range(new_low, new_high)

    def end_scale(self) -> None:
        self._drag_start_range = None

    def get_ticks_ex(
        self,
        target_major: int = 10,
        minor_divisions: int = 4,
    ) -> Dict[str, List[Tuple[float, float]]]:
        if self.log_scale:
            return self._get_log_ticks(target_major)
        return self._get_linear_ticks(target_major, minor_divisions)

    def _nice_step(self, raw_step: float) -> float:
        if raw_step <= 0 or not math.isfinite(raw_step):
            return 1.0

        exponent = math.floor(math.log10(raw_step))
        base = 10 ** exponent
        fraction = raw_step / base

        if fraction <= 1.0:
            nice = 1.0
        elif fraction <= 2.0:
            nice = 2.0
        elif fraction <= 2.5:
            nice = 2.5
        elif fraction <= 5.0:
            nice = 5.0
        else:
            nice = 10.0

        return nice * base

    def _get_linear_ticks(
        self,
        target: int,
        minor_divisions: int,
    ) -> Dict[str, List[Tuple[float, float]]]:
        lo, hi = self._range.low, self._range.high

        if hi <= lo:
            return {"major": [], "minor": []}

        target = max(4, int(target))
        raw_step = (hi - lo) / max(1, target - 1)
        step = self._nice_step(raw_step)

        first = math.floor(lo / step) * step
        last = math.ceil(hi / step) * step

        major_prices: List[float] = []
        price = first - step
        safety = 0

        while price <= last + step and safety < 300:
            major_prices.append(price)
            price += step
            safety += 1

        major: List[Tuple[float, float]] = []

        for price in major_prices:
            if lo <= price <= hi:
                major.append((price, self.price_to_y(price)))

        if len(major) < 4:
            step = self._nice_step(raw_step / 2.0)

            first = math.floor(lo / step) * step
            last = math.ceil(hi / step) * step

            major_prices = []
            price = first - step
            safety = 0

            while price <= last + step and safety < 300:
                major_prices.append(price)
                price += step
                safety += 1

            major = []
            for price in major_prices:
                if lo <= price <= hi:
                    major.append((price, self.price_to_y(price)))

        minor: List[Tuple[float, float]] = []

        if minor_divisions > 0:
            minor_step = step / (minor_divisions + 1)

            for major_price in major_prices:
                for j in range(1, minor_divisions + 1):
                    minor_price = major_price + j * minor_step

                    if lo <= minor_price <= hi:
                        minor.append((minor_price, self.price_to_y(minor_price)))

        return {"major": major, "minor": minor}

    def _get_log_ticks(self, target: int) -> Dict[str, List[Tuple[float, float]]]:
        lo, hi = self._range.low, self._range.high

        if lo <= 0:
            lo = 0.000001

        log_lo = math.log10(lo)
        log_hi = math.log10(hi)

        ticks: List[Tuple[float, float]] = []

        for exp in range(math.floor(log_lo), math.ceil(log_hi) + 1):
            for mult in [1, 2, 5]:
                price = mult * 10**exp
                if lo <= price <= hi:
                    ticks.append((price, self.price_to_y(price)))

        return {"major": ticks[: target * 2], "minor": []}

    def y_to_price(self, y: float) -> float:
        y0 = self.view_y + self.top_padding_px
        y1 = self.view_y + self.view_h - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)

        if self.y_down:
            t = (y1 - float(y)) / usable_h
        else:
            t = (float(y) - y0) / usable_h

        t = max(0.0, min(1.0, (t - 0.05) / 0.90))

        lo, hi = self._range.low, self._range.high

        if self.log_scale:
            if lo <= 0:
                lo = 0.000001
            log_lo = math.log10(lo)
            log_hi = math.log10(max(hi, lo * 1.001))
            return 10 ** (log_lo + t * (log_hi - log_lo))

        return lo + t * (hi - lo)

    def price_to_y(self, price: float) -> float:
        p = float(price)
        lo, hi = self._range.low, self._range.high

        y0 = self.view_y + self.top_padding_px
        y1 = self.view_y + self.view_h - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)

        if self.log_scale:
            if p <= 0:
                p = 0.000001

            if hi == lo:
                t = 0.5
            else:
                t = (math.log10(p) - math.log10(lo)) / (
                    math.log10(hi) - math.log10(lo)
                )
        else:
            if hi == lo:
                t = 0.5
            else:
                t = (p - lo) / (hi - lo)

        t = 0.05 + t * 0.90

        if self.y_down:
            return y1 - t * usable_h

        return y0 + t * usable_h

    def set_viewport(self, x: float, y: float, w: float, h: float) -> None:
        self.view_x = float(x)
        self.view_y = float(y)
        self.view_w = max(1.0, float(w))
        self.view_h = max(1.0, float(h))

    def set_range(self, low: float, high: float) -> None:
        low = max(0.000001, float(low))
        high = max(low * 1.001, float(high))
        self._range = PriceRange(low, high)

    def toggle_log_scale(self) -> None:
        self.log_scale = not self.log_scale

        if self.log_scale and self._range.low <= 0:
            self._range.low = max(0.000001, self._range.low)