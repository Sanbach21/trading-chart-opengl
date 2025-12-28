"""
Ventana GLFW + loop principal.

Esta clase es el 'Core App' inicial:
- Inicializa GLFW
- Crea contexto OpenGL 3.3 core
- Captura input y lo vuelca a InputState
- Corre el loop: update -> render

NOTA: Aquí todavía no existe Chart Engine. Por ahora validamos:
- Renderer2D en píxeles
- TimeScale (zoom/pan)
- PriceScale (autoscale + price->y)
- ChartOverlay (layout + grid + bandas de ejes)
- CandleSeries (velas con data fake)
"""
from __future__ import annotations

import time
import glfw

from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    glClear, glClearColor, glViewport,
    glGetString, GL_VERSION, GL_RENDERER, GL_VENDOR,
)

from app.input import InputState
from render.renderer import Renderer2D, Color

from charts.scales.time_scale import TimeScale
from charts.scales.price_scale import PriceScale
from charts.overlays.chart_overlay import ChartOverlay

from data.fake_ohlc import make_fake_ohlc
from charts.series.candles import CandleSeries


class _OverlayRendererAdapter:
    """
    Adapter para que ChartOverlay pueda dibujar usando tu Renderer2D aunque
    ChartOverlay intente pasar kwargs como color= o width=.

    Intentamos soportar:
      - draw_rect_px(x, y, w, h, color=..., **kwargs)
      - draw_line_px(x1, y1, x2, y2, width=..., color=..., **kwargs)
    """
    def __init__(self, renderer: Renderer2D):
        self._r = renderer

    def _to_color(self, c):
        if c is None:
            return Color(1.0, 1.0, 1.0, 1.0)
        if isinstance(c, Color):
            return c
        # tuple/list RGBA
        try:
            return Color(float(c[0]), float(c[1]), float(c[2]), float(c[3]))
        except Exception:
            return Color(1.0, 1.0, 1.0, 1.0)

    def draw_rect_px(self, x, y, w, h, color=None, **kwargs):
        self._r.draw_rect_px(float(x), float(y), float(w), float(h), self._to_color(color))

    def draw_line_px(self, x1, y1, x2, y2, width=1, color=None, **kwargs):
        """
        Si tu Renderer2D soporta width, lo pasamos.
        Si no lo soporta, esta llamada podría fallar: en ese caso, quitá el width
        o actualizá Renderer2D.draw_line_px para aceptarlo.
        """
        try:
            self._r.draw_line_px(
                float(x1), float(y1), float(x2), float(y2),
                self._to_color(color),
                width=float(width),
            )
        except TypeError:
            # fallback si tu firma no acepta width=
            self._r.draw_line_px(
                float(x1), float(y1), float(x2), float(y2),
                self._to_color(color),
            )


class GLFWWindow:
    def __init__(self, title: str, width: int, height: int) -> None:
        # TimeScale (pixeles)
        self.time_scale = TimeScale(bar_spacing=10.0, right_offset=0.0)

        # Serie + dataset fake
        self.series = CandleSeries(make_fake_ohlc(500))
        self.total_bars = len(self.series.data)  # o len(self.series) si implementaste __len__

        # Para pan con arrastre
        self._dragging = False

        self.title = title
        self.width = width
        self.height = height
        self._window = None
        self.input = InputState()

        self.renderer = Renderer2D()

        # ----------------------------
        # Overlay / Axes / Grid
        # ----------------------------
        self.chart_config = {
            "price_axis": {"side": "right", "width_px": 0, "show": True},
            "time_axis": {"height_px": 0, "show": True},
            "grid": {"show": True, "vx": 80, "hy": 60, "line_width": 3},
            "padding": {"left": 0, "right": 60, "top": 0, "bottom": 30},
            "coords": {"y_down": True},  # <— origen arriba
        }

        # PriceScale real (asumiendo que ya lo implementaste)
        self.price_scale = PriceScale()

        # Overlay conectado a tus escalas
        self.overlay = ChartOverlay(self.time_scale, self.price_scale, self.chart_config)

        # Adapter para evitar problemas de firma (kwargs)
        self.overlay_renderer = _OverlayRendererAdapter(self.renderer)

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
        glfw.swap_interval(1)  # VSync ON

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
            _ = dt  # reservado por si luego lo usas

            self.input.begin_frame()
            glfw.poll_events()

            # ----------------------------
            # Definir área base del chart
            # ----------------------------
            chart_x = 0.0
            chart_y = 0.0
            chart_w = float(self.width)
            chart_h = float(self.height)

            self.overlay.set_view(chart_x, chart_y, chart_w, chart_h)
            plot_x, plot_y, plot_w, plot_h = self.overlay.get_plot_rect()

            # ----------------------------
            # Conectar scales usando el PLOT
            # ----------------------------
            self.time_scale.set_view(plot_x, plot_w)
            self.time_scale.set_total_bars(self.total_bars)

            # IMPORTANTÍSIMO: PriceScale necesita el viewport del plot
            self.price_scale.set_viewport(plot_x, plot_y, plot_w, plot_h)

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

            # Cerrar con Q
            if self.input.is_key_down(glfw.KEY_Q):
                glfw.set_window_should_close(self._window, True)

            # ----------------------------
            # Render
            # ----------------------------
            glClearColor(0.06, 0.07, 0.09, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

            self.renderer.begin_frame(self.width, self.height)

            # Fondo TOTAL del chart
            self.renderer.draw_rect_px(
                0.0, 0.0,
                float(self.width), float(self.height),
                Color(0.5, 0.5, 0.5, 0.5)
            )

            # Overlay (grid + bandas de ejes)
            self.overlay.draw(self.overlay_renderer)

            # ----------------------------
            # Autoscale + velas
            # ----------------------------
            vr = self.time_scale.get_visible_range()
            vs = max(0, int(vr.start))
            ve = min(self.total_bars - 1, int(vr.end))

            if ve >= vs:
                # Autoscale SOLO con visibles
                self.price_scale.autoscale_from_provider(vs, ve, self.series.get_high_low)

                # Dibujar velas
                self.series.draw(self.renderer, self.time_scale, self.price_scale, vs, ve)

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
