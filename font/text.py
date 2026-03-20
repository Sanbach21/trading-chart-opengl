# font/text.py
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Dict, Tuple

import freetype
import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_CLAMP_TO_EDGE,
    GL_COMPILE_STATUS,
    GL_DYNAMIC_DRAW,
    GL_FALSE,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_LINEAR,
    GL_LINK_STATUS,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_RED,
    GL_SRC_ALPHA,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_UNPACK_ALIGNMENT,
    GL_UNSIGNED_BYTE,
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
    glDeleteBuffers,
    glDeleteProgram,
    glDeleteShader,
    glDeleteTextures,
    glDeleteVertexArrays,
    glDrawArrays,
    glEnable,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenTextures,
    glGenVertexArrays,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    glGetUniformLocation,
    glLinkProgram,
    glPixelStorei,
    glShaderSource,
    glTexImage2D,
    glTexParameteri,
    glUniform1i,
    glUniform4f,
    glUniformMatrix4fv,
    glUseProgram,
    glVertexAttribPointer,
)


VERTEX_SHADER_SOURCE = """
#version 330 core
layout (location = 0) in vec4 vertex; // x, y, u, v

out vec2 TexCoords;

uniform mat4 projection;

void main()
{
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

void main()
{
    float alpha = texture(textTexture, TexCoords).r;
    FragColor = vec4(textColor.rgb, textColor.a * alpha);
}
"""


def ortho(
    left: float,
    right: float,
    bottom: float,
    top: float,
    near: float = -1.0,
    far: float = 1.0,
) -> np.ndarray:
    """
    Matriz ortográfica.

    Si llamas:
        ortho(0, width, height, 0)

    entonces trabajas con coordenadas tipo UI:
    - origen arriba-izquierda
    - X hacia la derecha
    - Y hacia abajo
    """
    mat = np.identity(4, dtype=np.float32)
    mat[0, 0] = 2.0 / (right - left)
    mat[1, 1] = 2.0 / (top - bottom)
    mat[2, 2] = -2.0 / (far - near)
    mat[3, 0] = -(right + left) / (right - left)
    mat[3, 1] = -(top + bottom) / (top - bottom)
    mat[3, 2] = -(far + near) / (far - near)
    return mat


def compile_shader(source: str, shader_type: int) -> int:
    shader = glCreateShader(shader_type)
    if not shader:
        raise RuntimeError(
            "No se pudo crear el shader. Verifica que exista un contexto OpenGL activo."
        )

    glShaderSource(shader, source)
    glCompileShader(shader)

    success = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not success:
        error = glGetShaderInfoLog(shader).decode("utf-8", errors="replace")
        glDeleteShader(shader)
        raise RuntimeError(f"Error compilando shader:\n{error}")

    return shader


def create_program(vertex_src: str, fragment_src: str) -> int:
    vertex_shader = compile_shader(vertex_src, GL_VERTEX_SHADER)
    fragment_shader = compile_shader(fragment_src, GL_FRAGMENT_SHADER)

    program = glCreateProgram()
    if not program:
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        raise RuntimeError("No se pudo crear el programa OpenGL.")

    glAttachShader(program, vertex_shader)
    glAttachShader(program, fragment_shader)
    glLinkProgram(program)

    success = glGetProgramiv(program, GL_LINK_STATUS)
    if not success:
        error = glGetProgramInfoLog(program).decode("utf-8", errors="replace")
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        glDeleteProgram(program)
        raise RuntimeError(f"Error enlazando programa:\n{error}")

    glDeleteShader(vertex_shader)
    glDeleteShader(fragment_shader)
    return program


@dataclass
class Character:
    texture_id: int
    size: Tuple[int, int]
    bearing: Tuple[int, int]
    advance: int


