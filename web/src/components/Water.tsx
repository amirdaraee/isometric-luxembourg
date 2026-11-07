import { useEffect, useRef } from "react";
import { asset } from "../config";
import type { MapHandle } from "./IsometricMap";

/**
 * Moving light on the rivers, drawn only inside the painted water.
 *
 * The water mask (web/public/data/water_mask.png and .json, from pipeline/build_water_mask.py) is found in the
 * painted art itself, so the effect never spills over banks, trees, bridges or roads. It is drawn with WebGL on its
 * own canvas, in map coordinates, so the pattern sticks to the map:
 *  - shimmer: the water is cut into small 6 x 2 map px patches (1.5 x 0.5 m); six times a second each patch looks
 *    up a slow swell at a slightly jittered spot and, near its crest or trough, becomes a faint light or dark ripple
 *    stroke (the idea of "Pixel Singapore": patches that take their value from somewhere along the swell);
 *  - crest flashes: now and then a short bright crest lights up for half a second, with a dark ink line under it;
 *  - at night the ripples catch warm city light, and broken warm reflections hang below lamps on the banks.
 * Nothing changes between the 6 Hz steps, so the canvas is redrawn only on a new step or when the map moves.
 */

interface Props {
  map: React.RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
}

/** The mask atlas description written by build_water_mask.py. */
interface MaskInfo { x0: number; y0: number; scale: number; w: number; h: number; chunk: number; cols: number; chunks: number[] }

const MIN_ZOOM = 0.12; // further out the ripples would be under a pixel: draw nothing
const FADE_TO = 0.16;  // full strength from here in
const STEPS_PER_S = 6;

const VS = `
attribute vec4 a_pos;     // map px relative to the mask origin (xy), atlas uv (zw)
uniform vec2 u_view;      // map px at the screen centre, relative to the mask origin
uniform vec2 u_scale;     // z / half screen size, in clip units per map px
varying vec2 v_map;
varying vec2 v_uv;
void main() {
  v_map = a_pos.xy;
  v_uv = a_pos.zw;
  gl_Position = vec4((a_pos.xy - u_view) * u_scale * vec2(1.0, -1.0), 0.0, 1.0);
}`;

