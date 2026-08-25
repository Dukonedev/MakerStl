#version 330 core

// Mesh vertex shader — PBR-ready multi-light

layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;

uniform mat4 uModel;
uniform mat4 uView;
uniform mat4 uProjection;
uniform mat3 uNormalMatrix;

out vec3 vWorldPos;
out vec3 vNormal;
out vec3 vViewDir;

void main() {
    vec4 worldPos = uModel * vec4(aPos, 1.0);
    vWorldPos = worldPos.xyz;

    vNormal = normalize(uNormalMatrix * aNormal);

    // view direction (camera is at origin in view space, but we compute in world space)
    // We pass inverse-view position via uniform for proper view dir
    vec4 viewPos = uView * worldPos;
    vViewDir = -viewPos.xyz; // direction from fragment toward camera in view space

    gl_Position = uProjection * viewPos;
}
