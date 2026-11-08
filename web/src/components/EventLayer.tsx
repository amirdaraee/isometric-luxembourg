import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import type { Season } from "../scene";
import { asset } from "../config";
import { on } from "../features";
import { canvasDpr, subscribe } from "../frame";
import { CONSTITUTION_WHEEL, drawWheel, wheelAngle } from "./ferrisWheel";
import type { WheelSpec } from "./ferrisWheel";
import { drawEffects, type EventEffects } from "./eventEffects";
import { RULES, type EventId } from "../calendar";
import { sunTimes } from "../scene";

export interface EventLayerProps {
  map: RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
  /** hour of the day shown, 0 to 24 */
  hour: number;
  season: Season;
  /** "today" (the real date, or ?date= in tests) */
  date: Date;
  /** ids of the events shown now ("winterlights", ...) */
  active?: string[];
  /** the event picked in the Events menu (a preview: its effects play whatever the day), or null */
  picked?: string | null;
}

/** web/public/events/sprites.json, from pipeline/events/build_event_sprites.py */
interface RideSprite { frame: [number, number]; anchor: [number, number]; frames: number; day: [number, number][]; night: [number, number][] }
interface SpriteSheet { mpp: number; map_mpp: number; image: string; rides: Record<string, RideSprite> }
/** A ride placed on the map (events/<event>/rides.json): ground anchor in map px, frames per second. A "wheel" is
 * drawn live (ferrisWheel.ts), with optional changes to the default wheel. */
interface Ride {
  site: string; kind: string; x: number; y: number; fps?: number; wheel?: Partial<WheelSpec>;
  front?: { day: string; night: string; x0: number; y0: number; w: number; h: number };
}
/** Warm points of light of a site (events/<event>/lights.json): [x, y, size] in map px. */
interface Lights { site: string; pts: [number, number, number][] }

interface Loaded {
  sheet: SpriteSheet; atlas: HTMLImageElement; rides: Ride[]; lights: Lights[];
  fronts: Map<string, HTMLImageElement>; glow: HTMLCanvasElement;
}

const MIN_ZOOM = 0.25;   // further out the rides would be a few pixels: draw nothing
const FX_MIN_ZOOM = 0.08; // fireworks and bonfires still read from far out
const EVENT_DIRS: Record<string, string> = { winterlights: "xmas", newYear: "xmas" };

/** web/public/events/lift.json (pipeline/events/lift_model.py sprites): the Pfaffenthal lift's cabin. */
interface LiftCell { frame: [number, number]; anchor: [number, number]; day: [number, number]; night: [number, number] }
interface LiftMeta {
  image: string; mpp: number; map_mpp: number; cabin: LiftCell; front: LiftCell; tower?: LiftCell; structure?: boolean;
  bottom: [number, number]; rise: number; ride: number; wait: [number, number]; hours: [number, number];
}
interface Lift { meta: LiftMeta; atlas: HTMLImageElement }
const LIFT_MIN_ZOOM = 0.2;

/** How far up the shaft the cabin is (0 bottom .. 1 top) at a time: wait at the bottom, ride up, wait at the top,
 * ride down, eased at both ends of a ride. Outside the opening hours it waits at the bottom. */
export function liftPosition(m: Pick<LiftMeta, "ride" | "wait" | "hours">, sec: number, hour: number): number {
  const [h0, h1] = m.hours;
  const open = hour >= h0 || hour + 24 < h1;
  if (!open) return 0;
  const [wb, wt] = m.wait, T = 2 * m.ride + wb + wt;
  const t = ((sec % T) + T) % T;
  const ease = (u: number) => 0.5 - 0.5 * Math.cos(Math.PI * u);
  if (t < wb) return 0;
  if (t < wb + m.ride) return ease((t - wb) / m.ride);
  if (t < wb + m.ride + wt) return 1;
  return 1 - ease((t - wb - m.ride - wt) / m.ride);
}

/** web/public/events/events.json (pipeline/events/event_patch.py manifest), loaded once. */
let manifest: Promise<Record<string, EventEffects>> | null = null;
export function eventManifest(): Promise<Record<string, EventEffects>> {
  manifest ??= fetch(asset("/events/events.json")).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  return manifest;
}

/** Day of the event shown (0 = first) and days left (0 = last), or null if the date is not in it. */
function dayIndex(id: string, d: Date): [number, number] | null {
  const rule = RULES[id as EventId];
  if (!rule) return null;
  const day = (x: Date) => Math.round(+new Date(x.getFullYear(), x.getMonth(), x.getDate()) / 864e5);
  for (const y of [d.getFullYear() - 1, d.getFullYear()]) {
    const r = rule(y);
    if (r && day(d) >= day(r[0]) && day(d) <= day(r[1])) return [day(d) - day(r[0]), day(r[1]) - day(d)];
  }
  return null;
}

function img(url: string): Promise<HTMLImageElement> {
  return new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = url; });
}

