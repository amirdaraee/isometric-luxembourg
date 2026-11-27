// The viewer's part of gate G1 (called by v2/checks/g1_checks.py check_viewer, with a dev server running):
//   node scripts/viewer_checks.mjs <base url> <out folder>
// Writes <out>/viewer.json and the shadow masks the Python side compares with its reference (shadow_<name>.bin:
// one byte per pixel, 255 lit, 0 in shadow; with shadow_<name>.json: the view, the hour and the date).
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { open, settle } from "./shot.mjs";

const [base, out] = process.argv.slice(2);
const W = 1024, H = 768;
const DATE = "2026-06-21";
const res = { errors: [], layer_off: {}, speed: {} };

const { browser, page, errors } = await open(base, W, H);

async function go(q, opts = {}) {
  await page.goto(base + "?noui&" + q);
  await settle(page, opts);
}
const pixels = () => page.evaluate(() => {
  const c = document.getElementById("map");
  const gl = c.getContext("webgl2");
  const a = new Uint8Array(c.width * c.height * 4);
  gl.readPixels(0, 0, c.width, c.height, gl.RGBA, gl.UNSIGNED_BYTE, a);
  return Array.from(a);
});

// ---------------------------------------------------------------- speed
{
  const ctx2 = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  const p2 = await ctx2.newPage();
  await p2.goto(base + "?noui");
  await settle(p2, { vehicles: false, shadows: false });
  res.speed.first_view_cold_s = (await p2.evaluate(() => window.__v2.firstViewMs)) / 1000;
  await p2.reload();
  await settle(p2, { vehicles: true, shadows: true });
  res.speed.first_view_warm_s = (await p2.evaluate(() => window.__v2.firstViewMs)) / 1000;
  const pan = async (scale) => p2.evaluate(async (scale) => {
    const v = window.__v2;
    const [x0, y0, x1, y1] = v.idx.extent_px;
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
    // GPU time of one full frame (all passes), blocking
    const gl = document.getElementById("map").getContext("webgl2");
    const ts = [];
    for (let i = 0; i < 20; i++) { const a = performance.now(); v.renderNow(); gl.finish(); ts.push(performance.now() - a); }
    ts.sort((a, b) => a - b);
    return { fps, frame_ms_median: ts[10], tiles_missing: v.missing() };
  }, scale);
  res.speed.pan_whole_area = await pan(0.16);
  res.speed.pan_zoom1 = await pan(1.0);
  res.speed.pan_fps = Math.min(res.speed.pan_whole_area.fps, res.speed.pan_zoom1.fps);
  const cdp = await ctx2.newCDPSession(p2);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  res.speed.throttled = { cpu_slowdown: 4, pan_zoom1: await pan(1.0) };
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  res.speed.viewport = "1600x1000 CSS px, device pixel ratio 1";
  await ctx2.close();
}
// ---------------------------------------------------------------- a large window (C5)
// A 2552 x 1278 window at two device pixels a pixel asks for some 2,000 files in its first view. A browser refuses
// requests beyond what it will hold (net::ERR_INSUFFICIENT_RESOURCES): the viewer has to load them a few at a time
// (src/loadq.ts) and lose none, or the view keeps holes and never gets its shadows.
{
  const ctx3 = await browser.newContext({ viewport: { width: 2552, height: 1278 }, deviceScaleFactor: 2 });
  const p3 = await ctx3.newPage();
  let requests = 0, failed = 0;
  p3.on("request", () => requests++);
  p3.on("requestfailed", () => failed++);
  await p3.goto(base + `?noui&nosim&x=62900&y=33750&z=0.5&hour=13&date=${DATE}`);
  let timed_out = false;
  try {
    await p3.waitForFunction(() => window.__v2 && (window.__v2.error || (window.__v2.shadowsReady && window.__v2.missing() === 0)),
      null, { timeout: 120000 });
  } catch { timed_out = true; }
  res.large = await p3.evaluate(() => {
    const v = window.__v2;
    let tiles = 0, waiting = 0;
    for (const t of v.comp.tiles.values()) { tiles++; if (!t.ready) waiting++; }
    return { tiles, tiles_waiting: waiting, view_tiles_missing: v.missing(), shadows: !!v.shadowsReady,
      first_view_s: v.firstViewMs ? v.firstViewMs / 1000 : null, error: v.error ?? null };
  });
  Object.assign(res.large, { requests, requests_failed: failed, timed_out, viewport: "2552x1278 CSS px, device pixel ratio 2" });
  await ctx3.close();
}
// ---------------------------------------------------------------- review notes and the address (C6)
// ?review: a right-click on a place asks for a note; its pin stands on the place and moves with the map; the notes
// are kept over a reload. The address follows the view, and opened anew gives the same view. Without ?review there
// is none of it.
{
  const ctx4 = await browser.newContext({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 1 });
  const faults = [];
  const ready = (p) => p.waitForFunction(() => window.__v2 && (window.__v2.error || window.__v2.firstViewMs > 0), null, { timeout: 60000 });
  const pins = (p) => p.$$eval(".note", (els) => els.map((e) => [parseFloat(e.style.left), parseFloat(e.style.top)]));
  const near = (a, x, y) => a && Math.hypot(a[0] - x, a[1] - y) <= 1;
  const q = `nosim&x=62900&y=33750&z=1&hour=13&date=${DATE}`;
  let address = null, note = null;
  try {
    const p4 = await ctx4.newPage();
    await p4.route("**/notes", (r) => r.abort());            // the dev server's copy of the notes is not this check's to write
    await p4.goto(base + "?review&" + q);
    await ready(p4);
    await p4.mouse.click(700, 450, { button: "right" });
    await p4.waitForSelector("#noteBox:not([hidden])", { timeout: 5000 });
    await p4.fill("#noteText", "a note on this place");
    await p4.press("#noteText", "Enter");
    let at = await pins(p4);
    if (at.length !== 1 || !near(at[0], 700, 450)) faults.push(`the pin is not on the place clicked: ${JSON.stringify(at)}`);
    note = (await p4.evaluate(() => window.__v2.notes()))[0] ?? null;
    if (!note || note.x !== 63000 || note.y !== 33800 || note.z !== 1 || note.hour !== 13 || note.date !== DATE)
      faults.push(`the note is not the place, scale, hour and date: ${JSON.stringify(note)}`);
    await p4.mouse.move(600, 400); await p4.mouse.down(); await p4.mouse.move(500, 340, { steps: 4 }); await p4.mouse.up();
    await p4.waitForTimeout(700);
    at = await pins(p4);
    if (!near(at[0], 600, 390)) faults.push(`the pin did not move with the map: ${JSON.stringify(at)}`);
    address = await p4.evaluate(() => location.search);
    const want = `?review&nosim&x=63000&y=33810&z=1&hour=13&date=${DATE}`;
    if (address !== want) faults.push(`the address did not follow the view: ${address}, not ${want}`);
    const p5 = await ctx4.newPage();                          // the address opened anew: the same view, the note kept
    await p5.route("**/notes", (r) => r.abort());
    await p5.goto(base + address);
    await ready(p5);
    const v = await p5.evaluate(() => ({ cx: window.__v2.view.cx, cy: window.__v2.view.cy, scale: window.__v2.view.scale,
      notes: window.__v2.notes().length, link: window.__v2.noteLink(0) }));
    if (v.cx !== 63000 || v.cy !== 33810 || v.scale !== 1) faults.push(`the address opens another view: ${JSON.stringify(v)}`);
    if (v.notes !== 1) faults.push(`the note was not kept: ${v.notes} notes`);
    if (!v.link.endsWith(`?x=63000&y=33800&z=1&hour=13&date=${DATE}&review`)) faults.push(`the note's link: ${v.link}`);
    if (!near((await pins(p5))[0], 600, 390)) faults.push("the kept note's pin is not on its place");
    const p6 = await ctx4.newPage();                          // without ?review: no notes, a right-click asks for none
    await p6.goto(base + "?" + q);
    await ready(p6);
    await p6.mouse.click(700, 450, { button: "right" });
    await p6.waitForTimeout(200);
    const plain = await p6.evaluate(() => ({ panel: document.getElementById("review").hidden, box: document.getElementById("noteBox").hidden,
      pins: document.querySelectorAll(".note").length }));
    if (!plain.panel || !plain.box || plain.pins) faults.push(`notes without ?review: ${JSON.stringify(plain)}`);
  } catch (e) { faults.push(`the check stopped: ${String(e).slice(0, 300)}`); }
  res.notes = { faults, address, note };
  await ctx4.close();
}
res.gpu = await page.evaluate(() => { const gl = document.createElement("canvas").getContext("webgl2");
  const e = gl.getExtension("WEBGL_debug_renderer_info"); return { renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : "?",
    ua: navigator.userAgent }; });

