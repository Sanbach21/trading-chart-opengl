from __future__ import annotations
from typing import Any

from charts.panes import PaneManager, Pane


class Chart:
    """
    Motor principal del gráfico con soporte multi-pane.
    """

    def __init__(self) -> None:
        self.pane_manager = PaneManager()

        # Pane principal (precio + velas)
        self.main_pane = Pane("main", height_ratio=3.0)
        self.pane_manager.add_pane(self.main_pane)

        self.time_scale: Any = None
        self.price_scale: Any = None

        # Serie base del chart (normalmente velas / OHLC)
        # Se usa para recalcular indicadores en live.
        self.base_series: Any = None

    def set_scales(self, time_scale: Any, price_scale: Any) -> None:
        self.time_scale = time_scale
        self.price_scale = price_scale

    def add_series(self, series: Any, pane_name: str = "main") -> None:
        """
        Agregar serie a un pane específico.

        Si la serie se agrega al pane principal y parece ser la serie base
        (por ejemplo, velas con atributo .data), la guardamos para que
        update_indicators() pueda recalcular SMA/EMA/etc. usando esos datos.
        """
        for pane in self.pane_manager.panes:
            if pane.name == pane_name:
                pane.add_series(series)

                if pane_name == "main" and hasattr(series, "data"):
                    self.base_series = series
                return

        # Si no existe, va al main por defecto
        self.main_pane.add_series(series)
        if hasattr(series, "data"):
            self.base_series = series

    def add_overlay(self, overlay: Any, layer: str = "base", pane_name: str = "main") -> None:
        """
        Agregar overlay a un pane específico.
        """
        for pane in self.pane_manager.panes:
            if pane.name == pane_name:
                pane.add_overlay(overlay)
                return

        self.main_pane.add_overlay(overlay)

    def draw(self, renderer: Any) -> None:
        if self.time_scale is None or self.price_scale is None:
            return

        vr = self.time_scale.get_visible_range()
        if vr.end_idx < vr.start_idx:
            return

        # Dibujar todos los panes
        for pane in self.pane_manager.panes:
            if pane.config.show:
                pane.draw(
                    renderer,
                    self.time_scale,
                    self.price_scale,
                    vr.start_idx,
                    vr.end_idx,
                )

        # Futuro: dibujar separadores entre panes
        # self.pane_manager.draw_separators(...)

    def add_indicator(self, indicator: Any, pane_name: str = "main") -> None:
        """
        Agregar un indicador técnico.
        """
        for pane in self.pane_manager.panes:
            if pane.name == pane_name:
                pane.add_series(indicator)   # Los indicadores se comportan como series
                return

        self.main_pane.add_series(indicator)

    def update_indicators(self) -> None:
        """
        Actualiza los valores de todos los indicadores (útil en live).
        """
        if self.base_series is None or not hasattr(self.base_series, "data"):
            return

        base_data = self.base_series.data

        for pane in self.pane_manager.panes:
            for series in pane.series:
                # Recalcular solamente indicadores/series derivadas
                if hasattr(series, "calculate") and hasattr(series, "values"):
                    series.values = series.calculate(base_data)