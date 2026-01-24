from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from utils.math import clamp as _clamp  # ← AGREGADO AQUÍ PARA ARREGLAR EL ERROR

@dataclass
class PriceRange:
    low: float
    high: float


def _is_finite(x: float) -> bool:
    return math.isfinite(x)


def _nice_step(raw_step: float) -> float:
    if raw_step <= 0 or not _is_finite(raw_step):
        return 1.0
    exp = math.floor(math.log10(raw_step))
    f = raw_step / (10 ** exp)

    if f <= 1.0:
        nice = 1.0
    elif f <= 2.0:
        nice = 2.0
    elif f <= 5.0:
        nice = 5.0
    else:
        nice = 10.0

    return nice * (10 ** exp)


def _nice_bounds(lo: float, hi: float, step: float) -> Tuple[float, float]:
    if step <= 0:
        return lo, hi
    lo2 = math.floor(lo / step) * step
    hi2 = math.ceil(hi / step) * step
    return lo2, hi2


class PriceScale:
    def __init__(
        self,
        *,
        y_down: bool = True,
        top_padding_px: float = 6.0,
        bottom_padding_px: float = 6.0,
        min_range: float = 1e-9,
    ) -> None:
        # Viewport (PLOT)
        self.view_x: float = 0.0
        self.view_y: float = 0.0
        self.view_w: float = 1.0
        self.view_h: float = 1.0

        # Guardamos también para y_to_price
        self.plot_x: float = 0.0
        self.plot_y: float = 0.0
        self.plot_w: float = 1.0
        self.plot_h: float = 1.0

        # Coordinate system
        self.y_down: bool = bool(y_down)

        # Visual padding inside plot
        self.top_padding_px: float = float(top_padding_px)
        self.bottom_padding_px: float = float(bottom_padding_px)

        # Range
        self._range: PriceRange = PriceRange(0.0, 1.0)
        self._manual_range: Optional[PriceRange] = None

        # Safety
        self._min_range = float(min_range)

    # -------------------------
    # View / Config
    # -------------------------
    def set_viewport(self, x: float, y: float, w: float, h: float) -> None:
        self.view_x = float(x)
        self.view_y = float(y)
        self.view_w = max(1.0, float(w))
        self.view_h = max(1.0, float(h))

        # Guardamos para y_to_price
        self.plot_x = self.view_x
        self.plot_y = self.view_y
        self.plot_w = self.view_w
        self.plot_h = self.view_h

    def set_coord_system(self, *, y_down: bool) -> None:
        self.y_down = bool(y_down)

    def set_padding(self, *, top_px: float | None = None, bottom_px: float | None = None) -> None:
        if top_px is not None:
            self.top_padding_px = max(0.0, float(top_px))
        if bottom_px is not None:
            self.bottom_padding_px = max(0.0, float(bottom_px))

    # -------------------------
    # Range control
    # -------------------------
    def set_manual_range(self, low: float, high: float) -> None:
        """
        “Bloquea” el rango (para cuando implementemos drag del eje de precios).
        """
        lo = float(low)
        hi = float(high)
        if not (_is_finite(lo) and _is_finite(hi)):
            return
        if hi - lo < self._min_range:
            mid = 0.5 * (hi + lo)
            lo = mid - 0.5 * self._min_range
            hi = mid + 0.5 * self._min_range
        self._manual_range = PriceRange(lo, hi)
        self._range = self._manual_range

    def clear_manual_range(self) -> None:
        self._manual_range = None

    def set_range(self, low: float, high: float) -> None:
        """
        Setea el rango efectivo SOLO si no hay manual_range activo.
        """
        if self._manual_range is not None:
            return

        lo = float(low)
        hi = float(high)
        if not (_is_finite(lo) and _is_finite(hi)):
            return

        if hi < lo:
            lo, hi = hi, lo

        if hi - lo < self._min_range:
            mid = 0.5 * (hi + lo)
            lo = mid - 0.5 * self._min_range
            hi = mid + 0.5 * self._min_range

        self._range = PriceRange(lo, hi)

    def get_range(self) -> PriceRange:
        return self._range

    # -------------------------
    # Autoscale (visible bars)
    # -------------------------
    def autoscale_from_provider(
        self,
        visible_start: int,
        visible_end: int,
        get_high_low: Callable[[int], Tuple[float, float]],
        *,
        pad_ratio: float = 0.02,
    ) -> None:
        """
        Calcula min/max SOLO en [visible_start..visible_end] usando un provider:
            get_high_low(i) -> (high, low)

        pad_ratio agrega un margen porcentual arriba/abajo.
        """
        if self._manual_range is not None:
            return
        if visible_end < visible_start:
            return

        lo = math.inf
        hi = -math.inf

        for i in range(int(visible_start), int(visible_end) + 1):
            h, l = get_high_low(i)
            h = float(h); l = float(l)
            if not (_is_finite(h) and _is_finite(l)):
                continue
            if l < lo:
                lo = l
            if h > hi:
                hi = h

        if not (_is_finite(lo) and _is_finite(hi)) or hi <= -math.inf or lo >= math.inf:
            return

        if hi < lo:
            lo, hi = hi, lo

        rng = max(self._min_range, hi - lo)
        pad = rng * float(max(0.0, pad_ratio))

        self.set_range(lo - pad, hi + pad)

    def autoscale_from_hilo_arrays(
        self,
        visible_start: int,
        visible_end: int,
        highs: Sequence[float],
        lows: Sequence[float],
        *,
        pad_ratio: float = 0.02,
    ) -> None:
        """
        Variante rápida si ya tenés arrays highs/lows.
        """
        n = min(len(highs), len(lows))
        if n <= 0:
            return
        vs = _clamp(float(visible_start), 0, n - 1)
        ve = _clamp(float(visible_end), 0, n - 1)
        self.autoscale_from_provider(
            int(vs),
            int(ve),
            lambda i: (highs[i], lows[i]),
            pad_ratio=pad_ratio,
        )

    # -------------------------
    # Mapping
    # -------------------------
    def price_to_y(self, price: float) -> float:
        """
        Mapea precio -> y en pixeles DENTRO del plot.
        """
        p = float(price)
        lo, hi = self._range.low, self._range.high

        # Evitar división por cero
        rng = max(self._min_range, hi - lo)

        # Área usable (respetando padding)
        y0 = self.view_y + self.top_padding_px
        y1 = (self.view_y + self.view_h) - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)

        t = (p - lo) / rng  # 0..1

        # y_down: high arriba (t=1 => y=y0)
        if self.y_down:
            # low (t=0) abajo => y1
            return float(y1 - t * usable_h)
        else:
            # y_up: low abajo (y0), high arriba (y1) en coords y-up
            return float(y0 + t * usable_h)

    def y_to_price(self, y: float) -> float:
        """
        Mapea y(px) -> precio.
        """
        lo, hi = self._range.low, self._range.high
        rng = max(self._min_range, hi - lo)

        y0 = self.view_y + self.top_padding_px
        y1 = (self.view_y + self.view_h) - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)

        yy = float(y)
        if self.y_down:
            # y=y1 => t=0 ; y=y0 => t=1
            t = (y1 - yy) / usable_h
        else:
            t = (yy - y0) / usable_h

        t = _clamp(t, 0.0, 1.0)
        return float(lo + t * rng)

    # -------------------------
    # Ticks
    # -------------------------
    def get_ticks(self, target_count: int = 8) -> List[Tuple[float, float]]:
        """
        Devuelve lista de ticks como (price, y_px).
        OJO: todavía no renderizamos texto, pero esto ya sirve para líneas/ticks.
        """
        lo, hi = self._range.low, self._range.high
        rng = max(self._min_range, hi - lo)

        n = max(2, int(target_count))
        raw_step = rng / (n - 1)
        step = _nice_step(raw_step)

        lo2, hi2 = _nice_bounds(lo, hi, step)

        ticks: List[Tuple[float, float]] = []
        # Evitar loops infinitos si step raro
        if step <= 0 or not _is_finite(step):
            return ticks

        # Arrancar en el primer múltiplo >= lo2
        v = lo2
        # límite duro por seguridad
        max_iter = 512
        it = 0
        while v <= hi2 + 1e-12 and it < max_iter:
            y = self.price_to_y(v)
            ticks.append((float(v), float(y)))
            v += step
            it += 1

        return ticks