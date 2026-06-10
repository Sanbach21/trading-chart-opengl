from __future__ import annotations

from pathlib import Path

import glfw
from OpenGL.GL import GL_COLOR_BUFFER_BIT, glClear, glClearColor, glViewport

from app.input import InputState
from charts.chart import Chart
from charts.overlays.axis import PriceAxisOverlay, TimeAxisOverlay
from charts.overlays.chart_overlay import ChartOverlay
from charts.overlays.crosshair import CrosshairOverlay
from charts.overlays.grid import GridOverlay, GridStyle
from charts.overlays.tooltip import TooltipOverlay, TooltipStyle
from charts.scales.local_price_scale import LocalPriceScale
from charts.scales.time_scale import TimeScale
from charts.series.candles import CandleSeries, CandleStyle
from data.fake_ohlc import OHLC, make_fake_ohlc
from data.feeds.binance_rest import BinanceRESTFeed
from data.feeds.binance_ws import BinanceWSFeed
from font.text import TextRenderer
from render.renderer import Renderer2D


class GLFWWindow:
    """
    Ventana principal usando arquitectura B.
    """

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        title: str = "Libreria Grafica OpenGL - Trading Chart",
        live_mode: bool = False,
        live_symbol: str = "BTCUSDT",
        live_interval: str = "1m",
        history_limit: int = 1000,
    ) -> None:
        self.width = width
        self.height = height
        self.title = title
        self.window = None

        self.live_mode = bool(live_mode)
        self.live_symbol = live_symbol
        self.live_interval = live_interval
        self.history_limit = int(history_limit)

        self.renderer2d = Renderer2D()
        self.input = InputState()
        self.text_renderer: TextRenderer | None = None

        self._drag_mode: str | None = None
        self._price_manual_mode: bool = False

        self._price_axis_width_px: float = 110.0
        self._time_axis_height_px: float = 28.0
        self._last_price_axis_click_time: float = -999.0
        self._double_click_threshold: float = 0.30

        # Estilo velas
        style = CandleStyle(
            base_candle_width_px=8.0,
            base_gap_px=2.0,
            wick_width_px=1.0,
            border_color=(0.0, 0.0, 0.0, 0.95),
            draw_borders=True,
            clip_to_plot=True,
            min_width_px=1.60,
            min_gap_px=-0.0,
        )

        initial_bar_spacing = style.base_candle_width_px + style.base_gap_px

        self.time_scale = TimeScale(
            bar_spacing=initial_bar_spacing,
            right_offset=8.0,
            min_bar_spacing=0.15,
            max_bar_spacing=300.0,
            max_right_offset=500.0,
            right_padding_px=0.0,
        )

        self.price_scale = LocalPriceScale(
            y_down=True,
            top_padding_px=9.0,
            bottom_padding_px=9.0,
        )

        self.chart_overlay = ChartOverlay(
            time_scale=self.time_scale,
            price_scale=self.price_scale,
        )

        self.chart = Chart()
        self.chart.set_scales(self.time_scale, self.price_scale)

        # Datos
        self.live_feed: BinanceWSFeed | None = None
        if self.live_mode:
            print("[REST] Descargando histórico inicial...")
            rest = BinanceRESTFeed()
            try:
                initial_data: list[OHLC] = rest.fetch_klines(
                    symbol=self.live_symbol,
                    interval=self.live_interval,
                    limit=self.history_limit,
                )
                print(f"[REST] {len(initial_data)} velas cargadas")
            except Exception as e:
                print(f"[REST][ERROR] {e}")
                initial_data = []
        else:
            initial_data = make_fake_ohlc(
                400, start_price=100.0, volatility=1.2, seed=7
            )

        self.series = CandleSeries(initial_data, style=style)
        self.time_scale.set_timestamps([c.ts for c in initial_data])
        self.series.reset_initial_spacing()

        # Overlays
        self.price_axis_overlay: PriceAxisOverlay | None = None
        self.time_axis_overlay: TimeAxisOverlay | None = None
        self.crosshair_overlay: CrosshairOverlay | None = None
        self.grid_overlay: GridOverlay | None = None
        self.tooltip_overlay: TooltipOverlay | None = None

        self._pan_sensitivity = 2.0

    # ─────────────────────────────────────────────────────────────
    # Init
    # ─────────────────────────────────────────────────────────────
    def init(self) -> None:
        if not glfw.init():
            raise RuntimeError("No se pudo inicializar GLFW")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.SCALE_TO_MONITOR, glfw.TRUE)

        self.window = glfw.create_window(
            self.width, self.height, self.title, None, None
        )
        if not self.window:
            glfw.terminate()
            raise RuntimeError("No se pudo crear la ventana GLFW")

        glfw.make_context_current(self.window)
        glfw.swap_interval(1)

        self.renderer2d.init()

        fb_w, fb_h = glfw.get_framebuffer_size(self.window)

        project_root = Path(__file__).resolve().parent.parent
        font_path = str(project_root / "font" / "fonts_fft" / "Montserrat-Regular.ttf")

        self.text_renderer = TextRenderer(
            font_path=font_path, font_size=11, width=fb_w, height=fb_h
        )
        self.text_renderer.init_gl()

        # Overlays
        self.price_axis_overlay = PriceAxisOverlay(
            overlay=self.chart_overlay,
            price_scale=self.price_scale,
            time_scale=self.time_scale,
            data_provider=self.series.get_high_low,
            config={
                "show_minor": True,
                "minor_divisions": 4,
                "show_minor_labels": True,
                "minor_label_gap_px": 6,
                "minor_label_avoid_major_px": 4,
                "min_label_gap_px": 8,
                "minor_label_scale": 0.90,
            },
        )

        self.time_axis_overlay = TimeAxisOverlay(
            overlay=self.chart_overlay, time_scale=self.time_scale
        )

        self.crosshair_overlay = CrosshairOverlay(
            self.chart_overlay, self.input, self.series
        )

        self.grid_overlay = GridOverlay(
            overlay=self.chart_overlay,
            price_scale=self.price_scale,
            time_scale=self.time_scale,
            style=GridStyle(show_horizontal=True, show_vertical=True),
        )

        self.tooltip_overlay = TooltipOverlay(
            overlay=self.chart_overlay,
            input_state=self.input,
            series=self.series,
            text_renderer=self.text_renderer,
            style=TooltipStyle(show_timestamp=False),
        )

        # Inyecciones
        self.price_axis_overlay.text_renderer = self.text_renderer
        self.time_axis_overlay.text_renderer = self.text_renderer
        self.crosshair_overlay.text_renderer = self.text_renderer
        self.crosshair_overlay.price_scale = self.price_scale

        # Orden de dibujo
        self.chart.add_series(self.series, pane_name="main")
        self.chart.add_overlay(self.chart_overlay, layer="base", pane_name="main")
        self.chart.add_overlay(self.grid_overlay, layer="base", pane_name="main")
        self.chart.add_overlay(self.price_axis_overlay, layer="front", pane_name="main")
        self.chart.add_overlay(self.time_axis_overlay, layer="front", pane_name="main")
        self.chart.add_overlay(self.crosshair_overlay, layer="front", pane_name="main")
        self.chart.add_overlay(self.tooltip_overlay, layer="front", pane_name="main")

        # Callbacks
        glfw.set_cursor_pos_callback(self.window, self._on_cursor_pos)
        glfw.set_mouse_button_callback(self.window, self._on_mouse_button)
        glfw.set_framebuffer_size_callback(self.window, self._on_resize)

        self._update_layout_scales(fb_w, fb_h)

        if self.live_mode:
            self.live_feed = BinanceWSFeed(
                symbol=self.live_symbol,
                interval=self.live_interval,
                auto_reconnect=True,
            )
            self.live_feed.start()

    # ─────────────────────────────────────────────────────────────
    # Resize
    # ─────────────────────────────────────────────────────────────
    def _on_resize(self, window, width: int, height: int) -> None:
        fb_w, fb_h = glfw.get_framebuffer_size(window)
        self._update_layout_scales(fb_w, fb_h)

        if self.text_renderer is not None:
            self.text_renderer.update_projection(fb_w, fb_h)

    # ─────────────────────────────────────────────────────────────
    # Layout helpers
    # ─────────────────────────────────────────────────────────────
    def _chart_rect(self) -> tuple[float, float, float, float]:
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        chart_w = max(1.0, fb_w - self._price_axis_width_px)
        chart_h = max(1.0, fb_h - self._time_axis_height_px)
        return 0.0, 0.0, chart_w, chart_h

    def _price_axis_rect(self) -> tuple[float, float, float, float]:
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        x = max(0.0, fb_w - self._price_axis_width_px)
        h = max(1.0, fb_h - self._time_axis_height_px)
        return x, 0.0, self._price_axis_width_px, h

    def _time_axis_rect(self) -> tuple[float, float, float, float]:
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        w = max(1.0, fb_w - self._price_axis_width_px)
        y = max(0.0, fb_h - self._time_axis_height_px)
        return 0.0, y, w, self._time_axis_height_px

    def _point_in_rect(self, px: float, py: float, rect: tuple[float, float, float, float]) -> bool:
        x, y, w, h = rect
        return (x <= px <= x + w) and (y <= py <= y + h)

    def _mouse_over_chart(self) -> bool:
        return self._point_in_rect(self.input.mouse.x, self.input.mouse.y, self._chart_rect())

    def _mouse_over_price_axis(self) -> bool:
        return self._point_in_rect(self.input.mouse.x, self.input.mouse.y, self._price_axis_rect())

    def _mouse_over_time_axis(self) -> bool:
        return self._point_in_rect(self.input.mouse.x, self.input.mouse.y, self._time_axis_rect())

    def _update_layout_scales(self, fb_w: int, fb_h: int) -> None:
        self.chart_overlay.set_view(0, 0, fb_w, fb_h)

        chart_x, chart_y, chart_w, chart_h = self._chart_rect()
        self.time_scale.set_view(chart_x, chart_w)
        self.price_scale.set_viewport(chart_x, chart_y, chart_w, chart_h)

    def _reset_price_scale_to_default(self) -> None:
        self._price_manual_mode = False
        self.price_scale.end_scale()
        self.price_scale.clear_manual_range()

        vr = self.time_scale.get_visible_range()
        if vr.end_idx >= vr.start_idx and len(self.series.data) > 0:
            self.price_scale.autoscale_from_provider(
                vr.start_idx, vr.end_idx, self.series.get_high_low, pad_ratio=0.012
            )

    # ─────────────────────────────────────────────────────────────
    # Input callbacks
    # ─────────────────────────────────────────────────────────────
    def _on_cursor_pos(self, window, x: float, y: float) -> None:
        self.input.mouse.dx = x - self.input.mouse.x
        self.input.mouse.dy = y - self.input.mouse.y
        self.input.mouse.x = x
        self.input.mouse.y = y

    def _on_mouse_button(self, window, button: int, action: int, mods: int) -> None:
        is_down = action == glfw.PRESS

        if button == glfw.MOUSE_BUTTON_LEFT:
            self.input.mouse.left = is_down

            if is_down:
                if self._mouse_over_price_axis():
                    now = glfw.get_time()
                    if now - self._last_price_axis_click_time <= self._double_click_threshold:
                        self._reset_price_scale_to_default()
                        self._drag_mode = None
                        self._last_price_axis_click_time = -999.0
                        return

                    self._last_price_axis_click_time = now
                    self._drag_mode = "price-scale"
                    self._price_manual_mode = True
                    self.price_scale.start_scale(self.input.mouse.y)

                elif self._mouse_over_time_axis():
                    self._drag_mode = "time-zoom"   # ← Zoom arrastrando en Time Axis

                elif self._mouse_over_chart():
                    self._drag_mode = "time-pan"
                else:
                    self._drag_mode = None
            else:
                if self._drag_mode == "price-scale":
                    self.price_scale.end_scale()
                self._drag_mode = None

    # ─────────────────────────────────────────────────────────────
    # Update
    # ─────────────────────────────────────────────────────────────
    def update(self) -> None:
        self._update_live_feed()

        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        self._update_layout_scales(fb_w, fb_h)

        if self.input.mouse.left and self._drag_mode:
            if self._drag_mode == "time-pan" and abs(self.input.mouse.dx) > 2.0:
                adjusted_dx = -self.input.mouse.dx * self._pan_sensitivity
                self.time_scale.pan_by_pixels(adjusted_dx)

            elif self._drag_mode == "time-zoom" and abs(self.input.mouse.dx) > 1.0:
                self.time_scale.zoom_by_drag(
                    anchor_x=self.input.mouse.x,
                    dx_px=self.input.mouse.dx,
                )

            elif self._drag_mode == "price-scale" and abs(self.input.mouse.dy) > 1.0:
                self.price_scale.scale_to(self.input.mouse.y)

        # Autoscale compartido
        vr = self.time_scale.get_visible_range()
        if vr.end_idx >= vr.start_idx and len(self.series.data) > 0 and not self._price_manual_mode:
            self.price_scale.autoscale_from_provider(
                vr.start_idx, vr.end_idx, self.series.get_high_low, pad_ratio=0.005
            )

    def _update_live_feed(self) -> None:
        if self.live_feed is None:
            return

        events = self.live_feed.poll_events(limit=300)
        if not events:
            return

        changed = False
        new_bars = 0

        for ev in events:
            if ev.type == "bar":
                bar: OHLC = ev.payload

                if not self.series.data:
                    self.series.data.append(bar)
                    self.time_scale.append_timestamp(bar.ts)
                    new_bars += 1
                    changed = True
                    continue

                last = self.series.data[-1]

                if last.ts == bar.ts:
                    self.series.data[-1] = bar
                    self.time_scale.update_last_timestamp(bar.ts)
                    changed = True

                elif bar.ts > last.ts:
                    self.series.data.append(bar)
                    self.time_scale.append_timestamp(bar.ts)
                    new_bars += 1
                    changed = True

            elif ev.type == "status":
                print(f"[Feed][{ev.payload.state.upper()}] {ev.payload.message}")

            elif ev.type == "error":
                print(f"[Feed][ERROR] {ev.payload.message}")

        if changed:
            self.chart.update_indicators()

        if new_bars > 0:
            self.time_scale.right_offset = 8.0
            self.time_scale._clamp_right_offset()

        if changed and not self._price_manual_mode:
            vr = self.time_scale.get_visible_range()
            if vr.end_idx >= vr.start_idx and len(self.series.data) > 0:
                self.price_scale.autoscale_from_provider(
                    vr.start_idx, vr.end_idx, self.series.get_high_low, pad_ratio=0.005
                )

    # ─────────────────────────────────────────────────────────────
    # Render
    # ─────────────────────────────────────────────────────────────
    def render(self) -> None:
        fb_w, fb_h = glfw.get_framebuffer_size(self.window)
        glViewport(0, 0, fb_w, fb_h)

        if self.text_renderer is not None:
            self.text_renderer.update_projection(fb_w, fb_h)

        glClearColor(1.0, 1.0, 1.0, 0.90)
        glClear(GL_COLOR_BUFFER_BIT)

        self.renderer2d.begin_frame(fb_w, fb_h)
        self._update_layout_scales(fb_w, fb_h)
        self.chart.draw(self.renderer2d)

        if self.text_renderer is not None:
            ts = self.time_scale
            real_candle_width = self.series._compute_bar_width(ts.bar_spacing)

            debug_text = [
                f"bar_spacing       : {ts.bar_spacing:6.2f}px",
                f"real_candle_width : {real_candle_width:6.2f}px",
                f"price_low         : {self.price_scale._range.low:.2f}",
                f"price_high        : {self.price_scale._range.high:.2f}",
            ]

            y = 35.0
            for line in debug_text:
                self.text_renderer.render_text(
                    line, x=20.0, y=y, scale=1.05, color=(0.0, 0.0, 0.0, 0.98)
                )
                y += 24.0

        self.renderer2d.end_frame()

    # ─────────────────────────────────────────────────────────────
    # Main loop
    # ─────────────────────────────────────────────────────────────
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
        if self.live_feed is not None:
            self.live_feed.stop()

        if self.text_renderer is not None:
            self.text_renderer.shutdown()

        self.renderer2d.shutdown()

        if self.window is not None:
            glfw.destroy_window(self.window)

        glfw.terminate()