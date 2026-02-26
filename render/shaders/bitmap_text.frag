#version 330 core
in vec2 vUV;
out vec4 FragColor;

uniform samplerBuffer uCurves;   // TBO con floats (R32F)
uniform int uCurveCount;

uniform vec2 uGlyphSizePx;       // (bbox_w, bbox_h)
uniform float uSmoothPx;         // borde suave en px
uniform vec4 uColor;

float fetchf(int idx){
    return texelFetch(uCurves, idx).r;
}

void fetchBezier(int i, out vec2 p0, out vec2 p1, out vec2 p2){
    int base = i * 6;
    p0 = vec2(fetchf(base+0), fetchf(base+1));
    p1 = vec2(fetchf(base+2), fetchf(base+3));
    p2 = vec2(fetchf(base+4), fetchf(base+5));
}

vec2 bezier(vec2 p0, vec2 p1, vec2 p2, float t){
    vec2 a = mix(p0, p1, t);
    vec2 b = mix(p1, p2, t);
    return mix(a, b, t);
}

float distToSegment(vec2 p, vec2 a, vec2 b){
    vec2 ab = b - a;
    float t = clamp(dot(p-a, ab) / dot(ab, ab), 0.0, 1.0);
    vec2 q = a + t * ab;
    return length(p - q);
}

void main(){
    // p en coords locales del glyph en px (0..bbox)
    vec2 p = vUV * uGlyphSizePx;

    // 1) inside/outside por ray casting (paridad)
    bool inside = false;

    // 2) distancia mínima al contorno (aprox: sampleamos cada curva)
    float minD = 1e20;

    for(int i=0; i<uCurveCount; i++){
        vec2 p0, p1, p2;
        fetchBezier(i, p0, p1, p2);

        // IMPORTANTE:
        // Tus puntos vienen en "px del glyph" pero pueden estar desplazados.
        // Si en CPU ya los ajustas a bbox (0..w, 0..h), esto funciona directo.

        // sampleo simple (refinamos después)
        vec2 prev = p0;
        const int STEPS = 16;
        for(int s=1; s<=STEPS; s++){
            float t = float(s) / float(STEPS);
            vec2 cur = bezier(p0,p1,p2,t);

            // distancia al borde
            minD = min(minD, distToSegment(p, prev, cur));

            // ray cast horizontal hacia +X
            // contamos cruces del segmento con la línea y = p.y
            // y si cruza a la derecha de p.x, togglear
            float y0 = prev.y, y1 = cur.y;
            bool cond = ( (y0 > p.y) != (y1 > p.y) );
            if(cond){
                float xint = prev.x + (p.y - y0) * (cur.x - prev.x) / (y1 - y0);
                if(xint > p.x) inside = !inside;
            }

            prev = cur;
        }
    }

    // alpha con borde suave
    float a = inside ? 1.0 : 0.0;

    // suavizado alrededor del borde
    float edge = smoothstep(uSmoothPx, 0.0, minD); // 1 en el borde, 0 lejos
    if(inside) a = max(a, edge);        // dentro: mantiene sólido + suaviza borde
    else       a = max(a, edge * 0.9);  // fuera: solo borde suave (opcional)

    FragColor = vec4(uColor.rgb, uColor.a * a);
}