class TextRenderer:
    """
    Renderer de texto reutilizable para OpenGL 3.3.

    Importante:
    - Se puede crear la instancia en cualquier momento.
    - init_gl() debe llamarse solo cuando ya existe un contexto OpenGL activo.
    """

    def __init__(self, font_path: str, font_size: int, width: int, height: int) -> None:
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

        self._initialized = False

    def init_gl(self) -> None:
        if self._initialized:
            return

        self.program = create_program(VERTEX_SHADER_SOURCE, FRAGMENT_SHADER_SOURCE)

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
        self._load_font(self.font_path, self.font_size)

        self._initialized = True

    def update_projection(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))

        if self.program is None:
            return

        projection = ortho(0.0, float(self.width), float(self.height), 0.0)

        glUseProgram(self.program)
        glUniformMatrix4fv(self.proj_loc, 1, GL_FALSE, projection)

    def _load_font(self, font_path: str, font_size: int) -> None:
        face = freetype.Face(font_path)
        face.set_pixel_sizes(0, font_size)

        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)

        for char_code in range(32, 128):
            ch = chr(char_code)
            face.load_char(ch, freetype.FT_LOAD_RENDER)
            bitmap = face.glyph.bitmap

            tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, tex)

            width = int(bitmap.width)
            rows = int(bitmap.rows)
            buffer = bitmap.buffer

            glTexImage2D(
                GL_TEXTURE_2D,
                0,
                GL_RED,
                width,
                rows,
                0,
                GL_RED,
                GL_UNSIGNED_BYTE,
                buffer,
            )

            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            self.characters[ch] = Character(
                texture_id=tex,
                size=(width, rows),
                bearing=(int(face.glyph.bitmap_left), int(face.glyph.bitmap_top)),
                advance=int(face.glyph.advance.x),
            )

        glBindTexture(GL_TEXTURE_2D, 0)

    def render_text(
        self,
        text: str,
        x: float,
        y: float,
        scale: float = 1.0,
        color: Tuple[float, float, float] | Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        if not self._initialized:
            raise RuntimeError(
                "TextRenderer no está inicializado. Llama a init_gl() después de crear el contexto OpenGL."
            )

        if self.program is None or self.vao is None or self.vbo is None:
            return

        if len(color) == 3:
            r, g, b = color
            a = 1.0
        else:
            r, g, b, a = color

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glUseProgram(self.program)
        glUniform4f(self.text_color_loc, float(r), float(g), float(b), float(a))
        glUniform1i(self.text_sampler_loc, 0)

        glActiveTexture(GL_TEXTURE0)
        glBindVertexArray(self.vao)

        pen_x = float(x)
        pen_y = float(y)

        for ch in text:
            c = self.characters.get(ch)
            if c is None:
                continue

            xpos = pen_x + c.bearing[0] * scale
            ypos = pen_y - c.bearing[1] * scale

            w = c.size[0] * scale
            h = c.size[1] * scale

            vertices = np.array(
                [
                    [xpos,     ypos,     0.0, 0.0],
                    [xpos,     ypos + h, 0.0, 1.0],
                    [xpos + w, ypos + h, 1.0, 1.0],

                    [xpos,     ypos,     0.0, 0.0],
                    [xpos + w, ypos + h, 1.0, 1.0],
                    [xpos + w, ypos,     1.0, 0.0],
                ],
                dtype=np.float32,
            )

            glBindTexture(GL_TEXTURE_2D, c.texture_id)
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferSubData(GL_ARRAY_BUFFER, 0, vertices.nbytes, vertices)
            glDrawArrays(GL_TRIANGLES, 0, 6)

            pen_x += (c.advance >> 6) * scale

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)

    def measure_text(self, text: str, scale: float = 1.0) -> Tuple[float, float]:
        width = 0.0
        max_top = 0.0
        max_bottom = 0.0

        for ch in text:
            c = self.characters.get(ch)
            if c is None:
                continue

            width += (c.advance >> 6) * scale
            max_top = max(max_top, c.bearing[1] * scale)
            max_bottom = max(max_bottom, (c.size[1] - c.bearing[1]) * scale)

        height = max_top + max_bottom
        return width, height

    def shutdown(self) -> None:
        for c in self.characters.values():
            if c.texture_id:
                glDeleteTextures(int(c.texture_id))

        self.characters.clear()

        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
            self.vbo = None

        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            self.vao = None

        if self.program:
            glDeleteProgram(self.program)
            self.program = None

        self._initialized = False