from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional


Rect = Tuple[float, float, float, float]


# ============================================================
# PRICE AXIS - Major + Minor con etiquetas (como pediste)
# ============================================================
@dataclass
class PriceAxisStyle:
    padding_px: float = 6.0
    tick_major_len: float = 9.0
    tick_minor_len: float = 4.0
    tick_width: float = 1.0
    tick_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    decimals: int = 2
    target_major_ticks: int = 6          # mantiene limpio
    label_color: Tuple[float, float, float, float] = (0.68, 0.68, 0.68, 0.95)
    label_scale: float = 1.0
    min_label_gap_px: float = 5.0


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

    def _get_side(self) -> str:
        return (self.overlay.config["price_axis"].get("side", "right") or "right").lower()

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect

        if aw <= 0 or ah <= 0:
            return

        side = self._get_side()

        ticks = self.price_scale.get_ticks_ex(
            target_major=self.style.target_major_ticks,
            minor_divisions=2
        )

        # ====================== MAJOR TICKS ======================
        for price, y in ticks.get("major", []):
            y = float(y)
            if not (plot_y <= y <= plot_y + plot_h):
                continue

            # Tick largo + grid (el grid ya se dibuja en grid.py)
            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len

            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=self.style.tick_width)
            self._draw_label(r, price, y, side, ax, aw, is_major=True)

        # ====================== MINOR TICKS ======================
        for price, y in ticks.get("minor", []):
            y = float(y)
            if not (plot_y <= y <= plot_y + plot_h):
                continue

            # Tick corto (sin grid)
            if side == "left":
                x1 = ax + aw - self.style.tick_minor_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_minor_len

            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=self.style.tick_width)
            
            # ← AQUÍ ESTABA EL ERROR: ahora sí mostramos la etiqueta en minors
            self._draw_label(r, price, y, side, ax, aw, is_major=False)

    def _draw_label(self, r, price: float, y: float, side: str, ax: float, aw: float, is_major: bool):
        if self.text_renderer is None:
            return

        label = f"{price:.{self.style.decimals}f}"
        text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
        text_y = y + text_h * 0.3

        if side == "left":
            text_x = ax + aw - self.style.padding_px - text_w
        else:
            tick_len = self.style.tick_major_len if is_major else self.style.tick_minor_len
            text_x = ax + tick_len + self.style.padding_px

        text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))

        self.text_renderer.render_text(
            label, text_x, text_y,
            scale=self.style.label_scale,
            color=self.style.label_color
        )


# ============================================================
# TIME AXIS (sin cambios)
# ============================================================
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

        if aw <= 0 or ah <= 0:
            return

        tick_indices = self.time_scale.get_tick_indices(
            min_spacing_px=self.style.min_label_spacing_px,
            extend_by_one=True
        )

        bar_spacing = self.time_scale.bar_spacing
        show_seconds = bar_spacing < 9.0

        for i in tick_indices:
            if i >= len(self.time_scale._timestamps):
                continue

            x = self.time_scale.get_aligned_x(i, crisp=True)

            y1 = ay
            y2 = ay + self.style.tick_len
            r.draw_line_px(x, y1, x, y2,
                           color=self.style.tick_color,
                           width=float(self.style.tick_width))

            if self.text_renderer is not None:
                ts = self.time_scale._timestamps[i]
                label = ts.strftime("%H:%M:%S" if show_seconds else "%H:%M")

                text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
                text_x = x - text_w * 0.5
                text_y = ay + ah - 6.0

                label_center = text_x + text_w * 0.5
                if ax - 50 <= label_center <= ax + aw + 50:
                    self.text_renderer.render_text(
                        label, text_x, text_y,
                        scale=self.style.label_scale,
                        color=self.style.label_color
                    )