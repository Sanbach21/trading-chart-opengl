from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple


def _clamp(x: float, lo: float, hi: float) -> float:
    """
    Limita un valor x al rango [lo, hi].

    Parámetros:
        x: Valor a limitar.
        lo: Límite inferior.
        hi: Límite superior.

    Retorna:
        El valor x recortado al rango definido.
    """
    return max(lo, min(hi, x))


@dataclass
class PriceRange:
    """
    Representa un rango de precios visible.

    Atributos:
        low: Precio mínimo del rango.
        high: Precio máximo del rango.
    """
    low: float
    high: float

    @property
    def length(self) -> float:
        """
        Devuelve la longitud total del rango de precios.

        Retorna:
            high - low
        """
        return self.high - self.low

    @property
    def mid(self) -> float:
        """
        Devuelve el punto medio del rango de precios.

        Retorna:
            El valor central entre low y high.
        """
        return 0.5 * (self.low + self.high)


def _is_finite(x: float) -> bool:
    """
    Comprueba si un número es finito.

    Esto evita trabajar con valores inválidos como:
    - inf
    - -inf
    - nan

    Parámetros:
        x: Valor a evaluar.

    Retorna:
        True si el valor es finito, False en caso contrario.
    """
    return math.isfinite(x)


def _nice_step(raw_step: float) -> float:
    """
    Convierte un paso arbitrario en un paso 'bonito' para los ticks del eje.

    La idea es transformar un valor cualquiera en uno más legible visualmente,
    por ejemplo:
        0.387  -> 0.5
        1.34   -> 2
        6.7    -> 10
        0.021  -> 0.02

    Esto ayuda a que las marcas del eje de precios se vean limpias y naturales.

    Parámetros:
        raw_step: Paso original calculado a partir del rango visible.

    Retorna:
        Un paso ajustado a una escala bonita.
    """
    if raw_step <= 0 or not _is_finite(raw_step):
        return 1.0

    exp = math.floor(math.log10(raw_step))
    f = raw_step / (10 ** exp)

    if f <= 1.0:
        nice = 1.0
    elif f <= 2.0:
        nice = 2.0
    elif f <= 5.0:
        nice = 5.0
    else:
        nice = 10.0

    return nice * (10 ** exp)


def _nice_bounds(lo: float, hi: float, step: float) -> Tuple[float, float]:
    """
    Ajusta los límites inferior y superior de un rango al múltiplo más cercano
    del step indicado.

    Ejemplo:
        lo = 101.3, hi = 109.2, step = 2
        -> lo2 = 100, hi2 = 110

    Esto facilita que los ticks empiecen y terminen en números redondos.

    Parámetros:
        lo: Límite inferior actual.
        hi: Límite superior actual.
        step: Paso principal usado para los ticks.

    Retorna:
        Una tupla (lo2, hi2) con los límites ajustados.
    """
    if step <= 0:
        return lo, hi
    lo2 = math.floor(lo / step) * step
    hi2 = math.ceil(hi / step) * step
    return lo2, hi2


