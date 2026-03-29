from __future__ import annotations
from dataclasses import dataclass
from typing import List, Any, Tuple


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
        self.series: List[Any] = []
        self.overlays: List[Any] = []
        self.config = PaneConfig(name=name, height_ratio=height_ratio)

    def add_series(self, series: Any) -> None:
        self.series.append(series)

    def add_overlay(self, overlay: Any) -> None:
        self.overlays.append(overlay)

    def draw(self, renderer: Any, time_scale: Any, price_scale: Any, 
             visible_start: int, visible_end: int) -> None:
        for s in self.series:
            if hasattr(s, "draw"):
                s.draw(renderer, time_scale, price_scale, visible_start, visible_end)

        for o in self.overlays:
            if hasattr(o, "draw"):
                o.draw(renderer)


class PaneManager:
    """Gestiona todos los panes del gráfico"""
    
    def __init__(self):
        self.panes: List[Pane] = []
        self.separator_width: float = 2.0
        self.separator_color: Tuple[float, float, float, float] = (0.22, 0.22, 0.22, 1.0)

    def add_pane(self, pane: Pane) -> None:
        self.panes.append(pane)

    def get_total_height_ratio(self) -> float:
        return sum(p.config.height_ratio for p in self.panes if p.config.show)

    def draw_separators(self, renderer: Any, pane_rects: List[Tuple[float, float, float, float]]) -> None:
        for i in range(1, len(pane_rects)):
            x, y, w, h = pane_rects[i]
            renderer.draw_line_px(x, y-1, x + w, y-1, 
                                color=self.separator_color, 
                                width=self.separator_width)