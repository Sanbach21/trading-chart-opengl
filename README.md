# OpenGL Trading Chart Core (Python)

Este proyecto es el **core** de una librería de gráficos tipo trading usando **OpenGL moderno (3.3+ core)** con **GLFW** + **PyOpenGL**.
La idea es construir primero el motor (loop, input, renderer, escalas y series) y **después** integrarlo con UI externa (PyQt5/Tkinter).

## Requisitos
- Python 3.10+ (recomendado)
- GPU/driver con soporte OpenGL 3.3+

## Instalación
Crea un entorno virtual e instala dependencias:

```bash
pip install -r requirements.txt
```

## Ejecutar demo inicial
Esto abre una ventana GLFW y dibuja un triángulo usando shaders (pipeline moderno):
```bash
python -m app.main
```

## Estructura
- `app/`: loop, ventana e input
- `render/`: renderer OpenGL, shaders
- `charts/`: chart engine (scales/series/overlays/panes)
- `data/`: feeds, agregación, storage
- `trading/`: motor de trading (futuro)
- `utils/`: utilidades comunes

## Próximo paso (en nuestra conversación)
1) Confirmar que el demo abre y renderiza.
2) Implementar `render/renderer.py` con primitivas (líneas/rects) y un batch básico.
3) Empezar `charts/scales` (TimeScale/PriceScale) + transformaciones.