class PriceScale:
    """
    Maneja la escala vertical de precios de un gráfico.

    Responsabilidades principales:
    - Mantener el rango visible de precios.
    - Convertir un precio a coordenada Y en pantalla.
    - Convertir una coordenada Y a precio.
    - Ajustar el rango automáticamente según datos visibles.
    - Permitir escalado manual (zoom vertical).
    - Permitir scroll vertical del rango.
    - Generar ticks mayores y menores del eje de precios.

    Esta clase no dibuja directamente el eje; su trabajo es matemático:
    transformar y administrar el rango visible de precios.
    """

    def __init__(
        self,
        *,
        y_down: bool = True,
        top_padding_px: float = 6.0,
        bottom_padding_px: float = 6.0,
        min_range: float = 1e-9,
    ) -> None:
        """
        Inicializa la escala de precios.

        Parámetros:
            y_down:
                Si True, el eje Y crece hacia abajo (típico en coordenadas
                de pantalla). Si False, crece hacia arriba.
            top_padding_px:
                Espacio reservado arriba dentro del viewport.
            bottom_padding_px:
                Espacio reservado abajo dentro del viewport.
            min_range:
                Rango mínimo permitido para evitar divisiones por cero
                o escalas degeneradas.
        """
        # Rectángulo visible donde trabaja la escala.
        self.view_x: float = 0.0
        self.view_y: float = 0.0
        self.view_w: float = 1.0
        self.view_h: float = 1.0

        # Configuración del sistema de coordenadas y márgenes internos.
        self.y_down = bool(y_down)
        self.top_padding_px = float(top_padding_px)
        self.bottom_padding_px = float(bottom_padding_px)

        # Rango actual visible de precios.
        self._range: PriceRange = PriceRange(0.0, 1.0)

        # Si existe un rango manual, el autoscale no lo sobrescribe.
        self._manual_range: Optional[PriceRange] = None

        # Rango mínimo de seguridad.
        self._min_range = float(min_range)

        # Estado temporal para escalar manualmente con el mouse.
        self._scale_start_y: Optional[float] = None
        self._scale_start_range: Optional[PriceRange] = None

        # Estado temporal para scroll vertical con el mouse.
        self._scroll_start_y: Optional[float] = None
        self._scroll_start_range: Optional[PriceRange] = None

    def set_viewport(self, x: float, y: float, w: float, h: float) -> None:
        """
        Define el área visible del gráfico donde se aplicará la escala.

        Parámetros:
            x: Posición X del viewport.
            y: Posición Y del viewport.
            w: Ancho del viewport.
            h: Alto del viewport.

        Nota:
            Se fuerza un ancho y alto mínimos de 1.0 para evitar problemas
            matemáticos.
        """
        self.view_x = float(x)
        self.view_y = float(y)
        self.view_w = max(1.0, float(w))
        self.view_h = max(1.0, float(h))

    def set_coord_system(self, *, y_down: bool) -> None:
        """
        Cambia la orientación del eje Y.

        Parámetros:
            y_down:
                True si Y crece hacia abajo.
                False si Y crece hacia arriba.
        """
        self.y_down = bool(y_down)

    def set_padding(
        self,
        *,
        top_px: float | None = None,
        bottom_px: float | None = None,
    ) -> None:
        """
        Ajusta el padding superior e inferior del área utilizable.

        Parámetros:
            top_px: Nuevo padding superior en píxeles.
            bottom_px: Nuevo padding inferior en píxeles.

        Nota:
            Si alguno es None, ese valor no se modifica.
        """
        if top_px is not None:
            self.top_padding_px = max(0.0, float(top_px))
        if bottom_px is not None:
            self.bottom_padding_px = max(0.0, float(bottom_px))

    def _normalize_range(self, lo: float, hi: float) -> PriceRange:
        """
        Normaliza un rango de precios para garantizar que sea válido.

        Qué hace:
        - Convierte ambos valores a float.
        - Si hi < lo, los intercambia.
        - Si el rango es demasiado pequeño, lo expande hasta _min_range.

        Parámetros:
            lo: Límite inferior.
            hi: Límite superior.

        Retorna:
            Un PriceRange válido y seguro.
        """
        lo = float(lo)
        hi = float(hi)

        if hi < lo:
            lo, hi = hi, lo

        if hi - lo < self._min_range:
            mid = 0.5 * (hi + lo)
            lo = mid - 0.5 * self._min_range
            hi = mid + 0.5 * self._min_range

        return PriceRange(lo, hi)

    def set_manual_range(self, low: float, high: float) -> None:
        """
        Establece manualmente un rango fijo de precios.

        Mientras exista un rango manual:
        - set_range no lo sobrescribe.
        - autoscale tampoco lo sobrescribe.

        Parámetros:
            low: Precio mínimo.
            high: Precio máximo.
        """
        if not (_is_finite(low) and _is_finite(high)):
            return

        self._manual_range = self._normalize_range(low, high)
        self._range = self._manual_range

    def clear_manual_range(self) -> None:
        """
        Elimina el rango manual.

        Después de llamar a este método, el rango podrá volver a ajustarse
        automáticamente mediante autoscale o set_range.
        """
        self._manual_range = None

    def set_range(self, low: float, high: float) -> None:
        """
        Define el rango actual visible, salvo que exista un rango manual.

        Parámetros:
            low: Precio mínimo.
            high: Precio máximo.
        """
        if self._manual_range is not None:
            return

        if not (_is_finite(low) and _is_finite(high)):
            return

        self._range = self._normalize_range(low, high)

    def get_range(self) -> PriceRange:
        """
        Devuelve el rango actual visible de precios.

        Retorna:
            Un objeto PriceRange con low y high.
        """
        return self._range

    def autoscale_from_provider(
        self,
        visible_start: int,
        visible_end: int,
        get_high_low: Callable[[int], Tuple[float, float]],
        *,
        pad_ratio: float = 0.02,
    ) -> None:
        """
        Calcula automáticamente el rango visible usando un proveedor de datos.

        Recorre los índices visibles y obtiene para cada uno:
        - high
        - low

        Luego calcula el mínimo y máximo global visibles, y aplica un padding
        extra porcentual para que las velas no queden pegadas arriba o abajo.

        Parámetros:
            visible_start: Índice inicial visible.
            visible_end: Índice final visible.
            get_high_low:
                Función que recibe un índice y devuelve (high, low).
            pad_ratio:
                Porcentaje de padding respecto al rango calculado.
                Ejemplo: 0.02 = 2%.
        """
        if self._manual_range is not None:
            return
        if visible_end < visible_start:
            return

        lo = math.inf
        hi = -math.inf

        for i in range(int(visible_start), int(visible_end) + 1):
            h, l = get_high_low(i)
            h = float(h)
            l = float(l)

            if not (_is_finite(h) and _is_finite(l)):
                continue

            if l < lo:
                lo = l
            if h > hi:
                hi = h

        if not (_is_finite(lo) and _is_finite(hi)):
            return

        rng = max(self._min_range, hi - lo)
        pad = rng * max(0.0, float(pad_ratio))
        self.set_range(lo - pad, hi + pad)

    def autoscale_from_hilo_arrays(
        self,
        visible_start: int,
        visible_end: int,
        highs: Sequence[float],
        lows: Sequence[float],
        *,
        pad_ratio: float = 0.02,
    ) -> None:
        """
        Variante conveniente de autoscale_from_provider para trabajar
        directamente con arrays/listas de highs y lows.

        Parámetros:
            visible_start: Índice inicial visible.
            visible_end: Índice final visible.
            highs: Secuencia con máximos.
            lows: Secuencia con mínimos.
            pad_ratio: Padding extra porcentual.
        """
        n = min(len(highs), len(lows))
        if n <= 0:
            return

        vs = int(_clamp(visible_start, 0, n - 1))
        ve = int(_clamp(visible_end, 0, n - 1))

        self.autoscale_from_provider(
            vs,
            ve,
            lambda i: (highs[i], lows[i]),
            pad_ratio=pad_ratio,
        )

    def _usable_bounds(self) -> Tuple[float, float, float]:
        """
        Calcula la zona vertical realmente utilizable dentro del viewport.

        Se resta el padding superior e inferior para obtener el espacio
        donde las velas y precios deben proyectarse.

        Retorna:
            Una tupla:
                y0: inicio útil
                y1: final útil
                usable_h: alto útil
        """
        y0 = self.view_y + self.top_padding_px
        y1 = (self.view_y + self.view_h) - self.bottom_padding_px
        usable_h = max(1.0, y1 - y0)
        return y0, y1, usable_h

    def price_to_y(self, price: float) -> float:
        """
        Convierte un precio a coordenada Y dentro del viewport.

        Flujo de cálculo:
        1. Toma el rango actual (low, high).
        2. Convierte el precio a una proporción t en [0, 1].
        3. Aplica un margen interno adicional para que los precios no queden
           exactamente pegados a los bordes visuales.
        4. Lo proyecta al sistema Y del viewport.

        Parámetros:
            price: Precio a convertir.

        Retorna:
            Coordenada Y en pantalla.

        Nota importante:
            Aquí tienes un margen fijo adicional:
                margin = 0.05
            Eso significa que el precio utilizable no ocupa el 100% del alto
            útil, sino aproximadamente el 90%, dejando un 5% arriba y 5% abajo.
        """
        p = float(price)
        lo, hi = self._range.low, self._range.high
        rng = max(self._min_range, hi - lo)

        y0, y1, usable_h = self._usable_bounds()

        # t representa la posición relativa del precio dentro del rango.
        # t = 0   -> precio mínimo
        # t = 1   -> precio máximo
        t = (p - lo) / rng

        # Margen visual interno adicional.
        # Puedes subir o bajar este valor según cuánto espacio libre quieras
        # arriba y abajo dentro del área utilizable.
        margin = 0.05  # 5% arriba y 5% abajo

        # Reescala t para que no ocupe todo el rango vertical útil.
        t = margin + t * (1.0 - 2.0 * margin)

        if self.y_down:
            return float(y1 - t * usable_h)
        return float(y0 + t * usable_h)

    def y_to_price(self, y: float) -> float:
        """
        Convierte una coordenada Y de pantalla nuevamente a un precio.

        Esto es útil para:
        - interacción con el mouse
        - arrastre vertical
        - lectura del precio bajo el cursor

        Parámetros:
            y: Coordenada Y en pantalla.

        Retorna:
            El precio correspondiente a esa posición.
        """
        lo, hi = self._range.low, self._range.high
        rng = max(self._min_range, hi - lo)

        y0, y1, usable_h = self._usable_bounds()
        yy = float(y)

        if self.y_down:
            t = (y1 - yy) / usable_h
        else:
            t = (yy - y0) / usable_h

        t = _clamp(t, 0.0, 1.0)
        return float(lo + t * rng)

    def start_scale(self, mouse_y: float) -> None:
        """
        Inicia una operación de escalado manual.

        Normalmente se llama cuando el usuario comienza a arrastrar
        el eje de precios para expandir o comprimir la escala.

        Parámetros:
            mouse_y: Posición inicial Y del mouse.
        """
        self._scale_start_y = float(mouse_y)
        self._scale_start_range = PriceRange(self._range.low, self._range.high)

    def scale_to(self, mouse_y: float) -> None:
        """
        Actualiza la escala vertical durante un arrastre manual.

        Comportamiento actual:
        - Arrastrar hacia abajo:
            aumenta el rango visible -> velas más comprimidas
        - Arrastrar hacia arriba:
            reduce el rango visible -> velas más grandes/expandidas

        Parámetros:
            mouse_y: Posición actual Y del mouse.

        Nota:
            Usa un coeficiente lineal simple con sensibilidad configurable.
            Además, aplica límites duros para que el zoom vertical no se vaya
            al infinito ni colapse demasiado.
        """
        if self._scale_start_y is None or self._scale_start_range is None:
            return
        if self._manual_range is not None:
            return

        y = float(mouse_y)
        src = self._scale_start_range

        # Sensibilidad del escalado vertical.
        sensitivity = 0.0025

        # Distancia recorrida por el mouse desde el inicio del gesto.
        dy = y - self._scale_start_y

        # Lógica invertida intencionalmente:
        # abajo  -> más rango -> compresión
        # arriba -> menos rango -> expansión
        scale_coeff = 1.0 + dy * sensitivity

        # Evita escalados extremos.
        scale_coeff = max(0.2, min(5.0, scale_coeff))

        center = src.mid
        new_half = src.length * 0.5 * scale_coeff

        # Límites absolutos del rango.
        min_range = 0.0001
        max_range = 1e9

        new_half = max(min_range, min(max_range, new_half))

        self._range = self._normalize_range(center - new_half, center + new_half)

    def end_scale(self) -> None:
        """
        Finaliza la operación de escalado manual.

        Limpia el estado temporal usado durante el drag vertical.
        """
        self._scale_start_y = None
        self._scale_start_range = None

    def start_scroll(self, mouse_y: float) -> None:
        """
        Inicia una operación de desplazamiento vertical del rango.

        A diferencia del escalado, aquí no se cambia el tamaño del rango,
        sino que se desplaza completo hacia arriba o abajo.

        Parámetros:
            mouse_y: Posición inicial Y del mouse.
        """
        # Guardamos la posición inicial del mouse y el rango actual para calcular
        self._scroll_start_y = float(mouse_y)
        self._scroll_start_range = PriceRange(self._range.low, self._range.high)

    def scroll_to(self, mouse_y: float) -> None:
        """
        Desplaza verticalmente el rango visible según el movimiento del mouse.

        Lógica:
        - Calcula cuántos precios equivalen a un píxel.
        - Convierte el desplazamiento vertical del mouse en desplazamiento
          de precios.
        - Mueve el rango completo manteniendo su tamaño.

        Parámetros:
            mouse_y: Posición actual Y del mouse.
        """
        if self._scroll_start_y is None or self._scroll_start_range is None:
            return
        if self._manual_range is not None:
            return

        start = self._scroll_start_y
        current = float(mouse_y)
        dy = current - start

        src = self._scroll_start_range
        price_per_px = src.length / max(
            1.0,
            self.view_h - self.top_padding_px - self.bottom_padding_px,
        )

        price_delta = dy * price_per_px
        self._range = self._normalize_range(
            src.low + price_delta,
            src.high + price_delta,
        )

    def end_scroll(self) -> None:
        """
        Finaliza la operación de scroll vertical.

        Limpia el estado temporal usado durante el desplazamiento.
        """
        self._scroll_start_y = None
        self._scroll_start_range = None

    def get_ticks(self, target_count: int = 8) -> List[Tuple[float, float]]:
        """
        Devuelve únicamente los ticks mayores del eje de precios.

        Parámetros:
            target_count: Cantidad objetivo aproximada de ticks mayores.

        Retorna:
            Lista de tuplas (precio, y).
        """
        out = self.get_ticks_ex(target_major=target_count, minor_divisions=1)
        return out["major"]

    def get_ticks_ex(
        self,
        target_major: int = 8,
        minor_divisions: int = 4,
    ) -> Dict[str, List[Tuple[float, float]]]:
        """
        Genera ticks mayores y menores para la escala de precios.

        Flujo:
        1. Toma el rango visible actual.
        2. Calcula un step crudo según la cantidad objetivo.
        3. Lo convierte a un step 'bonito'.
        4. Ajusta límites a múltiplos bonitos.
        5. Recorre el rango generando ticks mayores.
        6. Inserta ticks menores entre cada tick mayor.

        Parámetros:
            target_major:
                Cantidad objetivo de ticks mayores.
            minor_divisions:
                En cuántas divisiones se separa cada segmento mayor.
                Si es 4, entre dos mayores se generan 3 menores.

        Retorna:
            Diccionario con dos listas:
                {
                    "major": [(precio, y), ...],
                    "minor": [(precio, y), ...],
                }
        """
        lo, hi = self._range.low, self._range.high
        rng = max(self._min_range, hi - lo)

        # Cantidad mínima razonable de ticks mayores.
        n = max(2, int(target_major))

        # Paso bruto estimado según el rango visible.
        raw_step = rng / (n - 1)

        # Paso principal ajustado a un valor visualmente agradable.
        major_step = _nice_step(raw_step)

        # Ajustamos límites para arrancar y terminar en valores redondos.
        lo2, hi2 = _nice_bounds(lo, hi, major_step)

        majors: List[Tuple[float, float]] = []
        minors: List[Tuple[float, float]] = []

        if major_step <= 0 or not _is_finite(major_step):
            return {"major": majors, "minor": minors}

        div = max(1, int(minor_divisions))
        minor_step = major_step / div

        v = lo2
        max_iter = 2048
        it = 0

        while v <= hi2 + 1e-12 and it < max_iter:
            # Tick mayor
            majors.append((float(v), self.price_to_y(v)))

            # Ticks menores intermedios
            if div > 1:
                for k in range(1, div):
                    mv = v + k * minor_step
                    if mv <= hi2 + 1e-12:
                        minors.append((float(mv), self.price_to_y(mv)))

            v += major_step
            it += 1

        return {"major": majors, "minor": minors}