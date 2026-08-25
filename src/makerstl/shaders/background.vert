#version 330 core

// Fullscreen quad vertex shader for background gradient

layout(location = 0) in vec2 aPos;

out vec2 vUV;

void main() {
    vUV = aPos * 0.5 + 0.5;
    gl_Position = vec4(aPos, 0.999, 1.0); // behind everything
}
