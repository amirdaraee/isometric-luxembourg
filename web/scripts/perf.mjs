#!/usr/bin/env node
// Timing harness: loads a build with every feature on, measures start-up on a fast 4G line, then idles, pans from
// the old town to Kirchberg and zooms in and out, at 21:00 and again at noon, and records frame intervals, main
// thread time per frame, long tasks, the JS heap, bytes and tiles loaded, and the per-layer times from src/perf.ts.
//
//   node scripts/perf.mjs --label baseline                 measure the current dist/ (vite preview on --port)
//   node scripts/perf.mjs --build --label after            build first (every feature on except perfHud)
//   node scripts/perf.mjs --label after --compare baseline also print the differences from an older run
//   node scripts/perf.mjs --compare-only baseline --label after   compare two saved runs, no new run
//   node scripts/perf.mjs --url http://localhost:3000 ...  measure a server that is already running
//
// Other options: --port 3019, --profiles desktop,phone (default both), --headed (a visible Chrome window: real
// GPU drawing; headless Chrome may draw WebGL in software), --quick (shorter phases, for a smoke test),
// --off clouds,tiltShift (switch features off, to measure their share), --query "hour=8" (added to every address),
// --force (replace a run).
// Output: data/work/perf/<date>-<label>.json, and a Markdown table of the main numbers next to it (.md).
//
// Profiles: desktop is 1440 x 900 at device pixel ratio 2; "mid phone" is 390 x 844 at ratio 3 with the CPU
// slowed four times. Start-up is measured with the cache off on a fast 4G line (9 Mbit/s down, 1.5 up, 60 ms).
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = resolve(WEB, "..");
const OUT = join(ROOT, "data/work/perf");

function args(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) continue;
    const [k, v] = a.slice(2).split("=", 2);
    if (v !== undefined) o[k] = v;
    else if (argv[i + 1] && !argv[i + 1].startsWith("--")) o[k] = argv[++i];
    else o[k] = true;
  }
  return o;
}

const opt = args(process.argv.slice(2));
const label = String(opt.label ?? "run").replace(/[^\w.-]+/g, "-");
const today = new Date().toISOString().slice(0, 10);
const port = +(opt.port ?? 3019);
const quick = !!opt.quick;

const PROFILES = {
  desktop: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, isMobile: false, hasTouch: false, cpu: 1,
    budget: { p95: 20, main: 6 } },
  phone: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true, cpu: 4,
    budget: { p95: 40, main: 12 } },
};
const FAST_4G = { offline: false, latency: 60, downloadThroughput: (9e6 / 8), uploadThroughput: (1.5e6 / 8) };
const BUDGET_START_MS = 2500;   // first painted map, fast 4G
const BUDGET_LONG_MS = 200;     // no long task over this after the first paint

const OLD_TOWN = [7615, 5801], KIRCHBERG = [19074, 6176], Z0 = 0.55;
const IDLE_MS = quick ? 3000 : 10000, PAN_MS = quick ? 3000 : 8000, ZOOM_MS = quick ? 3000 : 6000;

/** Every switch in src/features.ts except perfHud, so the measurement also works against a release build. */
function allFeatures() {
  const src = readFileSync(join(WEB, "src/features.ts"), "utf8");
  const body = src.slice(src.indexOf("DEFAULTS = {"), src.indexOf("};", src.indexOf("DEFAULTS = {")));
  return [...body.matchAll(/^\s+(\w+):\s*(true|false)/gm)].map((m) => m[1]).filter((k) => k !== "perfHud");
}

function findRun(name) {
  const f = (n) => join(OUT, n.endsWith(".json") ? n : `${n}.json`);
  if (existsSync(f(name))) return f(name);
  const hits = existsSync(OUT) ? readdirSync(OUT).filter((d) => d.endsWith(`-${name}.json`)).sort() : [];
  return hits.length ? join(OUT, hits[hits.length - 1]) : null;
}

async function waitFor(url, ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { if ((await fetch(url)).ok) return; } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`no answer from ${url} after ${ms / 1000} s`);
}

function build() {
  console.log("building (every feature on)");
  const r = spawnSync("npx", ["vite", "build"], { cwd: WEB, env: { ...process.env, VITE_FEATURES_OFF: "perfHud" }, stdio: "inherit" });
  if (r.status !== 0) throw new Error("build failed");
}

