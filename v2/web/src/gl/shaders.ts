// GLSL for the compositor (v2/docs/specs/compositor.md). The light pass is the viewer half of layer 9: the same
// march as v2/layers/light.py shadow_ref, step for step, so the checks measure what is seen.

export const CAM_GLSL = `
const float S30 = 0.5;
const float C30 = 0.8660254037844386;
const float R2 = 0.7071067811865476;
uniform vec2 uFrame;      // sx0, sy1 (screen metres)
uniform float uMpp;
uniform vec2 uDepthRange; // D0, D1 (cm)
// local world (E, N relative to the camera origin, z) -> (map px x, map px y, depth m)
vec3 projectLocal(vec3 w) {
  float u = (w.x + w.y) * R2;
  float f = (w.y - w.x) * R2;
  float sy = f * S30 + w.z * C30;
  return vec3((u - uFrame.x) / uMpp, (uFrame.y - sy) / uMpp, f * C30 - w.z * S30);
}
float depth01(float dm) { return (dm * 100.0 - uDepthRange.x) / (uDepthRange.y - uDepthRange.x); }
`;

export const VIEW_GLSL = `
uniform vec4 uView;       // centre x, centre y (map px), scale (device px per map px), unused
uniform vec2 uSize;       // canvas size (device px)
vec2 mapToClip(vec2 m) {
  vec2 s = (m - uView.xy) * uView.z + uSize * 0.5;
  return vec2(s.x / uSize.x * 2.0 - 1.0, 1.0 - s.y / uSize.y * 2.0);
}
vec2 fragToMap(vec2 frag) {
  return uView.xy + (vec2(frag.x, uSize.y - frag.y) - uSize * 0.5) / uView.z;
}
`;

export const OCT_GLSL = `
vec3 octDecode(vec2 o) {
  o = o * 2.0 - 1.0;
  vec3 v = vec3(o, 1.0 - abs(o.x) - abs(o.y));
  float t = max(-v.z, 0.0);
  v.x += v.x >= 0.0 ? -t : t;
  v.y += v.y >= 0.0 ? -t : t;
  return normalize(v);
}
vec2 octEncode(vec3 n) {
  n /= (abs(n.x) + abs(n.y) + abs(n.z));
  vec2 o = n.z >= 0.0 ? n.xy : (1.0 - abs(n.yx)) * vec2(n.x >= 0.0 ? 1.0 : -1.0, n.y >= 0.0 ? 1.0 : -1.0);
  return o * 0.5 + 0.5;
}
`;

// ------------------------------------------------------------------------------------------------ tiles (G-pass)
export const TILE_VS = `#version 300 es
in vec2 aCorner;
uniform vec3 uTile;   // x0, y0 (map px), size (map px)
${VIEW_GLSL}
out vec2 vUV;
void main() {
  vUV = aCorner;
  gl_Position = vec4(mapToClip(uTile.xy + aCorner * uTile.z), 0.0, 1.0);
}`;

const TILE_FS_HEAD = `#version 300 es
precision highp float;
precision highp int;
in vec2 vUV;
uniform vec4 uSub;        // sub-rectangle of the texture (fallback to a coarser tile): offset, scale
uniform vec2 uDepthRangeT;
uniform vec2 uSyRef;      // the texture's depth reference: sy (m) of texel row 0's centre, and per row
const float SQ3 = 1.7320508075688772;
layout(location = 0) out vec4 oAlbedo;
layout(location = 1) out vec4 oNormal;
// depth in cm: stored relative to sqrt(3) * sy of the texel's row (v2/layers/common.py depth_ref)
float decodeDepth(vec4 g, float dmin, int row) {
  float code = floor(g.r * 255.0 + 0.5) + floor(g.g * 255.0 + 0.5) * 256.0;
  if (code > 65534.5) return -1.0;
  return code + dmin + SQ3 * 100.0 * (uSyRef.x + float(row) * uSyRef.y);
}
float frag01(float dcm) { return (dcm - uDepthRangeT.x) / (uDepthRangeT.y - uDepthRangeT.x); }
`;

/** Layers 3-7: colour, geometry and class of one tile, into the G-buffer at the layer's own depth. */
export const LAYER_FS = TILE_FS_HEAD + `
uniform sampler2D uC;
uniform sampler2D uG;
uniform sampler2D uK;
uniform float uDmin;
uniform float uLayer;
uniform float uHasK;
void main() {
  vec2 uv = uSub.xy + vUV * uSub.zw;
  ivec2 p = clamp(ivec2(floor(uv * 512.0)), ivec2(0), ivec2(511));
  vec4 g = texelFetch(uG, p, 0);
  float dcm = decodeDepth(g, uDmin, p.y);
  if (dcm < 0.0) discard;
  gl_FragDepth = frag01(dcm);
  float k = uHasK > 0.5 ? texelFetch(uK, p, 0).r : 0.0;
  oAlbedo = vec4(texture(uC, uv).rgb, uLayer / 255.0);
  oNormal = vec4(g.b, g.a, k, 0.0);
}`;

