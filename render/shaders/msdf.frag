#version 330 core

in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uTex;
uniform vec4 uColor;
uniform float uPxRange;

float median(float r, float g, float b) {
    return max(min(r, g), min(max(r, g), b));
}

void main() {
    vec3 s = texture(uTex, vUV).rgb;

    // signed distance centrada en 0
    float sd = median(s.r, s.g, s.b) - 0.5;

    // distancia "en pixeles" del campo
    float distPx = uPxRange * sd;

    // ✅ ancho del borde basado en derivadas del sd (más estable)
    float w = uPxRange * fwidth(sd);

    // ✅ clamp mínimo para tamaños pequeños
    w = max(w, 0.85);     // prueba 0.75..1.25

    float alpha = smoothstep(-w, w, distPx);

    FragColor = vec4(uColor.rgb, uColor.a * alpha);
}