const pct = (s, p) => (s.length ? s[Math.min(s.length - 1, Math.round((s.length - 1) * p))] : 0);
function stats(v) {
  const s = [...v].sort((a, b) => a - b);
  const mean = s.length ? s.reduce((a, b) => a + b, 0) / s.length : 0;
  return { n: s.length, mean, p50: pct(s, 0.5), p90: pct(s, 0.9), p95: pct(s, 0.95), p99: pct(s, 0.99), max: s[s.length - 1] ?? 0 };
}
const r1 = (x) => Math.round(x * 10) / 10;
const r2 = (x) => Math.round(x * 100) / 100;

async function metrics(cdp) {
  const { metrics: m } = await cdp.send("Performance.getMetrics");
  return Object.fromEntries(m.map((x) => [x.name, x.value]));
}

/** Waits until the map's first view has fully loaded (the map-loaded mark from IsometricMap.tsx). */
async function waitMapLoaded(page, ms) {
  await page.waitForFunction(() => performance.getEntriesByName("map-loaded").length > 0, null, { timeout: ms, polling: 100 })
    .catch(() => console.log("  (the first view did not finish loading in time)"));
}

// In the page: move the view along a path, time-based, one immediate step per animation frame.
const MOVE = ({ keys, ms }) => new Promise((done) => {
  const { viewer: v, OpenSeadragon: O } = window.__iso;
  const b = v.world.getItemAt(0);
  const t0 = performance.now();
  const ease = (f) => (f < 0.5 ? 2 * f * f : 1 - 2 * (1 - f) * (1 - f));
  const step = () => {
    const f = Math.min(1, (performance.now() - t0) / ms);
    // keys: [[x, y, z], ...] evenly spaced in time; zoom moves geometrically
    const seg = Math.min(keys.length - 2, Math.floor(f * (keys.length - 1)));
    const g = ease(f * (keys.length - 1) - seg);
    const [x0, y0, z0] = keys[seg], [x1, y1, z1] = keys[seg + 1];
    const z = z0 * Math.pow(z1 / z0, g);
    v.viewport.zoomTo(b.imageToViewportZoom(z), undefined, true);
    v.viewport.panTo(b.imageToViewportCoordinates(new O.Point(x0 + (x1 - x0) * g, y0 + (y1 - y0) * g)), true);
    if (f < 1) requestAnimationFrame(step); else done();
  };
  requestAnimationFrame(step);
});

async function phase(page, cdp, net, name, prof, act) {
  await page.evaluate(() => { window.__perf.reset(); window.__perf.startRecord(); window.__phaseT0 = performance.now(); });
  const m0 = await metrics(cdp), b0 = net.bytes, t0 = net.tiles, q0 = net.requests;
  await act();
  const r = await page.evaluate(() => ({
    intervals: window.__perf.stopRecord(), snap: window.__perf.snapshot(), long: window.__perf.longTasksSince(window.__phaseT0),
  }));
  const m1 = await metrics(cdp);
  const fr = stats(r.intervals);
  const frames = Math.max(1, fr.n);
  const out = {
    frames: fr.n, fps: r1(fr.mean ? 1000 / fr.mean : 0),
    frame: { p50: r1(fr.p50), p90: r1(fr.p90), p95: r1(fr.p95), p99: r1(fr.p99), max: r1(fr.max) },
    slowShare: r2(r.intervals.filter((x) => x > prof.budget.p95).length / frames),
    // main-thread work per frame, from Chrome's own task accounting (ms)
    mainMsPerFrame: r2(((m1.TaskDuration - m0.TaskDuration) * 1000) / frames),
    scriptMsPerFrame: r2(((m1.ScriptDuration - m0.ScriptDuration) * 1000) / frames),
    styleLayoutMsPerFrame: r2((((m1.RecalcStyleDuration - m0.RecalcStyleDuration) + (m1.LayoutDuration - m0.LayoutDuration)) * 1000) / frames),
    longTasks: { count: r.long.length, maxMs: Math.round(Math.max(0, ...r.long.map((t) => t.ms))), over200: r.long.filter((t) => t.ms > BUDGET_LONG_MS).length },
    heapMB: r1(m1.JSHeapUsedSize / 1048576),
    bytesKB: Math.round((net.bytes - b0) / 1024), requests: net.requests - q0, tiles: net.tiles - t0,
    layers: Object.fromEntries(Object.entries(r.snap.layers).map(([k, v]) => [k, { mean: r2(v.mean), p95: r2(v.p95) }])),
    gauges: Object.fromEntries(Object.entries(r.snap.gauges).map(([k, v]) => [k, r1(v)])),
  };
  out.withinBudget = out.frame.p95 <= prof.budget.p95 && out.mainMsPerFrame <= prof.budget.main;
  console.log(`  ${name.padEnd(12)} ${String(out.fps).padStart(5)} fps  p50 ${out.frame.p50}  p95 ${out.frame.p95}  max ${out.frame.max} ms` +
    `  main ${out.mainMsPerFrame} ms/frame  long ${out.longTasks.count}  heap ${out.heapMB} MB  ${out.bytesKB} KB  ${out.tiles} tiles` +
    `${out.withinBudget ? "" : "  OVER BUDGET"}`);
  return out;
}

