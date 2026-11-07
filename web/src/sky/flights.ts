// The aircraft over the city: a believable daily plan of Luxair and Cargolux movements at Findel, and where each
// one is at a given moment. Free of DOM and Vite imports, so that flights.test.ts runs in Node.
//
// The plan is seeded from the date, and positions come from the clock (like the trains), so every visitor sees the
// same aircraft at the same moment. The tracks come from pipeline/build_flights.py (web/public/data/flights.json).
//
//   const plan = dayPlan("2026-11-10");
//   const now = planesAt(plan, flightsData, 10.25 * 3600, runwayFor(wind));

/** Sprite types (web/public/sprites/planes.json). */
export type PlaneType = "b748" | "b738" | "e295" | "dh8d";
export type Runway = "06" | "24";

export interface Movement {
  id: number;
  airline: "luxair" | "cargolux";
  type: PlaneType;
  kind: "dep" | "arr";
  /** seconds after local midnight: lift-off for a departure, touchdown for an arrival */
  t: number;
  /** 0 or 1: which way a departure turns (north or south) */
  side: number;
}

export interface Track {
  runway: Runway;
  kind: "dep" | "arr";
  /** metres along the full track at the first sample kept */
  s0: number;
  /** full track length, metres (an arrival: to touchdown) */
  len: number;
  step: number;
  /** gx, gy (ground map px), h (metres above the ground), per sample */
  p: number[];
}

export interface FlightsData {
  elevation: number;
  runway: Record<Runway, [number, number]>;
  tracks: Record<string, Track>;
}

export interface PlaneNow {
  id: number;
  type: PlaneType;
  airline: Movement["airline"];
  kind: Movement["kind"];
  /** ground point under the aircraft, map px */
  gx: number;
  gy: number;
  /** metres above the ground there */
  h: number;
  /** direction of travel on screen (radians, y down) */
  heading: number;
  /** nose up (climbing after take-off) */
  climb: boolean;
}

/** Ground speeds, m/s: climbing out, and on approach. */
const SPEED: Record<PlaneType, [number, number]> = {
  b748: [88, 74], b738: [84, 70], e295: [82, 68], dh8d: [68, 60],
};

/** Runway 06/24 points 064 / 244 degrees. */
const RWY24 = 244;

/** The runway in use for a wind (m/s, from degrees): 24 unless the tailwind on it is over 2.5 m/s (5 knots). */
export function runwayFor(wind: { speed: number; from: number }): Runway {
  const tail = -wind.speed * Math.cos(((wind.from - RWY24) * Math.PI) / 180);
  return tail > 2.5 ? "06" : "24";
}

/** A small seeded generator (mulberry32). */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}

const HOUR = 3600;

/**
 * The day's movements for a date ("YYYY-MM-DD", Luxembourg time), sorted by time.
 *  - Luxair: 40 departures and 40 arrivals between 06:00 and 23:00, a little busier in the morning and evening
 *    banks; Dash 8-400s on the short routes, 737s and E195-E2s on the rest.
 *  - Cargolux: 12 Boeing 747-8F movements (6 each way), most of them in the evening and at night. Night movements
 *    (23:00 to 06:00) are kept to four, a simplification of the airport's night rules.
 */
