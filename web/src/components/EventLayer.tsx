import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import type { Season } from "../scene";
import { asset } from "../config";
import { on } from "../features";
import { subscribe } from "../frame";

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
}

/** web/public/events/sprites.json, from pipeline/events/build_event_sprites.py */
interface RideSprite { frame: [number, number]; anchor: [number, number]; frames: number; day: [number, number][]; night: [number, number][] }
interface SpriteSheet { mpp: number; map_mpp: number; image: string; rides: Record<string, RideSprite> }
/** A ride placed on the map (events/<event>/rides.json): ground anchor in map px, frames per second. */
interface Ride { site: string; kind: string; x: number; y: number; fps: number; front?: { day: string; night: string; x0: number; y0: number; w: number; h: number } }
/** Warm points of light of a site (events/<event>/lights.json): [x, y, size] in map px. */
interface Lights { site: string; pts: [number, number, number][] }

interface Loaded {
  sheet: SpriteSheet; atlas: HTMLImageElement; rides: Ride[]; lights: Lights[];
  fronts: Map<string, HTMLImageElement>; glow: HTMLCanvasElement;
}

const MIN_ZOOM = 0.25;   // further out the rides would be a few pixels: draw nothing
const EVENT_DIRS: Record<string, string> = { winterlights: "xmas" };

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
export function EventLayer({ map, night, active = [] }: EventLayerProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const data = useRef<Record<string, Loaded | null>>({});
  const flags = useRef({ night, active });
  flags.current = { night, active };
  const want = on("eventRides") ? active.filter((a) => EVENT_DIRS[a]) : [];
  const key = want.join(",");

  useEffect(() => {
    for (const id of key ? key.split(",") : []) {
      if (id in data.current) continue;
      data.current[id] = null;
      load(EVENT_DIRS[id]).then((d) => { data.current[id] = d; });
    }
  }, [key]);

  useEffect(() => {
    if (!key) {
      const cv = canvas.current;
      cv?.getContext("2d")?.clearRect(0, 0, cv.width, cv.height);
      return;
    }
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const draw = () => {
      const cv = canvas.current, v = map.current?.getView();
      if (!cv || !v) return;
      const dpr = window.devicePixelRatio || 1, W = window.innerWidth, H = window.innerHeight;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
      const g = cv.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      if (v.z < MIN_ZOOM) return;
      const z = v.z, ox = W / 2 - v.x * z, oy = H / 2 - v.y * z;
      const n = flags.current.night;
      const sec = still ? 0 : Date.now() / 1000;
      g.imageSmoothingEnabled = true;
      g.imageSmoothingQuality = "high";
      for (const id of flags.current.active) {
        const d = data.current[id];
        if (!d) continue;
        const k = (d.sheet.mpp / d.sheet.map_mpp) * z;   // sprite px -> screen px
        for (const r of d.rides) {
          const s = d.sheet.rides[r.kind];
          if (!s) continue;
          const [fw, fh] = s.frame, [ax, ay] = s.anchor;
          const sx = r.x * z + ox - ax * k, sy = r.y * z + oy - ay * k;
          if (sx > W || sy > H || sx + fw * k < 0 || sy + fh * k < 0) continue;
          // between two frames, the next one fades in over the current one, so even a slow wheel turns smoothly
          const pos = sec * r.fps, f = Math.floor(pos) % s.frames, f2 = (f + 1) % s.frames, frac = still ? 0 : pos - Math.floor(pos);
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
    // Steady 24 fps for the rides and lights (slow movements), and also inside the map's own redraw, so the rides
    // never trail the map while it moves.
    const stop = still ? () => {} : subscribe(() => draw(), { fps: 24 });
    const off = map.current?.onFrame(() => draw());
    draw();
    return () => { stop(); off?.(); };
  }, [map, key]);

  return <canvas ref={canvas} className="overlay" aria-hidden="true" />;
}
