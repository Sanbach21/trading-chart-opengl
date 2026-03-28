"""Binance WebSocket feed para velas OHLC.

Diseñado para integrarse con el loop de render sin bloquear:
- Corre en un thread propio
- Usa websocket-client
- Acumula eventos en una queue
- Permite reconexión automática
- Entrega barras nuevas/actualizadas mediante poll_events()

Dependencia:
    pip install websocket-client
"""
from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

import websocket

from data.fake_ohlc import OHLC


# ---------------------------------------------------------
# Eventos internos
# ---------------------------------------------------------
@dataclass
class FeedEvent:
    type: str                  # "bar", "status", "error"
    payload: object


@dataclass
class FeedStatus:
    state: str                 # "connecting", "connected", "closed", "reconnecting", etc.
    message: str = ""


@dataclass
class FeedError:
    message: str


# ---------------------------------------------------------
# Feed principal
# ---------------------------------------------------------
class BinanceWSFeed:
    """
    Feed WebSocket para Binance Spot klines.

    Ejemplo de stream:
        wss://stream.binance.com:9443/ws/btcusdt@kline_1m

    Uso típico:
        feed = BinanceWSFeed("btcusdt", "1m")
        feed.start()

        # en el loop principal:
        for event in feed.poll_events():
            ...

        # al cerrar:
        feed.stop()
    """

    BASE_URL = "wss://stream.binance.com:9443/ws"

    def __init__(
        self,
        symbol: str,
        interval: str = "1m",
        *,
        auto_reconnect: bool = True,
        reconnect_delay: float = 3.0,
        max_queue_size: int = 5000,
        on_bar: Optional[Callable[[OHLC], None]] = None,
        on_status: Optional[Callable[[FeedStatus], None]] = None,
        on_error: Optional[Callable[[FeedError], None]] = None,
    ) -> None:
        self.symbol = symbol.strip().lower()
        self.interval = interval.strip().lower()

        self.auto_reconnect = bool(auto_reconnect)
        self.reconnect_delay = max(0.5, float(reconnect_delay))

        self.on_bar = on_bar
        self.on_status = on_status
        self.on_error = on_error

        self._queue: queue.Queue[FeedEvent] = queue.Queue(maxsize=max_queue_size)

        self._ws_app: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None

        self._stop_event = threading.Event()
        self._started = False
        self._lock = threading.Lock()

        self._last_bar_open_time_ms: Optional[int] = None

    # ---------------------------------------------------------
    # API pública
    # ---------------------------------------------------------
    @property
    def stream_name(self) -> str:
        return f"{self.symbol}@kline_{self.interval}"

    @property
    def url(self) -> str:
        return f"{self.BASE_URL}/{self.stream_name}"

    def is_running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_forever,
            name=f"BinanceWSFeed-{self.symbol}-{self.interval}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        ws = self._ws_app
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=2.0)

        with self._lock:
            self._started = False

        self._emit_status("closed", "Feed detenido")

    def poll_events(self, limit: int = 100) -> List[FeedEvent]:
        """
        Devuelve hasta `limit` eventos sin bloquear.
        Ideal para llamarlo una vez por frame.
        """
        out: List[FeedEvent] = []
        n = max(1, int(limit))

        for _ in range(n):
            try:
                ev = self._queue.get_nowait()
            except queue.Empty:
                break
            out.append(ev)

        return out

    # ---------------------------------------------------------
    # Internals
    # ---------------------------------------------------------
    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            self._emit_status("connecting", f"Conectando a {self.url}")

            try:
                self._ws_app = websocket.WebSocketApp(
                    self.url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error_ws,
                    on_close=self._on_close,
                )

                # ping_interval ayuda a mantener viva la conexión
                self._ws_app.run_forever(
                    ping_interval=20,
                    ping_timeout=10,
                )

            except Exception as exc:
                self._emit_error(f"Excepción en WebSocket: {exc!r}")

            if self._stop_event.is_set():
                break

            if not self.auto_reconnect:
                break

            self._emit_status("reconnecting", f"Reconectando en {self.reconnect_delay:.1f}s")
            time.sleep(self.reconnect_delay)

    def _on_open(self, ws) -> None:
        self._emit_status("connected", f"Conectado a {self.stream_name}")

    def _on_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            self._emit_error("Mensaje JSON inválido recibido desde Binance")
            return

        # Binance kline event
        # https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-streams
        k = data.get("k")
        if not isinstance(k, dict):
            return

        try:
            bar = self._parse_kline(k)
        except Exception as exc:
            self._emit_error(f"No se pudo parsear la vela: {exc!r}")
            return

        self._last_bar_open_time_ms = int(k["t"])
        self._emit_bar(bar)

    def _on_error_ws(self, ws, error) -> None:
        self._emit_error(str(error))

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        msg = f"Socket cerrado (code={close_status_code}, msg={close_msg})"
        self._emit_status("closed", msg)

    # ---------------------------------------------------------
    # Parse helpers
    # ---------------------------------------------------------
    def _parse_kline(self, k: dict) -> OHLC:
        """
        Convierte el bloque 'k' de Binance en OHLC.
        """
        open_time_ms = int(k["t"])

        ts = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)

        o = float(k["o"])
        h = float(k["h"])
        l = float(k["l"])
        c = float(k["c"])

        return OHLC(
            ts=ts,
            o=o,
            h=h,
            l=l,
            c=c,
        )

    # ---------------------------------------------------------
    # Event emitters
    # ---------------------------------------------------------
    def _push_event(self, event: FeedEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Si la cola está llena, descartamos el evento más viejo
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass

            try:
                self._queue.put_nowait(event)
            except queue.Full:
                pass

    def _emit_bar(self, bar: OHLC) -> None:
        ev = FeedEvent(type="bar", payload=bar)
        self._push_event(ev)

        if self.on_bar is not None:
            try:
                self.on_bar(bar)
            except Exception:
                pass

    def _emit_status(self, state: str, message: str = "") -> None:
        status = FeedStatus(state=state, message=message)
        ev = FeedEvent(type="status", payload=status)
        self._push_event(ev)

        if self.on_status is not None:
            try:
                self.on_status(status)
            except Exception:
                pass

    def _emit_error(self, message: str) -> None:
        err = FeedError(message=message)
        ev = FeedEvent(type="error", payload=err)
        self._push_event(ev)

        if self.on_error is not None:
            try:
                self.on_error(err)
            except Exception:
                pass