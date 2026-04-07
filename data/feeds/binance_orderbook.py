# data/feeds/binance_orderbook.py
"""
Feed WebSocket para Order Book (Depth) de Binance.
Actualiza en tiempo real los niveles de bids y asks.
"""

from __future__ import annotations
import json
import threading
import time
import queue
from dataclasses import dataclass
from typing import List, Tuple, Optional, Callable

import websocket

from data.feeds.binance_ws import FeedEvent, FeedStatus, FeedError


@dataclass
class OrderBookLevel:
    price: float
    quantity: float


@dataclass
class OrderBookSnapshot:
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    last_update_time: float


class BinanceOrderBookFeed:
    def __init__(
        self,
        symbol: str = "btcusdt",
        depth_levels: int = 20,
        auto_reconnect: bool = True,
        on_update: Optional[Callable[[OrderBookSnapshot], None]] = None,
    ) -> None:
        self.symbol = symbol.lower()
        self.depth_levels = depth_levels
        self.auto_reconnect = auto_reconnect

        self.on_update = on_update

        self._queue: queue.Queue[FeedEvent] = queue.Queue(maxsize=500)
        self._ws_app: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._current_book: Optional[OrderBookSnapshot] = None

    @property
    def url(self) -> str:
        return f"wss://stream.binance.com:9443/ws/{self.symbol}@depth{self.depth_levels}"

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._ws_app:
            self._ws_app.close()

    def poll_events(self, limit: int = 100) -> List[FeedEvent]:
        out: List[FeedEvent] = []
        for _ in range(limit):
            try:
                ev = self._queue.get_nowait()
                out.append(ev)
            except queue.Empty:
                break
        return out

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._emit_status("connecting", f"Conectando order book {self.symbol}")
                self._ws_app = websocket.WebSocketApp(
                    self.url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws_app.run_forever(ping_interval=20)
            except Exception:
                pass

            if not self.auto_reconnect or self._stop_event.is_set():
                break
            time.sleep(3.0)

    def _on_open(self, ws) -> None:
        self._emit_status("connected", f"Order book conectado: {self.symbol}")

    def _on_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)
            self._process_depth_update(data)
        except Exception as e:
            self._emit_error(f"Error procesando depth: {e}")

    def _process_depth_update(self, data: dict) -> None:
        bids = [OrderBookLevel(float(p), float(q)) for p, q in data.get("b", [])]
        asks = [OrderBookLevel(float(p), float(q)) for p, q in data.get("a", [])]

        snapshot = OrderBookSnapshot(
            bids=bids[:self.depth_levels],
            asks=asks[:self.depth_levels],
            last_update_time=time.time()
        )
        self._current_book = snapshot

        # Notificar actualización
        if self.on_update:
            self.on_update(snapshot)

        self._queue.put(FeedEvent(type="orderbook", payload=snapshot))

    def _on_error(self, ws, error) -> None:
        self._emit_error(str(error))

    def _on_close(self, ws, code, msg) -> None:
        self._emit_status("closed", f"Order book cerrado (code={code})")

    def _emit_status(self, state: str, message: str) -> None:
        self._queue.put(FeedEvent(type="status", payload=FeedStatus(state=state, message=message)))

    def _emit_error(self, message: str) -> None:
        self._queue.put(FeedEvent(type="error", payload=FeedError(message=message)))

    def get_current_book(self) -> Optional[OrderBookSnapshot]:
        return self._current_book
    