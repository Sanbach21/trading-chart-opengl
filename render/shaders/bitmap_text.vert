#version 330 core
layout (location = 0) in vec4 aVertex; // x,y,u,v

uniform vec2 uResolution;
out vec2 vUV;

void main()
{
    vec2 pos = aVertex.xy;

    // pixel -> NDC (y_down)
    vec2 ndc = vec2(
        (pos.x / uResolution.x) * 2.0 - 1.0,
        1.0 - (pos.y / uResolution.y) * 2.0
    );

    gl_Position = vec4(ndc, 0.0, 1.0);
    vUV = aVertex.zw;
}