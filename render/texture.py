from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from OpenGL.GL import (
    GL_TEXTURE_2D, GL_RGBA, GL_UNSIGNED_BYTE,
    GL_LINEAR, GL_CLAMP_TO_EDGE,
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T,
    GL_UNPACK_ALIGNMENT,
    glGenTextures, glBindTexture, glTexImage2D,
    glTexParameteri, glPixelStorei
)

from PIL import Image


@dataclass(frozen=True)
class Texture2D:
    id: int
    width: int
    height: int


def load_texture_rgba(path: str | Path) -> Texture2D:
    p = Path(path)
    img = Image.open(p).convert("RGBA")
    w, h = img.size
    pixels = img.tobytes("raw", "RGBA", 0, -1)

    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)

    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

    glTexImage2D(
        GL_TEXTURE_2D, 0, GL_RGBA,
        w, h, 0,
        GL_RGBA, GL_UNSIGNED_BYTE,
        pixels
    )

    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

    glBindTexture(GL_TEXTURE_2D, 0)
    return Texture2D(tex_id, w, h)
