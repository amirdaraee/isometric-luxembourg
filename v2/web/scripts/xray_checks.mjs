// The viewer's part of the tunnel view's checks X1-X8 (v2/docs/specs/tunnel-view.md), called by
// v2/checks/tunnel_checks.py check_tunnel_view with a dev server running:
//   node scripts/xray_checks.mjs <base url> <out folder>
// Reads <out>/jobs.json (the views, written by the Python side from the graph) and writes <out>/xray.json (counts
// and speed) and frames <out>/<name>.rgb.z: zlib of the canvas's RGB rows, top row first. A debug=xid frame holds
// class + 16 * depth step in red and the tube index in green and blue; a debug=xdepth frame the tubes' depth buffer.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { deflateSync } from "node:zlib";
import { open, settle } from "./shot.mjs";

const [base, out] = process.argv.slice(2);
const J = JSON.parse(readFileSync(join(out, "jobs.json"), "utf8"));
const [W, H] = J.size;
const DATE = J.date;
const res = { errors: [], frames: [], fade: [], layer_off: {}, tunnels_changed: {}, casemates: {}, vehicles: [], speed: {} };

const { browser, page, errors } = await open(base, W, H);

/** The canvas as RGB rows, top first. */
async function grab(pg = page) {
  const b64 = await pg.evaluate(() => {
    const c = document.getElementById("map");
    const gl = c.getContext("webgl2");
    const a = new Uint8Array(c.width * c.height * 4);
    gl.readPixels(0, 0, c.width, c.height, gl.RGBA, gl.UNSIGNED_BYTE, a);
    let s = "";
    for (let i = 0; i < a.length; i += 0x8000) s += String.fromCharCode.apply(null, a.subarray(i, i + 0x8000));
    return btoa(s);
  });
  const a = Buffer.from(b64, "base64");
  const rgb = Buffer.alloc(W * H * 3);
  for (let r = 0; r < H; r++) {
    const src = (H - 1 - r) * W * 4;                 // readPixels rows go bottom-up
    for (let c = 0; c < W; c++) { rgb[(r * W + c) * 3] = a[src + c * 4]; rgb[(r * W + c) * 3 + 1] = a[src + c * 4 + 1]; rgb[(r * W + c) * 3 + 2] = a[src + c * 4 + 2]; }
  }
  return rgb;
}
function save(name, rgb) {
  writeFileSync(join(out, `${name}.rgb.z`), deflateSync(rgb, { level: 1 }));
  res.frames.push(name);
}
const differ = (a, b) => { let n = 0; for (let i = 0; i < a.length; i += 3) if (a[i] !== b[i] || a[i + 1] !== b[i + 1] || a[i + 2] !== b[i + 2]) n++; return n; };

/** Set the viewer's state through its test hooks, wait for the view's tiles (unless tiles: false), draw. */
async function set(s, pg = page) {
  await pg.evaluate(async (s) => {
    const v = window.__v2;
    if (s.off) v.setOff(s.off);
    if (s.hour !== undefined) v.setHour(s.hour);
    if (s.xray !== undefined) v.setXray(s.xray);
    if (s.debug !== undefined) v.setDebug(s.debug);
    if (s.view) v.setView(s.view[0], s.view[1], s.view[2] ?? 1);
    if (s.tiles !== false) {
      const t0 = performance.now();
      while (v.missing() > 0 && performance.now() - t0 < 120000) await new Promise((r) => setTimeout(r, 50));
      await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    }
    v.renderNow();
  }, s);
}
async function go(q, opts = {}) {
  await page.goto(base + "?noui&" + q);
  await settle(page, { tunnels: true, ...opts });
}

// ---------------------------------------------------------------- X1, X2, X6, X7: the tubes alone, every view
// (the graph's tunnels without the casemates, which stand in front of some; then the views that hold casemates, with)
await go(`nosim&xray&off=vehicles&hour=13&date=${DATE}&x=${J.views[0][0]}&y=${J.views[0][1]}&z=1`, { vehicles: false });
for (const [name, off, list] of [["geo", ["vehicles", "casemates"], J.views.map((_, i) => i)], ["geoc", ["vehicles"], J.casemate_views]]) {
  await set({ off, tiles: false });
  for (const i of list) {
    await set({ view: [J.views[i][0], J.views[i][1], 1], debug: "xid", tiles: false });
    save(`${name}_${i}_id`, await grab());
    await set({ debug: "xdepth", tiles: false });
    save(`${name}_${i}_depth`, await grab());
  }
}

