// Live effects of events (web/public/events/events.json, made by pipeline/events/event_patch.py manifest):
// fireworks, New Year sparkles, bonfires with smoke, a stream of runners, a torchlight procession and bats.
// Everything is computed from the clock (no state kept between frames), so every visitor sees the same thing and a
// frame can be drawn at any moment. Nothing flashes: bursts fade in over a fraction of a second and the brightest
// alpha is kept under 0.9, with no full-screen light.

/** A firework display. kind "show": rockets from `at`, bursting about `height` + `burst` px up; "sparkles": small
 * scattered bursts over a square `spread` px wide round `at`. Hours `from`..`to` (to may pass 24). day: which day
 * of the event (0 first, -1 last); absent = every day. */
export interface Fireworks {
  kind: "show" | "sparkles"; at: [number, number]; height: number; burst?: number; spread?: number;
  from: number; to: number; rate: number; day?: number;
}
export interface Bonfire { at: [number, number]; size: number }
export interface Stream { route: [number, number][]; from: number; to: number; speed?: number; density?: number; day?: number }
export interface Bats { at: [number, number]; n: number; r: number }

export interface EventEffects {
  season?: string;
  patches?: { x0: number; y0: number; w: number; day?: string; night?: string }[];
  rides?: string;
  fireworks?: Fireworks[];
  bonfires?: Bonfire[];
  /** bonfires burn from sunset + dusk[0] to sunset + dusk[1] hours */
  dusk?: [number, number];
  runners?: Stream;
  torches?: Stream;
  bats?: Bats[];
}

export interface FxView {
  /** screen = map * z + (ox, oy) */
  z: number; ox: number; oy: number; W: number; H: number;
  /** seconds (real clock; 0 when reduced motion is asked for) */
  sec: number;
  /** the hour shown, 0..24 */
  hour: number;
  /** 0 day .. 1 night */
  night: number;
  /** sunset hour of the day shown */
  sunset: number;
  /** day of the event (0 = first) and days left (0 = last day); null when the event is previewed from the picker */
  dayIndex: [number, number] | null;
  glow: HTMLCanvasElement;
  still: boolean;
}

const MAP_MPP = 0.25;

/** Small fixed random numbers. */
function rnd(i: number): number {
  const s = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
}

function inHours(h: number, from: number, to: number): boolean {
  return (h >= from && h <= to) || (h + 24 >= from && h + 24 <= to);
}

function dayOk(want: number | undefined, v: FxView): boolean {
  if (want === undefined || !v.dayIndex) return true;
  return want >= 0 ? v.dayIndex[0] === want : v.dayIndex[1] === -want - 1;
}

const SHOW_COLOURS = ["#ff4d4d", "#ffffff", "#7cc8ff", "#ffd36b", "#ff8ad8", "#8dff9a"];

function dot(g: CanvasRenderingContext2D, glow: HTMLCanvasElement, x: number, y: number, r: number, a: number) {
  if (a <= 0.01) return;
  g.globalAlpha = Math.min(a, 0.9);
  g.drawImage(glow, x - r, y - r, r * 2, r * 2);
}

/** A firework spark: a solid core in its colour with a white heart, and a soft halo round it. */
function spark(g: CanvasRenderingContext2D, halo: HTMLCanvasElement, colour: string, x: number, y: number, r: number, a: number) {
  if (a <= 0.01) return;
  g.globalAlpha = Math.min(a, 0.9) * 0.55;
  g.drawImage(halo, x - r * 2.2, y - r * 2.2, r * 4.4, r * 4.4);
  g.globalAlpha = Math.min(a, 0.9);
  g.fillStyle = colour;
  g.beginPath(); g.arc(x, y, r * 0.55, 0, Math.PI * 2); g.fill();
  g.fillStyle = "#fffaf0";
  g.beginPath(); g.arc(x, y, r * 0.25, 0, Math.PI * 2); g.fill();
}

/** Tinted copies of the glow dot, one per colour, made once. */
const tinted = new Map<string, HTMLCanvasElement>();
function tint(glow: HTMLCanvasElement, colour: string): HTMLCanvasElement {
  let c = tinted.get(colour);
  if (c) return c;
  c = document.createElement("canvas");
  c.width = glow.width; c.height = glow.height;
  const g = c.getContext("2d")!;
  const r = g.createRadialGradient(c.width / 2, c.height / 2, 0, c.width / 2, c.height / 2, c.width / 2);
  r.addColorStop(0, "#ffffff");
  r.addColorStop(0.25, colour);
  r.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = r;
  g.fillRect(0, 0, c.width, c.height);
  tinted.set(colour, c);
  return c;
}