const FS = `
precision highp float;
varying vec2 v_map;
varying vec2 v_uv;
uniform sampler2D u_mask;
uniform float u_t;       // seconds, in 1/6 s steps
uniform float u_step;    // the step number, kept small
uniform float u_cell;    // patch size multiplier: 1, 2 or 4 as the map zooms out
uniform float u_night;   // 0 .. 1
uniform float u_fade;    // 0 .. 1, fades the effect in as the map zooms in
uniform float u_debug;   // 1: tint the whole mask magenta (?waterdebug in the address)

// Hash without sine (Dave Hoskins), stable for the cell indices used here.
float h21(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

const vec2 D1 = vec2(0.24, 0.97);   // main swell direction (screen y is foreshortened ground, so crests run across)
const vec2 D2 = vec2(-0.55, 0.83);
float swell(vec2 p, float t) {
  return 0.62 * sin(dot(p, D1) * 0.131 - t * 2.4) + 0.38 * sin(dot(p, D2) * 0.209 + t * 1.7 + 1.3);
}

void main() {
  float m = texture2D(u_mask, v_uv).r;
  if (m < 0.02) discard;
  vec2 p = v_map;
  float t = u_t;

  // Shimmer: 6 x 2 map px patches in rows, every row shifted by a random amount so the patches do not line up.
  vec2 cs = vec2(6.0, 2.0) * u_cell;
  float row = floor(p.y / cs.y);
  float off = h21(vec2(row, 7.0)) * cs.x;
  vec2 cell = vec2(floor((p.x + off) / cs.x), row);
  vec2 centre = vec2((cell.x + 0.5) * cs.x - off, (row + 0.5) * cs.y);
  float jit = (h21(cell + vec2(u_step * 0.37, u_step * 0.11)) - 0.5) * 10.0 * u_cell;
  float v = swell(centre + D1 * jit, t) + (h21(cell * 1.7 + 0.5) - 0.5) * 0.7;

  // By day pale sky-coloured ripples; at night fewer, brighter ones that catch the warm city light.
  vec3 lightCol = mix(vec3(0.90, 0.97, 0.98), vec3(1.0, 0.70, 0.34), u_night);
  vec3 darkCol = mix(vec3(0.05, 0.19, 0.24), vec3(0.02, 0.04, 0.10), u_night);
  vec3 col = vec3(0.0);
  float a = 0.0;
  if (v > mix(0.72, 0.98, u_night)) { col = lightCol; a = mix(0.30, 0.50, u_night); }
  else if (v < -0.8) { col = darkCol; a = mix(0.18, 0.24, u_night); }

  // Night: broken warm reflections, columns of short dashes that hang below a light and wobble each step.
  if (u_night > 0.01) {
    vec2 gs = vec2(44.0, 88.0);
    vec2 gc = floor(p / gs);
    if (h21(gc + 3.3) < 0.22 * u_night) {
      float yf = fract(p.y / gs.y);
      float ri = floor(p.y / cs.y);
      float cx = (gc.x + 0.2 + 0.6 * h21(gc + 1.1)) * gs.x + (h21(vec2(ri, u_step)) - 0.5) * 3.0 * u_cell;
      float hw = (1.5 + 2.5 * h21(gc + 2.2)) * (1.0 - 0.6 * yf) * max(u_cell * 0.6, 1.0);
      bool on = h21(vec2(ri * 1.3, gc.x + u_step * 0.21)) > 0.3;
      if (on && abs(p.x - cx) < hw) {
        float ra = 0.6 * (1.0 - yf) * u_night;
        if (ra > a) { col = vec3(1.0, 0.72, 0.36); a = ra; }
      }
    }
  }

  // Crest flashes: in a coarse grid, a rare cell lights a short crest for half a second (three 6 Hz steps).
  vec2 bs = vec2(40.0, 14.0) * u_cell;
  float brow = floor(p.y / bs.y);
  float boff = h21(vec2(brow, 3.0)) * bs.x;
  vec2 bc = vec2(floor((p.x + boff) / bs.x), brow);
  float ph0 = h21(bc + 0.7) * 7.0;
  float slot = floor(t * 2.0 + ph0);
  if (h21(bc + vec2(mod(slot, 97.0) * 1.31, 5.0)) < 0.025) {
    float ph = fract(t * 2.0 + ph0);
    float env = sin(3.14159 * (ph + 0.1667));
    vec2 lc = p - vec2((bc.x + 0.5) * bs.x - boff, (bc.y + 0.5) * bs.y);
    float halfLen = bs.x * 0.25 * (0.6 + 0.4 * env);
    if (abs(lc.x) < halfLen) {
      if (abs(lc.y) < cs.y * 0.5) { col = mix(vec3(1.0), vec3(1.0, 0.86, 0.6), u_night); a = 0.62 * env; }
      else if (lc.y >= cs.y * 0.5 && lc.y < cs.y * 1.5 && abs(lc.x) < halfLen * 0.8) {
        col = darkCol; a = max(a, 0.18 * env);
      }
    }
  }

  a *= clamp(m * 1.2, 0.0, 1.0) * u_fade;
  if (u_debug > 0.5) { col = mix(vec3(1.0, 0.0, 0.8), col, a); a = max(a, 0.45 * m); }
  if (a < 0.003) discard;
  gl_FragColor = vec4(col * a, a);
}`;

/** Centres of the water mask's blocks, in map px: places over the rivers (for example to start bird flocks). */
export async function waterPoints(): Promise<{ x: number; y: number }[]> {
  const info: MaskInfo = await fetch(asset("/data/water_mask.json")).then((r) => r.json());
  const span = info.chunk * info.scale, pts: { x: number; y: number }[] = [];
  for (let k = 0; k < info.chunks.length; k += 2) {
    pts.push({ x: info.x0 + (info.chunks[k] + 0.5) * span, y: info.y0 + (info.chunks[k + 1] + 0.5) * span });
  }
  return pts;
}

interface GlState {
  gl: WebGLRenderingContext;
  prog: WebGLProgram;
  count: number;
  u: Record<string, WebGLUniformLocation | null>;
}

function compile(gl: WebGLRenderingContext, type: number, src: string): WebGLShader {
  const s = gl.createShader(type)!;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? "shader");
  return s;
}

