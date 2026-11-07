/**
 * Foreground occlusion for vehicles drawn over the painted map (after Pixel Singapore's foreground layer).
 *
 * In this view, whatever is higher along a line of sight is nearer the camera. pipeline/build_occlusion.py
 * compares the 3D height pass with the ground behind each surface and bakes, near every road and rail line:
 *
 *   /data/occluders.png  RGB, 1 px = `scale` map px from (x0, y0) in /data/occluders.json, values in decimetres:
 *     R  "ground" layer: height of the surface in front, above the ground behind it (buildings, bridge decks over
 *        a valley road, tree crowns from the painted art as 8 m). Clipped at 25.5 m.
 *     G  "deck" layer, near bridges and viaducts only: height of a built surface above the deck's own height
 *        (a tower in front of a viaduct, a higher deck crossing it). Visible ground never counts.
 *   /data/road_heights.json  per lines.json way id (bridges and viaducts that carry vehicles): samples every ~4 m
 *     with x, y, s (map px along the lines.json polyline), z (deck height, m above sea level), dz (m the modelled
 *     deck sits above the line lines.json drew), h (m above the terrain below). Smoothed: no jumps, 1 in 8 at most.
 *
 * API (all coordinates in map px; a view is screen = map * z + (ox, oy), the same numbers Overlay uses):
 *
 *   loadOcclusion(): Promise<Occlusion>     fetches both assets once; later calls return the same promise.
 *   occ.cut(g, view, heightM, layer?)       erases (destination-out) every pixel already on `g` that the
 *                                           foreground hides for a vehicle `heightM` tall; layer "ground"
 *                                           (default) or "deck". Draws in g's current transform.
 *   occ.isHidden(x, y, heightM, layer?)     true when the whole vehicle standing at (x, y) is hidden: every
 *                                           sample up its vertical centre line is behind the foreground.
 *   occ.coverage(x, y, heightM, layer?)     the hidden fraction (0..1) of that centre line.
 *   occ.heightAt(x, y, layer?)              occluder height in metres at a map px (0 outside the data).
 *   occ.deckAt(x, y, r?)                    the nearest deck sample within r map px (default 12), or null:
 *                                           { id, z, dz, h, lift } where lift = dz in map px (draw that much
 *                                           higher to sit on the modelled deck). For tram and train positions
 *                                           that come from GTFS shapes rather than lines.json ways.
 *   occ.deckLift(id, s)                     lift in map px for lines.json way `id` at distance s along it;
 *                                           0 for ways that are not decks. occ.isDeck(id) tells which they are.
 *
 * Recommended drawing (one extra canvas, the "vehicle layer", the size of the overlay, cleared every frame):
 *   1. draw cars (about 1.6 m tall) on ground ways      then occ.cut(v, view, 1.6)
 *   2. draw buses, trams, trains (4.5 m) on ground ways  then occ.cut(v, view, 4.5)
 *      (shortest first: a taller vehicle's cut only removes pixels a shorter one's cut has already removed)
 *   3. draw every vehicle on a deck (isDeck / deckAt), lifted by deckLift, then occ.cut(v, view, 4.5, "deck")
 *   4. overlay.drawImage(vehicleLayer, 0, 0)
 * The erased pixels show the painted map underneath, which is exactly the foreground, so no copy of the art is
 * needed and it works for every season and the night variant. Cutting directly on the overlay canvas would
 * also erase the street lines and birds drawn before the vehicles, hence the separate layer.
 *
 * Limits: the cut uses one threshold per pass (Pixel Singapore's rule: the surface is higher than the vehicle's
 * top), so a low wall in front of a car's lower half does not hide it; isHidden does the exact per-pixel test.
 * Data covers the painted area only; outside it nothing is hidden.
 */
import { asset } from "../config";

export type Layer = "ground" | "deck";
export interface View { z: number; ox: number; oy: number; w: number; h: number }
export interface DeckHit { id: number; z: number; dz: number; h: number; lift: number }

interface Meta { x0: number; y0: number; scale: number; w: number; h: number; unit: number }
interface Profile { x: number[]; y: number[]; s: number[]; z: number[]; dz: number[]; h: number[] }