/** Layers 1 and 2 together: the ground's colour times the relief's (a multiply layer), or the relief's walls. */
export const GROUND_FS = TILE_FS_HEAD + `
uniform sampler2D uGC; uniform sampler2D uGG; uniform sampler2D uGK; uniform float uGDmin; uniform float uGOn;
uniform sampler2D uRC; uniform sampler2D uRG; uniform sampler2D uRK; uniform float uRDmin; uniform float uROn;
uniform vec3 uPaper;
void main() {
  vec2 uv = uSub.xy + vUV * uSub.zw;
  ivec2 p = clamp(ivec2(floor(uv * 512.0)), ivec2(0), ivec2(511));
  float gd = -1.0, rd = -1.0;
  vec4 gg = vec4(0.0), rg = vec4(0.0);
  if (uGOn > 0.5) { gg = texelFetch(uGG, p, 0); gd = decodeDepth(gg, uGDmin, p.y); }
  if (uROn > 0.5) { rg = texelFetch(uRG, p, 0); rd = decodeDepth(rg, uRDmin, p.y); }
  if (gd < 0.0 && rd < 0.0) discard;
  float rk = uROn > 0.5 ? floor(texelFetch(uRK, p, 0).r * 255.0 + 0.5) : 0.0;
  if (rd >= 0.0 && rk > 2.5 && (gd < 0.0 || rd <= gd)) {           // a wall face of the relief layer
    gl_FragDepth = frag01(rd);
    oAlbedo = vec4(texelFetch(uRC, p, 0).rgb, 2.0 / 255.0);
    oNormal = vec4(rg.b, rg.a, 0.0, 0.0);
    return;
  }
  vec3 base = gd >= 0.0 ? texture(uGC, uv).rgb : uPaper;
  if (rd >= 0.0 && rk > 0.5) base *= texture(uRC, uv).rgb;
  float d = gd >= 0.0 ? gd : rd;
  vec4 n = gd >= 0.0 ? gg : rg;
  gl_FragDepth = frag01(d);
  float k = gd >= 0.0 ? texelFetch(uGK, p, 0).r : 0.0;
  oAlbedo = vec4(base, (gd >= 0.0 ? 1.0 : 2.0) / 255.0);
  oNormal = vec4(n.b, n.a, k, 0.0);
}`;

// ------------------------------------------------------------------------------------------------ vehicles
export const VEH_VS = `#version 300 es
in vec3 aPos;           // unit cube corner (-0.5..0.5, -0.5..0.5, 0..1)
in vec3 aNrm;
in vec4 aInst;          // local E, N, z of the ground centre, heading (radians, from east, counter-clockwise)
in vec4 aSize;          // length, width, height, colour index
${CAM_GLSL}
${VIEW_GLSL}
uniform float uEps;
out vec3 vN;
flat out float vCol;
void main() {
  float c = cos(aInst.w), s = sin(aInst.w);
  vec3 l = vec3(aPos.x * aSize.x, aPos.y * aSize.y, aPos.z * aSize.z);
  vec3 w = vec3(aInst.x + l.x * c - l.y * s, aInst.y + l.x * s + l.y * c, aInst.z + l.z);
  vec3 m = projectLocal(w);
  gl_Position = vec4(mapToClip(m.xy), depth01(m.z - uEps) * 2.0 - 1.0, 1.0);
  vN = vec3(aNrm.x * c - aNrm.y * s, aNrm.x * s + aNrm.y * c, aNrm.z);
  vCol = aSize.w;
}`;

export const VEH_FS = `#version 300 es
precision highp float;
in vec3 vN;
flat in float vCol;
uniform vec3 uColours[8];
layout(location = 0) out vec4 oAlbedo;
layout(location = 1) out vec4 oNormal;
${OCT_GLSL}
void main() {
  int i = int(vCol + 0.5);
  vec3 c = uColours[i];
  if (vN.z > 0.5) c = c * 0.92 + 0.08;          // the roof a touch lighter (paint, not light)
  oAlbedo = vec4(c, 8.0 / 255.0);
  oNormal = vec4(octEncode(normalize(vN)), 0.0, 0.0);
}`;

