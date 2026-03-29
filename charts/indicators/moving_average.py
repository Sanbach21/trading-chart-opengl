from __future__ import annotations
from typing import List, Any
import statistics

from charts.indicators.base import Indicator, IndicatorStyle


class SMA(Indicator):
    """Simple Moving Average"""
    
    def __init__(self, period: int = 20, style: IndicatorStyle | None = None):
        super().__init__(style)
        self.period = period
        self.name = f"SMA({period})"
        if not self.style.label:
            self.style.label = self.name

    def calculate(self, data: List[Any]) -> List[float | None]:
        closes = [d.c for d in data]
        result: List[float | None] = [None] * (self.period - 1)
        
        for i in range(self.period - 1, len(closes)):
            window = closes[i - self.period + 1:i + 1]
            result.append(statistics.mean(window))
        
        return result

    def draw(self, renderer, time_scale, price_scale, visible_start: int, visible_end: int):
        if not hasattr(self, 'values') or not self.values:
            return

        for i in range(max(visible_start, self.period), visible_end + 1):
            if i >= len(self.values) or self.values[i] is None:
                continue

            x1 = time_scale.index_to_x(i - 1)
            x2 = time_scale.index_to_x(i)
            y1 = price_scale.price_to_y(self.values[i - 1])
            y2 = price_scale.price_to_y(self.values[i])

            renderer.draw_line_px(x1, y1, x2, y2, color=self.style.color, width=self.style.width)