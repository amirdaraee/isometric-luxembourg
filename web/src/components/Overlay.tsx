import { useEffect, useRef } from "react";
import { asset } from "../config";
import { on } from "../features";
import type { MapHandle, MapMeta } from "./IsometricMap";
import { luxDayMask, luxSeconds, prepareShapes, stretch, transitSections, TRANSIT_HEIGHT_M, type Section, type Shape,
  type TransitData } from "./Transit";
import { drawLamps, drawVehicle, loadSprites, spriteLength, type Sprites } from "./sprites";
import { DRIVABLE, loadDrivable, loadOcclusion, type Drivable, type Occlusion } from "./occlusion";
import { waterPoints } from "./Water";
import { Traffic, type DrawableCar } from "../sim/traffic";
import { testParams } from "../testParams";
import { subscribe } from "../frame";

// Projected OSM lines (web/public/data/lines.json, from pipeline/project_lines.py), in map image pixels.
interface Line { id: number; n?: string; k?: string; b?: boolean; t?: boolean; o?: boolean; p: number[] }
interface Lines { roads: Line[]; rail: Line[]; waterways: Line[]; water: Line[] }
interface Prepared extends Line { box: [number, number, number, number]; len: number; cum: number[] }

interface Props {
  map: React.RefObject<MapHandle>;
  meta: MapMeta;
  streets: boolean;
  traffic: boolean;
  /** 0 day .. 1 full night: car lights, lit trains, less traffic */
  night: number;
  /** null: live clock; else the hour shown */
  hour: number | null;
  season: string;
}

const MPP = 0.25; // metres per image pixel
const ROAD_STYLE: Record<string, [string, number]> = {
  motorway: ["#ff6b35", 3], trunk: ["#ff8c42", 3], primary: ["#ffb347", 2.6], secondary: ["#ffd166", 2.2],
  tertiary: ["#fff3b0", 1.8], residential: ["#ffffff", 1.4], unclassified: ["#ffffff", 1.4], living_street: ["#e0f2fe", 1.2],
};
const CAR_COLOURS = ["#c0392b", "#2c3e50", "#ecf0f1", "#7f8c8d", "#2980b9", "#f1c40f", "#16a085", "#34495e", "#d35400", "#bdc3c7"];
const BUS_COLOUR = "#d62839";
const SIGNAL_COLOURS = { green: "#3ddc6f", amber: "#ffb020", red: "#ff3b30" };

/**
 * Placeholder drawing of one vehicle (until the sprites arrive, and as their fallback): a shaded rectangle, with
 * head and tail lights. sx, sy: screen px; z: zoom (screen px per map px).
 */
function drawCarRect(g: CanvasRenderingContext2D, c: DrawableCar, sx: number, sy: number, z: number, night: number) {
  const L = c.length * z, Wd = Math.max(c.width * z, 1.2);
  g.save(); g.translate(sx, sy); g.rotate(c.headingScreenRad);
  g.fillStyle = "rgba(0,0,0,.28)"; g.fillRect(-L / 2 + 1, -Wd / 2 + 1.5, L, Wd);
  g.fillStyle = c.type === "bus" ? BUS_COLOUR : CAR_COLOURS[c.variant % CAR_COLOURS.length]; g.fillRect(-L / 2, -Wd / 2, L, Wd);
  if (L > 8) { g.fillStyle = "rgba(255,255,255,.45)"; g.fillRect(-L * 0.12, -Wd / 2 + 1, L * 0.3, Wd - 2); }
  drawCarLights(g, c, L, Wd, night);
  g.restore();
}

/**
 * Headlight beam of a vehicle: a soft wedge on the ground ahead of it, drawn in ground metres (forward, right) through
 * the map's 2:1 view, so it narrows and shortens with the heading like the road itself. sx, sy: screen px of the
 * vehicle's ground centre; z: screen px per map px.
 */
function drawBeam(g: CanvasRenderingContext2D, c: DrawableCar, sx: number, sy: number, z: number, night: number) {
  const h = c.headingScreenRad, fx = Math.cos(h), fy = 2 * Math.sin(h), n = Math.hypot(fx, fy);
  const k = z / MPP;   // screen px per ground metre, before the 2:1 squash
  const half = (c.length * MPP) / 2, w = (c.width * MPP) / 2, reach = 9 + half;
  g.save();
  g.transform((fx / n) * k, (fy / n / 2) * k, (-fy / n) * k, (fx / n / 2) * k, sx, sy);
  const grd = g.createLinearGradient(half - 0.3, 0, reach, 0);
  grd.addColorStop(0, `rgba(255,236,190,${0.5 * night})`); grd.addColorStop(1, "rgba(255,236,190,0)");
  g.fillStyle = grd;
  g.beginPath(); g.moveTo(half - 0.3, -w * 0.9); g.lineTo(reach, -w * 2.4); g.lineTo(reach, w * 2.4); g.lineTo(half - 0.3, w * 0.9); g.fill();
  g.restore();
}

