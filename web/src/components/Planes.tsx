import { useEffect, useRef, type RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import { asset } from "../config";
import { canvasDpr, subscribe } from "../frame";
import { weather } from "../weather";
import { drawVehicle, headingIndex, loadSprites, type Sprites, type SpriteType } from "./sprites";
import { dayPlan, planesAt, runwayFor, shadowOffset, UP_PX_PER_M, type FlightsData, type Movement, type PlaneNow } from "../sky/flights";

/**
 * Cargolux and Luxair aircraft over the city (switch planes), drawn by Sky.tsx above the clouds and below the pins.
 * The day's movements come from src/sky/flights.ts (seeded from the date), the tracks from
 * public/data/flights.json, the sprites from public/sprites/planes.json (pipeline/build_plane_sprites.py). The
 * runway follows the wind (src/weather.ts): 24 as a rule, 06 with an east wind, when arrivals come in low over the
 * city from the west. Time runs on from the hour shown, so every visitor sees the same aircraft at the same moment.
 * At most three are drawn. Below 400 m a faint shadow falls on the ground, cast by the map's sun. At night they show
 * navigation lights, a red beacon and white strobes, and landing lights on final and just after take-off; with
 * reduced motion nothing flashes, and the aircraft move only when the hour shown changes.
 */
export interface PlanesProps {
  map: RefObject<MapHandle>;
  night: number;
  hour: number;
  date: Date;
}

const MAX_SHOWN = 3;
/** Zoomed far out, aircraft are drawn as at this zoom (larger than life), so that they still read as aircraft. */
const MIN_DRAW_ZOOM = 0.28;
const LIGHT: Record<string, [number, number, number]> = {
  red: [255, 64, 52], green: [70, 255, 130], white: [255, 250, 236], beacon: [255, 40, 32], strobe: [255, 255, 255],
  landing: [255, 246, 214],
};

function dayKey(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function Planes({ map, night, hour, date }: PlanesProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const props = useRef({ night, hour, date, at: performance.now() });
  // the clock runs on from the moment the hour shown last changed
  if (props.current.hour !== hour) props.current.at = performance.now();
  props.current = { ...props.current, night, hour, date };
  const wake = useRef<() => void>(() => {});
  useEffect(() => wake.current(), [night, hour, date]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const g = cv.getContext("2d")!;
    const still = matchMedia("(prefers-reduced-motion: reduce)");
    let spr: Sprites | null = null, data: FlightsData | null = null;
    let alive = true;
    loadSprites("/sprites/planes.json").then((s) => { if (alive) spr = s; }).catch(() => {});
    fetch(asset("/data/flights.json")).then((r) => r.json()).then((d: FlightsData) => { if (alive) data = d; }).catch(() => {});
    let plans: { key: string; today: Movement[]; yesterday: Movement[] } | null = null;
    let clear = true;

    const draw = (t: number) => {
      const W = window.innerWidth, H = window.innerHeight;
      const dpr = canvasDpr(1.5);
      const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; clear = true; }
      const v = map.current?.getView();
      if (!spr || !data || !v) return;
      const { night, hour, date, at } = props.current;
      const key = dayKey(date);
      if (plans?.key !== key) {
        const y = new Date(date.getTime() - 86400000);
        plans = { key, today: dayPlan(key), yesterday: dayPlan(dayKey(y)) };
      }
      const secs = hour * 3600 + (still.matches ? 0 : (t - at) / 1000);
      const rwy = runwayFor(weather().wind);
      const z = v.z, ox = W / 2 - v.x * z, oy = H / 2 - v.y * z;
      // on screen (with a margin for the sprite), nearest the middle first
      const shown: { p: PlaneNow; sx: number; sy: number }[] = [];
      for (const p of planesAt(plans.today, data, secs, rwy, plans.yesterday)) {
        if (p.h < 2) continue;                  // the runway is beyond the painted map
        const sx = p.gx * z + ox, sy = (p.gy - p.h * UP_PX_PER_M) * z + oy;
        const m = 120 * Math.max(z, MIN_DRAW_ZOOM) + 40;
        if (sx < -m || sx > W + m || sy < -m || sy > H + m) continue;
        shown.push({ p, sx, sy });
      }
      shown.sort((a, b) => Math.hypot(a.sx - W / 2, a.sy - H / 2) - Math.hypot(b.sx - W / 2, b.sy - H / 2));
      shown.length = Math.min(shown.length, MAX_SHOWN);
      if (!shown.length) {
        if (!clear) { g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, bw, bh); clear = true; }
        return;
      }
      clear = false;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      // farther (higher up the screen) first
      shown.sort((a, b) => a.sy - b.sy);
      const s = spr;
      const dz = Math.max(z, MIN_DRAW_ZOOM);
      for (const { p } of shown) {
        if (p.h >= 400) continue;
        const [dx, dy] = shadowOffset(p.h);
        g.globalAlpha = (1 - p.h / 400) * (1 - 0.7 * night);
        drawVehicle(g, s, p.type, 2, (p.gx + dx) * z + ox, (p.gy + dy) * z + oy, p.heading, dz);
      }
      g.globalAlpha = 1;
      const dim = night > 0.05 ? `brightness(${(1 - 0.45 * night).toFixed(2)})` : "none";
      for (const { p, sx, sy } of shown) {
        g.filter = dim;
        drawVehicle(g, s, p.type, p.climb ? 1 : 0, sx, sy, p.heading, dz);
        g.filter = "none";
        if (night > 0.2) lights(g, s.types[p.type], s, p, sx, sy, dz, night, still.matches ? -1 : t);
      }
    };

    const sub = subscribe((t, _dt, moved) => {
      if (!moved && !clear && still.matches) return;
      draw(t);
    }, { fps: 30, name: "planes" });
    wake.current = () => { clear = false; sub.wake(); };
    return () => { alive = false; sub(); };
  }, [map]);

  return <canvas ref={canvas} aria-hidden="true"
    style={{ position: "fixed", inset: 0, width: "100vw", height: "100vh", pointerEvents: "none", zIndex: 1 }} />;
}

