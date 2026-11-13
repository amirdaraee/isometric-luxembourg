// The viewer's part of the landmark cutaways' checks K2, K5, K6 (v2/docs/specs/landmark-cutaways.md), called by
// v2/checks/cutaway_view_checks.py check_cutaways_view with a dev server running:
//   node scripts/cutaway_checks.mjs <base url> <out folder>
// Reads <out>/jobs.json (per landmark its view, probe vehicles and label points, written by the Python side) and
// writes <out>/view.json (counts) and frames <out>/<name>.rgb.z: zlib of the canvas's RGB rows, top row first.
// A debug=layer frame holds the layer in red (layer / 8) and the class in green (k / 16); debug=albedo the colour.
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { deflateSync } from "node:zlib";
import { open, settle } from "./shot.mjs";

const [base, out] = process.argv.slice(2);
const J = JSON.parse(readFileSync(join(out, "jobs.json"), "utf8"));
const [W, H] = J.size;
const res = { errors: [], frames: [], landmarks: {}, far: {} };
const { browser, page, errors } = await open(base, W, H);

async function grab() {
  const b64 = await page.evaluate(() => {
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

/** Set the viewer's state through its test hooks, wait for the view's tiles, draw. */
async function set(s) {
  await page.evaluate(async (s) => {
    const v = window.__v2;
    if (s.off) v.setOff(s.off);
    if (s.cut !== undefined) v.setCutaway(s.cut);
    if (s.xray !== undefined) v.setXray(s.xray);
    if (s.debug !== undefined) v.setDebug(s.debug);
    if (s.probes !== undefined) v.setProbes(s.probes ? s.probes.inst : null, s.probes ? s.probes.size : []);
    if (s.view) v.setView(s.view[0], s.view[1], s.view[2] ?? 1);
    const t0 = performance.now();
    do { await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); }
    while (v.missing() > 0 && performance.now() - t0 < 120000);
    v.renderNow();
  }, s);
}
async function go(q) {
  await page.goto(base + "?noui&nosim&" + q);
  await settle(page, { tunnels: true });
  await page.waitForTimeout(1500);                    // the night's windows and lamps are in
}

for (const [name, L] of Object.entries(J.landmarks)) {
  const r = { off_differs_px: {}, on_differs_px: {} };
  const view = [L.view[0], L.view[1], 1];
  for (const hour of J.hours) {
    // K6: a view that never had the cutaway on; then on; then off again
    await go(`hour=${hour}&date=${J.date}&x=${view[0]}&y=${view[1]}&z=1`);
    await set({ view, off: ["labels"] });
    const before = await grab();
    await set({ cut: [name] });
    const on = await grab();
    await set({ cut: false });
    const after = await grab();
    save(`${name}_${hour}_off`, before); save(`${name}_${hour}_on`, on);
    r.off_differs_px[hour] = differ(before, after);
    r.on_differs_px[hour] = differ(before, on);
    if (hour !== J.hours[0]) continue;
    // K2, and the whole frame against the tiles: what is drawn, and its colour
    await set({ cut: [name], off: ["labels", "vehicles"], debug: "layer" });
    save(`${name}_layer`, await grab());
    await set({ debug: "albedo" });
    save(`${name}_albedo`, await grab());
    // K5: the probe vehicles against the cutaway's depth
    await set({ off: ["labels"], debug: "layer", probes: L.probes });
    save(`${name}_probes`, await grab());
    await set({ probes: null });
    // K5: the label points
    r.labels_hidden = await page.evaluate(async (pts) => {
      const v = window.__v2;
      const t0 = performance.now();
      while (pts.some((p) => v.depthAt(p[0], p[1], 0) === null) && performance.now() - t0 < 60000) await new Promise((r) => setTimeout(r, 50));
      return pts.map((p) => (v.depthAt(p[0], p[1], 0) === null ? -1 : v.labelHidden(p[0], p[1], p[2], 0) ? 1 : 0));
    }, L.labels);
    // with layer 5 off the cutaway is off too
    await set({ off: ["labels", "vehicles", "buildings"], debug: "layer" });
    const noB = await grab();
    let n5 = 0;
    for (let i = 0; i < noB.length; i += 3) if (Math.round((noB[i] / 255) * 8) === 5) n5++;
    r.buildings_off_layer5_px = n5;
    // with the tunnel view: the cut building is part of the faded city
    const hasXray = await page.evaluate(() => !!window.__v2.idx.tunnels);
    if (hasXray) {
      await set({ off: ["labels"], debug: "", cut: false, xray: true });
      const x0 = await grab();
      await set({ cut: [name] });
      const x1 = await grab();
      await set({ cut: false });
      r.xray_on_differs_px = differ(x0, x1);
      r.xray_off_differs_px = differ(x0, await grab());
      await set({ xray: false });
      r.xray_then_off_differs_px = differ(before, await grab());
    }
  }
  // K3: the opening is lit by the sky only. Frames without the look pass, the night lights and the labels, so that
  // a pixel is its colour times its light: with the rule, with the opening lit as any building (?off=cutlight),
  // and what light the viewer says it gave the opening
  r.sky = {};
  for (const hour of J.sky_hours) {
    await go(`hour=${hour}&date=${J.sky_date}&x=${view[0]}&y=${view[1]}&z=1`);
    await set({ view, cut: [name], off: ["labels", "vehicles", "look", "night"], debug: "" });
    save(`${name}_sky_${hour}_lit`, await grab());
    r.sky[hour] = await page.evaluate(() => window.__v2.openLight());
    await set({ off: ["labels", "vehicles", "look", "night", "cutlight"] });
    save(`${name}_sky_${hour}_plain`, await grab());
  }
  res.landmarks[name] = r;
}
// far zoom: the merged far set is left while a cutaway is on, and comes back
{
  const [x, y, z] = J.whole;
  await go(`hour=${J.hours[0]}&date=${J.date}&x=${x}&y=${y}&z=${z}`);
  await set({ view: J.whole, off: ["labels"] });
  const before = await grab();
  await set({ cut: true });
  const on = await grab();
  save("far_on", on);
  await set({ cut: false });
  res.far = { on_differs_px: differ(before, on), off_differs_px: differ(before, await grab()) };
}
res.gpu = await page.evaluate(() => { const gl = document.createElement("canvas").getContext("webgl2");
  const e = gl.getExtension("WEBGL_debug_renderer_info"); return { renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : "?" }; });
res.errors = errors;
writeFileSync(join(out, "view.json"), JSON.stringify(res));
await browser.close();
console.log(JSON.stringify({ frames: res.frames.length, landmarks: Object.fromEntries(Object.entries(res.landmarks).map(([k, v]) => [k, { off: v.off_differs_px, on: v.on_differs_px }])), far: res.far }));
