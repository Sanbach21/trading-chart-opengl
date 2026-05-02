from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

Rect = Tuple[float, float, float, float]


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class OverlayLayout:
    chart_rect: Rect
    plot_rect: Rect
    price_axis_rect: Rect
    time_axis_rect: Rect


class ChartOverlay:
    DEFAULT_CONFIG = {
        "price_axis": {"show": True, "side": "right", "width_px": 90},
        "time_axis": {"show": True, "height_px": 28},
        "colors": {"axis_band": (0.12, 0.12, 0.12, 0.00)},
    }

    def __init__(self, time_scale, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.time_scale = time_scale
        self.price_scale = price_scale
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        self._x = self._y = self._w = self._h = 0.0
        self._layout: Optional[OverlayLayout] = None

    def set_view(self, x: float, y: float, w: float, h: float) -> None:
        self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)
        self._layout = None

    def get_layout(self) -> OverlayLayout:
        if self._layout is None:
            self._layout = self._compute_layout()
        return self._layout

    def _compute_layout(self) -> OverlayLayout:
        pa_width = float(self.config["price_axis"]["width_px"]) if self.config["price_axis"]["show"] else 0.0
        ta_height = float(self.config["time_axis"]["height_px"]) if self.config["time_axis"]["show"] else 0.0

        # Plot area (área útil donde van velas + grid)
        plot_x = self._x
        plot_y = self._y
        plot_w = self._w - pa_width
        plot_h = self._h - ta_height

        # Price axis (derecha)
        price_rect = (self._x + plot_w, plot_y, pa_width, plot_h) if pa_width > 0 else (0, 0, 0, 0)

        # Time axis (solo debajo del plot, NO invade price axis)
        time_rect = (plot_x, self._y + plot_h, plot_w, ta_height) if ta_height > 0 else (0, 0, 0, 0)

        return OverlayLayout(
            chart_rect=(self._x, self._y, self._w, self._h),
            plot_rect=(plot_x, plot_y, plot_w, plot_h),
            price_axis_rect=price_rect,
            time_axis_rect=time_rect,
        )
    def draw(self, renderer) -> None:
        layout = self.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        pa_x, pa_y, pa_w, pa_h = layout.price_axis_rect
        ta_x, ta_y, ta_w, ta_h = layout.time_axis_rect

        # Fondo sutil de los ejes
        axis_band = self.config["colors"].get("axis_band", (0.085, 0.085, 0.085, 0.97))
        if pa_w > 0:
            renderer.draw_rect_px(pa_x, pa_y, pa_w, pa_h, axis_band)
        if ta_w > 0:
            renderer.draw_rect_px(ta_x, ta_y, ta_w, ta_h, axis_band)

        # === LÍNEAS DELGADAS DE SEPARACIÓN (esto es lo que realmente quieres) ===
        separator_color = (0.32, 0.32, 0.32, 1.0)
        separator_width = 1.0

        # Línea vertical entre el chart y el price axis
        if pa_w > 0:
            renderer.draw_line_px(
                plot_x + plot_w, plot_y,
                plot_x + plot_w, plot_y + plot_h,
                color=separator_color, width=separator_width
            )

        # Línea horizontal entre el chart y el time axis
        if ta_h > 0:
            renderer.draw_line_px(
                plot_x, plot_y + plot_h,
                plot_x + plot_w, plot_y + plot_h,
                color=separator_color, width=separator_width
            )

        # Rellenamos la esquina inferior derecha (evita el hueco negro)
        if pa_w > 0 and ta_h > 0:
            renderer.draw_rect_px(pa_x, ta_y, pa_w, ta_h, axis_band)