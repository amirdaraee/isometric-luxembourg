import { useEffect, useRef, type RefObject } from "react";
import type { MapHandle, MapMeta } from "./IsometricMap";
import type { Season } from "../scene";
import { on } from "../features";
import { tilesBase } from "../config";
import { canvasDpr, subscribe } from "../frame";
import { currentAmounts, onWeather } from "../weather";
import { groundToScreen } from "../sky/weatherCore";
import { Fog } from "./Fog";
import { Planes } from "./Planes";

export interface SkyProps {
  map: RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
  /** hour of the day shown, 0 to 24 */
  hour: number;
  season: Season;
  /** "today" (the real date, or ?date= in tests) */
  date: Date;
}

/**
 * The sky over the map: the weather (src/weather.ts) and the aircraft. In order, from the map up:
 *  - valley fog and haze (Fog.tsx, switch fog);
 *  - a wash that dims and cools the map under an overcast or rainy sky (a plain coloured layer, not a CSS filter);
 *  - the aircraft (Planes.tsx, switch planes);
 *  - rain and snow on one 2D canvas: rain as streaks slanted by the wind (projected like the map: a west wind
 *    drives them to the right), with small splash rings on the painted ground when zoomed in and, at night, a few
 *    streaks catching warm lamp light; snow as flakes drifting with the wind;
 *  - lightning in a storm: two short brightenings of 80 ms, every 8 to 25 s (never more than three flashes in any
 *    second, WCAG 2.3.1), and none at all with reduced motion.
 * With reduced motion the rain and snow stand still. Snow falls when the weather says snow or, with the weather
 * switched off, in winter with the snow switch on.
 */
/** How much snow falls: what the weather says, with the weather switched on; with it off, winter with the snow switch on. */
function snowAmount(weatherSnow: number, season: Season): number {
  if (on("weather")) return weatherSnow;
  return season === "winter" && on("snow") ? 0.5 : 0;
}

