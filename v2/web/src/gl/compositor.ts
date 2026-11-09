// The layer compositor (v2/docs/specs/compositor.md): one WebGL2 canvas.
//
//  1. G-pass: for the visible tiles, every layer that is on draws its colour, normal and class at its own depth
//     (gl_FragDepth from its depth tile) into a G-buffer, so the nearest surface wins per pixel (ties: later layer).
//     Layers 1 and 2 share a pass (the relief multiplies the ground). Vehicles (layer 12) are 3D boxes at their
//     profile height, depth-tested against the same buffer, per pixel.
//  2. Light pass (layers 9 and 11): sun shading from the normal, cast shadows marched through the shadow height map
//     for the sun's real position, the sky grade, seasons and snow.
//  3. Night (layer 10): lit windows and street lamps, depth-tested against the G-buffer, added on.
//  4. Look (layer 14): grade and ink from the geometry, to the canvas.
// Any layer can be switched off (?off=...): it is then neither drawn nor casting shadows.

import type { LightConfig, ReleaseIndex } from "../data.ts";
import { fetchBin, fetchImage } from "../data.ts";
import { FULL_VS, GROUND_FS, LAMP_FS, LAMP_VS, LAYER_FS, LIGHT_FS, LOOK_FS, TILE_VS, VEH_FS, VEH_VS, WIN_FS, WIN_VS } from "./shaders.ts";

export const LAYER_ID: Record<string, number> = { ground: 1, relief: 2, water: 3, transport: 4, buildings: 5, structures: 6, trees: 7 };
const DRAW_ORDER = ["water", "transport", "buildings", "structures", "trees"];

export interface View { cx: number; cy: number; scale: number }
export interface LightState {
  sun: [number, number, number]; el: number; az: number;
  season: string; snow: boolean; hour: number; debug: number; off: Set<string>;
}
export interface VehicleInstances { count: number; inst: Float32Array; size: Float32Array }

interface TileTex { c?: WebGLTexture; g?: WebGLTexture; k?: WebGLTexture; dmin: number; ready: boolean; failed?: boolean; used: number }

function compile(gl: WebGL2RenderingContext, vs: string, fs: string): WebGLProgram {
  const mk = (type: number, src: string) => {
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) + "\n" + src.split("\n").map((l, i) => `${i + 1}: ${l}`).join("\n"));
    return s;
  };
  const p = gl.createProgram()!;
  gl.attachShader(p, mk(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, mk(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) ?? "link");
  return p;
}

class Prog {
  loc = new Map<string, WebGLUniformLocation | null>();
  constructor(public gl: WebGL2RenderingContext, public p: WebGLProgram) {}
  u(name: string) {
    if (!this.loc.has(name)) this.loc.set(name, this.gl.getUniformLocation(this.p, name));
    return this.loc.get(name)!;
  }
  f(name: string, ...v: number[]) {
    const gl = this.gl, l = this.u(name);
    if (l === null) return;
    if (v.length === 1) gl.uniform1f(l, v[0]); else if (v.length === 2) gl.uniform2f(l, v[0], v[1]);
    else if (v.length === 3) gl.uniform3f(l, v[0], v[1], v[2]); else gl.uniform4f(l, v[0], v[1], v[2], v[3]);
  }
  i(name: string, ...v: number[]) {
    const gl = this.gl, l = this.u(name);
    if (l === null) return;
    if (v.length === 1) gl.uniform1i(l, v[0]); else gl.uniform2i(l, v[0], v[1]);
  }
}

export class Compositor {
  gl: WebGL2RenderingContext;
  W = 1; H = 1;
  private quad: WebGLBuffer;
  private progLayer: Prog; private progGround: Prog; private progVeh: Prog; private progLight: Prog;
  private progWin: Prog; private progLamp: Prog; private progLook: Prog;
  private gbuf!: { fb: WebGLFramebuffer; albedo: WebGLTexture; normal: WebGLTexture; depth: WebGLTexture };
  private litbuf!: { fb: WebGLFramebuffer; fbDepth: WebGLFramebuffer; color: WebGLTexture };
  private tiles = new Map<string, TileTex>();
  private frameNo = 0;
  private hmA: WebGLTexture | null = null; private hmB: WebGLTexture | null = null;
  private cube: { buf: WebGLBuffer; n: number }; private vehBuf: WebGLBuffer; private vehSize: WebGLBuffer;
  private winBuf: WebGLBuffer | null = null; private winCount = 0;
  private lampBuf: WebGLBuffer | null = null; private lampCount = 0;
  pending = 0;
  onTile: () => void = () => {};
  stats = { tilesDrawn: 0, tilesMissing: 0 };

