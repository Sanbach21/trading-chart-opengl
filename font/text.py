# font/text.py
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Dict, Tuple

import freetype
import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_CLAMP_TO_EDGE, GL_COMPILE_STATUS,
    GL_DYNAMIC_DRAW, GL_FALSE, GL_FLOAT, GL_FRAGMENT_SHADER,
    GL_LINEAR, GL_ONE_MINUS_SRC_ALPHA, GL_RED, GL_SRC_ALPHA,
    GL_TEXTURE0, GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S, GL_TEXTURE_WRAP_T, GL_TRIANGLES, GL_UNPACK_ALIGNMENT,
    GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, GL_LINK_STATUS,
    
    glActiveTexture, glAttachShader, glBindBuffer, glBindTexture,
    glBindVertexArray, glBlendFunc, glBufferData, glBufferSubData,
    glCompileShader, glCreateProgram, glCreateShader, glDeleteBuffers,
    glDeleteProgram, glDeleteShader, glDeleteTextures, glDeleteVertexArrays,
    glDrawArrays, glEnable, glEnableVertexAttribArray, glGenBuffers,
    glGenTextures, glGenVertexArrays, glGetProgramInfoLog, glGetProgramiv,
    glGetShaderInfoLog, glGetShaderiv, glGetUniformLocation, glLinkProgram,
    glPixelStorei, glShaderSource, glTexImage2D, glTexParameteri,
    glUniform1i, glUniform4f, glUniformMatrix4fv, glUseProgram,
    glVertexAttribPointer,
)


VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec4 vertex; // x, y, u, v
out vec2 TexCoords;
uniform mat4 projection;

void main() {
    gl_Position = projection * vec4(vertex.xy, 0.0, 1.0);
    TexCoords = vertex.zw;
}
"""

FRAGMENT_SHADER_SOURCE = """
#version 330 core
in vec2 TexCoords;
out vec4 FragColor;
uniform sampler2D textTexture;
uniform vec4 textColor;

