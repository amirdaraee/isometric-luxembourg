/**
 * Car traffic, independent of drawing.
 *
 * After "Pixel Singapore": a road graph from OSM ways, car following with the Intelligent Driver Model, junctions
 * treated as boxes that cars take turns to cross, two-phase traffic lights, deadlocked cars removed after 12 s, and
 * only the streets near the view simulated, with cars appearing and leaving at the margins.
 *
 * Luxembourg drives on the right. Internally everything is in metres; the input lines and every output are in map
 * pixels (0.25 m per pixel unless told otherwise).
 */

// ---------------------------------------------------------------------------------------------------------------
// Public types

/** One projected OSM way, as in lines.json. */
export interface RoadLine { id: number; n?: string; k?: string; o?: boolean; b?: boolean; t?: boolean; l?: string | number | null;
  /** Access flags from OSM (pipeline/project_lines.py): 1 cars, 2 buses, 4 cars to a destination only, 8 emergency
   * vehicles on a call, 16 buses also against the one-way direction. Missing: derived from the kind. */
  a?: number;
  /** Carriageway width in metres, and where the painted road's centre lies across the line (metres to the right of
   * the drawn direction), both measured on the drivable map (pipeline/build_drivable.py). */
  w?: number; c?: number;
  p: number[] }
/** A rectangle in map pixels. */
export interface Rect { x0: number; y0: number; x1: number; y1: number }
export type VehicleType = "car" | "van" | "bus" | "police" | "ambulance" | "fire";
/** A car to draw: centre in map px, heading in screen terms (atan2 of the map px direction, y down). */
export interface DrawableCar {
  id: number; x: number; y: number; headingScreenRad: number; type: VehicleType; variant: number; braking: boolean;
  /** Emergency vehicle on a call: blue lights flashing (always false for other vehicles). */
  siren: boolean;
  /** On a bridge deck / in a tunnel (for the visibility test). */
  bridge: boolean; tunnel: boolean;
  /** Size in map px. */
  length: number; width: number;
}
export interface SignalLight { x: number; y: number; state: "green" | "amber" | "red" }
export interface TrafficOptions {
  /** Only roads inside these rectangles carry traffic (meta.painted). Omit for everywhere. */
  areas?: { x0: number; y0: number; w: number; h: number }[];
  /** Seed for the random choices, so a run can be repeated. */
  seed?: number;
  /** Upper bound on cars alive; densities are scaled down to fit. */
  maxCars?: number;
  /** Metres per map pixel. */
  mpp?: number;
  /** Police cars, ambulances and fire engines (default true). Off: none, and pedestrian streets are left out. */
  emergency?: boolean;
}

// ---------------------------------------------------------------------------------------------------------------
// Tunables

const DRIVE = new Set(["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
  "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "living_street"]);
const MAJOR = new Set(["trunk", "primary", "secondary", "trunk_link", "primary_link", "secondary_link"]);
/** Speed limits, km/h. */
const V0_KMH: Record<string, number> = { motorway: 90, trunk: 70, primary: 50, secondary: 50, tertiary: 40, unclassified: 35,
  residential: 30, living_street: 15, motorway_link: 50, trunk_link: 40, primary_link: 35, secondary_link: 35, tertiary_link: 30 };
/** Cars per km per lane at the busiest hour. */
const DENSITY: Record<string, number> = { motorway: 30, trunk: 25, primary: 15, secondary: 14, tertiary: 12, unclassified: 8,
  residential: 6, living_street: 2, motorway_link: 10, trunk_link: 10, primary_link: 10, secondary_link: 9, tertiary_link: 7 };
const RANK: Record<string, number> = { motorway: 6, trunk: 5, primary: 4, secondary: 3, tertiary: 2, motorway_link: 4,
  trunk_link: 3, primary_link: 3, secondary_link: 2, tertiary_link: 2, living_street: 0 };

// Intelligent Driver Model (metres, seconds).
const IDM_A = 1.7; // maximum acceleration
const IDM_B = 2.2; // comfortable deceleration
const IDM_S0 = 2.2; // minimum gap
const IDM_T = 1.3; // desired time headway
const B_MAX = 7; // hardest braking allowed
const SQRT_AB = 2 * Math.sqrt(IDM_A * IDM_B);
const LAT_ACC = 3; // comfortable sideways acceleration in a turn

const LANE_W = 3.2;
const SNAP_PX = 3; // vertices this close are one node
const CLUSTER_M = 20; // junction nodes within this distance form one box

// Signals: two phases on a 70 s cycle, each 31 s green, 3 s amber, 1 s all red.
const CYCLE = 70, GREEN = 31, AMBER = 3, PHASE = 35;
const DEADLOCK_S = 12; // stuck in or at a box this long: removed
const LONG_WAIT_S = 45; // waiting at a box for a full exit this long (gridlock): removed

// Access flags (RoadLine.a) and who they let through.
const A_CAR = 1, A_BUS = 2, A_DEST = 4, A_EMG = 8, A_BACK = 16;
/** Streets carrying traffic besides DRIVE: pedestrian streets (emergency vehicles on a call, buses where signed),
 * bus-only service roads and busways. */
const EXTRA = new Set(["pedestrian", "service", "busway"]);
V0_KMH.pedestrian = 12; V0_KMH.service = 25; V0_KMH.busway = 40;

// Emergency vehicles: about one in EMG_RATE vehicles, a third of them on a call that lasts CALL_S seconds.
const EMG_RATE = 150, CALL_FRAC = 1 / 3, CALL_S: [number, number] = [60, 120];
const SIREN_VF = 1.3; // on a call: up to this times the limit
// Making way for a siren (Luxembourg's Code de la route asks drivers to form an emergency corridor, "couloir de
// secours", where there are two lanes or more their way, and otherwise to keep right and let it through; see the
// Chamber's answer to parliamentary question 277335, wdocs-pub.chd.lu/docs/exped/0138/133/277335.pdf).
const CORRIDOR_M = 120; // two lanes or more: cars this far ahead move aside (left lane left, the others right)
const CORRIDOR_PULL = 1.2; // ... by up to this much (m)
const CORRIDOR_V = 0.3; // ... and slow to this share of the limit
const PULL_M = 60; // one lane: cars this far ahead pull in to the kerb and stop
const PAST_M = 20; // a car stays aside until the siren is this far past
const ONCOMING_STOP_M = 50; // overtaking on the oncoming lane: oncoming cars this far beyond its passing stretch stop
const RED_CREEP = 4.5; // m/s: a siren crosses a red light no faster than this

// Why a car may not enter a box yet.
const Why = { None: 0, Signal: 1, Occupied: 2, Room: 3, Turn: 4 } as const;
type Why = (typeof Why)[keyof typeof Why];

// ---------------------------------------------------------------------------------------------------------------
// Internal types

interface Edge {
  id: number; kind: string; oneway: boolean; bridge: boolean; tunnel: boolean; perDir: number;
  a: number; b: number; px: Float64Array; py: Float64Array; len: number;
  bx0: number; by0: number; bx1: number; by1: number;
  allowed: boolean; active: boolean; stamp: number; lanes: Lane[];
  /** Access flags (A_*). */
  acc: number;
  /** Carriageway width (m, 0 when unknown) and the painted road's centre, m to the right of the drawn direction. */
  wid: number; shift: number;
  /** Street name ("" when none). */
  name: string;
}
interface Path { x: Float64Array; y: Float64Array; cum: Float64Array; len: number }
interface Lane extends Path {
  kind: 0; id: number; edge: Edge; fwd: boolean; idx: number;
  from: Junction; to: Junction; outs: Conn[]; ins: Conn[];
  v0: number; rank: number; density: number; hStart: number; hEnd: number;
  cars: Car[]; phase: number; entry: boolean; bx0: number; by0: number; bx1: number; by1: number;
  /** Access flags of this lane (a contraflow bus lane: buses and emergency vehicles only). */
  acc: number;
  /** Lane centre, m right of the drawn line in the lane's direction (laneOffset). */
  off: number;
}
interface Conn extends Path {
  kind: 1; id: number; from: Lane; to: Lane; j: Junction; box: boolean; turn: number; vTurn: number; w: number; cars: Car[];
  /** Right of way when taking turns: 2 straight on, 1 turning right, 0 turning left (across oncoming traffic). */
  pri: number;
}
type El = Lane | Conn;
interface Junction {
  /** box: cars take turns to cross; otherwise lanes simply join. sig: signal clock offset in seconds, or -1. */
  id: number; box: boolean; sig: number; ins: Lane[]; outs: Lane[];
  /** Cars holding the box, with the move each holds (reserved ahead, driving it, or clearing it). */
  occCar: Car[]; occConn: Conn[];
}
interface Car {
  id: number; el: El; prev: El | null; s: number; v: number; acc: number; len: number; wid: number;
  type: VehicleType; variant: number; vf: number; route: Conn[];
  /** Box connector reserved ahead (or being driven). */
  res: Conn | null;
  /** Box connector just left, held until the tail is clear of the box. */
  hold: Conn | null; holdS: number;
  /** Stopped at a box it may not enter yet, since when, why, and (if a car in the box) which car. */
  waiting: boolean; waitSince: number; why: Why; blocker: Car | null;
  /** Seconds stuck (deadlock watch) and seconds waiting for room. */
  stall: number; longWait: number; alive: boolean;
  /** Private car to or from a destination-only street: 0 through traffic, 1 leaving one (may use them until it
   * reaches a through street), 2 arriving (parks on parkLane at parkS). */
  dest: number; parkLane: Lane | null; parkS: number;
  /** Emergency vehicle; on a call (siren) until callEnd. */
  emg: boolean; siren: boolean; callEnd: number;
  /** Standing aside for a siren: 0 not, -1 to the left, 1 to the right; asked last until asideTill, rejoins at
   * rejoinAt (0 until set). pullTo: the drawn sideways offset aside (m, right +). asideStop: pulled in and stopping.
   * pass: the street is wide enough for the siren to pass it in the same lane. */
  aside: number; asideTill: number; rejoinAt: number; pullTo: number; asideStop: boolean; pass: boolean;
  /** On a narrow one-way street with a siren behind: keeps going, and turns off at the next junction (until this
   * time). fled: its route has been changed already. */
  flee: number; fled: boolean;
  /** A siren: its drawn sideways offset (along the corridor, or in the oncoming lane), and overtaking on the oncoming
   * lane up to overtakeEnd (m along overtakeLane). */
  sirenPull: number; overtake: boolean; overtakeEnd: number; overtakeLane: Lane | null;
  /** Drawn sideways offset, metres to the right: easing out of a lane change (lat) and pulling over (pull). */
  lat: number; pull: number;
}
const isEmg = (t: VehicleType) => t === "police" || t === "ambulance" || t === "fire";

// ---------------------------------------------------------------------------------------------------------------
// Small helpers

function mulberry32(a: number) {
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
/** Key of a grid cell. */
const ck = (cx: number, cy: number) => (cx + 20000) * 40000 + (cy + 20000);
const wrap = (a: number) => { while (a > Math.PI) a -= 2 * Math.PI; while (a < -Math.PI) a += 2 * Math.PI; return a; };

function cumulative(x: Float64Array, y: Float64Array): Float64Array {
  const c = new Float64Array(x.length);
  for (let i = 1; i < x.length; i++) c[i] = c[i - 1] + Math.hypot(x[i] - x[i - 1], y[i] - y[i - 1]);
  return c;
}

/** Index of the segment holding arc length s (binary search). */
function segAt(cum: Float64Array, s: number): number {
  let lo = 0, hi = cum.length - 2;
  if (hi <= 0) return 0;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (cum[m] <= s) lo = m; else hi = m - 1; }
  return lo;
}

/** Point and heading at arc length s along a path; writes into out. */
function sample(p: Path, s: number, out: { x: number; y: number; h: number }) {
  const n = p.x.length;
  if (n < 2) { out.x = p.x[0]; out.y = p.y[0]; out.h = 0; return; }
  s = Math.min(Math.max(s, 0), p.len);
  const i = segAt(p.cum, s), seg = p.cum[i + 1] - p.cum[i];
  const f = seg > 1e-9 ? (s - p.cum[i]) / seg : 0;
  const dx = p.x[i + 1] - p.x[i], dy = p.y[i + 1] - p.y[i];
  out.x = p.x[i] + dx * f; out.y = p.y[i] + dy * f;
  out.h = Math.atan2(dy, dx);
}

/** Heading over the first / last few metres of a path. */
function headingNear(p: Path, atEnd: boolean): number {
  const o = { x: 0, y: 0, h: 0 }, q = { x: 0, y: 0, h: 0 };
  const d = Math.min(6, p.len);
  if (atEnd) { sample(p, p.len - d, o); sample(p, p.len, q); } else { sample(p, 0, o); sample(p, d, q); }
  if (Math.hypot(q.x - o.x, q.y - o.y) < 1e-6) return o.h;
  return Math.atan2(q.y - o.y, q.x - o.x);
}

/**
 * Lane centre, metres to the right of the drawn line (in the lane's own direction of travel). Without a measured
 * width: two-way lanes 1.6 m apart from the line per lane, one-way lanes centred (nudged right on two-lane
 * carriageways) as before. With the street's width w: two-way lanes spread over their half (one lane each way at
 * w / 4); on a two-way street narrower than 5 m drivers keep to the middle: each way 0.4 m right of it where the
 * street is narrower than 3.6 m, else just far enough over (0.95 m) for two cars to pass without overlapping;
 * no lane centre closer than 1.1 m to the edge; one-way lanes centred, at most w / lanes wide. Then everything moves
 * across to the painted road's centre.
 */
function laneOffset(e: { oneway: boolean; perDir: number; wid: number; shift: number }, idx: number, fwd: boolean,
  contra: boolean, f0: number): number {
  const w = e.wid;
  if (!w) return contra ? LANE_W - f0 : e.oneway ? f0 + idx * LANE_W : (idx + 0.5) * LANE_W;
  const edge = Math.max(0.4, w / 2 - 1.1);
  let off: number;
  if (contra) off = Math.min(LANE_W - f0, edge);
  else if (!e.oneway) off = w < 5 ? (w < 3.6 ? 0.4 : 0.95) : Math.min(Math.max((idx + 0.5) * (w / 2) / e.perDir, 0.4), edge);
  else {
    const lw = Math.min(LANE_W, w / e.perDir), back = f0 - (-(e.perDir - 1) / 2 * LANE_W + (e.perDir > 1 ? 0.8 : 0));
    off = -(e.perDir - 1) / 2 * lw + idx * lw + back;
    off = Math.max(-edge, Math.min(edge, off));
  }
  return off + (fwd ? e.shift : -e.shift);
}

/** Polyline moved sideways by off (positive = right of travel, y down). */
function offsetLine(x: Float64Array, y: Float64Array, off: number): [Float64Array, Float64Array] {
  const n = x.length, ox = new Float64Array(n), oy = new Float64Array(n);
  if (off === 0) { ox.set(x); oy.set(y); return [ox, oy]; }
  const nrm = (i: number): [number, number] => {
    const dx = x[i + 1] - x[i], dy = y[i + 1] - y[i], l = Math.hypot(dx, dy) || 1;
    return [-dy / l, dx / l];
  };
  for (let i = 0; i < n; i++) {
    const a = i > 0 ? nrm(i - 1) : nrm(i), b = i < n - 1 ? nrm(i) : nrm(i - 1);
    let mx = a[0] + b[0], my = a[1] + b[1];
    const ml = Math.hypot(mx, my);
    if (ml < 1e-6) { mx = b[0]; my = b[1]; } else { mx /= ml; my /= ml; }
    const k = off / Math.max(0.5, mx * b[0] + my * b[1]);
    ox[i] = x[i] + mx * k; oy[i] = y[i] + my * k;
  }
  return [ox, oy];
}

/** The part of a polyline between arc lengths a and b. */
function slice(x: Float64Array, y: Float64Array, cum: Float64Array, a: number, b: number): [Float64Array, Float64Array] {
  const xs: number[] = [], ys: number[] = [];
  const o = { x: 0, y: 0, h: 0 };
  const p: Path = { x, y, cum, len: cum[cum.length - 1] };
  sample(p, a, o); xs.push(o.x); ys.push(o.y);
  for (let i = 0; i < x.length; i++) if (cum[i] > a + 1e-6 && cum[i] < b - 1e-6) { xs.push(x[i]); ys.push(y[i]); }
  sample(p, b, o); xs.push(o.x); ys.push(o.y);
  return [Float64Array.from(xs), Float64Array.from(ys)];
}

function segsCross(ax: number, ay: number, bx: number, by: number, cx: number, cy: number, dx: number, dy: number) {
  const d1 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx);
  const d2 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx);
  const d3 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
  const d4 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax);
  return d1 * d2 < 0 && d3 * d4 < 0;
}

