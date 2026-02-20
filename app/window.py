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
import json
from pathlib import Path
from typing import Dict

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
from render.texture import load_texture_rgba

from charts.scales.time_scale import TimeScale
from charts.scales.price_scale import PriceScale
from charts.overlays.chart_overlay import ChartOverlay
from charts.overlays.axis import PriceAxisOverlay, TimeAxisOverlay
from charts.overlays.crosshair import CrosshairOverlay, CrosshairStyle
from charts.overlays.tooltip import TooltipOverlay

from data.fake_ohlc import make_fake_ohlc
from charts.series.candles import CandleSeries

# Text / MSDF
from render.text.msdf_text import MsdfFontManager, MsdfFont, MsdfGlyph, MsdfFontMetrics


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

    # --- MSDF pass-through (para MsdfFont.draw_text) ---
    def begin_msdf_text(self, texture_id: int, edge: float, smoothing: float, color=None, **_):
        self._r.begin_msdf_text(
            texture_id=int(texture_id),
            edge=float(edge),
            smoothing=float(smoothing),
            color=self._to_color(color),
        )

    def draw_textured_quad_px(self, x, y, w, h, u0, v0, u1, v1, **_):
        self._r.draw_textured_quad_px(
            float(x), float(y), float(w), float(h),
            u0=float(u0), v0=float(v0), u1=float(u1), v1=float(v1)
        )

    def end_msdf_text(self, **_):
        self._r.end_msdf_text()


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
        # Chart config (layout + style) - Ninja-like base
        # ----------------------------
        self.chart_config = {
            "colors": {
                "bg": (0.12, 0.12, 0.12, 1.0),
                "axis_band": (0.12, 0.12, 0.12, 1.0),
                "axis_separator": (0.35, 0.35, 0.35, 0.85),
            },
            "price_axis": {
                "side": "right",
                "show": True,
                "width_px": 60,

                "font_size_px": 16,
                "font_color": (0.78, 0.78, 0.78, 1.0),
                "padding_px": 3,

                # MSDF tuning (opcionales)
                "edge": 0.5,
                "smoothing": 0.08,
                "letter_spacing_px": 1.0,

                "target_major_ticks": 12,
                "minor_divisions": 3,

                "grid_major_color": (0.25, 0.25, 0.25, 0.35),
                "grid_minor_color": (0.25, 0.25, 0.25, 0.15),
                "grid_major_width": 1.0,
                "grid_minor_width": 1.0,

                "tick_major_len": 7,
                "tick_minor_len": 4,
                "tick_width": 1.0,
                "tick_color": (0.60, 0.60, 0.60, 0.9),

                "decimals": 2,
            },
            "time_axis": {
                "height_px": 28,
                "show": True,

                "font_size_px": 14,
                "font_color": (0.78, 0.78, 0.78, 1.0),
                "padding_px": 6,

                # MSDF tuning (opcionales)
                "edge": 0.5,
                "smoothing": 0.08,
                "letter_spacing_px": 1.0,

                "min_label_spacing_px": 100.0,
                "format_compact": True,

                "tick_in_axis": True,
                "tick_length_px": 6,
                "tick_width": 1,
                "tick_color": (0.60, 0.60, 0.60, 0.9),

                "gridline_in_plot": True,
                "gridline_color": (0.25, 0.25, 0.25, 0.25),
                "target_ticks": 5,
            },
            "padding": {"left": 0, "right": 0, "top": 0, "bottom": 0},
            "coords": {"y_down": True},
            "draw": {"axis_bands": True},
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
        self.crosshair = CrosshairOverlay(
            overlay=self.overlay,
            input_state=self.input,
            series=self.series,
            style=CrosshairStyle(
                color=(0.10, 0.10, 0.10, 0.55),
                width=1.2
            )
        )

        # ----------------------------
        # Tooltip
        # ----------------------------
        self.tooltip = TooltipOverlay(
            overlay=self.overlay,
            time_scale=self.time_scale,
            input_state=self.input,
            series=self.series,
            max_distance_px=20.0
        )

        # ----------------------------
        # MSDF Font Manager
        # ----------------------------
        self.msdf_fonts = MsdfFontManager()

    # -------------------------------------------------
    # MSDF init (después de renderer.init())
    # -------------------------------------------------
    def _init_msdf_fonts(self) -> None:
        root = Path(__file__).resolve().parents[1]

        png_path = root / "render" / "text" / "fonts" / "segoeui" / "trading_atlas.png"
        json_path = root / "render" / "text" / "fonts" / "segoeui" / "trading_atlas.json"

        if not png_path.exists():
            raise FileNotFoundError(f"No existe: {png_path}")
        if not json_path.exists():
            raise FileNotFoundError(f"No existe: {json_path}")

        # PNG -> texture_id
        tex = load_texture_rgba(png_path)
        texture_id = int(tex.id)

        # JSON -> glyphs + metrics
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        metrics_obj = data.get("metrics", {})
        ascent = float(metrics_obj.get("ascent", 0.0))
        descent = float(metrics_obj.get("descent", 0.0))
        line_height = float(metrics_obj.get("lineHeight", (ascent - descent) if (ascent or descent) else 1.0))
        metrics = MsdfFontMetrics(line_height=line_height, ascent=ascent, descent=descent)

        base_size_px = float(data.get("size", 48))

        atlas_obj = data.get("atlas", {})
        atlas_w = float(atlas_obj.get("width", 1.0))
        atlas_h = float(atlas_obj.get("height", 1.0))
        if atlas_w <= 0 or atlas_h <= 0:
            atlas_w, atlas_h = 1.0, 1.0

        glyphs: Dict[int, MsdfGlyph] = {}

        for g in data.get("glyphs", []):
            cp = g.get("unicode")
            if cp is None:
                continue
            cp = int(cp)

            ab = g.get("atlasBounds") or {}
            pb = g.get("planeBounds") or {}

            left = float(ab.get("left", 0.0))
            bottom = float(ab.get("bottom", 0.0))
            right = float(ab.get("right", 0.0))
            top = float(ab.get("top", 0.0))

            u0 = left / atlas_w
            v0 = bottom / atlas_h
            u1 = right / atlas_w
            v1 = top / atlas_h

            w = max(0.0, right - left)
            h = max(0.0, top - bottom)

            pl = float(pb.get("left", 0.0))
            pt = float(pb.get("top", 0.0))

            xoff = pl
            yoff = -pt
            xadv = float(g.get("advance", w))

            glyphs[cp] = MsdfGlyph(
                u0=u0, v0=v0, u1=u1, v1=v1,
                w=w, h=h,
                xoff=xoff, yoff=yoff,
                xadv=xadv
            )

        font = MsdfFont(texture_id, glyphs, metrics, base_size_px=base_size_px)
        self.msdf_fonts.register("segoeui", font)

        print(f"[MSDF] cargado segoeui: {len(glyphs)} glyphs | tex={texture_id} | base={base_size_px}px")

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
        self._init_msdf_fonts()
        font = self.msdf_fonts.get("segoeui")

        self.price_axis_overlay.font = font
        self.time_axis_overlay.font = font
        self.tooltip.font = font
        self.crosshair.font = font

        last = time.perf_counter()
        while not glfw.window_should_close(self._window):
            now = time.perf_counter()
            dt = now - last
            last = now

            self.input.begin_frame()
            glfw.poll_events()

            self.overlay.set_view(0.0, 0.0, float(self.width), float(self.height))
            plot_x, plot_y, plot_w, plot_h = self.overlay.get_plot_rect()

            self.time_scale.set_view(plot_x, plot_w)
            self.price_scale.set_viewport(plot_x, plot_y, plot_w, plot_h)

            if self.input.mouse.scroll_y != 0.0:
                self.time_scale.zoom_at_x(self.input.mouse.x, self.input.mouse.scroll_y)

            if self.input.mouse.left and not self._dragging:
                self._dragging = True
            if not self.input.mouse.left:
                self._dragging = False
            if self._dragging and self.input.mouse.dx != 0.0:
                self.time_scale.pan_by_pixels(self.input.mouse.dx)

            if self.input.is_key_down(glfw.KEY_Q):
                glfw.set_window_should_close(self._window, True)

            bg = self.chart_config["colors"]["bg"]
            glClearColor(float(bg[0]), float(bg[1]), float(bg[2]), float(bg[3]))
            glClear(GL_COLOR_BUFFER_BIT)

            self.renderer.begin_frame(self.width, self.height)

            self.overlay.draw(self.overlay_renderer)

            self.price_axis_overlay.draw(self.overlay_renderer)
            self.time_axis_overlay.draw(self.overlay_renderer)

            vr = self.time_scale.get_visible_range()
            vs = max(0, vr.start_idx)
            ve = min(self.total_bars - 1, vr.end_idx)

            if ve >= vs:
                self.price_scale.autoscale_from_provider(vs, ve, lambda i: self.series.get_high_low(i))
                self.series.draw(self.renderer, self.time_scale, self.price_scale, vs, ve)

            self.tooltip.draw(self.renderer)
            self.crosshair.draw(self.renderer)

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