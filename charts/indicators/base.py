from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Any


@dataclass
class IndicatorStyle:
    color: Tuple[float, float, float, float] = (0.0, 0.8, 1.0, 1.0)
    width: float = 1.5
    label: str = ""


class Indicator:
    """Clase base para todos los indicadores"""
    
    def __init__(self, style: IndicatorStyle | None = None):
        self.style = style or IndicatorStyle()
        self.name = "Indicator"

    def calculate(self, data: List[Any]) -> List[float | None]:
        """Debe retornar una lista del mismo largo que los datos"""
        raise NotImplementedError("Subclase debe implementar calculate()")

    def draw(self, renderer: Any, time_scale: Any, price_scale: Any, 
             visible_start: int, visible_end: int) -> None:
        raise NotImplementedError("Subclase debe implementar draw()")