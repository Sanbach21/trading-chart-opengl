"""Tiempo y zona horaria (placeholder).

Regla:
- Internamente UTC.
- Conversión solo al mostrar (timezone display).
"""
from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
