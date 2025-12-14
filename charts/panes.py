"""Sistema de panes (placeholder).

Pane = región vertical con su propio layout y rango:
- Pane 1: precio
- Pane 2: volumen
- Pane 3: indicadores

Más adelante: separadores ajustables + estilos.
"""
from __future__ import annotations


class Pane:
    def __init__(self, name: str) -> None:
        self.name = name
