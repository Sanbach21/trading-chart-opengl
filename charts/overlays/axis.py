from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple, List, Optional

Rect = Tuple[float, float, float, float]


@dataclass
class PriceAxisStyle:
    padding_px: float = 6.0
    tick_major_len: float = 9.0
    tick_minor_len: float = 9.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    decimals: int = 2
    target_major_ticks: int = 5
    label_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    label_scale: float = 1.0
    min_label_gap_px: float = 8.0   # ← aumentado para evitar solapamientos


class PriceAxisOverlay:
    def __init__(self, overlay, price_scale, config: Optional[Dict[str, Any]] = None) -> None:
        self.overlay = overlay
        self.price_scale = price_scale
        self.text_renderer = None
        self.style = PriceAxisStyle()
        self._last_label_y: float = -9999.0  # Para evitar etiquetas superpuestas

        if config:
            for k, v in config.items():
                if hasattr(self.style, k):
                    setattr(self.style, k, v)

    def _get_side(self) -> str:
        return (self.overlay.config["price_axis"].get("side", "right") or "right").lower()

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect

        if aw <= 0 or ah <= 0:
            return

        side = self._get_side()

        # Solo usamos major ticks (evita duplicados)
        ticks = self.price_scale.get_ticks_ex(
            target_major=self.style.target_major_ticks,
            minor_divisions=0
        )

        self._last_label_y = -9999.0

        for price, y in ticks.get("major", []):
            y = float(y)
            if not (plot_y <= y <= plot_y + plot_h):
                continue

            # Evitar etiquetas muy juntas
            if abs(y - self._last_label_y) < self.style.min_label_gap_px:
                continue

            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len

            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=self.style.tick_width)
            self._draw_label(r, price, y, side, ax, aw)

            self._last_label_y = y

    def _draw_label(self, r, price: float, y: float, side: str, ax: float, aw: float):
        if self.text_renderer is None:
            return

        label = f"{price:.{self.style.decimals}f}"
        text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
        
        text_y = y + text_h * 0.35   # mejor centrado

        if side == "left":
            text_x = ax + aw - self.style.padding_px - text_w
        else:
            text_x = ax + self.style.tick_major_len + self.style.padding_px

        # Clamp para que no se salga del axis
        text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))

        self.text_renderer.render_text(
            label, 
            text_x, 
            text_y,
            scale=self.style.label_scale,
            color=self.style.label_color
        )


@dataclass
class TimeAxisStyle:
    padding_px: float = 6.0
    tick_len: float = 6.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    min_label_spacing_px: float = 90.0
    label_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    label_scale: float = 1.0
    crisp_ticks: bool = True


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

        ax, ay, aw, ah = layout.time_axis_rect
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect

        if aw <= 0 or ah <= 0:
            return

        tick_indices = self.time_scale.get_tick_indices(
            min_spacing_px=self.style.min_label_spacing_px,
            extend_by_one=False,
        )

        max_allowed_x = plot_x + plot_w

        for i in tick_indices:
            if i < 0:
                continue

            x = self.time_scale.get_aligned_x(i, crisp=self.style.crisp_ticks)

            if x < plot_x - 40 or x > max_allowed_x + 20:
                continue

            # Tick del eje
            r.draw_line_px(
                x, ay,
                x, ay + self.style.tick_len,
                color=self.style.tick_color,
                width=self.style.tick_width,
            )

            # Etiqueta
            if self.text_renderer is not None:
                if i < len(self.time_scale._timestamps):
                    ts: datetime = self.time_scale._timestamps[i]
                else:
                    # Future space
                    last_ts = self.time_scale._timestamps[-1]
                    minutes_extra = i - (len(self.time_scale._timestamps) - 1)
                    ts = last_ts + timedelta(minutes=minutes_extra)

                label = ts.strftime("%I:%M %p")

                text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)

                text_x = x - text_w * 0.5
                text_y = ay + ah - 6.0

                # Evitar que se salga por la derecha
                if text_x + text_w > max_allowed_x:
                    text_x = max_allowed_x - text_w

                self.text_renderer.render_text(
                    label,
                    text_x,
                    text_y,
                    scale=self.style.label_scale,
                    color=self.style.label_color,
                )