/** The placeholder rectangle's lights (drawCarRect only; it is flat, so lamps at its ends are right): headlight beam
 * ahead and tail lights behind, in the car's own frame; brake lights brighter when braking. */
function drawCarLights(g: CanvasRenderingContext2D, c: DrawableCar, L: number, Wd: number, night: number) {
  if (night > 0.05) {
    g.globalAlpha = night;
    const grd = g.createLinearGradient(L / 2, 0, L / 2 + L * 2.2, 0);
    grd.addColorStop(0, "rgba(255,236,190,.55)"); grd.addColorStop(1, "rgba(255,236,190,0)");
    g.fillStyle = grd;
    g.beginPath(); g.moveTo(L / 2, -Wd / 2); g.lineTo(L / 2 + L * 2.2, -Wd * 1.3); g.lineTo(L / 2 + L * 2.2, Wd * 1.3); g.lineTo(L / 2, Wd / 2); g.fill();
    g.globalAlpha = 1;
  }
  // Tail lights: on at night; brighter brake lights whenever the car brakes or stands (by day only close up).
  const a = c.braking ? Math.max(night, L > 6 ? 0.9 : 0) : night * 0.7;
  if (a > 0.05) {
    g.globalAlpha = a;
    g.fillStyle = c.braking ? "#ff1a10" : "#c8241c";
    const tw = c.braking ? 2.4 : 2;
    g.fillRect(-L / 2 - 1, -Wd / 2, tw, Wd * 0.3); g.fillRect(-L / 2 - 1, Wd / 2 - Wd * 0.3, tw, Wd * 0.3);
    g.globalAlpha = 1;
  }
}

/** Blue lamps of each emergency vehicle (as modelled in pipeline/build_sprites.py): metres ahead of the centre,
 * height, and half the distance between the left and right lamp. */
const LAMPS: Record<string, [number, number, number][]> = {
  police: [[-0.35, 1.66, 0.36]],
  ambulance: [[1.55, 2.46, 0.45], [-2.75, 2.77, 0.85]],
  fire: [[3.3, 2.9, 0.6], [-4.3, 3.08, 1.0]],
};

/** Is the lamp on at time t (s)? A double flash, left and right in turn. */
function lampOn(t: number, right: boolean): boolean {
  const ph = (t * 1.6 + (right ? 0.5 : 0)) % 1;
  return ph < 0.1 || (ph > 0.17 && ph < 0.27);
}

/**
 * Flashing blue lights of an emergency vehicle on a call, at its lamps on the roof: a small bright core and a halo,
 * kept modest by day and larger at night, with a faint blue wash on the ground after dark. sx, sy: screen px of the
 * vehicle's ground centre; z: screen px per map px; t: seconds.
 */
function drawSirenLights(g: CanvasRenderingContext2D, c: DrawableCar, sx: number, sy: number, z: number, t: number, night: number) {
  const lamps = LAMPS[c.type];
  if (!lamps) return;
  // Ground directions on screen (the map is drawn 2:1): forward along the heading, sideways across it, per metre.
  const h = c.headingScreenRad, fx = Math.cos(h), fy = 2 * Math.sin(h), n = Math.hypot(fx, fy);
  const k = z / MPP, ax = (fx / n) * k, ay = (fy / n / 2) * k, lx = (-fy / n) * k, ly = (fx / n / 2) * k;
  const up = 0.866 * k; // screen px per metre of height
  const tt = t + (c.id % 17) * 0.137; // vehicles out of step with each other
  const core = Math.max(1.4, 0.25 * k), halo = Math.max(5, 1.4 * k) * (1 + night);
  g.save();
  g.globalCompositeOperation = "lighter";
  if (night > 0.05) {
    const on = lampOn(tt, false) || lampOn(tt, true);
    const r = Math.max(6, 4.5 * k);
    const gr = g.createRadialGradient(sx, sy, 0, sx, sy, r);
    gr.addColorStop(0, `rgba(60,110,255,${(on ? 0.32 : 0.14) * night})`); gr.addColorStop(1, "rgba(60,110,255,0)");
    g.fillStyle = gr;
    g.beginPath(); g.ellipse(sx, sy, r, r / 2, 0, 0, Math.PI * 2); g.fill();
  }
  for (const [x, ht, w] of lamps) for (const right of [false, true]) {
    if (!lampOn(tt, right)) continue;
    const s = right ? -w : w;
    const px = sx + ax * x + lx * s, py = sy + ay * x + ly * s - up * ht;
    const gr = g.createRadialGradient(px, py, 0, px, py, halo);
    gr.addColorStop(0, "rgba(70,130,255,.95)");
    gr.addColorStop(0.4, `rgba(30,90,255,${0.55 + 0.25 * night})`);
    gr.addColorStop(1, "rgba(20,70,255,0)");
    g.fillStyle = gr;
    g.beginPath(); g.arc(px, py, halo, 0, Math.PI * 2); g.fill();
    g.fillStyle = "rgb(200,225,255)";
    g.beginPath(); g.arc(px, py, core, 0, Math.PI * 2); g.fill();
  }
  g.restore();
}

