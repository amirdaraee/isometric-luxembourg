/**
 * Headless check: do vehicles run on the roads and tracks as painted? (pipeline/fit_roads.py)
 *
 *   node src/sim/roadfit.test.ts [minutes] [busy] [--min 98] [--json out.json]
 *
 * (Node 22.6+ runs TypeScript directly.) Runs the traffic simulation over the whole painted city twice with the same
 * seed: on the OSM lines (with the old sideways shift "c", as before the fit) and on the fitted lines (lines.json
 * "q"). Every second (after a 30 s warm-up) each car's drawn ground point is looked up in the painted masks
 * (data/roadfit: bit 1 asphalt, bit 2 rail bed, 0.5 m cells). Left out, as the viewer does not show the car there or
 * the art cannot tell: tunnels, bridge decks (the car is lifted onto the modelled deck), cells behind a building or
 * outside the art (drivable map), and cells under a tree crown (occluders B channel over a half).
 * "On painted asphalt": the point's cell or one next to it (within 0.5 m) is asphalt, or (cars) it lies in a gap of up
 * to 3.5 m in the painted road (bit 16: a painted car, a marking); "strict": its own cell is asphalt.
 * Trams and trains: every section running at each sampled time of a weekday (every 30 s) is tested the same way
 * against the rail bed (or asphalt, for trams in the street), on the old shapes and on the fitted ones.
 * Prints both shares and the places with most samples off the painted road after the fit (#x,y,1.0 view links).
 * Exits non-zero when the fitted share of cars on painted asphalt is under --min (default 98).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { readPng, type Png } from "./png.ts";
import { Traffic, type RoadLine } from "./traffic.ts";
import type { TransitData } from "../components/Transit.ts";

// Transit.ts reads ?date= through testParams, which looks at the address: give it an empty one.
(globalThis as { location?: { search: string } }).location ??= { search: "" };
const { prepareShapes, transitSections } = await import("../components/Transit.ts");

const PUB = new URL("../../public/", import.meta.url).pathname;
const args = process.argv.slice(2);
const opt = (k: string) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : undefined; };
const pos = args.filter((a, i) => !a.startsWith("--") && !args[i - 1]?.startsWith("--"));
const minutes = Number(pos[0] ?? 5), busy = Number(pos[1] ?? 0.75), minShare = Number(opt("--min") ?? 98);

interface Tiled { cell: number; tile: number; tiles: string[] }
function tiled(dir: string) {
  const idx = JSON.parse(readFileSync(`${PUB}data/${dir}/index.json`, "utf8")) as Tiled;
  const t = new Map<string, Png>();
  for (const n of idx.tiles) t.set(n, readPng(`${PUB}data/${dir}/${n}.png`));
  return (x: number, y: number): number => {
    const cx = Math.floor(x / idx.cell), cy = Math.floor(y / idx.cell);
    if (cx < 0 || cy < 0) return -1;
    const p = t.get(`${Math.floor(cx / idx.tile)}_${Math.floor(cy / idx.tile)}`);
    if (!p) return 0;
    const i = cx % idx.tile, j = cy % idx.tile;
    return i < p.w && j < p.h ? p.d[j * p.w + i] : 0;
  };
}
const mask = tiled("roadfit"), drivable = tiled("drivable");
const om = JSON.parse(readFileSync(PUB + "data/occluders.json", "utf8")) as
  { x0: number; y0: number; scale: number; w: number; h: number; tile: number; tiles: string[] };
const occ = new Map<string, Png>();
for (const n of om.tiles) occ.set(n, readPng(`${PUB}data/occluders/${n}.png`));
function canopy(x: number, y: number): number {
  const i = Math.floor((x - om.x0) / om.scale), j = Math.floor((y - om.y0) / om.scale);
  if (i < 0 || j < 0) return 0;
  const t = occ.get(`${Math.floor(i / om.tile)}_${Math.floor(j / om.tile)}`);
  if (!t) return 0;
  const k = ((j % om.tile) * t.w + (i % om.tile)) * t.ch;
  return t.ch >= 3 ? t.d[k + 2] / 255 : 0;
}
const painted = (JSON.parse(readFileSync(PUB + "tiles/meta.json", "utf8")) as { painted: { x0: number; y0: number; w: number; h: number }[] }).painted;
const inArt = (x: number, y: number) => painted.some((a) => x >= a.x0 && x < a.x0 + a.w && y >= a.y0 && y < a.y0 + a.h);
/** 0 left out, 1 on (strict), 2 on within 0.5 m, 3 off. */
function classify(x: number, y: number, bits: number): number {
  const v = drivable(x, y);
  if (v === 5 || v === 6 || v < 0 || !inArt(x, y) || mask(x, y) & 4 || canopy(x, y) > 0.5) return 0;
  if (mask(x, y) & bits) return 1;
  for (const [dx, dy] of [[2, 0], [-2, 0], [0, 2], [0, -2], [2, 2], [-2, -2], [2, -2], [-2, 2]]) if (mask(x + dx, y + dy) & bits) return 2;
  if (bits & 1 && mask(x, y) & 16) return 2;   // in a closed gap of the painted road (a painted car, a marking)
  return 3;
}

