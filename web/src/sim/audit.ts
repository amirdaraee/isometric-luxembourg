/**
 * Headless audit of where cars are drawn, against the drivable map (pipeline/build_drivable.py) and the tree
 * canopy (occluders.png).
 *
 *   node src/sim/audit.ts [minutes] [busy] [--out audit.json] [--dump x0,y0,x1,y1 points.json]
 *
 * (Node 22.6+ runs TypeScript directly.) Runs the traffic simulation over the whole painted city for `minutes`
 * simulated minutes (default 10) and samples every car's drawn position once a second: the point Overlay draws it at
 * (lane offset and pull included, lifted onto the modelled deck on a bridge). Each sample is classed by the drivable
 * cell under it: road, deck, off the road (pavement, grass), water, inside a building (its footprint), hidden behind
 * a building (split into "cut", where the occlusion layer is high enough to hide a car there, and "not cut", where
 * the car would show on the facade), and, separately, under a tree crown (the canopy that fades cars in the vehicle
 * layer). Samples where the map is unpainted are left out. Prints the share of car-seconds in each class and the 30
 * places with the most samples on water, in a building, off the road or showing on a facade, as #x,y,1.0 view links.
 * Cars in tunnels are not drawn and not counted.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { inflateSync } from "node:zlib";
import { Traffic, type RoadLine } from "./traffic.ts";

const PUB = new URL("../../public/", import.meta.url).pathname;
const args = process.argv.slice(2);
const outAt = args.indexOf("--out"), dumpAt = args.indexOf("--dump");
const outFile = outAt >= 0 ? args[outAt + 1] : null;
// --dump: every sample inside a map px box, with its class, for drawing over the art
const dumpBox = dumpAt >= 0 ? args[dumpAt + 1].split(",").map(Number) : null, dumpFile = dumpAt >= 0 ? args[dumpAt + 2] : null;
const skip = new Set([outAt + 1, dumpAt + 1, dumpAt + 2].filter((i) => i > 0));
const pos = args.filter((a, i) => !a.startsWith("--") && !skip.has(i));
const dumped: [number, number, number][] = [];
const minutes = Number(pos[0] ?? 10), busy = Number(pos[1] ?? 1);

// --- a small PNG reader (8-bit grey, RGB, RGBA or palette indices), enough for the map's data files -------------
interface Png { w: number; h: number; ch: number; d: Uint8Array }
function readPng(file: string): Png {
  const b = readFileSync(file);
  let o = 8, w = 0, h = 0, type = 0;
  const idat: Buffer[] = [];
  while (o < b.length) {
    const len = b.readUInt32BE(o), kind = b.toString("latin1", o + 4, o + 8), data = b.subarray(o + 8, o + 8 + len);
    if (kind === "IHDR") {
      w = data.readUInt32BE(0); h = data.readUInt32BE(4); type = data[9];
      if (data[8] !== 8 || data[12] !== 0) throw new Error(`${file}: only 8-bit, non-interlaced PNGs`);
    } else if (kind === "IDAT") idat.push(data);
    else if (kind === "IEND") break;
    o += 12 + len;
  }
  const ch = type === 0 || type === 3 ? 1 : type === 2 ? 3 : type === 4 ? 2 : 4;
  const raw = inflateSync(Buffer.concat(idat)), stride = w * ch, d = new Uint8Array(w * h * ch);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)], src = y * (stride + 1) + 1, dst = y * stride;
    for (let x = 0; x < stride; x++) {
      const a = x >= ch ? d[dst + x - ch] : 0, up = y ? d[dst - stride + x] : 0, ul = y && x >= ch ? d[dst - stride + x - ch] : 0;
      let v = raw[src + x];
      if (f === 1) v += a; else if (f === 2) v += up; else if (f === 3) v += (a + up) >> 1;
      else if (f === 4) { const p = a + up - ul, pa = Math.abs(p - a), pb = Math.abs(p - up), pc = Math.abs(p - ul); v += pa <= pb && pa <= pc ? a : pb <= pc ? up : ul; }
      d[dst + x] = v & 255;
    }
  }
  return { w, h, ch, d };
}

// --- data --------------------------------------------------------------------------------------------------------
const lines = JSON.parse(readFileSync(PUB + "data/lines.json", "utf8")) as { roads: RoadLine[] };
const meta = JSON.parse(readFileSync(PUB + "tiles/meta.json", "utf8")) as { painted: { x0: number; y0: number; w: number; h: number }[] };
const di = JSON.parse(readFileSync(PUB + "data/drivable/index.json", "utf8")) as { cell: number; tile: number; tiles: string[]; values: Record<string, number> };
const tiles = new Map<string, Png>();
for (const n of di.tiles) tiles.set(n, readPng(`${PUB}data/drivable/${n}.png`));
/** Drivable value at map px, or -1 where there is no data (far from every street). */
function drivable(x: number, y: number): number {
  const cx = Math.floor(x / di.cell), cy = Math.floor(y / di.cell);
  const t = tiles.get(`${Math.floor(cx / di.tile)}_${Math.floor(cy / di.tile)}`);
  if (!t) return cx < 0 || cy < 0 ? 6 : 0;   // off the map: unpainted
  const i = cx % di.tile, j = cy % di.tile;
  return i < t.w && j < t.h ? t.d[j * t.w + i] : 0;
}
const om = JSON.parse(readFileSync(PUB + "data/occluders.json", "utf8")) as { x0: number; y0: number; scale: number; w: number; h: number };
const occ = readPng(PUB + "data/occluders.png");
/** Tree canopy coverage 0..1 at map px: the B channel where present, else (older data) an R value of exactly 8 m. */
function canopy(x: number, y: number): number {
  const i = Math.floor((x - om.x0) / om.scale), j = Math.floor((y - om.y0) / om.scale);
  if (i < 0 || j < 0 || i >= occ.w || j >= occ.h) return 0;
  const k = (j * occ.w + i) * occ.ch;
  return occ.ch >= 3 && occ.d[k + 2] ? occ.d[k + 2] / 255 : occ.d[k] === 80 ? 1 : 0;
}
/** Is a car (1.6 m) standing at map px hidden by the ground occlusion layer (more than half its centre line)? */
function cut(x: number, y: number): boolean {
  let n = 0, hid = 0;
  for (let t = 0; t <= 1.6; t += 0.2, n++) {
    const i = Math.floor((x - om.x0) / om.scale), j = Math.floor((y - t * UP - om.y0) / om.scale);
    if (i < 0 || j < 0 || i >= occ.w || j >= occ.h) continue;
    if (occ.d[(j * occ.w + i) * occ.ch] / 10 > t + 0.3) hid++;
  }
  return hid * 2 > n;
}
// Deck profiles: the nearest sample within 12 map px gives the lift (as occlusion.ts deckAt).
const prof = JSON.parse(readFileSync(PUB + "data/road_heights.json", "utf8")) as Record<string, { x: number[]; y: number[]; dz: number[] }>;
const UP = 0.8660254 / 0.25, CELL = 64, deckCells = new Map<number, [number, number, number][]>();
for (const p of Object.values(prof)) for (let i = 0; i < p.x.length; i++) {
  const k = Math.floor(p.y[i] / CELL) * 100000 + Math.floor(p.x[i] / CELL);
  (deckCells.get(k) ?? deckCells.set(k, []).get(k)!).push([p.x[i], p.y[i], p.dz[i] * UP]);
}
function deckLift(x: number, y: number): number | null {
  let best: number | null = null, bd = 144;
  for (let cy = Math.floor((y - 12) / CELL); cy <= Math.floor((y + 12) / CELL); cy++)
    for (let cx = Math.floor((x - 12) / CELL); cx <= Math.floor((x + 12) / CELL); cx++)
      for (const [px, py, lift] of deckCells.get(cy * 100000 + cx) ?? []) {
        const d = (px - x) ** 2 + (py - y) ** 2;
        if (d <= bd) { bd = d; best = lift; }
      }
  return best;
}

