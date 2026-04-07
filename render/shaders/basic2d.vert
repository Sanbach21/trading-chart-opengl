#version 330 core
layout (location = 0) in vec2 aPosPx;
layout (location = 1) in vec4 aColor;

out vec4 vColor;           // ← Salida del color hacia el fragment shader

uniform vec2 uResolution;  // (width, height) en píxeles

void main() {
    // Convertir coordenadas de píxeles a NDC (Normalized Device Coordinates)
    float x = (aPosPx.x / uResolution.x) * 2.0 - 1.0;
    float y = 1.0 - (aPosPx.y / uResolution.y) * 2.0;   // Sistema Y-down (como en pantallas)

    gl_Position = vec4(x, y, 0.0, 1.0);
    vColor = aColor;           // ← Aquí se pasa el color (esto era lo que faltaba)
}