function fireworks(g: CanvasRenderingContext2D, f: Fireworks, v: FxView) {
  if (!inHours(v.hour, f.from, f.to) || !dayOk(f.day, v)) return;
  const { z, ox, oy, sec } = v;
  const show = f.kind === "show";
  const life = show ? 4.2 : 2.6, rise = show ? 1.6 : 0.9;
  const first = Math.floor((sec - life - rise) * f.rate), last = Math.floor(sec * f.rate);
  for (let i = first; i <= last; i++) {
    const t0 = i / f.rate + rnd(i) / f.rate;
    const t = sec - t0;
    if (t < 0 || t > rise + life) continue;
    const spread = show ? (f.burst ?? 300) * 0.7 : f.spread ?? 1500;
    const bx = f.at[0] + (rnd(i * 3 + 1) - 0.5) * spread;
    const by0 = f.at[1] + (show ? 0 : (rnd(i * 3 + 4) - 0.5) * spread * 0.5);
    const top = f.height + (show ? (f.burst ?? 300) * (0.55 + 0.45 * rnd(i * 3 + 2)) : 40 + 80 * rnd(i * 3 + 2));
    const colour = SHOW_COLOURS[Math.floor(rnd(i * 7 + 5) * SHOW_COLOURS.length)];
    const img = tint(v.glow, colour);
    if (t < rise) {
      // the rising rocket: a small warm spark with a short trail
      const k = t / rise, y = by0 - (f.height + (top - f.height) * (1 - (1 - k) * (1 - k)));
      for (let s = 0; s < 5; s++) dot(g, v.glow, bx * z + ox, (y + s * 8) * z + oy, Math.max(2.5, 4 * z), 0.8 - s * 0.15);
      continue;
    }
    const tb = t - rise, k = tb / life;
    const n = show ? 56 : 18;
    const R = (show ? (f.burst ?? 300) * 0.8 : 70) * (1 - Math.exp(-3.2 * tb));
    const fade = Math.min(1, tb * 6) * (1 - k) * (1 - k);
    const cx = bx, cy = by0 - top;
    const size = Math.max(show ? 3 : 2.2, (show ? 5 : 3.5) * z);
    for (let p = 0; p < n; p++) {
      const ang = (p / n) * Math.PI * 2 + rnd(i + p) * 0.2;
      const el = rnd(i * 13 + p) * 0.6 + 0.4;                      // a sphere seen from the side: some points nearer the centre
      const tw = 0.75 + 0.25 * Math.sin(sec * 20 + p);
      // the spark and a short trail behind it (where it was a moment ago)
      for (let tr = 0; tr < 3; tr++) {
        const tt = Math.max(tb - tr * 0.12, 0);
        const rr = R * (1 - Math.exp(-3.2 * tt)) / Math.max(1 - Math.exp(-3.2 * tb), 1e-3);
        const drop = 9 * tt * tt;                                   // gravity, map px
        const px = cx + Math.cos(ang) * rr * el, py = cy + Math.sin(ang) * rr * el * 0.9 + drop;
        if (tr === 0) spark(g, img, colour, px * z + ox, py * z + oy, size, fade * tw);
        else dot(g, img, px * z + ox, py * z + oy, size * (1 - tr * 0.25), fade * tw * (0.7 - tr * 0.2));
      }
    }
    const drop = 9 * tb * tb;
    // a soft light over the burst, never brighter than a street lamp
    dot(g, img, cx * z + ox, (cy + drop) * z + oy, R * z * 0.9, fade * 0.16);
  }
}

