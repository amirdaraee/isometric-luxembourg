// Headless audit of layer 12 (the simulation the viewer runs), for the gate checks in v2/checks/g1_checks.py:
//   node --experimental-strip-types scripts/audit.ts <release folder> <out folder> [sample seconds]
// Runs v1's traffic for a simulated day on the v2 graph (and every tram and train of the day), writes every
// vehicle's box every <sample> seconds (samples.bin: float32 x 10 per vehicle: E, N local, z, heading, length,
// width, height, edge, kind code, sim second), and measures the largest height change between two frames (1/30 s)
// for every car over a simulated hour and every tram and train over the day (jumps.json).
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Vehicles, type VehiclesData } from "../src/vehicles.ts";
import { prepareShapes, transitSections, type TransitData } from "../src/sim/transit.ts";

const [rel, out, sampleArg] = process.argv.slice(2);
const vd = JSON.parse(readFileSync(join(rel, "vehicles.json"), "utf8")) as VehiclesData;
const td = JSON.parse(readFileSync(join(rel, "transit.json"), "utf8")) as TransitData;
const SAMPLE = Number(sampleArg ?? 20);
const KIND: Record<string, number> = { car: 0, van: 1, bus: 2, police: 3, ambulance: 4, fire: 5, tram_end: 10, tram_mid: 11,
  train_cab: 20, train_coach: 21, train_loco: 22, funicular: 30 };

const v = new Vehicles(vd, td, 20240607);
const rows: number[] = [];
const dt = 0.1;
let n = 0;
const t0 = Date.now();
for (let sec = 0; sec < 86400; sec += dt) {
  const hour = sec / 3600;
  v.step(dt, hour);
  if (Math.abs(sec / SAMPLE - Math.round(sec / SAMPLE)) < dt / SAMPLE / 2) {
    v.update(sec, 1, true);
    for (const s of v.samples) rows.push(s.x, s.y, s.z, s.h, s.L, s.W, s.H, s.edge, KIND[s.kind] ?? 0, sec);
    n++;
  }
}
writeFileSync(join(out, "samples.bin"), Buffer.from(new Float32Array(rows).buffer));

// frame-to-frame height jumps: cars over a busy simulated hour at 30 frames a second
const fr = 1 / 30;
const last = new Map<number, number>();
let carMax = 0, carN = 0, carWorst: unknown = null;
const v2 = new Vehicles(vd, td, 7);
for (let s = 0; s < 600; s += 0.1) v2.step(0.1, 8.5);
for (let f = 0; f < 3600 * 30; f++) {
  v2.traffic.step(fr, v2.area, 1);
  for (const c of v2.traffic.cars()) {
    const z = v2.roadZ(c.rid, c.x, c.y);
    const p = last.get(c.id);
    if (p !== undefined) {
      const d = Math.abs(z - p);
      carN++;
      if (d > carMax) { carMax = d; carWorst = { id: c.id, rid: c.rid, x: c.x * vd.unit_m, y: -c.y * vd.unit_m, z, prev: p }; }
    }
    last.set(c.id, z);
  }
  if (f % 300 === 0) for (const id of [...last.keys()]) if (!v2.traffic.cars().some((c) => c.id === id)) last.delete(id);
}
// trams and trains: every trip of the day, each section's centre every frame while it runs
const shapes = prepareShapes(td, false);
let trMax = 0, trN = 0, trWorst: unknown = null;
for (const trip of td.trips) {
  const one: TransitData = { ...td, trips: [trip] };
  const t = trip.t;
  const prev = new Map<number, number>();
  for (let sec = t[0][0]; sec <= t[t.length - 1][1]; sec += fr) {
    const secs = transitSections(one, shapes, sec, 7, [-1e9, -1e9, 1e9, 1e9]);
    secs.forEach((s) => {
      const i = s.idx;
      if (s.way < 0) return;
      const z = v.edgeZ(s.way, s.s);
      const p = prev.get(i);
      if (p !== undefined) {
        const d = Math.abs(z - p);
        trN++;
        if (d > trMax) { trMax = d; trWorst = { trip: trip.n, shape: trip.s, edge: s.way, s: s.s, z, prev: p, sec }; }
      }
      prev.set(i, z);
    });
    for (const k of [...prev.keys()]) if (!secs.some((s) => s.idx === k)) prev.delete(k);
  }
}
writeFileSync(join(out, "jumps.json"), JSON.stringify({ frame_s: fr, cars: { max_m: carMax, frames: carN, worst: carWorst },
  transit: { max_m: trMax, frames: trN, worst: trWorst }, samples: n, sample_s: SAMPLE, rows: rows.length / 10,
  seconds: (Date.now() - t0) / 1000, stats: v.traffic.stats }));
console.log(JSON.stringify({ samples: n, vehicles: rows.length / 10, carMax, trMax, seconds: (Date.now() - t0) / 1000 }));