// ---------------------------------------------------------------------------------------------------------------

export class Traffic {
  readonly mpp: number;
  readonly maxCars: number;
  /** Counters since construction. */
  readonly stats = { alive: 0, spawned: 0, left: 0, deadlocks: 0, parked: 0, emergency: 0, calls: 0, callsEnded: 0,
    redCrossed: 0, overtakes: 0,
    /** Sirens: seconds and metres driven, summed over every siren and step; cars a siren passed while they stood
     * aside. */
    sirenS: 0, sirenM: 0, passed: 0,
    /** Set by the viewer: cars near the view it is fading out (drawn on water, in a building, ...). Near zero. */
    guarded: 0 };
  private readonly emergencyOn: boolean;
  /** Emergency vehicles alive with the siren on. */
  private sirens: Car[] = [];
  /** Deadlock removals by cause, for tuning. */
  readonly removedWhy: Record<string, number> = {};
  /** Simulated seconds. */
  t = 0;

  private edges: Edge[] = [];
  private lanes: Lane[] = [];
  private junctions: Junction[] = [];
  private grid = new Map<number, Edge[]>();
  private readonly cell = 512; // px
  private activeEdges: Edge[] = [];
  private activeLanes: Lane[] = [];
  private busyConns = new Set<Conn>();
  private region: Rect | null = null;
  private view: Rect = { x0: 0, y0: 0, x1: 0, y1: 0 };
  private rnd: () => number;
  private nextCar = 1;
  private nextConn = 1;
  private conflicts = new Map<number, { k: number; sp: number; sq: number }>();
  private densScale = 1;
  private topUpT = 0;
  private stamp = 0;
  private tmp = { x: 0, y: 0, h: 0 };

  constructor(roads: RoadLine[], opts: TrafficOptions = {}) {
    this.mpp = opts.mpp ?? 0.25;
    this.maxCars = opts.maxCars ?? 1400;
    this.rnd = mulberry32(opts.seed ?? 20240607);
    this.emergencyOn = opts.emergency ?? true;
    this.build(roads, opts.areas);
  }

  /** Number of graph edges and lanes, for checks. */
  get size() { return { edges: this.edges.length, lanes: this.lanes.length, junctions: this.junctions.length,
    boxes: this.junctions.filter((j) => j.box).length, signals: this.junctions.filter((j) => j.sig >= 0).length }; }

  // -------------------------------------------------------------------------------------------------------------
  // Graph

  private build(roads: RoadLine[], areas?: TrafficOptions["areas"]) {
    const M = this.mpp;
    const inArea = (x: number, y: number, pad: number) => !areas || areas.some((a) =>
      x >= a.x0 - pad && x <= a.x0 + a.w + pad && y >= a.y0 - pad && y <= a.y0 + a.h + pad);
    // Who may use a way: its access flags, or for older data everyone on a DRIVE street. Pedestrian streets only
    // with emergency vehicles about; service roads and busways only when they are for buses alone.
    const accOf = (r: RoadLine) => r.a ?? (DRIVE.has(r.k ?? "") ? A_CAR | A_BUS | A_EMG : 0);
    const usable = (r: RoadLine) => {
      const k = r.k ?? "", a = accOf(r);
      if (DRIVE.has(k)) return (a & (A_CAR | A_BUS | A_EMG)) !== 0;
      if (!EXTRA.has(k)) return false;
      if (k === "pedestrian") return (a & A_BUS) !== 0 || (this.emergencyOn && (a & A_EMG) !== 0);
      return (a & A_BUS) !== 0 && !(a & A_CAR);
    };
    const ways = roads.filter((r) => usable(r) && r.p.length >= 4 && (() => {
      for (let i = 0; i < r.p.length; i += 2) if (inArea(r.p[i], r.p[i + 1], 400)) return true;
      return false;
    })());

    // 1. Nodes: snap vertices within SNAP_PX. Interior vertices only join nodes on the same level (ground, bridge,
    // tunnel), so a bridge passing over a street does not connect to it; way ends join anything.
    const nx: number[] = [], ny: number[] = [], nLayer: number[] = [], nEnd: number[] = [], nRefs: number[] = [];
    const cells = new Map<number, number[]>();
    const find = (x: number, y: number, layer: number, isEnd: boolean) => {
      const cx = Math.floor(x / SNAP_PX), cy = Math.floor(y / SNAP_PX);
      let best = -1, bd = SNAP_PX * SNAP_PX + 1e-9;
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
        const list = cells.get(ck(cx + i, cy + j));
        if (!list) continue;
        for (const id of list) {
          const d = (nx[id] - x) ** 2 + (ny[id] - y) ** 2;
          if (d <= bd && (nLayer[id] === layer || nEnd[id] || isEnd)) { bd = d; best = id; }
        }
      }
      if (best < 0) {
        best = nx.length; nx.push(x); ny.push(y); nLayer.push(layer); nEnd.push(0); nRefs.push(0);
        const k = ck(cx, cy);
        (cells.get(k) ?? cells.set(k, []).get(k)!).push(best);
      }
      return best;
    };
    const seqs: number[][] = [];
    for (const w of ways) {
      const layer = w.t ? -1 : w.b ? 1 : 0, n = w.p.length / 2, seq: number[] = [];
      for (let i = 0; i < n; i++) {
        const end = i === 0 || i === n - 1;
        const id = find(w.p[2 * i], w.p[2 * i + 1], layer, end);
        if (end) nEnd[id] = 1;
        if (seq[seq.length - 1] !== id) { seq.push(id); nRefs[id]++; }
      }
      seqs.push(seq);
    }

