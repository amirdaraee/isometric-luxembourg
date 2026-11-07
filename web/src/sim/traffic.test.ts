/**
 * Headless check of the traffic simulation on the real road data.
 *
 *   node src/sim/traffic.test.ts [path/to/lines.json] [minutes] [busy]
 *
 * (Node 22.6+ runs TypeScript directly.) Runs the old-town view at 30 steps per second and prints cars alive, mean
 * speed, deadlock removals and cars that ever overlapped another. Exits non-zero if the numbers look wrong.
 */
import { readFileSync } from "node:fs";
import { Traffic, type RoadLine } from "./traffic.ts";

const file = process.argv[2] ?? new URL("../../public/data/lines.json", import.meta.url).pathname;
const minutes = Number(process.argv[3] ?? 5);
const busy = Number(process.argv[4] ?? 1);
const lines = JSON.parse(readFileSync(file, "utf8")) as { roads: RoadLine[] };

const painted = [{ x0: 5500, y0: 3700, w: 6000, h: 6000 }];
let t0 = performance.now();
const sim = new Traffic(lines.roads, { areas: painted, seed: 1 });
console.log(`graph: ${JSON.stringify(sim.size)} built in ${(performance.now() - t0).toFixed(0)} ms`);

const view = { x0: 5500, y0: 3700, x1: 11500, y1: 9700 };
const dt = 1 / 30, steps = Math.round((minutes * 60) / dt);
const everOverlapped = new Set<number>(), everClose = new Set<number>();
let speedSum = 0, speedN = 0, aliveSum = 0, stepMs = 0;
t0 = performance.now();
for (let i = 1; i <= steps; i++) {
  const a = performance.now();
  sim.step(dt, view, busy);
  stepMs += performance.now() - a;
  for (const id of sim.laneOverlaps()) everOverlapped.add(id);
  if (i % 15 === 0) for (const id of sim.closeCalls()) everClose.add(id);
  if (i > 30 * 30) { // after a 30 s warm-up
    speedSum += sim.meanSpeed(); speedN++; aliveSum += sim.stats.alive;
  }
  if (i % (30 * 60) === 0) {
    console.log(`t=${(i * dt).toFixed(0)} s alive=${sim.stats.alive} mean=${(sim.meanSpeed() * 3.6).toFixed(1)} km/h ` +
      `spawned=${sim.stats.spawned} left=${sim.stats.left} deadlocks=${sim.stats.deadlocks} overlapped=${everOverlapped.size}`);
  }
}
let n = 0;
for (const _ of sim.cars()) n++;
const mean = (speedSum / Math.max(speedN, 1)) * 3.6;
console.log("---");
console.log(`cars alive: ${sim.stats.alive} (drawable ${n}), average over run ${(aliveSum / Math.max(speedN, 1)).toFixed(0)}`);
console.log(`average speed: ${mean.toFixed(1)} km/h`);
console.log(`deadlock removals: ${sim.stats.deadlocks} (${(sim.stats.deadlocks / minutes).toFixed(1)} per minute; ${sim.stats.spawned} spawned)`);
console.log(`cars that ever overlapped another in the same lane: ${everOverlapped.size}`);
console.log(`cars ever under 1.5 m from a car on another lane (sampled twice a second): ${everClose.size}`);
console.log(`deadlock causes: ${JSON.stringify(sim.removedWhy)}`);
console.log(`step time: ${(stepMs / steps).toFixed(3)} ms average`);

// Second run: a close-up view (about 1900 x 1100 map px) panning slowly across the old town and then jumping, so
// streets come and go at the margins.
const pan = new Traffic(lines.roads, { areas: painted, seed: 2 });
const panOverlaps = new Set<number>();
let panMax = 0, panMs = 0;
const panSteps = 120 * 30;
for (let i = 0; i < panSteps; i++) {
  const f = i / panSteps;
  const cx = f < 0.8 ? 6500 + f * 5000 : 7000, cy = f < 0.8 ? 5000 + f * 3000 : 8500;
  const v = { x0: cx - 950, y0: cy - 550, x1: cx + 950, y1: cy + 550 };
  const a = performance.now();
  pan.step(dt, v, busy);
  panMs += performance.now() - a;
  for (const id of pan.laneOverlaps()) panOverlaps.add(id);
  panMax = Math.max(panMax, pan.stats.alive);
}
console.log("--- panning close-up, 2 minutes");
console.log(`alive at end ${pan.stats.alive} (most ${panMax}); spawned ${pan.stats.spawned}, left ${pan.stats.left}, ` +
  `deadlocks ${pan.stats.deadlocks}; same-lane overlaps ${panOverlaps.size}; step ${(panMs / panSteps).toFixed(3)} ms`);

const ok = mean > 15 && mean < 50 && everOverlapped.size <= Math.max(2, sim.stats.spawned * 0.002) &&
  sim.stats.deadlocks <= sim.stats.spawned * 0.02 && panOverlaps.size === 0 && pan.stats.alive > 20;
if (!ok) { console.error("FAIL"); process.exit(1); }
console.log("ok");
