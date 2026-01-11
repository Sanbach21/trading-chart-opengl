"""
Ventana GLFW + loop principal.

Esta clase es el 'Core App' inicial:
- Inicializa GLFW
- Crea contexto OpenGL 3.3 core
- Captura input y lo vuelca a InputState
- Corre el loop: update -> render
"""
from __future__ import annotations

import time
import glfw

from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    glClear,
    glClearColor,
    glViewport,
    glGetString,
    GL_VERSION,
    GL_RENDERER,
    GL_VENDOR,
)

from app.input import InputState
from render.renderer import Renderer2D, Color

from charts.scales.time_scale import TimeScale
from charts.scales.price_scale import PriceScale
from charts.overlays.chart_overlay import ChartOverlay
from charts.overlays.axis import PriceAxisOverlay, TimeAxisOverlay
from charts.overlays.crosshair import CrosshairOverlay, CrosshairStyle
from charts.overlays.tooltip import TooltipOverlay

from data.fake_ohlc import make_fake_ohlc
from charts.series.candles import CandleSeries


# -------------------------------------------------
# Adapter: ChartOverlay / AxisOverlay -> Renderer2D
# -------------------------------------------------
class _OverlayRendererAdapter:
    def __init__(self, renderer: Renderer2D):
        self._r = renderer

    def _to_color(self, c):
        if c is None:
            return Color(1.0, 1.0, 1.0, 1.0)
        if isinstance(c, Color):
            return c
        try:
            return Color(float(c[0]), float(c[1]), float(c[2]), float(c[3]))
        except Exception:
            return Color(1.0, 1.0, 1.0, 1.0)

    def draw_rect_px(self, x, y, w, h, color=None, **_):
        self._r.draw_rect_px(float(x), float(y), float(w), float(h), self._to_color(color))

    def draw_line_px(self, x1, y1, x2, y2, width=1, color=None, **_):
        try:
            self._r.draw_line_px(
                float(x1), float(y1), float(x2), float(y2),
                self._to_color(color),
                width=float(width),
            )
        except TypeError:
            self._r.draw_line_px(
                float(x1), float(y1), float(x2), float(y2),
                self._to_color(color),
            )