/** The lights of one aircraft drawn at (sx, sy): soft dots added on top. t < 0: nothing flashes (reduced motion). */
function lights(g: CanvasRenderingContext2D, ty: SpriteType & { lights?: Record<string, [string, number, number][][]> },
  s: Sprites, p: PlaneNow, sx: number, sy: number, z: number, night: number, t: number) {
  const list = ty.lights?.[p.climb ? "climb" : "level"]?.[headingIndex(s, p.heading)];
  if (!list) return;
  const k = (z * s.mpp) / s.map_mpp;
  const x0 = sx - ty.anchor[0] * k, y0 = sy - ty.anchor[1] * k;
  const sec = t / 1000;
  const beacon = t < 0 ? 0.6 : (sec + p.id * 0.37) % 1.1 < 0.12 ? 1 : 0.15;
  const ph = (sec + p.id * 0.53) % 1.3;
  const strobe = t < 0 ? 0 : ph < 0.06 || (ph > 0.16 && ph < 0.22) ? 1 : 0;
  const landing = (p.kind === "arr" && p.h < 800) || (p.kind === "dep" && p.h < 450) ? 1 : 0;
  const prev = g.globalCompositeOperation;
  g.globalCompositeOperation = "lighter";
  const base = Math.max(3, 5 * k);
  for (const [kind, lx, ly] of list) {
    const a = kind === "beacon" ? beacon : kind === "strobe" ? strobe : kind === "landing" ? landing : 0.9;
    if (a <= 0.01) continue;
    const r = kind === "landing" ? base * 3 : kind === "strobe" ? base * 2.2 : base;
    const [cr, cg, cb] = LIGHT[kind] ?? LIGHT.white;
    const x = x0 + lx * k, y = y0 + ly * k;
    const gr = g.createRadialGradient(x, y, 0, x, y, r);
    gr.addColorStop(0, `rgba(${cr},${cg},${cb},${(a * night).toFixed(3)})`);
    gr.addColorStop(0.35, `rgba(${cr},${cg},${cb},${(a * night * 0.45).toFixed(3)})`);
    gr.addColorStop(1, `rgba(${cr},${cg},${cb},0)`);
    g.fillStyle = gr;
    g.fillRect(x - r, y - r, 2 * r, 2 * r);
  }
  g.globalCompositeOperation = prev;
}
