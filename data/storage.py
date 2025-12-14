"""Persistencia (placeholder).

SQLite primero.
"""
from __future__ import annotations


class Storage:
    def __init__(self, path: str = "market.sqlite3") -> None:
        self.path = path
