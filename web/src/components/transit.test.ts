/**
 * Headless check of the trams and trains (transit.json from pipeline/build_transit.py) against the rail lines.
 *
 *   node src/components/transit.test.ts [path/to/data folder]
 *
 * (Node 22.6+ runs TypeScript directly.)
 *  - On the tracks: a sample every 2 m along every shape lies within 0.5 m of a lines.json rail line (99% at least).
 *  - Plausible speeds: the mean speed between stops stays under 160 km/h (trains) and 70 km/h (trams), and the
 *    mean over all runs is in a sane range.
 * Exits non-zero if the numbers look wrong.
 */
import { readFileSync } from "node:fs";

const dir = process.argv[2] ?? new URL("../../public/data/", import.meta.url).pathname;
const lines = JSON.parse(readFileSync(`${dir}/lines.json`, "utf8")) as { rail: { id: number; p: number[]; k: string; t?: boolean }[] };
const transit = JSON.parse(readFileSync(`${dir}/transit.json`, "utf8")) as {
  shapes: number[][]; runs?: [number, number, number][][];
  trips: { s: number; k: "tram" | "train"; n: string; t: [number, number, number][] }[];
};

const MPP = 0.25;   // map px per metre on the ground (along the screen's horizontal); good enough for a check
const fails: string[] = [];

// ------------------------------------------------------------------------------------------- on the tracks
const CELL = 64;
const grid = new Map<string, [number, number, number, number][]>();
for (const w of lines.rail) {
  if (!["rail", "tram", "light_rail"].includes(w.k)) continue;
  for (let i = 0; i + 3 < w.p.length; i += 2) {
    const a: [number, number, number, number] = [w.p[i], w.p[i + 1], w.p[i + 2], w.p[i + 3]];
    for (let cx = Math.floor(Math.min(a[0], a[2]) / CELL); cx <= Math.floor(Math.max(a[0], a[2]) / CELL); cx++)
      for (let cy = Math.floor(Math.min(a[1], a[3]) / CELL); cy <= Math.floor(Math.max(a[1], a[3]) / CELL); cy++) {
        const k = `${cx},${cy}`;
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k)!.push(a);
      }
  }
}
function nearest(x: number, y: number): number {
  let best = Infinity;
  for (const s of grid.get(`${Math.floor(x / CELL)},${Math.floor(y / CELL)}`) ?? []) {
    const dx = s[2] - s[0], dy = s[3] - s[1], L2 = dx * dx + dy * dy || 1e-9;
    const t = Math.min(Math.max(((x - s[0]) * dx + (y - s[1]) * dy) / L2, 0), 1);
    best = Math.min(best, Math.hypot(s[0] + dx * t - x, s[1] + dy * t - y));
  }
  return best;
}
let samples = 0, on = 0, matched = 0;
const worst: [number, number][] = [];
transit.shapes.forEach((p, si) => {
  if (transit.runs?.[si]?.length) matched++;
  let off = 0, n = 0;
  for (let i = 0; i + 3 < p.length; i += 2) {
    const L = Math.hypot(p[i + 2] - p[i], p[i + 3] - p[i + 1]), k = Math.max(1, Math.ceil(L / (2 / MPP)));
    for (let j = 0; j < k; j++) {
      const f = j / k, d = nearest(p[i] + (p[i + 2] - p[i]) * f, p[i + 1] + (p[i + 3] - p[i + 1]) * f);
      n++;
      if (d * MPP <= 0.5) on++; else off++;
    }
  }
  samples += n;
  if (off) worst.push([si, off / n]);
});
const share = on / samples;
console.log(`shapes ${transit.shapes.length} (matched onto OSM: ${matched}), samples ${samples}, on the tracks ${(share * 100).toFixed(2)}%`);
worst.sort((a, b) => b[1] - a[1]);
if (worst.length) console.log("  most off:", worst.slice(0, 5).map(([s, f]) => `shape ${s} ${(f * 100).toFixed(1)}%`).join(", "));
if (share < 0.99) fails.push(`only ${(share * 100).toFixed(2)}% of shape samples on a rail line (want 99%)`);

// ---------------------------------------------------------------------------------------------- the speeds
const MAX = { tram: 70, train: 160 };
const sum = { tram: [0, 0], train: [0, 0] };
let fast = 0;
for (const tr of transit.trips) {
  for (let i = 1; i < tr.t.length; i++) {
    const a = tr.t[i - 1], b = tr.t[i], dt = b[0] - a[1];
    if (dt <= 0) continue;
    // px along the shape on screen: the horizontal scale is 0.25 m per px, the vertical is foreshortened, so
    // this underestimates the ground distance a little where the track runs up and down the screen.
    const kmh = (Math.abs(b[2] - a[2]) * MPP) / dt * 3.6;
    sum[tr.k][0] += Math.abs(b[2] - a[2]) * MPP; sum[tr.k][1] += dt;
    if (kmh > MAX[tr.k]) { fast++; if (fast <= 5) console.log(`  fast: ${tr.k} ${tr.n} ${kmh.toFixed(0)} km/h`); }
  }
}
for (const k of ["tram", "train"] as const) {
  const v = (sum[k][0] / Math.max(sum[k][1], 1)) * 3.6;
  console.log(`${k}: mean speed between stops ${v.toFixed(1)} km/h`);
  if (v < 8 || v > MAX[k]) fails.push(`${k} mean speed ${v.toFixed(1)} km/h is implausible`);
}
if (fast) fails.push(`${fast} runs between stops faster than the limit`);

if (fails.length) {
  console.error("FAIL\n  " + fails.join("\n  "));
  process.exit(1);
}
console.log("ok");