void main() {
    float alpha = texture(textTexture, TexCoords).r;
    FragColor = vec4(textColor.rgb, textColor.a * alpha);
}
"""


def ortho(left: float, right: float, bottom: float, top: float):
    mat = np.identity(4, dtype=np.float32)
    mat[0, 0] = 2.0 / (right - left)
    mat[1, 1] = 2.0 / (top - bottom)
    mat[3, 0] = -(right + left) / (right - left)
    mat[3, 1] = -(top + bottom) / (top - bottom)
    return mat


@dataclass
class Character:
    texture_id: int
    size: Tuple[int, int]
    bearing: Tuple[int, int]
    advance: int


class TextRenderer:
    def __init__(
        self,
        font_path: str,
        font_size: int = 11,
        width: int = 1280,
        height: int = 720,
        *,
        snap_to_pixels: bool = True,
        snap_x: bool = False,
        snap_y: bool = True,
    ) -> None:
        self.font_path = font_path
        self.font_size = int(font_size)
        self.width = max(1, int(width))
        self.height = max(1, int(height))

        self.characters: Dict[str, Character] = {}
        self.program: int | None = None
        self.vao: int | None = None
        self.vbo: int | None = None

        self.proj_loc: int = -1
        self.text_color_loc: int = -1
        self.text_sampler_loc: int = -1

        self.snap_to_pixels = bool(snap_to_pixels)
        self.snap_x = bool(snap_x)
        self.snap_y = bool(snap_y)

        self._initialized = False

    def init_gl(self) -> None:
        if self._initialized:
            return

        vs = self._compile_shader(VERTEX_SHADER_SOURCE, GL_VERTEX_SHADER)
        fs = self._compile_shader(FRAGMENT_SHADER_SOURCE, GL_FRAGMENT_SHADER)
        self.program = self._link_program(vs, fs)

        self.proj_loc = glGetUniformLocation(self.program, "projection")
        self.text_color_loc = glGetUniformLocation(self.program, "textColor")
        self.text_sampler_loc = glGetUniformLocation(self.program, "textTexture")

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(0))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        self.update_projection(self.width, self.height)
        self._load_font()

        self._initialized = True

    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)

        if not glGetShaderiv(shader, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(shader).decode(errors="replace")
            glDeleteShader(shader)
            raise RuntimeError(f"Shader compilation failed:\n{error}")
        return shader

    def _link_program(self, vs: int, fs: int) -> int:
        program = glCreateProgram()
        glAttachShader(program, vs)
        glAttachShader(program, fs)
        glLinkProgram(program)

        if not glGetProgramiv(program, GL_LINK_STATUS):
            error = glGetProgramInfoLog(program).decode(errors="replace")
            glDeleteProgram(program)
            raise RuntimeError(f"Program linking failed:\n{error}")

        glDeleteShader(vs)
        glDeleteShader(fs)
        return program

    def _load_font(self) -> None:
        face = freetype.Face(self.font_path)
        face.set_pixel_sizes(0, self.font_size)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        print(f"[TextRenderer] Cargando fuente: {self.font_path} | Tamaño: {self.font_size}px")

        for char_code in range(32, 256):  # ASCII + Latin-1 (suficiente para precios, horas, etc.)
            ch = chr(char_code)
            try:
                face.load_char(ch, freetype.FT_LOAD_RENDER)
                bitmap = face.glyph.bitmap

                if bitmap.width == 0 or bitmap.rows == 0:
                    # Glyph vacío (espacio, etc.)
                    self.characters[ch] = Character(
                        texture_id=0,
                        size=(0, 0),
                        bearing=(0, 0),
                        advance=face.glyph.advance.x,
                    )
                    continue

                tex = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, tex)

                glTexImage2D(
                    GL_TEXTURE_2D, 0, GL_RED,
                    bitmap.width, bitmap.rows, 0,
                    GL_RED, GL_UNSIGNED_BYTE, bitmap.buffer
                )

                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

                self.characters[ch] = Character(
                    texture_id=tex,
                    size=(bitmap.width, bitmap.rows),
                    bearing=(face.glyph.bitmap_left, face.glyph.bitmap_top),
                    advance=face.glyph.advance.x,
                )
            except Exception as e:
                print(f"[TextRenderer] Warning: No se pudo cargar glyph '{ch}': {e}")
                # Fallback simple
                self.characters[ch] = Character(0, (0, 0), (0, 0), 0)

        glBindTexture(GL_TEXTURE_2D, 0)
        print(f"[TextRenderer] {len(self.characters)} glyphs cargados correctamente.")

    def update_projection(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))

        if self.program is None:
            return

        projection = ortho(0, self.width, self.height, 0)
        glUseProgram(self.program)
        glUniformMatrix4fv(self.proj_loc, 1, GL_FALSE, projection)
        glUseProgram(0)

    def render_text(self, text: str, x: float, y: float, scale: float = 1.0,
                    color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)) -> None:
        if not self._initialized or self.program is None:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glUseProgram(self.program)
        glUniform4f(self.text_color_loc, *color)
        glUniform1i(self.text_sampler_loc, 0)

        glActiveTexture(GL_TEXTURE0)
        glBindVertexArray(self.vao)

        pen_x = float(x)
        pen_y = float(y)

        if self.snap_to_pixels:
            if self.snap_x: pen_x = round(pen_x)
            if self.snap_y: pen_y = round(pen_y)

        for ch in text:
            c = self.characters.get(ch)
            if c is None or c.texture_id == 0:
                # Avanzar aunque sea espacio
                if c is not None:
                    pen_x += (c.advance >> 6) * scale
                continue

            xpos = pen_x + c.bearing[0] * scale
            ypos = pen_y - c.bearing[1] * scale

            if self.snap_to_pixels:
                xpos = round(xpos) if self.snap_x else xpos
                ypos = round(ypos) if self.snap_y else ypos

            w = c.size[0] * scale
            h = c.size[1] * scale

            vertices = np.array([
                [xpos,     ypos,     0.0, 0.0],
                [xpos,     ypos + h, 0.0, 1.0],
                [xpos + w, ypos + h, 1.0, 1.0],
                [xpos,     ypos,     0.0, 0.0],
                [xpos + w, ypos + h, 1.0, 1.0],
                [xpos + w, ypos,     1.0, 0.0],
            ], dtype=np.float32)

            glBindTexture(GL_TEXTURE_2D, c.texture_id)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, vertices.nbytes, vertices)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            pen_x += (c.advance >> 6) * scale

        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)

    def measure_text(self, text: str, scale: float = 1.0) -> Tuple[float, float]:
        width = 0.0
        max_h = 0.0
        for ch in text:
            c = self.characters.get(ch)
            if c is None or c.texture_id == 0:
                continue
            width += (c.advance >> 6) * scale
            max_h = max(max_h, c.size[1] * scale)
        return width, max_h

    def shutdown(self) -> None:
        for char in self.characters.values():
            if char.texture_id != 0:
                glDeleteTextures(1, [char.texture_id])
        self.characters.clear()

        if self.vbo: glDeleteBuffers(1, [self.vbo])
        if self.vao: glDeleteVertexArrays(1, [self.vao])
        if self.program: glDeleteProgram(self.program)

        self._initialized = False