// --- run ---------------------------------------------------------------------------------------------------------
const box = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
for (const a of meta.painted) { box.x0 = Math.min(box.x0, a.x0); box.y0 = Math.min(box.y0, a.y0); box.x1 = Math.max(box.x1, a.x0 + a.w); box.y1 = Math.max(box.y1, a.y0 + a.h); }
const sim = new Traffic(lines.roads, { areas: meta.painted, seed: 42 });
// classes: the drivable values 0..5, with 5 (hidden) split into 5 cut and 6 not cut
const names = ["off road", "road", "deck", "water", "in building", "hidden, cut", "hidden, NOT cut"];
const count = [0, 0, 0, 0, 0, 0, 0];
let crown = 0, total = 0, guarded = 0, unpainted = 0;
/** Samples still drawn after the guard on water, in a building, on a facade (only on a modelled deck). */
const drawnBad = [0, 0, 0];
const bad = new Map<number, { n: number; x: number; y: number; cls: number[] }>();
const dt = 1 / 15;
const t0 = performance.now();
for (let i = 1; i <= minutes * 60 * 15; i++) {
  sim.step(dt, box, busy);
  if (i % 15 || i < 30 * 15) continue;   // once a second, after a 30 s warm-up
  for (const c of sim.cars()) {
    if (c.tunnel) continue;
    let y = c.y;
    let onDeck = false;
    if (c.bridge) { const l = deckLift(c.x, c.y); if (l !== null) { y -= l; onDeck = true; } }
    let v = drivable(c.x, y);
    if (v === 6) { unpainted++; continue; }
    if (v < 0 || v > 5) v = 0;
    if (v === 5 && !cut(c.x, y)) v = 6;
    total++; count[v]++;
    if (dumpBox && c.x >= dumpBox[0] && c.x < dumpBox[2] && y >= dumpBox[1] && y < dumpBox[3]) dumped.push([Math.round(c.x), Math.round(y), v]);
    if (canopy(c.x, y) > 0.5) crown++;
    // What the viewer's guard (Overlay.tsx) fades out: water, inside a building, or behind one where the cut does
    // not hide it (on a facade), unless the car is on a modelled deck.
    if ((v === 3 || v === 4 || v === 6) && !onDeck) guarded++;
    else if (v === 3) drawnBad[0]++; else if (v === 4) drawnBad[1]++; else if (v === 6) drawnBad[2]++;
    if (v === 0 || v === 3 || v === 4 || v === 6) {
      const k = Math.floor(y / 256) * 1000 + Math.floor(c.x / 256);
      const e = bad.get(k) ?? bad.set(k, { n: 0, x: 0, y: 0, cls: [0, 0, 0, 0, 0, 0, 0] }).get(k)!;
      e.n++; e.x += c.x; e.y += y; e.cls[v]++;
    }
  }
}
const pct = (n: number) => `${((100 * n) / Math.max(total, 1)).toFixed(2)}%`;
console.log(`${minutes} simulated minutes over the painted city (${((performance.now() - t0) / 1000).toFixed(0)} s), ` +
  `${total} car-seconds sampled, ${sim.stats.spawned} vehicles`);
