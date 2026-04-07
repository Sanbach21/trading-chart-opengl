# trading/backtest.py
"""
Backtesting Engine - Motor simple pero potente
Puede ejecutar estrategias sobre datos históricos usando las mismas series e indicadores.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Callable
from datetime import datetime

from charts.series.candles import CandleSeries
from charts.indicators.base import Indicator


@dataclass
class Trade:
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    side: str          # "long" o "short"
    profit: float


class BacktestEngine:
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]

    def run(
        self,
        series: CandleSeries,
        strategy: Callable,
        indicators: List[Indicator] | None = None,
    ) -> Dict[str, Any]:
        """
        Ejecuta el backtest con una estrategia.
        strategy debe ser una función que reciba (index, data) y retorne "buy", "sell" o None.
        """
        if indicators:
            for ind in indicators:
                ind.values = ind.calculate(series.data)

        data = series.data
        position = None
        entry_price = 0.0

        for i in range(1, len(data)):
            signal = strategy(i, data)

            # Salida de posición
            if position and signal == "sell" and position == "long":
                profit = (data[i].c - entry_price) * 1000  # 1000 contratos ejemplo
                self.current_capital += profit
                self.trades.append(Trade(
                    entry_time=data[i-1].ts, entry_price=entry_price,
                    exit_time=data[i].ts, exit_price=data[i].c,
                    side="long", profit=profit
                ))
                position = None

            # Entrada larga
            elif not position and signal == "buy":
                position = "long"
                entry_price = data[i].c

            # Actualizar equity
            self.equity_curve.append(self.current_capital)

        # Resultados
        total_trades = len(self.trades)
        win_rate = len([t for t in self.trades if t.profit > 0]) / total_trades * 100 if total_trades > 0 else 0
        total_profit = self.current_capital - self.initial_capital

        return {
            "final_capital": self.current_capital,
            "total_profit": total_profit,
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "equity_curve": self.equity_curve,
            "trades": self.trades
        }


# ==================== EJEMPLO DE ESTRATEGIA ====================
def sma_crossover_strategy(index: int, data: List) -> str | None:
    """Estrategia simple: SMA20 cruza sobre SMA50 → buy"""
    if index < 50:
        return None

    # Aquí puedes acceder a los valores de los indicadores si los pasas
    # Por ahora usamos solo precio (puedes mejorarlo después)
    return None  # placeholder - lo mejoraremos en el siguiente paso