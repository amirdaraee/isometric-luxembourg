// Real trams and trains from the national timetable (GTFS, data.public.lu, CC BY), see pipeline/build_transit.py.
// Positions come from the clock: each trip lists [arrival s, departure s, distance along its track shape]. The track
// shapes are the OSM rail lines the painting followed, as runs over lines.json ways, so every section knows its way
// and its distance along it: Overlay lifts it onto bridge decks (occlusion deckLift), hides it in tunnels and cuts
// it against the foreground like the cars.
//
// This module has no drawing and no DOM, so the headless test (transit.test.ts) runs it in Node.

import { today } from "../testParams.ts";

export interface TransitData {
  shapes: number[][];
  /** Per shape, the same points moved onto the rails as painted (pipeline/fit_roads.py). Distances are measured on
   * `shapes` (stop times refer to them); positions and headings are drawn on `fit`. */
  fit?: number[][];
  /** Per shape: the stretches of lines.json rail ways it runs over, [way id, s from, s to] (map px along the way). */
  runs?: [number, number, number][][];
  /** The ids of the ways in `runs` that are tunnels. */
  tunnels?: number[];
  /** d: day types the trip runs on (1 weekday, 2 Saturday, 4 Sunday and public holidays). */
  trips: { s: number; k: "tram" | "train"; n: string; t: [number, number, number][]; d?: number }[];
}
/** One stretch of a shape along one way: shape distance d0..d1 maps onto way distance s0 + (d - d0) * k. */
interface Run { d0: number; d1: number; id: number; s0: number; k: number; tunnel: boolean }
export interface Shape {
  /** p: the shape (distances along it); q: where it is drawn (the fitted points, else p), same number of points. */
  p: number[]; q: number[]; cum: number[]; len: number; box: [number, number, number, number];
  runs: Run[];
  /** Shape distance intervals in tunnels, merged. */
  tunnels: [number, number][];
}

export function prepareShapes(d: TransitData, fitted = true): Shape[] {
  const tun = new Set(d.tunnels ?? []);
  return d.shapes.map((p, si) => {
    const f0 = fitted ? d.fit?.[si] : undefined;
    const q = f0 && f0.length === p.length ? f0 : p;
    const cum = [0];
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < p.length; i += 2) {
      x0 = Math.min(x0, p[i], q[i]); x1 = Math.max(x1, p[i], q[i]);
      y0 = Math.min(y0, p[i + 1], q[i + 1]); y1 = Math.max(y1, p[i + 1], q[i + 1]);
      if (i) cum.push(cum[cum.length - 1] + Math.hypot(p[i] - p[i - 2], p[i + 1] - p[i - 1]));
    }
    const len = cum[cum.length - 1];
    // The runs' lengths along their ways add up to the shape's length (both are the same polylines in map px), up to
    // the rounding of the stored numbers: scale them onto the shape so the two never drift apart.
    const raw = d.runs?.[si] ?? [];
    const total = raw.reduce((a, r) => a + Math.abs(r[2] - r[1]), 0);
    const f = total > 0 ? len / total : 1;
    const runs: Run[] = [];
    let at = 0;
    for (const [id, a, b] of raw) {
      const L = Math.abs(b - a) * f;
      runs.push({ d0: at, d1: at + L, id, s0: a, k: (b >= a ? 1 : -1) / f, tunnel: tun.has(id) });
      at += L;
    }
    const tunnels: [number, number][] = [];
    for (const r of runs) {
      if (!r.tunnel) continue;
      const last = tunnels[tunnels.length - 1];
      if (last && r.d0 - last[1] < 1) last[1] = r.d1; else tunnels.push([r.d0, r.d1]);
    }
    return { p, q, cum, len, box: [x0, y0, x1, y1], runs, tunnels };
  });
}

