"""Chart principal.

Chart Engine central:
- Mantiene series y overlays
- Coordina TimeScale / PriceScale
- Expone una API simple para agregar series y overlays
- Dibuja en orden: overlays base -> series -> overlays front

Más adelante aquí podremos agregar:
- panes
- append/update de data
- indicadores
- set_visible_range
- autoscale configurable
"""
from __future__ import annotations

from typing import Any, List, Optional


class Chart:
    def __init__(self) -> None:
        self.series: List[Any] = []
        self.base_overlays: List[Any] = []
        self.front_overlays: List[Any] = []

        self.time_scale: Optional[Any] = None
        self.price_scale: Optional[Any] = None

    def set_scales(self, time_scale: Any, price_scale: Any) -> None:
        self.time_scale = time_scale
        self.price_scale = price_scale

    def add_series(self, series: Any) -> None:
        self.series.append(series)

    def add_overlay(self, overlay: Any, layer: str = "base") -> None:
        if layer == "front":
            self.front_overlays.append(overlay)
        else:
            self.base_overlays.append(overlay)

    def clear_series(self) -> None:
        self.series.clear()

    def clear_overlays(self) -> None:
        self.base_overlays.clear()
        self.front_overlays.clear()

    def get_visible_range(self):
        if self.time_scale is None:
            return None
        if not hasattr(self.time_scale, "get_visible_range"):
            return None
        return self.time_scale.get_visible_range()

    def draw(self, renderer: Any) -> None:
        if self.time_scale is None or self.price_scale is None:
            return

        vr = self.get_visible_range()
        if vr is None:
            return

        # 1) overlays base
        for overlay in self.base_overlays:
            if hasattr(overlay, "draw"):
                overlay.draw(renderer)

        # 2) series
        if vr.end_idx >= vr.start_idx:
            for s in self.series:
                if hasattr(s, "draw"):
                    s.draw(
                        renderer,
                        self.time_scale,
                        self.price_scale,
                        vr.start_idx,
                        vr.end_idx,
                    )

        # 3) overlays front
        for overlay in self.front_overlays:
            if hasattr(overlay, "draw"):
                overlay.draw(renderer)