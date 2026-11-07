import { useEffect, useRef } from "react";
import { asset } from "../config";
import { canvasDpr, subscribe } from "../frame";
import { currentAmounts, onWeather } from "../weather";
import { groundToScreen } from "../sky/weatherCore";
import type { MapHandle } from "./IsometricMap";

/**
 * Valley fog and haze, drawn with WebGL on one canvas over the map (under the pins), in map coordinates.
 *
 * web/public/data/fog.png (pipeline/build_fog_mask.py) holds, every 32 map px, the height of the surface seen there
 * (R, 200 .. 420 m) and how near the rivers it is (G). Fog fills everything below a fog line that the weather sets:
 * at about 290 m in thick fog, so the Alzette and the Petrusse valleys (Grund at about 245 m, Pfaffenthal 250 m)
 * fill while the old town (about 305 m) and Kirchberg (340 m) rise above it. It is a little thicker over the water,
 * and its top is broken by slow noise that drifts with the wind and moves a little more than the map when panning,
 * which gives it depth. Low visibility adds a thin haze everywhere. The fog thins at close zoom so the streets stay
 * readable, and at night it turns a dark blue-grey with a faint warm glow from the city below.
 * Drawn at half the CSS resolution (the fog is soft), 30 times a second while it drifts; with reduced motion only
 * when the map moves.
 */

interface Props {
  map: React.RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
}

interface FogInfo { file: string; scale: number; w: number; h: number; h0: number; h1: number }

const VS = `
attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }`;

const FS = `
precision highp float;
uniform sampler2D u_mask;
uniform vec2 u_res;       // canvas, device px
uniform float u_dpr;
uniform vec2 u_view;      // map px at the screen centre
uniform float u_z;        // screen px per map px
uniform vec2 u_size;      // map px covered by the mask
uniform float u_line;     // fog line, metres above sea level
uniform vec2 u_hrange;    // metres at R = 0 and R = 1
uniform float u_amount;   // 0 .. 1 valley fog
uniform float u_haze;     // 0 .. 1 haze everywhere
uniform float u_night;
uniform float u_fade;     // less fog close up
uniform vec2 u_drift;     // map px

float h21(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1.0, 0.0)), f.x), mix(h21(i + vec2(0.0, 1.0)), h21(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) { return 0.55 * vnoise(p) + 0.3 * vnoise(p * 2.13 + 7.1) + 0.15 * vnoise(p * 4.37 + 3.3); }

void main() {
  vec2 px = vec2(gl_FragCoord.x, u_res.y - gl_FragCoord.y) / u_dpr;
  vec2 d = (px - u_res / u_dpr * 0.5) / u_z;
  vec2 m = u_view + d;
  vec3 s = texture2D(u_mask, m / u_size).rgb;
  float h = mix(u_hrange.x, u_hrange.y, s.r);
  // the fog's own surface, a little parallax: it lies above the ground
  vec2 q = u_view + d * 1.04 + u_drift;
  float n = fbm(q / 700.0);
  float n2 = fbm(q / 190.0 + 11.0);
  float depth = u_line + (n - 0.5) * 26.0 - h;               // metres under the fog's top
  float dens = smoothstep(-6.0, 22.0, depth);
  dens *= mix(0.8, 1.15, s.g) * (0.75 + 0.45 * n2);
  float a = clamp(u_amount * dens * 0.82 + u_haze * (0.18 + 0.12 * n), 0.0, 0.88) * u_fade;
  if (a < 0.004) { gl_FragColor = vec4(0.0); return; }
  vec3 day = mix(vec3(0.80, 0.84, 0.88), vec3(0.95, 0.96, 0.97), n2);
  vec3 nightCol = mix(vec3(0.10, 0.13, 0.20), vec3(0.20, 0.23, 0.31), n2) + vec3(0.16, 0.10, 0.04) * dens * 0.5;
  vec3 col = mix(day, nightCol, u_night);
  gl_FragColor = vec4(col * a, a);
}`;

function compile(gl: WebGLRenderingContext, type: number, src: string) {
  const s = gl.createShader(type)!;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? "shader");
  return s;
}

