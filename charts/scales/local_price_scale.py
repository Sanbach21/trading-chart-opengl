from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple
import math


@dataclass
class PriceRange:
    low: float
    high: float


class LocalPriceScale:
    """
    Escala de precio compartida para arquitectura B.

    Responsabilidades:
    - almacenar rango visible de precios
    - convertir price <-> y
    - autoscale desde un provider(index) -> (high, low)
    - soportar zoom vertical manual (drag / wheel)
    - exponer viewport del plot

    Esta clase reemplaza el uso del PriceScale clásico en:
    - candles
    - axis
    - grid
    - crosshair
    """

    def __init__(
        self,
        *,
        y_down: bool = True,
        top_padding_px: float = 0.0,
        bottom_padding_px: float = 0.0,
    ) -> None:
        self.y_down = bool(y_down)
        self.top_padding_px = float(top_padding_px)
        self.bottom_padding_px = float(bottom_padding_px)

        self._range = PriceRange(0.0, 1.0)
        self._manual_range: Optional[PriceRange] = None

        self._viewport: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)

        # estado de scaling manual
        self._scale_anchor_y: Optional[float] = None
        self._scale_anchor_price: Optional[float] = None
        self._scale_start_range: Optional[PriceRange] = None

    # ─────────────────────────────────────────────
    # Viewport
    # ─────────────────────────────────────────────

    def set_viewport(self, x: float, y: float, w: float, h: float) -> None:
        self._viewport = (float(x), float(y), float(max(1.0, w)), float(max(1.0, h)))

    def get_viewport(self) -> Tuple[float, float, float, float]:
        return self._viewport

    # ─────────────────────────────────────────────
    # Rango
    # ─────────────────────────────────────────────

    @property
    def _min_price(self) -> float:
        return self._range.low

    @property
    def _max_price(self) -> float:
        return self._range.high

    def set_range(self, low: float, high: float) -> None:
        low = float(low)
        high = float(high)

        if not math.isfinite(low) or not math.isfinite(high):
            return

        if high <= low:
            center = (low + high) * 0.5
            low = center - 0.5
            high = center + 0.5

        self._range = PriceRange(low, high)

        if self._manual_range is not None:
            self._manual_range = PriceRange(low, high)

    def clear_manual_range(self) -> None:
        self._manual_range = None

    # ─────────────────────────────────────────────
    # Autoscale
    # ─────────────────────────────────────────────

    def update_from_provider(
        self,
        start_idx: int,
        end_idx: int,
        provider: Callable[[int], Tuple[float, float]],
        pad_ratio: float = 0.02,
    ) -> None:
        """
        Actualiza el rango usando provider(i) -> (high, low).
        Respeta _manual_range: si está activa, no sobrescribe.
        """
        if start_idx > end_idx:
            return

        if self._manual_range is not None:
            return

        min_low = float("inf")
        max_high = float("-inf")

        for i in range(start_idx, end_idx + 1):
            h, l = provider(i)
            h = float(h)
            l = float(l)

            if h > max_high:
                max_high = h
            if l < min_low:
                min_low = l

        if not math.isfinite(min_low) or not math.isfinite(max_high):
            return

        if max_high <= min_low:
            center = min_low
            self._range = PriceRange(center - 0.5, center + 0.5)
            return

        pad = (max_high - min_low) * float(pad_ratio)
        self._range = PriceRange(min_low - pad, max_high + pad)

    # alias de compatibilidad
    def autoscale_from_provider(
        self,
        start_idx: int,
        end_idx: int,
        provider: Callable[[int], Tuple[float, float]],
        pad_ratio: float = 0.02,
    ) -> None:
        self.update_from_provider(start_idx, end_idx, provider, pad_ratio=pad_ratio)

    # ─────────────────────────────────────────────
    # Conversión price <-> y
    # ─────────────────────────────────────────────

    def _usable_vertical_area(self) -> Tuple[float, float]:
        """
        Devuelve y_top usable y alto usable considerando padding superior/inferior.
        """
        _, y, _, h = self._viewport
        y_top = y + self.top_padding_px
        usable_h = max(1.0, h - self.top_padding_px - self.bottom_padding_px)
        return y_top, usable_h

    def price_to_y(self, price: float) -> float:
        price = float(price)
        low = self._range.low
        high = self._range.high
        rng = high - low

        y_top, usable_h = self._usable_vertical_area()

        if rng <= 1e-12:
            return y_top + usable_h * 0.5

        t = (price - low) / rng

        if self.y_down:
            return y_top + (1.0 - t) * usable_h
        return y_top + t * usable_h

    def y_to_price(self, y: float) -> float:
        y = float(y)
        low = self._range.low
        high = self._range.high
        rng = high - low

        y_top, usable_h = self._usable_vertical_area()

        if rng <= 1e-12:
            return low

        rel = (y - y_top) / usable_h
        rel = max(0.0, min(1.0, rel))

        if self.y_down:
            t = 1.0 - rel
        else:
            t = rel

        return low + t * rng

    # ─────────────────────────────────────────────
    # Scaling manual (drag / wheel)
    # ─────────────────────────────────────────────

    def start_scale(self, anchor_y: float) -> None:
        """
        Inicia zoom vertical manual alrededor del precio bajo anchor_y.
        """
        anchor_y = float(anchor_y)
        self._scale_anchor_y = anchor_y
        self._scale_anchor_price = self.y_to_price(anchor_y)
        self._scale_start_range = PriceRange(self._range.low, self._range.high)

        # al iniciar manipulación manual, congelamos autoscale
        self._manual_range = PriceRange(self._range.low, self._range.high)

    # def scale_to(self, current_y: float) -> None:
    #     """
    #     Ajusta el rango manual en función del desplazamiento vertical.
    #     """
    #     if self._scale_anchor_y is None or self._scale_start_range is None or self._scale_anchor_price is None:
    #         return

    #     current_y = float(current_y)
    #     dy = current_y - self._scale_anchor_y

    #     start_low = self._scale_start_range.low
    #     start_high = self._scale_start_range.high
    #     start_rng = start_high - start_low

    #     if start_rng <= 1e-12:
    #         return

    #     # factor de zoom suave:
    #     # dy > 0 => zoom out
    #     # dy < 0 => zoom in
    #     zoom_factor = math.exp(dy * 0.01)

    #     new_rng = max(1e-9, start_rng * zoom_factor)

    #     _, y0, _, h = self._viewport
    #     y_top, usable_h = self._usable_vertical_area()

    #     if usable_h <= 1e-9:
    #         return

    #     rel = (self._scale_anchor_y - y_top) / usable_h
    #     rel = max(0.0, min(1.0, rel))

    #     if self.y_down:
    #         anchor_t = 1.0 - rel
    #     else:
    #         anchor_t = rel

    #     anchor_price = self._scale_anchor_price

    #     new_low = anchor_price - anchor_t * new_rng
    #     new_high = new_low + new_rng

    #     self._range = PriceRange(new_low, new_high)
    #     self._manual_range = PriceRange(new_low, new_high)

    def end_scale(self) -> None:
        self._scale_anchor_y = None
        self._scale_anchor_price = None
        self._scale_start_range = None