import { useEffect, useRef } from "react";
import { asset } from "../config";
import type { MapHandle } from "./IsometricMap";

// Illustrated clouds round the edge of the map, and a sky in place of the flat background outside the data.
// Positions come from web/public/data/clouds.json (pipeline/build_clouds.py), sprites from web/public/clouds/.
// Drawn on one canvas above the map tiles and below the pins; redrawn in the map's own frame (map.onFrame) so it
// never lags the map, and by a slow animation loop for the drift while any cloud is showing.

interface Cloud {
  x: number; y: number; w: number;
  s: number;   // sprite
  f: number;   // 1: mirrored
  p: number;   // parallax: 0 sits on the map; higher clouds move a little more than the map when panning
  v: number;   // drift speed, map px per second
  ph: number;  // drift phase
  r: number;   // 0 on the edge of the data, larger further out
}
interface CloudData {
  sprites: number;
  spriteSize: [number, number];
  centre: [number, number];
  width: number;
  edge: number[];
  clouds: Cloud[];
}

interface Props {
  map: React.RefObject<MapHandle>;
  /** 0 day .. 1 full night */
  night: number;
}

const DRIFT_PERIOD = 240; // seconds: clouds wander to and fro round their place rather than blowing away
// Zoom (screen px per map px) over which the clouds fade out: the bank on the edge lasts a little longer.
const FADE_EDGE: [number, number] = [0.28, 0.5];
const FADE_SEA: [number, number] = [0.16, 0.34];
// Sky: [centre, outside], by day and by night.
const SKY_DAY = [[58, 82, 116], [22, 33, 54]];
const SKY_NIGHT = [[20, 30, 50], [7, 11, 22]];

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
};
const mixRgb = (a: number[], b: number[], t: number) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",")})`;

/** A sprite as a bitmap, and its mirror image. */
async function load(url: string): Promise<[ImageBitmap, ImageBitmap]> {
  const blob = await (await fetch(url)).blob();
  const img = await createImageBitmap(blob);
  const c = new OffscreenCanvas(img.width, img.height);
  const g = c.getContext("2d")!;
  g.scale(-1, 1);
  g.drawImage(img, -img.width, 0);
  return [img, c.transferToImageBitmap()];
}

export function Clouds({ map, night }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const nightRef = useRef(night);
  const draw = useRef<() => void>(() => {});
  useEffect(() => {
    nightRef.current = night;
    draw.current();
  }, [night]);

  useEffect(() => {
    let data: CloudData | null = null;
    let day: [ImageBitmap, ImageBitmap][] = [];
    let dark: [ImageBitmap, ImageBitmap][] = [];
    let raf = 0;
    let last = 0;
    let alive = true;
    let layer: HTMLCanvasElement | null = null;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t0 = performance.now();

    const paint = () => {
      const cv = canvas.current, m = map.current, v = m?.getView();
      if (!cv || !v || !data) return false;
      last = performance.now();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const W = window.innerWidth, H = window.innerHeight;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) {
        cv.width = Math.round(W * dpr);
        cv.height = Math.round(H * dpr);
      }
      const g = cv.getContext("2d")!;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, W, H);
      const z = v.z, cx = W / 2, cy = H / 2;
      const sx = (x: number) => (x - v.x) * z + cx;
      const sy = (y: number) => (y - v.y) * z + cy;
      const n = nightRef.current;

      // Sky: everything outside the outline of the data.
      const e = data.edge;
      const mx = sx(data.centre[0]), my = sy(data.centre[1]);
      const grad = g.createRadialGradient(mx, my, data.width * z * 0.3, mx, my, data.width * z * 1.4);
      grad.addColorStop(0, mixRgb(SKY_DAY[0], SKY_NIGHT[0], n));
      grad.addColorStop(1, mixRgb(SKY_DAY[1], SKY_NIGHT[1], n));
      g.beginPath();
      g.rect(0, 0, W, H);
      g.moveTo(sx(e[0]), sy(e[1]));
      for (let i = 2; i < e.length; i += 2) g.lineTo(sx(e[i]), sy(e[i + 1]));
      g.closePath();
      g.fillStyle = grad;
      g.fill("evenodd");

      // Clouds.
      const aEdge = 1 - smooth(FADE_EDGE[0], FADE_EDGE[1], z);
      const aSea = 1 - smooth(FADE_SEA[0], FADE_SEA[1], z);
      if (aEdge <= 0.001) return false;
      // While fading, draw the clouds at full strength on a layer of their own and lay that down faded, so
      // overlapping clouds don't show through one another.
      let out = g;
      if (aEdge < 0.999) {
        layer ??= document.createElement("canvas");
        if (layer.width !== cv.width || layer.height !== cv.height) { layer.width = cv.width; layer.height = cv.height; }
        out = layer.getContext("2d")!;
        out.setTransform(dpr, 0, 0, dpr, 0, 0);
        out.clearRect(0, 0, W, H);
      }
      const t = still ? 0 : (performance.now() - t0) / 1000;
      const w0 = (2 * Math.PI) / DRIFT_PERIOD;
      const [SW, SH] = data.spriteSize;
      for (const c of data.clouds) {
        // the bank on the edge is solid; out in the open sky the clouds grow fainter
        const a = (c.r <= 1 ? aEdge : aSea * (1 - Math.min(c.r - 2, 6) * 0.07)) / (out === g ? 1 : aEdge);
        if (a <= 0.001) continue;
        const amp = (c.v * DRIFT_PERIOD) / (2 * Math.PI) / 4;
        const dx = amp * Math.sin(t * w0 + c.ph), dy = amp * 0.3 * Math.cos(t * w0 * 0.7 + c.ph);
        const k = 1 + c.p;
        const px = cx + ((c.x + dx - v.x) * z) * k, py = cy + ((c.y + dy - v.y) * z) * k;
        const w = c.w * z * k, h = (w * SH) / SW;
        if (px + w / 2 < 0 || px - w / 2 > W || py + h / 2 < 0 || py - h / 2 > H) continue;
        const pair = c.f ? 1 : 0;
        if (n < 0.999 && day[c.s]) {
          out.globalAlpha = a * (1 - n);
          out.drawImage(day[c.s][pair], px - w / 2, py - h / 2, w, h);
        }
        if (n > 0.001 && dark[c.s]) {
          out.globalAlpha = a * n;
          out.drawImage(dark[c.s][pair], px - w / 2, py - h / 2, w, h);
        }
      }
      out.globalAlpha = 1;
      if (out !== g && layer) {
        g.setTransform(1, 0, 0, 1, 0, 0);
        g.globalAlpha = aEdge;
        g.drawImage(layer, 0, 0);
        g.globalAlpha = 1;
      }
      return true;
    };

    // The drift needs a steady redraw only while clouds are showing; the map's own frames cover panning.
    const loop = () => {
      raf = 0;
      if (!alive) return;
      const showing = performance.now() - last > 12 ? paint() : true;
      if (showing && !still) raf = requestAnimationFrame(loop);
    };
    const kick = () => {
      paint();
      if (!raf && alive && !still) raf = requestAnimationFrame(loop);
    };
    draw.current = kick;

    fetch(asset("/data/clouds.json"))
      .then((r) => r.json())
      .then(async (d: CloudData) => {
        const ids = Array.from({ length: d.sprites }, (_, i) => i);
        const [a, b] = await Promise.all([
          Promise.all(ids.map((i) => load(asset(`/clouds/c${i}.png`)))),
          Promise.all(ids.map((i) => load(asset(`/clouds/c${i}_n.png`)))),
        ]);
        if (!alive) return;
        data = d; day = a; dark = b;
        kick();
      })
      .catch(() => {});

    const off = map.current?.onFrame(kick);
    window.addEventListener("resize", kick);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      off?.();
      window.removeEventListener("resize", kick);
      draw.current = () => {};
    };
  }, [map]);

  return <canvas ref={canvas} aria-hidden="true"
    style={{ position: "fixed", inset: 0, width: "100vw", height: "100vh", pointerEvents: "none", zIndex: 1 }} />;
}
