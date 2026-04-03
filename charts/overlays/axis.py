from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional, Set

import math   # ← Añadido para el snap del grid

Rect = Tuple[float, float, float, float]


# ============================================================
# ESTILOS DEL EJE DE PRECIOS
# ============================================================

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

    edge_dead_zone_factor: float = 0.38
    label_edge_extra_margin_px: float = 6.0


# ============================================================
# OVERLAY DEL EJE DE PRECIOS
# ============================================================

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

    def _get_ticks(self) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
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

        return majors, minors

    def draw(self, r) -> None:
        layout = self.overlay.get_layout()
        plot_x, plot_y, plot_w, plot_h = layout.plot_rect
        ax, ay, aw, ah = layout.price_axis_rect

        if aw <= 0 or ah <= 0 or plot_w <= 0 or plot_h <= 0:
            return

        side = self._get_side()

        majors, minors = self._get_ticks()
        all_ticks = self._build_all_ticks(majors, minors)

        if self.text_renderer is not None:
            visible_label_tick_ids = self._compute_visible_label_tick_ids(
                all_ticks=all_ticks,
                majors=majors,
                ay=ay,
                ah=ah,
            )
        else:
            visible_label_tick_ids = {source_index for _, y, _, source_index in all_ticks
                                      if self._is_inside_tick_clip(y, plot_y, plot_h)}

        # Ticks menores
        for price, yy, is_major, source_index in all_ticks:
            if is_major:
                continue
            y = float(yy)
            if not self._is_inside_tick_clip(y, plot_y, plot_h):
                continue
            if self.style.label_minor and source_index not in visible_label_tick_ids:
                continue

            if side == "left":
                x1 = ax + aw - self.style.tick_minor_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_minor_len

            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=float(self.style.tick_width))

        # Ticks mayores
        for price, yy, is_major, source_index in all_ticks:
            if not is_major:
                continue
            y = float(yy)
            if not self._is_inside_tick_clip(y, plot_y, plot_h):
                continue
            if source_index not in visible_label_tick_ids:
                continue

            if side == "left":
                x1 = ax + aw - self.style.tick_major_len
                x2 = ax + aw
            else:
                x1 = ax
                x2 = ax + self.style.tick_major_len

            r.draw_line_px(x1, y, x2, y, color=self.style.tick_color, width=float(self.style.tick_width))

        # Grid horizontal
        every = max(1, int(self.style.grid_every_n_minor_ticks))
        for idx, (_price, y, is_major, _source_index) in enumerate(all_ticks):
            if not self._is_inside_tick_clip(y, plot_y, plot_h):
                continue
            if not (is_major or (idx % every == 0)):
                continue

            color = self.style.grid_major_color if is_major else self.style.grid_minor_color
            width = self.style.grid_major_width if is_major else self.style.grid_minor_width

            r.draw_line_px(plot_x, y, plot_x + plot_w, y, color=color, width=float(width))

        # Labels
        if self.text_renderer is not None:
            r.flush()
            if self.style.label_minor:
                label_candidates = all_ticks
            else:
                major_set = {(float(p), float(y)) for p, y in majors}
                label_candidates = [item for item in all_ticks if (item[0], item[1]) in major_set and item[2]]

            for price, y, _is_major, source_index in label_candidates:
                if source_index not in visible_label_tick_ids:
                    continue

                label = f"{price:.{self.style.decimals}f}"
                text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
                text_y = y + text_h * 0.30

                if side == "left":
                    text_x = ax + aw - self.style.padding_px - text_w
                else:
                    text_x = ax + self.style.tick_major_len + self.style.padding_px

                text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))
                text_y = max(ay + text_h, min(text_y, ay + ah - 2.0))

                self.text_renderer.render_text(
                    label, text_x, text_y, scale=self.style.label_scale, color=self.style.label_color
                )

    # ====================== MÉTODOS AUXILIARES (sin cambios importantes) ======================
    def _build_all_ticks(self, majors, minors):
        all_ticks: List[Tuple[float, float, bool, int]] = []
        idx = 0
        for price, y in majors:
            all_ticks.append((float(price), float(y), True, idx))
            idx += 1
        for price, y in minors:
            all_ticks.append((float(price), float(y), False, idx))
            idx += 1
        all_ticks.sort(key=lambda t: t[1])
        return all_ticks

    def _is_inside_tick_clip(self, y: float, plot_y: float, plot_h: float) -> bool:
        top_clip = plot_y + 2.0
        bottom_clip = plot_y + plot_h - 2.0
        return top_clip <= y <= bottom_clip

    def _get_label_vertical_limits(self, ay: float, ah: float, text_h: float) -> Tuple[float, float]:
        extra_margin_px = float(self.style.label_edge_extra_margin_px)
        edge_dead_zone = text_h * float(self.style.edge_dead_zone_factor)
        top_limit = ay + edge_dead_zone + extra_margin_px
        bottom_limit = ay + ah - edge_dead_zone - extra_margin_px
        return top_limit, bottom_limit

    def _can_draw_label_by_limits(self, y: float, ay: float, ah: float, text_h: float) -> bool:
        top_limit, bottom_limit = self._get_label_vertical_limits(ay, ah, text_h)
        if y <= top_limit or y >= bottom_limit:
            return False
        return True

    def _measure_label(self, label: str) -> Tuple[float, float]:
        if self.text_renderer is None:
            text_h = 12.0 * float(self.style.label_scale)
            text_w = max(10.0, len(label) * 7.0 * float(self.style.label_scale))
            return text_w, text_h
        return self.text_renderer.measure_text(label, scale=self.style.label_scale)

    def _compute_visible_label_tick_ids(self, all_ticks, majors, ay, ah) -> Set[int]:
        visible_ids: Set[int] = set()
        last_label_text_y: Optional[float] = None

        if self.style.label_minor:
            candidates = all_ticks
        else:
            major_set = {(float(p), float(y)) for p, y in majors}
            candidates = [item for item in all_ticks if (item[0], item[1]) in major_set and item[2]]

        for price, y, _is_major, source_index in candidates:
            label = f"{price:.{self.style.decimals}f}"
            text_w, text_h = self._measure_label(label)

            if not self._can_draw_label_by_limits(y, ay, ah, text_h):
                continue

            text_y = y + text_h * 0.30

            if last_label_text_y is not None and abs(text_y - last_label_text_y) < self.style.min_label_gap_px:
                continue

            visible_ids.add(source_index)
            last_label_text_y = text_y

        return visible_ids


