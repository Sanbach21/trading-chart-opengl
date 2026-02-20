#version 330 core

in vec2 vUV;
out vec4 FragColor;

uniform sampler2D uTex;
uniform vec4 uColor;
uniform float uEdge;
uniform float uSmoothing;

float median(float r, float g, float b) {
    return max(min(r,g), min(max(r,g), b));
}

void main()
{
    vec3 msd = texture(uTex, vUV).rgb;
    float sd = median(msd.r, msd.g, msd.b);

    float alpha = smoothstep(uEdge - uSmoothing, uEdge + uSmoothing, sd);
    FragColor = vec4(uColor.rgb, uColor.a * alpha);
}