function bonfire(g: CanvasRenderingContext2D, b: Bonfire, v: FxView, dusk: [number, number]) {
  if (v.hour < v.sunset + dusk[0] || v.hour > v.sunset + dusk[1]) return;
  const { z, ox, oy, sec } = v;
  const x = b.at[0] * z + ox, y = b.at[1] * z + oy, s = b.size * z;
  if (x < -200 || y < -300 || x > v.W + 200 || y > v.H + 200) return;
  // smoke, drifting up and to the left (the usual westerly), behind the flames
  g.globalCompositeOperation = "source-over";
  for (let i = 0; i < 9; i++) {
    const k = ((sec * 0.12 + i / 9) % 1);
    g.globalAlpha = 0.22 * (1 - k) * Math.min(1, k * 5);
    g.fillStyle = v.night > 0.5 ? "#4a4f5c" : "#9a9890";
    g.beginPath();
    g.arc(x - k * 40 * s, y - (30 + k * 160) * s, (8 + k * 30) * s, 0, Math.PI * 2);
    g.fill();
  }
  g.globalCompositeOperation = "lighter";
  // the light on the ground
  const flick = 0.8 + 0.2 * Math.sin(sec * 11) * Math.sin(sec * 7.3 + 1);
  dot(g, tint(v.glow, "#ff8a30"), x, y - 4 * s, Math.max(40, 110 * s), 0.6 * flick * (0.4 + 0.6 * v.night));
  // flames: tongues that rise and shrink
  for (let i = 0; i < 7; i++) {
    const k = (sec * 1.6 + rnd(i)) % 1;
    const fx = x + (rnd(i * 5) - 0.5) * 12 * s + Math.sin(sec * 3 + i) * 2 * s;
    const fy = y - (6 + k * 28) * s;
    dot(g, tint(v.glow, k < 0.4 ? "#ffd27a" : "#ff6a1a"), fx, fy, Math.max(4, (16 - k * 10) * s), (1 - k) * 0.95);
  }
  // sparks
  for (let i = 0; i < 10; i++) {
    const k = (sec * 0.5 + rnd(i * 9)) % 1;
    dot(g, v.glow, x + (rnd(i * 3) - 0.5) * 30 * s - k * 10 * s, y - (20 + k * 90) * s, Math.max(2, 2.5 * z), (1 - k) * 0.9);
  }
  g.globalCompositeOperation = "source-over";
}

/** Cumulative lengths of a route (map px). */
const lengths = new WeakMap<object, number[]>();
function cum(route: [number, number][]): number[] {
  let c = lengths.get(route);
  if (c) return c;
  c = [0];
  for (let i = 1; i < route.length; i++) c.push(c[i - 1] + Math.hypot(route[i][0] - route[i - 1][0], route[i][1] - route[i - 1][1]));
  lengths.set(route, c);
  return c;
}

function stream(g: CanvasRenderingContext2D, st: Stream, v: FxView, look: "runners" | "torches") {
  if (!inHours(v.hour, st.from, st.to) || !dayOk(st.day, v)) return;
  const { z, ox, oy, sec } = v;
  const c = cum(st.route), L = c[c.length - 1];
  const speed = (st.speed ?? 1.2) / MAP_MPP;                           // map px per second
  const gap = 1 / ((st.density ?? 0.5) * MAP_MPP);                     // map px between people
  // the head of the stream moves on from the start; the tail stays at the start (people keep setting off)
  const head = Math.min(L, ((v.hour - st.from + 24) % 24) * 3600 * speed * 0.35 + 400);
  const phase = (sec * speed) % gap;
  // the stream as a whole: a soft band along the route as far as the head, so it reads from far out
  g.globalCompositeOperation = v.night > 0.3 ? "lighter" : "source-over";
  g.beginPath();
  for (let i = 0; i < st.route.length && c[i] <= head + 1; i++) {
    const q = st.route[i];
    if (i) g.lineTo(q[0] * z + ox, q[1] * z + oy); else g.moveTo(q[0] * z + ox, q[1] * z + oy);
  }
  g.lineCap = "round"; g.lineJoin = "round";
  g.globalAlpha = 1;
  g.strokeStyle = look === "torches" ? `rgba(255,140,50,${0.18 + 0.2 * v.night})`
    : v.night > 0.3 ? `rgba(255,236,170,${0.12 + 0.18 * v.night})` : "rgba(250,250,245,0.35)";
  g.lineWidth = Math.max(4, 18 * z);
  g.stroke();
  let seg = 1;
  for (let s = phase; s < head; s += gap) {
    while (seg < c.length - 1 && c[seg] < s) seg++;
    const a = st.route[seg - 1], b = st.route[seg], f = (s - c[seg - 1]) / Math.max(c[seg] - c[seg - 1], 1e-3);
    const i = Math.floor((s - phase) / gap);
    const side = (rnd(i) - 0.5) * 18, nx = -(b[1] - a[1]), ny = b[0] - a[0], nl = Math.hypot(nx, ny) || 1;
    const x = (a[0] + (b[0] - a[0]) * f + (nx / nl) * side) * z + ox;
    const y = (a[1] + (b[1] - a[1]) * f + (ny / nl) * side) * z + oy;
    if (x < -10 || y < -10 || x > v.W + 10 || y > v.H + 10) continue;
    if (look === "torches") {
      dot(g, tint(v.glow, "#ff9a3a"), x, y - 4 * z, Math.max(4, 8 * z), 0.8 + 0.2 * Math.sin(sec * 9 + i));
    } else if (v.night > 0.3) {
      // head torches and high-vis: small white and yellow lights
      dot(g, tint(v.glow, rnd(i * 3) < 0.6 ? "#fff6c8" : "#d8ff4a"), x, y - 3 * z, Math.max(3, 5 * z), 0.95);
    } else {
      g.globalAlpha = 1;
      g.fillStyle = ["#e84a3c", "#2f6fb0", "#f2d33a", "#ffffff", "#3aa35b"][Math.floor(rnd(i * 5) * 5)];
      g.fillRect(x - Math.max(1, 1.2 * z), y - Math.max(3, 5 * z), Math.max(2, 2.4 * z), Math.max(3, 5 * z));
    }
  }
  g.globalCompositeOperation = "source-over";
}