for (let v = 0; v < names.length; v++) console.log(`  ${names[v].padEnd(16)} ${pct(count[v]).padStart(7)}`);
console.log(`  under a tree crown ${pct(crown)}; faded by the guard ${pct(guarded)}; left out (unpainted) ${unpainted}`);
console.log(`drawn after the guard: on water ${pct(drawnBad[0])}, in a building ${pct(drawnBad[1])}, on a facade ${pct(drawnBad[2])}`);
const worst = [...bad.values()].sort((a, b) => b.n - a.n).slice(0, 30);
console.log("worst places (car-seconds: off road / water / in building / on a facade):");
for (const e of worst) console.log(`  #${Math.round(e.x / e.n)},${Math.round(e.y / e.n)},1.0  ${e.n}: ${e.cls[0]} / ${e.cls[3]} / ${e.cls[4]} / ${e.cls[6]}`);
if (outFile) writeFileSync(outFile, JSON.stringify({ minutes, busy, total, unpainted, count: Object.fromEntries(names.map((n, i) => [n, count[i]])),
  crown, guarded, drawn: { water: drawnBad[0], building: drawnBad[1], facade: drawnBad[2] }, worst: worst.map((e) => ({ x: Math.round(e.x / e.n), y: Math.round(e.y / e.n), n: e.n, offRoad: e.cls[0], water: e.cls[3], building: e.cls[4], facade: e.cls[6] })) }, null, 1));
if (dumpFile) writeFileSync(dumpFile, JSON.stringify(dumped));