    // 2. Edges: split every way where it meets another (shared vertices, not only way ends).
    const isGraph = (id: number) => nEnd[id] === 1 || nRefs[id] >= 2;
    const nodeEdges: { e: Edge; atStart: boolean }[][] = nx.map(() => []);
    for (let wi = 0; wi < ways.length; wi++) {
      const w = ways[wi], seq = seqs[wi];
      if (seq.length < 2) continue;
      let oneway = !!w.o;
      // Small closed rings are roundabouts: one way, in the direction drawn.
      if (seq[0] === seq[seq.length - 1] && seq.length > 4) {
        let per = 0, area = 0;
        for (let i = 1; i < seq.length; i++) {
          const a = seq[i - 1], b = seq[i];
          per += Math.hypot(nx[b] - nx[a], ny[b] - ny[a]) * M;
          area += (nx[a] * ny[b] - nx[b] * ny[a]) * M * M / 2;
        }
        if (per < 260 && (4 * Math.PI * Math.abs(area)) / (per * per) > 0.6) oneway = true;
      }
      const kind = w.k ?? "residential";
      const tag = w.l == null ? NaN : parseInt(String(w.l), 10);
      let perDir = 1;
      if (kind === "motorway" || kind === "trunk" || kind === "primary") {
        perDir = Number.isFinite(tag) ? (oneway ? tag : Math.floor(tag / 2)) : kind === "primary" ? 1 : 2;
        perDir = Math.min(2, Math.max(1, perDir));
      }
      let start = 0;
      for (let j = 1; j < seq.length; j++) {
        if (!(isGraph(seq[j]) || j === seq.length - 1)) continue;
        const ids = seq.slice(start, j + 1);
        start = j;
        const px = Float64Array.from(ids.map((i) => nx[i])), py = Float64Array.from(ids.map((i) => ny[i]));
        let len = 0;
        for (let i = 1; i < ids.length; i++) len += Math.hypot(px[i] - px[i - 1], py[i] - py[i - 1]) * M;
        if (len < 0.3) continue;
        let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
        for (let i = 0; i < px.length; i++) {
          bx0 = Math.min(bx0, px[i]); by0 = Math.min(by0, py[i]); bx1 = Math.max(bx1, px[i]); by1 = Math.max(by1, py[i]);
        }
        const mid = Math.floor(px.length / 2);
        const e: Edge = { id: this.edges.length, kind, oneway, bridge: !!w.b, tunnel: !!w.t, perDir,
          a: ids[0], b: ids[ids.length - 1], px, py, len, bx0, by0, bx1, by1,
          allowed: inArea((px[0] + px[px.length - 1] + px[mid]) / 3, (py[0] + py[py.length - 1] + py[mid]) / 3, 0),
          active: false, stamp: 0, lanes: [], acc: accOf(w), wid: w.w ?? 0, shift: w.c ?? 0, name: w.n ?? "" };
        // Pedestrian streets and bus-only roads never take private cars, whatever the tags.
        if (!DRIVE.has(kind)) e.acc &= ~(A_CAR | A_DEST);
        if (!this.emergencyOn && !(e.acc & (A_CAR | A_BUS))) continue;
        this.edges.push(e);
        nodeEdges[e.a].push({ e, atStart: true });
        nodeEdges[e.b].push({ e, atStart: false });
      }
    }

    // 3. Junction boxes: three or more streets, or a change in lane count (a merge). Nearby boxes become one.
    // Lanes against the drawn direction: as many as with it, none on a one-way street, one for a contraflow bus lane.
    const against = (e: Edge) => (!e.oneway ? e.perDir : e.acc & A_BACK ? 1 : 0);
    const half = (e: Edge) => (e.perDir + against(e)) * LANE_W / 2;
    const into = (e: Edge, atStart: boolean) => (atStart ? against(e) : e.perDir);
    const outOf = (e: Edge, atStart: boolean) => (atStart ? e.perDir : against(e));
    const box = new Uint8Array(nx.length), R = new Float64Array(nx.length);
    for (let n = 0; n < nx.length; n++) {
      const list = nodeEdges[n];
      if (list.length >= 3) box[n] = 1;
      else if (list.length === 2) {
        const [p, q] = list;
        if (into(p.e, p.atStart) !== outOf(q.e, q.atStart) || into(q.e, q.atStart) !== outOf(p.e, p.atStart)) box[n] = 1;
      }
      for (const { e } of list) R[n] = Math.max(R[n], half(e) + 1);
    }
    const parent = Int32Array.from({ length: nx.length }, (_, i) => i);
    const root = (i: number): number => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
    const cg = new Map<number, number[]>(), cs = CLUSTER_M / M;
    for (let n = 0; n < nx.length; n++) if (box[n]) {
      const k = ck(Math.floor(nx[n] / cs), Math.floor(ny[n] / cs));
      (cg.get(k) ?? cg.set(k, []).get(k)!).push(n);
    }
    for (let n = 0; n < nx.length; n++) if (box[n]) {
      const cx = Math.floor(nx[n] / cs), cy = Math.floor(ny[n] / cs);
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (const m of cg.get(ck(cx + i, cy + j)) ?? []) {
        if (m <= n || nLayer[m] !== nLayer[n] && !nEnd[m] && !nEnd[n]) continue;
        const d = Math.hypot(nx[m] - nx[n], ny[m] - ny[n]) * M;
        if (d < CLUSTER_M) parent[root(m)] = root(n);
      }
    }
    const nodeJ: (Junction | undefined)[] = new Array(nx.length);
    const mkJ = (isBox: boolean): Junction => {
      const j: Junction = { id: this.junctions.length, box: isBox, sig: -1, ins: [], outs: [], occCar: [], occConn: [] };
      this.junctions.push(j);
      return j;
    };
    for (let n = 0; n < nx.length; n++) {
      if (!nodeEdges[n].length) continue;
      if (box[n]) { const r = root(n); nodeJ[n] = nodeJ[r] ?? (nodeJ[r] = mkJ(true)); } else nodeJ[n] = mkJ(false);
    }

    // 4. Lanes: offset to the right of the centreline, cut back to the edge of each box.
    for (const e of this.edges) {
      const ja = nodeJ[e.a]!, jb = nodeJ[e.b]!;
      if (ja === jb && ja.box && e.a !== e.b && e.len < 30) continue; // inside a merged box
      const x = new Float64Array(e.px.length), y = new Float64Array(e.px.length);
      for (let i = 0; i < x.length; i++) { x[i] = e.px[i] * M; y[i] = e.py[i] * M; }
      const rx = x.slice().reverse(), ry = y.slice().reverse();
      // A one-way street with a contraflow bus lane: the general lanes move half a lane right, the bus lane runs
      // the other way on their left.
      const back = e.oneway && (e.acc & A_BACK) !== 0;
      const f0 = -(e.perDir - 1) / 2 * LANE_W + (e.perDir > 1 ? 0.8 : 0) + (back ? LANE_W / 2 : 0);
      for (const fwd of e.oneway && !back ? [true] : [true, false]) {
        const contra = back && !fwd;
        for (let idx = 0; idx < (contra ? 1 : e.perDir); idx++) {
          // Two-way: lanes to the right of the centreline. One-way: centred on it, nudged right on two-lane
          // carriageways, whose drawn lines tend to sit closer together than the real ones.
          const off = laneOffset(e, idx, fwd, contra, f0);
          const [ox, oy] = offsetLine(fwd ? x : rx, fwd ? y : ry, off);
          const c0 = cumulative(ox, oy), L = c0[c0.length - 1];
          const nFrom = fwd ? e.a : e.b, nTo = fwd ? e.b : e.a;
          const from = nodeJ[nFrom]!, to = nodeJ[nTo]!;
          const t0 = from.box ? Math.min(R[nFrom], L * 0.35) : 0, t1 = to.box ? Math.min(R[nTo], L * 0.35) : 0;
          const [lx, ly] = t0 || t1 ? slice(ox, oy, c0, t0, L - t1) : [ox, oy];
          const cum = cumulative(lx, ly);
          const acc = contra ? A_BUS | A_EMG : e.acc;
          // Cars per km: as for the kind where cars may drive (half on destination-only streets), a bus now and then
          // on bus-only lanes, none where only emergency vehicles go.
          const dens = acc & A_CAR ? (DENSITY[e.kind] ?? 5) * (acc & A_DEST ? 0.5 : 1) : acc & A_BUS ? 1.2 : 0;
          const lane: Lane = { kind: 0, id: this.lanes.length, edge: e, fwd, idx, x: lx, y: ly, cum, len: Math.max(cum[cum.length - 1], 0.05),
            from, to, outs: [], ins: [], v0: (V0_KMH[e.kind] ?? 30) / 3.6, rank: RANK[e.kind] ?? 1, density: dens,
            hStart: 0, hEnd: 0, cars: [], phase: -1, entry: false, bx0: e.bx0, by0: e.by0, bx1: e.bx1, by1: e.by1, acc, off };
          lane.hStart = headingNear(lane, false); lane.hEnd = headingNear(lane, true);
          this.lanes.push(lane); e.lanes.push(lane);
          from.outs.push(lane); to.ins.push(lane);
        }
      }
    }

