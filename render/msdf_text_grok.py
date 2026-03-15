# render/msdf_text_grok.py
from OpenGL.GL import *
import numpy as np
from PIL import Image
import json
import glfw

class MSDFTextRenderer:
    def __init__(self, atlas_png_path: str, atlas_json_path: str, px_range: float = 5.0):
        """
        Renderizador MSDF con soporte para atlas generado con -allglyphs.
        Mapeo aproximado index ≈ unicode (funciona bien en Arial para Latin-1).
        """
        self.glyphs = {}
        self.atlas_width = 0
        self.atlas_height = 0
        self.px_range = px_range

        # Cargar JSON
        with open(atlas_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.atlas_width = data['atlas']['width']
        self.atlas_height = data['atlas']['height']

        glyphs_list = data.get('glyphs', [])

        # Diccionario index → glyph
        index_to_glyph = {g['index']: g for g in glyphs_list if 'index' in g}

        # Mapeo aproximado unicode → index
        char_to_index = {chr(cp): cp for cp in range(0, 256)}

        loaded = 0
        for char, idx in char_to_index.items():
            glyph_data = index_to_glyph.get(idx)
            if glyph_data and 'planeBounds' in glyph_data and 'atlasBounds' in glyph_data:
                self.glyphs[char] = {
                    'advance': glyph_data['advance'],
                    'plane': glyph_data['planeBounds'],
                    'atlas': glyph_data['atlasBounds']
                }
                loaded += 1

        print(f"[MSDF] Cargados {loaded} glyphs visibles (aprox. Latin-1). "
              f"'A' (65) existe: {'A' in self.glyphs} | "
              f"'á' (225) existe: {'á' in self.glyphs} | "
              f"Total glyphs en atlas: {len(glyphs_list)}")

        # Textura
        img = Image.open(atlas_png_path).convert('RGB')
        img_data = np.asarray(img, dtype=np.uint8)

        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, img.width, img.height, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, img_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glBindTexture(GL_TEXTURE_2D, 0)

        # Shaders
        self.program = self._compile_shaders()

        # VAO y VBO (creados una vez)
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 4 * 4, None)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _compile_shaders(self):
        vs_src = """#version 330 core
        layout(location = 0) in vec4 vertex;
        uniform mat4 projection;
        out vec2 vTexCoord;
        void main() {
            gl_Position = projection * vec4(vertex.xy, 0.0, 1.0);
            vTexCoord = vertex.zw;
        }"""

        fs_src = """#version 330 core
        in vec2 vTexCoord;
        out vec4 FragColor;
        uniform sampler2D tex;
        uniform vec3 color;
        uniform float pxRange;

        float median(float r, float g, float b) {
            return max(min(r, g), min(max(r, g), b));
        }

        void main() {
            vec3 msd = texture(tex, vTexCoord).rgb;
            float sd = median(msd.r, msd.g, msd.b) - 0.5;
            float d = fwidth(sd) * pxRange;
            float opacity = smoothstep(-d, d, sd);
            FragColor = vec4(color, opacity);
        }"""

        vs = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vs, vs_src)
        glCompileShader(vs)
        if not glGetShaderiv(vs, GL_COMPILE_STATUS):
            print("Vertex Shader error:", glGetShaderInfoLog(vs).decode().strip())
            raise RuntimeError("Vertex shader failed")

        fs = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs, fs_src)
        glCompileShader(fs)
        if not glGetShaderiv(fs, GL_COMPILE_STATUS):
            print("Fragment Shader error:", glGetShaderInfoLog(fs).decode().strip())
            raise RuntimeError("Fragment shader failed")

        prog = glCreateProgram()
        glAttachShader(prog, vs)
        glAttachShader(prog, fs)
        glLinkProgram(prog)
        if not glGetProgramiv(prog, GL_LINK_STATUS):
            print("Shader program link error:", glGetProgramInfoLog(prog).decode().strip())
            raise RuntimeError("Shader link failed")

        glDeleteShader(vs)
        glDeleteShader(fs)
        return prog

    def render(self, text: str, x: float, y: float, size_px: float,
               color: tuple[float, float, float] = (1.0, 1.0, 1.0),
               projection_matrix=None):
        glUseProgram(self.program)
        glUniform3f(glGetUniformLocation(self.program, "color"), *color)
        glUniform1f(glGetUniformLocation(self.program, "pxRange"), self.px_range)

        if projection_matrix is None:
            w, h = glfw.get_window_size(glfw.get_current_context())
            projection_matrix = np.array([
                [2.0 / w, 0.0, 0.0, 0.0],
                [0.0, 2.0 / h, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [-1.0, -1.0, 0.0, 1.0]
            ], dtype=np.float32)

        glUniformMatrix4fv(glGetUniformLocation(self.program, "projection"), 1, GL_FALSE, projection_matrix)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)

        vertices = []
        xpos = x

        for char in text:
            if ord(char) < 32 or ord(char) > 126 or char not in self.glyphs:
                xpos += size_px * 0.6  # fallback
                continue

            g = self.glyphs[char]
            p = g['plane']
            a = g['atlas']

            glyph_w = (p['right'] - p['left']) * size_px
            glyph_h = (p['top'] - p['bottom']) * size_px

            uv_l = a['left'] / self.atlas_width
            uv_b = a['bottom'] / self.atlas_height
            uv_r = a['right'] / self.atlas_width
            uv_t = a['top'] / self.atlas_height

            quad = [
                xpos,           y + p['bottom'] * size_px, uv_l, uv_b,
                xpos + glyph_w, y + p['bottom'] * size_px, uv_r, uv_b,
                xpos,           y + p['top']    * size_px, uv_l, uv_t,

                xpos + glyph_w, y + p['bottom'] * size_px, uv_r, uv_b,
                xpos + glyph_w, y + p['top']    * size_px, uv_r, uv_t,
                xpos,           y + p['top']    * size_px, uv_l, uv_t,
            ]
            vertices.extend(quad)

            xpos += g['advance'] * size_px

        if vertices:
            data = np.array(vertices, dtype=np.float32)
            glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
            glDrawArrays(GL_TRIANGLES, 0, len(vertices) // 4)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_BLEND)
        glUseProgram(0)