export function dayPlan(date: string): Movement[] {
  const r = rng(hash(date));
  const out: Movement[] = [];
  let id = 0;
  // Luxair: a spread over 06:00-23:00 with two banks (07:00-09:00 and 17:00-20:00) slightly denser
  const luxTime = () => {
    for (;;) {
      const t = 6 * HOUR + r() * 17 * HOUR;
      const hr = t / HOUR;
      const w = (hr >= 7 && hr < 9) || (hr >= 17 && hr < 20) ? 1 : 0.6;
      if (r() < w) return Math.round(t);
    }
  };
  for (const kind of ["dep", "arr"] as const) {
    for (let i = 0; i < 40; i++) {
      const x = r();
      const type: PlaneType = x < 0.35 ? "dh8d" : x < 0.75 ? "b738" : "e295";
      out.push({ id: id++, airline: "luxair", type, kind, t: luxTime(), side: r() < 0.5 ? 0 : 1 });
    }
  }
  // Cargolux: 2 in the day, 6 in the evening, 4 at night (after 23:00 or before 06:00), half of them departures
  const slots: [number, number][] = [
    [10, 17], [10, 17], [17, 23], [17, 23], [17, 23], [17, 23], [17, 23], [17, 23], [23, 24], [23, 24], [0, 6], [0, 6],
  ];
  slots.forEach(([a, b], i) => {
    const t = Math.round((a + r() * (b - a)) * HOUR);
    out.push({ id: id++, airline: "cargolux", type: "b748", kind: i % 2 ? "arr" : "dep", t, side: r() < 0.5 ? 0 : 1 });
  });
  return out.sort((p, q) => p.t - q.t);
}

/** The track a movement flies with the runway in use (null: it stays off the map). */
export function trackName(m: Movement, rwy: Runway): string | null {
  if (m.kind === "dep") return rwy === "24" ? (m.side ? "dep24s" : "dep24n") : null;
  return rwy === "06" ? "arr06" : "arr24";
}

/** Where a movement is at `secs` after midnight, or null when it is not on its kept track. */
export function position(m: Movement, data: FlightsData, secs: number, rwy: Runway): PlaneNow | null {
  const name = trackName(m, rwy);
  const tr = name ? data.tracks[name] : undefined;
  if (!tr) return null;
  const [vDep, vArr] = SPEED[m.type];
  let s: number;
  if (m.kind === "dep") {
    s = (secs - m.t) * vDep;
  } else {
    // a high downwind is flown faster than the final
    const v = name === "arr24" ? vArr * 1.5 : vArr;
    // after touchdown the landing roll slows to a stop over about 2000 m
    s = secs <= m.t ? tr.len - (m.t - secs) * v : tr.len + Math.min(2000, (secs - m.t) * v * 0.5);
  }
  const n = tr.p.length / 3;
  const f = (s - tr.s0) / tr.step;
  if (f < 0 || f > n - 1) return null;
  const i = Math.min(n - 2, Math.floor(f)), k = f - i;
  const a = i * 3, b = a + 3;
  const gx = tr.p[a] + (tr.p[b] - tr.p[a]) * k, gy = tr.p[a + 1] + (tr.p[b + 1] - tr.p[a + 1]) * k;
  const h = tr.p[a + 2] + (tr.p[b + 2] - tr.p[a + 2]) * k;
  const heading = Math.atan2(tr.p[b + 1] - tr.p[a + 1], tr.p[b] - tr.p[a]);
  return { id: m.id, type: m.type, airline: m.airline, kind: m.kind, gx, gy, h, heading, climb: m.kind === "dep" && h > 2 && h < 1200 };
}

/** Every aircraft on a kept track at `secs` after midnight (yesterday's late movements included). */
export function planesAt(plan: Movement[], data: FlightsData, secs: number, rwy: Runway, yesterday: Movement[] = []): PlaneNow[] {
  const out: PlaneNow[] = [];
  for (const m of plan) {
    if (Math.abs(m.t - secs) > 1800) continue;   // no track lasts half an hour
    const p = position(m, data, secs, rwy);
    if (p) out.push(p);
  }
  for (const m of yesterday) {
    if (m.t < 23 * HOUR) continue;
    const p = position(m, data, secs + 24 * HOUR, rwy);
    if (p) out.push(p);
  }
  return out;
}

/** Map px an aircraft is drawn above its ground point, per metre of height (cos 30 degrees / 0.25 m). */
export const UP_PX_PER_M = 0.8660254 / 0.25;

/** Where the shadow of a point `h` metres up falls, relative to its ground point, in map px (the map's sun from the
 * upper left, as in pipeline/build_sprites.py). */
export function shadowOffset(h: number): [number, number] {
  return [2.07 * h, 2.17 * h];
}
