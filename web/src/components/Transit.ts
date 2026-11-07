// Real trams and trains from the national timetable (GTFS, data.public.lu, CC BY), see pipeline/build_transit.py.
// Positions come from the clock: each trip lists [arrival s, departure s, distance along its track shape].

import { drawVehicle, spriteLength, type Sprites } from "./sprites";

export interface TransitData {
  shapes: number[][];
  /** d: day types the trip runs on (1 weekday, 2 Saturday, 4 Sunday and public holidays). */
  trips: { s: number; k: "tram" | "train"; n: string; t: [number, number, number][]; d?: number }[];
}
interface Shape { p: number[]; cum: number[]; len: number; box: [number, number, number, number] }

export function prepareShapes(d: TransitData): Shape[] {
  return d.shapes.map((p) => {
    const cum = [0];
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < p.length; i += 2) {
      x0 = Math.min(x0, p[i]); x1 = Math.max(x1, p[i]); y0 = Math.min(y0, p[i + 1]); y1 = Math.max(y1, p[i + 1]);
      if (i) cum.push(cum[cum.length - 1] + Math.hypot(p[i] - p[i - 2], p[i + 1] - p[i - 1]));
    }
    return { p, cum, len: cum[cum.length - 1], box: [x0, y0, x1, y1] };
  });
}

function at(s: Shape, d: number): [number, number, number] {
  d = Math.min(Math.max(d, 0), s.len);
  let lo = 1, hi = s.cum.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (s.cum[mid] < d) lo = mid + 1; else hi = mid; }
  const i = lo, a = (i - 1) * 2, seg = s.cum[i] - s.cum[i - 1] || 1, f = (d - s.cum[i - 1]) / seg;
  const dx = s.p[a + 2] - s.p[a], dy = s.p[a + 3] - s.p[a + 1];
  return [s.p[a] + dx * f, s.p[a + 1] + dy * f, Math.atan2(dy, dx)];
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

/** Today's day type in Luxembourg: 1 weekday, 2 Saturday, 4 Sunday or public holiday. */
export function luxDayMask(now = new Date()): number {
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
const TRAM = { car: 45 / MPP, width: 2.65 / MPP, cars: 1 };
const TRAIN = { car: 26.8 / MPP, width: 2.9 / MPP, cars: 4 };

/** Draw every vehicle running at `sec`. `toScreen` maps image px to screen px; `visible` says whether a point shows. */
export function drawTransit(g: CanvasRenderingContext2D, d: TransitData, shapes: Shape[], sec: number, z: number,
  ox: number, oy: number, W: number, H: number, visible: (x: number, y: number) => boolean, night: number,
  spr?: Sprites | null) {
  // With sprites, every section is collected first and drawn far to near (by screen y), so nearer ones overlap.
  const queue: { type: string; sx: number; sy: number; h: number; lit: boolean }[] = [];
  const mask = luxDayMask();
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
      const dir = t[t.length - 1][2] >= t[0][2] ? 1 : -1;
      if (spr) {
        // Luxtram: end, three middle sections, end (turned round); CFL push-pull: cab, coaches, locomotive.
        const types = tr.k === "tram" ? ["tram_end", "tram_mid", "tram_mid", "tram_mid", "tram_end"]
          : ["train_cab", "train_coach", "train_coach", "train_loco"];
        let back = 0;
        types.forEach((type, i) => {
          // lengths along the track are on-screen map px, so a section takes its foreshortened length
          const L0 = (spriteLength(spr, type) || (tr.k === "tram" ? 9 : 26) / MPP) + 0.4 / MPP;
          const h0 = at(sh, dist - dir * back)[2];
          const L = L0 * shrink(h0);
          const centre = dist - dir * (back + L / 2);
          back += L;
          const [x, y, ang] = at(sh, centre);
          const sx = x * z + ox, sy = y * z + oy;
          if (sx < -200 || sx > W + 200 || sy < -200 || sy > H + 200 || !visible(x, y)) return;
          const forward = ang + (dir < 0 ? Math.PI : 0);
          const last = i === types.length - 1;
          queue.push({ type, sx, sy, h: tr.k === "tram" && last ? forward + Math.PI : forward, lit: night > 0.05 });
        });
        continue;
      }
      const spec = tr.k === "tram" ? TRAM : TRAIN;
      for (let c = 0; c < spec.cars; c++) {
        const centre = dist - dir * (c + 0.5) * (spec.car + 1.2 / MPP);
        const [x, y, ang] = at(sh, centre);
        const sx = x * z + ox, sy = y * z + oy;
        if (sx < -200 || sx > W + 200 || sy < -200 || sy > H + 200 || !visible(x, y)) continue;
        drawCar(g, sx, sy, ang + (dir < 0 ? Math.PI : 0), spec.car * z, Math.max(spec.width * z, 2), tr.k, c, spec.cars, night);
      }
    }
  }
  if (spr && queue.length) {
    queue.sort((a, b) => a.sy - b.sy);
    for (const q of queue) {
      drawVehicle(g, spr, q.type, 0, q.sx, q.sy, q.h, z);
      if (q.lit) {   // lit windows at night: a warm glow over the body
        g.globalAlpha = night * 0.55;
        g.fillStyle = "rgba(255,206,130,1)";
        g.beginPath(); g.ellipse(q.sx, q.sy - 2.2 / MPP * z, Math.max(2, 3.5 / MPP * z), Math.max(1, 1.2 / MPP * z), 0, 0, Math.PI * 2); g.fill();
        g.globalAlpha = 1;
      }
    }
  }
}