  constructor(public canvas: HTMLCanvasElement, public idx: ReleaseIndex) {
    const gl = canvas.getContext("webgl2", { antialias: false, depth: false, alpha: false, preserveDrawingBuffer: true,
      powerPreference: "high-performance" });
    if (!gl) throw new Error("WebGL2 is not available");
    this.gl = gl;
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    this.quad = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), gl.STATIC_DRAW);
    this.progLayer = new Prog(gl, compile(gl, TILE_VS, LAYER_FS));
    this.progGround = new Prog(gl, compile(gl, TILE_VS, GROUND_FS));
    this.progVeh = new Prog(gl, compile(gl, VEH_VS, VEH_FS));
    this.progLight = new Prog(gl, compile(gl, FULL_VS, LIGHT_FS));
    this.progWin = new Prog(gl, compile(gl, WIN_VS, WIN_FS));
    this.progLamp = new Prog(gl, compile(gl, LAMP_VS, LAMP_FS));
    this.progLook = new Prog(gl, compile(gl, FULL_VS, LOOK_FS));
    this.cube = this.makeCube();
    this.vehBuf = gl.createBuffer()!;
    this.vehSize = gl.createBuffer()!;
  }

  get cfg(): LightConfig { return this.idx.config; }

  private makeCube() {
    const gl = this.gl;
    const F: [number[], number[][]][] = [
      [[0, 0, 1], [[-.5, -.5, 1], [.5, -.5, 1], [.5, .5, 1], [-.5, .5, 1]]],
      [[1, 0, 0], [[.5, -.5, 0], [.5, .5, 0], [.5, .5, 1], [.5, -.5, 1]]],
      [[-1, 0, 0], [[-.5, .5, 0], [-.5, -.5, 0], [-.5, -.5, 1], [-.5, .5, 1]]],
      [[0, 1, 0], [[.5, .5, 0], [-.5, .5, 0], [-.5, .5, 1], [.5, .5, 1]]],
      [[0, -1, 0], [[-.5, -.5, 0], [.5, -.5, 0], [.5, -.5, 1], [-.5, -.5, 1]]],
    ];
    const v: number[] = [];
    for (const [n, q] of F) for (const i of [0, 1, 2, 0, 2, 3]) v.push(...q[i], ...n);
    const buf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(v), gl.STATIC_DRAW);
    return { buf, n: v.length / 6 };
  }

  resize(w: number, h: number) {
    const gl = this.gl;
    if (w === this.W && h === this.H && this.gbuf) return;
    this.W = w; this.H = h;
    this.canvas.width = w; this.canvas.height = h;
    const tex = (internal: number, format: number, type: number) => {
      const t = gl.createTexture()!;
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, type, null);
      for (const p of [gl.TEXTURE_MIN_FILTER, gl.TEXTURE_MAG_FILTER]) gl.texParameteri(gl.TEXTURE_2D, p, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      return t;
    };
    if (this.gbuf) {
      gl.deleteTexture(this.gbuf.albedo); gl.deleteTexture(this.gbuf.normal); gl.deleteTexture(this.gbuf.depth);
      gl.deleteFramebuffer(this.gbuf.fb); gl.deleteTexture(this.litbuf.color); gl.deleteFramebuffer(this.litbuf.fb);
      gl.deleteFramebuffer(this.litbuf.fbDepth);
    }
    const albedo = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE);
    const normal = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE);
    const depth = tex(gl.DEPTH_COMPONENT24, gl.DEPTH_COMPONENT, gl.UNSIGNED_INT);
    const fb = gl.createFramebuffer()!;
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, albedo, 0);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, normal, 0);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.TEXTURE_2D, depth, 0);
    this.gbuf = { fb, albedo, normal, depth };
    const color = tex(gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE);
    // the light pass samples the depth, so its target has no depth attachment; the night pass tests against it
    const lfb = gl.createFramebuffer()!;
    gl.bindFramebuffer(gl.FRAMEBUFFER, lfb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, color, 0);
    const dfb = gl.createFramebuffer()!;
    gl.bindFramebuffer(gl.FRAMEBUFFER, dfb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, color, 0);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.TEXTURE_2D, depth, 0);
    this.litbuf = { fb: lfb, fbDepth: dfb, color };
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  // -------------------------------------------------------------------------------------------- data
  setHeightMap(A: Uint8Array, B: Uint8Array) {
    const gl = this.gl, L = this.idx.light;
    const up = (d: Uint8Array) => {
      const t = gl.createTexture()!;
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, L.width, L.height, 0, gl.RGBA, gl.UNSIGNED_BYTE, d);
      for (const p of [gl.TEXTURE_MIN_FILTER, gl.TEXTURE_MAG_FILTER]) gl.texParameteri(gl.TEXTURE_2D, p, gl.NEAREST);
      return t;
    };
    this.hmA = up(A); this.hmB = up(B);
  }

  setWindows(data: Float32Array) {
    const gl = this.gl;
    this.winBuf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.winBuf);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    this.winCount = data.length / 8;
  }

  setLamps(data: Float32Array) {
    const gl = this.gl;
    this.lampBuf = gl.createBuffer()!;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.lampBuf);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    this.lampCount = data.length / 3;
  }

  private texFrom(data: Uint8Array | ImageBitmap, fmt: "rgba" | "r", linear: boolean) {
    const gl = this.gl;
    const t = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, t);
    if (data instanceof Uint8Array) {
      if (fmt === "rgba") gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, 512, 512, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
      else gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, 512, 512, 0, gl.RED, gl.UNSIGNED_BYTE, data);
    } else {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, data);
    }
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, linear ? gl.LINEAR : gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }

  /** A layer's tile: loaded on first request; undefined until ready, null if the layer has no such tile. */
  tile(layer: string, z: number, name: string): TileTex | null | undefined {
    const li = this.idx.layers[layer];
    const dmin = li?.tiles[String(z)]?.[name];
    if (dmin === undefined) return null;
    const key = `${layer}/${z}/${name}`;
    let t = this.tiles.get(key);
    if (!t) {
      t = { dmin, ready: false, used: this.frameNo };
      this.tiles.set(key, t);
      this.pending++;
      const tt = t;
      const base = `${layer}/${z}/${name}`;
      const hasK = li.files.includes("k.bin");
      Promise.all([layer === "buffers" ? Promise.resolve(null) : fetchImage(`${base}.c.webp`), fetchBin(`${base}.g.bin`, 512, 4),
        hasK ? fetchBin(`${base}.k.bin`, 512, 1) : Promise.resolve(null)])
        .then(([c, g, k]) => {
          if (c) tt.c = this.texFrom(c, "rgba", true);
          if (g) tt.g = this.texFrom(g, "rgba", false);
          if (k) tt.k = this.texFrom(k, "r", false);
          tt.ready = true;
          if (c) c.close();
        })
        .catch(() => { tt.failed = true; })
        .finally(() => { this.pending--; this.onTile(); });
    }
    t.used = this.frameNo;
    return t.ready ? t : undefined;
  }

  private evict(max = 900) {
    if (this.tiles.size <= max) return;
    const gl = this.gl;
    const old = [...this.tiles.entries()].filter(([, t]) => t.ready && this.frameNo - t.used > 2).sort((a, b) => a[1].used - b[1].used);
    for (const [k, t] of old.slice(0, this.tiles.size - max)) {
      for (const x of [t.c, t.g, t.k]) if (x) gl.deleteTexture(x);
      this.tiles.delete(k);
    }
  }

  level(view: View): number {
    const z = Math.floor(Math.log2(1 / Math.max(view.scale, 1e-6)) + 0.25);
    return Math.max(0, Math.min(this.idx.levels, z));
  }

  visibleTiles(view: View, z: number): [number, number][] {
    const size = 512 * 2 ** z;
    const x0 = view.cx - this.W / 2 / view.scale, x1 = view.cx + this.W / 2 / view.scale;
    const y0 = view.cy - this.H / 2 / view.scale, y1 = view.cy + this.H / 2 / view.scale;
    const out: [number, number][] = [];
    for (let ty = Math.floor(y0 / size); ty <= Math.floor(y1 / size); ty++)
      for (let tx = Math.floor(x0 / size); tx <= Math.floor(x1 / size); tx++) out.push([tx, ty]);
    return out;
  }

  /** Tiles of the view not yet loaded (for "first view drawn" timing). */
  missing(view: View, off: Set<string>): number {
    const z = this.level(view);
    let n = 0;
    for (const [tx, ty] of this.visibleTiles(view, z)) for (const L of Object.keys(LAYER_ID)) {
      if (off.has(L)) continue;
      if (this.tile(L, z, `${tx}_${ty}`) === undefined) n++;
    }
    return n;
  }

  // -------------------------------------------------------------------------------------------- frame
  private setView(p: Prog, view: View) {
    p.f("uView", view.cx, view.cy, view.scale, 0);
    p.f("uSize", this.W, this.H);
  }

  private setCam(p: Prog) {
    const c = this.idx.camera;
    p.f("uFrame", c.frame.sx0, c.frame.sy1);
    p.f("uMpp", c.mpp);
    p.f("uDepthRange", this.idx.depth_cm[0], this.idx.depth_cm[1]);
  }

  private bindQuad(p: Prog) {
    const gl = this.gl;
    const a = gl.getAttribLocation(p.p, "aCorner");
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.enableVertexAttribArray(a);
    gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
    gl.vertexAttribDivisor(a, 0);
    return a;
  }

  /** For a wanted tile, the loaded tile to draw and the part of it: itself, or a coarser one while it loads. */
  private find(layer: string, z: number, tx: number, ty: number, minD = 0): [TileTex, number, number, number] | null {
    for (let d = minD; z + d <= this.idx.levels; d++) {
      const ax = tx >> d, ay = ty >> d;
      const t = this.tile(layer, z + d, `${ax}_${ay}`);
      if (t === null) { if (d === 0) return null; continue; }
      if (t) {
        const k = 1 / 2 ** d;
        return [t, (tx - (ax << d)) * k, (ty - (ay << d)) * k, k];
      }
    }
    return null;
  }

  /** The depth reference of a texture tile (row ty at zoom z): sy of its row 0 centre and the step per row. */
  syRef(z: number, ty: number): [number, number] {
    const c = this.idx.camera, k = 2 ** z;
    return [c.frame.sy1 - (ty * 512 + 0.5) * k * c.mpp, -k * c.mpp];
  }

  render(view: View, st: LightState, veh: VehicleInstances | null) {
    const gl = this.gl, cfg = this.cfg;
    this.frameNo++;
    const z = this.level(view);
    const size = 512 * 2 ** z;
    const tiles = this.visibleTiles(view, z);
    // ------------------------------------------------------------ 1. G-pass
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.gbuf.fb);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
    gl.viewport(0, 0, this.W, this.H);
    gl.clearColor(0, 0, 0, 0);
    gl.clearDepth(1);
    gl.disable(gl.BLEND);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(true);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    this.stats.tilesDrawn = 0; this.stats.tilesMissing = 0;
    const pal = this.idx.palette;
    const paper = pal.ink.paper.rgb.map((v) => v / 255);
    // layers 1 + 2
    const gOn = !st.off.has("ground"), rOn = !st.off.has("relief");
    if (gOn || rOn) {
      const p = this.progGround;
      gl.useProgram(p.p);
      this.setView(p, view);
      p.f("uDepthRangeT", this.idx.depth_cm[0], this.idx.depth_cm[1]);
      p.f("uPaper", paper[0], paper[1], paper[2]);
      this.bindQuad(p);
      const names = ["uGC", "uGG", "uGK", "uRC", "uRG", "uRK"];
      names.forEach((n, i) => p.i(n, i));
      for (const [tx, ty] of tiles) {
        const g = gOn ? this.find("ground", z, tx, ty) : null;
        const r = rOn ? this.find("relief", z, tx, ty) : null;
        if (!g && !r) continue;
        // both must show the same part of a tile: while one is still loading, both come from the coarser level
        let gg = g, rr = r;
        if (g && r && g[3] !== r[3]) {
          const d = Math.round(Math.log2(1 / Math.min(g[3], r[3])));
          gg = this.find("ground", z, tx, ty, d); rr = this.find("relief", z, tx, ty, d);
          if (gg && rr && gg[3] !== rr[3]) rr = null;
        }
        const A = (gg ?? rr)!;
        p.f("uSub", A[1], A[2], A[3], A[3]);
        { const d = Math.round(Math.log2(1 / A[3])); p.f("uSyRef", ...this.syRef(z + d, ty >> d)); }
        p.f("uTile", tx * size, ty * size, size);
        const bind = (unit: number, t?: WebGLTexture) => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t ?? null); };
        if (gg) { bind(0, gg[0].c); bind(1, gg[0].g); bind(2, gg[0].k); p.f("uGDmin", gg[0].dmin); }
        if (rr) { bind(3, rr[0].c); bind(4, rr[0].g); bind(5, rr[0].k); p.f("uRDmin", rr[0].dmin); }
        p.f("uGOn", gg ? 1 : 0); p.f("uROn", rr ? 1 : 0);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        this.stats.tilesDrawn++;
      }
    }
    // layers 3 - 7
    {
      const p = this.progLayer;
      gl.useProgram(p.p);
      this.setView(p, view);
      p.f("uDepthRangeT", this.idx.depth_cm[0], this.idx.depth_cm[1]);
      this.bindQuad(p);
      p.i("uC", 0); p.i("uG", 1); p.i("uK", 2);
      for (const L of DRAW_ORDER) {
        if (st.off.has(L)) continue;
        p.f("uLayer", LAYER_ID[L]);
        for (const [tx, ty] of tiles) {
          const f = this.find(L, z, tx, ty);
          if (!f) continue;
          const [t, sx, sy, k] = f;
          if (k < 1) this.stats.tilesMissing++;
          p.f("uSub", sx, sy, k, k);
          { const d = Math.round(Math.log2(1 / k)); p.f("uSyRef", ...this.syRef(z + d, ty >> d)); }
          p.f("uTile", tx * size, ty * size, size);
          p.f("uDmin", t.dmin);
          p.f("uHasK", t.k ? 1 : 0);
          gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, t.c ?? null);
          gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, t.g ?? null);
          gl.activeTexture(gl.TEXTURE2); gl.bindTexture(gl.TEXTURE_2D, t.k ?? null);
          gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
          this.stats.tilesDrawn++;
        }
      }
    }
    // vehicles (layer 12): boxes, depth-tested per pixel
    if (veh && veh.count && !st.off.has("vehicles")) {
      const p = this.progVeh;
      gl.useProgram(p.p);
      this.setView(p, view); this.setCam(p);
      p.f("uEps", (cfg.vehicles.depth_eps_m as number));
      const cols = [[0.78, 0.22, 0.2], [0.2, 0.36, 0.62], [0.92, 0.9, 0.86], [0.22, 0.24, 0.26], [0.85, 0.72, 0.25],
        [0.82, 0.16, 0.18], [0.86, 0.86, 0.84], [0.35, 0.55, 0.3]];
      gl.uniform3fv(p.u("uColours"), new Float32Array(cols.flat()));
      const aPos = gl.getAttribLocation(p.p, "aPos"), aNrm = gl.getAttribLocation(p.p, "aNrm");
      const aInst = gl.getAttribLocation(p.p, "aInst"), aSize = gl.getAttribLocation(p.p, "aSize");
      gl.bindBuffer(gl.ARRAY_BUFFER, this.cube.buf);
      gl.enableVertexAttribArray(aPos); gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 24, 0); gl.vertexAttribDivisor(aPos, 0);
      gl.enableVertexAttribArray(aNrm); gl.vertexAttribPointer(aNrm, 3, gl.FLOAT, false, 24, 12); gl.vertexAttribDivisor(aNrm, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.vehBuf);
      gl.bufferData(gl.ARRAY_BUFFER, veh.inst.subarray(0, veh.count * 4), gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(aInst); gl.vertexAttribPointer(aInst, 4, gl.FLOAT, false, 0, 0); gl.vertexAttribDivisor(aInst, 1);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.vehSize);
      gl.bufferData(gl.ARRAY_BUFFER, veh.size.subarray(0, veh.count * 4), gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(aSize); gl.vertexAttribPointer(aSize, 4, gl.FLOAT, false, 0, 0); gl.vertexAttribDivisor(aSize, 1);
      gl.drawArraysInstanced(gl.TRIANGLES, 0, this.cube.n, veh.count);
      for (const a of [aInst, aSize]) { gl.vertexAttribDivisor(a, 0); gl.disableVertexAttribArray(a); }
      gl.disableVertexAttribArray(aNrm);
    }
    // ------------------------------------------------------------ 2. light
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.litbuf.fb);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
    gl.disable(gl.DEPTH_TEST);
    gl.depthMask(false);
    {
      const p = this.progLight;
      gl.useProgram(p.p);
      this.setView(p, view); this.setCam(p);
      this.bindQuad(p);
      const tex = [this.gbuf.albedo, this.gbuf.normal, this.gbuf.depth, this.hmA, this.hmB];
      ["uAlbedo", "uNormal", "uDepth", "uHmA", "uHmB"].forEach((n, i) => {
        gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, tex[i]); p.i(n, i);
      });
      const L = this.idx.light, o = this.idx.camera.origin_en;
      p.f("uHm", L.e0 - o[0], L.n0 - o[1], L.step, L.zbase);
      p.i("uHmSize", L.width, L.height);
      p.f("uHmUnits", L.encoding.building_unit_m, L.encoding.tree_unit_m, L.encoding.structure_unit_m);
      p.f("uMarch", cfg.march.t0_m, cfg.march.growth, cfg.march.steps, cfg.march.bias_m);
      p.f("uZTop", this.zTop);
      p.f("uSun", st.sun[0], st.sun[1], st.sun[2], st.el);
      const lightOn = !st.off.has("light");
      const shadowsReady = this.hmA !== null;
      p.f("uSources", shadowsReady && !(st.off.has("ground") && st.off.has("relief") && st.off.has("water")) ? 1 : 0,
        shadowsReady && !st.off.has("buildings") ? 1 : 0, shadowsReady && !st.off.has("trees") ? 1 : 0,
        shadowsReady && !(st.off.has("structures") && st.off.has("transport")) ? 1 : 0);
      p.f("uLightK", cfg.sun.wrap, cfg.sun.ambient, cfg.sun.direct, cfg.sun.shadow_keep);
      const g = grade(cfg, st.el);
      p.f("uSunTint", ...g.sun);
      p.f("uAmbTint", ...g.amb);
      const sht = pal.light.shadow_tint.rgb.map((v) => v / 255);
      const shm = Math.max(...sht);
      p.f("uShadowTint", sht[0] / shm, sht[1] / shm, sht[2] / shm);
      p.f("uLightOn", lightOn ? 1 : 0);
      const seasonsOn = !st.off.has("seasons");
      const s = cfg.seasons[seasonsOn ? st.season : "summer"];
      p.f("uSeasonTree", s.tree[0], s.tree[1], s.tree[2]);
      p.f("uSeasonGreen", s.green[0], s.green[1], s.green[2]);
      p.f("uSeasonSat", s.sat);
      p.f("uWinter", seasonsOn && st.season === "winter" ? 1 : 0);
      p.f("uSnow", seasonsOn && st.snow ? 1 : 0);
      p.f("uSnowCos", cfg.seasons.snow_cos);
      p.f("uPaper", paper[0], paper[1], paper[2]);
      const tr = pal.trees.trunk.rgb.map((v) => v / 255);
      p.f("uTrunk", tr[0], tr[1], tr[2]);
      p.i("uDebug", st.debug);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    // ------------------------------------------------------------ 3. night lights, depth-tested against the G-buffer
    const night = nightFactor(cfg, st.el);
    if (night > 0 && !st.off.has("night") && !st.off.has("light") && st.debug === 0) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.litbuf.fbDepth);
      gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
      gl.enable(gl.DEPTH_TEST);
      gl.depthFunc(gl.LEQUAL);
      gl.depthMask(false);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE);
      const warm = pal.buildings.window_lit.rgb.map((v) => v / 255);
      if (this.winBuf && !st.off.has("buildings")) {
        const p = this.progWin;
        gl.useProgram(p.p);
        this.setView(p, view); this.setCam(p);
        p.f("uEps", cfg.night.depth_eps_m);
        const share = litShare(cfg, st.hour);
        p.f("uLit", share.homes, share.shops, 7.0, st.hour);
        p.f("uWarm", warm[0], warm[1], warm[2]);
        p.f("uNight", night);
        const a = this.bindQuad(p);
        void a;
        const aA = gl.getAttribLocation(p.p, "aA"), aB = gl.getAttribLocation(p.p, "aB");
        gl.bindBuffer(gl.ARRAY_BUFFER, this.winBuf);
        gl.enableVertexAttribArray(aA); gl.vertexAttribPointer(aA, 4, gl.FLOAT, false, 32, 0); gl.vertexAttribDivisor(aA, 1);
        gl.enableVertexAttribArray(aB); gl.vertexAttribPointer(aB, 4, gl.FLOAT, false, 32, 16); gl.vertexAttribDivisor(aB, 1);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.winCount);
        for (const x of [aA, aB]) { gl.vertexAttribDivisor(x, 0); gl.disableVertexAttribArray(x); }
      }
      if (this.lampBuf) {
        const p = this.progLamp;
        gl.useProgram(p.p);
        this.setView(p, view); this.setCam(p);
        p.f("uEps", cfg.night.depth_eps_m);
        p.f("uRadius", Math.max(4, cfg.night.lamp_radius_px * Math.min(1, view.scale * 2)));
        p.f("uWarm", warm[0], warm[1] * 0.92, warm[2] * 0.75);
        p.f("uNight", night);
        this.bindQuad(p);
        const aP = gl.getAttribLocation(p.p, "aP");
        gl.bindBuffer(gl.ARRAY_BUFFER, this.lampBuf);
        gl.enableVertexAttribArray(aP); gl.vertexAttribPointer(aP, 3, gl.FLOAT, false, 0, 0); gl.vertexAttribDivisor(aP, 1);
        gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, this.lampCount);
        gl.vertexAttribDivisor(aP, 0); gl.disableVertexAttribArray(aP);
      }
      gl.disable(gl.BLEND);
      gl.disable(gl.DEPTH_TEST);
    }
    // ------------------------------------------------------------ 4. look, to the canvas
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    {
      const p = this.progLook;
      gl.useProgram(p.p);
      this.setCam(p);
      this.bindQuad(p);
      const tex = [this.litbuf.color, this.gbuf.normal, this.gbuf.depth, this.gbuf.albedo];
      ["uLit", "uNormal", "uDepth", "uAlbedo"].forEach((n, i) => {
        gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, tex[i]); p.i(n, i);
      });
      const lk = cfg.look;
      p.f("uLook", lk.sat_max, lk.lum_min, lk.lum_max, lk.ink_depth_m);
      p.f("uInkCos", lk.ink_normal_cos);
      p.f("uInkMin", 4 * this.idx.camera.mpp / view.scale);
      const ink = pal.ink.line.rgb.map((v) => v / 255);
      p.f("uInk", ink[0], ink[1], ink[2]);
      p.f("uLookOn", st.off.has("look") ? 0 : 1);
      p.i("uDebug", st.debug);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    this.evict();
  }

  zTop = 1e9;
}