const lines = JSON.parse(readFileSync(PUB + "data/lines.json", "utf8")) as { roads: RoadLine[] };
const meta = JSON.parse(readFileSync(PUB + "tiles/meta.json", "utf8")) as { painted: { x0: number; y0: number; w: number; h: number }[] };
const box = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
for (const a of meta.painted) { box.x0 = Math.min(box.x0, a.x0); box.y0 = Math.min(box.y0, a.y0); box.x1 = Math.max(box.x1, a.x0 + a.w); box.y1 = Math.max(box.y1, a.y0 + a.h); }

interface Tally { n: number; strict: number; near: number; left: number; bad: Map<number, { n: number; x: number; y: number }> }
const tally = (): Tally => ({ n: 0, strict: 0, near: 0, left: 0, bad: new Map() });
function add(t: Tally, x: number, y: number, c: number) {
  if (c === 0) { t.left++; return; }
  t.n++;
  if (c === 1) t.strict++;
  if (c <= 2) t.near++;
  else {
    const k = Math.floor(y / 128) * 10000 + Math.floor(x / 128);
    const e = t.bad.get(k) ?? t.bad.set(k, { n: 0, x: 0, y: 0 }).get(k)!;
    e.n++; e.x += x; e.y += y;
  }
}
const pct = (a: number, b: number) => (100 * a / Math.max(b, 1)).toFixed(2);

/** All samples, and those the viewer's painted-road guard lets through (roadfit bit 8, as Overlay.tsx). */
function cars(fitted: boolean): { all: Tally; drawn: Tally } {
  const sim = new Traffic(lines.roads, { areas: meta.painted, seed: 42, fitted });
  const all = tally(), drawn = tally(), dt = 1 / 15;
  for (let i = 1; i <= minutes * 60 * 15; i++) {
    sim.step(dt, box, busy);
    if (i % 15 || i < 30 * 15) continue;
    for (const c of sim.cars()) {
      if (c.tunnel) continue;
      if (c.bridge) { all.left++; drawn.left++; continue; }
      const k = classify(c.x, c.y, 1);
      add(all, c.x, c.y, k);
      if (k === 0 || mask(c.x, c.y) & 8) add(drawn, c.x, c.y, k); else drawn.left++;
    }
  }
  return { all, drawn };
}

function trains(fitted: boolean): Tally {
  const d = JSON.parse(readFileSync(PUB + "data/transit.json", "utf8")) as TransitData;
  const shapes = prepareShapes(d, fitted), t = tally();
  const deck = new Set(Object.keys(JSON.parse(readFileSync(PUB + "data/road_heights.json", "utf8"))).map(Number));
  for (let sec = 5 * 3600; sec < 24 * 3600; sec += 30) {
    for (const s of transitSections(d, shapes, sec, 1, [box.x0, box.y0, box.x1, box.y1])) {
      if (s.portal || (s.way >= 0 && deck.has(s.way))) { t.left++; continue; }
      add(t, s.x, s.y, classify(s.x, s.y, s.kind === "tram" ? 3 : 2));
    }
  }
  return t;
}

const t0 = performance.now();
const cb = cars(false), ca = cars(true);
const res = { cars: { before: cb.all, after: ca.all }, transit: { before: trains(false), after: trains(true) } };
const out: Record<string, unknown> = { minutes, busy };
const g = ca.drawn, hidden = ca.all.n - g.n;
console.log(`cars with the painted-road guard: ${pct(hidden, ca.all.n)}% of the samples faded out (before the fit it ` +
  `would fade ${pct(cb.all.n - cb.drawn.n, cb.all.n)}%); of those drawn, on the painted asphalt ${pct(g.near, g.n)}% ` +
  `(strict ${pct(g.strict, g.n)}%)`);
out.guard = { faded: hidden, drawn: g.n, near: g.near, strict: g.strict, fadedBefore: cb.all.n - cb.drawn.n };
for (const [k, v] of Object.entries(res)) {
  const b = v.before, a = v.after;
  console.log(`${k}: ${a.n} samples (${a.left} left out). On the painted ${k === "cars" ? "asphalt" : "rail bed"}: ` +
    `before ${pct(b.near, b.n)}% (strict ${pct(b.strict, b.n)}%), after ${pct(a.near, a.n)}% (strict ${pct(a.strict, a.n)}%)`);
  const worst = [...a.bad.values()].sort((p, q) => q.n - p.n).slice(0, 15);
  console.log("  most samples off it after the fit: " + worst.map((e) => `#${Math.round(e.x / e.n)},${Math.round(e.y / e.n)},1.0 (${e.n})`).join(" "));
  out[k] = { before: { n: b.n, near: b.near, strict: b.strict }, after: { n: a.n, near: a.near, strict: a.strict },
    worst: worst.map((e) => [Math.round(e.x / e.n), Math.round(e.y / e.n), e.n]) };
}
console.log(`(${((performance.now() - t0) / 1000).toFixed(0)} s)`);
const jf = opt("--json");
if (jf) writeFileSync(jf, JSON.stringify(out, null, 1));
const share = 100 * g.near / Math.max(g.n, 1);
if (share < minShare) { console.error(`FAIL: ${share.toFixed(2)}% of the drawn car samples on painted asphalt, under ${minShare}%`); process.exit(1); }
console.log("ok");