/** Point and screen heading at distance d along a shape. */
export function at(s: Shape, d: number): [number, number, number] {
  d = Math.min(Math.max(d, 0), s.len);
  let lo = 1, hi = s.cum.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (s.cum[mid] < d) lo = mid + 1; else hi = mid; }
  const i = lo, a = (i - 1) * 2, seg = s.cum[i] - s.cum[i - 1] || 1, f = (d - s.cum[i - 1]) / seg;
  const q = s.q, dx = q[a + 2] - q[a], dy = q[a + 3] - q[a + 1];
  return [q[a] + dx * f, q[a + 1] + dy * f, Math.atan2(dy, dx)];
}

/** The lines.json way at distance d along a shape and the distance along that way (map px), or null for a shape
 * without runs. */
export function wayAt(s: Shape, d: number): { id: number; s: number; tunnel: boolean } | null {
  const R = s.runs;
  if (!R.length) return null;
  let lo = 0, hi = R.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (R[mid].d1 < d) lo = mid + 1; else hi = mid; }
  const r = R[lo];
  return { id: r.id, s: r.s0 + (Math.min(Math.max(d, r.d0), r.d1) - r.d0) * r.k, tunnel: r.tunnel };
}

/** The shape between distances d0 and d1 as map px points [x, y, x, y, ...]. */
export function stretch(s: Shape, d0: number, d1: number): number[] {
  d0 = Math.max(0, d0); d1 = Math.min(s.len, d1);
  if (d1 <= d0) return [];
  const a = at(s, d0), b = at(s, d1), out = [a[0], a[1]];
  for (let i = 1; i < s.cum.length - 1; i++) if (s.cum[i] > d0 && s.cum[i] < d1) out.push(s.q[i * 2], s.q[i * 2 + 1]);
  out.push(b[0], b[1]);
  return out;
}

/** Seconds since midnight, Luxembourg time. */
export function luxSeconds(now = new Date()): number {
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Luxembourg", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" })
    .formatToParts(now).reduce((o, p) => ({ ...o, [p.type]: p.value }), {} as Record<string, string>);
  return +parts.hour * 3600 + +parts.minute * 60 + +parts.second + now.getMilliseconds() / 1000;
}

/** Easter Sunday (Gregorian), as [month 1-12, day]. */
function easter(y: number): [number, number] {
  const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  return [Math.floor((h + l - 7 * m + 114) / 31), ((h + l - 7 * m + 114) % 31) + 1];
}

/** Today's day type in Luxembourg (or that of ?date=): 1 weekday, 2 Saturday, 4 Sunday or public holiday. */
export function luxDayMask(now = today()): number {
  const p = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Luxembourg", year: "numeric", month: "numeric", day: "numeric", weekday: "short" })
    .formatToParts(now).reduce((o, x) => ({ ...o, [x.type]: x.value }), {} as Record<string, string>);
  const y = +p.year, mo = +p.month, da = +p.day;
  const [em, ed] = easter(y);
  const eDay = Date.UTC(y, em - 1, ed), today = Date.UTC(y, mo - 1, da), day = 86400000;
  const fixed = ["1-1", "5-1", "5-9", "6-23", "8-15", "11-1", "12-25", "12-26"];   // incl. Europe Day and National Day
  const moving = [1, 39, 50].map((n) => eDay + n * day);                           // Easter Monday, Ascension, Whit Monday
  if (fixed.includes(`${mo}-${da}`) || moving.includes(today) || p.weekday === "Sun") return 4;
  return p.weekday === "Sat" ? 2 : 1;
}

const MPP = 0.25;
/** How much a ground length shrinks on screen along screen heading h (full left-right, half up-down). */
function shrink(h: number): number {
  const c = Math.cos(h), sn = Math.sin(h);
  return 1 / Math.sqrt(c * c + 4 * sn * sn);
}
/** Luxtram: end, three middle sections, end (turned round); CFL push-pull: cab, coaches, locomotive. */
const TYPES = {
  tram: ["tram_end", "tram_mid", "tram_mid", "tram_mid", "tram_end"],
  train: ["train_cab", "train_coach", "train_coach", "train_loco"],
};
/** Section lengths in metres when the sprites are not there (the placeholder drawing). */
const DEFAULT_M: Record<string, number> = { tram_end: 9.5, tram_mid: 8.7, train_cab: 26.8, train_coach: 26.8, train_loco: 19 };
/** Vehicle heights in metres, for the foreground cut and the tunnel clip. */
export const TRANSIT_HEIGHT_M = { tram: 3.6, train: 4.6 };

