/**
 * Headless check of the traffic simulation on the real road data.
 *
 *   node src/sim/traffic.test.ts [path/to/lines.json] [minutes] [busy]
 *
 * (Node 22.6+ runs TypeScript directly.) Runs the old-town view at 30 steps per second and prints cars alive, mean
 * speed, deadlock removals, cars that ever overlapped another, vehicles on lanes closed to them (cars on
 * pedestrian streets, bus lanes, through a destination-only street) and the emergency vehicles and their calls; then
 * runs emergency scenarios on real streets (sirens making their way: corridor, pull-over, overtaking). Exits non-zero
 * if the numbers look wrong.
 */
import { readFileSync } from "node:fs";
import { Traffic, type RoadLine } from "./traffic.ts";

/** Vehicles that ever stood on a lane they may not use, by "id:type". */
function accessCheck(sim: Traffic, seen: Map<string, string>) {
  for (const v of sim.accessViolations()) { const [id, type, edge] = v.split(":"); seen.set(`${id}:${type}`, edge); }
}

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
const everOverlapped = new Set<number>(), everClose = new Set<number>(), forbidden = new Map<string, string>();
let sirenSpeed = 0, sirenN = 0, maxEmg = 0, forced = 0;
let speedSum = 0, speedN = 0, aliveSum = 0, stepMs = 0;
t0 = performance.now();
for (let i = 1; i <= steps; i++) {
  const a = performance.now();
  sim.step(dt, view, busy);
  stepMs += performance.now() - a;
  for (const id of sim.laneOverlaps()) everOverlapped.add(id);
  accessCheck(sim, forbidden);
  if (i % 15 === 0) for (const id of sim.closeCalls()) everClose.add(id);
  // Every 40 s an emergency vehicle on a call near the middle of the view, so sirens are always tried.
  if (i % (40 * 30) === 0) forced += +sim.spawnEmergency(i % 3 === 0 ? "fire" : i % 2 ? "ambulance" : "police", true);
  const ea = sim.emergencyAlive(); maxEmg = Math.max(maxEmg, ea.all);
  const ss = sim.sirenSpeeds(); for (const v of ss) { sirenSpeed += v; sirenN++; }
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
console.log(`vehicles ever on a lane closed to them: ${forbidden.size}${forbidden.size ? " " + [...forbidden].slice(0, 8).join(" ") : ""}`);
console.log(`parked on destination-only streets: ${sim.stats.parked}`);
const natural = sim.stats.emergency - forced;
console.log(`emergency vehicles: ${sim.stats.emergency} of ${sim.stats.spawned}, ${forced} of them put in on a call by the test; ` +
  `the rest 1 in ${(sim.stats.spawned / Math.max(natural, 1)).toFixed(0)} vehicles; ` +
  `most at once ${maxEmg}; calls ${sim.stats.calls} (${sim.stats.callsEnded} ended in view); siren mean speed ` +
  `${((sirenSpeed / Math.max(sirenN, 1)) * 3.6).toFixed(1)} km/h; red lights crossed ${sim.stats.redCrossed}; overtakes ${sim.stats.overtakes}`);
console.log(`step time: ${(stepMs / steps).toFixed(3)} ms average`);

// Second run: a close-up view (about 1900 x 1100 map px) panning slowly across the old town and then jumping, so
// streets come and go at the margins.
const pan = new Traffic(lines.roads, { areas: painted, seed: 2 });
const panOverlaps = new Set<number>(), panForbidden = new Map<string, string>();
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
  accessCheck(pan, panForbidden);
  if (i % (20 * 30) === 0) pan.spawnEmergency("police", true);
  panMax = Math.max(panMax, pan.stats.alive);
}
console.log("--- panning close-up, 2 minutes");
console.log(`alive at end ${pan.stats.alive} (most ${panMax}); spawned ${pan.stats.spawned}, left ${pan.stats.left}, ` +
  `deadlocks ${pan.stats.deadlocks}; same-lane overlaps ${panOverlaps.size}; on closed lanes ${panForbidden.size}; ` +
  `emergency ${pan.stats.emergency}, calls ${pan.stats.calls}; step ${(panMs / panSteps).toFixed(3)} ms`);

// Third run: the same view with emergency vehicles switched off (pedestrian streets then leave the graph), to see
// what they cost the rest of the traffic.
const plain = new Traffic(lines.roads, { areas: painted, seed: 1, emergency: false });
const plainOverlaps = new Set<number>(), plainForbidden = new Map<string, string>();
let plainSpeed = 0, plainN = 0;
for (let i = 1; i <= 120 * 30; i++) {
  plain.step(dt, view, busy);
  for (const id of plain.laneOverlaps()) plainOverlaps.add(id);
  accessCheck(plain, plainForbidden);
  if (i > 30 * 30) { plainSpeed += plain.meanSpeed(); plainN++; }
}
console.log("--- emergency vehicles off, 2 minutes");
console.log(`graph ${JSON.stringify(plain.size)}; mean ${((plainSpeed / plainN) * 3.6).toFixed(1)} km/h; spawned ${plain.stats.spawned}, ` +
  `deadlocks ${plain.stats.deadlocks}; overlaps ${plainOverlaps.size}; on closed lanes ${plainForbidden.size}; emergency ${plain.stats.emergency}`);