function bats(g: CanvasRenderingContext2D, b: Bats, v: FxView) {
  if (v.night < 0.35) return;
  const { z, ox, oy, sec } = v;
  g.globalCompositeOperation = "source-over";
  g.strokeStyle = "#141218";
  g.lineWidth = Math.max(1, 1.2 * z);
  g.globalAlpha = Math.min(1, (v.night - 0.35) * 3) * 0.9;
  for (let i = 0; i < b.n; i++) {
    // each bat on its own looping path round the point, fast and jerky as bats fly
    const w = 0.35 + 0.4 * rnd(i), ph = rnd(i + 50) * 6.28;
    const t = sec * w + ph;
    const x = b.at[0] + Math.sin(t) * b.r * (0.4 + 0.6 * rnd(i + 7)) + Math.sin(t * 3.1) * 18;
    const y = b.at[1] + Math.sin(t * 2) * b.r * 0.35 + Math.cos(t * 4.3) * 10;
    const sx = x * z + ox, sy = y * z + oy;
    if (sx < -20 || sy < -20 || sx > v.W + 20 || sy > v.H + 20) continue;
    const flap = Math.sin(sec * 14 + i) * 0.6, span = Math.max(6, 13 * z);
    g.beginPath();
    g.moveTo(sx - span, sy - span * flap * 0.6);
    g.quadraticCurveTo(sx - span * 0.4, sy + span * 0.15, sx, sy);
    g.quadraticCurveTo(sx + span * 0.4, sy + span * 0.15, sx + span, sy - span * flap * 0.6);
    // a pale moonlit edge under the dark wings, so a bat reads over the dark valley
    g.strokeStyle = "rgba(214,206,240,0.55)";
    g.lineWidth = Math.max(2.6, 3.2 * z);
    g.stroke();
    g.strokeStyle = "#141218";
    g.lineWidth = Math.max(1.4, 1.8 * z);
    g.stroke();
  }
  g.globalAlpha = 1;
}

/** Draws every live effect of one event. */
export function drawEffects(g: CanvasRenderingContext2D, fx: EventEffects, v: FxView): void {
  g.save();
  if (fx.bonfires) for (const b of fx.bonfires) bonfire(g, b, v, fx.dusk ?? [-0.5, 3]);
  if (fx.torches) stream(g, fx.torches, v, "torches");
  if (fx.runners) stream(g, fx.runners, v, "runners");
  if (fx.bats) for (const b of fx.bats) bats(g, b, v);
  if (fx.fireworks && v.night > 0.4) {
    g.globalCompositeOperation = "lighter";
    for (const f of fx.fireworks) fireworks(g, f, v);
  }
  g.restore();
}
