/**
 * Famous statues and monuments (switch `statues`): small ink drawings placed on their plinths over the painted map,
 * which leaves them out or too small (pipeline/build_statues.py writes /data/statues.json and /statues/*.webp).
 *
 * Own canvas, under the street lines and vehicles. Each statue stands at its plinth's ground centre (x, y map px),
 * at its true height (h map px, 0.25 m per px, seen at 30 degrees) and, zoomed in, a little larger so it stays
 * readable (at most MAX_GROW times, never more than MIN_PX tall). Drawn far to near, then cut by the occlusion data
 * in horizontal bands, each with the height that part of the statue has above its base, so a building in front
 * hides it like a vehicle. At night the night drawing fades in (darker; floodlit ones lit warm from the foot) with a
 * warm glow on the ground, and the eternal flame flickers.
 *
 * Clicking a statue (an invisible button over it) opens its landmark card, or the nearest one.
 */
import { useEffect, useRef, useState } from "react";
import { forwardWheel } from "../forwardWheel";
import { asset } from "../config";
import type { MapHandle } from "./IsometricMap";
import type { Place } from "./Pins";
import { loadOcclusion, type Occlusion } from "./occlusion";
import { canvasDpr, subscribe } from "../frame";
import { span as perfSpan } from "../perf";

interface Statue {
  id: string; name: string; landmark: string | null; x: number; y: number;
  /** true height and width, map px */
  h: number; w: number; hm: number;
  /** the ground centre, as fractions of the sprite: of its width from the left, of its height up from the bottom */
  ax: number; ay: number;
  lit: boolean; flame: boolean;
  /** warm ground glow radius at night, map px (0: none) */
  glow: number;
  day: string; night: string;
}

interface Props {
  map: React.RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
  season: string;
  onPick: (p: Place) => void;
}

const UP = 0.8660254 / 0.25;   // map px a point rises per metre
const MIN_PX = 34;             // zoomed in, a statue is drawn at least this tall (CSS px)...
const MAX_GROW = 2.5;          // ...but never more than this many times its true size
const MIN_Z = 0.06;            // not drawn when zoomed out further than this
const BANDS = 8;               // occlusion bands up a statue
/** Where the shadow of a point 1 px above the ground falls, screen px right and down of its foot. */
const SHADOW: [number, number] = [0.75, 0.3];

/** How much larger than life a statue is drawn at zoom z: 1 zoomed out, up to MAX_GROW from z 0.5 in. */
function grow(s: Statue, z: number): number {
  const want = Math.min(MAX_GROW, Math.max(1, MIN_PX / (s.h * z)));
  const t = Math.min(1, Math.max(0, (z - 0.25) / 0.25));
  return 1 + (want - 1) * t * t * (3 - 2 * t);
}

