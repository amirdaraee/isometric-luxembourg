// The v2 viewer: navigation, the clock, the compositor, the simulation, labels and hover.
// Test hooks for the headless checks live on window.__v2 (scripts/viewer_checks.mjs).

import { BASE, fetchBin, fetchBytes, fetchJSON, inflate, undelta, type ReleaseIndex } from "./data.ts";
import { Compositor, DEBUG_XDEPTH, DEBUG_XID, LAYER_ID, type LightState, type View } from "./gl/compositor.ts";
import { declutter, type Label } from "./labels.ts";
import { luxDate, params, seasonOf, today, type Season } from "./params.ts";
import { sunPosition, sunVector } from "./sun.ts";
import type { TransitData } from "./sim/transit.ts";
import { luxDayMask, luxSeconds } from "./sim/transit.ts";
import { TunnelIndex, type TunnelsData } from "./tunnels.ts";
import { Vehicles, type VehiclesData } from "./vehicles.ts";

const t0 = performance.now();
const canvas = document.getElementById("map") as HTMLCanvasElement;
const labelsEl = document.getElementById("labels") as HTMLDivElement;
const tipEl = document.getElementById("tip") as HTMLDivElement;
const DEBUG: Record<string, number> = { albedo: 1, layer: 2, shadow: 3, depth: 4, normal: 5, xid: DEBUG_XID, xdepth: DEBUG_XDEPTH };

declare global { interface Window { __v2: Record<string, unknown> } }
const hooks: Record<string, unknown> = {};
window.__v2 = hooks;

