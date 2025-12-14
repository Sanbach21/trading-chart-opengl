"""Punto de entrada.

Ejecuta:
    python -m app.main

Abre una ventana GLFW con OpenGL 3.3 core y dibuja un triángulo con shaders.
"""
from __future__ import annotations

from app.window import GLFWWindow


def main() -> None:
    win = GLFWWindow(title="OpenGL Trading Core - Demo", width=1280, height=720)
    win.run()


if __name__ == "__main__":
    main()
