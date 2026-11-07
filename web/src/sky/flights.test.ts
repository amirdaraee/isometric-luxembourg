/**
 * Checks of the flight plan and the aircraft positions (src/sky/flights.ts) against public/data/flights.json.
 *
 *   node src/sky/flights.test.ts [--find]
 *
 * (Node 22.6+ runs TypeScript directly.) Exits non-zero on a wrong answer. --find lists the moments on
 * 2026-11-10 when a departure (runway 24) or an arrival (runway 06) is in the planes shots' views.
 */
import { readFileSync } from "node:fs";
import { dayPlan, planesAt, position, runwayFor, UP_PX_PER_M, type FlightsData } from "./flights.ts";

let failed = 0;
function check(what: string, ok: boolean, got?: unknown) {
  if (ok) return;
  failed++;
  console.error(`FAIL ${what}${got === undefined ? "" : `: ${JSON.stringify(got)}`}`);
}

const data = JSON.parse(readFileSync(new URL("../../public/data/flights.json", import.meta.url), "utf8")) as FlightsData;

// the same plan for the same date, a different one for another date
const a = dayPlan("2026-11-10"), b = dayPlan("2026-11-10"), c = dayPlan("2026-11-11");
check("same date, same plan", JSON.stringify(a) === JSON.stringify(b));
check("another date, another plan", JSON.stringify(a) !== JSON.stringify(c));
check("92 movements", a.length === 92, a.length);
check("sorted by time", a.every((m, i) => i === 0 || a[i - 1].t <= m.t));
const lux = a.filter((m) => m.airline === "luxair"), cv = a.filter((m) => m.airline === "cargolux");
check("Luxair 40 + 40", lux.filter((m) => m.kind === "dep").length === 40 && lux.filter((m) => m.kind === "arr").length === 40);
check("Luxair from 06:00 to 23:00", lux.every((m) => m.t >= 6 * 3600 && m.t <= 23 * 3600),
  [lux[0].t / 3600, lux[lux.length - 1].t / 3600]);
check("Cargolux 12, all 747-8F", cv.length === 12 && cv.every((m) => m.type === "b748"));
check("Cargolux at night at most 4", cv.filter((m) => m.t < 6 * 3600 || m.t >= 23 * 3600).length <= 4);
check("every time within the day", a.every((m) => m.t >= 0 && m.t < 24 * 3600));

// runway from the wind
check("south-west wind: 24", runwayFor({ speed: 6, from: 240 }) === "24");
check("calm: 24", runwayFor({ speed: 0, from: 80 }) === "24");
check("east wind 6 m/s: 06", runwayFor({ speed: 6, from: 80 }) === "06");
check("light east wind: 24", runwayFor({ speed: 2, from: 60 }) === "24");

// positions: a departure climbs from lift-off, an arrival comes down to touchdown
const dep = a.find((m) => m.kind === "dep" && m.airline === "luxair")!;
const p1 = position(dep, data, dep.t + 30, "24"), p2 = position(dep, data, dep.t + 90, "24");
check("departure on its track", !!p1 && !!p2);
if (p1 && p2) check("departure climbs", p2.h > p1.h, [p1.h, p2.h]);
const arr = a.find((m) => m.kind === "arr")!;
const q1 = position(arr, data, arr.t - 80, "06"), q2 = position(arr, data, arr.t - 20, "06");
check("arrival on final", !!q1 && !!q2);
if (q1 && q2) check("arrival descends", q2.h < q1.h, [q1.h, q2.h]);
check("departure on 06 stays off the map", position(dep, data, dep.t + 60, "06") === null);
check("no aircraft long before or after", position(dep, data, dep.t - 60, "24") === null && position(dep, data, dep.t + 3600, "24") === null);

if (process.argv.includes("--find")) {
  // the shots: #16000,8000,0.15 and #12000,8700,0.25 at 1280 x 800
  const views = [{ name: "day #16000,8000,0.15", x: 16000, y: 8000, z: 0.15, rwy: "24" as const },
    { name: "east wind #12000,8700,0.25", x: 12000, y: 8700, z: 0.25, rwy: "06" as const }];
  for (const v of views) {
    const hw = 640 / v.z, hh = 400 / v.z, hits: string[] = [];
    for (let s = 6 * 3600; s < 23.5 * 3600; s += 15) {
      const inView = planesAt(a, data, s, v.rwy).filter((p) => p.h > 2 && Math.abs(p.gx - v.x) < hw * 0.8 &&
        Math.abs(p.gy - p.h * UP_PX_PER_M - v.y) < hh * 0.8);
      if (inView.length) hits.push(`${(s / 3600).toFixed(3)} h ${inView.map((p) => `${p.type} ${p.kind} ${Math.round(p.h)} m`).join(", ")}`);
    }
    console.log(`${v.name}: ${hits.length} moments\n  ${hits.filter((_, i) => i % 6 === 0).slice(0, 40).join("\n  ")}`);
  }
}

if (failed) { console.error(`${failed} check(s) failed`); process.exit(1); }
console.log("flights: all checks passed");
