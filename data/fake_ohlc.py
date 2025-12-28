# charts/data/fake_ohlc.py
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import List


@dataclass
class OHLC:
    o: float
    h: float
    l: float
    c: float


def make_fake_ohlc(n: int = 400, start: float = 100.0, volatility: float = 1.2, seed: int = 7) -> List[OHLC]:
    """
    Genera una caminata aleatoria simple para testear el motor:
    - o/h/l/c coherentes
    - variación suave + picos ocasionales
    """
    rnd = random.Random(seed)
    out: List[OHLC] = []
    last = start

    for _ in range(n):
        o = last
        # cambio base
        delta = rnd.uniform(-volatility, volatility)
        c = o + delta

        # rango intrabar
        wick_up = abs(rnd.uniform(0.0, volatility * 0.9))
        wick_dn = abs(rnd.uniform(0.0, volatility * 0.9))

        h = max(o, c) + wick_up
        l = min(o, c) - wick_dn

        # a veces un spike
        if rnd.random() < 0.04:
            h += rnd.uniform(0.5, volatility * 3.0)
        if rnd.random() < 0.04:
            l -= rnd.uniform(0.5, volatility * 3.0)

        out.append(OHLC(o=o, h=h, l=l, c=c))
        last = c

    return out
