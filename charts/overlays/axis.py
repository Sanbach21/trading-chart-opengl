from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional


Rect = Tuple[float, float, float, float]


@dataclass
class PriceAxisStyle:
    padding_px: float = 6.0

    grid_major_color: Tuple[float, float, float, float] = (0.42, 0.42, 0.42, 0.38)
    grid_minor_color: Tuple[float, float, float, float] = (0.32, 0.32, 0.32, 0.22)
    grid_major_width: float = 1.0
    grid_minor_width: float = 1.0

    tick_major_len: float = 7.0
    tick_minor_len: float = 4.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)

    decimals: int = 2
    target_major_ticks: int = 12
    minor_divisions: int = 3
    label_minor: bool = True
    min_label_gap_px: float = 5.0

    grid_every_n_minor_ticks: int = 3

    label_color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    label_scale: float = 1.0

    # margen para no dibujar labels pegadas arriba/abajo
    edge_dead_zone_factor: float = 0.38


class PriceAxisOverlay:
    def __init__(self, overlay, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.text_renderer = None

        self.style = PriceAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect
        if aw <= 0 or ah <= 0 or plot_w <= 0 or plot_h <= 0:
            return

        side = (self.overlay.config["price_axis"].get("side", "right") or "right").lower()

        majors: List[Tuple[float, float]] = []
        minors: List[Tuple[float, float]] = []

        if hasattr(self.price_scale, "get_ticks_ex"):
            out = self.price_scale.get_ticks_ex(
                target_major=self.style.target_major_ticks,
                minor_divisions=self.style.minor_divisions,
            )
            majors = out.get("major", []) or []
            minors = out.get("minor", []) or []
        else:
            majors = self.price_scale.get_ticks(target_count=self.style.target_major_ticks)
        
        # 1) ticks menores
        for _, yy in minors:
            y = float(yy)

            if side == "left":
                x1 = ax + aw - self.style.tick_minor_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_minor_len

            r.draw_line_px(
                x1, y, x2, y,
                color=self.style.tick_color,
                width=float(self.style.tick_width),
            )

        # 2) ticks mayores
        for _, yy in majors:
            y = float(yy)

            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len
            # IMPORTANTE: dibujar los ticks mayores después de los menores, para que no queden tapados por el flush final del frame.
            r.draw_line_px(
                x1, y, x2, y,
                color=self.style.tick_color,
                width=float(self.style.tick_width),
            )

        # 3) grid
        every = max(1, int(self.style.grid_every_n_minor_ticks))

        all_ticks: List[Tuple[float, float, bool]] = []
        for price, y in majors:
            all_ticks.append((float(price), float(y), True))
        for price, y in minors:
            all_ticks.append((float(price), float(y), False))

        all_ticks.sort(key=lambda t: t[1])

        for idx, (_, y, is_major) in enumerate(all_ticks):
            if is_major or (idx % every == 0):
                color = self.style.grid_major_color if is_major else self.style.grid_minor_color
                width = self.style.grid_major_width if is_major else self.style.grid_minor_width

                r.draw_line_px(
                    plot_x,
                    y,
                    plot_x + plot_w,
                    y,
                    color=color,
                    width=float(width),
                )

        # IMPORTANTE:
        # flush del renderer batcheado antes del texto,
        # para que el texto no quede tapado por el flush final del frame.
        # Además, el flush hace que el orden de dibujo sea consistente, para que los labels no queden tapados por los ticks o gridlines.
        if self.text_renderer is not None:
            r.flush()

            last_label_text_y: Optional[float] = None

            if self.style.label_minor:
                normalized_items = [(price, yy) for price, yy, _ in all_ticks]
            else:
                normalized_items = majors

            for price, yy in normalized_items:
                y = float(yy)

                label = f"{price:.{self.style.decimals}f}"
                text_w, text_h = self.text_renderer.measure_text(
                    label,
                    scale=self.style.label_scale,
                )
                # extra_margin_px es un margen adicional para evitar dibujar labels pegados al borde del eje cuando el espacio es limitado. Se basa en el tamaño del texto y un factor definido en el estilo.
                extra_margin_px = 6 
                # el edge_dead_zone es un margen adicional basado en el tamaño del texto, para evitar dibujar labels pegados al borde del eje cuando el espacio es limitado.
                edge_dead_zone = text_h * float(self.style.edge_dead_zone_factor)

                top_limit = ay + edge_dead_zone + extra_margin_px  
                bottom_limit = ay + ah - edge_dead_zone - extra_margin_px  
                
                if y <= top_limit:
                    continue
                if y >= bottom_limit:
                    continue

                # baseline aproximada
                text_y = y + text_h * 0.30

                if side == "left":
                    text_x = ax + aw - self.style.padding_px - text_w
                else:
                    text_x = ax + self.style.tick_major_len + self.style.padding_px

                # clamp final
                text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))
                text_y = max(ay + text_h, min(text_y, ay + ah - 2.0))

                # comparar con la posición final del texto, no con y
                if (
                    last_label_text_y is not None
                    and abs(text_y - last_label_text_y) < self.style.min_label_gap_px
                ):
                    continue

                self.text_renderer.render_text(
                    label,
                    text_x,
                    text_y,
                    scale=self.style.label_scale,
                    color=self.style.label_color,
                )

                last_label_text_y = text_y