// ---------------------------------------------------------------- X7: the casemates only in tunnel view
{
  const [x, y] = J.bock;
  const from = J.casemate_from;
  const count = (rgb, f) => { let n = 0; for (let i = 0; i < rgb.length; i += 3) if (f(rgb[i], rgb[i + 1] + 256 * rgb[i + 2])) n++; return n; };
  await set({ view: [x, y, 1], debug: "xid", xray: true, off: ["vehicles"], tiles: false });
  res.casemates.on_px = count(await grab(), (r, idx) => r > 0 && idx >= from);
  await set({ off: ["vehicles", "casemates"], tiles: false });
  res.casemates.switched_off_px = count(await grab(), (r, idx) => r > 0 && idx >= from);
  await set({ xray: false, off: ["vehicles"], tiles: false });
  res.casemates.view_off_px = count(await grab(), (r) => r > 0);
  await set({ xray: true, debug: "" });
}

// ---------------------------------------------------------------- X3: vehicles in tunnels, still frames
for (const hour of J.vehicle_hours) {
  await go(`nosim&xray&hour=${hour}&date=${DATE}&simtime=600&x=${J.views[0][0]}&y=${J.views[0][1]}&z=1`, { vehicles: true });
  const veh = await page.evaluate(() => {
    const v = window.__v2.vehicles, c = window.__v2.idx.camera;
    return { count: v.count, inst: Array.from(v.inst.subarray(0, v.count * 4)), size: Array.from(v.size.subarray(0, v.count * 4)),
      deep: Array.from(v.deep.subarray(0, v.count)), camera: c };
  });
  // the views that hold a vehicle in a tunnel
  const R2 = Math.SQRT1_2, C30 = Math.sqrt(3) / 2, c = veh.camera;
  const used = [];
  for (const [i, [x, y]] of J.views.entries()) {
    let n = 0;
    for (let k = 0; k < veh.count; k++) {
      if (!veh.deep[k]) continue;
      const le = veh.inst[k * 4], ln = veh.inst[k * 4 + 1], z = veh.inst[k * 4 + 2];
      const px = ((le + ln) * R2 - c.frame.sx0) / c.mpp, py = (c.frame.sy1 - ((ln - le) * R2 * 0.5 + z * C30)) / c.mpp;
      if (Math.abs(px - x) < W / 2 && Math.abs(py - y) < H / 2) n++;
    }
    if (!n) continue;
    await set({ view: [x, y, 1], debug: "xid", tiles: false });
    save(`veh_${hour}_${i}_id`, await grab());
    await set({ debug: "xdepth", tiles: false });
    save(`veh_${hour}_${i}_depth`, await grab());
    used.push(i);
  }
  res.vehicles.push({ hour, count: veh.count, inst: veh.inst, size: veh.size, deep: veh.deep, views: used });
}

// ---------------------------------------------------------------- X5: every layer off stays off in tunnel view
{
  await go(`nosim&xray&hour=13&date=${DATE}&x=${J.whole[0]}&y=${J.whole[1]}&z=${J.whole[2]}`, { vehicles: true });
  for (const [i, L] of J.layers.entries()) {
    await set({ off: [L, "vehicles"], debug: "layer", view: J.whole });
    const px = await grab();
    const want = Math.round(((i + 1) / 8) * 255);
    let n = 0;
    for (let k = 0; k < px.length; k += 3) if (Math.abs(px[k] - want) <= 1 && !(px[k] === 239 && px[k + 1] === 232)) n++;
    res.layer_off[L] = n;
  }
  // the tunnels and their vehicles are the same whatever layer is off; the city is the faded frame of that state
  const [x, y] = J.busy;
  await set({ off: [], debug: "xid", view: [x, y, 1], tiles: false });
  const id0 = await grab();
  await set({ debug: "xdepth", tiles: false });
  const d0 = await grab();
  for (const L of J.layers) {
    await set({ off: [L], debug: "xid", tiles: false });
    const id = await grab();
    await set({ debug: "xdepth", tiles: false });
    res.tunnels_changed[L] = differ(id0, id) + differ(d0, await grab());
    await set({ debug: "", xray: true });
    save(`off_${L}_xray`, await grab());
    save(`off_${L}_id`, id);
    await set({ xray: false });
    save(`off_${L}_plain`, await grab());
    await set({ xray: true });
  }
}