    // 5. Connectors: every allowed move through a junction, as a short curve from lane end to lane start.
    const uturn = (a: Lane, b: Lane) => a.edge === b.edge && a.fwd !== b.fwd;
    /** Does lane m, followed through plain joins, come back into box j within 30 m? */
    const loopsBack = (m: Lane, j: Junction) => {
      let cur = m, len = m.len;
      for (let k = 0; k < 4 && len < 30; k++) {
        if (cur.to === j) return true;
        if (cur.to.box) return false;
        const nx = cur.to.outs.filter((x) => !uturn(cur, x) && x.idx === cur.idx);
        if (nx.length !== 1) return false;
        cur = nx[0]; len += cur.len;
      }
      return cur.to === j && len < 30;
    };
    for (const j of this.junctions) {
      for (const L of j.ins) {
        let cand: Lane[];
        if (!j.box) cand = j.outs.filter((m) => !uturn(L, m) && m.idx === L.idx);
        else {
          cand = j.outs.filter((m) => !uturn(L, m) && Math.abs(wrap(m.hStart - L.hEnd)) < 2.6 &&
            (m.edge.perDir !== L.edge.perDir || m.idx === L.idx));
          // Not onto a stub that only leads back into the same box (slivers between merged junction nodes): cars
          // going round such a loop lock it.
          const keep = cand.filter((m) => !loopsBack(m, j));
          if (keep.length) cand = keep;
        }
        // Turning back only where there is no other way on, for each kind of vehicle the lane carries.
        for (const cls of [A_CAR, A_BUS, A_EMG]) {
          if (!(L.acc & cls) || cand.some((m) => m.acc & cls)) continue;
          for (const m of j.outs) if (uturn(L, m) && (m.idx === L.idx || m.edge.perDir === 1) && !cand.includes(m)) cand.push(m);
        }
        for (const m of cand) this.connect(L, m, j);
        // Most cars go straight on: the exit with the smallest change of heading is favoured.
        if (L.outs.length) {
          let best = Infinity;
          for (const c of L.outs) best = Math.min(best, c.turn);
          const per = new Map<Edge, number>();
          for (const c of L.outs) per.set(c.to.edge, (per.get(c.to.edge) ?? 0) + 1);
          for (const c of L.outs) {
            const straight = c.turn === best && best < 0.6 ? 7 : 1;
            c.w = straight * (MAJOR.has(c.to.edge.kind) ? 1.5 : 1) * (c.to.edge.kind === "living_street" ? 0.4 : 1) / per.get(c.to.edge)!;
          }
        }
      }
    }

    // 6. Traffic lights where two major streets cross or meet: three or more streets of tertiary or above, two of
    // them major, and a street of tertiary or above on each of the two phases (a side street off a boulevard takes
    // turns instead). The phase of an approach is its direction: along the most important street, or across it.
    for (const j of this.junctions) {
      if (!j.box || !j.ins.length) continue;
      const streets = new Set<Edge>();
      for (const l of j.ins) streets.add(l.edge);
      for (const l of j.outs) streets.add(l.edge);
      let major = 0, big = 0;
      for (const e of streets) { if (MAJOR.has(e.kind)) major++; if ((RANK[e.kind] ?? 1) >= 2) big++; }
      if (big < 3 || major < 2) continue;
      let axis = j.ins[0];
      for (const l of j.ins) if (l.rank > axis.rank || (l.rank === axis.rank && l.edge.len > axis.edge.len)) axis = l;
      const phase = j.ins.map((l) => {
        const d = Math.abs(wrap(l.hEnd - axis.hEnd));
        return Math.min(d, Math.PI - d) < Math.PI / 4 ? 0 : 1;
      });
      if (!j.ins.some((l, i) => phase[i] === 1 && l.rank >= 2)) continue;
      j.ins.forEach((l, i) => { l.phase = phase[i]; });
      // All lights on one clock (a few seconds apart), so a boulevard tends to show green together.
      j.sig = (j.id * 1.37) % 4;
    }