async function runProfile(browser, base, name, query) {
  const prof = PROFILES[name];
  const ctx = await browser.newContext({ viewport: prof.viewport, deviceScaleFactor: prof.deviceScaleFactor, isMobile: prof.isMobile, hasTouch: prof.hasTouch });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const cdp = await ctx.newCDPSession(page);
  const net = { bytes: 0, requests: 0, tiles: 0, kinds: {}, files: [] };
  const urls = new Map();
  await cdp.send("Network.enable");
  await cdp.send("Performance.enable");
  cdp.on("Network.requestWillBeSent", (e) => urls.set(e.requestId, e.request.url));
  cdp.on("Network.loadingFinished", (e) => {
    const u = urls.get(e.requestId) ?? "";
    net.bytes += e.encodedDataLength; net.requests++;
    if (/\/tiles\/.*\.webp/.test(u)) net.tiles++;
    // what the bytes are: tiles, code, data, sprites and so on (the first folder of the path)
    const path = u.replace(/^[a-z]+:\/\/[^/]+/i, "").split("?")[0];
    const kind = path.split("/")[1] || "page";
    net.kinds[kind] = (net.kinds[kind] ?? 0) + e.encodedDataLength;
    net.files.push([path, e.encodedDataLength]);
  });
  if (prof.cpu > 1) await cdp.send("Emulation.setCPUThrottlingRate", { rate: prof.cpu });
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Network.emulateNetworkConditions", FAST_4G);
  console.log(`${name}: ${prof.viewport.width} x ${prof.viewport.height} @${prof.deviceScaleFactor}${prof.cpu > 1 ? `, CPU / ${prof.cpu}` : ""}`);

  const url = (hour) => `${base}/?${query}&hour=${hour}#${OLD_TOWN[0]},${OLD_TOWN[1]},${Z0}`;
  // Start-up, cold, on fast 4G.
  const t0 = Date.now();
  await page.goto(url(21), { waitUntil: "load", timeout: 120000 });
  await waitMapLoaded(page, 120000);
  const s = await page.evaluate(() => {
    const m = (n) => performance.getEntriesByName(n)[0]?.startTime ?? null;
    const nav = performance.getEntriesByType("navigation")[0];
    const fcp = performance.getEntriesByType("paint").find((p) => p.name === "first-contentful-paint")?.startTime ?? null;
    const gl = document.createElement("canvas").getContext("webgl");
    const dbg = gl?.getExtension("WEBGL_debug_renderer_info");
    return {
      fcp, mapOpen: m("map-open"), firstTile: m("map-first-tile"), mapLoaded: m("map-loaded"),
      domContentLoaded: nav?.domContentLoadedEventEnd ?? null, long: window.__perf?.longTasksSince(0) ?? [],
      renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : "unknown", drawer: window.__iso?.drawer() ?? null,
    };
  });
  const firstPaint = s.firstTile ?? 0;
  const startup = {
    fcpMs: s.fcp && Math.round(s.fcp), mapOpenMs: s.mapOpen && Math.round(s.mapOpen), firstTileMs: s.firstTile && Math.round(s.firstTile),
    mapLoadedMs: s.mapLoaded && Math.round(s.mapLoaded), domContentLoadedMs: Math.round(s.domContentLoaded ?? 0),
    bytesKB: Math.round(net.bytes / 1024), requests: net.requests, tiles: net.tiles,
    kindsKB: Object.fromEntries(Object.entries(net.kinds).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k, Math.round(v / 1024)])),
    largestKB: net.files.filter(([p]) => !p.startsWith("/tiles/")).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([p, v]) => [p, Math.round(v / 1024)]),
    longTasks: { count: s.long.length, maxMs: Math.round(Math.max(0, ...s.long.map((t) => t.ms))),
      totalMs: Math.round(s.long.reduce((a, t) => a + t.ms, 0)),
      over200AfterFirstPaint: s.long.filter((t) => t.start > firstPaint && t.ms > BUDGET_LONG_MS).length },
    wallMs: Date.now() - t0,
  };
  startup.withinBudget = (startup.mapLoadedMs ?? Infinity) <= BUDGET_START_MS && startup.longTasks.over200AfterFirstPaint === 0;
  console.log(`  start-up     FCP ${startup.fcpMs} ms  first tile ${startup.firstTileMs} ms  first view ${startup.mapLoadedMs} ms  ` +
    `${startup.bytesKB} KB in ${startup.requests} requests  long tasks ${startup.longTasks.count} (max ${startup.longTasks.maxMs} ms)` +
    `${startup.withinBudget ? "" : "  OVER BUDGET"}`);
  console.log(`  loaded by kind (KB): ${Object.entries(startup.kindsKB).map(([k, v]) => `${k} ${v}`).join(", ")}`);
  console.log(`  largest files besides tiles (KB): ${startup.largestKB.map(([p, v]) => `${p} ${v}`).join(", ")}`);
  console.log(`  renderer: ${s.renderer}, map drawer: ${s.drawer}`);

  // The rest without throttling the network (the motion is what is measured), the cache on.
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: false });
  const phases = {};
  for (const hour of [21, 13]) {
    const tag = hour === 21 ? "night" : "noon";
    if (hour !== 21) { await page.goto(url(hour), { waitUntil: "load", timeout: 60000 }); await waitMapLoaded(page, 60000); }
    await page.waitForTimeout(1500);
    phases[`${tag}-idle`] = await phase(page, cdp, net, `${tag}-idle`, prof, () => page.waitForTimeout(IDLE_MS));
    phases[`${tag}-pan`] = await phase(page, cdp, net, `${tag}-pan`, prof, () => page.evaluate(MOVE,
      { keys: [[...OLD_TOWN, Z0], [...KIRCHBERG, Z0]], ms: PAN_MS }));
    phases[`${tag}-zoom`] = await phase(page, cdp, net, `${tag}-zoom`, prof, () => page.evaluate(MOVE,
      { keys: [[...KIRCHBERG, Z0], [...KIRCHBERG, 1.2], [...KIRCHBERG, 0.15], [...KIRCHBERG, Z0]], ms: ZOOM_MS }));
  }
  await ctx.close();
  return { viewport: prof.viewport, dpr: prof.deviceScaleFactor, cpuSlowdown: prof.cpu, renderer: s.renderer, drawer: s.drawer, startup, phases, errors };
}

