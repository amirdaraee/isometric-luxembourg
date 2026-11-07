#!/usr/bin/env node
// Screenshot set: loads every view in scripts/shots.json against `vite preview` of a build and saves one PNG per
// view, so that a change can be checked at the same places, at the same hour, season, date and seed, every time.
//
//   node scripts/shots.mjs --label before               shots of the current dist/ into data/work/shots/<date>-before/
//   node scripts/shots.mjs --build --label after        build first (every feature on except perfHud), then shoot
//   node scripts/shots.mjs --build=release --label pub  build with the release switches (.env.production)
//   node scripts/shots.mjs --label after --compare before   also write compare.html: old, new and difference
//   node scripts/shots.mjs --only a-rail,m0 ...          only the views whose name starts with one of these
//   node scripts/shots.mjs --url http://localhost:3000   shoot a server that is already running (no preview)
//   node scripts/shots.mjs --compare-only before --label after   compare two existing sets, no new shots
//
// Other options: --port 3018 (preview port), --wait 1.5 (multiplies every waitMs), --force (replace a set).
// Each entry in shots.json: {name, hash: "x,y,z", query: "hour=13&on=traffic", waitMs, size: [w, h]}.
// The set also gets report.json: per view, the URL, the console errors and the load time.
//
// Needs Playwright's Chromium once: npx playwright install chromium
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = resolve(WEB, "..");
const OUT = join(ROOT, "data/work/shots");

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
const port = +(opt.port ?? 3018);
const waitScale = +(opt.wait ?? 1);

/** The newest set for a label ("before", or a full folder name such as "2026-11-07-before"). */
function findSet(name) {
  if (existsSync(join(OUT, name))) return join(OUT, name);
  const hits = existsSync(OUT) ? readdirSync(OUT).filter((d) => d.endsWith(`-${name}`)).sort() : [];
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

function build(kind) {
  const env = { ...process.env };
  // Shots check features, so by default every switch is on (perfHud stays off: it would show in every shot).
  if (kind !== "release") env.VITE_FEATURES_OFF = "perfHud";
  console.log(`building (${kind === "release" ? "release switches" : "every feature on"})`);
  const r = spawnSync("npx", ["vite", "build"], { cwd: WEB, env, stdio: "inherit" });
  if (r.status !== 0) throw new Error("build failed");
}

async function shoot(dir) {
  const list = JSON.parse(readFileSync(join(WEB, "scripts/shots.json"), "utf8"));
  const only = opt.only ? String(opt.only).split(",") : null;
  const views = only ? list.filter((s) => only.some((p) => s.name.startsWith(p))) : list;
  if (!views.length) throw new Error("no views match --only");

  let server = null, base = opt.url ? String(opt.url).replace(/\/$/, "") : null;
  if (!base) {
    if (opt.build) build(opt.build);
    if (!existsSync(join(WEB, "dist/index.html"))) throw new Error("no dist/: run with --build, or npm run build first");
    base = `http://localhost:${port}`;
    server = spawn("npx", ["vite", "preview", "--port", String(port), "--strictPort"], { cwd: WEB, stdio: "ignore", detached: true });
    await waitFor(base, 30000);
  }

  mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ args: ["--use-angle=metal", "--ignore-gpu-blocklist"] });
  const report = [];
  try {
    for (const s of views) {
      const [w, h] = s.size ?? [1280, 800];
      const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
      const errors = [];
      page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
      page.on("pageerror", (e) => errors.push(String(e)));
      const url = `${base}/${s.query ? `?${s.query}` : ""}#${String(s.hash).replace(/^#/, "")}`;
      const t0 = Date.now();
      try {
        await page.goto(url, { waitUntil: "load", timeout: 60000 });
        await page.waitForSelector("#root > *", { timeout: 30000 }).catch(() => {});
        await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
        const loadMs = Date.now() - t0;
        await page.waitForTimeout((s.waitMs ?? 4000) * waitScale);
        await page.screenshot({ path: join(dir, `${s.name}.png`) });
        report.push({ name: s.name, url, loadMs, errors });
        console.log(`${s.name}  ${(loadMs / 1000).toFixed(1)} s${errors.length ? `  ${errors.length} console error(s)` : ""}`);
      } catch (e) {
        report.push({ name: s.name, url, failed: String(e), errors });
        console.log(`${s.name}  FAILED: ${e}`);
      }
      await page.close();
    }
  } finally {
    await browser.close();
    if (server) { try { process.kill(-server.pid); } catch { /* already gone */ } }
  }
  writeFileSync(join(dir, "report.json"), JSON.stringify({ base, date: new Date().toISOString(), views: report }, null, 2));
  const bad = report.filter((r) => r.failed || r.errors.length).length;
  console.log(`${report.length} views in ${relative(ROOT, dir)}${bad ? `, ${bad} with errors (see report.json)` : ""}`);
}

