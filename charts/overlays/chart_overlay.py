from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


Rect = Tuple[float, float, float, float]  # (x, y, w, h)


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def merge_defaults(user_cfg: Optional[Dict[str, Any]], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mezcla configuración por defecto con configuración del usuario.

    Soporta mezcla shallow y de un nivel para subdiccionarios.
    """
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
    Maneja el layout visual del chart.

    Responsabilidades:
    - calcular las zonas del chart
    - separar plot, price axis y time axis
    - dibujar bandas de ejes y separadores

    Idea importante:
    - El time axis NO debe ocupar el ancho completo si existe price axis.
    - El time axis debe alinearse con el ancho útil del plot.
    """

    DEFAULT_CONFIG: Dict[str, Any] = {
        "padding": {"left": 0, "right": 0, "top": 0, "bottom": 0},
        "plot_padding": {
            "left": 0,
            "right": 0,
            "top": 0,
            "bottom": 0,
        },
        "price_axis": {
            "show": True,
            "side": "right",
            "width_px": 70,
            "separator_width": 1.5,
        },
        "time_axis": {
            "show": True,
            "height_px": 28,
            "separator_width": 1.5,
        },
        "colors": {
            "bg": (0.12, 0.12, 0.12, 0.92),
            "axis_band": (0.12, 0.12, 0.12, 0.92),
            "axis_separator": (0.80, 0.80, 0.80, 0.95),
        },
        "draw": {
            "axis_bands": True,
        },
        "coords": {"y_down": True},
    }

    def __init__(self, time_scale, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.time_scale = time_scale
        self.price_scale = price_scale
        self.config = merge_defaults(config, self.DEFAULT_CONFIG)

        self._x = 0.0
        self._y = 0.0
        self._w = 0.0
        self._h = 0.0

        self._layout: Optional[OverlayLayout] = None
        self._y_down = bool(self.config["coords"].get("y_down", True))

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def set_view(self, x: float, y: float, w: float, h: float) -> None:
        self._x = float(x)
        self._y = float(y)
        self._w = float(w)
        self._h = float(h)
        self._layout = None

    def get_layout(self) -> OverlayLayout:
        if self._layout is None:
            self._layout = self._compute_layout()

            px, py, pw, ph = self._layout.plot_rect
            self.time_scale.set_view(px, pw)

            if hasattr(self.price_scale, "set_viewport"):
                self.price_scale.set_viewport(px, py, pw, ph)

        return self._layout

    def get_plot_rect(self) -> Rect:
        return self.get_layout().plot_rect

    def draw(self, renderer) -> None:
        layout = self.get_layout()
        colors = self.config["colors"]
        draw_cfg = self.config.get("draw", {})

        if draw_cfg.get("axis_bands", True):
            band = colors.get("axis_band", None)
            if band is not None:
                if self.config["price_axis"]["show"]:
                    ax, ay, aw, ah = layout.price_axis_rect
                    if aw > 0 and ah > 0:
                        renderer.draw_rect_px(ax, ay, aw, ah, color=band)

                if self.config["time_axis"]["show"]:
                    tx, ty, tw, th = layout.time_axis_rect
                    if tw > 0 and th > 0:
                        renderer.draw_rect_px(tx, ty, tw, th, color=band)

        if self.config["price_axis"]["show"]:
            self._draw_price_axis_separator(renderer, layout.price_axis_rect, layout.plot_rect)

        if self.config["time_axis"]["show"]:
            self._draw_time_axis_separator(renderer, layout.time_axis_rect, layout.plot_rect)

    # -------------------------------------------------
    # Layout calculation
    # -------------------------------------------------
    def _compute_layout(self) -> OverlayLayout:
        """
        Calcula el layout completo.

        Regla clave:
        - Primero se calcula la zona interior total.
        - Luego se separa price axis del plot.
        - Finalmente el time axis toma el MISMO ancho horizontal del plot,
          no el ancho interior total.
        """
        pad = self.config["padding"]
        left = float(pad["left"])
        right = float(pad["right"])
        top = float(pad["top"])
        bottom = float(pad["bottom"])

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
        plot_pad = self.config.get("plot_padding", {})

        price_w = float(pa["width_px"]) if pa["show"] else 0.0
        time_h = float(ta["height_px"]) if ta["show"] else 0.0

        plot_pad_left = float(plot_pad.get("left", 0.0))
        plot_pad_right = float(plot_pad.get("right", 0.0))
        plot_pad_top = float(plot_pad.get("top", 0.0))
        plot_pad_bottom = float(plot_pad.get("bottom", 0.0))

        # -------------------------------------------------
        # Espacio vertical bruto:
        # el time axis siempre descuenta altura al plot
        # -------------------------------------------------
        if self._y_down:
            plot_y_raw = inner_y
            plot_h_raw = max(0.0, inner_h - time_h)
            time_y = inner_y + plot_h_raw
        else:
            plot_h_raw = max(0.0, inner_h - time_h)
            plot_y_raw = inner_y + time_h
            time_y = inner_y

        # -------------------------------------------------
        # Separación horizontal:
        # primero separar plot y price axis
        # -------------------------------------------------
        side = (pa["side"] or "right").lower()

        if side == "left":
            price_rect_raw: Rect = (
                inner_x,
                plot_y_raw,
                price_w,
                plot_h_raw,
            ) if pa["show"] else (0.0, 0.0, 0.0, 0.0)

            plot_rect_raw: Rect = (
                inner_x + price_w,
                plot_y_raw,
                max(0.0, inner_w - price_w),
                plot_h_raw,
            )
        else:
            plot_rect_raw = (
                inner_x,
                plot_y_raw,
                max(0.0, inner_w - price_w),
                plot_h_raw,
            )

            price_rect_raw = (
                inner_x + plot_rect_raw[2],
                plot_y_raw,
                price_w,
                plot_h_raw,
            ) if pa["show"] else (0.0, 0.0, 0.0, 0.0)

        # -------------------------------------------------
        # Aplicar padding interno solo al plot
        # -------------------------------------------------
        prx, pry, prw, prh = plot_rect_raw
        plot_rect: Rect = (
            prx + plot_pad_left,
            pry + plot_pad_top,
            max(0.0, prw - plot_pad_left - plot_pad_right),
            max(0.0, prh - plot_pad_top - plot_pad_bottom),
        )

        # -------------------------------------------------
        # Ajustar price axis a la altura visible del plot
        # para que el eje y la banda visual coincidan mejor
        # -------------------------------------------------
        pax, pay, paw, pah = price_rect_raw
        price_rect: Rect = (
            pax,
            plot_y_raw,
            paw,
            plot_h_raw,
        ) if pa["show"] else (0.0, 0.0, 0.0, 0.0)

        # -------------------------------------------------
        # FIX PRINCIPAL:
        # el time axis debe ocupar el mismo ancho horizontal del plot,
        # NO el ancho total interior.
        # -------------------------------------------------
        tx = plot_rect_raw[0]
        tw = plot_rect_raw[2]

        time_rect: Rect = (
            tx,
            time_y,
            tw,
            time_h,
        ) if ta["show"] else (0.0, 0.0, 0.0, 0.0)

        return OverlayLayout(
            chart_rect=chart_rect,
            plot_rect=plot_rect,
            price_axis_rect=price_rect,
            time_axis_rect=time_rect,
        )

    # -------------------------------------------------
    # Drawing helpers
    # -------------------------------------------------
    def _draw_line(
        self,
        renderer,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        width: float = 1.0,
        color: Any = None,
    ) -> None:
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