function drawCar(g: CanvasRenderingContext2D, x: number, y: number, ang: number, L: number, Wd: number,
  kind: "tram" | "train", i: number, n: number, night: number) {
  g.save();
  g.translate(x, y);
  g.rotate(ang);
  // shadow, then a darker "side" strip to suggest height in the isometric view
  g.fillStyle = "rgba(0,0,0,.28)"; g.fillRect(-L / 2 + 1.5, -Wd / 2 + 2, L, Wd);
  if (kind === "tram") {
    g.fillStyle = "#1f2125"; g.fillRect(-L / 2, -Wd / 2, L, Wd);                     // black body
    g.fillStyle = "#b9bec6"; g.fillRect(-L / 2, -Wd / 2, L, Wd * 0.38);              // silver roof band
    g.fillStyle = "#2e8fa8"; for (let k = 1; k < 5; k++) g.fillRect(-L / 2 + (L * k) / 5 - 1, -Wd / 2, 2, Wd); // coloured door glass
  } else {
    g.fillStyle = "#f2f2ef"; g.fillRect(-L / 2, -Wd / 2, L, Wd);                     // white double-deck coach
    g.fillStyle = "#d4202b"; g.fillRect(-L / 2, Wd * 0.22, L, Wd * 0.28);            // red lower band
    g.fillStyle = "#d4202b"; g.fillRect(-L * 0.06, -Wd / 2, L * 0.06, Wd);           // red doors
    if (i === 0) { g.fillStyle = "#d4202b"; g.fillRect(L / 2 - L * 0.1, -Wd / 2, L * 0.1, Wd); }   // red nose
    if (i === n - 1) { g.fillStyle = "#d4202b"; g.fillRect(-L / 2, -Wd / 2, L * 0.1, Wd); }
  }
  g.strokeStyle = "rgba(20,20,24,.85)"; g.lineWidth = 1; g.strokeRect(-L / 2, -Wd / 2, L, Wd);
  if (night > 0.05) {   // lit windows and head/tail lights at night
    g.globalAlpha = night;
    g.fillStyle = "rgba(255,214,140,.9)";
    for (let k = 0; k < 6; k++) g.fillRect(-L / 2 + (L * (k + 0.5)) / 6 - L * 0.04, -Wd * 0.12, L * 0.08, Wd * 0.24);
    g.globalAlpha = 1;
  }
  g.restore();
}
