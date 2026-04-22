from __future__ import annotations
from dataclasses import dataclass
from typing import List, Any, Tuple

Rect = Tuple[float, float, float, float]


@dataclass
class PaneConfig:
    name: str
    height_ratio: float = 1.0
    show: bool = True
    min_height_px: float = 60.0
    background_color: Tuple[float, float, float, float] = (0.08, 0.08, 0.08, 0.95)


class Pane:
    """Un panel individual (Precio, Volumen, Indicadores, etc.)"""

    def __init__(self, name: str, height_ratio: float = 1.0):
        self.name = name
        self.height_ratio = height_ratio
        self.config = PaneConfig(name=name, height_ratio=height_ratio)

        self.series: List[Any] = []
        self.base_overlays: List[Any] = []   # Se dibujan ANTES de las velas
        self.front_overlays: List[Any] = []  # Se dibujan DESPUÉS de las velas
        self.price_scale: Any = None

    def add_series(self, series: Any) -> None:
        self.series.append(series)

    def add_overlay(self, overlay: Any, layer: str = "base") -> None:
        """Guarda el overlay en la capa correcta"""
        if layer == "base":
            self.base_overlays.append(overlay)
        else:
            self.front_overlays.append(overlay)

    def set_price_scale(self, price_scale: Any) -> None:
        self.price_scale = price_scale

    def draw(self, renderer: Any, time_scale: Any, visible_start: int, visible_end: int) -> None:
        """Orden correcto de dibujo:
           1. Overlays base (chart_overlay + grid) → fondo y grid detrás de velas
           2. Series (velas + indicadores)
           3. Overlays front (price_axis, time_axis, crosshair, tooltip) → encima de todo
        """
        # 1. Base layer
        for o in self.base_overlays:
            if hasattr(o, "draw"):
                o.draw(renderer)

        # 2. Velas e indicadores
        for s in self.series:
            if hasattr(s, "draw"):
                s.draw(renderer, time_scale, self.price_scale or None, visible_start, visible_end)

        # 3. Front layer
        for o in self.front_overlays:
            if hasattr(o, "draw"):
                o.draw(renderer)


class PaneManager:
    """Gestiona múltiples panes con ratios de altura y separadores"""

    def __init__(self):
        self.panes: List[Pane] = []
        self.separator_width: float = 2.0
        self.separator_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 1.0)

    def add_pane(self, pane: Pane) -> None:
        self.panes.append(pane)

    def get_total_height_ratio(self) -> float:
        return sum(p.config.height_ratio for p in self.panes if p.config.show)

    def calculate_pane_rects(self, chart_x: float, chart_y: float, chart_w: float, chart_h: float) -> List[Rect]:
        if not self.panes:
            return []
        total_ratio = self.get_total_height_ratio()
        if total_ratio <= 0:
            return []

        pane_rects: List[Rect] = []
        current_y = chart_y
        for pane in self.panes:
            if not pane.config.show:
                continue
            height = (pane.config.height_ratio / total_ratio) * chart_h
            height = max(pane.config.min_height_px, height)
            pane_rects.append((chart_x, current_y, chart_w, height))
            current_y += height + self.separator_width
        return pane_rects

    def draw_separators(self, renderer: Any, pane_rects: List[Rect]) -> None:
        for i in range(1, len(pane_rects)):
            x, y, w, h = pane_rects[i]
            renderer.draw_line_px(
                x, y - self.separator_width,
                x + w, y - self.separator_width,
                color=self.separator_color,
                width=self.separator_width
            )