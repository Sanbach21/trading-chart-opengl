# charts/overlays/dom.py
"""
DOM Overlay - Depth of Market (Libro de Órdenes)
Versión corregida: se dibuja claramente a la derecha del price axis.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List

from charts.overlays.chart_overlay import ChartOverlay
from data.feeds.binance_orderbook import OrderBookSnapshot, OrderBookLevel


@dataclass
class DOMStyle:
    width_px: float = 190.0
    row_height_px: float = 22.0
    bid_color: Tuple[float, float, float, float] = (0.0, 0.78, 0.0, 0.95)
    ask_color: Tuple[float, float, float, float] = (0.95, 0.15, 0.15, 0.95)
    text_color: Tuple[float, float, float, float] = (0.98, 0.98, 0.98, 1.0)
    bg_color: Tuple[float, float, float, float] = (0.09, 0.09, 0.09, 0.98)
    border_color: Tuple[float, float, float, float] = (0.45, 0.45, 0.45, 0.9)


class DOMOverlay:
    def __init__(
        self,
        overlay: ChartOverlay,
        orderbook_feed,
        style: Optional[DOMStyle] = None,
        text_renderer=None,
    ) -> None:
        self.overlay = overlay
        self.feed = orderbook_feed
        self.style = style or DOMStyle()
        self.text_renderer = text_renderer

    def draw(self, renderer) -> None:
        layout = self.overlay.get_layout()
        ax, ay, aw, ah = layout.price_axis_rect   # ← Usamos el price axis como referencia

        # Posicionamos el DOM justo a la derecha del price axis
        dom_x = ax + aw + 6.0
        dom_y = ay
        dom_w = self.style.width_px
        dom_h = ah

        if dom_w <= 0 or dom_h <= 0 or self.text_renderer is None:
            return

        # Fondo y borde
        renderer.draw_rect_px(dom_x, dom_y, dom_w, dom_h, self.style.bg_color)
        renderer.draw_line_px(dom_x, dom_y, dom_x + dom_w, dom_y, self.style.border_color, 1.5)
        renderer.draw_line_px(dom_x, dom_y + dom_h, dom_x + dom_w, dom_y + dom_h, self.style.border_color, 1.5)
        renderer.draw_line_px(dom_x, dom_y, dom_x, dom_y + dom_h, self.style.border_color, 1.5)
        renderer.draw_line_px(dom_x + dom_w, dom_y, dom_x + dom_w, dom_y + dom_h, self.style.border_color, 1.5)

        book = self.feed.get_current_book()
        if not book:
            return

        row_h = self.style.row_height_px
        max_rows = int(dom_h // row_h)

        # Calcular cantidad máxima para normalizar barras
        max_qty = max((lvl.quantity for lvl in book.bids + book.asks), default=1.0)

        # === BIDS (desde abajo hacia arriba) ===
        y = dom_y + dom_h - row_h
        for level in book.bids[:max_rows]:
            bar_w = (level.quantity / max_qty) * (dom_w * 0.75)
            renderer.draw_rect_px(dom_x, y, bar_w, row_h - 1, self.style.bid_color)

            self.text_renderer.render_text(f"{level.price:.2f}", dom_x + 8, y + row_h*0.65, scale=0.82, color=self.style.text_color)
            self.text_renderer.render_text(f"{level.quantity:.3f}", dom_x + dom_w - 72, y + row_h*0.65, scale=0.82, color=self.style.text_color)
            y -= row_h

        # === ASKS (desde arriba hacia abajo) ===
        y = dom_y
        for level in book.asks[:max_rows]:
            bar_w = (level.quantity / max_qty) * (dom_w * 0.75)
            renderer.draw_rect_px(dom_x + dom_w - bar_w, y, bar_w, row_h - 1, self.style.ask_color)

            self.text_renderer.render_text(f"{level.price:.2f}", dom_x + 8, y + row_h*0.65, scale=0.82, color=self.style.text_color)
            self.text_renderer.render_text(f"{level.quantity:.3f}", dom_x + dom_w - 72, y + row_h*0.65, scale=0.82, color=self.style.text_color)
            y += row_h