/** Writes compare.html in `newDir`: old, new and a difference image per view, and the share of changed pixels. */
async function compare(oldDir, newDir) {
  const names = readdirSync(newDir).filter((f) => f.endsWith(".png") && !f.startsWith("diff-") && existsSync(join(oldDir, f)));
  if (!names.length) { console.log("nothing to compare"); return; }
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const rows = [];
  try {
    for (const f of names) {
      const a = `data:image/png;base64,${readFileSync(join(oldDir, f)).toString("base64")}`;
      const b = `data:image/png;base64,${readFileSync(join(newDir, f)).toString("base64")}`;
      // A pixel counts as changed when any channel moved by more than 24 of 255; changed pixels show in magenta
      // over a faded copy of the new shot.
      const r = await page.evaluate(async ([a, b]) => {
        const load = (src) => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });
        const [ia, ib] = await Promise.all([load(a), load(b)]);
        const w = Math.max(ia.width, ib.width), h = Math.max(ia.height, ib.height);
        const px = (im) => { const c = new OffscreenCanvas(w, h), g = c.getContext("2d"); g.drawImage(im, 0, 0); return g.getImageData(0, 0, w, h); };
        const da = px(ia), db = px(ib), out = new ImageData(w, h);
        let changed = 0;
        for (let i = 0; i < da.data.length; i += 4) {
          const d = Math.max(Math.abs(da.data[i] - db.data[i]), Math.abs(da.data[i + 1] - db.data[i + 1]), Math.abs(da.data[i + 2] - db.data[i + 2]));
          if (d > 24) { changed++; out.data.set([255, 0, 255, 255], i); }
          else { const y = (db.data[i] + db.data[i + 1] + db.data[i + 2]) / 3; out.data.set([y, y, y, 70], i); }
        }
        const c = new OffscreenCanvas(w, h); c.getContext("2d").putImageData(out, 0, 0);
        const blob = await c.convertToBlob({ type: "image/png" });
        const buf = new Uint8Array(await blob.arrayBuffer());
        let s = ""; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
        return { share: changed / (w * h), png: btoa(s), sizeDiffers: ia.width !== ib.width || ia.height !== ib.height };
      }, [a, b]);
      writeFileSync(join(newDir, `diff-${f}`), Buffer.from(r.png, "base64"));
      rows.push({ f, share: r.share, sizeDiffers: r.sizeDiffers });
    }
  } finally {
    await browser.close();
  }
  rows.sort((x, y) => y.share - x.share);
  const oldRel = relative(newDir, oldDir);
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const html = `<!doctype html><meta charset="utf-8"><title>Shots compared</title>
<style>body{font:14px system-ui;margin:16px;background:#f4f4f4}h2{font-size:15px;margin:24px 0 6px}
.row{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}img{width:100%;display:block;background:#fff}
.k{color:#666}.hi{color:#b0006a;font-weight:600}</style>
<h1>${esc(relative(OUT, newDir))} against ${esc(relative(OUT, oldDir))}</h1>
<p class="k">Columns: before, after, changed pixels (magenta: a channel moved by more than 24 of 255). Most changed first.</p>
${rows.map((r) => `<h2>${esc(r.f.replace(/\.png$/, ""))} <span class="${r.share > 0.01 ? "hi" : "k"}">${(r.share * 100).toFixed(2)}% changed${r.sizeDiffers ? ", sizes differ" : ""}</span></h2>
<div class="row"><img loading="lazy" src="${esc(join(oldRel, r.f))}"><img loading="lazy" src="${esc(r.f)}"><img loading="lazy" src="diff-${esc(r.f)}"></div>`).join("\n")}
`;
  writeFileSync(join(newDir, "compare.html"), html);
  console.log(`compare: ${rows.filter((r) => r.share > 0.01).length} of ${rows.length} views changed by more than 1%  ${relative(ROOT, join(newDir, "compare.html"))}`);
}

const older = opt["compare-only"] ?? opt.compare;
if (opt["compare-only"]) {
  const nd = findSet(label), od = findSet(String(older));
  if (!nd || !od) throw new Error(`set not found: ${!nd ? label : older}`);
  await compare(od, nd);
} else {
  const dir = join(OUT, `${today}-${label}`);
  if (existsSync(dir)) {
    if (!opt.force) throw new Error(`${relative(ROOT, dir)} exists: pick another --label, or add --force`);
    rmSync(dir, { recursive: true, force: true });
  }
  const od = older ? findSet(String(older)) : null;
  if (older && !od) throw new Error(`no set labelled ${older} in ${relative(ROOT, OUT)}`);
  await shoot(dir);
  if (od) await compare(od, dir);
}