async function main() {
  const idx = await fetchJSON<ReleaseIndex>("index.json");
  const comp = new Compositor(canvas, idx);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const size = () => comp.resize(Math.round(canvas.clientWidth * dpr), Math.round(canvas.clientHeight * dpr));
  size();
  // ------------------------------------------------------------------ view
  const [ex0, ey0, ex1, ey1] = idx.extent_px;
  const fit = Math.min(comp.W / (ex1 - ex0), comp.H / (ey1 - ey0)) * 0.95;
  const view: View = { cx: (ex0 + ex1) / 2, cy: (ey0 + ey1) / 2, scale: fit };
  if (params.v1x !== null && params.v1y !== null) {
    const k = idx.camera.mpp > 0 ? 0.25 / idx.camera.mpp : 2;
    view.cx = (params.v1x + idx.camera.v1_offset_px[0]) * k; view.cy = (params.v1y + idx.camera.v1_offset_px[1]) * k;
    view.scale = 0.5;
  }
  if (params.x !== null) view.cx = params.x;
  if (params.y !== null) view.cy = params.y;
  if (params.z !== null) view.scale = params.z * dpr;
  // ------------------------------------------------------------------ clock and state
  const off = new Set(params.off);
  let hourOverride: number | null = params.hour;
  let season: Season | null = params.season;
  const st: LightState = { sun: [0, 0, 1], el: 45, az: 180, season: "summer", snow: params.snow, hour: 12,
    debug: DEBUG[params.debug] ?? 0, off, xray: false };
  // tunnel view (tunnel-view.md): the button or ?xray turns it on; holding X shows the other state while held
  const xrayCan = !!idx.tunnels && !!idx.config.xray && !!idx.palette.tunnel;
  let xrayOn = xrayCan && params.xray, xrayHeld = false;
  const setXray = () => { st.xray = xrayCan && xrayOn !== xrayHeld; dirty = true; };
  const now = () => {
    if (hourOverride === null) return params.date ? today() : new Date();
    const d = params.date ?? (() => { const t = new Date(); return { y: t.getFullYear(), m: t.getMonth() + 1, d: t.getDate() }; })();
    return luxDate(d.y, d.m, d.d, hourOverride);
  };
  const updateSun = () => {
    const t = now();
    const p = sunPosition(t);
    st.az = p.az; st.el = p.el; st.sun = sunVector(p.az, p.el);
    st.hour = luxSeconds(t) / 3600;
    st.season = season ?? seasonOf(t);
  };
  updateSun();
  comp.zTop = idx.config ? 0 : 0;
  // the highest anything stands (terrain + 80 m), as the reference march
  comp.zTop = 1e9;
  let dirty = true;
  comp.onTile = () => { dirty = true; };
  setXray();
  // ------------------------------------------------------------------ first view
  let first = 0;
  hooks.view = view; hooks.state = st; hooks.comp = comp; hooks.idx = idx;
  hooks.setView = (cx: number, cy: number, scale: number) => { view.cx = cx; view.cy = cy; view.scale = scale; dirty = true; };
  hooks.setHour = (h: number) => { hourOverride = h; updateSun(); dirty = true; };
  hooks.setOff = (names: string[]) => { off.clear(); names.forEach((n) => off.add(n)); dirty = true; };
  hooks.setDebug = (d: string) => { st.debug = DEBUG[d] ?? 0; dirty = true; };
  hooks.missing = () => comp.missing(view, off) + comp.pending;
  hooks.renderNow = () => { draw(); };
  hooks.setXray = (on: boolean) => { xrayOn = on; setXray(); };
  // ------------------------------------------------------------------ shadows (loaded after the first view)
  const loadShadows = async () => {
    const L = idx.light;
    const [A, B] = await Promise.all([fetchBin("shadow_a.bin", L.height, 4), fetchBin("shadow_b.bin", L.height, 4)]);
    if (A && B) {
      comp.setHeightMap(A, B);
      let tmax = -1e9;
      for (let i = 0; i < A.length; i += 4) tmax = Math.max(tmax, A[i] + A[i + 1] * 256);
      comp.zTop = L.zbase + tmax / 100 + 80;
      hooks.shadowsReady = true;
      dirty = true;
    }
  };
  // ------------------------------------------------------------------ night data
  const loadNight = async () => {
    const [w, l] = await Promise.all([fetchBytes("windows.bin"), fetchBytes("lamps.bin")]);
    comp.setWindows(new Float32Array(w));
    comp.setLamps(new Float32Array(l));
    dirty = true;
  };
  // ------------------------------------------------------------------ vehicles
  let veh: Vehicles | null = null;
  const loadVehicles = async () => {
    const [vd, td] = await Promise.all([fetchJSON<VehiclesData>("vehicles.json"), fetchJSON<TransitData>("transit.json")]);
    veh = new Vehicles(vd, td, params.seed ?? 20240607);
    veh.ring = idx.polygon_en.map(([e, n]) => [e - idx.camera.origin_en[0], n - idx.camera.origin_en[1]] as [number, number]);
    veh.tunnels = tunnels;
    // fill the streets: run the simulation for a while first
    const warm = params.nosim ? Math.min(params.simtime, 600) : params.simtime;
    for (let t = 0; t < warm; t += 0.1) veh.step(0.1, st.hour);
    veh.update(luxSeconds(now()), luxDayMask(now()));
    hooks.vehicles = veh;
    dirty = true;
  };
  // ------------------------------------------------------------------ tunnel view: the tubes
  let tunnels: TunnelIndex | null = null;
  const loadTunnels = async () => {
    if (!xrayCan) { hooks.tunnelsReady = true; return; }       // a release built before the tunnel view: none to wait for
    comp.enableXray();
    const td = await fetchJSON<TunnelsData>(idx.tunnels!.file);
    comp.setTunnels(td);
    tunnels = new TunnelIndex(td);
    if (veh) { veh.tunnels = tunnels; veh.update(luxSeconds(now()), luxDayMask(now())); }
    hooks.tunnels = td;
    hooks.tunnelsReady = true;
    dirty = true;
  };
  // ------------------------------------------------------------------ labels and hover (layer 8 on the CPU)
  let labels: Label[] = [];
  const bufCache = new Map<string, Promise<{ g: Uint8Array | null; i: Uint8Array | null } | null>>();
  const bufTile = (z: number, name: string) => {
    const key = `${z}/${name}`;
    if (!bufCache.has(key)) {
      const has = idx.layers.buffers.tiles[String(z)]?.[name] !== undefined;
      bufCache.set(key, has ? Promise.all([fetchBin(`buffers/${z}/${name}.g.bin`, 512, 4), fetchBin(`buffers/${z}/${name}.i.bin`, 512, 4)])
        .then(([g, i]) => ({ g, i })) : Promise.resolve(null));
    }
    return bufCache.get(key)!;
  };
  const bufDecoded = new Map<string, { g: Uint8Array | null; i: Uint8Array | null } | null>();
  const bufferAt = (mx: number, my: number, z: number) => {
    const size = 512 * 2 ** z, tx = Math.floor(mx / size), ty = Math.floor(my / size), name = `${tx}_${ty}`;
    const key = `${z}/${name}`;
    if (!bufDecoded.has(key)) { bufDecoded.set(key, null); bufTile(z, name).then((b) => { bufDecoded.set(key, b); dirty = true; }); }
    const b = bufDecoded.get(key);
    if (!b || !b.g) return null;
    const px = Math.floor((mx - tx * size) / 2 ** z), py = Math.floor((my - ty * size) / 2 ** z);
    const o = (py * 512 + px) * 4;
    const code = b.g[o] + b.g[o + 1] * 256;
    const dmin = idx.layers.buffers.tiles[String(z)][name];
    const id = b.i ? b.i[o] | (b.i[o + 1] << 8) | (b.i[o + 2] << 16) | (b.i[o + 3] << 24) : 0;
    const sy = idx.camera.frame.sy1 - (ty * 512 + py + 0.5) * 2 ** z * idx.camera.mpp;
    return { depth: code === 65535 ? Infinity : (code + dmin) / 100 + Math.sqrt(3) * sy, id: id >>> 0 };
  };
  hooks.bufferAt = bufferAt;
  const loadLabels = async () => { labels = await fetchJSON<Label[]>("labels.json"); dirty = true; };
  const measureCtx = document.createElement("canvas").getContext("2d")!;
  const placeLabels = () => {
    if (off.has("labels")) { labelsEl.replaceChildren(); return; }
    const z = comp.level(view);
    const shown = declutter(labels, view.scale, (l) => [(l.px - view.cx) * view.scale / dpr + comp.W / dpr / 2,
      (l.py - view.cy) * view.scale / dpr + comp.H / dpr / 2], (l) => {
      measureCtx.font = l.prio <= 2 ? "600 13px system-ui" : "12px system-ui";
      return measureCtx.measureText(l.name).width;
    }, (l) => {
      const b = bufferAt(l.px, l.py, z);
      return !!b && Number.isFinite(b.depth) && b.depth < l.depth - 1.5 * 2 ** z;
    }, { w: comp.W / dpr, h: comp.H / dpr });
    hooks.labelsShown = shown.map((s) => ({ name: s.l.name, box: s.box }));
    labelsEl.replaceChildren(...shown.map((s) => {
      const d = document.createElement("div");
      d.className = `lab p${Math.min(s.l.prio, 5)}`;
      d.dataset.cat = s.l.cat;
      d.style.left = `${s.x}px`; d.style.top = `${s.y}px`;
      if (s.l.prio <= 2) d.appendChild(document.createElement("i")).className = "pin";
      d.appendChild(document.createElement("span")).textContent = s.l.name;
      return d;
    }));
  };
  // ------------------------------------------------------------------ drawing
  const draw = () => {
    const t = performance.now();
    comp.render(view, st, veh && !off.has("vehicles") ? { count: veh.count, inst: veh.inst, size: veh.size, deep: veh.deep } : null);
    hooks.lastFrameMs = performance.now() - t;
    hooks.xrayDrawn = !!st.xray;
    placeLabels();
  };
  let lastT = performance.now();
  let frames = 0;
  const loop = () => {
    const t = performance.now();
    const dt = Math.min((t - lastT) / 1000, 0.1);
    lastT = t;
    if (veh && !params.nosim && !off.has("vehicles")) {
      if (hourOverride === null) updateSun();
      veh.step(dt, st.hour);
      const sec = hourOverride === null ? luxSeconds(now()) : (hourOverride * 3600 + (t - t0) / 1000) % 86400;
      veh.update(sec, luxDayMask(now()));
      dirty = true;
    }
    if (dirty) {
      dirty = false;
      draw();
      frames++;
      if (!first && comp.missing(view, off) === 0 && comp.pending === 0) {
        first = performance.now() - t0;
        hooks.firstViewMs = first;
        loadShadows().then(() => { hooks.shadowsMs = performance.now() - t0; });
        loadNight();
        loadLabels();
        loadVehicles();
        loadTunnels();
      }
    }
    hooks.frames = frames;
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
  // ------------------------------------------------------------------ navigation
  let drag: { x: number; y: number } | null = null;
  const pointers = new Map<number, { x: number; y: number }>();
  let pinch = 0;
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    drag = { x: e.clientX, y: e.clientY };
    if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch = Math.hypot(a.x - b.x, a.y - b.y); }
  });
  canvas.addEventListener("pointermove", (e) => {
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinch > 0) zoomAt((a.x + b.x) / 2, (a.y + b.y) / 2, d / pinch);
      pinch = d;
      return;
    }
    if (drag) {
      view.cx -= (e.clientX - drag.x) * dpr / view.scale; view.cy -= (e.clientY - drag.y) * dpr / view.scale;
      drag = { x: e.clientX, y: e.clientY };
      dirty = true;
    } else hover(e.clientX, e.clientY);
  });
  const end = (e: PointerEvent) => { pointers.delete(e.pointerId); if (!pointers.size) drag = null; pinch = 0; };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  const zoomAt = (x: number, y: number, k: number) => {
    const r = canvas.getBoundingClientRect();
    const sx = (x - r.left) * dpr, sy = (y - r.top) * dpr;
    const mx = view.cx + (sx - comp.W / 2) / view.scale, my = view.cy + (sy - comp.H / 2) / view.scale;
    view.scale = Math.max(0.01, Math.min(8, view.scale * k));
    view.cx = mx - (sx - comp.W / 2) / view.scale; view.cy = my - (sy - comp.H / 2) / view.scale;
    dirty = true;
  };
  canvas.addEventListener("wheel", (e) => { e.preventDefault(); zoomAt(e.clientX, e.clientY, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  window.addEventListener("resize", () => { size(); dirty = true; });
  // hover: what is under the pointer (layer 8 ids)
  const vd = { roads: new Map<number, string>() };
  const hover = (x: number, y: number) => {
    const r = canvas.getBoundingClientRect();
    const mx = view.cx + ((x - r.left) * dpr - comp.W / 2) / view.scale, my = view.cy + ((y - r.top) * dpr - comp.H / 2) / view.scale;
    const b = bufferAt(mx, my, comp.level(view));
    if (!b || !b.id) { tipEl.style.display = "none"; return; }
    const cls = b.id & 255, obj = b.id >>> 8;
    const names: Record<number, string> = { 1: "ground", 2: "wall", 3: "water", 4: "road", 5: "railway", 6: "tram line", 7: "path",
      8: "steps", 9: "bridge", 10: "tunnel portal", 11: "building", 12: "window", 13: "door", 14: "shop front", 15: "bridge",
      16: "viaduct pier", 17: "viaduct arch", 18: "tree", 19: "tree", 20: "parapet", 21: "lift", 22: "building", 23: "roof" };
    let text = names[cls] ?? "";
    if ((cls >= 4 && cls <= 9) && veh) {
      const e = (veh as Vehicles).data.edges[obj - 1];
      const road = (veh as Vehicles).roadById.get(obj - 1);
      text += road?.n ? `: ${road.n}` : e ? ` (${e.id})` : "";
    }
    void vd;
    tipEl.textContent = text;
    tipEl.style.display = text ? "block" : "none";
    tipEl.style.left = `${x + 12}px`; tipEl.style.top = `${y + 12}px`;
  };
  // ------------------------------------------------------------------ the panel
  const panel = document.getElementById("panel") as HTMLDivElement;
  if (!params.ui) panel.style.display = "none";
  const hourIn = document.getElementById("hour") as HTMLInputElement;
  const hourOut = document.getElementById("hourOut") as HTMLSpanElement;
  const showHour = () => { const h = st.hour; hourOut.textContent = `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.floor((h % 1) * 60)).padStart(2, "0")}`; };
  hourIn.value = String(st.hour);
  showHour();
  hourIn.addEventListener("input", () => { hourOverride = +hourIn.value; updateSun(); showHour(); dirty = true; });
  const seasonIn = document.getElementById("season") as HTMLSelectElement;
  seasonIn.value = season ?? "auto";
  seasonIn.addEventListener("change", () => { season = seasonIn.value === "auto" ? null : seasonIn.value as Season; updateSun(); dirty = true; });
  const snowIn = document.getElementById("snow") as HTMLInputElement;
  snowIn.checked = st.snow;
  snowIn.addEventListener("change", () => { st.snow = snowIn.checked; dirty = true; });
  const toggles = document.getElementById("toggles") as HTMLDivElement;
  const names = [...Object.keys(LAYER_ID), "light", "night", "seasons", "vehicles", "look", "labels"];
  if (xrayCan && idx.tunnels!.casemates) names.push("casemates");
  for (const n of names) {
    const lab = document.createElement("label");
    const box = lab.appendChild(document.createElement("input"));
    box.type = "checkbox"; box.dataset.l = n; box.checked = !off.has(n);
    lab.append(` ${n}`);
    toggles.appendChild(lab);
  }
  // tunnel view: the button, and X held
  const xrayBtn = document.getElementById("xray") as HTMLButtonElement;
  const showXray = () => { xrayBtn.setAttribute("aria-pressed", String(xrayOn)); };
  if (!xrayCan) (document.getElementById("xrayRow") as HTMLDivElement).style.display = "none";
  showXray();
  xrayBtn.addEventListener("click", () => {
    xrayOn = !xrayOn;
    setXray(); showXray();
    const u = new URL(location.href);                 // the state is in the address, so the view can be repeated
    if (xrayOn) u.searchParams.set("xray", ""); else u.searchParams.delete("xray");
    history.replaceState(null, "", u.pathname + u.search.replace(/=(?=&|$)/g, "") + u.hash);
  });
  const typing = (e: KeyboardEvent) => {
    const t = e.target;
    return t instanceof HTMLTextAreaElement || (t instanceof HTMLElement && t.isContentEditable)
      || (t instanceof HTMLInputElement && !["range", "checkbox", "radio", "button"].includes(t.type));
  };
  window.addEventListener("keydown", (e) => {
    if (e.key.toLowerCase() !== "x" || e.repeat || e.ctrlKey || e.metaKey || e.altKey || typing(e)) return;
    xrayHeld = true; setXray();
  });
  window.addEventListener("keyup", (e) => { if (e.key.toLowerCase() === "x" && xrayHeld) { xrayHeld = false; setXray(); } });
  window.addEventListener("blur", () => { if (xrayHeld) { xrayHeld = false; setXray(); } });
  toggles.addEventListener("change", (e) => {
    const t = e.target as HTMLInputElement;
    if (t.checked) off.delete(t.dataset.l!); else off.add(t.dataset.l!);
    dirty = true;
  });
  void BASE; void inflate; void undelta;
}

main().catch((e) => {
  const pre = document.body.appendChild(document.createElement("pre"));
  pre.className = "err";
  pre.textContent = String(e?.stack ?? e);
  hooks.error = String(e);
});
