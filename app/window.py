from __future__ import annotations

import glfw
from OpenGL.GL import GL_COLOR_BUFFER_BIT, glClear, glClearColor, glViewport

from app.input import InputState
from charts.overlays.axis import PriceAxisOverlay, TimeAxisOverlay
from charts.overlays.chart_overlay import ChartOverlay
from charts.overlays.crosshair import CrosshairOverlay
from charts.overlays.tooltip import TooltipOverlay
from charts.scales.price_scale import PriceScale
from charts.scales.time_scale import TimeScale
from charts.series.candles import CandleSeries
from data.fake_ohlc import make_fake_ohlc
from font.text import TextRenderer
from render.renderer import Renderer2D


class GLFWWindow:
    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "Libreria Grafica OpenGL",
    ):
        self.width = width
        self.height = height
        self.title = title
        self.window = None

        # Core
        self.renderer2d = Renderer2D()
        self.input = InputState()
        self.text_renderer: TextRenderer | None = None

        # Scales
        self.price_scale = PriceScale(
            y_down=True,
            top_padding_px=12,
            bottom_padding_px=12,
        )
        self.time_scale = TimeScale(bar_spacing=12)

        # Overlay base
        self.chart_overlay = ChartOverlay(
            time_scale=self.time_scale,
            price_scale=self.price_scale,
        )

        # Demo data
        self.ohlc = make_fake_ohlc(400, start_price=100.0, volatility=1.2, seed=7)
        self.series = CandleSeries(self.ohlc)

        # TimeScale necesita timestamps
        self.time_scale.set_timestamps([c.ts for c in self.ohlc])

        # Overlays
        self.price_axis_overlay = PriceAxisOverlay(self.chart_overlay, self.price_scale)
        self.time_axis_overlay = TimeAxisOverlay(self.chart_overlay, self.time_scale)
        self.crosshair_overlay = CrosshairOverlay(self.chart_overlay, self.input, self.series)
        self.tooltip_overlay = TooltipOverlay()  # hoy no dibuja nada

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

        self.renderer2d.init()

        fb_w, fb_h = glfw.get_framebuffer_size(self.window)

        self.text_renderer = TextRenderer(
            font_path=r"C:\Users\ozzyj\OneDrive\Escritorio\Programacion\libreria_grafica_openGL\font\fonts_fft\Oswald-VariableFont_wght.ttf",
            font_size=15,
            width=fb_w,
            height=fb_h,
        )
        self.text_renderer.init_gl()

        # Se deja listo para que axis.py pueda usarlo si lo integras allí
        self.price_axis_overlay.text_renderer = self.text_renderer
        self.time_axis_overlay.text_renderer = self.text_renderer

        # Callbacks de mouse
        glfw.set_cursor_pos_callback(self.window, self._on_cursor_pos)
        glfw.set_mouse_button_callback(self.window, self._on_mouse_button)
        glfw.set_scroll_callback(self.window, self._on_scroll)

    # -------------------------
    # Input callbacks
    # -------------------------
    def _on_cursor_pos(self, window, x: float, y: float) -> None:
        self.input.mouse.dx = x - self.input.mouse.x
        self.input.mouse.dy = y - self.input.mouse.y
        self.input.mouse.x = x
        self.input.mouse.y = y

    def _on_mouse_button(self, window, button: int, action: int, mods: int) -> None:
        is_down = action == glfw.PRESS
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.input.mouse.left = is_down
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            self.input.mouse.middle = is_down
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            self.input.mouse.right = is_down

    def _on_scroll(self, window, xoffset: float, yoffset: float) -> None:
        self.input.mouse.scroll_y += yoffset

    # -------------------------
    # Update
    # -------------------------
    def update(self) -> None:
        if self.input.mouse.scroll_y != 0.0:
            self.time_scale.zoom_at_x(self.input.mouse.x, self.input.mouse.scroll_y)

        if self.input.mouse.left and abs(self.input.mouse.dx) > 0.0:
            self.time_scale.pan_by_pixels(-self.input.mouse.dx)

        vr = self.time_scale.get_visible_range()
        if vr.end_idx >= vr.start_idx:
            self.price_scale.autoscale_from_provider(
                vr.start_idx,
                vr.end_idx,
                self.series.get_high_low,
                pad_ratio=0.03,
            )

    # -------------------------
    # Render
    # -------------------------
    def render(self) -> None:
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        glViewport(0, 0, fb_w, fb_h)

        if self.text_renderer is not None:
            self.text_renderer.update_projection(fb_w, fb_h)

        glClearColor(0.08, 0.08, 0.08, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        self.renderer2d.begin_frame(fb_w, fb_h)

        # actualizar layout del chart con tamaño nuevo
        self.chart_overlay.set_view(0, 0, fb_w, fb_h)

        # 1) base/fondo
        self.chart_overlay.draw(self.renderer2d)

        # 2) grid detrás de candles
        self.price_axis_overlay.draw(self.renderer2d)
        self.time_axis_overlay.draw(self.renderer2d)

        # 3) candles encima
        vr = self.time_scale.get_visible_range()
        if vr.end_idx >= vr.start_idx:
            self.series.draw(
                self.renderer2d,
                self.time_scale,
                self.price_scale,
                vr.start_idx,
                vr.end_idx,
            )

        # 4) overlays arriba
        self.crosshair_overlay.draw(self.renderer2d)
        self.tooltip_overlay.draw(self.renderer2d)

        self.renderer2d.end_frame()

    def run(self) -> None:
        self.init()
        try:
            while not glfw.window_should_close(self.window):
                self.input.begin_frame()
                glfw.poll_events()
                self.update()
                self.render()
                glfw.swap_buffers(self.window)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self.text_renderer is not None:
            self.text_renderer.shutdown()
            self.text_renderer = None

        self.renderer2d.shutdown()

        if self.window is not None:
            glfw.destroy_window(self.window)
            self.window = None

        glfw.terminate()