# data/fake_ohlc.py
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import List
from datetime import datetime, timedelta


@dataclass
class OHLC:
    ts: datetime  # Nuevo: timestamp UTC
    o: float
    h: float
    l: float
    c: float


def make_fake_ohlc(n: int = 400, start_price: float = 100.0, volatility: float = 1.2, seed: int = 7,
                   start_time: datetime = datetime(2026, 1, 1, 0, 0), interval: timedelta = timedelta(minutes=1)) -> List[OHLC]:
    rnd = random.Random(seed)
    out: List[OHLC] = []
    last = start_price
    current_time = start_time

    for _ in range(n):
        o = last
        delta = rnd.uniform(-volatility, volatility)
        c = o + delta
        wick_up = abs(rnd.uniform(0.0, volatility * 0.9))
        wick_dn = abs(rnd.uniform(0.0, volatility * 0.9))
        h = max(o, c) + wick_up
        l = min(o, c) - wick_dn

        if rnd.random() < 0.04:
            h += rnd.uniform(0.5, volatility * 3.0)
        if rnd.random() < 0.04:
            l -= rnd.uniform(0.5, volatility * 3.0)

        out.append(OHLC(ts=current_time, o=o, h=h, l=l, c=c))
        last = c
        current_time += interval  # Avanza el tiempo

    return out