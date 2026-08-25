#version 330 core

// Background gradient fragment shader — vertical gradient from dark to slightly lighter

in vec2 vUV;

uniform vec3 uColorTop;
uniform vec3 uColorBottom;

out vec4 FragColor;

void main() {
    // Smooth vertical gradient
    vec3 color = mix(uColorBottom, uColorTop, vUV.y);

    // Slight vignette from center
    vec2 center = vUV - 0.5;
    float vignette = 1.0 - dot(center, center) * 0.3;
    color *= vignette;

    FragColor = vec4(color, 1.0);
}
