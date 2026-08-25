#version 330 core

// Mesh fragment shader — PBR multi-light + ACES tone mapping

in vec3 vWorldPos;
in vec3 vNormal;
in vec3 vViewDir;

uniform vec3 uBaseColor;
uniform float uRoughness;
uniform float uMetalness;

// Light structure
struct Light {
    vec3 direction;
    vec3 color;
    float intensity;
};

#define MAX_LIGHTS 4
uniform Light uLights[MAX_LIGHTS];
uniform int uNumLights;
uniform vec3 uAmbientColor;
uniform float uAmbientIntensity;

// ACES tone mapping (Narkowicz 2015)
vec3 acesToneMapping(vec3 x) {
    float a = 2.51;
    float b = 0.03;
    float c = 2.43;
    float d = 0.59;
    float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// Fresnel-Schlick approximation
vec3 fresnelSchlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
}

// GGX Distribution
float distributionGGX(vec3 N, vec3 H, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH = max(dot(N, H), 0.0);
    float NdotH2 = NdotH * NdotH;

    float denom = NdotH2 * (a2 - 1.0) + 1.0;
    return a2 / (3.14159265 * denom * denom);
}

// Geometry function (Schlick-GGX)
float geometrySchlickGGX(float NdotV, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) / 8.0;
    return NdotV / (NdotV * (1.0 - k) + k);
}

float geometrySmith(vec3 N, vec3 V, vec3 L, float roughness) {
    float NdotV = max(dot(N, V), 0.0);
    float NdotL = max(dot(N, L), 0.0);
    return geometrySchlickGGX(NdotV, roughness) * geometrySchlickGGX(NdotL, roughness);
}

out vec4 FragColor;

void main() {
    vec3 N = normalize(vNormal);
    vec3 V = normalize(vViewDir);

    // Base reflectivity
    vec3 F0 = mix(vec3(0.04), uBaseColor, uMetalness);

    // Accumulate lighting
    vec3 Lo = vec3(0.0);

    for (int i = 0; i < uNumLights && i < MAX_LIGHTS; i++) {
        vec3 L = normalize(-uLights[i].direction);
        vec3 H = normalize(V + L);

        // Radiance
        vec3 radiance = uLights[i].color * uLights[i].intensity;

        // Cook-Torrance BRDF
        float NDF = distributionGGX(N, H, uRoughness);
        float G = geometrySmith(N, V, L, uRoughness);
        vec3 F = fresnelSchlick(max(dot(H, V), 0.0), F0);

        vec3 numerator = NDF * G * F;
        float denominator = 4.0 * max(dot(N, V), 0.0) * max(dot(N, L), 0.0) + 0.0001;
        vec3 specular = numerator / denominator;

        // Energy conservation
        vec3 kS = F;
        vec3 kD = vec3(1.0) - kS;
        kD *= 1.0 - uMetalness;

        float NdotL = max(dot(N, L), 0.0);

        Lo += (kD * uBaseColor / 3.14159265 + specular) * radiance * NdotL;
    }

    // Ambient
    vec3 ambient = uAmbientColor * uAmbientIntensity * uBaseColor;

    vec3 color = ambient + Lo;

    // ACES tone mapping
    color = acesToneMapping(color * 1.1);

    // Gamma correction (sRGB)
    color = pow(color, vec3(1.0 / 2.2));

    FragColor = vec4(color, 1.0);
}
