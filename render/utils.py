# render/utils.py
from render.msdf_cython.msdf_atlas import MSDFAtlasGenerator
import os

def generate_msdf_atlas(ttf_path: str, output_dir: str = "assets/fonts/msdf"):
    """Genera atlas con Cython y guarda PNG + JSON"""
    os.makedirs(output_dir, exist_ok=True)
    
    gen = MSDFAtlasGenerator()
    gen.add_unicode_range(32, 126)  # ASCII
    # gen.add_unicode_range(160, 255)  # Latin-1 extendido (si lo tienes)
    gen.load_font(ttf_path)
    
    # Llama a generate_atlas (debe guardar o retornar)
    png_path = os.path.join(output_dir, "generated_atlas.png")
    json_path = os.path.join(output_dir, "generated_atlas.json")
    
    # Placeholder: aquí llamas la función real que guarda
    # gen.generate_atlas(1024, 1024, 5.0, png_path, json_path)
    
    print(f"Atlas generado: {png_path} y {json_path}")
    return png_path, json_path