    // 7. Spatial buckets of the edges that may carry traffic.
    for (const e of this.edges) {
      if (!e.allowed || !e.lanes.length) continue;
      for (let cx = Math.floor(e.bx0 / this.cell); cx <= Math.floor(e.bx1 / this.cell); cx++)
        for (let cy = Math.floor(e.by0 / this.cell); cy <= Math.floor(e.by1 / this.cell); cy++) {
          const k = ck(cx, cy);
          (this.grid.get(k) ?? this.grid.set(k, []).get(k)!).push(e);
        }
    }
  }

  private connect(a: Lane, b: Lane, j: Junction) {
    // Cubic curve from a's end to b's start, tangent to both.
    const x0 = a.x[a.x.length - 1], y0 = a.y[a.y.length - 1], x3 = b.x[0], y3 = b.y[0];
    const signed = wrap(b.hStart - a.hEnd), turn = Math.abs(signed);
    const D = Math.hypot(x3 - x0, y3 - y0);
    const k = Math.max(D * 0.4, turn > 2.5 ? 4 : 0.05);
    const x1 = x0 + Math.cos(a.hEnd) * k, y1 = y0 + Math.sin(a.hEnd) * k;
    const x2 = x3 - Math.cos(b.hStart) * k, y2 = y3 - Math.sin(b.hStart) * k;
    const N = D < 1 && turn < 0.3 ? 1 : 10;
    const x = new Float64Array(N + 1), y = new Float64Array(N + 1);
    for (let i = 0; i <= N; i++) {
      const t = i / N, u = 1 - t;
      x[i] = u * u * u * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t * t * t * x3;
      y[i] = u * u * u * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y3;
    }
    const cum = cumulative(x, y), len = Math.max(cum[N], 0.05);
    const radius = turn > 0.2 ? Math.max(len, 1) / turn : Infinity;
    const c: Conn = { kind: 1, id: this.nextConn++, from: a, to: b, j, box: j.box, x, y, cum, len, turn,
      vTurn: Math.max(3, Math.sqrt(LAT_ACC * radius)), w: 1, cars: [],
      pri: turn < 0.5 ? 2 : signed > 0 ? 1 : 0 }; // y is down: a positive turn is to the right
    a.outs.push(c); b.ins.push(c);
  }

  /**
   * How two box moves interact: 0 not at all, 1 they cross or pass too close, 2 they only merge into the same exit
   * (the second may follow the first in). Moves from the same lane start together (cars there simply follow each
   * other) and only conflict if they come together again later. For crossings, also where along a the last point of
   * conflict is (this.conflictS), so a car may go once the one in its way has passed it.
   */
  private conflictKind(a: Conn, b: Conn): number {
    if (a === b) return 0;
    const lo = a.id < b.id, key = lo ? a.id * 1e6 + b.id : b.id * 1e6 + a.id;
    let hit = this.conflicts.get(key);
    if (!hit) {
      const p = lo ? a : b, q = lo ? b : a;
      const skip = p.from === q.from ? 4 : 0, cut = p.to === q.to ? 4 : 0;
      let k = 0, sp = 0, sq = 0;
      for (let i = skip; i < p.x.length - cut; i++) for (let m = skip; m < q.x.length - cut; m++) {
        const close = (p.x[i] - q.x[m]) ** 2 + (p.y[i] - q.y[m]) ** 2 < 1.9 * 1.9 ||
          (i > skip && m > skip && segsCross(p.x[i - 1], p.y[i - 1], p.x[i], p.y[i], q.x[m - 1], q.y[m - 1], q.x[m], q.y[m]));
        if (close) { k = 1; sp = Math.max(sp, p.cum[i]); sq = Math.max(sq, q.cum[m]); }
      }
      if (!k && p.to === q.to) k = 2;
      hit = { k, sp, sq };
      this.conflicts.set(key, hit);
    }
    this.conflictS = lo ? hit.sp : hit.sq;
    return hit.k;
  }
  /** Set by conflictKind: the last point of conflict along its first argument. */
  private conflictS = 0;

  /** Has car o (taking or past box move oc) cleared the point s along it, tail and all? */
  private cleared(o: Car, oc: Conn, s: number): boolean {
    const tail = o.el === oc ? o.s - o.len : o.el === oc.from ? -Infinity : oc.len + o.s - o.len;
    return tail > s + 1;
  }

  /** Distance from car o's front to the end of box move oc it holds or is about to take. */
  private toExit(o: Car, oc: Conn): number {
    if (o.el === oc) return oc.len - o.s;
    if (o.el === oc.from) return oc.from.len - o.s + oc.len;
    return -o.s; // already out on the exit
  }

  /**
   * Cars merging into the same exit from other moves of box j, ahead of a car whose front is mine metres from the
   * exit: the closest one as [gap, its speed].
   */
  private mergeLeader(c: Car, cn: Conn, mine: number): [number, number] {
    const j = cn.j;
    let gap = Infinity, lv = 0;
    for (let i = 0; i < j.occCar.length; i++) {
      const o = j.occCar[i], oc = j.occConn[i];
      if (o === c || oc === cn || oc.to !== cn.to || o.el !== oc) continue;
      const theirs = this.toExit(o, oc);
      if (theirs < mine) { const g = mine - theirs - o.len; if (g < gap) { gap = g; lv = o.v; } }
    }
    return [gap, lv];
  }

  // -------------------------------------------------------------------------------------------------------------
  // Signals

  /** 0 green, 1 amber, 2 red for a phase at a junction. */
  private light(j: Junction, phase: number): number {
    const ph = (this.t + j.sig + phase * PHASE) % CYCLE;
    return ph < GREEN ? 0 : ph < GREEN + AMBER ? 1 : 2;
  }

  /** Signal heads at the stop lines of signalised approaches near the view (map px). */
  *signals(): IterableIterator<SignalLight> {
    const o = this.tmp;
    for (const l of this.activeLanes) {
      if (l.phase < 0 || l.idx !== l.edge.perDir - 1) continue;
      sample(l, l.len, o);
      const st = this.light(l.to, l.phase);
      const x = (o.x - Math.sin(o.h) * 2.2) / this.mpp, y = (o.y + Math.cos(o.h) * 2.2) / this.mpp;
      if (x < this.view.x0 || x > this.view.x1 || y < this.view.y0 || y > this.view.y1) continue;
      yield { x, y, state: st === 0 ? "green" : st === 1 ? "amber" : "red" };
    }
  }

  // -------------------------------------------------------------------------------------------------------------
  // Region near the view

  private updateRegion(view: Rect) {
    const w = view.x1 - view.x0, h = view.y1 - view.y0, m = Math.max(0.35 * Math.max(w, h), 300);
    const want: Rect = { x0: view.x0 - m, y0: view.y0 - m, x1: view.x1 + m, y1: view.y1 + m };
    const r = this.region;
    const inner = { x0: view.x0 - m / 2, y0: view.y0 - m / 2, x1: view.x1 + m / 2, y1: view.y1 + m / 2 };
    const area = (q: Rect) => (q.x1 - q.x0) * (q.y1 - q.y0);
    if (r && inner.x0 >= r.x0 && inner.y0 >= r.y0 && inner.x1 <= r.x1 && inner.y1 <= r.y1 && area(r) < 3 * area(want)) return;
    this.region = want;
    const s = ++this.stamp, now: Edge[] = [];
    for (let cx = Math.floor(want.x0 / this.cell); cx <= Math.floor(want.x1 / this.cell); cx++)
      for (let cy = Math.floor(want.y0 / this.cell); cy <= Math.floor(want.y1 / this.cell); cy++)
        for (const e of this.grid.get(ck(cx, cy)) ?? []) {
          if (e.stamp === s || e.bx1 < want.x0 || e.bx0 > want.x1 || e.by1 < want.y0 || e.by0 > want.y1) continue;
          e.stamp = s; now.push(e);
        }
    for (const e of this.activeEdges) if (e.stamp !== s) {
      e.active = false;
      for (const l of e.lanes) while (l.cars.length) this.remove(l.cars[l.cars.length - 1], false);
    }
    const fresh: Lane[] = [];
    for (const e of now) if (!e.active) { e.active = true; fresh.push(...e.lanes); }
    this.activeEdges = now;
    this.activeLanes = now.flatMap((e) => e.lanes);
    let target = 0;
    for (const l of this.activeLanes) {
      l.entry = !l.ins.some((c) => c.from.edge.active);
      target += (l.density * l.len) / 1000;
    }
    this.densScale = Math.min(1, (this.maxCars * 0.9) / Math.max(target, 1));
    this.target = target * this.densScale;
    this.freshLanes.push(...fresh);
  }
  private freshLanes: Lane[] = [];
  /** Cars wanted near the view at the busiest hour. */
  private target = 0;

  // -------------------------------------------------------------------------------------------------------------
  // Cars

  /** A new vehicle on lane, of a kind the lane may carry. force: make it this emergency vehicle. */
  private makeCar(lane: Lane, s: number, v: number, force?: { type: VehicleType; siren: boolean }): Car {
    const r = this.rnd(), a = lane.acc;
    let type: VehicleType;
    if (force) type = force.type;
    else if (this.emergencyOn && a & (A_CAR | A_BUS) && r < 1 / EMG_RATE) {
      const q = this.rnd();
      type = q < 0.45 ? "police" : q < 0.8 ? "ambulance" : "fire";
    } else if (!(a & A_CAR)) type = "bus";
    else type = a & A_BUS && lane.rank >= 3 && r < 0.05 ? "bus" : r < 0.17 ? "van" : "car";
    const SIZE: Record<VehicleType, [number, number]> = { car: [4.4, 1.8], van: [5.4, 2], bus: [12, 2.55],
      police: [4.5, 1.85], ambulance: [5.8, 2.1], fire: [9, 2.5] };
    const [len, wid] = SIZE[type], emg = isEmg(type);
    const c: Car = { id: this.nextCar++, el: lane, prev: null, s, v, acc: 0, len, wid,
      type, variant: Math.floor(this.rnd() * 16), vf: type === "bus" || type === "fire" ? 0.85 : emg ? 0.95 : 0.85 + this.rnd() * 0.25,
      route: [], res: null, hold: null, holdS: 0, waiting: false, waitSince: 0, why: Why.None, blocker: null, stall: 0, longWait: 0,
      alive: true, dest: type !== "bus" && !emg && a & A_DEST ? 1 : 0, parkLane: null, parkS: 0,
      emg, siren: false, callEnd: 0, aside: 0, asideTill: 0, rejoinAt: 0, pullTo: 0, asideStop: false, pass: false,
      flee: 0, fled: false, sirenPull: 0, overtake: false, overtakeEnd: 0, overtakeLane: null, lat: 0, pull: 0 };
    if (emg) {
      this.stats.emergency++;
      if (force ? force.siren : this.rnd() < CALL_FRAC) this.startCall(c);
    }
    this.plan(c);
    this.stats.alive++; this.stats.spawned++;
    return c;
  }

  private startCall(c: Car) {
    c.siren = true; c.vf = SIREN_VF;
    c.callEnd = this.t + CALL_S[0] + this.rnd() * (CALL_S[1] - CALL_S[0]);
    this.sirens.push(c);
    this.stats.calls++;
  }

  private endCall(c: Car) {
    c.siren = false; c.vf = c.type === "fire" ? 0.85 : 0.95;
    const i = this.sirens.indexOf(c);
    if (i >= 0) this.sirens.splice(i, 1);
  }

  /**
   * How much car c (in destination state dest) would like to drive onto lane m: 0 when it may not. Private cars keep
   * to car lanes and use destination-only streets just to arrive or leave; buses keep to bus lanes; emergency vehicles
   * may also use bus lanes, and on a call pedestrian streets (rarely, and slowly).
   */
  private allowance(c: Car, m: Lane, from: Lane, dest: number): number {
    const a = m.acc;
    if (c.emg) {
      if (a & (A_CAR | A_BUS)) return 1;
      if (a & A_EMG && (c.siren || !(from.acc & (A_CAR | A_BUS)))) return 0.15;
      return 0;
    }
    if (c.type === "bus") return a & A_BUS ? 1 : 0;
    if (!(a & A_CAR)) return 0;
    if (a & A_DEST && dest !== 1) return 0.3; // arriving: it parks there
    return 1;
  }

  /** Choose the next few moves ahead, among those the vehicle may take. */
  private plan(c: Car) {
    if (c.dest === 2 || c.parkLane) return; // arriving: no further
    let L: Lane = c.route.length ? c.route[c.route.length - 1].to : c.el.kind === 0 ? c.el : c.el.to;
    let dest = c.dest;
    for (const cn of c.route) if (!(cn.to.acc & A_DEST)) dest = 0;
    const w: number[] = [];
    while (c.route.length < 3 && L.edge.active && L.outs.length) {
      let sum = 0;
      w.length = 0;
      for (const o of L.outs) { const x = o.w * this.allowance(c, o.to, L, dest); w.push(x); sum += x; }
      if (sum <= 0) break; // no way on for this vehicle: it leaves the streets at the end of the lane
      let t = this.rnd() * sum, pick = L.outs[0];
      for (let i = 0; i < L.outs.length; i++) { if (!w[i]) continue; pick = L.outs[i]; t -= w[i]; if (t <= 0) break; }
      c.route.push(pick);
      L = pick.to;
      if (c.type === "car" || c.type === "van") {
        if (!(L.acc & A_DEST)) dest = 0;
        else if (dest !== 1) { c.parkLane = L; break; } // arrives here: no further
      }
    }
  }

  private release(c: Car, cn: Conn) {
    const j = cn.j;
    for (let i = 0; i < j.occCar.length; i++) if (j.occCar[i] === c && j.occConn[i] === cn) {
      j.occCar.splice(i, 1); j.occConn.splice(i, 1); return;
    }
  }

  private reserve(c: Car, cn: Conn) {
    c.res = cn; c.waiting = false; c.why = Why.None; c.stall = 0; c.longWait = 0;
    if (c.siren && cn.j.sig >= 0 && cn.from.phase >= 0 && this.light(cn.j, cn.from.phase) !== 0) this.stats.redCrossed++;
    cn.j.occCar.push(c); cn.j.occConn.push(cn);
  }

  /**
   * Follows who a stopped car is waiting for (the head of the queue on its exit, the car in the box). If that leads
   * back to the car's own lane it is a gridlock: returns the newest car on the ring. A red light ends the search.
   */
  private gridlock(c: Car): Car | null {
    let x = c, newest = c;
    for (let step = 0; step < 40; step++) {
      let y: Car | undefined | null;
      const el = x.el;
      if (el.cars[0] !== x) y = el.cars[0];
      else if (el.kind === 1) y = el.to.cars[0];
      else if (x.waiting) {
        if (x.why === Why.Room) y = x.route[0]?.to.cars[0];
        else if (x.why === Why.Occupied) y = x.blocker;
        else return null;
      } else y = x.route[0]?.cars[0] ?? x.route[0]?.to.cars[0];
      if (!y || !y.alive || y.v > 0.3) return null;
      if (y === c || y.el === c.el) return newest;
      if (y.id > newest.id) newest = y;
      x = y;
    }
    return null;
  }

  private remove(c: Car, deadlock: boolean) {
    if (!c.alive) return;
    c.alive = false;
    const arr = c.el.cars, i = arr.indexOf(c);
    if (i >= 0) arr.splice(i, 1);
    if (c.el.kind === 1 && !arr.length) this.busyConns.delete(c.el);
    if (c.res) this.release(c, c.res);
    if (c.hold) this.release(c, c.hold);
    if (c.siren) this.endCall(c);
    this.stats.alive--;
    if (deadlock) this.stats.deadlocks++; else this.stats.left++;
  }

  /** May car c (front at dist from the stop line) enter box move cn now? Sets c.why when not. */
  private mayEnter(c: Car, cn: Conn, dist: number): boolean {
    const j = cn.j;
    // On a call: through red lights, but only into an empty path (the checks on cars in the box below still apply).
    // So does a car with a siren behind it on a narrow one-way street, to clear the way.
    if (j.sig >= 0 && cn.from.phase >= 0 && !c.siren && !(c.flee > this.t)) {
      const st = this.light(j, cn.from.phase);
      if (st === 2 || (st === 1 && dist > (c.v * c.v) / (2 * IDM_B) + 1)) { c.why = Why.Signal; return false; }
    }
    for (let i = 0; i < j.occCar.length; i++) {
      if (j.occCar[i] === c) continue;
      const oc = j.occConn[i];
      if (oc === cn) continue;
      const kind = this.conflictKind(oc, cn), o = j.occCar[i];
      if ((kind === 1 && !this.cleared(o, oc, this.conflictS)) || (kind === 2 && this.toExit(o, oc) + o.len + IDM_S0 > dist + cn.len)) {
        c.why = Why.Occupied; c.blocker = j.occCar[i]; return false;
      }
    }
    // Room on the far side.
    const to = cn.to, r = c.siren ? this.rearmost(c, to.cars) : to.cars[to.cars.length - 1];
    let free = r ? r.s - r.len : to.len + 30;
    if (!r) {
      // An empty short exit: look one move further.
      const nx = to.outs.length === 1 ? to.outs[0] : undefined;
      if (nx && !nx.box && nx.to.cars.length) free = to.len + nx.len + nx.to.cars[nx.to.cars.length - 1].s - nx.to.cars[nx.to.cars.length - 1].len;
    }
    for (let i = 0; i < j.occCar.length; i++) if (j.occConn[i] === cn && j.occCar[i] !== c) free -= j.occCar[i].len + IDM_S0;
    if (free < c.len + 1 && !(r && r.v > 3 && free > 0)) { c.why = Why.Room; return false; }
    if (c.siren) return true; // others wait for it
    // A siren coming up to this box on another approach goes first.
    for (const e of this.sirens) {
      const el = e.el;
      if (el.kind !== 0 || el.to !== j || el === cn.from || el.cars[0] !== e || el.len - e.s > 50 || !e.route.length) continue;
      if (this.conflictKind(e.route[0], cn)) { c.why = Why.Turn; return false; }
    }
    // Take turns: a car already waiting at a crossing move goes first.
    const mine = c.waiting ? c.waitSince : this.t;
    for (const L of j.ins) {
      if (L === cn.from) continue;
      const w = L.cars[0];
      if (!w || !w.waiting || w.why === Why.Signal || w.why === Why.Room || !w.route.length || w.waitSince >= mine) continue;
      if (w.el !== L) continue;
      // The bigger road, and straight-on traffic over turning traffic, keep going a while before giving way.
      const wait = this.t - w.waitSince;
      if (L.rank < cn.from.rank && wait < 4) continue;
      if (w.route[0].pri < cn.pri && wait < 8) continue;
      if (this.conflictKind(w.route[0], cn)) { c.why = Why.Turn; return false; }
    }
    return true;
  }

  /**
   * IDM for one car: finds the obstacle ahead (car, or stop line of a box it may not enter yet) and the speed it
   * should slow to for the next turn. Returns the acceleration.
   */
  private accel(c: Car, i: number): number {
    const el = c.el, arr = el.cars;
    const limit = el.kind === 0 ? el.v0 : Math.min(el.from.v0, el.to.v0);
    // On a pedestrian street (no cars or buses) a siren goes no faster than walking-pace traffic.
    const lane = el.kind === 0 ? el : el.to;
    let v0 = (lane.acc & (A_CAR | A_BUS) ? c.vf : Math.min(c.vf, 1)) * limit;
    if (el.kind === 1) v0 = Math.min(v0, el.vTurn);
    // Standing aside in an emergency corridor: slow right down.
    if (c.aside && !c.asideStop) v0 = Math.min(v0, limit * CORRIDOR_V);
    let gap = Infinity, lv = 0;
    if (el.kind === 1 && el.box) [gap, lv] = this.mergeLeader(c, el, el.len - c.s);
    // Arriving at a destination-only street: pull in and stop at the parking spot.
    if (c.dest === 2 && el === c.parkLane) gap = Math.min(gap, c.parkS - c.s + IDM_S0);
    // The car ahead, passing over any a siren may share the lane with (see ghost).
    let li = i - 1;
    while (li >= 0 && this.ghost(c, arr[li])) li--;
    if (li >= 0) { const l = arr[li], g = l.s - l.len - c.s; if (g < gap) { gap = g; lv = l.v; } }
    else {
      let dist = el.len - c.s, cur: El = el, ri = 0;
      const H = 30 + c.v * 5;
      let atLine = false;
      while (dist < H) {
        let nx: El;
        if (cur.kind === 0) {
          const cn = c.route[ri];
          if (!cn || !cn.to.edge.active) break; // leaves the simulated streets here
          v0 = Math.min(v0, Math.sqrt(cn.vTurn * cn.vTurn * c.vf * c.vf + 2 * 1.6 * Math.max(dist, 0)));
          // A siren slows to a crawl before crossing against the light.
          if (c.siren && cn.box && cn.j.sig >= 0 && cn.from.phase >= 0 && this.light(cn.j, cn.from.phase) !== 0)
            v0 = Math.min(v0, Math.sqrt(RED_CREEP * RED_CREEP + 2 * 1.6 * Math.max(dist, 0)));
          if (cn.box && c.res !== cn) {
            // Only the box at the end of the car's own lane is reserved; boxes further on are checked again later.
            const first = el.kind === 0 && ri === 0;
            if (!this.mayEnter(c, cn, dist)) {
              gap = dist + IDM_S0 - 0.8; lv = 0; atLine = first;
              break;
            }
            if (first && dist <= (c.v * c.v) / 7 + 2) this.reserve(c, cn);
          }
          // A car that has just turned off from this lane onto another move is still in the way at the fork.
          let sib: Car | null = null;
          for (const o of cur.outs) {
            if (o === cn || !o.cars.length) continue;
            const r = o.cars[o.cars.length - 1];
            if (r !== c && r.s - r.len < 6 && (!sib || r.s - r.len < sib.s - sib.len)) sib = r;
          }
          if (sib) { const g = dist + sib.s - sib.len; if (g < gap) { gap = g; lv = sib.v; } }
          if (cn.box) { const [g, w] = this.mergeLeader(c, cn, dist + cn.len); if (g < gap) { gap = g; lv = w; } }
          nx = cn; ri++;
        } else nx = cur.to;
        const r = this.rearmost(c, nx.cars);
        if (r && r !== c) { const g = dist + r.s - r.len; if (g < gap) { gap = g; lv = r.v; } break; }
        if (gap < Infinity) break;
        dist += nx.len; cur = nx;
      }
      if (atLine) { if (!c.waiting && c.v < 1 && el.len - c.s < 8) { c.waiting = true; c.waitSince = this.t; } }
      else if (c.waiting && !c.res) { c.waiting = false; }
    }
    const v = c.v;
    let a = IDM_A * (1 - (v / Math.max(v0, 0.5)) ** 4);
    if (gap < Infinity) {
      const ss = IDM_S0 + Math.max(0, v * IDM_T + (v * (v - lv)) / SQRT_AB);
      a -= IDM_A * (ss / Math.max(gap, 0.1)) ** 2;
    }
    // Pulled in for a siren: stop over about two seconds.
    if (c.aside && c.asideStop) a = Math.min(a, v > 0.05 ? -Math.max(1.2, v / 1.5) : 0);
    return Math.max(a, -B_MAX);
  }

  /** Move car c from the front of its element to the next. False if it has to stay. */
  private advance(c: Car): boolean {
    const el = c.el;
    let next: El;
    if (el.kind === 0) {
      const cn = c.route[0];
      if (!cn || !cn.to.edge.active) { this.remove(c, false); return true; }
      if (cn.box && c.res !== cn) {
        if (this.mayEnter(c, cn, 0)) this.reserve(c, cn);
        else { c.s = el.len; c.v = 0; return false; }
      }
      next = cn;
    } else {
      next = el.to;
      if (!next.edge.active) { this.remove(c, false); return true; }
    }
    const r = this.rearmost(c, next.cars), over = c.s - el.len;
    if (r && r.s - r.len < over + 0.3) { c.s = el.len; c.v = Math.min(c.v, r.v); return false; }
    el.cars.shift();
    c.prev = el; c.el = next; c.s = over;
    next.cars.push(c);
    if (el.kind === 0) { c.route.shift(); this.plan(c); this.busyConns.add(next as Conn); }
    else {
      const L = next as Lane;
      if (c.parkLane === L) { c.dest = 2; c.parkS = Math.min(L.len - 1, Math.max(over + c.len, L.len * (0.3 + 0.5 * this.rnd()))); }
      else if (c.dest === 1 && !(L.acc & A_DEST)) c.dest = 0;
      if (!el.cars.length) this.busyConns.delete(el);
      if (el.box && c.res === el) {
        if (c.hold) this.release(c, c.hold);
        c.hold = el; c.holdS = 0; c.res = null;
      }
    }
    return true;
  }

  private trySpawn(l: Lane, rate: number, dt: number) {
    if (this.stats.alive >= this.maxCars || this.rnd() > rate * dt) return;
    const r = l.cars[l.cars.length - 1], free = r ? r.s - r.len : l.len;
    if (l.len < 14 || free < 12 + IDM_S0 + 2) return; // room even for a bus
    const c = this.makeCar(l, 0, 0);
    c.s = c.len + 0.5;
    c.v = Math.min(l.v0 * c.vf * 0.8, r ? r.v + 1 : 99);
    l.cars.push(c);
  }

  /** Put a car in the largest gap of a lane (never in front of its first car). */
  private insertInGap(l: Lane, vfrac: number): boolean {
    const n = l.cars.length;
    let best = -1, bestGap = 0, bestFront = 0;
    for (let i = 1; i <= n; i++) {
      const lead = l.cars[i - 1], back = i < n ? l.cars[i].s : 0;
      const g = lead.s - lead.len - back;
      if (g > bestGap) { bestGap = g; best = i; bestFront = back; }
    }
    if (!n) { best = 0; bestGap = l.len * 0.7; bestFront = l.len * 0.15; }
    const need = 2 * (IDM_S0 + 12) + 6;
    if (best < 0 || bestGap < need) return false;
    const c = this.makeCar(l, 0, 0);
    c.s = bestFront + (bestGap + c.len) / 2;
    const lead = best > 0 ? l.cars[best - 1] : null;
    c.v = Math.min(l.v0 * c.vf * vfrac, lead ? lead.v + 2 : 99);
    l.cars.splice(best, 0, c);
    return true;
  }

  // -------------------------------------------------------------------------------------------------------------
  // Emergency vehicles

  /**
   * May c and o share a lane, side by side? A siren and a car that stands aside on a street wide enough for both, or
   * a siren overtaking on the oncoming lane and the cars it is passing.
   */
  private ghost(c: Car, o: Car): boolean {
    if (c.siren) return (o.aside !== 0 && o.pass) || (c.overtake && o.s - o.len < c.overtakeEnd);
    if (o.siren) return (c.aside !== 0 && c.pass) || (o.overtake && c.s - c.len < o.overtakeEnd);
    return false;
  }

  /** The rearmost car of a lane that c may not share it with (null if none). */
  private rearmost(c: Car, cars: Car[]): Car | null {
    for (let k = cars.length - 1; k >= 0; k--) if (!this.ghost(c, cars[k])) return cars[k];
    return null;
  }

  /** Sideways room (m) a car on lane m has to move over, to the right kerb (side 1) or to the left (side -1): to the
   * centre line of a two-way street, to the far kerb of a one-way one. */
  private room(c: Car, m: Lane, side: number): number {
    const e = m.edge, w = e.wid;
    if (!w) return 0.9;
    const off = m.off - (m.fwd ? e.shift : -e.shift);   // lane centre from the carriageway's middle, right of travel
    const r = side > 0 ? w / 2 - off - c.wid / 2 - 0.3 : off - (e.oneway ? -w / 2 : 0) - c.wid / 2 - 0.3;
    return Math.max(0, r);
  }

  /** Car o makes way for a siren: aside to `side`, drawn `pullTo` m over, stopping or not, passable or not. */
  private setAside(o: Car, side: number, pullTo: number, stop: boolean, pass: boolean) {
    if (o.emg) return;
    o.aside = side; o.pullTo = pullTo; o.asideStop = stop; o.pass = pass;
    o.asideTill = this.t + 1.5; o.rejoinAt = 0;
  }

  /** Cars on lane m near a siren whose front is at sBase on m (m along m; negative: before its start). */
  private *near(e: Car, m: Lane, sBase: number, range: number): IterableIterator<Car> {
    for (const o of m.cars) {
      if (o === e) continue;
      if (o.s - o.len - sBase < range && o.s > sBase - e.len - PAST_M) yield o;
    }
  }

  /**
   * Calls ending, and the cars near a siren making way for it:
   *  - two lanes or more its way: an emergency corridor; the cars within CORRIDOR_M ahead move aside (the left lane
   *    to the left, the others to the right) and slow down, and the siren drives along the lane boundary through them;
   *  - one lane: cars within PULL_M ahead pull in to the kerb and stop; where the street is wide enough for both the
   *    siren passes them, else it overtakes on the oncoming lane when that is clear and oncoming cars stop;
   *  - a narrow one-way street: cars ahead keep going and turn off at the next junction, away from the siren's route;
   *  - cars queued at a red light stay put.
   * Cars rejoin once the siren is PAST_M past (see step). On two lanes a siren may still change to a free lane.
   */
  private emergencyStep() {
    const t = this.t;
    for (let k = this.sirens.length - 1; k >= 0; k--) {
      const e = this.sirens[k];
      if (t > e.callEnd) {
        this.endCall(e); this.stats.callsEnded++;
        e.overtake = false; e.sirenPull = 0;
        continue;
      }
      const cur = e.el;
      // Past a car it may share the lane (or move through a box) with: now in front of it.
      let i = cur.cars.indexOf(e);
      while (i > 0 && cur.cars[i - 1].s < e.s && this.ghost(e, cur.cars[i - 1])) {
        const o = cur.cars[i - 1];
        cur.cars[i - 1] = e; cur.cars[i] = o; i--;
        this.stats.passed++;
      }
      if (cur.kind !== 0) {
        // Crossing a box: keeps what it had, and the cars it shares the move with stay aside.
        for (const o of cur.cars) if (o.aside) o.asideTill = t + 1.5;
        continue;
      }
      const el = cur;
      if (e.overtake && e.overtakeLane !== el) e.overtake = false;
      const edge = el.edge, nx = e.route[0]?.to;
      const rest = el.len - e.s;
      e.sirenPull = 0;
      if (edge.perDir >= 2) {
        let any = false;
        const lanes = (L: Lane, sBase: number, range: number) => {
          for (const m of L.edge.lanes) {
            if (m.fwd !== L.fwd || !(m.acc & (A_CAR | A_BUS))) continue;
            const sb = (sBase * m.len) / L.len;
            for (const o of this.near(e, m, sb, range)) {
              if (o.waiting && o.why === Why.Signal && L !== el) continue;
              const side = m.idx === 0 ? -1 : 1;
              this.setAside(o, side, side * Math.min(CORRIDOR_PULL, this.room(o, m, side)), false, true);
              any = true;
            }
          }
        };
        lanes(el, e.s, CORRIDOR_M);
        if (nx && nx.edge.perDir >= 2 && rest < CORRIDOR_M) lanes(nx, -rest, CORRIDOR_M - rest);
        if (any) {
          const w = edge.wid, lw = w ? (edge.oneway ? Math.min(LANE_W, w / edge.perDir) : w / 2 / edge.perDir) : LANE_W;
          e.sirenPull = el.idx === 0 ? lw / 2 : -(el.idx - 0.5) * lw;
        }
      } else {
        const wide = (o: Car) => edge.wid > 0 && edge.wid >= e.wid + o.wid + 0.6;
        let aside = false;
        const one = (L: Lane, sBase: number, range: number) => {
          for (const o of this.near(e, L, sBase, range)) {
            if (o.emg) continue;
            if (L.edge.oneway && !wide(o)) {
              o.flee = t + 1.5;
              if (!o.fled && !o.res && o.el === e.el && o.route.length && e.route.length && o.route[0].to === e.route[0].to) {
                const alt = el.outs.filter((cn) => cn.to !== e.route[0].to && this.allowance(o, cn.to, el, o.dest) > 0);
                if (alt.length) { o.route.length = 0; o.route.push(alt[Math.floor(this.rnd() * alt.length)]); this.plan(o); }
                o.fled = true;
              }
              continue;
            }
            // Queued at a red light, or at the line of a box it waits for, where the siren cannot pass it in the
            // lane: stays put (the siren overtakes on the oncoming lane).
            if (!wide(o) && (o.waiting || (o.v < 0.5 && L.len - o.s < 25 && o.s > sBase))) continue;
            // Beyond the siren's own lane a car it could not pass keeps going, so as to clear the way into the next
            // street rather than block it.
            if (L !== el && !wide(o)) continue;
            this.setAside(o, 1, Math.min(1.5, this.room(o, L, 1)), true, wide(o));
            aside = true;
          }
        };
        one(el, e.s, PULL_M);
        if (nx && nx.edge.perDir === 1 && rest < PULL_M) one(nx, -rest, PULL_M - rest);
        const offR = el.off - (el.fwd ? edge.shift : -edge.shift);
        const opp = edge.oneway ? null : edge.lanes.find((m) => m.fwd !== el.fwd && m.acc & (A_CAR | A_BUS)) ?? null;
        // The car ahead it may not pass in the lane.
        let lead: Car | null = null;
        for (let m = i - 1; m >= 0; m--) if (!this.ghost(e, el.cars[m])) { lead = el.cars[m]; break; }
        if (!e.overtake && opp && lead && lead.s - lead.len - e.s < 30 && (lead.aside || lead.v < e.v * 0.7 || lead.v < 2)) {
          // Overtake on the oncoming lane if nothing comes the other way along its passing distance.
          const pass = Math.max(e.v, 8) * 4 + 20, end = Math.min(el.len - 6, e.s + pass);
          let clear = end > lead.s + 4;
          if (clear) for (const o of opp.cars) {
            const at = ((opp.len - o.s) * el.len) / opp.len;   // where it is in this lane's terms
            if (at > e.s - 5 && at - o.len < end + 10 + o.v * 3) { clear = false; break; }
          }
          if (clear) { e.overtake = true; e.overtakeEnd = end; e.overtakeLane = el; this.stats.overtakes++; }
        }
        if (e.overtake) {
          // Done once past its end and clear of every car in the lane.
          const beside = el.cars.some((o) => o !== e && Math.abs(o.s - e.s) < o.len + e.len + 1);
          if (e.s > e.overtakeEnd && !beside) e.overtake = false;
          else {
            e.sirenPull = -2 * offR;
            if (opp) for (const o of opp.cars) {
              const at = ((opp.len - o.s) * el.len) / opp.len;
              if (at > e.s - e.len && at - o.len < e.overtakeEnd + ONCOMING_STOP_M) this.setAside(o, 1, Math.min(0.4, this.room(o, opp, 1)), true, false);
            }
          }
        } else if (aside && edge.wid) {
          // Passing cars pulled in to the kerb: as far left as it needs to clear them.
          const w = edge.wid, car = offR + Math.min(1.5, this.room(e, el, 1)) - 1.8 / 2 - e.wid / 2 - 0.3;
          e.sirenPull = Math.min(0, Math.max(car, -w / 2 + e.wid / 2 + 0.2) - offR);
        }
      }
      // On two lanes or more: change to a free lane when the car ahead is close, slower and not aside.
      if (edge.perDir < 2) continue;
      i = el.cars.indexOf(e);
      let lead: Car | null = null;
      for (let m = i - 1; m >= 0; m--) if (!this.ghost(e, el.cars[m])) { lead = el.cars[m]; break; }
      if (!lead || lead.s - lead.len - e.s > 25 || lead.v > e.v + 0.5 && lead.v > el.v0 * 0.8 || e.res || e.waiting) continue;
      for (const m of edge.lanes) if (m !== el && m.fwd === el.fwd && Math.abs(m.idx - el.idx) === 1 && this.changeLane(e, el, m)) {
        this.stats.overtakes++; break;
      }
    }
  }

  /** Moves car c sideways from lane a to the parallel lane b if there is room. */
  private changeLane(c: Car, a: Lane, b: Lane): boolean {
    const s = (c.s * b.len) / a.len;
    if (s < c.len + 1 || s > b.len - 4 || !this.allowance(c, b, a, c.dest)) return false;
    let i = 0;
    while (i < b.cars.length && b.cars[i].s > s) i++;
    const ahead = b.cars[i - 1], behind = b.cars[i];
    if (ahead && ahead.s - ahead.len - s < IDM_S0 + 3) return false;
    if (behind && s - c.len - behind.s < IDM_S0 + 2 + behind.v) return false;
    a.cars.splice(a.cars.indexOf(c), 1);
    b.cars.splice(i, 0, c);
    c.el = b; c.s = s;
    c.lat = (a.idx - b.idx) * LANE_W * (a.fwd === b.fwd ? 1 : -1);
    c.route.length = 0;
    this.plan(c);
    return true;
  }

  /**
   * Puts an emergency vehicle on a street near the middle of the view (for testing and demonstrations). False if
   * there was no room.
   */
  spawnEmergency(type: "police" | "ambulance" | "fire" = "police", siren = true, street?: string): boolean {
    if (!this.emergencyOn) return false;
    const v = this.view, cx = (v.x0 + v.x1) / 2, cy = (v.y0 + v.y1) / 2;
    const o = this.tmp;
    const cand = this.activeLanes.filter((l) => l.acc & A_CAR && l.len > 40 && (!street || l.edge.name === street)).map((l) => {
      sample(l, l.len / 2, o);
      return { l, d: Math.hypot(o.x / this.mpp - cx, o.y / this.mpp - cy) };
    }).sort((p, q) => p.d - q.d);
    for (const { l } of cand.slice(0, 40)) {
      const n = l.cars.length;
      // The largest gap, as insertInGap.
      let best = -1, bestGap = 0, front = 0;
      for (let i = 1; i <= n; i++) {
        const lead = l.cars[i - 1], back = i < n ? l.cars[i].s : 0, g = lead.s - lead.len - back;
        if (g > bestGap) { bestGap = g; best = i; front = back; }
      }
      if (!n) { best = 0; bestGap = l.len * 0.7; front = l.len * 0.15; }
      if (best < 0 || bestGap < 2 * (IDM_S0 + 9) + 4) continue;
      const c = this.makeCar(l, 0, 0, { type, siren });
      c.s = front + (bestGap + c.len) / 2;
      c.v = l.v0 * 0.6;
      l.cars.splice(best, 0, c);
      return true;
    }
    return false;
  }

  // -------------------------------------------------------------------------------------------------------------
  // Step

  /**
   * Advance the simulation by dt seconds. view: the visible part of the map in map px; busy: 0..1, how much traffic
   * for the time of day.
   */
  step(dt: number, view: Rect, busy: number) {
    if (dt <= 0) return;
    dt = Math.min(dt, 0.1);
    this.t += dt;
    this.view = view;
    this.updateRegion(view);
    const k = (l: Lane) => l.density * busy * this.densScale; // cars per km
    const offScreen = (l: Lane) => l.bx1 < view.x0 || l.bx0 > view.x1 || l.by1 < view.y0 || l.by0 > view.y1;

    // New streets near the view start with their share of cars.
    for (const l of this.freshLanes) {
      if (!l.edge.active) continue;
      const want = (k(l) * l.len) / 1000;
      let n = Math.floor(want + this.rnd());
      while (n-- > 0 && this.stats.alive < this.maxCars && this.insertInGap(l, 0.7)) { /* placed */ }
    }
    this.freshLanes.length = 0;

    // Arrivals: on streets coming in from outside, and topping up streets out of sight, while there are fewer
    // cars than wanted.
    const want = this.target * busy;
    if (this.stats.alive < want) {
      for (const l of this.activeLanes) if (l.entry) this.trySpawn(l, (k(l) * l.v0 * 0.6) / 1000, dt);
    }
    this.topUpT += dt;
    if (this.topUpT > 1) {
      this.topUpT = 0;
      for (const l of this.activeLanes) {
        if (this.stats.alive >= want) break;
        if (l.len < 30 || !offScreen(l)) continue;
        if (l.cars.length < ((k(l) * l.len) / 1000) * 0.6 && this.rnd() < 0.3) this.insertInGap(l, 0.7);
      }
    }

    this.emergencyStep();
    for (const e of this.sirens) { this.stats.sirenS += dt; this.stats.sirenM += e.v * dt; }

    // Accelerations.
    const els: El[] = this.activeLanes.slice();
    for (const c of this.busyConns) els.push(c);
    for (const el of els) for (let i = 0; i < el.cars.length; i++) el.cars[i].acc = this.accel(el.cars[i], i);

    // Integrate, front to back, never into the car ahead.
    const stuck: Car[] = [], parked: Car[] = [];
    for (const el of els) {
      const arr = el.cars;
      for (let i = 0; i < arr.length; i++) {
        const c = arr[i];
        const v = Math.max(0, c.v + c.acc * dt);
        let ds = v * dt;
        let li = i - 1;
        while (li >= 0 && this.ghost(c, arr[li])) li--;
        if (li >= 0) {
          const l = arr[li], lim = l.s - l.len - 0.4 - c.s;
          if (ds > lim) { ds = Math.max(0, lim); c.v = Math.min(v, l.v); } else c.v = v;
        } else c.v = v;
        c.s += ds;
        if (c.hold) { c.holdS += ds; if (c.holdS > c.len * 0.8) { this.release(c, c.hold); c.hold = null; } }
        // Drawn sideways offsets ease back (out of a lane change) or out (aside for a siren, or a siren along the
        // corridor or in the oncoming lane). Aside: once no siren has asked for a while, wait 0.5 to 2 s, then rejoin.
        if (c.lat) c.lat = Math.abs(c.lat) < 0.05 ? 0 : c.lat * Math.exp(-2.5 * dt);
        if (c.aside && this.t > c.asideTill) {
          if (!c.rejoinAt) c.rejoinAt = this.t + 0.5 + 1.5 * this.rnd();
          else if (this.t > c.rejoinAt) { c.aside = 0; c.asideStop = false; c.pass = false; c.rejoinAt = 0; }
        }
        const pull = c.siren ? c.sirenPull : c.aside ? c.pullTo : 0;
        if (c.pull !== pull) c.pull += Math.max(-1.2 * dt, Math.min(1.2 * dt, pull - c.pull));
        if (c.dest === 2 && el === c.parkLane && c.s > c.parkS - 1.5 && c.v < 0.8) { parked.push(c); continue; }
        // Deadlock watch: stopped inside a box, or held at one by a box car that is itself stuck. Of two cars waiting
        // on each other, the newer one goes.
        if (c.v < 0.3) {
          const b = c.blocker;
          const heldByStuck = c.waiting && c.why === Why.Occupied && b !== null && b.alive && b.v < 0.3;
          if ((el.kind === 1 && el.box) || heldByStuck) c.stall += dt; else c.stall = 0;
          if (c.waiting && c.why !== Why.Signal) c.longWait += dt; else c.longWait = 0;
          // Waiting for room that never comes: a ring of queues all waiting on each other.
          if (c.longWait > DEADLOCK_S && Math.floor(c.longWait - dt) !== Math.floor(c.longWait)) {
            const g = this.gridlock(c);
            if (g) { stuck.push(g); this.removedWhy["gridlock ring"] = (this.removedWhy["gridlock ring"] ?? 0) + 1; c.longWait = 0; }
          }
          if (c.stall > DEADLOCK_S || c.longWait > LONG_WAIT_S) {
            const victim = heldByStuck && c.stall > DEADLOCK_S && b!.id > c.id ? b! : c;
            stuck.push(victim);
            const why = el.kind === 1 ? "in box" : c.stall > DEADLOCK_S ? "held by stuck box car" : "long wait " + c.why;
            this.removedWhy[why] = (this.removedWhy[why] ?? 0) + 1;
            c.stall = 0;
          }
        } else { c.stall = 0; c.longWait = 0; }
      }
    }
    for (const c of stuck) this.remove(c, true);
    for (const c of parked) if (c.alive) { this.remove(c, false); this.stats.parked++; }

    // Moves onto the next lane or through a box.
    for (const el of els) {
      let guard = 8;
      while (el.cars.length && el.cars[0].s > el.len && guard--) if (!this.advance(el.cars[0])) break;
    }
  }

  // -------------------------------------------------------------------------------------------------------------
  // Output

  /** Drawable cars, reused from one call of cars() to the next (no new objects every frame). */
  private pool: DrawableCar[] = [];
  private drawn: DrawableCar[] = [];

  /**
   * Every car near the view, centre and heading in map px. The array and its objects are reused: they are valid
   * until the next call, so copy anything that has to be kept.
   */
  cars(): readonly DrawableCar[] {
    const o = this.tmp, M = this.mpp, out = this.drawn;
    let n = 0;
    const one = (c: Car) => {
      let el = c.el, s = c.s - c.len / 2;
      if (s < 0 && c.prev) { el = c.prev; s += el.len; }
      sample(el, s, o);
      const off = c.lat + c.pull; // metres to the right of travel
      if (off) { o.x -= Math.sin(o.h) * off; o.y += Math.cos(o.h) * off; }
      const lane = el.kind === 0 ? el : el.to, e = lane.edge, e2 = el.kind === 1 ? el.from.edge : e;
      const d = this.pool[n] ?? (this.pool[n] = { id: 0, x: 0, y: 0, headingScreenRad: 0, type: "car", variant: 0,
        braking: false, siren: false, bridge: false, tunnel: false, length: 0, width: 0 });
      d.id = c.id; d.x = o.x / M; d.y = o.y / M; d.headingScreenRad = o.h; d.type = c.type; d.variant = c.variant;
      d.braking = c.acc < -0.8 || c.v < 0.5; d.siren = c.siren; d.bridge = e.bridge || e2.bridge;
      d.tunnel = e.tunnel && e2.tunnel; d.length = c.len / M; d.width = c.wid / M;
      out[n++] = d;
    };
    for (const l of this.activeLanes) for (const c of l.cars) one(c);
    for (const cn of this.busyConns) for (const c of cn.cars) one(c);
    out.length = n;
    return out;
  }

  /** Check for tests: ids of cars overlapping the car ahead on the same lane or move (should never happen). */
  laneOverlaps(): number[] {
    const bad: number[] = [];
    const els: El[] = this.activeLanes.slice();
    for (const c of this.busyConns) els.push(c);
    for (const el of els) for (let i = 1; i < el.cars.length; i++) {
      const a = el.cars[i - 1], b = el.cars[i];
      if (a.s - a.len - b.s < -0.05 && !this.ghost(a, b)) bad.push(a.id, b.id);
    }
    return bad;
  }

  /**
   * Check for tests: ids of cars whose centres are under dist metres from a car on another lane or move on the same
   * level (crossing traffic in a box, or streets drawn too close together).
   */
  closeCalls(dist = 1.5): number[] {
    const bad = new Set<number>();
    const pts = this.cars();
    const g = new Map<number, DrawableCar[]>(), cs = 8; // px
    for (const p of pts) { const kk = Math.floor(p.x / cs) * 100000 + Math.floor(p.y / cs); (g.get(kk) ?? g.set(kk, []).get(kk)!).push(p); }
    const lim = dist / this.mpp;
    for (const p of pts) {
      const cx = Math.floor(p.x / cs), cy = Math.floor(p.y / cs);
      for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (const q of g.get((cx + i) * 100000 + cy + j) ?? []) {
        if (q.id <= p.id || q.bridge !== p.bridge || q.tunnel !== p.tunnel) continue;
        if (Math.hypot(q.x - p.x, q.y - p.y) < lim) { bad.add(p.id); bad.add(q.id); }
      }
    }
    return [...bad];
  }

  /**
   * Check for tests: vehicles on a lane (or a junction move onto a lane) they may not use: private cars off car
   * lanes or passing through a destination-only street, buses off bus lanes, emergency vehicles off theirs. Returns
   * "id:type:edge" for each.
   */
  accessViolations(): string[] {
    const bad: string[] = [];
    const check = (c: Car, l: Lane) => {
      const a = l.acc;
      let ok: boolean;
      if (c.emg) ok = (a & (A_CAR | A_BUS | A_EMG)) !== 0;
      else if (c.type === "bus") ok = (a & A_BUS) !== 0;
      else ok = (a & A_CAR) !== 0 && (!(a & A_DEST) || c.dest !== 0 || c.parkLane === l);
      if (!ok) bad.push(`${c.id}:${c.type}:${l.edge.id}`);
    };
    for (const l of this.activeLanes) for (const c of l.cars) check(c, l);
    for (const cn of this.busyConns) for (const c of cn.cars) check(c, cn.to);
    return bad;
  }

  /** Cars still standing aside for a siren more than `sec` seconds after it last asked them to (for tests). */
  asideStale(sec: number): number {
    let n = 0;
    for (const l of this.activeLanes) for (const c of l.cars) if (c.aside && this.t - c.asideTill > sec) n++;
    for (const cn of this.busyConns) for (const c of cn.cars) if (c.aside && this.t - c.asideTill > sec) n++;
    return n;
  }

  /** Emergency vehicles alive, and how many of them have the siren on. */
  emergencyAlive(): { all: number; siren: number } {
    let all = 0;
    for (const l of this.activeLanes) for (const c of l.cars) if (c.emg) all++;
    for (const cn of this.busyConns) for (const c of cn.cars) if (c.emg) all++;
    return { all, siren: this.sirens.length };
  }

  /** The emergency vehicles with the siren on: speed (m/s) and the street they are on (for tests). */
  sirenStates(): { v: number; street: string }[] {
    return this.sirens.map((c) => ({ v: c.v, street: (c.el.kind === 0 ? c.el : c.el.to).edge.name }));
  }

  /** Speeds of the emergency vehicles with the siren on, m/s (for tests). */
  sirenSpeeds(): number[] {
    return this.sirens.map((c) => c.v);
  }

  /** Mean speed of the cars alive, m/s. */
  meanSpeed(): number {
    let n = 0, s = 0;
    for (const l of this.activeLanes) for (const c of l.cars) { n++; s += c.v; }
    for (const cn of this.busyConns) for (const c of cn.cars) { n++; s += c.v; }
    return n ? s / n : 0;
  }
}
