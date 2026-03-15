#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform vec4  uColor;
uniform vec2  uGlyphPx;
uniform float uAAPx;
uniform float uStrokePx;

const int MAX_CURVES = 64;

uniform vec4 uCurvesA[MAX_CURVES];
uniform vec4 uCurvesB[MAX_CURVES];
uniform int  uCurveCount;

vec2 quad_bezier(vec2 p0, vec2 p1, vec2 p2, float t) {
    float u = 1.0 - t;
    return (u*u)*p0 + (2.0*u*t)*p1 + (t*t)*p2;
}

float dist_to_segment(vec2 p, vec2 a, vec2 b) {
    vec2 ab = b - a;
    float ab2 = dot(ab, ab);
    if (ab2 < 1e-8) return length(p - a);
    float t = clamp(dot(p - a, ab) / ab2, 0.0, 1.0);
    vec2 q = a + t * ab;
    return length(p - q);
}

void main() {
    vec2 p = vUV * uGlyphPx;

    float minD = 1e9;
    bool inside = false;

    const int SUBDIV = 16;

    for (int i = 0; i < uCurveCount; i++) {
        vec4 A = uCurvesA[i];
        vec4 B = uCurvesB[i];

        vec2 p0 = A.xy;
        vec2 p1 = A.zw;
        vec2 p2 = B.xy;

        vec2 prev = quad_bezier(p0, p1, p2, 0.0);

        for (int s = 1; s <= SUBDIV; s++) {
            float t = float(s) / float(SUBDIV);
            vec2 cur = quad_bezier(p0, p1, p2, t);

            minD = min(minD, dist_to_segment(p, prev, cur));

            float y0 = prev.y;
            float y1 = cur.y;
            bool cond = ((y0 > p.y) != (y1 > p.y));
            if (cond) {
                float xint = prev.x + (p.y - y0) * (cur.x - prev.x) / (y1 - y0);
                if (xint < p.x) inside = !inside;
            }

            prev = cur;
        }
    }

    float aa = max(0.75, uAAPx);

    // distancia firmada aproximada
    float signedDist = inside ? minD : -minD;

    // >0 engrosa, <0 adelgaza
    float alpha = smoothstep(-aa, aa, signedDist + uStrokePx);

    if (alpha <= 0.001) discard;
    FragColor = vec4(uColor.rgb, uColor.a * alpha);
}