/** A soft warm dot, drawn with "lighter" for twinkling lights. */
function glowSprite(): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = 32;
  const g = c.getContext("2d")!;
  const r = g.createRadialGradient(16, 16, 0, 16, 16, 16);
  r.addColorStop(0, "rgba(255,236,190,1)");
  r.addColorStop(0.25, "rgba(255,196,110,.55)");
  r.addColorStop(1, "rgba(255,160,60,0)");
  g.fillStyle = r;
  g.fillRect(0, 0, 32, 32);
  return c;
}

async function load(dir: string): Promise<Loaded | null> {
  try {
    const [sheet, rides, lights] = await Promise.all([
      fetch(asset("/events/sprites.json")).then((r) => r.json() as Promise<SpriteSheet>),
      fetch(asset(`/events/${dir}/rides.json`)).then((r) => r.json() as Promise<Ride[]>),
      fetch(asset(`/events/${dir}/lights.json`)).then((r) => (r.ok ? r.json() : [])).catch(() => []) as Promise<Lights[]>,
    ]);
    const atlas = await img(asset(`/events/${sheet.image}`));
    const fronts = new Map<string, HTMLImageElement>();
    await Promise.all(rides.flatMap((r) => (r.front ? [r.front.day, r.front.night] : [])).map(async (u) => {
      fronts.set(u, await img(asset(`/events/${dir}/${u}`)));
    }));
    return { sheet, atlas, rides, lights, fronts, glow: glowSprite() };
  } catch {
    return null;
  }
}

/** Small per-point numbers that stay the same from frame to frame. */
function hash(i: number): number {
  const s = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
}

/**
 * Live effects of the events shown: the turning parts of rides (the Ferris wheel, the carousel's horses, the
 * pyramid's blades) over the still event patches, and lights that twinkle slowly at night. Ride positions come from
 * the clock, so every visitor sees the same thing. With reduced motion asked for, rides stand still and lights
 * stay steady.
 */