const MPP = 0.25;
const CE = 0.8660254;
const UP = CE / MPP;          // map px a point rises per metre of height
const TILE = 256;             // mask tiles, in occluder px
const EPS = 0.3;              // m: a surface this close to the vehicle's body counts as level with it
const CELL = 64;              // deck sample index cell, map px

export interface Occlusion {
  cut(g: CanvasRenderingContext2D, view: View, heightM: number, layer?: Layer): void;
  isHidden(x: number, y: number, heightM: number, layer?: Layer): boolean;
  coverage(x: number, y: number, heightM: number, layer?: Layer): number;
  heightAt(x: number, y: number, layer?: Layer): number;
  deckAt(x: number, y: number, r?: number): DeckHit | null;
  deckLift(id: number, s: number): number;
  isDeck(id: number): boolean;
}

let loading: Promise<Occlusion> | null = null;

export function loadOcclusion(): Promise<Occlusion> {
  if (!loading) loading = load();
  return loading;
}

async function load(): Promise<Occlusion> {
  const [meta, profiles, img] = await Promise.all([
    fetch(asset("/data/occluders.json")).then((r) => r.json() as Promise<Meta>),
    fetch(asset("/data/road_heights.json")).then((r) => r.json() as Promise<Record<string, Profile>>),
    fetch(asset("/data/occluders.png")).then((r) => r.blob())
      .then((b) => createImageBitmap(b, { colorSpaceConversion: "none", premultiplyAlpha: "none" })),
  ]);
  const { w, h } = meta;
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const cg = c.getContext("2d", { willReadFrequently: true })!;
  cg.drawImage(img, 0, 0);
  img.close();
  const px = cg.getImageData(0, 0, w, h).data;
  c.width = c.height = 0;  // free the decode canvas
  const ground = new Uint8Array(w * h), deck = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) { ground[i] = px[i * 4]; deck[i] = px[i * 4 + 1]; }
  return new Occ(meta, ground, deck, profiles);
}

class Occ implements Occlusion {
  private tiles = new Map<string, HTMLCanvasElement | null>();
  private cells = new Map<number, [number, number][]>();   // cell -> [way id, sample index]

  constructor(private m: Meta, private ground: Uint8Array, private deck: Uint8Array,
              private prof: Record<string, Profile>) {
    for (const [id, p] of Object.entries(prof)) {
      for (let i = 0; i < p.x.length; i++) {
        const k = this.cellKey(Math.floor(p.x[i] / CELL), Math.floor(p.y[i] / CELL));
        let a = this.cells.get(k);
        if (!a) this.cells.set(k, (a = []));
        a.push([+id, i]);
      }
    }
  }

  private cellKey(cx: number, cy: number) { return cy * 100000 + cx; }

  private data(layer: Layer) { return layer === "deck" ? this.deck : this.ground; }

  heightAt(x: number, y: number, layer: Layer = "ground"): number {
    const { x0, y0, scale, w, h, unit } = this.m;
    const i = Math.floor((x - x0) / scale), j = Math.floor((y - y0) / scale);
    if (i < 0 || j < 0 || i >= w || j >= h) return 0;
    return this.data(layer)[j * w + i] * unit;
  }

  coverage(x: number, y: number, heightM: number, layer: Layer = "ground"): number {
    // Walk up the vehicle's centre line one occluder pixel at a time; a sample t metres up the body is hidden
    // when the surface in front there is higher than t.
    const step = this.m.scale;
    const n = Math.max(1, Math.ceil((heightM * UP) / step));
    let hidden = 0;
    for (let k = 0; k <= n; k++) {
      const t = Math.min(heightM, (k * step) / UP);
      if (this.heightAt(x, y - k * step, layer) > t + EPS) hidden++;
    }
    return hidden / (n + 1);
  }

  isHidden(x: number, y: number, heightM: number, layer: Layer = "ground"): boolean {
    return this.coverage(x, y, heightM, layer) >= 1;
  }