/** ?siren=<street name> (for videos and checks): an emergency vehicle on a call on that street near the middle of the
 * view, again whenever none is about (needs the emergency switch). */
const SIREN_STREET = typeof location !== "undefined" ? new URLSearchParams(location.search).get("siren") : null;

/** One thing to draw on the vehicle layer: a road vehicle or a tram or train section, at screen (sx, sy) (its ground
 * centre, lifted onto a deck where it is on one), with an opacity. */
interface Item { car?: DrawableCar; sec?: Section; sx: number; sy: number; a: number }
/** The cut height of each vehicle pass (m): cars; buses, fire engines and trams; trains; everything on a deck. */
const PASS_HEIGHT_M = [1.6, 3.2, TRANSIT_HEIGHT_M.train, TRANSIT_HEIGHT_M.train];
/** Half the width of the tube a tunnel clip erases (m), either side of the track. */
const TUNNEL_HALF_M = 3.5;

/** A tram or train section: its sprite and lamps (headlamps at the front by day as well, tail lamps and lit windows
 * at night; only the lamp pixels the camera sees light up), or the placeholder when the sprites are not there. */
function drawSection(g: CanvasRenderingContext2D, spr: Sprites | null, q: Section, sx: number, sy: number, z: number,
  night: number) {
  if (spr) {
    drawVehicle(g, spr, q.type, 0, sx, sy, q.h, z);
    drawLamps(g, spr, q.type, sx, sy, q.h, z,
      { head: q.end === 1 ? Math.max(0.35, night) : 0, tail: q.end === -1 ? night : 0, glass: night * 0.8 });
    return;
  }
  const L = (q.d1 - q.d0) * z, Wd = Math.max(((q.kind === "tram" ? 2.65 : 2.9) / MPP) * z, 2);
  g.save(); g.translate(sx, sy); g.rotate(q.h);
  g.fillStyle = "rgba(0,0,0,.28)"; g.fillRect(-L / 2 + 1.5, -Wd / 2 + 2, L, Wd);
  g.fillStyle = q.kind === "tram" ? "#1f2125" : "#f2f2ef"; g.fillRect(-L / 2, -Wd / 2, L, Wd);
  g.fillStyle = q.kind === "tram" ? "#b9bec6" : "#d4202b"; g.fillRect(-L / 2, Wd * 0.22, L, Wd * 0.28);
  g.strokeStyle = "rgba(20,20,24,.85)"; g.lineWidth = 1; g.strokeRect(-L / 2, -Wd / 2, L, Wd);
  if (night > 0.05) {
    g.globalAlpha = night; g.fillStyle = "rgba(255,214,140,.9)";
    for (let k = 0; k < 4; k++) g.fillRect(-L / 2 + (L * (k + 0.5)) / 4 - L * 0.05, -Wd * 0.12, L * 0.1, Wd * 0.24);
    g.globalAlpha = 1;
  }
  g.restore();
}

/**
 * Clips a section at a tunnel portal: erases, on `g`, the tunnel stretches of its shape near it, as a tube of
 * TUNNEL_HALF_M either side of the track swept up by the vehicle's height, so the coach slides into the hillside.
 * lift: screen px the section was lifted by (a deck at the portal).
 */
function clipTunnels(g: CanvasRenderingContext2D, sh: Shape, q: Section, lift: number, z: number, ox: number, oy: number) {
  const up = (TRANSIT_HEIGHT_M[q.kind] + 0.5) * (0.8660254 / MPP) * z, b = (TUNNEL_HALF_M / MPP) * z;
  g.save();
  g.globalCompositeOperation = "destination-out";
  g.fillStyle = "#000";
  for (const [t0, t1] of sh.tunnels) {
    if (t1 < q.d0 - 10 || t0 > q.d1 + 10) continue;
    const p = stretch(sh, Math.max(t0, q.d0 - 40), Math.min(t1, q.d1 + 40));
    for (let i = 0; i + 3 < p.length; i += 2) {
      const ax = p[i] * z + ox, ay = p[i + 1] * z + oy + lift, bx = p[i + 2] * z + ox, by = p[i + 3] * z + oy + lift;
      // across the track on the ground (the map is drawn 2:1), on screen
      const gx = bx - ax, gy = (by - ay) * 2, n = Math.hypot(gx, gy) || 1;
      const px = (-gy / n) * b, py = ((gx / n) * b) / 2;
      // the convex hull of the tube's cross-section at both ends, at the ground and at the roof
      const pts: [number, number][] = [];
      for (const [x, y] of [[ax, ay], [bx, by]]) for (const s of [-1, 1]) for (const h of [0, up]) pts.push([x + px * s, y + py * s - h]);
      const hull = convexHull(pts);
      g.beginPath(); g.moveTo(hull[0][0], hull[0][1]);
      for (let k = 1; k < hull.length; k++) g.lineTo(hull[k][0], hull[k][1]);
      g.closePath(); g.fill();
    }
  }
  g.restore();
}