@dataclass
class TimeAxisStyle:
    padding_px: float = 6.0

    tick_len: float = 6.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.60, 0.60, 0.60, 0.9)

    gridline_in_plot: bool = True
    grid_major_color: Tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)
    grid_major_width: float = 1.0

    min_label_spacing_px: float = 90.0
    format_compact: bool = True

    label_color: Tuple[float, float, float, float] = (0.88, 0.88, 0.88, 1.0)
    label_scale: float = 1.0


class TimeAxisOverlay:
    def __init__(self, overlay, time_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.time_scale = time_scale
        self.text_renderer = None

        self.style = TimeAxisStyle()
        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.time_axis_rect
        if aw <= 0 or ah <= 0 or plot_w <= 0:
            return

        vr = self.time_scale.get_visible_range()
        vs = int(vr.start_idx)
        ve = int(vr.end_idx)
        if ve <= vs:
            return

        x0 = self.time_scale.index_to_x(vs)
        x1 = self.time_scale.index_to_x(min(vs + 1, ve))
        px_per_bar = max(1.0, abs(x1 - x0))
        step = max(1, int(self.style.min_label_spacing_px / px_per_bar))

        text_items: List[Tuple[float, str]] = []

        for i in range(vs, ve + 1, step):
            if i >= len(self.time_scale._timestamps):
                break

            x = float(self.time_scale.index_to_x(i))

            if self.style.gridline_in_plot:
                r.draw_line_px(
                    x,
                    plot_y,
                    x,
                    plot_y + plot_h,
                    color=self.style.grid_major_color,
                    width=float(self.style.grid_major_width),
                )

            y1 = ay
            y2 = ay + self.style.tick_len
            r.draw_line_px(
                x,
                y1,
                x,
                y2,
                color=self.style.tick_color,
                width=float(self.style.tick_width),
            )

            if self.text_renderer is not None:
                text_items.append((x, self._format_time(self.time_scale._timestamps[i])))

        if self.text_renderer is not None and text_items:
            r.flush()

            for x, label in text_items:
                text_w, text_h = self.text_renderer.measure_text(
                    label,
                    scale=self.style.label_scale,
                )

                text_x = x - text_w * 0.5
                text_y = ay + ah - 6.0

                text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))
                text_y = max(ay + text_h, min(text_y, ay + ah - 2.0))

                self.text_renderer.render_text(
                    label,
                    text_x,
                    text_y,
                    scale=self.style.label_scale,
                    color=self.style.label_color,
                )

    def _format_time(self, ts: datetime) -> str:
        if self.style.format_compact:
            return ts.strftime("%H:%M")
        return ts.strftime("%Y-%m-%d %H:%M")