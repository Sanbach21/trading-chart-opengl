"""WebSocket feed (placeholder).

Luego lo haremos con asyncio + websockets (o similar), manteniendo timestamps en UTC internamente.
"""
from __future__ import annotations


class BinanceWSFeed:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