/** Convex hull of a few points (monotone chain), in order round the hull. */
function convexHull(p: [number, number][]): [number, number][] {
  const s = [...p].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: number[], a: number[], b: number[]) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo: [number, number][] = [], hi: [number, number][] = [];
  for (const q of s) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
  for (let i = s.length - 1; i >= 0; i--) { const q = s[i]; while (hi.length >= 2 && cross(hi[hi.length - 2], hi[hi.length - 1], q) <= 0) hi.pop(); hi.push(q); }
  return lo.slice(0, -1).concat(hi.slice(0, -1));
}

function prepare(l: Line): Prepared {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const cum = [0];
  for (let i = 0; i < l.p.length; i += 2) {
    const x = l.p[i], y = l.p[i + 1];
    x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    if (i) cum.push(cum[cum.length - 1] + Math.hypot(x - l.p[i - 2], y - l.p[i - 1]));
  }
  return { ...l, box: [x0, y0, x1, y1], len: cum[cum.length - 1], cum };
}

// Point and heading at distance s along a polyline.
function at(r: Prepared, s: number): [number, number, number] {
  let i = 1;
  while (i < r.cum.length - 1 && r.cum[i] < s) i++;
  const a = (i - 1) * 2, seg = r.cum[i] - r.cum[i - 1] || 1, f = Math.min(Math.max((s - r.cum[i - 1]) / seg, 0), 1);
  const dx = r.p[a + 2] - r.p[a], dy = r.p[a + 3] - r.p[a + 1];
  return [r.p[a] + dx * f, r.p[a + 1] + dy * f, Math.atan2(dy, dx)];
}

/** A flock: centre in map px, heading, speed (map px/s), birds as offsets from the centre with a flap phase. */
interface Flock { x: number; y: number; h: number; v: number; turn: number; birds: { dx: number; dy: number; ph: number }[] }

function newFlock(spawn: Glint[], rnd: () => number): Flock {
  const at = spawn[Math.floor(rnd() * spawn.length)];
  const n = 4 + Math.floor(rnd() * 10);
  const birds = Array.from({ length: n }, () => ({ dx: (rnd() - 0.5) * 70, dy: (rnd() - 0.5) * 40, ph: rnd() * 6.28 }));
  return { x: at.x, y: at.y - 60, h: rnd() * 6.28, v: 28 + rnd() * 20, turn: (rnd() - 0.5) * 0.3, birds };
}
/** A point of light on the water: map px, a phase for its twinkle, a length. */
interface Glint { x: number; y: number; ph: number; len: number }