// Emergency scenarios on real streets (PLAN_NEXT.md item 8): a siren put on the street every 15 s (when the last one
// has gone) for 3 minutes, after 30 s of traffic, against the same run without them. Per scenario: the sirens' mean
// speed on the street as a share of their free-flow speed there (the same sirens with no other traffic), cars passed while aside, overtakes, overlaps (only a siren passing a car that
// stands aside may share its lane), cars still aside 15 s after the siren has gone, and deadlocks.
interface Scenario { name: string; street: string; x: number; y: number; want: number }
const SCENARIOS: Scenario[] = [
  { name: "two lanes, Boulevard Royal", street: "Boulevard Royal", x: 7025, y: 5515, want: 0.7 },
  // Avenue Pasteur ends at the Allée Scheffer lights, whose queue often reaches back over the junction: a siren
  // waits there for room as everyone does (40% before item 8).
  { name: "one lane two-way, Avenue Pasteur", street: "Avenue Pasteur", x: 9458, y: 3413, want: 0.45 },
  { name: "one lane two-way, Rue Guillaume Schneider", street: "Rue Guillaume Schneider", x: 9458, y: 3413, want: 0.5 },
  { name: "narrow two-way, Rue Michel Lentz", street: "Rue Michel Lentz", x: 9458, y: 3413, want: 0.5 },
  { name: "narrow one-way, Avenue Émile Reuter", street: "Avenue Émile Reuter", x: 7615, y: 5801, want: 0.5 },
  { name: "signalled, Boulevard Prince Henri", street: "Boulevard Prince Henri", x: 7025, y: 5515, want: 0.5 },
];
const scenarioFails: string[] = [];
console.log("--- emergency scenarios, 3 minutes each");
for (const sc of SCENARIOS) {
  const run = (sirens: boolean, busy = 1) => {
    const t = new Traffic(lines.roads, { areas: [{ x0: 0, y0: 0, w: 26624, h: 14336 }], seed: 7 });
    const v = { x0: sc.x - 700, y0: sc.y - 450, x1: sc.x + 700, y1: sc.y + 450 };
    const over = new Set<string>();
    let spawned = 0, lastSpawn = -1e9, stale = 0, onS = 0, onM = 0;
    for (let i = 1; i <= 210 * 30; i++) {
      t.step(dt, v, busy);
      const sec = i * dt;
      for (const q of t.sirenStates()) if (q.street === sc.street) { onS += dt; onM += q.v * dt; }
      if (sirens && sec > 30 && sec - lastSpawn > 15 && t.emergencyAlive().siren === 0) {
        if (t.spawnEmergency(spawned % 3 === 0 ? "ambulance" : spawned % 3 === 1 ? "police" : "fire", true, sc.street)) spawned++;
        lastSpawn = sec;
      }
      if (i % 15 === 0) {
        const ids = t.laneOverlaps();
        for (let k = 0; k < ids.length; k += 2) over.add(`${ids[k]}:${ids[k + 1]}`);
        stale = Math.max(stale, t.asideStale(15));
      }
    }
    return { t, spawned, over: over.size, stale, speed: onM / Math.max(onS, 1e-9) };
  };
  const a = run(true), b = run(false), f = run(true, 0), st = a.t.stats;
  const share = a.speed / Math.max(f.speed, 0.1);
  console.log(`${sc.name}: sirens ${a.spawned}, speed ${(share * 100).toFixed(0)}% of free flow (${(f.speed * 3.6).toFixed(0)} km/h; want ${sc.want * 100}%), ` +
    `passed ${st.passed}, overtakes ${st.overtakes}, overlaps ${a.over}, aside 15 s after ${a.stale}, deadlocks ` +
    `${st.deadlocks} (without sirens ${b.t.stats.deadlocks})`);
  if (!a.spawned) scenarioFails.push(`${sc.name}: no siren could be put on the street`);
  if (share < sc.want) scenarioFails.push(`${sc.name}: siren speed ${(share * 100).toFixed(0)}% of free`);
  if (a.over) scenarioFails.push(`${sc.name}: ${a.over} overlaps`);
  if (a.stale) scenarioFails.push(`${sc.name}: ${a.stale} cars aside 15 s after the siren`);
  if (st.deadlocks > b.t.stats.deadlocks + 2) scenarioFails.push(`${sc.name}: deadlocks ${st.deadlocks} against ${b.t.stats.deadlocks}`);
}
if (scenarioFails.length) console.error("scenario failures:\n  " + scenarioFails.join("\n  "));

const ok = scenarioFails.length === 0 && mean > 15 && mean < 50 && everOverlapped.size <= Math.max(2, sim.stats.spawned * 0.002) &&
  sim.stats.deadlocks <= sim.stats.spawned * 0.02 && panOverlaps.size === 0 && pan.stats.alive > 20 &&
  forbidden.size === 0 && panForbidden.size === 0 && plainForbidden.size === 0 && plain.stats.emergency === 0 &&
  sim.stats.emergency > 0 && sim.stats.calls > 0;
if (!ok) { console.error("FAIL"); process.exit(1); }
console.log("ok");