function table(run) {
  const rows = ["| Profile | Phase | fps | p50 ms | p95 ms | max ms | main ms/frame | long tasks | heap MB | KB loaded | tiles |",
    "|---|---|---|---|---|---|---|---|---|---|---|"];
  for (const [name, p] of Object.entries(run.profiles)) {
    const s = p.startup;
    rows.push(`| ${name} | start-up (FCP ${s.fcpMs}, first tile ${s.firstTileMs}, first view ${s.mapLoadedMs} ms) | | | | | | ${s.longTasks.count} (max ${s.longTasks.maxMs}) | | ${s.bytesKB} | ${s.tiles} |`);
    for (const [ph, x] of Object.entries(p.phases))
      rows.push(`| ${name} | ${ph} | ${x.fps} | ${x.frame.p50} | ${x.frame.p95} | ${x.frame.max} | ${x.mainMsPerFrame} | ${x.longTasks.count} | ${x.heapMB} | ${x.bytesKB} | ${x.tiles} |`);
  }
  const layers = new Set();
  for (const p of Object.values(run.profiles)) for (const x of Object.values(p.phases)) Object.keys(x.layers).forEach((k) => layers.add(k));
  const L = [...layers].sort();
  const lrows = [`| Profile | Phase | ${L.join(" | ")} |`, `|---|---|${L.map(() => "---").join("|")}|`];
  for (const [name, p] of Object.entries(run.profiles))
    for (const [ph, x] of Object.entries(p.phases)) lrows.push(`| ${name} | ${ph} | ${L.map((k) => (x.layers[k] ? `${x.layers[k].mean} / ${x.layers[k].p95}` : "")).join(" | ")} |`);
  return `${rows.join("\n")}\n\nPer layer, ms per frame (mean / p95):\n\n${lrows.join("\n")}\n`;
}