/** One tram or train section to draw, in map px. */
export interface Section {
  kind: "tram" | "train";
  type: string;
  /** Ground centre, map px. */
  x: number; y: number;
  /** Screen heading for the sprite. */
  h: number;
  /** 1 the leading section (headlamps), -1 the last one (tail lamps), 0 between. */
  end: number;
  /** lines.json way under the centre and the distance along it (map px); way -1 for a shape without runs. */
  way: number; s: number;
  /** The section reaches into a tunnel: draw it, then clip it at the portal. */
  portal: boolean;
  shape: number;
  /** The section's stretch along its shape. */
  d0: number; d1: number;
}

/**
 * Every tram and train section running at `sec` (seconds since midnight) on day type `mask`, inside the map px box
 * `box` (x0, y0, x1, y1), far to near is the caller's business. Sections wholly inside a tunnel are left out.
 * `lengthPx(type)` gives a section's length in map px (the sprite's), or 0 for the default.
 */
export function transitSections(d: TransitData, shapes: Shape[], sec: number, mask: number,
  box: [number, number, number, number], lengthPx: (type: string) => number = () => 0): Section[] {
  const out: Section[] = [];
  for (const tr of d.trips) {
    if (tr.d !== undefined && !(tr.d & mask)) continue;
    const t = tr.t;
    for (const s2 of [sec, sec + 86400]) {   // trips after midnight are stored with times > 24 h
      if (s2 < t[0][0] || s2 > t[t.length - 1][1]) continue;
      let dist = t[t.length - 1][2];
      for (let i = 0; i < t.length; i++) {
        if (s2 <= t[i][1]) {
          if (s2 >= t[i][0] || i === 0) { dist = t[i][2]; break; }       // dwelling at a stop
          const a = t[i - 1], b = t[i], f = (s2 - a[1]) / Math.max(b[0] - a[1], 1);
          // ease in/out between stops
          const e = f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;
          dist = a[2] + (b[2] - a[2]) * e;
          break;
        }
      }
      const sh = shapes[tr.s];
      if (sh.box[2] < box[0] - 400 || sh.box[0] > box[2] + 400 || sh.box[3] < box[1] - 400 || sh.box[1] > box[3] + 400) continue;
      const dir = t[t.length - 1][2] >= t[0][2] ? 1 : -1;
      const types = TYPES[tr.k];
      let back = 0;
      types.forEach((type, i) => {
        // lengths along the track are on-screen map px, so a section takes its foreshortened length
        const L0 = (lengthPx(type) || DEFAULT_M[type] / MPP) + 0.4 / MPP;
        const h0 = at(sh, dist - dir * back)[2];
        const L = L0 * shrink(h0);
        const a = dist - dir * back, b = dist - dir * (back + L);
        const centre = (a + b) / 2;
        back += L;
        const lo = Math.min(a, b), hi = Math.max(a, b);
        if (hi < 0 || lo > sh.len) return;                                    // not on the track yet, or past its end
        let portal = false;
        for (const [t0, t1] of sh.tunnels) {
          if (lo >= t0 && hi <= t1) return;                                    // wholly in a tunnel
          if (hi > t0 && lo < t1) portal = true;
        }
        const [x, y, ang] = at(sh, centre);
        if (x < box[0] || x > box[2] || y < box[1] || y > box[3]) return;
        const forward = ang + (dir < 0 ? Math.PI : 0);
        const last = i === types.length - 1;
        const w = wayAt(sh, centre);
        out.push({
          kind: tr.k, type, x, y, h: tr.k === "tram" && last ? forward + Math.PI : forward,
          end: i === 0 ? 1 : last ? -1 : 0, way: w ? w.id : -1, s: w ? w.s : 0, portal, shape: tr.s, d0: lo, d1: hi,
        });
      });
    }
  }
  return out;
}