// ------------------------------------------------------------------------------------------------ full screen
export const FULL_VS = `#version 300 es
in vec2 aCorner;
void main() { gl_Position = vec4(aCorner * 2.0 - 1.0, 0.0, 1.0); }`;

/** Layer 9 (light: sun shading, cast shadows from the height map, sky grade) and layer 11 (seasons, snow). */
export const LIGHT_FS = `#version 300 es
precision highp float;
precision highp int;
uniform sampler2D uAlbedo;
uniform sampler2D uNormal;
uniform highp sampler2D uDepth;
uniform sampler2D uHmA;
uniform sampler2D uHmB;
${CAM_GLSL}
${VIEW_GLSL}
${OCT_GLSL}
uniform vec2 uOrigin;          // camera origin (E, N)
uniform vec4 uHm;              // e0, n0 (local, relative to the camera origin), step, zbase
uniform ivec2 uHmSize;
uniform vec3 uHmUnits;         // building, tree, structure units (m)
uniform vec4 uMarch;           // t0, growth, steps, bias
uniform float uZTop;
uniform vec4 uSun;             // sun vector (E, N, up), elevation (deg)
uniform vec4 uSources;         // terrain, buildings, trees, structures cast shadows (1/0)
uniform vec4 uLightK;          // wrap, ambient, direct, shadow keep
uniform vec3 uSunTint;
uniform vec3 uAmbTint;
uniform vec3 uShadowTint;
uniform float uLightOn;
uniform vec3 uSeasonTree;
uniform vec3 uSeasonGreen;
uniform float uSeasonSat;
uniform float uWinter;
uniform float uSnow;
uniform float uSnowCos;
uniform vec3 uPaper;
uniform vec3 uTrunk;
uniform int uDebug;            // 0 normal, 1 albedo, 2 layer, 3 shadow, 4 depth, 5 normal
out vec4 oColor;

float shadowAt(vec3 P) {
  if (uSun.w <= 0.0) return 1.0;
  vec2 h = normalize(uSun.xy);
  float tz = uSun.z / length(uSun.xy);
  float t = uMarch.x;
  int steps = int(uMarch.z);
  for (int k = 0; k < 256; k++) {
    if (k >= steps) break;
    vec2 q = P.xy + h * t;
    float zr = P.z + tz * t + uMarch.w;
    if (zr > uZTop) break;
    ivec2 c = ivec2(floor((q - uHm.xy) / uHm.z));
    if (c.x >= 0 && c.y >= 0 && c.x < uHmSize.x && c.y < uHmSize.y) {
      vec4 A = texelFetch(uHmA, c, 0);
      vec4 B = texelFetch(uHmB, c, 0);
      float T = uHm.w + (floor(A.r * 255.0 + 0.5) + floor(A.g * 255.0 + 0.5) * 256.0) / 100.0;
      if (uSources.x > 0.5 && T > zr) return 1.0;
      float bt = floor(A.b * 255.0 + 0.5) * uHmUnits.x;
      if (uSources.y > 0.5 && bt > 0.0 && T + bt > zr) return 1.0;
      float tt = floor(A.a * 255.0 + 0.5) * uHmUnits.y, tb = floor(B.r * 255.0 + 0.5) * uHmUnits.y;
      if (uSources.z > 0.5 && tt > 0.0 && T + tb < zr && T + tt > zr) return 1.0;
      float st = floor(B.g * 255.0 + 0.5) * uHmUnits.z, sb = floor(B.b * 255.0 + 0.5) * uHmUnits.z;
      if (uSources.w > 0.5 && st > 0.0 && T + sb < zr && T + st > zr) return 1.0;
    }
    t *= uMarch.y;
  }
  return 0.0;
}

bool covered(vec3 P) {          // something above this point (a crown, a deck, a roof): no snow under it
  ivec2 c = ivec2(floor((P.xy - uHm.xy) / uHm.z));
  if (c.x < 0 || c.y < 0 || c.x >= uHmSize.x || c.y >= uHmSize.y) return false;
  vec4 A = texelFetch(uHmA, c, 0);
  vec4 B = texelFetch(uHmB, c, 0);
  float T = uHm.w + (floor(A.r * 255.0 + 0.5) + floor(A.g * 255.0 + 0.5) * 256.0) / 100.0;
  float top = max(max(floor(A.b * 255.0 + 0.5) * uHmUnits.x, floor(A.a * 255.0 + 0.5) * uHmUnits.y),
                  floor(B.g * 255.0 + 0.5) * uHmUnits.z);
  return top > 0.0 && T + top > P.z + 1.0;
}

vec3 saturate3(vec3 c, float s) { float l = dot(c, vec3(0.2126, 0.7152, 0.0722)); return mix(vec3(l), c, s); }

void main() {
  ivec2 fc = ivec2(gl_FragCoord.xy);
  float d01 = texelFetch(uDepth, fc, 0).r;
  if (d01 >= 1.0) { oColor = vec4(uPaper, 1.0); return; }
  vec4 alb = texelFetch(uAlbedo, fc, 0);
  vec4 nk = texelFetch(uNormal, fc, 0);
  int layer = int(floor(alb.a * 255.0 + 0.5));
  int k = int(floor(nk.b * 255.0 + 0.5));
  vec3 n = octDecode(nk.rg);
  float dm = (uDepthRange.x + d01 * (uDepthRange.y - uDepthRange.x)) / 100.0;
  vec2 m = fragToMap(gl_FragCoord.xy);
  float u = uFrame.x + m.x * uMpp;
  float sy = uFrame.y - m.y * uMpp;
  float f = sy * S30 + dm * C30;
  float z = sy * C30 - dm * S30;
  vec3 P = vec3((u - f) * R2, (u + f) * R2, z);           // local E, N (relative to the camera origin), z
  vec3 c = alb.rgb;
  if (uDebug == 1) { oColor = vec4(c, 1.0); return; }
  if (uDebug == 2) { oColor = vec4(float(layer) / 8.0, float(k) / 16.0, 0.0, 1.0); return; }
  if (uDebug == 4) { oColor = vec4(vec3(fract(dm / 10.0)), 1.0); return; }
  if (uDebug == 5) { oColor = vec4(n * 0.5 + 0.5, 1.0); return; }
  // layer 11: seasons change only trees and green ground; snow on up-facing, uncovered surfaces
  bool crown = layer == 7 && k >= 1 && k <= 4;
  bool green = layer == 1 && k >= 6 && k <= 12;
  if (crown) {
    c = saturate3(c * uSeasonTree, uSeasonSat);
    if (uWinter > 0.5) c = mix(uTrunk, c, 0.3);
  } else if (green) {
    c = saturate3(c * uSeasonGreen, uSeasonSat);
  }
  c = clamp(c, 0.0, 1.0);
  if (uSnow > 0.5 && n.z > uSnowCos && layer != 8 && !covered(P)) c = mix(c, vec3(0.96, 0.97, 1.0), 0.85);
  float sh = 0.0;
  if (uLightOn > 0.5 || uDebug == 3) sh = shadowAt(P);
  if (uDebug == 3) { oColor = vec4(vec3(1.0 - sh), 1.0); return; }
  if (uLightOn < 0.5) { oColor = vec4(c, 1.0); return; }
  vec3 sv = uSun.xyz;
  float L = clamp((dot(n, sv) + uLightK.x) / (1.0 + uLightK.x), 0.0, 1.0);
  float up = clamp((uSun.w + 1.0) / 3.0, 0.0, 1.0);
  float direct = uLightK.z * L * (1.0 - sh) * up;
  vec3 amb = uLightK.y * uAmbTint * mix(vec3(1.0), uShadowTint, 0.45 * (1.0 - L * (1.0 - sh)) * up);
  vec3 lit = c * (amb + uSunTint * direct);
  oColor = vec4(lit, 1.0);
}`;