// ---------------------------------------------------------------- layers off leave no trace (debug=layer: red = layer / 8)
const LAYERS = ["ground", "relief", "water", "transport", "buildings", "structures", "trees"];
await go(`nosim&hour=13&date=${DATE}&z=0.25`, { vehicles: false });
const ext = await page.evaluate(() => window.__v2.idx.extent_px);
const cx = Math.round((ext[0] + ext[2]) / 2), cy = Math.round((ext[1] + ext[3]) / 2);
for (const [i, L] of LAYERS.entries()) {
  await go(`nosim&off=${L},vehicles&debug=layer&hour=13&date=${DATE}&x=${cx}&y=${cy}&z=0.25`, { vehicles: false });
  const px = await pixels();
  const want = Math.round(((i + 1) / 8) * 255);
  let n = 0;
  for (let k = 0; k < px.length; k += 4) if (Math.abs(px[k] - want) <= 1 && px[k + 3] === 255 && !(px[k] === 239 && px[k + 1] === 232)) n++;
  res.layer_off[L] = n;
}

// ---------------------------------------------------------------- shadow masks for the reference (zoom-0 pixels)
const x0 = 62600 - W / 2, y0 = 34400 - H / 2;     // the Grund, Neumuenster and the Rham
async function mask(name, q) {
  await go(`nosim&debug=shadow&date=${DATE}&x=${x0 + W / 2}&y=${y0 + H / 2}&z=1&${q}`, { vehicles: false });
  const px = await pixels();
  const m = new Uint8Array(W * H);
  // readPixels rows go bottom-up
  for (let r = 0; r < H; r++) for (let c = 0; c < W; c++) m[r * W + c] = px[((H - 1 - r) * W + c) * 4];
  writeFileSync(join(out, `shadow_${name}.bin`), m);
  writeFileSync(join(out, `shadow_${name}.json`), JSON.stringify({ x0, y0, W, H, date: DATE, q }));
}
await mask("10", "hour=10");
await mask("16", "hour=16");
await mask("13", "hour=13");
await mask("16_nobuildings", "hour=16&off=buildings");

