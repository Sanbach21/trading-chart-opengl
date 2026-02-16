# charts/overlays/chart_overlay.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


Rect = Tuple[float, float, float, float]  # (x, y, w, h)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def merge_defaults(user_cfg: Optional[Dict[str, Any]], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Merge shallow + one-level nested dicts, user overrides defaults."""
    out = dict(defaults)
    for k, v in (user_cfg or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            tmp = dict(out[k])
            tmp.update(v)
            out[k] = tmp
        else:
            out[k] = v
    return out


@dataclass
class OverlayLayout:
    chart_rect: Rect
    plot_rect: Rect
    price_axis_rect: Rect
    time_axis_rect: Rect


class ChartOverlay:
    """
    Layout + bandas opcionales + separadores.
    - NO dibuja grid (eso lo hace axis overlay).
    - NO dibuja labels/ticks (axis overlay).
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        "padding": {"left": 0, "right": 0, "top": 0, "bottom": 0},
        "price_axis": {
            "show": True,
            "side": "right",
            "width_px": 70,            # Ninja-like: angosto
            "separator_width": 1.0,
        },
        "time_axis": {
            "show": True,
            "height_px": 28,           # Ninja-like: más compacto
            "separator_width": 1.0,
        },
        "colors": {
            # Ninja-ish base palette
            "bg": (0.12, 0.12, 0.12, 1.0),
            "axis_band": (0.08, 0.08, 0.08, 1.0),      # banda eje
            "axis_separator": (0.35, 0.35, 0.35, 0.85),
        },
        "draw": {
            "axis_bands": True,        # dibuja rectángulos de fondo de ejes
        },
        "coords": {"y_down": True},    # UI normal: y crece hacia abajo
    }

    def __init__(self, time_scale, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.time_scale = time_scale
        self.price_scale = price_scale
        self.config = merge_defaults(config, self.DEFAULT_CONFIG)

        self._x = self._y = self._w = self._h = 0.0
        self._layout: Optional[OverlayLayout] = None
        self._y_down = bool(self.config["coords"].get("y_down", True))

    # ----------------------------
    # Public API
    # ----------------------------
    def set_view(self, x: float, y: float, w: float, h: float) -> None:
        self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)
        self._layout = None

    def get_layout(self) -> OverlayLayout:
        if self._layout is None:
            self._layout = self._compute_layout()

            # Conectar escalas al área de plot
            px, py, pw, ph = self._layout.plot_rect
            self.time_scale.set_view(px, pw)
            if hasattr(self.price_scale, "set_viewport"):
                self.price_scale.set_viewport(px, py, pw, ph)

        return self._layout

    def get_plot_rect(self) -> Rect:
        return self.get_layout().plot_rect

    def draw(self, renderer) -> None:
        """
        Dibuja:
        - bandas de fondo de ejes (opcional)
        - separadores (líneas grises)
        """
        layout = self.get_layout()
        colors = self.config["colors"]
        draw_cfg = self.config.get("draw", {})

        # bandas (fondo de axis)
        if draw_cfg.get("axis_bands", True):
            band = colors.get("axis_band", None)
            if band is not None:
                # price axis band
                if self.config["price_axis"]["show"]:
                    ax, ay, aw, ah = layout.price_axis_rect
                    if aw > 0 and ah > 0:
                        renderer.draw_rect_px(ax, ay, aw, ah, color=band)

                # time axis band
                if self.config["time_axis"]["show"]:
                    tx, ty, tw, th = layout.time_axis_rect
                    if tw > 0 and th > 0:
                        renderer.draw_rect_px(tx, ty, tw, th, color=band)

        # separadores
        if self.config["price_axis"]["show"]:
            self._draw_price_axis_separator(renderer, layout.price_axis_rect, layout.plot_rect)

        if self.config["time_axis"]["show"]:
            self._draw_time_axis_separator(renderer, layout.time_axis_rect, layout.plot_rect)

    # ----------------------------
    # Layout calculation
    # ----------------------------
    def _compute_layout(self) -> OverlayLayout:
        pad = self.config["padding"]
        left, right = float(pad["left"]), float(pad["right"])
        top, bottom = float(pad["top"]), float(pad["bottom"])

        chart_rect: Rect = (self._x, self._y, self._w, self._h)

        inner_x = self._x + left
        inner_w = max(0.0, self._w - left - right)

        if self._y_down:
            inner_y = self._y + top
            inner_h = max(0.0, self._h - top - bottom)
        else:
            inner_y = self._y + bottom
            inner_h = max(0.0, self._h - top - bottom)

        pa = self.config["price_axis"]
        ta = self.config["time_axis"]
        price_w = float(pa["width_px"]) if pa["show"] else 0.0
        time_h = float(ta["height_px"]) if ta["show"] else 0.0

        # time axis abajo
        if self._y_down:
            plot_y = inner_y
            plot_h = max(0.0, inner_h - time_h)
            time_y = inner_y + plot_h
        else:
            plot_h = max(0.0, inner_h - time_h)
            plot_y = inner_y + time_h
            time_y = inner_y

        time_rect: Rect = (inner_x, time_y, inner_w, time_h) if ta["show"] else (0.0, 0.0, 0.0, 0.0)

        # price axis izquierda/derecha
        side = (pa["side"] or "right").lower()
        if side == "left":
            price_rect: Rect = (inner_x, plot_y, price_w, plot_h)
            plot_rect: Rect = (inner_x + price_w, plot_y, max(0.0, inner_w - price_w), plot_h)
        else:
            plot_rect = (inner_x, plot_y, max(0.0, inner_w - price_w), plot_h)
            price_rect = (inner_x + plot_rect[2], plot_y, price_w, plot_h) if pa["show"] else (0.0, 0.0, 0.0, 0.0)

        return OverlayLayout(
            chart_rect=chart_rect,
            plot_rect=plot_rect,
            price_axis_rect=price_rect,
            time_axis_rect=time_rect,
        )

    # ----------------------------
    # Drawing helpers
    # ----------------------------
    def _draw_line(self, renderer, x1: float, y1: float, x2: float, y2: float,
                   width: float = 1.0, color: Any = None) -> None:
        renderer.draw_line_px(x1, y1, x2, y2, color=color, width=width)

    def _draw_price_axis_separator(self, renderer, axis_rect: Rect, plot_rect: Rect) -> None:
        ax, ay, aw, ah = axis_rect
        px, py, pw, ph = plot_rect
        side = (self.config["price_axis"]["side"] or "right").lower()
        sep_w = float(self.config["price_axis"]["separator_width"])
        sep_col = self.config["colors"]["axis_separator"]

        x_sep = (ax + aw) if side == "left" else ax
        self._draw_line(renderer, x_sep, py, x_sep, py + ph, width=sep_w, color=sep_col)

    def _draw_time_axis_separator(self, renderer, axis_rect: Rect, plot_rect: Rect) -> None:
        tx, ty, tw, th = axis_rect
        px, py, pw, ph = plot_rect
        sep_w = float(self.config["time_axis"]["separator_width"])
        sep_col = self.config["colors"]["axis_separator"]

        y_sep = ty if self._y_down else (ty + th)
        self._draw_line(renderer, px, y_sep, px + pw, y_sep, width=sep_w, color=sep_col)
