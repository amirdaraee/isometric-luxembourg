import { useEffect, useRef } from "react";
import { asset } from "../config";
import { on } from "../features";
import type { MapHandle, MapMeta } from "./IsometricMap";
import { drawTransit, luxSeconds, prepareShapes, type TransitData } from "./Transit";

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
const DRIVE = new Set(["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
  "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "living_street"]);
const SPEED_KMH: Record<string, number> = { motorway: 90, trunk: 70, primary: 50, secondary: 50, tertiary: 40,
  residential: 30, living_street: 15, unclassified: 40 };
const ROAD_STYLE: Record<string, [string, number]> = {
  motorway: ["#ff6b35", 3], trunk: ["#ff8c42", 3], primary: ["#ffb347", 2.6], secondary: ["#ffd166", 2.2],
  tertiary: ["#fff3b0", 1.8], residential: ["#ffffff", 1.4], unclassified: ["#ffffff", 1.4], living_street: ["#e0f2fe", 1.2],
};
const CAR_COLOURS = ["#c0392b", "#2c3e50", "#ecf0f1", "#7f8c8d", "#2980b9", "#f1c40f", "#16a085", "#34495e", "#d35400", "#bdc3c7"];

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

interface Car { road: Prepared; s: number; dir: 1 | -1; speed: number; colour: string; len: number }
/** A point of light on the water: map px, a phase for its twinkle, a length. */
interface Glint { x: number; y: number; ph: number; len: number }

// Scatter glints over the water polygons, about one per 22 x 22 map px, in a fixed (seeded) pattern. Scanlines
// rather than random tries, because a river is one long thin polygon whose bounding box covers the whole city.
function scatterGlints(water: Prepared[]): Glint[] {
  let seed = 1867;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const out: Glint[] = [];
  const STEP = 22;
  for (const w of water) {
    const p = w.p;
    for (let y = Math.ceil(w.box[1] / STEP) * STEP; y <= w.box[3]; y += STEP) {
      const xs: number[] = [];
      for (let i = 0, j = p.length - 2; i < p.length; j = i, i += 2) {
        const yi = p[i + 1], yj = p[j + 1];
        if ((yi > y) !== (yj > y)) xs.push(p[i] + ((y - yi) * (p[j] - p[i])) / (yj - yi));
      }
      xs.sort((m, n) => m - n);
      for (let k = 0; k + 1 < xs.length; k += 2) {
        for (let x = xs[k] + rnd() * STEP; x < xs[k + 1]; x += STEP) {
          out.push({ x, y: y + (rnd() - 0.5) * STEP * 0.8, ph: rnd(), len: 5 + rnd() * 8 });
        }
      }
    }
  }
  return out;
}

export function Overlay({ map, meta, streets, traffic, night, hour, season }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef<{ lines?: Lines; roads?: Prepared[]; named?: Prepared[]; rail?: Prepared[]; water?: Prepared[];
    waterways?: Prepared[]; glints?: Glint[]; cars?: Car[]; ends?: Map<string, { road: Prepared; atStart: boolean }[]> }>({});
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
      st.glints = scatterGlints(st.water);
      st.waterways = L.waterways.filter((r) => !r.t).map(prepare);
      // Traffic only where the map is painted, on roads cars use.
      const areas = meta.painted ?? [];
      const inPainted = (r: Prepared) => areas.some((a) => r.box[0] >= a.x0 && r.box[2] <= a.x0 + a.w && r.box[1] >= a.y0 && r.box[3] <= a.y0 + a.h);
      const drive = st.roads.filter((r) => DRIVE.has(r.k ?? "") && inPainted(r) && r.len > 8);
      const key = (x: number, y: number) => `${Math.round(x / 3)},${Math.round(y / 3)}`;
      const ends = new Map<string, { road: Prepared; atStart: boolean }[]>();
      for (const r of drive) {
        for (const [x, y, atStart] of [[r.p[0], r.p[1], true], [r.p[r.p.length - 2], r.p[r.p.length - 1], false]] as const) {
          const k = key(x, y);
          (ends.get(k) ?? ends.set(k, []).get(k)!).push({ road: r, atStart });
        }
      }
      st.ends = ends;
      // More cars on bigger roads.
      const weight = (r: Prepared) => r.len * ({ motorway: 3, trunk: 3, primary: 2.5, secondary: 2, tertiary: 1.5 }[r.k ?? ""] ?? 0.7);
      const total = drive.reduce((a, r) => a + weight(r), 0);
      const n = Math.min(900, Math.round(total / 260));
      const cars: Car[] = [];
      for (let i = 0; i < n && drive.length; i++) {
        let t = Math.random() * total, road = drive[0];
        for (const r of drive) { t -= weight(r); if (t <= 0) { road = r; break; } }
        const dir: 1 | -1 = road.o || Math.random() < 0.5 ? 1 : -1;
        cars.push({ road, s: Math.random() * road.len, dir, speed: 0, colour: CAR_COLOURS[i % CAR_COLOURS.length],
          len: (Math.random() < 0.08 ? 10 : 4.4) / MPP });
      }
      for (const c of cars) c.speed = (((SPEED_KMH[c.road.k ?? ""] ?? 30) / 3.6) / MPP) * (0.75 + Math.random() * 0.4);
      st.cars = cars;
    });
  }, [meta]);

  useEffect(() => {
    let raf = 0, last = performance.now();
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      draw(now);
    };
    const draw = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      const cv = canvas.current, v = map.current?.getView(), st = state.current;
      if (!cv || !v || !st.roads) return;
      const dpr = window.devicePixelRatio || 1, W = window.innerWidth, H = window.innerHeight;
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      const g = cv.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const { streets, traffic, night, hour, season } = flags.current;
      const winter = season === "winter" && on("snow");
      const glints = on("water") && st.glints && v.z >= 0.12;
      if (!streets && !traffic && !winter && !glints) return;
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

      if (glints) {
        // Light on the water: short horizontal glints that twinkle in steps (6 per second), like ripples catching
        // the sun; warm reflections at night. Only where the water is really visible from above.
        const V = vis_.current;
        const t = Math.floor(now / 1000 * 6) / 6;
        const col = night > 0.5 ? "255,206,130" : "255,255,255";
        const peak = night > 0.5 ? 0.7 : 0.95;
        const wpx = Math.max(1.2, z * 1.8);
        for (const gl of st.glints!) {
          const sx = gl.x * z + ox, sy = gl.y * z + oy;
          if (sx < -10 || sx > W + 10 || sy < -10 || sy > H + 10) continue;
          if (V) {
            const vx = gl.x >> 3, vy = gl.y >> 3;
            if (!(vx >= 0 && vy >= 0 && vx < V.w && vy < V.h && V.d[vy * V.w + vx] === 255)) continue;
          }
          const s = Math.sin(t * 1.7 + gl.ph * 6.283);
          if (s < 0.35) continue;
          const a = ((s - 0.35) / 0.65) ** 1.5 * peak;
          const L = Math.max(2, gl.len * z);
          g.fillStyle = `rgba(${col},${a.toFixed(3)})`;
          g.fillRect(sx - L / 2, sy, L, wpx);
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

      if (traffic && on("transit") && transit.current && z >= 0.06) {
        const V = vis_.current;
        const visible = (x: number, y: number) => {
          if (!V) return true;
          const vx = x >> 3, vy = y >> 3;
          const v = vx >= 0 && vy >= 0 && vx < V.w && vy < V.h ? V.d[vy * V.w + vx] : 0;
          return v === 255 || v === 128;
        };
        drawTransit(g, transit.current.d, transit.current.shapes, hour === null ? luxSeconds() : hour * 3600, z, ox, oy, W, H, visible, night);
      }

      if (traffic && on("traffic") && st.cars && z >= 0.08) {
        const lane = 1.6 / MPP; // drive on the right, 1.6 m off the centreline
        // fewer cars late at night and at dawn, rush hours busiest
        const hr = hour === null ? luxSeconds() / 3600 : hour;
        const busy = hr < 5 ? 0.12 : hr < 6.5 ? 0.35 : hr < 9.5 ? 1 : hr < 16 ? 0.75 : hr < 19 ? 1 : hr < 22 ? 0.5 : 0.25;
        let idx = 0;
        for (const c of st.cars) {
          idx++;
          c.s += c.speed * dt * c.dir;
          if ((idx * 0.618) % 1 > busy) continue;
          if (c.s > c.road.len || c.s < 0) {
            // Continue onto a road that starts or ends here; otherwise turn around.
            const endX = c.dir > 0 ? c.road.p[c.road.p.length - 2] : c.road.p[0];
            const endY = c.dir > 0 ? c.road.p[c.road.p.length - 1] : c.road.p[1];
            const opts = (st.ends!.get(`${Math.round(endX / 3)},${Math.round(endY / 3)}`) ?? [])
              .filter((o) => o.road !== c.road && (o.atStart || !o.road.o));
            if (opts.length) {
              const o = opts[Math.floor(Math.random() * opts.length)];
              c.road = o.road; c.dir = o.atStart ? 1 : -1; c.s = o.atStart ? 0 : o.road.len;
              c.speed = (((SPEED_KMH[c.road.k ?? ""] ?? 30) / 3.6) / MPP) * (0.75 + Math.random() * 0.4);
            } else if (!c.road.o) { c.dir = c.dir > 0 ? -1 : 1; c.s = Math.min(Math.max(c.s, 0), c.road.len); }
            else c.s = 0;
          }
          if (!vis(c.road.box)) continue;
          const [x, y, ang] = at(c.road, c.s);
          // Hidden behind a building (or under a bridge, for ground roads): don't draw.
          const V = vis_.current;
          if (V) {
            const vx = x >> 3, vy = y >> 3;
            const val = vx >= 0 && vy >= 0 && vx < V.w && vy < V.h ? V.d[vy * V.w + vx] : 0;
            if (!(val === 255 || (val === 128 && c.road.b))) continue;
          }
          const h = c.dir > 0 ? ang : ang + Math.PI;
          const off = c.road.o ? 0 : lane;
          const sx = (x - Math.sin(h) * off) * z + ox, sy = (y + Math.cos(h) * off) * z + oy; // right-hand side (y is down)
          const L = c.len * z, Wd = Math.max(1.9 / MPP * z, 1.2);
          g.save(); g.translate(sx, sy); g.rotate(h);
          g.fillStyle = "rgba(0,0,0,.28)"; g.fillRect(-L / 2 + 1, -Wd / 2 + 1.5, L, Wd);
          g.fillStyle = c.colour; g.fillRect(-L / 2, -Wd / 2, L, Wd);
          if (L > 8) { g.fillStyle = "rgba(255,255,255,.45)"; g.fillRect(-L * 0.12, -Wd / 2 + 1, L * 0.3, Wd - 2); }
          if (night > 0.05) {
            // headlight beam ahead, red tail lights behind
            g.globalAlpha = night;
            const grd = g.createLinearGradient(L / 2, 0, L / 2 + L * 2.2, 0);
            grd.addColorStop(0, "rgba(255,236,190,.55)"); grd.addColorStop(1, "rgba(255,236,190,0)");
            g.fillStyle = grd;
            g.beginPath(); g.moveTo(L / 2, -Wd / 2); g.lineTo(L / 2 + L * 2.2, -Wd * 1.3); g.lineTo(L / 2 + L * 2.2, Wd * 1.3); g.lineTo(L / 2, Wd / 2); g.fill();
            g.fillStyle = "#ff2a20";
            g.fillRect(-L / 2 - 1, -Wd / 2, 2, Wd * 0.3); g.fillRect(-L / 2 - 1, Wd / 2 - Wd * 0.3, 2, Wd * 0.3);
            g.globalAlpha = 1;
          }
          g.restore();
        }
      }
    };
    raf = requestAnimationFrame(loop);
    // Also redraw inside the map's own redraw, so cars and street lines never trail the map while it moves.
    const off = map.current?.onFrame(() => draw(performance.now()));
    return () => { cancelAnimationFrame(raf); off?.(); };
  }, [map]);

  return <canvas ref={canvas} className="overlay" aria-hidden="true" />;
}
