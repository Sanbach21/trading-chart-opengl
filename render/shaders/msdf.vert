#version 330 core

layout (location = 0) in vec2 aPosPx;
layout (location = 1) in vec2 aUV;

uniform vec2 uResolution;

out vec2 vUV;

void main()
{
    vec2 ndc = vec2(
        (aPosPx.x / uResolution.x) * 2.0 - 1.0,
        1.0 - (aPosPx.y / uResolution.y) * 2.0
    );

    gl_Position = vec4(ndc, 0.0, 1.0);
    vUV = aUV;
}
