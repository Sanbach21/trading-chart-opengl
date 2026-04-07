# charts/chart.py
from __future__ import annotations
from typing import Any

from charts.panes import PaneManager, Pane


class Chart:
    """
    Motor principal del gráfico con soporte multi-pane completo.
    """

    def __init__(self) -> None:
        self.pane_manager = PaneManager()

        # Pane principal
        self.main_pane = Pane("main", height_ratio=3.0)
        self.pane_manager.add_pane(self.main_pane)

        self.time_scale: Any = None
        self.price_scale: Any = None
        self.base_series: Any = None

    def set_scales(self, time_scale: Any, price_scale: Any) -> None:
        self.time_scale = time_scale
        self.price_scale = price_scale
        self.main_pane.set_price_scale(price_scale)

    def add_series(self, series: Any, pane_name: str = "main") -> None:
        for pane in self.pane_manager.panes:
            if pane.name == pane_name:
                pane.add_series(series)
                if pane_name == "main" and hasattr(series, "data"):
                    self.base_series = series
                return

        # Crear pane automáticamente si no existe
        new_pane = Pane(pane_name, height_ratio=1.0)
        new_pane.add_series(series)
        self.pane_manager.add_pane(new_pane)

    def add_indicator(self, indicator: Any, pane_name: str = "main") -> None:
        self.add_series(indicator, pane_name)

    def add_overlay(self, overlay: Any, layer: str = "base", pane_name: str = "main") -> None:
        for pane in self.pane_manager.panes:
            if pane.name == pane_name:
                pane.add_overlay(overlay)
                return
        new_pane = Pane(pane_name, height_ratio=1.0)
        new_pane.add_overlay(overlay)
        self.pane_manager.add_pane(new_pane)

    def update_indicators(self) -> None:
        """Actualiza todos los indicadores (llamado desde live feed)"""
        if self.base_series is None or not hasattr(self.base_series, "data"):
            return

        base_data = self.base_series.data

        for pane in self.pane_manager.panes:
            for series in pane.series:
                if hasattr(series, "calculate") and hasattr(series, "values"):
                    series.values = series.calculate(base_data)

    def draw(self, renderer: Any) -> None:
        if self.time_scale is None or self.price_scale is None:
            return

        vr = self.time_scale.get_visible_range()
        if vr.end_idx < vr.start_idx:
            return

        # Dibujar todos los panes
        for pane in self.pane_manager.panes:
            if pane.config.show:
                pane.draw(renderer, self.time_scale, vr.start_idx, vr.end_idx)

        # Separadores entre panes
        pane_rects = self.pane_manager.calculate_pane_rects(0, 0, 800, 600)  # temporal
        self.pane_manager.draw_separators(renderer, pane_rects)