"""Input centralizado.

Mantiene el estado de teclado/ratón para que el resto del core no dependa de GLFW directamente.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MouseState:
    x: float = 0.0
    y: float = 0.0
    dx: float = 0.0
    dy: float = 0.0
    left: bool = False
    middle: bool = False
    right: bool = False
    scroll_y: float = 0.0


class InputState:
    def __init__(self) -> None:
        self.keys_down: set[int] = set()
        self.mouse = MouseState()

    def begin_frame(self) -> None:
        # Reset deltas/scroll cada frame
        self.mouse.dx = 0.0
        self.mouse.dy = 0.0
        self.mouse.scroll_y = 0.0

    def set_key(self, key: int, is_down: bool) -> None:
        if is_down:
            self.keys_down.add(key)
        else:
            self.keys_down.discard(key)

    def is_key_down(self, key: int) -> bool:
        return key in self.keys_down
