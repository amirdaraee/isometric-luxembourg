import { useEffect, useRef, useState, type RefObject } from "react";
import type { MapHandle } from "./IsometricMap";
import { asset } from "../config";
import { on } from "../features";

/**
 * Layered-map proof of concept (LAYERS_POC.md), local only: open the dev server with ?layers.
 *
 * The old-town block is drawn from separate layers instead of the single painting: the ground stack (land cover,
 * slopes, water, roads, walls) and the shadows go on a canvas under the vehicles; buildings, bridges and trees go
 * on a canvas above them, in depth bands (far to near, objects then trees in each band), so a tree in front of a
 * house covers it and one behind is hidden. Layer files come from pipeline/layers/export_web.py and live in
 * public/layers/<block>/ (never published).
 */
interface Band { i: number; obj?: number[]; [k: string]: number[] | number | undefined }
interface Meta { x0: number; y0: number; w: number; h: number; size: number; style: string; seasons: string[]; bands: Band[] }

type Shadow = "off" | "midday" | "evening";
type Trees = "off" | "summer" | "spring";
interface Switches { ground: boolean; relief: boolean; water: boolean; roads: boolean; walls: boolean; shadow: Shadow; objects: boolean; trees: Trees }
const START: Switches = { ground: true, relief: true, water: true, roads: true, walls: true, shadow: "midday", objects: true, trees: "summer" };

export const layersPocOn = import.meta.env.DEV && on("layersPoc") && new URLSearchParams(location.search).has("layers");

function load(url: string): HTMLImageElement {
  const im = new Image();
  im.decoding = "async";
  im.src = url;
  return im;
}

export function LayersPoc({ map, below }: { map: RefObject<MapHandle>; below: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [sw, setSw] = useState<Switches>(() => {
    const q = new URLSearchParams(location.search).get("layers");
    if (!q) return START;
    // ?layers=ground,roads,objects : only those (shadow and trees take their default version)
    const keep = new Set(q.split(","));
    return { ground: keep.has("ground"), relief: keep.has("relief"), water: keep.has("water"), roads: keep.has("roads"),
      walls: keep.has("walls"), shadow: keep.has("evening") ? "evening" : keep.has("shadow") ? "midday" : "off",
      objects: keep.has("objects"), trees: keep.has("spring") ? "spring" : keep.has("trees") ? "summer" : "off" };
  });
  const imgs = useRef<Record<string, HTMLImageElement>>({});
  const swRef = useRef(sw);
  swRef.current = sw;
  const base = asset("/layers/b00");

  useEffect(() => {
    fetch(`${base}/layers.json`).then((r) => r.json()).then((m: Meta) => {
      const im = imgs.current;
      if (below) {
        for (const n of ["ground", "relief", "water", "roads", "walls", "shadow_midday", "shadow_evening"]) im[n] = load(`${base}/${n}.webp`);
      } else {
        for (const b of m.bands) {
          for (const k of Object.keys(b)) if (k !== "i") im[`${k}_${b.i}`] = load(`${base}/bands/${k}_${b.i}.webp`);
        }
      }
      setMeta(m);
    }).catch(() => {});
  }, [base, below]);

  // the switches live in the "above" instance's panel; the "below" instance listens for them
  useEffect(() => {
    const on = (e: Event) => setSw((e as CustomEvent<Switches>).detail);
    if (below) window.addEventListener("layers-poc", on);
    return () => window.removeEventListener("layers-poc", on);
  }, [below]);
  useEffect(() => {
    if (!below) window.dispatchEvent(new CustomEvent("layers-poc", { detail: sw }));
  }, [sw, below]);

  useEffect(() => {
    if (!meta) return;
    let raf = 0;
    const draw = () => {
      raf = 0;
      const cv = canvas.current, m = map.current;
      if (!cv || !m) return;
      const dpr = window.devicePixelRatio || 1, W = window.innerWidth, H = window.innerHeight;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
      const ctx = cv.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, cv.width, cv.height);
      const a = m.toScreen(meta.x0, meta.y0), b = m.toScreen(meta.x0 + meta.w, meta.y0 + meta.h);
      if (!a || !b) return;
      const k = (b.x - a.x) / meta.size; // screen px per layer px
      ctx.setTransform(k * dpr, 0, 0, k * dpr, a.x * dpr, a.y * dpr);
      ctx.imageSmoothingQuality = k < 1 ? "high" : "low";
      const s = swRef.current, im = imgs.current;
      const put = (key: string, x = 0, y = 0) => {
        const i = im[key];
        if (i && i.complete && i.naturalWidth) ctx.drawImage(i, x, y);
      };
      if (below) {
        if (s.ground) put("ground");
        if (s.relief) put("relief");
        if (s.water) put("water");
        if (s.roads) put("roads");
        if (s.shadow !== "off") put(`shadow_${s.shadow}`);
        if (s.walls) put("walls");
      } else {
        for (const band of meta.bands) {
          if (s.objects && band.obj) put(`obj_${band.i}`, band.obj[0], band.obj[1]);
          const tk = `trees_${s.trees}`;
          const box = band[tk] as number[] | undefined;
          if (s.trees !== "off" && box) put(`${tk}_${band.i}`, box[0], box[1]);
        }
      }
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(draw); };
    const off = map.current?.onFrame(schedule);
    const t = setInterval(schedule, 500); // images finishing their download
    window.addEventListener("resize", schedule);
    schedule();
    return () => { off?.(); clearInterval(t); window.removeEventListener("resize", schedule); if (raf) cancelAnimationFrame(raf); };
  }, [meta, map, below, sw]);

  const box = (key: keyof Switches, label: string) => (
    <label><input type="checkbox" checked={sw[key] as boolean} onChange={(e) => setSw({ ...sw, [key]: e.target.checked })} /> {label}</label>
  );
  return (
    <>
      <canvas ref={canvas} className="overlay" aria-hidden="true" />
      {!below && meta && (
        <div className="layers-poc glass" role="group" aria-label="Layers (proof of concept)">
          <b>Layers, old town (test)</b>
          {box("ground", "L1 ground")}
          {box("relief", "L2 slopes and cliffs")}
          {box("walls", "L2 walls")}
          {box("water", "L3 water")}
          {box("roads", "L4 roads and rails")}
          <label>L6 shadows <select value={sw.shadow} onChange={(e) => setSw({ ...sw, shadow: e.target.value as Shadow })}>
            <option value="off">off</option><option value="midday">midday</option><option value="evening">evening</option></select></label>
          {box("objects", "L5 + L7 bridges and buildings")}
          <label>L8 trees <select value={sw.trees} onChange={(e) => setSw({ ...sw, trees: e.target.value as Trees })}>
            <option value="off">off</option>
            {meta.seasons.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <small>All off shows today's painting underneath.</small>
        </div>
      )}
    </>
  );
}