export function Sky({ map, night, hour, season, date }: SkyProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const wash = useRef<HTMLDivElement>(null);
  const flash = useRef<HTMLDivElement>(null);
  const props = useRef({ night, season });
  props.current = { night, season };
  const redrawRef = useRef<() => void>(() => {});
  useEffect(() => redrawRef.current(), [night, season]);

  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const g = cv.getContext("2d")!;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let painted: MapMeta["painted"] = [];
    fetch(`${tilesBase}/meta.json`).then((r) => r.json()).then((m: MapMeta) => { painted = m.painted ?? []; }).catch(() => {});

    // Fixed random numbers per drop, so the pattern is steady from frame to frame.
    const N = 900;
    const seed = new Float32Array(N * 4);
    let s = 12345;
    for (let i = 0; i < seed.length; i++) { s = (s * 48271) % 2147483647; seed[i] = s / 2147483647; }

    let clear = true, t0 = performance.now(), nextFlash = 0, flashAt = -1;
    // opacity written only when it changes (to the third decimal), so a still wash costs no style work per frame
    const shown = new WeakMap<HTMLElement, string>();
    const setOpacity = (el: HTMLElement, o: number) => {
      const s = o.toFixed(3);
      if (shown.get(el) !== s) { shown.set(el, s); el.style.opacity = s; }
    };
    const nextGap = () => 8000 + Math.random() * 17000;

    const draw = (t: number) => {
      const a = currentAmounts();
      const { night, season } = props.current;
      const snow = snowAmount(a.snow, season);
      const rain = a.rain;

      // the overcast wash: a little darker and cooler
      if (wash.current) {
        const o = (a.overcast * 0.2 + rain * 0.1 + a.storm * 0.08) * (1 - 0.5 * night);
        setOpacity(wash.current, o);
      }

      // lightning
      if (flash.current) {
        let f = 0;
        if (a.storm > 0.05 && !still) {
          if (!nextFlash) nextFlash = t + 2000 + Math.random() * 6000;
          if (t >= nextFlash) { flashAt = t; nextFlash = t + nextGap(); }
          const e = t - flashAt;
          // two pulses: 0-80 ms and 200-280 ms
          if (flashAt >= 0 && (e < 80 || (e >= 200 && e < 280))) f = (e < 80 ? 1 : 0.7) * a.storm;
        }
        setOpacity(flash.current, f * (0.22 + 0.2 * night));
      }

      const W = window.innerWidth, H = window.innerHeight;
      // thin soft streaks: 1.25 device pixels per CSS pixel are enough
      const dpr = canvasDpr(1.25);
      const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; clear = true; }
      if (rain < 0.005 && snow < 0.005) {
        if (!clear) { g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, bw, bh); clear = true; }
        return;
      }
      clear = false;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const v = map.current?.getView();
      const z = v?.z ?? 0.5;
      const time = still ? 0 : (t - t0) / 1000;

      if (rain > 0.005) {
        // Direction on screen: falling 9 m/s (straight down the screen) plus the wind, damped a little.
        const [gx, gy] = groundToScreen(a.windE * 0.6, a.windN * 0.6);
        const fall = 9 * 3.46;
        const len0 = Math.hypot(gx, gy + fall);
        const dx = gx / len0, dy = (gy + fall) / len0;
        const n = Math.min(N, Math.round(rain * W * H / 1000));
        const speed = 950;
        const span = W + 80, spanY = H + 80;
        // Two depths: far streaks fainter and shorter, near ones longer. Each streak is drawn pale with a faint dark
        // edge beside it, so it reads over pale stone as well as over dark roofs and the night.
        for (const near of [false, true]) {
          const path = new Path2D(), warmPath = new Path2D();
          for (let i = near ? 1 : 0; i < n; i += 2) {
            const r0 = seed[i * 4], r1 = seed[i * 4 + 1], r2 = seed[i * 4 + 2], r3 = seed[i * 4 + 3];
            const sp = speed * (near ? 1.15 : 0.8) * (0.85 + 0.3 * r2);
            const L = (near ? 24 : 14) * (0.7 + 0.6 * r3);
            let x = r0 * span + dx * sp * time, y = r1 * spanY + dy * sp * time;
            x = ((x % span) + span) % span - 40; y = ((y % spanY) + spanY) % spanY - 40;
            const into = night > 0.3 && r3 > 0.86 ? warmPath : path;
            into.moveTo(x, y); into.lineTo(x - dx * L, y - dy * L);
          }
          const lw = near ? 1.5 : 1;
          g.lineCap = "round";
          g.save();
          g.translate(1, 0.8);
          g.lineWidth = lw;
          g.strokeStyle = `rgba(20,32,55,${(near ? 0.22 : 0.14) * (1 - 0.6 * night)})`;
          g.stroke(path);
          g.restore();
          g.lineWidth = lw;
          g.strokeStyle = night > 0.5 ? `rgba(180,200,232,${near ? 0.55 : 0.36})` : `rgba(226,236,250,${near ? 0.72 : 0.48})`;
          g.stroke(path);
          if (night > 0.3) {
            g.strokeStyle = `rgba(255,196,120,${0.6 * night})`;
            g.stroke(warmPath);
          }
        }
        // splashes on the painted ground, when close enough to see them
        if (z >= 0.6 && map.current) {
          const m = map.current;
          const cnt = Math.round(90 * rain);
          g.lineWidth = 1.2;
          g.strokeStyle = night > 0.5 ? "rgba(190,205,230,.55)" : "rgba(240,246,252,.75)";
          g.beginPath();
          for (let i = 0; i < cnt; i++) {
            const cyc = 0.45 + 0.2 * seed[i * 4 + 3];
            const ph = time / cyc + seed[i * 4 + 2];
            const k = Math.floor(ph), f = ph - k;
            const hx = Math.sin((i + 1) * 12.9898 + k * 78.233) * 43758.5453, hy = Math.sin((i + 1) * 39.346 + k * 11.135) * 24634.6345;
            const x = (hx - Math.floor(hx)) * W, y = (hy - Math.floor(hy)) * H;
            const p = m.toMap(x, y);
            if (!p || !painted?.some((r) => p.x >= r.x0 && p.x <= r.x0 + r.w && p.y >= r.y0 && p.y <= r.y0 + r.h)) continue;
            const rr = (1 + 3.5 * f) * Math.max(1, z);
            g.moveTo(x + rr, y);
            g.ellipse(x, y, rr, rr * 0.45, 0, 0, Math.PI * 2);
          }
          g.stroke();
        }
      }

      if (snow > 0.005) {
        const n = Math.min(N, Math.round(snow * W * H / 1800));
        const [gx] = groundToScreen(a.windE * 0.5, a.windN * 0.5);
        const span = W + 40, spanY = H + 40;
        const flakes = new Path2D();
        for (let i = 0; i < n; i++) {
          const r0 = seed[i * 4], r1 = seed[i * 4 + 1], r2 = seed[i * 4 + 2], r3 = seed[i * 4 + 3];
          const fallV = 26 + 30 * r2;
          let x = r0 * span + (gx * 0.6 + 6) * time + Math.sin(time * 0.7 + i) * 14;
          let y = r1 * spanY + fallV * time;
          x = ((x % span) + span) % span - 20; y = ((y % spanY) + spanY) % spanY - 20;
          const r = 1 + r3 * 1.9;
          flakes.moveTo(x + r, y);
          flakes.arc(x, y, r, 0, Math.PI * 2);
        }
        // a faint blue-grey shadow under each flake, so it shows over the white winter roofs too
        g.save();
        g.translate(0.8, 1);
        g.fillStyle = `rgba(40,58,90,${0.3 * (1 - 0.5 * night)})`;
        g.fill(flakes);
        g.restore();
        g.fillStyle = night > 0.5 ? "rgba(225,232,245,.85)" : "rgba(255,255,255,.95)";
        g.fill(flakes);
      }
    };

    // Every frame while anything falls or flashes; otherwise only when the weather changes. With reduced motion,
    // only when the map moves or the weather changes.
    let dirty = true;
    const sub = subscribe((t, _dt, moved) => {
      const a = currentAmounts();
      const falling = a.rain > 0.005 || a.storm > 0.005 || snowAmount(a.snow, props.current.season) > 0.005;
      if (!(falling && !still) && !moved && !dirty) return;
      dirty = false;
      draw(t);
    }, { name: "sky" });
    const redraw = () => { dirty = true; sub.wake(); };
    redrawRef.current = redraw;
    const offW = onWeather(redraw);
    // a blend of the weather lasts up to 20 s: draw through it even when nothing falls
    const blend = setInterval(redraw, 1000);
    t0 = performance.now();
    return () => { sub(); offW(); clearInterval(blend); };
  }, [map]);

  return (
    <>
      {on("weather") && on("fog") && <Fog map={map} night={night} />}
      {on("weather") && <div ref={wash} aria-hidden="true"
        style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1, background: "rgb(52,64,86)", opacity: 0 }} />}
      {on("planes") && <Planes map={map} night={night} hour={hour} date={date} />}
      {(on("weather") || on("snow")) && <canvas ref={canvas} aria-hidden="true"
        style={{ position: "fixed", inset: 0, width: "100vw", height: "100vh", pointerEvents: "none", zIndex: 1 }} />}
      {on("weather") && <div ref={flash} aria-hidden="true"
        style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 1, background: "#eef3ff", opacity: 0 }} />}
    </>
  );
}
