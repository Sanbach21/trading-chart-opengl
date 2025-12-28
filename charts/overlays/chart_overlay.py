# charts/overlays/chart_overlay.py
from dataclasses import dataclass
from typing import Dict, Tuple, Any

Rect = Tuple[float, float, float, float]  # (x, y, w, h)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _merge_defaults(user_cfg: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Merge shallow + one-level nested dicts, so user cfg overrides defaults."""
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
    ChartOverlay = layout + grid + ejes (bandas).
    NO dibuja series (velas/lineas).
    """

    DEFAULT_CONFIG = {
        "padding": {"left": 0, "right": 0, "top": 0, "bottom": 0},
        "price_axis": {"show": True, "side": "right", "width_px": 90, "separator_width": 1},
        "time_axis": {"show": True, "height_px": 44, "separator_width": 1},
        "grid": {"show": True, "vx": 80, "hy": 20, "line_width": 5},
        "colors": {
            "grid": (0.10, 0.70, 0.05, 0.50),
            "axis_band": (1.0, 1.0, 0.0, 1.0),
            "axis_separator": (0.5, 0.5, 0.5, 1.0),
        },
        "coords": {"y_down": False},  # origen arriba si True (típico UI)
    }

    def __init__(self, time_scale, price_scale, config: Dict[str, Any] = None):
        self.time_scale = time_scale
        self.price_scale = price_scale
        self.config = _merge_defaults(config or {}, self.DEFAULT_CONFIG)
        self._x = self._y = self._w = self._h = 0.0
        self._layout: OverlayLayout | None = None
        self._y_down = bool(self.config["coords"].get("y_down", False))

    # ----------------------------
    # Public API
    # ----------------------------
    def set_view(self, x: float, y: float, w: float, h: float) -> None:
        """Define el rect del chart (área total asignada)."""
        self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)
        self._layout = None  # invalidate

    def get_layout(self) -> OverlayLayout:
        """Devuelve layout calculado (cacheado)."""
        if self._layout is None:
            self._layout = self._compute_layout()

            # Conectamos escalas al PLOT (no al chart completo)
            px, py, pw, ph = self._layout.plot_rect

            # TimeScale en tu engine usa set_view(x, w)
            if hasattr(self.time_scale, "set_view"):
                self.time_scale.set_view(px, pw)

            # PriceScale debería tener set_viewport(x, y, w, h)
            if hasattr(self.price_scale, "set_viewport"):
                self.price_scale.set_viewport(px, py, pw, ph)

        return self._layout

    def get_plot_rect(self) -> Rect:
        """Devuelve el rectángulo del área de plot (sin ejes)."""
        return self.get_layout().plot_rect

    def draw(self, renderer) -> None:
        """Dibuja overlay: grid + bandas de ejes."""
        layout = self.get_layout()

        if self.config["grid"]["show"]:
            self._draw_grid(renderer, layout.plot_rect)

        # Bandas y separadores de ejes
        if self.config["price_axis"]["show"]:
            self._draw_price_axis_band(renderer, layout.price_axis_rect, layout.plot_rect)

        if self.config["time_axis"]["show"]:
            self._draw_time_axis_band(renderer, layout.time_axis_rect, layout.plot_rect)

    # ----------------------------
    # Layout
    # ----------------------------
    def _compute_layout(self) -> OverlayLayout:
        pad = self.config["padding"]
        px_l, px_r = float(pad["left"]), float(pad["right"])
        px_t, px_b = float(pad["top"]), float(pad["bottom"])

        chart_rect: Rect = (self._x, self._y, self._w, self._h)

        # Padding vertical según sistema de coordenadas
        if self._y_down:
            # Origen arriba: y crece hacia abajo → el "top" empuja hacia abajo
            inner_x = self._x + px_l
            inner_y = self._y + px_t
            inner_w = max(0.0, self._w - (px_l + px_r))
            inner_h = max(0.0, self._h - (px_t + px_b))
        else:
            # Origen abajo: y crece hacia arriba (comportamiento original)
            inner_x = self._x + px_l
            inner_y = self._y + px_b
            inner_w = max(0.0, self._w - (px_l + px_r))
            inner_h = max(0.0, self._h - (px_t + px_b))

        pa, ta = self.config["price_axis"], self.config["time_axis"]
        price_axis_w = float(pa["width_px"]) if pa["show"] else 0.0
        time_axis_h = float(ta["height_px"]) if ta["show"] else 0.0

        # Layout vertical (plot vs time axis) según sistema
        if self._y_down:
            # y-down: el time-axis "abajo" está en el borde inferior (mayor y)
            plot_y = inner_y
            plot_h = max(0.0, inner_h - time_axis_h)
            time_y = inner_y + plot_h
            time_axis_rect: Rect = (
                (inner_x, time_y, inner_w, time_axis_h) if ta["show"] else (0.0, 0.0, 0.0, 0.0)
            )
        else:
            # y-up: el time-axis "abajo" empieza en inner_y
            plot_h = max(0.0, inner_h - time_axis_h)
            plot_y = inner_y + time_axis_h
            time_axis_rect: Rect = (
                (inner_x, inner_y, inner_w, time_axis_h) if ta["show"] else (0.0, 0.0, 0.0, 0.0)
            )

        # Layout horizontal (plot vs price axis)
        side = (pa["side"] or "right").lower()
        if pa["show"] and side == "left":
            price_axis_rect: Rect = (inner_x, plot_y, price_axis_w, plot_h)
            plot_rect: Rect = (inner_x + price_axis_w, plot_y, max(0.0, inner_w - price_axis_w), plot_h)
        else:
            plot_rect: Rect = (inner_x, plot_y, max(0.0, inner_w - price_axis_w), plot_h)
            price_axis_rect: Rect = (
                (inner_x + plot_rect[2], plot_y, price_axis_w, plot_h) if pa["show"] else (0.0, 0.0, 0.0, 0.0)
            )

        return OverlayLayout(
            chart_rect=chart_rect,
            plot_rect=plot_rect,
            price_axis_rect=price_axis_rect,
            time_axis_rect=time_axis_rect,
        )

    # ----------------------------
    # Drawing helpers (renderer-agnostic)
    # ----------------------------
    def _draw_rect(self, renderer, rect: Rect, color=None) -> None:
        """Dibuja un rect de fondo si el renderer lo soporta."""
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return

        if hasattr(renderer, "draw_rect_px"):
            try:
                renderer.draw_rect_px(x, y, w, h, color=color)
            except TypeError:
                renderer.draw_rect_px(x, y, w, h)
        elif hasattr(renderer, "rect"):
            try:
                renderer.rect(x, y, w, h, color=color)
            except TypeError:
                renderer.rect(x, y, w, h)

    def _draw_line(self, renderer, x1, y1, x2, y2, width=1, color=None) -> None:
        """Dibuja línea si el renderer lo soporta."""
        if hasattr(renderer, "draw_line_px"):
            try:
                renderer.draw_line_px(x1, y1, x2, y2, color=color, width=width)
            except TypeError:
                renderer.draw_line_px(x1, y1, x2, y2, color)
        elif hasattr(renderer, "line"):
            try:
                renderer.line(x1, y1, x2, y2, color=color, width=width)
            except TypeError:
                renderer.line(x1, y1, x2, y2, color)

    # ----------------------------
    # Grid / Axis bands
    # ----------------------------
    def _draw_grid(self, renderer, plot_rect: Rect) -> None:
       
        """Dibuja la cuadrícula principal dentro del área de plot."""
        x, y, w, h = plot_rect
        if w <= 0 or h <= 0:
            return

        grid_cfg = self.config["grid"]
        step_x = max(10.0, float(grid_cfg["vx"]))
        step_y = max(10.0, float(grid_cfg["hy"]))
        lw = max(1, int(grid_cfg["line_width"]))
        col = self.config["colors"]["grid"]

        # Vertical lines
        gx = x
        while gx <= x + w:
            
            self._draw_line(renderer, gx, y, gx, y + h, width=lw, color=col)
            gx += step_x

        # Horizontal lines
        gy = y
        while gy <= y + h:
            self._draw_line(renderer, x, gy, x + w, gy, width=lw, color=col)
            gy += step_y

    def _draw_price_axis_band(self, renderer, axis_rect: Rect, plot_rect: Rect) -> None:
        """Dibuja la banda y separador del eje de precios."""
        band_col = self.config["colors"]["axis_band"]
        sep_col = self.config["colors"]["axis_separator"]
        pa = self.config["price_axis"]
        sep_w = max(1, int(pa["separator_width"]))

        self._draw_rect(renderer, axis_rect, color=band_col)

        # Separador entre plot y eje
        ax, ay, aw, ah = axis_rect
        px, py, pw, ph = plot_rect
        side = pa["side"].lower()

        if side == "left":
            x_sep = ax + aw
            self._draw_line(renderer, x_sep, py, x_sep, py + ph, width=sep_w, color=sep_col)
        else:
            x_sep = ax
            self._draw_line(renderer, x_sep, py, x_sep, py + ph, width=sep_w, color=sep_col)

    def _draw_time_axis_band(self, renderer, axis_rect: Rect, plot_rect: Rect) -> None:
        """Dibuja la banda inferior y el separador horizontal del eje de tiempo."""
        band_col = self.config["colors"]["axis_band"]
        sep_col = self.config["colors"]["axis_separator"]
        ta = self.config["time_axis"]
        sep_w = max(1, int(ta["separator_width"]))

        self._draw_rect(renderer, axis_rect, color=band_col)

        # Separador entre plot y time axis
        tx, ty, tw, th = axis_rect
        px, py, pw, ph = plot_rect

        if self._y_down:
            y_sep = ty  # borde superior de la banda
        else:
            y_sep = ty + th  # borde superior cuando y-up

        self._draw_line(renderer, px, y_sep, px + pw, y_sep, width=sep_w, color=sep_col)
