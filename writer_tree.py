from pathlib import Path

ROOT = Path("C:/Users/ozzyj/OneDrive/Escritorio/Programacion/libreria_grafica_openGL")
OUTPUT = Path("C:/Users/ozzyj/OneDrive/Escritorio/Programacion/libreria_grafica_openGL/project_tree.txt")

IGNORE_DIRS = {
    "venv",
    "__pycache__",
    ".git",
    ".idea",
    ".vscode"
}

IGNORE_FILES = {
    OUTPUT.name,
}

def should_ignore(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts) or path.name in IGNORE_FILES

with OUTPUT.open("w", encoding="utf-8") as out:
    # 1) ESTRUCTURA
    out.write("PROJECT STRUCTURE\n")
    out.write("=" * 80 + "\n")
    for path in sorted(ROOT.rglob("*")):
        if should_ignore(path):
            continue
        out.write(str(path) + "\n")

    # 2) CONTENIDO DE ARCHIVOS
    out.write("\n\nPROJECT FILE CONTENT\n")
    out.write("=" * 80 + "\n")

    for path in sorted(ROOT.rglob("*")):
        if should_ignore(path) or not path.is_file():
            continue

        out.write("\n" + "=" * 80 + "\n")
        out.write(f"FILE: {path}\n")
        out.write("=" * 80 + "\n")

        try:
            out.write(path.read_text(encoding="utf-8"))
        except Exception as e:
            out.write(f"[No se pudo leer el archivo: {e}]")
