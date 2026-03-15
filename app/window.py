from __future__ import annotations

import glfw
from OpenGL.GL import glClearColor, glClear, GL_COLOR_BUFFER_BIT


class GLFWWindow:
    def __init__(self, width: int = 1280, height: int = 720, title: str = "Libreria Grafica OpenGL"):
        self.width = width
        self.height = height
        self.title = title
        self.window = None

    def init(self) -> None:
        if not glfw.init():
            raise RuntimeError("No se pudo inicializar GLFW")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

        self.window = glfw.create_window(self.width, self.height, self.title, None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("No se pudo crear la ventana GLFW")

        glfw.make_context_current(self.window)
        glfw.swap_interval(1)

    def render(self) -> None:
        glClearColor(0.08, 0.08, 0.10, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

    def run(self) -> None:
        self.init()
        try:
            while not glfw.window_should_close(self.window):
                glfw.poll_events()
                self.render()
                glfw.swap_buffers(self.window)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self.window is not None:
            glfw.destroy_window(self.window)
            self.window = None
        glfw.terminate()