class GLFWWindow:
    def __init__(self, title: str = "OpenGL Trading Core - Demo", width: int = 1280, height: int = 720) -> None:
        # ----------------------------
        # Scales
        # ----------------------------
        self.time_scale = TimeScale(bar_spacing=10.0, right_offset=0.0)
        self.price_scale = PriceScale()

        # ----------------------------
        # Serie + data fake (con timestamps)
        # ----------------------------
        self.series = CandleSeries(make_fake_ohlc(500))
        self.total_bars = len(self.series.data)
        self.time_scale.set_timestamps([bar.ts for bar in self.series.data])

        # ----------------------------
        # State
        # ----------------------------
        self._dragging = False
        self.title = title
        self.width = width
        self.height = height
        self._window = None
        self.input = InputState()

        # ----------------------------
        # Renderer
        # ----------------------------
        self.renderer = Renderer2D()

        # ----------------------------
        # Chart config (layout + style)
        # ----------------------------
        self.chart_config = {
            "price_axis": {
                "side": "right",
                "width_px": 100,
                "show": True,
                "font_size_px": 20,
                "font_thickness_px": 2,
                "font_color": (1, 1, 1, 1),
                "padding_px": 10,
                "gridline_in_plot": True,
                "gridline_color": (0.2, 0.2, 0.2, 0.25),
                "gridline_width": 1,
                "tick_in_axis": True,
                "tick_length_px": 10,
                "tick_width": 2,
                "tick_color": (0.7, 0.7, 0.7, 0.9),
                "decimals": 2,
                "target_ticks": 6,
            },
            "time_axis": {
                "height_px": 34,
                "show": True,
                "font_size_px": 14,
                "font_thickness_px": 2,
                "font_color": (1, 1, 1, 1),
                "padding_px": 6,
                "tick_in_axis": True,
                "tick_length_px": 10,
                "tick_width": 1,
                "tick_color": (0.7, 0.7, 0.7, 0.9),
                "gridline_in_plot": False,
                "target_ticks": 8,
            },
            "grid": {"show": True, "vx": 80, "hy": 60, "line_width": 1},
            "padding": {"left": 0, "right": 60, "top": 0, "bottom": 30},
            "coords": {"y_down": True},
        }

        # ----------------------------
        # Overlay layout (¡PRIMERO!)
        # ----------------------------
        self.overlay = ChartOverlay(self.time_scale, self.price_scale, self.chart_config)
        self.overlay_renderer = _OverlayRendererAdapter(self.renderer)

        # ----------------------------
        # Axis overlays
        # ----------------------------
        self.price_axis_overlay = PriceAxisOverlay(
            self.overlay,
            self.price_scale,
            config=self.chart_config["price_axis"],
        )

        self.time_axis_overlay = TimeAxisOverlay(
            self.overlay,
            self.time_scale,
            config=self.chart_config["time_axis"],
        )

        # ----------------------------
        # Crosshair
        # ----------------------------
                # Crosshair
        self.crosshair = CrosshairOverlay(
            overlay=self.overlay,
            input_state=self.input,
            series=self.series,  # ← AGREGADO AQUÍ
            style=CrosshairStyle(
                color=(0.9, 0.9, 0.95, 0.55),
                width=1.2
            )
        )

        # ----------------------------
        # Tooltip (AHORA SÍ, después de crear overlay)
        # ----------------------------
        self.tooltip = TooltipOverlay(
            overlay=self.overlay,
            time_scale=self.time_scale,
            input_state=self.input,
            series=self.series,
            max_distance_px=20.0
        )

    # -------------------------------------------------
    # GLFW callbacks
    # -------------------------------------------------
    def _on_framebuffer_size(self, window, w: int, h: int) -> None:
        self.width = max(1, int(w))
        self.height = max(1, int(h))
        glViewport(0, 0, self.width, self.height)

    def _on_key(self, window, key: int, scancode: int, action: int, mods: int) -> None:
        if action == glfw.PRESS:
            self.input.set_key(key, True)
        elif action == glfw.RELEASE:
            self.input.set_key(key, False)

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

    # -------------------------------------------------
    # Init GLFW
    # -------------------------------------------------
    def _init_glfw(self) -> None:
        if not glfw.init():
            raise RuntimeError("No se pudo inicializar GLFW.")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)

        self._window = glfw.create_window(self.width, self.height, self.title, None, None)
        if not self._window:
            glfw.terminate()
            raise RuntimeError("No se pudo crear la ventana GLFW.")

        glfw.make_context_current(self._window)
        glfw.swap_interval(1)

        glfw.set_framebuffer_size_callback(self._window, self._on_framebuffer_size)
        glfw.set_key_callback(self._window, self._on_key)
        glfw.set_cursor_pos_callback(self._window, self._on_cursor_pos)
        glfw.set_mouse_button_callback(self._window, self._on_mouse_button)
        glfw.set_scroll_callback(self._window, self._on_scroll)

        fb_w, fb_h = glfw.get_framebuffer_size(self._window)
        self._on_framebuffer_size(self._window, fb_w, fb_h)

        try:
            version = glGetString(GL_VERSION)
            vendor = glGetString(GL_VENDOR)
            renderer = glGetString(GL_RENDERER)
            print("OpenGL:", version.decode() if version else "Unknown")
            print("Vendor:", vendor.decode() if vendor else "Unknown")
            print("Renderer:", renderer.decode() if renderer else "Unknown")
        except Exception:
            print("No se pudo obtener info de OpenGL")

    # -------------------------------------------------
    # Main loop
    # -------------------------------------------------
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

            # Actualizar layout del chart
            self.overlay.set_view(0.0, 0.0, float(self.width), float(self.height))
            plot_x, plot_y, plot_w, plot_h = self.overlay.get_plot_rect()

            # Actualizar escalas
            self.time_scale.set_view(plot_x, plot_w)
            self.price_scale.set_viewport(plot_x, plot_y, plot_w, plot_h)

            # Zoom con rueda
            if self.input.mouse.scroll_y != 0.0:
                self.time_scale.zoom_at_x(self.input.mouse.x, self.input.mouse.scroll_y)

            # Pan con drag
            if self.input.mouse.left and not self._dragging:
                self._dragging = True
            if not self.input.mouse.left:
                self._dragging = False
            if self._dragging and self.input.mouse.dx != 0.0:
                self.time_scale.pan_by_pixels(self.input.mouse.dx)

            # Cerrar con Q
            if self.input.is_key_down(glfw.KEY_Q):
                glfw.set_window_should_close(self._window, True)

            # ---------------- Render ----------------
            glClearColor(0.0, 0.0, 0.0, 1.0)  # Fondo negro puro
            glClear(GL_COLOR_BUFFER_BIT)

            self.renderer.begin_frame(self.width, self.height)

            # Fondo general (opcional, pero si querés un overlay sutil)
            # self.renderer.draw_rect_px(0, 0, float(self.width), float(self.height), Color(0.01, 0.01, 0.01, 0.5))

            # Overlay (grid + bandas de ejes)
            self.overlay.draw(self.overlay_renderer)

            # Velas + autoscale
            vr = self.time_scale.get_visible_range()
            vs = max(0, vr.start_idx)
            ve = min(self.total_bars - 1, vr.end_idx)

            if ve >= vs:
                self.price_scale.autoscale_from_provider(
                    vs, ve,
                    lambda i: self.series.get_high_low(i)
                )
                self.series.draw(self.renderer, self.time_scale, self.price_scale, vs, ve)

            # Tooltip (después de velas, antes del crosshair)
            self.tooltip.draw(self.renderer)

            # Crosshair encima de todo
            self.crosshair.draw(self.renderer)

            # Ejes (ticks + labels con fechas)
            self.price_axis_overlay.draw(self.overlay_renderer)
            self.time_axis_overlay.draw(self.overlay_renderer)

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


def main() -> None:
    win = GLFWWindow(title="OpenGL Trading Core - Demo", width=1280, height=720)
    win.run()


if __name__ == "__main__":
    main()