export function Statues({ map, night, season, onPick }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [list, setList] = useState<Statue[]>([]);
  const imgs = useRef(new Map<string, HTMLImageElement>());
  // the day drawing's silhouette in the shadow colour, per statue (made once its drawing is in)
  const shadows = useRef(new Map<string, HTMLCanvasElement>());
  const occ = useRef<Occlusion | null>(null);
  const hits = useRef(new Map<string, HTMLButtonElement>());
  const flags = useRef({ night, season });
  flags.current = { night, season };
  const wake = useRef<(() => void) | null>(null);

  useEffect(() => {
    fetch(asset("/data/statues.json")).then((r) => r.json()).then((l: Statue[]) => {
      for (const s of l) {
        for (const src of [s.day, s.night]) {
          const im = new Image();
          im.onload = () => {
            if (src === s.day) {
              const c = document.createElement("canvas");
              c.width = im.naturalWidth; c.height = im.naturalHeight;
              const cg = c.getContext("2d")!;
              cg.drawImage(im, 0, 0);
              cg.globalCompositeOperation = "source-in";
              cg.fillStyle = "rgb(24,28,48)"; cg.fillRect(0, 0, c.width, c.height);
              shadows.current.set(s.id, c);
            }
            wake.current?.();
          };
          im.src = asset(src);
          imgs.current.set(src, im);
        }
      }
      setList(l);
    }).catch(() => {});
    loadOcclusion().then((o) => { occ.current = o; wake.current?.(); }).catch(() => {});
  }, []);
  useEffect(() => { wake.current?.(); }, [night, season]);

  useEffect(() => {
    if (!list.length) return;
    let lastKey = "", settle = 0, dirty = true;
    const draw = (now: number) => {
      const cv = canvas.current, v = map.current?.getView();
      if (!cv || !v) return;
      const dpr = canvasDpr(2), W = window.innerWidth, H = window.innerHeight;
      const { night, season } = flags.current;
      const z = v.z, ox = W / 2 - v.x * z, oy = H / 2 - v.y * z;
      const flameOn = night > 0.05;
      // Nothing changed: redraw a few more times while the occlusion tiles come in, then rest (the flame excepted).
      const key = `${z.toFixed(5)},${ox.toFixed(1)},${oy.toFixed(1)},${night.toFixed(3)},${season},${W},${H}`;
      if (key === lastKey && !dirty) { if (++settle > 30 && !flameOn) return; } else { lastKey = key; settle = 0; dirty = false; }
      const end = perfSpan("statues");
      const bw = Math.round(W * dpr), bh = Math.round(H * dpr);
      if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; }
      const g = cv.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const shown: { s: Statue; sx: number; sy: number; k: number; dw: number; dh: number }[] = [];
      for (const s of list) {
        const hit = hits.current.get(s.id);
        const sx = s.x * z + ox, sy = s.y * z + oy;
        const k = grow(s, z), dh = s.h * z * k, dw = s.w * z * k;
        const vis = z >= MIN_Z && dh >= 2 && sx > -dw - 50 && sx < W + dw + 50 && sy > -50 && sy - dh < H + 50;
        if (hit) {
          hit.style.display = vis && z >= 0.15 ? "block" : "none";
          if (vis) {
            hit.style.transform = `translate(${sx - dw * s.ax}px,${sy - dh * (1 - s.ay)}px)`;
            hit.style.width = `${Math.max(dw, 14)}px`; hit.style.height = `${Math.max(dh, 14)}px`;
          }
        }
        if (vis) shown.push({ s, sx, sy, k, dw, dh });
      }
      shown.sort((a, b) => a.sy - b.sy);
      const t = now / 1000;
      for (const { s, sx, sy, k, dw, dh } of shown) {
        // warm pool of floodlight on the ground, under the statue
        if (s.lit && s.glow && night > 0.05) {
          const r = s.glow * z * Math.sqrt(k);
          g.save();
          g.translate(sx, sy); g.scale(1, 0.5);
          const gr = g.createRadialGradient(0, 0, 0, 0, 0, r);
          gr.addColorStop(0, `rgba(255,196,120,${0.55 * night})`); gr.addColorStop(1, "rgba(255,196,120,0)");
          g.fillStyle = gr; g.beginPath(); g.arc(0, 0, r, 0, Math.PI * 2); g.fill();
          g.restore();
        }
        const day = imgs.current.get(s.day), nt = imgs.current.get(s.night);
        const x0 = sx - dw * s.ax, y0 = sy - dh * (1 - s.ay);
        // its shadow on the ground, cast to the lower right by the sun at the upper left (as painted), faint at night
        const sh = shadows.current.get(s.id);
        if (sh && night < 0.95) {
          g.save();
          g.globalAlpha = 0.3 * (1 - night);
          g.transform(1, 0, -SHADOW[0], -SHADOW[1], sx, sy);
          g.drawImage(sh, -dw * s.ax, -dh * (1 - s.ay), dw, dh);
          g.restore();
        }
        if (day?.complete && day.naturalWidth) { g.globalAlpha = 1; g.drawImage(day, x0, y0, dw, dh); }
        if (night > 0.01 && nt?.complete && nt.naturalWidth) { g.globalAlpha = night; g.drawImage(nt, x0, y0, dw, dh); }
        g.globalAlpha = 1;
        if (s.flame && flameOn) {
          // a soft flicker over the flame (the top of the drawing)
          const f = 0.75 + 0.15 * Math.sin(t * 13.1) + 0.1 * Math.sin(t * 7.3 + 1.7);
          const r = Math.max(4, dw * 0.9);
          g.save(); g.globalCompositeOperation = "lighter";
          const gr = g.createRadialGradient(sx, y0 + dh * 0.25, 0, sx, y0 + dh * 0.25, r);
          gr.addColorStop(0, `rgba(255,170,70,${0.5 * f * night})`); gr.addColorStop(1, "rgba(255,120,40,0)");
          g.fillStyle = gr; g.beginPath(); g.arc(sx, y0 + dh * 0.25, r, 0, Math.PI * 2); g.fill();
          g.restore();
        }
      }
      // Buildings and trees in front hide them, band by band up each statue: a band d px above the base is hidden
      // where the surface in front is higher than d / (UP z) metres.
      const o = occ.current;
      if (o) {
        const view = { z, ox, oy, w: W, h: H };
        const canopy = season === "winter" ? 0.4 : 1;
        for (const { s, sx, sy, dw, dh, k } of shown) {
          const gr = s.lit && night > 0.05 ? s.glow * z * Math.sqrt(k) : 0;
          // (the shadow reaches SHADOW times the height to the right and down; it is cut with the base band)
          const xa = Math.min(sx - dw * s.ax, sx - gr) - 2;
          const xb = Math.max(sx + dw * (1 - s.ax) + SHADOW[0] * dh, sx + gr) + 2;
          const bottom = sy + Math.max(gr * 0.5, SHADOW[1] * dh) + 2;
          for (let i = 0; i < BANDS; i++) {
            const d0 = (dh * i) / BANDS, d1 = (dh * (i + 1)) / BANDS;
            const yTop = sy - d1 - (i === BANDS - 1 ? 4 : 0), yBot = i === 0 ? bottom : sy - d0;
            g.save();
            g.beginPath(); g.rect(xa, yTop, xb - xa, yBot - yTop); g.clip();
            o.cut(g, view, Math.max(0.3, (d0 + d1) / 2 / (UP * z)), "ground", canopy, [xa, yTop, xb, yBot]);
            g.restore();
          }
        }
      }
      end();
    };
    const stop = subscribe(draw, { name: "statues", fps: 15 });
    wake.current = () => { dirty = true; stop.wake(); };
    return () => { stop(); wake.current = null; };
  }, [list, map]);

  return (
    <>
      <canvas ref={canvas} className="overlay statues" aria-hidden="true" />
      <div className="statue-hits" onWheel={forwardWheel}>
        {list.map((s) => (
          <button key={s.id} type="button" className="statue-hit" aria-label={s.name} title={s.name}
            ref={(el) => { if (el) hits.current.set(s.id, el); else hits.current.delete(s.id); }}
            onClick={() => onPick({ n: s.name, c: "landmark", x: s.x, y: s.y, ...(s.landmark ? { s: s.landmark } : {}),
              d: `Statue or monument, about ${Math.round(s.hm)} m tall.` })} />
        ))}
      </div>
    </>
  );
}