/** Program, one static vertex buffer with a quad per mask block, and the atlas texture. */
function setup(gl: WebGLRenderingContext, info: MaskInfo, img: HTMLImageElement): GlState {
  const prog = gl.createProgram()!;
  gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS));
  gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog) ?? "link");
  gl.useProgram(prog);

  const C = info.chunk, cell = C + 2, span = C * info.scale;
  const AW = img.width, AH = img.height, n = info.chunks.length / 2;
  const v = new Float32Array(n * 6 * 4);
  for (let k = 0; k < n; k++) {
    const i = info.chunks[2 * k], j = info.chunks[2 * k + 1];
    const x0 = i * span, y0 = j * span, x1 = x0 + span, y1 = y0 + span;
    const ax = (k % info.cols) * cell + 1, ay = Math.floor(k / info.cols) * cell + 1;
    const u0 = ax / AW, v0 = ay / AH, u1 = (ax + C) / AW, v1 = (ay + C) / AH;
    v.set([x0, y0, u0, v0, x1, y0, u1, v0, x0, y1, u0, v1, x0, y1, u0, v1, x1, y0, u1, v0, x1, y1, u1, v1], k * 24);
  }
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, v, gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "a_pos");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, 0, 0);

  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.LUMINANCE, gl.LUMINANCE, gl.UNSIGNED_BYTE, img);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

  gl.enable(gl.BLEND);
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.clearColor(0, 0, 0, 0);
  const u: GlState["u"] = {};
  for (const name of ["u_view", "u_scale", "u_mask", "u_t", "u_step", "u_cell", "u_night", "u_fade", "u_debug"]) {
    u[name] = gl.getUniformLocation(prog, name);
  }
  gl.uniform1i(u.u_mask, 0);
  gl.uniform1f(u.u_debug, new URLSearchParams(location.search).has("waterdebug") ? 1 : 0);
  return { gl, prog, count: n * 6, u };
}

export function Water({ map, night }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const nightRef = useRef(night);
  const dirty = useRef(true);
  if (nightRef.current !== night) { nightRef.current = night; dirty.current = true; }

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    let st: GlState | null = null;
    let info: MaskInfo | null = null;
    let img: HTMLImageElement | null = null;
    let raf = 0, alive = true, lastStep = -1, last = "", cleared = false;
    const still = matchMedia("(prefers-reduced-motion: reduce)");

    const init = () => {
      if (!info || !img) return;
      const gl = cv.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false });
      if (!gl) return;
      try { st = setup(gl, info, img); } catch (e) { console.warn("water effect off:", e); st = null; }
      dirty.current = true;
    };

    const draw = (now: number) => {
      const v = map.current?.getView();
      if (!st || !info || !v) return;
      const gl = st.gl;
      const dpr = Math.min(window.devicePixelRatio || 1, 2), W = window.innerWidth, H = window.innerHeight;
      const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; dirty.current = true; }
      const step = still.matches ? 0 : Math.floor((now / 1000) * STEPS_PER_S);
      const key = `${v.x},${v.y},${v.z},${bw},${bh}`;
      if (step === lastStep && key === last && !dirty.current) return;
      lastStep = step; last = key; dirty.current = false;

      gl.viewport(0, 0, bw, bh);
      if (v.z < MIN_ZOOM) {
        if (!cleared) { gl.clear(gl.COLOR_BUFFER_BIT); cleared = true; }
        return;
      }
      cleared = false;
      gl.clear(gl.COLOR_BUFFER_BIT);
      const u = st.u;
      gl.uniform2f(u.u_view, v.x - info.x0, v.y - info.y0);
      gl.uniform2f(u.u_scale, v.z / (W / 2), v.z / (H / 2));
      gl.uniform1f(u.u_t, step / STEPS_PER_S);
      gl.uniform1f(u.u_step, step % 512);
      gl.uniform1f(u.u_cell, v.z >= 0.6 ? 1 : v.z >= 0.3 ? 2 : 4);
      gl.uniform1f(u.u_night, nightRef.current);
      gl.uniform1f(u.u_fade, Math.min(1, (v.z - MIN_ZOOM) / (FADE_TO - MIN_ZOOM)));
      gl.drawArrays(gl.TRIANGLES, 0, st.count);
    };

    Promise.all([
      fetch(asset("/data/water_mask.json")).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
      new Promise<HTMLImageElement>((ok, fail) => {
        const im = new Image();
        im.onload = () => ok(im);
        im.onerror = fail;
        im.src = asset("/data/water_mask.png");
      }),
    ]).then(([i, im]) => {
      if (!alive) return;
      info = i as MaskInfo;
      img = im;
      init();
    }).catch(() => { /* No mask yet: no water effect. */ });

    const lost = (e: Event) => { e.preventDefault(); st = null; };
    cv.addEventListener("webglcontextlost", lost);
    cv.addEventListener("webglcontextrestored", init);

    const loop = (now: number) => { raf = requestAnimationFrame(loop); draw(now); };
    raf = requestAnimationFrame(loop);
    // Also redraw inside the map's own redraw, so the ripples never trail the map while it moves.
    const off = map.current?.onFrame(() => draw(performance.now()));
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      off?.();
      cv.removeEventListener("webglcontextlost", lost);
      cv.removeEventListener("webglcontextrestored", init);
    };
  }, [map]);

  return <canvas ref={canvas} className="overlay" aria-hidden="true" />;
}