export function grade(cfg: LightConfig, el: number): { sun: [number, number, number]; amb: [number, number, number] } {
  const G = cfg.grade;
  const mix = (a: number[], b: number[], t: number) => a.map((v, i) => v + (b[i] - v) * Math.max(0, Math.min(1, t))) as [number, number, number];
  if (el >= G.golden_deg[1]) return { sun: G.day_tint as [number, number, number], amb: [1, 1, 1] };
  if (el >= G.golden_deg[0]) {
    const t = (el - G.golden_deg[0]) / (G.golden_deg[1] - G.golden_deg[0]);
    return { sun: mix(G.golden_tint, G.day_tint, t), amb: mix([1, 0.9, 0.82], [1, 1, 1], t) };
  }
  if (el >= G.night_deg) {
    const t = (el - G.night_deg) / (G.blue_deg[1] - G.night_deg);
    const night = G.night_tint.map((v) => v * G.night_level);
    return { sun: [0, 0, 0], amb: mix(night, G.blue_tint, t) };
  }
  return { sun: [0, 0, 0], amb: G.night_tint.map((v) => v * G.night_level) as [number, number, number] };
}

/** How much the night lights show: none with the sun up (layer-10 rule 3), full from civil twilight's end. */
export function nightFactor(cfg: LightConfig, el: number): number {
  if (el > 0) return 0;
  return Math.max(0, Math.min(1, -el / -cfg.grade.night_deg));
}

/** Share of windows lit by the hour: homes in the evening, few after midnight; shops until 20:00. */
export function litShare(cfg: LightConfig, hour: number) {
  const N = cfg.night;
  const evening = hour >= 16 || hour < 0.5;
  const late = hour >= 0.5 && hour < 6;
  const homes = late ? N.window_lit_share_late : evening ? N.window_lit_share_evening : 0.3;
  const shops = hour >= 7 && hour < 20 ? 0.9 : 0.08;
  return { homes, shops };
}