// ---------------------------------------------------------------- X4: the fade, and off is as it was
for (const f of J.fade_views) {
  await page.goto(base + `?noui&nosim&hour=${f.hour}&date=${DATE}&x=${f.x}&y=${f.y}&z=1`);          // the view never on yet
  await settle(page, { tunnels: true });
  await page.waitForTimeout(1500);                    // the night's windows and lamps are in
  await set({ view: [f.x, f.y, 1] });
  const before = await grab();
  await set({ xray: true });
  const on = await grab();
  await set({ debug: "xid", tiles: false });
  const id = await grab();
  await set({ debug: "", xray: false });
  const after = await grab();
  save(`fade_${f.name}_plain`, before); save(`fade_${f.name}_xray`, on); save(`fade_${f.name}_id`, id);
  res.fade.push({ name: f.name, hour: f.hour, x: f.x, y: f.y, off_differs_px: differ(before, after), on_differs_px: differ(before, on) });
}

// ---------------------------------------------------------------- X8: speed
{
  const ctx2 = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const p2 = await ctx2.newPage();
  p2.on("pageerror", (e) => errors.push(String(e)));
  await p2.goto(base + `?noui&hour=13&date=${DATE}&x=${J.busy[0]}&y=${J.busy[1]}&z=1`);
  await settle(p2, { tunnels: true });
  // turning the view on and off: frames until the frame with the new state is drawn
  res.speed.toggle = await p2.evaluate(async () => {
    const v = window.__v2, out = [];
    for (let k = 0; k < 10; k++) {
      const on = k % 2 === 0;
      await new Promise((r) => requestAnimationFrame(r));
      const t0 = performance.now();
      v.setXray(on);
      let frames = 0;
      while (v.xrayDrawn !== on && frames < 100) { await new Promise((r) => requestAnimationFrame(r)); frames++; }
      out.push({ on, frames, ms: performance.now() - t0 });
    }
    return out;
  });
  const pan = (scale) => p2.evaluate(async (scale) => {
    const v = window.__v2;
    const [x0, y0, x1, y1] = v.idx.extent_px;
    v.setXray(true);
    v.setView((x0 + x1) / 2, (y0 + y1) / 2, scale);
    await new Promise((r) => setTimeout(r, 1500));
    let frames = 0;
    const t0 = performance.now();
    await new Promise((resolve) => {
      const step = () => {
        const t = performance.now() - t0;
        v.setView((x0 + x1) / 2 + Math.sin(t / 700) * 600, (y0 + y1) / 2 + Math.cos(t / 900) * 300, scale);
        frames++;
        if (t < 4000) requestAnimationFrame(step); else resolve();
      };
      requestAnimationFrame(step);
    });
    const fps = frames / ((performance.now() - t0) / 1000);
    const gl = document.getElementById("map").getContext("webgl2");
    const ts = [];
    for (let i = 0; i < 20; i++) { const a = performance.now(); v.renderNow(); gl.finish(); ts.push(performance.now() - a); }
    ts.sort((a, b) => a - b);
    return { fps, frame_ms_median: ts[10], tiles_missing: v.missing(), xray: v.state.xray, tunnel_vehicles: v.comp.stats.tunnelVehicles };
  }, scale);
  res.speed.pan_whole_area = await pan(0.16);
  res.speed.pan_zoom1 = await pan(1.0);
  res.speed.pan_fps = Math.min(res.speed.pan_whole_area.fps, res.speed.pan_zoom1.fps);
  res.speed.viewport = "1600x1000 CSS px, device pixel ratio 1";
  await ctx2.close();
}
res.gpu = await page.evaluate(() => { const gl = document.createElement("canvas").getContext("webgl2");
  const e = gl.getExtension("WEBGL_debug_renderer_info"); return { renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : "?",
    ua: navigator.userAgent }; });
res.errors = errors;
writeFileSync(join(out, "xray.json"), JSON.stringify(res));
await browser.close();
console.log(JSON.stringify({ frames: res.frames.length, fade: res.fade, speed: res.speed }));
