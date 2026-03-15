# setup.py
from setuptools import setup, Extension
from Cython.Build import cythonize
import os

# Ajusta estas rutas según donde compilaste las libs
MSDF_ATLAS_GEN_DIR = r"..\..\vendor\msdf-atlas-gen"
MSDF_GEN_DIR = r"..\..\vendor\msdfgen"

ext_modules = [
    Extension(
        "msdf_atlas",
        sources=["msdf_atlas.pyx"],
        include_dirs=[
            os.path.join(MSDF_ATLAS_GEN_DIR, "include"),
            os.path.join(MSDF_GEN_DIR, "include"),
        ],
        library_dirs=[
            os.path.join(MSDF_ATLAS_GEN_DIR, "lib"),  # o "build" si compilaste allí
            os.path.join(MSDF_GEN_DIR, "lib"),
        ],
        libraries=["msdf-atlas-gen", "msdfgen"],
        language="c++",
        extra_compile_args=["/std:c++17", "/EHsc"],  # /EHsc para excepciones
        extra_link_args=["/LIBPATH:" + os.path.join(MSDF_ATLAS_GEN_DIR, "lib")],
    )
]

setup(
    name="msdf_atlas",
    ext_modules=cythonize(ext_modules, language_level=3),
)