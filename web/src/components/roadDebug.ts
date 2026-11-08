// ?roaddebug: the painted-road masks (pipeline/fit_roads.py) under the vehicles, with the OSM lines (red), the lines
// fitted to the painting (yellow) and the traffic lanes laid along them (cyan). For checking the fit by eye.
//
//   painted asphalt  green        rail bed  magenta        guard (where a car may be shown)  faint white
import { asset } from "../config";

export const roadDebugOn = typeof location !== "undefined" && new URLSearchParams(location.search).has("roaddebug");

interface Index { cell: number; tile: number; tiles: string[] }
interface Line { k?: string; p: number[]; q?: number[] }

let index: Index | null = null, asked = false;
const tiles = new Map<string, HTMLCanvasElement | null>();

function tile(key: string): HTMLCanvasElement | null {
  const t = tiles.get(key);
  if (t !== undefined) return t;
  tiles.set(key, null);
  const img = new Image();
  img.onload = () => {
    const n = index!.tile, c = document.createElement("canvas");
    c.width = n; c.height = n;
    const g = c.getContext("2d", { willReadFrequently: true })!;
    g.drawImage(img, 0, 0);
    const im = g.getImageData(0, 0, n, n), d = im.data;
    for (let i = 0; i < d.length; i += 4) {
      const v = d[i];
      let r = 0, gg = 0, b = 0, a = 0;
      if (v & 8) { r = 255; gg = 255; b = 255; a = 40; }
      if (v & 1) { r = 0; gg = 230; b = 60; a = 110; }
      if (v & 2) { r = 230; gg = 0; b = 230; a = 120; }
      d[i] = r; d[i + 1] = gg; d[i + 2] = b; d[i + 3] = a;
    }
    g.putImageData(im, 0, 0);
    tiles.set(key, c);
  };
  img.onerror = () => tiles.delete(key);
  img.src = asset(`/data/roadfit/${key}.png`);
  return null;
}

function poly(g: CanvasRenderingContext2D, p: number[], z: number, ox: number, oy: number) {
  g.beginPath();
  for (let i = 0; i < p.length; i += 2) {
    const x = p[i] * z + ox, y = p[i + 1] * z + oy;
    if (i) g.lineTo(x, y); else g.moveTo(x, y);
  }
  g.stroke();
}

/** Draw the debug layer for the view (z: screen px per map px, ox/oy: screen offset, W/H: screen size). */
export function drawRoadDebug(g: CanvasRenderingContext2D, z: number, ox: number, oy: number, W: number, H: number,
  lines: { roads: Line[]; rail: Line[] } | undefined, lanes: number[][]) {
  if (!asked) {
    asked = true;
    fetch(asset("/data/roadfit/index.json")).then((r) => r.json()).then((i: Index) => { index = i; }).catch(() => { asked = false; });
  }
  const x0 = -ox / z, y0 = -oy / z, x1 = (W - ox) / z, y1 = (H - oy) / z;
  if (index && z >= 0.15) {
    const span = index.cell * index.tile, have = new Set(index.tiles);
    g.imageSmoothingEnabled = false;
    for (let ty = Math.floor(y0 / span); ty <= Math.floor(y1 / span); ty++)
      for (let tx = Math.floor(x0 / span); tx <= Math.floor(x1 / span); tx++) {
        const key = `${tx}_${ty}`;
        if (!have.has(key)) continue;
        const c = tile(key);
        if (c) g.drawImage(c, tx * span * z + ox, ty * span * z + oy, span * z, span * z);
      }
    g.imageSmoothingEnabled = true;
  }
  if (!lines) return;
  const inView = (p: number[]) => {
    for (let i = 0; i < p.length; i += 2) if (p[i] >= x0 && p[i] <= x1 && p[i + 1] >= y0 && p[i + 1] <= y1) return true;
    return false;
  };
  g.lineWidth = 1.2;
  for (const [key, colour] of [["p", "rgba(255,40,40,.9)"], ["q", "rgba(255,230,0,.95)"]] as const) {
    g.strokeStyle = colour;
    for (const w of [...lines.roads, ...lines.rail]) {
      const p = key === "p" ? (w.q ? w.p : null) : w.q;
      if (p && inView(p)) poly(g, p, z, ox, oy);
    }
  }
  g.strokeStyle = "rgba(0,220,255,.9)";
  g.setLineDash([4, 3]);
  for (const p of lanes) poly(g, p, z, ox, oy);
  g.setLineDash([]);
}
