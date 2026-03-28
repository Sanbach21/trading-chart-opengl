from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from data.fake_ohlc import OHLC


class BinanceRESTError(Exception):
    pass


class BinanceRESTFeed:
    """
    Cliente REST simple para descargar velas históricas de Binance Spot.

    Endpoint usado:
        GET /api/v3/klines

    Ejemplo:
        feed = BinanceRESTFeed()
        bars = feed.fetch_klines("btcusdt", "1m", limit=500)
    """

    BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = float(timeout)

    def fetch_klines(
        self,
        symbol: str,
        interval: str = "1m",
        *,
        limit: int = 5000,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
    ) -> List[OHLC]:
        """
        Descarga velas históricas OHLC de Binance.

        Parámetros:
            symbol: ej. "btcusdt"
            interval: ej. "1m", "5m", "15m", "1h"
            limit: máximo 1000 en Binance
            start_time_ms: opcional, timestamp en milisegundos
            end_time_ms: opcional, timestamp en milisegundos
        """
        symbol = symbol.strip().upper()
        interval = interval.strip()

        limit = max(1, min(int(limit), 5000))

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }

        if start_time_ms is not None:
            params["startTime"] = int(start_time_ms)

        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)

        url = f"{self.BASE_URL}?{urlencode(params)}"

        try:
            with urlopen(url, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except Exception as exc:
            raise BinanceRESTError(f"No se pudo descargar histórico de Binance: {exc}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BinanceRESTError("Respuesta JSON inválida desde Binance REST") from exc

        if not isinstance(payload, list):
            raise BinanceRESTError(f"Respuesta inesperada de Binance REST: {payload!r}")

        bars: List[OHLC] = []

        for row in payload:
            # Formato Binance kline:
            # [
            #   0 open time,
            #   1 open,
            #   2 high,
            #   3 low,
            #   4 close,
            #   5 volume,
            #   6 close time,
            #   ...
            # ]
            if not isinstance(row, list) or len(row) < 5:
                continue

            try:
                open_time_ms = int(row[0])
                o = float(row[1])
                h = float(row[2])
                l = float(row[3])
                c = float(row[4])
            except (ValueError, TypeError):
                continue

            ts = datetime.fromtimestamp(
                open_time_ms / 1000.0,
                tz=timezone.utc,
            ).replace(tzinfo=None)

            bars.append(
                OHLC(
                    ts=ts,
                    o=o,
                    h=h,
                    l=l,
                    c=c,
                )
            )

        return bars
    