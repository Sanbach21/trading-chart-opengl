"""Ventana GLFW + loop principal.

Esta clase es el 'Core App' inicial:
- Inicializa GLFW
- Crea contexto OpenGL 3.3 core
- Captura input y lo vuelca a InputState
- Corre el loop: update -> render

NOTA: Aquí todavía no existe Chart Engine. Por ahora solo validamos la base del renderer.
"""
from __future__ import annotations

import ctypes
import time
import glfw
from charts.scales.time_scale import TimeScale
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    glClear, glClearColor, glViewport,
    glGetString, GL_VERSION, GL_RENDERER, GL_VENDOR,
)

from app.input import InputState
from render.renderer import Renderer2D, Color


class GLFWWindow:
    def __init__(self, title: str, width: int, height: int) -> None:
        # TimeScale (pixeles)
        self.time_scale = TimeScale(bar_spacing=10.0, right_offset=0.0)

        # Datset fake (200 varras) Por ahora solo usamos el count
        self.total_bars = 200

        # Para pan con arratre
        self._dragging = False  

        self.title = title
        self.width = width
        self.height = height
        self._window = None
        self.input = InputState()
        self.renderer = Renderer2D()

    def _on_framebuffer_size(self, window, w: int, h: int) -> None:
        self.width = max(1, int(w))
        self.height = max(1, int(h))
        glViewport(0, 0, self.width, self.height)

    def _on_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        if action == glfw.PRESS:
            self.input.set_key(key, True)
        elif action == glfw.RELEASE:
            self.input.set_key(key, False)

        # ESC para cerrar
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.set_window_should_close(window, True)

    def _on_cursor_pos(self, window, x: float, y: float) -> None:
        m = self.input.mouse
        m.dx += float(x) - m.x
        m.dy += float(y) - m.y
        m.x = float(x)
        m.y = float(y)

    def _on_mouse_button(self, window, button: int, action: int, mods: int) -> None:
        down = (action == glfw.PRESS)
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.input.mouse.left = down
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            self.input.mouse.middle = down
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            self.input.mouse.right = down

    def _on_scroll(self, window, xoff: float, yoff: float) -> None:
        self.input.mouse.scroll_y += float(yoff)

    def _init_glfw(self) -> None:
        if not glfw.init():
            raise RuntimeError("No se pudo inicializar GLFW.")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

        # En macOS a veces se requiere forward compat
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

        self._window = glfw.create_window(self.width, self.height, self.title, None, None)
        if not self._window:
            glfw.terminate()
            raise RuntimeError("No se pudo crear la ventana GLFW.")

        glfw.make_context_current(self._window)
        glfw.swap_interval(1)  # VSync ON (lo podemos hacer configurable)

        glfw.set_framebuffer_size_callback(self._window, self._on_framebuffer_size)
        glfw.set_key_callback(self._window, self._on_key)
        glfw.set_cursor_pos_callback(self._window, self._on_cursor_pos)
        glfw.set_mouse_button_callback(self._window, self._on_mouse_button)
        glfw.set_scroll_callback(self._window, self._on_scroll)

        # Ajuste inicial de viewport
        fb_w, fb_h = glfw.get_framebuffer_size(self._window)
        self._on_framebuffer_size(self._window, fb_w, fb_h)

        # Info básica (útil para debug)
        try:
            version = glGetString(GL_VERSION)
            vendor = glGetString(GL_VENDOR)
            renderer = glGetString(GL_RENDERER)
            print("OpenGL:", version.decode() if version else version)
            print("Vendor:", vendor.decode() if vendor else vendor)
            print("Renderer:", renderer.decode() if renderer else renderer)
        except Exception:
            # Algunas plataformas pueden fallar si el contexto no está listo
            pass

    def run(self) -> None:
        self._init_glfw()
        assert self._window is not None

        self.renderer.init()

        last = time.perf_counter()
        while not glfw.window_should_close(self._window):
            now = time.perf_counter()
            dt = now - last
            last = now

            self.input.begin_frame()
            glfw.poll_events()

            # --- TimeScale: configurar viewport y data ---
            left_margin = 60
            right_margin = 60
            view_x = float(left_margin)
            view_w = float(self.width - left_margin - right_margin)

            self.time_scale.set_view(view_x, view_w)
            self.time_scale.set_total_bars(self.total_bars)

            # --- Zoom con rueda ---
            if self.input.mouse.scroll_y != 0.0:
                self.time_scale.zoom_at_x(self.input.mouse.x, self.input.mouse.scroll_y)

            # --- Pan con arrastre (mouse left) ---
            if self.input.mouse.left and not self._dragging:
                self._dragging = True

            if not self.input.mouse.left and self._dragging:
                self._dragging = False

            if self._dragging and self.input.mouse.dx != 0.0:
            # dx positivo (mueves mouse a la derecha) => ver historial (más viejo)
                self.time_scale.pan_by_pixels(self.input.mouse.dx)


            # Update (por ahora solo un ejemplo: cerrar con Q)
            if self.input.is_key_down(glfw.KEY_Q):
                glfw.set_window_should_close(self._window, True)

            # Render
            glClearColor(0.06, 0.07, 0.09, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

            self.renderer.begin_frame(self.width, self.height)

            # Fondo del área del chart
            chart_y = 80
            chart_h = self.height - 160
            self.renderer.draw_rect_px(view_x, chart_y, view_w, chart_h, Color(0.15, 0.18, 0.22, 1.0))

            # Dibujar “peine” de barras verticales usando TimeScale
            vr = self.time_scale.get_visible_range()

            for i in range(vr.start, vr.end + 1):
                x = self.time_scale.index_to_x(i)
                self.renderer.draw_line_px(
                    x, chart_y, x, chart_y + chart_h,
                    Color(0.25, 0.35, 0.55, 0.8)
                )


            # borde del chart
            self.renderer.draw_line_px(view_x, chart_y, view_x + view_w, chart_y, Color(0.6, 0.6, 0.6, 1.0))
            self.renderer.draw_line_px(view_x, chart_y + chart_h, view_x + view_w, chart_y + chart_h, Color(0.6, 0.6, 0.6, 1.0))
            self.renderer.draw_line_px(view_x, chart_y, view_x, chart_y + chart_h, Color(0.6, 0.6, 0.6, 1.0))
            self.renderer.draw_line_px(view_x + view_w, chart_y, view_x + view_w, chart_y + chart_h, Color(0.6, 0.6, 0.6, 1.0))

            self.renderer.end_frame()



            glfw.swap_buffers(self._window)

        self.shutdown()

    def shutdown(self) -> None:
        try:
            self.renderer.shutdown()
        finally:
            if self._window is not None:
                glfw.destroy_window(self._window)
                self._window = None
            glfw.terminate()
