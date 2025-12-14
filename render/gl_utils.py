"""Utilidades OpenGL (shaders, buffers).

Separado para mantener renderer.py limpio.
"""
from __future__ import annotations

from OpenGL.GL import (
    GL_COMPILE_STATUS, GL_LINK_STATUS,
    glCreateShader, glShaderSource, glCompileShader, glGetShaderiv, glGetShaderInfoLog,
    glCreateProgram, glAttachShader, glLinkProgram, glGetProgramiv, glGetProgramInfoLog,
    glDeleteShader,
)


class ShaderCompilationError(RuntimeError):
    pass


def compile_shader(shader_type: int, source: str) -> int:
    shader = glCreateShader(shader_type)
    glShaderSource(shader, source)
    glCompileShader(shader)

    ok = glGetShaderiv(shader, GL_COMPILE_STATUS)
    if not ok:
        info = glGetShaderInfoLog(shader).decode("utf-8", errors="replace")
        raise ShaderCompilationError(info)
    return shader


def link_program(vertex_shader: int, fragment_shader: int) -> int:
    program = glCreateProgram()
    glAttachShader(program, vertex_shader)
    glAttachShader(program, fragment_shader)
    glLinkProgram(program)

    ok = glGetProgramiv(program, GL_LINK_STATUS)
    if not ok:
        info = glGetProgramInfoLog(program).decode("utf-8", errors="replace")
        raise ShaderCompilationError(info)

    # shaders ya no se necesitan luego de link
    glDeleteShader(vertex_shader)
    glDeleteShader(fragment_shader)
    return program