// ------------------------------------------------------------------------------------------------ night (layer 10)
export const WIN_VS = `#version 300 es
in vec2 aCorner;
in vec4 aA;              // x, y, z, ux
in vec4 aB;              // uy, height, building, code
${CAM_GLSL}
${VIEW_GLSL}
uniform float uEps;
uniform vec4 uLit;       // homes share, shops share, seed, hour
out vec2 vUV;
flat out float vKind;
float hash(float n) { return fract(sin(n * 12.9898 + uLit.z * 78.233) * 43758.5453); }
void main() {
  float id = float(gl_InstanceID);
  float code = aB.w;
  float shop = code >= 3.5 ? 1.0 : 0.0;
  float kind = mod(code, 4.0);
  float share = kind > 1.5 ? uLit.y : (kind > 0.5 ? uLit.x * 0.6 : uLit.x);
  // a building's windows are lit together by floor more often than not (a family's rooms)
  float floorKey = floor(aA.z / 3.0);
  float r = hash(id) * 0.6 + hash(aB.z * 31.0 + floorKey) * 0.4;
  if (r > share) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec3 w = vec3(aA.x + aA.w * aCorner.x, aA.y + aB.x * aCorner.x, aA.z + aB.y * aCorner.y);
  vec3 m = projectLocal(w);
  gl_Position = vec4(mapToClip(m.xy), depth01(m.z - uEps) * 2.0 - 1.0, 1.0);
  vUV = aCorner;
  vKind = kind + shop * 4.0;
}`;