export function Fog({ map, night }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const nightRef = useRef(night);
  const wake = useRef<() => void>(() => {});
  if (nightRef.current !== night) { nightRef.current = night; wake.current(); }

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const gl = cv.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false, depth: false, stencil: false });
    if (!gl) return;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let alive = true, info: FogInfo | null = null, cleared = true;
    const prog = gl.createProgram()!;
    try {
      gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS));
      gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FS));
    } catch (e) { console.warn("fog:", e); return; }
    gl.linkProgram(prog);
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(prog, "a_pos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    const U = (n: string) => gl.getUniformLocation(prog, n);
    const u = {
      res: U("u_res"), dpr: U("u_dpr"), view: U("u_view"), z: U("u_z"), size: U("u_size"), line: U("u_line"), hrange: U("u_hrange"),
      amount: U("u_amount"), haze: U("u_haze"), night: U("u_night"), fade: U("u_fade"), drift: U("u_drift"),
    };
    gl.uniform1i(U("u_mask"), 0);
    let tex: WebGLTexture | null = null;
    const drift = [0, 0];

    const draw = (dt: number) => {
      const v = map.current?.getView();
      if (!v || !info || !tex) return;
      const w = currentAmounts();
      const fog = w.fog;
      const res = canvasDpr(2) * 0.5;
      const W = window.innerWidth, H = window.innerHeight;
      const bw = Math.round(W * res), bh = Math.round(H * res);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; cleared = false; }
      gl.viewport(0, 0, bw, bh);
      if (fog < 0.005) {
        if (!cleared) { gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); cleared = true; }
        return;
      }
      cleared = false;
      if (!still) {
        // the fog creeps with the wind, slowly
        const [sx, sy] = groundToScreen(w.windE, w.windN);
        const k = Math.min(dt, 100) / 1000 * 0.08;
        drift[0] = (drift[0] - sx * k) % 70000; drift[1] = (drift[1] - sy * k) % 70000;
      }
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform2f(u.res, bw, bh);
      gl.uniform1f(u.dpr, res);
      gl.uniform2f(u.view, v.x, v.y);
      gl.uniform1f(u.z, v.z);
      gl.uniform2f(u.size, info.w * info.scale, info.h * info.scale);
      gl.uniform1f(u.line, 246 + 46 * Math.min(1, fog));
      gl.uniform2f(u.hrange, info.h0, info.h1);
      gl.uniform1f(u.amount, Math.min(1, fog * 1.1));
      gl.uniform1f(u.haze, fog * 0.6);
      gl.uniform1f(u.night, nightRef.current);
      gl.uniform1f(u.fade, 1 - 0.45 * Math.min(1, Math.max(0, (v.z - 0.6) / 0.6)));
      gl.uniform2f(u.drift, drift[0], drift[1]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };

    const sub = subscribe((_t, dt) => draw(dt), { fps: 30, still, name: "fog" });
    wake.current = sub.wake;
    const offW = onWeather(sub.wake);
    // while the weather blends, the still version still needs its frames
    const blendTimer = setInterval(sub.wake, 500);

    fetch(asset("/data/fog.json")).then((r) => r.json()).then((d: FogInfo) => new Promise<void>((ok, fail) => {
      const im = new Image();
      im.onload = () => {
        if (!alive) return ok();
        gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
        tex = gl.createTexture();
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, im);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        info = d;
        sub.wake();
        ok();
      };
      im.onerror = fail;
      im.src = asset(d.file);
    })).catch(() => { /* no fog mask: no fog */ });

    return () => {
      alive = false;
      sub();
      offW();
      clearInterval(blendTimer);
      wake.current = () => {};
      if (tex) gl.deleteTexture(tex);
      gl.deleteBuffer(buf);
      gl.deleteProgram(prog);
    };
  }, [map]);

  return <canvas ref={canvas} aria-hidden="true"
    style={{ position: "fixed", inset: 0, width: "100vw", height: "100vh", pointerEvents: "none", zIndex: 1 }} />;
}