// ---------------------------------------------------------------- no light by day; seasons only on their masks
async function shot(q) { await go(`nosim&date=${DATE}&x=${x0 + W / 2}&y=${y0 + H / 2}&z=1&${q}`, { vehicles: true }); return pixels(); }
{
  const a = await shot("hour=13"), b = await shot("hour=13&off=night");
  let n = 0;
  for (let k = 0; k < a.length; k++) if (a[k] !== b[k]) n++;
  res.night_by_day = n;
  // the day frame itself, for the look's idempotence (Python side)
  writeFileSync(join(out, "day_13.bin"), Uint8Array.from(a));
  // the light pass alone (no look, labels, vehicles or night) and the surfaces' own colours, for the hue of what is lit
  // to the top (Python side)
  const quiet = async (q) => { await go(`nosim&date=${DATE}&x=${x0 + W / 2}&y=${y0 + H / 2}&z=1&off=look,labels,vehicles,night&${q}`, { vehicles: false }); return pixels(); };
  writeFileSync(join(out, "lit_13.bin"), Uint8Array.from(await quiet("hour=13")));
  writeFileSync(join(out, "albedo_13.bin"), Uint8Array.from(await quiet("hour=13&debug=albedo")));
}
{
  const cls = await shot("hour=13&debug=layer");
  const s = await shot("hour=13&season=summer"), au = await shot("hour=13&season=autumn"), wi = await shot("hour=13&season=winter");
  let n = 0;
  for (let k = 0; k < s.length; k += 4) {
    const layer = Math.round(cls[k] / 255 * 8), kk = Math.round(cls[k + 1] / 255 * 16);
    const allowed = (layer === 7 && kk >= 1 && kk <= 4) || (layer === 1 && kk >= 6 && kk <= 12);
    if (allowed) continue;
    for (const o of [au, wi]) if (o[k] !== s[k] || o[k + 1] !== s[k + 1] || o[k + 2] !== s[k + 2]) { n++; break; }
  }
  res.season_outside = n;
}

// ---------------------------------------------------------------- labels never overlap
{
  let overlaps = 0;
  const views = [[cx, cy, 0.12], [cx, cy, 0.3], [62600, 34400, 0.6], [61000, 33200, 1.0]];
  for (const [x, y, z] of views) {
    await go(`nosim&hour=13&date=${DATE}&x=${x}&y=${y}&z=${z}`, { vehicles: false });
    await page.waitForFunction(() => window.__v2.labelsShown && window.__v2.labelsShown.length > 0, null, { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(800);
    const boxes = await page.evaluate(() => window.__v2.labelsShown ?? []);
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].box, b = boxes[j].box;
      if (a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1) overlaps++;
    }
  }
  res.label_overlaps = overlaps;
}
res.errors = errors;
writeFileSync(join(out, "viewer.json"), JSON.stringify(res, null, 1));
await browser.close();
console.log(JSON.stringify(res.speed));
