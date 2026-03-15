# render/msdf_cython/msdf_atlas.pyx
# cython: language_level=3

from libc.stdlib cimport malloc, free
from libc.string cimport memcpy
from cython.operator cimport dereference as deref

cdef extern from "ft2build.h":
    pass

cdef extern from "freetype/freetype.h":
    ctypedef struct FT_FaceRec
    ctypedef FT_FaceRec* FT_Face

    int FT_Init_FreeType(void** library)
    int FT_New_Face(void* library, const char* filepathname, long index, FT_Face* aface)
    int FT_Done_Face(FT_Face face)
    int FT_Done_FreeType(void* library)

cdef extern from "msdfgen.h" namespace msdfgen:
    cdef cppclass Shape
    cdef cppclass Bitmap
    cdef void generateMTSDF(Bitmap &output, const Shape &shape, double range, double scale, double tx, double ty, double edgeColoringAngleThreshold)
    cdef Shape* adoptFreetypeFont(FT_Face face)

cdef extern from "msdf-atlas-gen/ext/charset.h" namespace msdf_atlas:
    cdef cppclass Charset:
        Charset()
        void add(unsigned unicode)

cdef extern from "msdf-atlas-gen/msdf-atlas-gen.h" namespace msdf_atlas:
    cdef cppclass FontGeometry:
        FontGeometry()
        int loadGlyphs(const Charset &charset, double angleThreshold, double edgeThreshold, double edgeColoringDistance)

    cdef cppclass AtlasGeometry:
        AtlasGeometry()
        int packAndRender(GlyphGeometry *glyphs, int glyphCount, int width, int height, double pxRange, double scale, double tx, double ty)

cdef class MSDFAtlasGenerator:
    cdef FontGeometry* font
    cdef Charset charset
    cdef void* freetype_library
    cdef FT_Face face

    def __cinit__(self):
        self.font = new FontGeometry()
        self.charset = Charset()
        FT_Init_FreeType(&self.freetype_library)

    def load_font(self, ttf_path: str):
        cdef int error = FT_New_Face(self.freetype_library, ttf_path.encode(), 0, &self.face)
        if error:
            raise RuntimeError("Failed to load font")

        # Adopt FreeType face into msdfgen (simplificado)
        # En producción: usar msdfgen::adoptFreetypeFont(self.face)

    def add_unicode_range(self, start: int, end: int):
        for cp in range(start, end + 1):
            self.charset.add(cp)

    def generate_atlas(self, width: int, height: int, px_range: float):
        # Placeholder: aquí iría la generación real
        # Cargar glyphs con loadGlyphs, packAndRender, guardar PNG/JSON
        print("Generando atlas...", width, height, px_range)
        return "generated_atlas.png", "generated_atlas.json"  # placeholder paths

    def __dealloc__(self):
        if self.face:
            FT_Done_Face(self.face)
        if self.freetype_library:
            FT_Done_FreeType(self.freetype_library)
        del self.font