export function Overlay({ map, meta, streets, traffic, night, hour, season }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  // Vehicles: 32-heading sprites, the foreground that hides them, and their own layer (cut, then copied over).
  const sprites = useRef<Sprites | null>(null);
  const occl = useRef<Occlusion | null>(null);
  const vlayer = useRef<HTMLCanvasElement | null>(null);
  // Tram and train sections at a tunnel portal, drawn here and clipped before they join the vehicle layer.
  const portalLayer = useRef<HTMLCanvasElement | null>(null);
  // When the last ?siren= vehicle was put on its street.
  const sirenAt = useRef(-1e9);
  const drivable = useRef<Drivable | null>(null);
  // Per car id: how visible it is (0..1, the guard's fade) and the frame it was last seen in.
  const fades = useRef(new Map<number, { a: number; stamp: number }>());
  const fadeStamp = useRef(0);
  useEffect(() => {
    if (!on("traffic") && !on("transit")) return;
    loadSprites().then((x) => { sprites.current = x; }).catch(() => {});
    loadOcclusion().then((x) => { occl.current = x; }).catch(() => {});
    loadDrivable().then((x) => { drivable.current = x; }).catch(() => {});
  }, []);
  const state = useRef<{ lines?: Lines; roads?: Prepared[]; named?: Prepared[]; rail?: Prepared[]; water?: Prepared[];
    waterways?: Prepared[]; flocks?: Flock[]; sim?: Traffic }>({});
  const flags = useRef({ streets, traffic, night, hour, season });
  flags.current = { streets, traffic, night, hour, season };

  // Where the ground / bridge decks are really visible (from the 3D render), 1 px = 8 map px.
  const vis_ = useRef<{ w: number; h: number; d: Uint8Array } | null>(null);
  const transit = useRef<{ d: TransitData; shapes: ReturnType<typeof prepareShapes> } | null>(null);
  useEffect(() => {
    if (on("transit")) fetch(asset("/data/transit.json")).then((r) => r.json()).then((d: TransitData) => { transit.current = { d, shapes: prepareShapes(d) }; }).catch(() => {});
  }, []);
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width; c.height = img.height;
      const g = c.getContext("2d")!;
      g.drawImage(img, 0, 0);
      const px = g.getImageData(0, 0, img.width, img.height).data;
      const d = new Uint8Array(img.width * img.height);
      for (let i = 0; i < d.length; i++) d[i] = px[i * 4];
      vis_.current = { w: img.width, h: img.height, d };
    };
    img.src = asset("/data/visibility.png");
  }, []);

  useEffect(() => {
    fetch(asset("/data/lines.json")).then((r) => r.json()).then((L: Lines) => {
      const st = state.current;
      st.roads = L.roads.filter((r) => !r.t).map(prepare);
      st.named = st.roads.filter((r) => r.n && r.k !== "footway" && r.k !== "path" && r.k !== "steps" && r.len > 120);
      st.rail = L.rail.filter((r) => !r.t).map(prepare);
      st.water = L.water.map(prepare);
      // Birds start over the rivers (the painted water mask) inside the painted area.
      const areas0 = meta.painted ?? [];
      let bseed = 7;
      const brnd = () => ((bseed = (bseed * 48271) % 2147483647) / 2147483647);
      waterPoints().then((pts) => {
        const spawn = pts.filter((g) => areas0.some((a) => g.x > a.x0 && g.x < a.x0 + a.w && g.y > a.y0 && g.y < a.y0 + a.h))
          .map((g) => ({ x: g.x, y: g.y, ph: 0, len: 0 }));
        st.flocks = spawn.length ? Array.from({ length: 14 }, () => newFlock(spawn, brnd)) : [];
        (st as { spawn?: Glint[] }).spawn = spawn;
      }).catch(() => { st.flocks = []; });
      st.waterways = L.waterways.filter((r) => !r.t).map(prepare);
      // Traffic only where the map is painted (src/sim/traffic.ts: road graph, junctions, signals, car following).
      if (meta.painted?.length) st.sim = new Traffic(L.roads, { areas: meta.painted, mpp: MPP, emergency: on("emergency"), seed: testParams.seed ?? undefined });
      // In development, the simulation is reachable from the console and from headless checks.
      if (import.meta.env.DEV) (window as unknown as { traffic?: Traffic }).traffic = st.sim;
    });
  }, [meta]);

  useEffect(() => {
    let last = performance.now();
    // Draw once per frame. While the map moves, OpenSeadragon's own frame ("update-viewport") draws, so cars and
    // street lines never trail the map; the frame clock then skips its draw. When the map is still, the frame clock
    // draws. (A guard until frame.ts merges the map's frame into its own.)
    let lastMapDraw = -1e9;
    const draw = (now: number) => {
      const dt = Math.min(Math.max(now - last, 0) / 1000, 0.1);
      last = Math.max(last, now);
      const cv = canvas.current, v = map.current?.getView(), st = state.current;
      if (!cv || !v || !st.roads) return;
      const dpr = window.devicePixelRatio || 1, W = window.innerWidth, H = window.innerHeight;
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      const g = cv.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const { streets, traffic, night, hour, season } = flags.current;
      const winter = season === "winter" && on("snow");
      const birds = on("birds") && st.flocks?.length && night < 0.6 && v.z >= 0.1;
      if (!streets && !traffic && !winter && !birds) return;
      // image px -> screen px
      const z = v.z, ox = W / 2 - v.x * z, oy = H / 2 - v.y * z;
      const vis = (b: number[]) => b[2] * z + ox > -50 && b[0] * z + ox < W + 50 && b[3] * z + oy > -50 && b[1] * z + oy < H + 50;
      const path = (p: number[]) => {
        g.beginPath();
        g.moveTo(p[0] * z + ox, p[1] * z + oy);
        for (let i = 2; i < p.length; i += 2) g.lineTo(p[i] * z + ox, p[i + 1] * z + oy);
      };

      if (streets) {
        g.lineJoin = "round"; g.lineCap = "round";
        g.fillStyle = "rgba(56,152,255,.35)"; g.strokeStyle = "rgba(56,152,255,.9)"; g.lineWidth = 1.5;
        for (const w of st.water!) if (vis(w.box)) { path(w.p); g.closePath(); g.fill(); g.stroke(); }
        g.lineWidth = 3;
        for (const w of st.waterways!) if (vis(w.box)) { path(w.p); g.stroke(); }
        g.strokeStyle = "rgba(20,20,20,.85)"; g.setLineDash([6, 4]); g.lineWidth = 2;
        for (const r of st.rail!) if (vis(r.box)) { path(r.p); g.stroke(); }
        g.setLineDash([]);
        const zs = Math.min(Math.max(z * 4, 0.6), 2.2);
        for (const r of st.roads) {
          const sty = ROAD_STYLE[r.k ?? ""];
          if (!sty || !vis(r.box)) continue;
          if (z < 0.12 && !["motorway", "trunk", "primary", "secondary"].includes(r.k!)) continue;
          path(r.p);
          g.strokeStyle = "rgba(20,24,32,.55)"; g.lineWidth = sty[1] * zs + 2; g.stroke();
          g.strokeStyle = r.b ? "#ffe066" : sty[0]; g.lineWidth = sty[1] * zs; g.stroke();
        }
        // Street names along their longest straight-ish stretch, only when zoomed in enough to read.
        if (z >= 0.22) {
          g.font = `600 ${Math.round(11 + Math.min(z, 1.2) * 4)}px system-ui, sans-serif`;
          g.textAlign = "center"; g.textBaseline = "middle";
          const used: [number, number, number, number][] = [], seen = new Set<string>();
          for (const r of st.named!) {
            if (seen.has(r.n!) || !vis(r.box)) continue;
            const [x, y, ang] = at(r, r.len / 2);
            const sx = x * z + ox, sy = y * z + oy;
            if (sx < 40 || sx > W - 40 || sy < 40 || sy > H - 40) continue;
            const tw = g.measureText(r.n!).width;
            if (tw > r.len * z * 0.9) continue;
            const bx: [number, number, number, number] = [sx - tw / 2 - 4, sy - 12, sx + tw / 2 + 4, sy + 12];
            if (used.some((u) => bx[0] < u[2] && bx[2] > u[0] && bx[1] < u[3] && bx[3] > u[1])) continue;
            used.push(bx); seen.add(r.n!);
            let a = ang;
            if (a > Math.PI / 2) a -= Math.PI; else if (a < -Math.PI / 2) a += Math.PI;
            g.save(); g.translate(sx, sy); g.rotate(a);
            g.lineWidth = 3.5; g.strokeStyle = "rgba(20,24,32,.85)"; g.strokeText(r.n!, 0, 0);
            g.fillStyle = "#fff"; g.fillText(r.n!, 0, 0);
            g.restore();
          }
        }
      }

      if (birds) {
        // Inked birds: two short wing strokes that flap; flocks drift and turn slowly, and start again over a river
        // when they leave the painted area.
        const t = now / 1000;
        const areas = meta.painted ?? [];
        const spawn = (st as { spawn?: Glint[] }).spawn!;
        g.strokeStyle = "rgba(28,30,40,.85)"; g.lineCap = "round";
        g.lineWidth = Math.max(1.4, z * 2.2);
        const span = Math.max(5, 11 * z);
        for (let i = 0; i < st.flocks!.length; i++) {
          const f = st.flocks![i];
          f.h += (f.turn + Math.sin(t * 0.13 + i) * 0.25) * dt;
          f.x += Math.cos(f.h) * f.v * dt; f.y += Math.sin(f.h) * f.v * 0.5 * dt;
          if (!areas.some((a) => f.x > a.x0 && f.x < a.x0 + a.w && f.y > a.y0 && f.y < a.y0 + a.h)) {
            st.flocks![i] = newFlock(spawn, Math.random);
            continue;
          }
          for (const b of f.birds) {
            const sx = (f.x + b.dx) * z + ox, sy = (f.y + b.dy) * z + oy;
            if (sx < -20 || sx > W + 20 || sy < -20 || sy > H + 20) continue;
            const up = Math.sin(t * 9 + b.ph) * 0.6;
            g.beginPath();
            g.moveTo(sx - span, sy - span * up); g.quadraticCurveTo(sx - span * 0.4, sy - span * 0.35, sx, sy);
            g.quadraticCurveTo(sx + span * 0.4, sy - span * 0.35, sx + span, sy - span * up);
            g.stroke();
          }
        }
      }

      if (winter) {
        const t = now / 1000;
        g.fillStyle = "rgba(255,255,255,.85)";
        for (let i = 0; i < 260; i++) {
          const sx = ((i * 97.13 + Math.sin(t * 0.7 + i) * 18 + t * 12) % (W + 20) + W + 20) % (W + 20) - 10;
          const sy = ((i * 53.71 + t * (28 + (i % 7) * 6)) % (H + 20)) - 10;
          const r = 0.8 + (i % 3) * 0.6;
          g.beginPath(); g.arc(sx, sy, r, 0, Math.PI * 2); g.fill();
        }
      }

      const doCars = traffic && on("traffic") && !!st.sim && z >= 0.08;
      const doTrains = traffic && on("transit") && !!transit.current && z >= 0.06;
      if (doCars || doTrains) {
        const V = vis_.current;
        // Is the ground (or, for a bridge road, the deck) really visible from above here?
        const seen = (x: number, y: number, bridge: boolean) => {
          if (!V) return true;
          const vx = x >> 3, vy = y >> 3;
          const val = vx >= 0 && vy >= 0 && vx < V.w && vy < V.h ? V.d[vy * V.w + vx] : 0;
          return val === 255 || (val === 128 && bridge);
        };
        const spr = sprites.current, occ = occl.current, drv = drivable.current;
        // Four passes, shortest vehicles first, each followed by its cut: cars, vans, police cars and ambulances
        // (1.6 m); buses, fire engines and trams (3.2 m); trains (4.6 m); then everything on a bridge deck, lifted
        // onto the modelled deck and cut against the deck layer.
        const passes: Item[][] = [[], [], [], []];
        if (doCars) {
          const sim = st.sim!;
          // fewer cars late at night and at dawn, rush hours busiest
          const hr = hour === null ? luxSeconds() / 3600 : hour;
          const busy = hr < 5 ? 0.12 : hr < 6.5 ? 0.35 : hr < 9.5 ? 1 : hr < 16 ? 0.75 : hr < 19 ? 1 : hr < 22 ? 0.5 : 0.25;
          // Only the streets near the view are simulated; cars come and go at the margins.
          sim.step(dt, { x0: -ox / z, y0: -oy / z, x1: (W - ox) / z, y1: (H - oy) / z }, busy);
          if (SIREN_STREET && on("emergency") && now - sirenAt.current > 4000 && sim.emergencyAlive().siren === 0) {
            sirenAt.current = now;
            const kinds = ["ambulance", "police", "fire"] as const;
            sim.spawnEmergency(kinds[Math.floor(now / 1000) % 3], true, SIREN_STREET);
          }
          // The guard: where a car's drawn ground point is on water, inside a building, outside the painted art, or
          // behind a building that the occlusion cut does not hide it behind (it would show on the facade), the car
          // fades out over 0.3 s (and back in when it leaves). On a modelled deck it is fine. Without drivable data
          // yet, the old visibility test decides.
          const show = (c: DrawableCar, gy: number, onDeck: boolean) => {
            const v = drv ? drv.at(c.x, gy) : -1;
            if (v < 0) return seen(c.x, c.y, c.bridge);
            if (v === DRIVABLE.unpainted) return false;
            if (v === DRIVABLE.water || v === DRIVABLE.building) return onDeck;
            if (v === DRIVABLE.hidden) return onDeck || (occ ? occ.coverage(c.x, gy, 1.6) >= 0.5 : false);
            return true;
          };
          const fade = fades.current, stamp = ++fadeStamp.current;
          let guarded = 0;
          for (const c of sim.cars()) {
            // In a tunnel: not drawn.
            if (c.tunnel) continue;
            let sx = c.x * z + ox, sy = c.y * z + oy;
            if (sx < -30 || sx > W + 30 || sy < -30 || sy > H + 30) continue;
            let gy = c.y, pass = c.type === "bus" || c.type === "fire" ? 1 : 0;
            if (c.bridge && occ) {
              const d = occ.deckAt(c.x, c.y);
              if (d) { sy -= d.lift * z; gy -= d.lift; pass = 3; }
            }
            const want = show(c, gy, pass === 3) ? 1 : 0;
            const f = fade.get(c.id);
            let a = f ? f.a : want;
            a = want > a ? Math.min(want, a + dt / 0.3) : Math.max(want, a - dt / 0.3);
            if (f) { f.a = a; f.stamp = stamp; } else fade.set(c.id, { a, stamp });
            if (!want) guarded++;
            if (a <= 0.01) continue;
            passes[pass].push({ car: c, sx, sy, a });
          }
          sim.stats.guarded = guarded;
          if (stamp % 120 === 0) for (const [id, f] of fade) if (f.stamp !== stamp) fade.delete(id);
        }
        if (doTrains) {
          // Trams and trains: on the OSM rail ways the painting followed. In a tunnel they are not drawn (a section
          // at a portal is clipped there); on a viaduct or bridge they are lifted onto the modelled deck; everywhere
          // they are cut against the foreground like the cars. Outside the painted art they are not drawn.
          const tc = transit.current!;
          const m = 300 / z;
          const secs = transitSections(tc.d, tc.shapes, hour === null ? luxSeconds() : hour * 3600, luxDayMask(),
            [-ox / z - m, -oy / z - m, (W - ox) / z + m, (H - oy) / z + m], spr ? (t) => spriteLength(spr, t) : undefined);
          for (const q of secs) {
            if (drv && drv.at(q.x, q.y) === DRIVABLE.unpainted) continue;
            const sx = q.x * z + ox;
            let sy = q.y * z + oy, pass = q.kind === "tram" ? 1 : 2;
            if (occ && q.way >= 0 && occ.isDeck(q.way)) {   // on a deck, even where it sits where lines.json drew it
              sy -= occ.deckLift(q.way, q.s) * z;
              pass = 3;
            }
            if (sx < -300 || sx > W + 300 || sy < -300 || sy > H + 300) continue;
            passes[pass].push({ sec: q, sx, sy, a: 1 });
          }
        }
        if (passes.some((l) => l.length)) {
          const vl = vlayer.current ?? (vlayer.current = document.createElement("canvas"));
          if (vl.width !== cv.width || vl.height !== cv.height) { vl.width = cv.width; vl.height = cv.height; }
          const vg = vl.getContext("2d")!;
          vg.setTransform(dpr, 0, 0, dpr, 0, 0);
          vg.clearRect(0, 0, W, H);
          const view = { z, ox, oy, w: W, h: H };
          // Bare crowns in winter hide much less.
          const canopy = season === "winter" ? 0.4 : 1;
          // Far to near within each pass (by screen y), so a nearer vehicle overlaps the one behind it.
          for (const list of passes) list.sort((a, b) => a.sy - b.sy);
          // Brake lights by day only close up and softer; at night tail lights always on and brake lights brighter.
          const brakeDay = z >= 0.6 ? 0.6 : 0;
          const tunnels = transit.current?.shapes;
          passes.forEach((list, i) => {
            // Headlight beams first, on the ground: the bodies drawn next cover their start, and the cut trims them.
            if (spr && night > 0.05) for (const it of list) if (it.car) { vg.globalAlpha = it.a; drawBeam(vg, it.car, it.sx, it.sy, z, night); }
            // Sections at a tunnel portal go on their own layer first, to be clipped there.
            let portals: Item[] | null = null;
            for (const it of list) {
              const c = it.car;
              if (!c) {
                if (it.sec!.portal && tunnels) (portals ??= []).push(it);
                else drawSection(vg, spr, it.sec!, it.sx, it.sy, z, night);
                continue;
              }
              vg.globalAlpha = it.a;
              if (spr) {
                drawVehicle(vg, spr, c.type, c.variant, it.sx, it.sy, c.headingScreenRad, z);
                drawLamps(vg, spr, c.type, it.sx, it.sy, c.headingScreenRad, z,
                  { tail: night * 0.85, brake: c.braking ? Math.max(night, brakeDay) : 0, head: night });
              } else drawCarRect(vg, c, it.sx, it.sy, z, night);
              if (c.siren) drawSirenLights(vg, c, it.sx, it.sy, z, now / 1000, night);
            }
            vg.globalAlpha = 1;
            if (portals && tunnels) {
              const pl = portalLayer.current ?? (portalLayer.current = document.createElement("canvas"));
              if (pl.width !== cv.width || pl.height !== cv.height) { pl.width = cv.width; pl.height = cv.height; }
              const pg = pl.getContext("2d")!;
              pg.setTransform(dpr, 0, 0, dpr, 0, 0);
              pg.clearRect(0, 0, W, H);
              for (const it of portals) drawSection(pg, spr, it.sec!, it.sx, it.sy, z, night);
              for (const it of portals) clipTunnels(pg, tunnels[it.sec!.shape], it.sec!, it.sy - (it.sec!.y * z + oy), z, ox, oy);
              vg.save(); vg.setTransform(1, 0, 0, 1, 0, 0); vg.drawImage(pl, 0, 0); vg.restore();
            }
            if (occ && list.length) occ.cut(vg, view, PASS_HEIGHT_M[i], i === 3 ? "deck" : "ground", canopy);
          });
          g.save(); g.setTransform(1, 0, 0, 1, 0, 0); g.drawImage(vl, 0, 0); g.restore();
        }
        // Small signal heads at the stop lines, when zoomed in.
        if (doCars && on("signals") && z > 0.6) {
          const r = Math.max(1.6, (0.45 / MPP) * z);
          for (const sg of st.sim!.signals()) {
            if (!seen(sg.x, sg.y, false)) continue;
            const sx = sg.x * z + ox, sy = sg.y * z + oy;
            g.fillStyle = "rgba(20,22,28,.85)";
            g.beginPath(); g.arc(sx, sy, r + 1.2, 0, Math.PI * 2); g.fill();
            g.fillStyle = SIGNAL_COLOURS[sg.state];
            g.beginPath(); g.arc(sx, sy, r, 0, Math.PI * 2); g.fill();
          }
        }
      }
    };
    const stop = subscribe((t) => { if (t - lastMapDraw > 40) draw(t); });
    const off = map.current?.onFrame(() => { const t = performance.now(); lastMapDraw = t; draw(t); });
    return () => { stop(); off?.(); };
  }, [map]);

  return <canvas ref={canvas} className="overlay" aria-hidden="true" />;
}