  cut(g: CanvasRenderingContext2D, view: View, heightM: number, layer: Layer = "ground"): void {
    const { x0, y0, scale, w, h } = this.m;
    const thr = Math.round(heightM * 10);
    const span = TILE * scale * view.z;  // a tile's size on screen
    // tiles that touch the view
    const tx0 = Math.max(0, Math.floor((-view.ox / view.z - x0) / scale / TILE));
    const ty0 = Math.max(0, Math.floor((-view.oy / view.z - y0) / scale / TILE));
    const tx1 = Math.min(Math.ceil(w / TILE) - 1, Math.floor(((view.w - view.ox) / view.z - x0) / scale / TILE));
    const ty1 = Math.min(Math.ceil(h / TILE) - 1, Math.floor(((view.h - view.oy) / view.z - y0) / scale / TILE));
    if (tx1 < tx0 || ty1 < ty0) return;
    g.save();
    g.globalCompositeOperation = "destination-out";
    g.imageSmoothingEnabled = true;  // soft edges when zoomed in past the mask's resolution
    for (let ty = ty0; ty <= ty1; ty++) {
      for (let tx = tx0; tx <= tx1; tx++) {
        const t = this.tile(layer, thr, tx, ty);
        if (!t) continue;
        const sx = (x0 + tx * TILE * scale) * view.z + view.ox, sy = (y0 + ty * TILE * scale) * view.z + view.oy;
        g.drawImage(t, sx, sy, (t.width / TILE) * span, (t.height / TILE) * span);
      }
    }
    g.restore();
  }

  /** Alpha mask of one tile for a threshold (built on first use, null when nothing in it is foreground). */
  private tile(layer: Layer, thr: number, tx: number, ty: number): HTMLCanvasElement | null {
    const key = `${layer}:${thr}:${tx}:${ty}`;
    const hit = this.tiles.get(key);
    if (hit !== undefined) return hit;
    const { w, h } = this.m;
    const d = this.data(layer);
    const tw = Math.min(TILE, w - tx * TILE), th = Math.min(TILE, h - ty * TILE);
    const img = new ImageData(tw, th);
    const a = img.data;
    let any = false;
    for (let j = 0; j < th; j++) {
      let src = (ty * TILE + j) * w + tx * TILE, dst = j * tw * 4;
      for (let i = 0; i < tw; i++, src++, dst += 4) {
        if (d[src] > thr) { a[dst + 3] = 255; any = true; }
      }
    }
    let c: HTMLCanvasElement | null = null;
    if (any) {
      c = document.createElement("canvas");
      c.width = tw; c.height = th;
      c.getContext("2d")!.putImageData(img, 0, 0);
    }
    this.tiles.set(key, c);
    return c;
  }

  deckAt(x: number, y: number, r = 12): DeckHit | null {
    let best: DeckHit | null = null, bd = r * r;
    const c0x = Math.floor((x - r) / CELL), c1x = Math.floor((x + r) / CELL);
    const c0y = Math.floor((y - r) / CELL), c1y = Math.floor((y + r) / CELL);
    for (let cy = c0y; cy <= c1y; cy++) {
      for (let cx = c0x; cx <= c1x; cx++) {
        for (const [id, i] of this.cells.get(this.cellKey(cx, cy)) ?? []) {
          const p = this.prof[id];
          const dd = (p.x[i] - x) ** 2 + (p.y[i] - y) ** 2;
          if (dd <= bd) { bd = dd; best = { id, z: p.z[i], dz: p.dz[i], h: p.h[i], lift: p.dz[i] * UP }; }
        }
      }
    }
    return best;
  }

  isDeck(id: number): boolean { return String(id) in this.prof; }

  deckLift(id: number, s: number): number {
    const p = this.prof[id];
    if (!p) return 0;
    const S = p.s, n = S.length;
    if (s <= S[0]) return p.dz[0] * UP;
    if (s >= S[n - 1]) return p.dz[n - 1] * UP;
    let lo = 0, hi = n - 1;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (S[mid] <= s) lo = mid; else hi = mid; }
    const f = (s - S[lo]) / (S[hi] - S[lo] || 1);
    return (p.dz[lo] + (p.dz[hi] - p.dz[lo]) * f) * UP;
  }
}