# ============================================================
# ESTILOS DEL EJE DE TIEMPO
# ============================================================

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


# ============================================================
# OVERLAY DEL EJE DE TIEMPO (GRID CORREGIDO)
# ============================================================

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
            x = math.floor(x) + 0.5          # ← CLAVE: mismo snap que las velas

            if self.style.gridline_in_plot:
                r.draw_line_px(
                    x, plot_y, x, plot_y + plot_h,
                    color=self.style.grid_major_color,
                    width=float(self.style.grid_major_width),
                )

            y1 = ay
            y2 = ay + self.style.tick_len
            r.draw_line_px(
                x, y1, x, y2,
                color=self.style.tick_color,
                width=float(self.style.tick_width),
            )

            if self.text_renderer is not None:
                text_items.append((x, self._format_time(self.time_scale._timestamps[i])))

        if self.text_renderer is not None and text_items:
            r.flush()

            for x, label in text_items:
                text_w, text_h = self.text_renderer.measure_text(label, scale=self.style.label_scale)
                text_x = x - text_w * 0.5
                text_y = ay + ah - 6.0

                text_x = max(ax + 2.0, min(text_x, ax + aw - text_w - 2.0))
                text_y = max(ay + text_h, min(text_y, ay + ah - 2.0))

                self.text_renderer.render_text(
                    label, text_x, text_y,
                    scale=self.style.label_scale,
                    color=self.style.label_color,
                )

    def _format_time(self, ts: datetime) -> str:
        if self.style.format_compact:
            return ts.strftime("%H:%M")
        return ts.strftime("%Y-%m-%d %H:%M")