export function EventLayer({ map, night, hour, date, active = [], picked = null }: EventLayerProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const data = useRef<Record<string, Loaded | null>>({});
  const fx = useRef<Record<string, EventEffects>>({});
  const glowRef = useRef<HTMLCanvasElement | null>(null);
  const flags = useRef({ night, active, hour, date, picked });
  flags.current = { night, active, hour, date, picked };
  // events with live effects: every event but Christmas needs the events switch and its own
  const withFx = active.filter((a) => a === "winterlights" || (on("events") && on(a as never)));
  const dirs = on("eventRides") ? [...new Set(active.map((a) => EVENT_DIRS[a]).filter(Boolean))] : [];
  const key = [...withFx, "|", ...dirs, ...(on("liftCabin") ? ["lift"] : [])].join(",");
  const lift = useRef<Lift | null>(null);
  useEffect(() => {
    if (!on("liftCabin")) return;
    fetch(asset("/events/lift.json")).then((r) => r.json() as Promise<LiftMeta>)
      .then(async (meta) => { lift.current = { meta, atlas: await img(asset(`/events/${meta.image}`)) }; })
      .catch(() => {});
  }, []);

  useEffect(() => {
    for (const dir of dirs) {
      if (dir in data.current) continue;
      data.current[dir] = null;
      load(dir).then((d) => { data.current[dir] = d; });
    }
    if (withFx.length) eventManifest().then((m) => { fx.current = m; });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (key === "|") {
      const cv = canvas.current;
      cv?.getContext("2d")?.clearRect(0, 0, cv.width, cv.height);
      return;
    }
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const draw = () => {
      const cv = canvas.current, v = map.current?.getView();
      if (!cv || !v) return;
      // at most 2 device pixels per CSS pixel (1 on the lowest quality tier), like the other layers
      const dpr = canvasDpr(2), W = window.innerWidth, H = window.innerHeight;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
      const g = cv.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      if (v.z < FX_MIN_ZOOM) return;
      const z = v.z, ox = W / 2 - v.x * z, oy = H / 2 - v.y * z;
      const n = flags.current.night;
      const sec = still ? 0 : Date.now() / 1000;
      glowRef.current ??= glowSprite();
      const f = flags.current;
      // the Pfaffenthal lift: the structure while the art lacks it, the cabin, then the shaft's front frame over it
      const L = lift.current;
      if (L && z >= LIFT_MIN_ZOOM) {
        const m = L.meta, k = (m.mpp / m.map_mpp) * z;
        const bx = m.bottom[0] * z + ox, by = m.bottom[1] * z + oy;
        if (bx > -300 && bx < W + 300 && by > -200 && by < H + 600) {
          const cell = (c: LiftCell, dy: number) => {
            for (const [xy, a] of [[c.day, 1], [c.night, n]] as const) {
              if (a < 0.01) continue;
              g.globalAlpha = a;
              g.drawImage(L.atlas, xy[0], xy[1], c.frame[0], c.frame[1], bx - c.anchor[0] * k, by + dy - c.anchor[1] * k, c.frame[0] * k, c.frame[1] * k);
            }
            g.globalAlpha = 1;
          };
          if (m.structure && m.tower) cell(m.tower, 0);
          cell(m.cabin, -m.rise * z * liftPosition(m, sec, f.hour));
          cell(m.front, 0);
        }
      }
      for (const id of f.active) {
        const e = fx.current[id];
        if (!e || (id !== "winterlights" && !(on("events") && on(id as never)))) continue;
        const effects = on("fireworks") ? e : { ...e, fireworks: undefined };
        drawEffects(g, effects, {
          z, ox, oy, W, H, sec: still ? 1000 : sec, hour: f.hour, night: n, sunset: sunTimes(f.date)[1],
          dayIndex: f.picked === id ? null : dayIndex(id, f.date), glow: glowRef.current, still,
        });
      }
      if (v.z < MIN_ZOOM) return;
      g.imageSmoothingEnabled = true;
      g.imageSmoothingQuality = "high";
      for (const dir of new Set(flags.current.active.map((a) => EVENT_DIRS[a]).filter(Boolean))) {
        const d = data.current[dir];
        if (!d) continue;
        const k = (d.sheet.mpp / d.sheet.map_mpp) * z;   // sprite px -> screen px
        for (const r of d.rides) {
          if (r.kind === "wheel") {
            const spec = { ...CONSTITUTION_WHEEL, ...r.wheel };
            const sx = r.x * z + ox, sy = r.y * z + oy;
            const half = ((spec.radius + 4) / 0.25) * z, tall = ((spec.hub + spec.radius + 2) * 0.866 / 0.25) * z;
            if (sx - half > W || sx + half < 0 || sy - tall > H || sy - tall * 0.2 - half > H || sy + half * 0.5 < 0) continue;
            drawWheel(g, spec, { sx, sy, z, night: n, theta: still ? 0.3 : wheelAngle(spec, sec), sec, glow: d.glow });
            continue;
          }
          const s = d.sheet.rides[r.kind];
          if (!s) continue;
          const [fw, fh] = s.frame, [ax, ay] = s.anchor;
          const sx = r.x * z + ox - ax * k, sy = r.y * z + oy - ay * k;
          if (sx > W || sy > H || sx + fw * k < 0 || sy + fh * k < 0) continue;
          // between two frames, the next one fades in over the current one, so even a slow wheel turns smoothly
          const pos = sec * (r.fps ?? 6), f = Math.floor(pos) % s.frames, f2 = (f + 1) % s.frames, frac = still ? 0 : pos - Math.floor(pos);
          for (const [cells, a] of [[s.day, 1 - n], [s.night, n]] as const) {
            if (a < 0.01) continue;
            g.globalAlpha = a;
            g.drawImage(d.atlas, cells[f][0], cells[f][1], fw, fh, sx, sy, fw * k, fh * k);
            if (frac > 0.02) {
              g.globalAlpha = a * frac;
              g.drawImage(d.atlas, cells[f2][0], cells[f2][1], fw, fh, sx, sy, fw * k, fh * k);
            }
          }
          if (r.front) {
            const fr = r.front;
            const fx = fr.x0 * z + ox, fy = fr.y0 * z + oy;
            // the day front stays on under the night one, as the patches do, so nothing shows through at dusk
            const dayImg = d.fronts.get(fr.day), nightImg = d.fronts.get(fr.night);
            g.globalAlpha = 1;
            if (dayImg) g.drawImage(dayImg, fx, fy, fr.w * z, fr.h * z);
            if (nightImg && n > 0.01) { g.globalAlpha = n; g.drawImage(nightImg, fx, fy, fr.w * z, fr.h * z); }
          }
        }
        if (n > 0.02 && d.lights.length) {
          g.globalCompositeOperation = "lighter";
          let i = 0;
          for (const site of d.lights) {
            for (const [x, y, size] of site.pts) {
              i++;
              const px = x * z + ox, py = y * z + oy;
              if (px < -20 || py < -20 || px > W + 20 || py > H + 20) continue;
              // slow, gentle twinkle: each light has its own speed and phase; never a hard flash
              const tw = still ? 0.7 : 0.55 + 0.45 * Math.sin(sec * (0.8 + 1.6 * hash(i)) + 6.28 * hash(i + 99));
              const rr = Math.max(2.5, size * 2.2 * z);
              g.globalAlpha = n * 0.55 * tw;
              g.drawImage(d.glow, px - rr, py - rr, rr * 2, rr * 2);
            }
          }
          g.globalCompositeOperation = "source-over";
        }
      }
      g.globalAlpha = 1;
    };
    // Steady 24 fps for the rides and lights (slow movements), and on every frame the map moves: the frame clock
    // then calls it straight after the map's own redraw, so the rides never trail the map (and are drawn once).
    // With reduced motion, only when the map moves.
    const stop = subscribe(() => draw(), still ? { still: true, name: "events" } : { fps: 24, name: "events" });
    return () => { stop(); };
  }, [map, key]);

  return <canvas ref={canvas} className="overlay" aria-hidden="true" />;
}