export const WIN_FS = `#version 300 es
precision highp float;
in vec2 vUV;
flat in float vKind;
uniform vec3 uWarm;
uniform float uNight;
out vec4 oColor;
void main() {
  vec2 e = min(vUV, 1.0 - vUV);
  float frame = smoothstep(0.0, 0.12, min(e.x, e.y));
  vec3 c = uWarm * (0.75 + 0.25 * frame);
  if (mod(vKind, 4.0) > 1.5) c = mix(uWarm, vec3(1.0, 0.95, 0.85), 0.35);
  oColor = vec4(c * uNight, 1.0);
}`;

export const LAMP_VS = `#version 300 es
in vec2 aCorner;
in vec3 aP;
${CAM_GLSL}
${VIEW_GLSL}
uniform float uEps;
uniform float uRadius;    // device px
out vec2 vUV;
void main() {
  vec3 m = projectLocal(aP);
  vec2 clip = mapToClip(m.xy);
  vec2 off = (aCorner * 2.0 - 1.0) * uRadius / uSize * 2.0;
  gl_Position = vec4(clip + off, depth01(m.z - uEps) * 2.0 - 1.0, 1.0);
  vUV = aCorner * 2.0 - 1.0;
}`;

export const LAMP_FS = `#version 300 es
precision highp float;
in vec2 vUV;
uniform vec3 uWarm;
uniform float uNight;
out vec4 oColor;
void main() {
  float r = length(vUV);
  if (r > 1.0) discard;
  float a = exp(-r * r * 5.0) * 0.55 + smoothstep(0.12, 0.0, r) * 0.6;
  oColor = vec4(uWarm * a * uNight, 1.0);
}`;

// ------------------------------------------------------------------------------------------------ look (layer 14)
/** Grade (a projection: channels clamped, saturation capped, so applying it twice changes nothing) and ink where the
 * geometry breaks (depth steps, creases), never from colour. */
export const LOOK_FS = `#version 300 es
precision highp float;
uniform sampler2D uLit;
uniform sampler2D uNormal;
uniform highp sampler2D uDepth;
uniform sampler2D uAlbedo;
${CAM_GLSL}
${OCT_GLSL}
uniform vec4 uLook;        // sat max, lum min, lum max, ink depth (m)
uniform float uInkMin;     // the depth step one screen pixel can hold on steep ground (m)
uniform float uInkCos;
uniform vec3 uInk;
uniform float uLookOn;
uniform int uDebug;
out vec4 oColor;
vec3 grade(vec3 c) {
  c = clamp(c, uLook.y, uLook.z);
  float mx = max(c.r, max(c.g, c.b)), mn = min(c.r, min(c.g, c.b));
  float s = (mx - mn) / max(mx, 1e-6);
  if (s > uLook.x + 1e-4) c = mx - (mx - c) * (uLook.x / s);
  return c;
}
float dAt(ivec2 p) {
  float d01 = texelFetch(uDepth, p, 0).r;
  return d01 >= 1.0 ? 1e9 : (uDepthRange.x + d01 * (uDepthRange.y - uDepthRange.x)) / 100.0;
}
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy);
  vec3 c = texelFetch(uLit, p, 0).rgb;
  if (uDebug != 0 || uLookOn < 0.5) { oColor = vec4(c, 1.0); return; }
  float d = dAt(p);
  bool ink = false;
  int lay = int(floor(texelFetch(uAlbedo, p, 0).a * 255.0 + 0.5));
  if (d < 1e8) {
    vec3 n = octDecode(texelFetch(uNormal, p, 0).rg);
    ivec2 nb[4] = ivec2[4](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1));
    for (int i = 0; i < 4; i++) {
      ivec2 q = p + nb[i];
      float dq = dAt(q);
      if (dq - d > max(uLook.w, uInkMin)) ink = true;                    // a silhouette: the line on the nearer side
      if (i < 2 && (lay == 5 || lay == 6) && dq < 1e8 && abs(dq - d) < uLook.w) {
        vec3 nq = octDecode(texelFetch(uNormal, q, 0).rg);
        if (dot(n, nq) < uInkCos) ink = true;            // a crease
      }
    }
  }
  oColor = vec4(ink ? grade(uInk) : grade(c), 1.0);
}`;
