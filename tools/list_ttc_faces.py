import freetype

path = r"C:\Users\ozzyj\OneDrive\Escritorio\Programacion\libreria_grafica_openGL\times.ttf"

face0 = freetype.Face(path, index=0)

print("num_faces:", face0.num_faces)
print("face 0 family:", face0.family_name, "style:", face0.style_name)

for i in range(face0.num_faces):
    f = freetype.Face(path, index=i)
    print(i, "| family:", f.family_name, "| style:", f.style_name)

    