# render/text/bitmap_text.py
from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Tuple

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_COMPILE_STATUS,
    GL_DYNAMIC_DRAW,
    GL_FALSE,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_LINK_STATUS,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_SRC_ALPHA,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TRIANGLES,
    GL_TRUE,
    GL_VERTEX_SHADER,
    glActiveTexture,
    glAttachShader,
    glBindBuffer,
    glBindTexture,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glBufferSubData,
    glCompileShader,
    glCreateProgram,
    glCreateShader,
    glDeleteProgram,
    glDeleteShader,
    glDeleteVertexArrays,
    glDeleteBuffers,
    glDrawArrays,
    glEnable,
    glEnableVertexAttribArray,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    glGetUniformLocation,
    glLinkProgram,
    glShaderSource,
    glUniform1i,
    glUniform2f,
    glUniform4f,
    glUseProgram,
    glVertexAttribPointer,
    glGenVertexArrays,
    glGenBuffers,
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _compile_shader(shader_type: int, src: str) -> int:
    sid = glCreateShader(shader_type)
    glShaderSource(sid, src)
    glCompileShader(sid)

    ok = glGetShaderiv(sid, GL_COMPILE_STATUS)
    if ok != GL_TRUE:
        info = glGetShaderInfoLog(sid).decode("utf-8", errors="ignore")
        glDeleteShader(sid)
        raise RuntimeError(f"Shader compile failed:\n{info}")

    return sid


def _link_program(vs: int, fs: int) -> int:
    pid = glCreateProgram()
    glAttachShader(pid, vs)
    glAttachShader(pid, fs)
    glLinkProgram(pid)

    ok = glGetProgramiv(pid, GL_LINK_STATUS)
    if ok != GL_TRUE:
        info = glGetProgramInfoLog(pid).decode("utf-8", errors="ignore")
        glDeleteProgram(pid)
        raise RuntimeError(f"Program link failed:\n{info}")

    return pid


class BitmapTextRenderer:
    """
    Renderer simple (como en el tutorial clásico):
    - 1 VAO/VBO
    - por glyph: actualiza vertices y dibuja 2 triángulos
    - textura del glyph en canal R
    """

    def __init__(self, shader_dir: str = "render/shaders") -> None:
        shader_dir_path = Path(shader_dir)
        vert_path = shader_dir_path / "bitmap_text.vert"
        frag_path = shader_dir_path / "bitmap_text.frag"

        if not vert_path.exists():
            raise FileNotFoundError(f"No existe shader: {vert_path}")
        if not frag_path.exists():
            raise FileNotFoundError(f"No existe shader: {frag_path}")

        vs = _compile_shader(GL_VERTEX_SHADER, _read_text(vert_path))
        fs = _compile_shader(GL_FRAGMENT_SHADER, _read_text(frag_path))
        self.program = _link_program(vs, fs)

        # shaders ya linkeados: los borramos
        glDeleteShader(vs)
        glDeleteShader(fs)

        # uniforms
        self.uResolution = glGetUniformLocation(self.program, "uResolution")
        self.uColor = glGetUniformLocation(self.program, "uColor")
        self.uTexture = glGetUniformLocation(self.program, "uTexture")

        # VAO/VBO
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)

        # 6 vertices * 4 floats (x,y,u,v) * 4 bytes
        glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(
            0, 4, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(0)
        )

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def destroy(self) -> None:
        try:
            if getattr(self, "vbo", 0):
                glDeleteBuffers(1, [self.vbo])
            if getattr(self, "vao", 0):
                glDeleteVertexArrays(1, [self.vao])
            if getattr(self, "program", 0):
                glDeleteProgram(self.program)
        except Exception:
            pass

    def draw_text(
        self,
        font,
        text: str,
        x: float,
        y: float,
        size_px: float,
        color: Tuple[float, float, float, float],
        resolution: Tuple[int, int],
        letter_spacing_px: float = 0.0,
    ) -> None:
        """
        Dibuja texto en coordenadas de pixeles.
        - (x,y) es el "baseline" (como en el video).
        """

        # blending típico para texto
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glUseProgram(self.program)

        # uniforms
        glUniform2f(self.uResolution, float(resolution[0]), float(resolution[1]))
        glUniform4f(self.uColor, float(color[0]), float(color[1]), float(color[2]), float(color[3]))

        glActiveTexture(GL_TEXTURE0)
        glUniform1i(self.uTexture, 0)

        glBindVertexArray(self.vao)

        scale = float(size_px) / float(font.pixel_size)

        pen_x = float(x)
        for ch in text:
            glyph = font.get_glyph(ch)
            if glyph is None:
                # fallback simple si falta glyph
                pen_x += size_px * 0.33
                continue

            # layout como tutorial
            xpos = pen_x + glyph.bearing_x * scale
            ypos = float(y) - (glyph.h - glyph.bearing_y) * scale

            w = glyph.w * scale
            h = glyph.h * scale

            # 2 triángulos
            vertices = np.array([
                [xpos,     ypos + h,  0.0, 0.0],
                [xpos,     ypos,      0.0, 1.0],
                [xpos + w, ypos,      1.0, 1.0],

                [xpos,     ypos + h,  0.0, 0.0],
                [xpos + w, ypos,      1.0, 1.0],
                [xpos + w, ypos + h,  1.0, 0.0],
            ], dtype=np.float32)

            glBindTexture(GL_TEXTURE_2D, int(glyph.tex_id))

            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, vertices.nbytes, vertices)

            glDrawArrays(GL_TRIANGLES, 0, 6)

            pen_x += (glyph.advance_px * scale) + float(letter_spacing_px)

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)