function compare(a, b) {
  const pc = (x, y) => (x ? `${y >= x ? "+" : ""}${Math.round(((y - x) / x) * 100)}%` : "");
  console.log(`\n${b.label} against ${a.label}`);
  for (const [name, p] of Object.entries(b.profiles)) {
    const o = a.profiles[name];
    if (!o) continue;
    const s0 = o.startup, s1 = p.startup;
    console.log(`${name} start-up: first view ${s0.mapLoadedMs} -> ${s1.mapLoadedMs} ms (${pc(s0.mapLoadedMs, s1.mapLoadedMs)}), ` +
      `${s0.bytesKB} -> ${s1.bytesKB} KB (${pc(s0.bytesKB, s1.bytesKB)}), long tasks ${s0.longTasks.count} -> ${s1.longTasks.count} (max ${s0.longTasks.maxMs} -> ${s1.longTasks.maxMs} ms)`);
    for (const [ph, x] of Object.entries(p.phases)) {
      const y = o.phases[ph];
      if (!y) continue;
      console.log(`  ${ph.padEnd(11)} fps ${y.fps} -> ${x.fps}  p95 ${y.frame.p95} -> ${x.frame.p95} ms (${pc(y.frame.p95, x.frame.p95)})  ` +
        `main ${y.mainMsPerFrame} -> ${x.mainMsPerFrame} ms (${pc(y.mainMsPerFrame, x.mainMsPerFrame)})  heap ${y.heapMB} -> ${x.heapMB} MB` +
        `${y.withinBudget && !x.withinBudget ? "  NEWLY OVER BUDGET" : ""}`);
    }
  }
}

const older = opt["compare-only"] ?? opt.compare;
if (opt["compare-only"]) {
  const nf = findRun(label), of = findRun(String(older));
  if (!nf || !of) throw new Error(`run not found: ${!nf ? label : older}`);
  compare(JSON.parse(readFileSync(of, "utf8")), JSON.parse(readFileSync(nf, "utf8")));
} else {
  const file = join(OUT, `${today}-${label}.json`);
  if (existsSync(file) && !opt.force) throw new Error(`${relative(ROOT, file)} exists: pick another --label, or add --force`);
  const of = older ? findRun(String(older)) : null;
  if (older && !of) throw new Error(`no run labelled ${older} in ${relative(ROOT, OUT)}`);
  let server = null, base = opt.url ? String(opt.url).replace(/\/$/, "") : null;
  if (!base) {
    if (opt.build) build();
    if (!existsSync(join(WEB, "dist/index.html"))) throw new Error("no dist/: run with --build, or npm run build first");
    base = `http://localhost:${port}`;
    // something else on the port (a dev server) would be measured instead of the build
    if (await fetch(base).then(() => true, () => false)) throw new Error(`port ${port} is already in use: stop that server or pick another --port`);
    server = spawn("npx", ["vite", "preview", "--port", String(port), "--strictPort"], { cwd: WEB, stdio: "ignore", detached: true });
    await waitFor(base, 30000);
  }
  const offList = opt.off ? String(opt.off).split(",") : [];
  const onList = allFeatures().filter((f) => !offList.includes(f));
  const query = [`perftest`, `on=${onList.join(",")}`, offList.length ? `off=${offList.join(",")}` : "", opt.query ? String(opt.query) : ""].filter(Boolean).join("&");
  const browser = await chromium.launch({ headless: !opt.headed, args: ["--use-angle=metal", "--ignore-gpu-blocklist", "--enable-precise-memory-info"] });
  const run = { label, date: new Date().toISOString(), base, query, commit: spawnSync("git", ["rev-parse", "--short", "HEAD"], { cwd: WEB }).stdout?.toString().trim(),
    headed: !!opt.headed, quick, profiles: {} };
  try {
    for (const name of String(opt.profiles ?? "desktop,phone").split(",")) {
      if (!PROFILES[name]) throw new Error(`unknown profile ${name}`);
      run.profiles[name] = await runProfile(browser, base, name, query);
    }
  } finally {
    await browser.close();
    if (server) { try { process.kill(-server.pid); } catch { /* already gone */ } }
  }
  mkdirSync(OUT, { recursive: true });
  writeFileSync(file, JSON.stringify(run, null, 2));
  writeFileSync(file.replace(/\.json$/, ".md"), table(run));
  console.log(`\n${table(run)}\nsaved ${relative(ROOT, file)}`);
  if (of) compare(JSON.parse(readFileSync(of, "utf8")), run);
}
