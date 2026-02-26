#version 330 core
layout(location=0) in vec2 aPosPx;   // posición en px
layout(location=1) in vec2 aUV;      // 0..1

uniform vec2 uResolution;

out vec2 vUV;

vec2 px_to_ndc(vec2 p){
    vec2 ndc = (p / uResolution) * 2.0 - 1.0;
    return vec2(ndc.x, -ndc.y); // flip Y (si tu motor usa Y hacia abajo)
}

void main(){
    vUV = aUV;
    gl_Position = vec4(px_to_ndc(aPosPx), 0.0, 1.0);
}