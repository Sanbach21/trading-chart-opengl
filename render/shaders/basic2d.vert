#version 330 core
layout (location = 0) in vec2 aPosPx;
layout (location = 1) in vec4 aColor;

out vec4 vColor;

uniform vec2 uResolution; // (width, height) en pixeles

void main() {
    // Convertir de pixeles a NDC:
    // x_ndc = (x / w) * 2 - 1
    // y_ndc = 1 - (y / h) * 2   (si usamos origen arriba)
    float x = (aPosPx.x / uResolution.x) * 2.0 - 1.0;
    float y = 1.0 - (aPosPx.y / uResolution.y) * 2.0;

    gl_Position = vec4(x, y, 0.0, 1.0);
    vColor = aColor;
}
