/**
 * Foreground occlusion for vehicles drawn over the painted map (after Pixel Singapore's foreground layer).
 *
 * In this view, whatever is higher along a line of sight is nearer the camera. pipeline/build_occlusion.py
 * compares the 3D height pass with the ground behind each surface and bakes, near every road and rail line:
 *
 *   /data/occluders/<tx>_<ty>.png  RGB tiles of `tile` px, 1 px = `scale` map px from (x0, y0) in
 *     /data/occluders.json (tiles not listed there are empty); loaded when the view first needs them:
 *     R  "ground" layer, decimetres: height of the built surface in front, above the ground behind it (buildings,
 *        bridge decks over a valley road). Clipped at 25.5 m.
 *     G  "deck" layer, near bridges and viaducts only, decimetres: height of a built surface above the deck's own
 *        height (a tower in front of a viaduct, a higher deck crossing it). Visible ground never counts.
 *     B  tree canopy in front of the lanes, soft: 0..255 is how much of a vehicle there is hidden. It fades
 *        vehicles into the crowns rather than cutting them off, in both layers.
 *   /data/road_heights.json  per lines.json way id (bridges and viaducts that carry vehicles): samples every ~4 m
 *     with x, y, s (map px along the lines.json polyline), z (deck height, m above sea level), dz (m the modelled
 *     deck sits above the line lines.json drew), h (m above the terrain below). Smoothed: no jumps, 1 in 8 at most.
 *
 * API (all coordinates in map px; a view is screen = map * z + (ox, oy), the same numbers Overlay uses):
 *
 *   loadOcclusion(): Promise<Occlusion>     fetches the index and the deck profiles once; later calls return the same
 *                                           promise. Occluder tiles load on first use: until a tile is in, nothing
 *                                           there is hidden.
 *   occ.cut(g, view, heightM, layer?, canopy?, rect?)  erases (destination-out) every pixel already on `g` that the
 *                                           foreground hides for a vehicle `heightM` tall; layer "ground"
 *                                           (default) or "deck". The tree canopy erases by its coverage times
 *                                           `canopy` (default 1; bare winter crowns hide less, 0.4). Draws in g's
 *                                           current transform. rect: only the tiles touching this screen
 *                                           rectangle (x0, y0, x1, y1), or touching any of a list of them
 *                                           (each tile drawn once, so partial canopy is not erased twice).
 *   occ.canopyAt(x, y)                      tree canopy coverage 0..1 at a map px.
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
/** A screen rectangle: x0, y0, x1, y1. */
export type Rect = [number, number, number, number];
export interface DeckHit { id: number; z: number; dz: number; h: number; lift: number }

interface Meta { x0: number; y0: number; scale: number; w: number; h: number; unit: number; tile: number; tiles: string[] }
/** A deck profile; fx, fy: its samples moved onto the road as painted (pipeline/fit_roads.py), used for deckAt. */
interface Profile { x: number[]; y: number[]; fx?: number[]; fy?: number[]; s: number[]; z: number[]; dz: number[]; h: number[] }
/** One decoded data tile: its size and the three layers. */
interface DataTile { w: number; h: number; ground: Uint8Array; deck: Uint8Array; crown: Uint8Array }

const MPP = 0.25;
const CE = 0.8660254;
const UP = CE / MPP;          // map px a point rises per metre of height
const TILE = 256;             // mask tiles, in occluder px (a data tile holds whole mask tiles)
const EPS = 0.3;              // m: a surface this close to the vehicle's body counts as level with it
const CELL = 64;              // deck sample index cell, map px
const KEEP_DATA = 48;         // decoded data tiles kept (each 0.75 MB), least recently used dropped first
const KEEP_MASKS = 150;       // mask canvases kept, likewise

export interface Occlusion {
  cut(g: CanvasRenderingContext2D, view: View, heightM: number, layer?: Layer, canopy?: number,
    rect?: Rect | Rect[]): void;
  canopyAt(x: number, y: number): number;
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
  const [meta, profiles] = await Promise.all([
    fetch(asset("/data/occluders.json")).then((r) => r.json() as Promise<Meta>),
    fetch(asset("/data/road_heights.json")).then((r) => r.json() as Promise<Record<string, Profile>>),
  ]);
  return new Occ(meta, profiles);
}

/** Decodes one occluder tile (RGB, no alpha, so the values come through untouched). */
async function decodeTile(url: string): Promise<DataTile> {
  const img = await fetch(url).then((r) => r.blob())
    .then((b) => createImageBitmap(b, { colorSpaceConversion: "none", premultiplyAlpha: "none" }));
  const w = img.width, h = img.height;
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const cg = c.getContext("2d", { willReadFrequently: true })!;
  cg.drawImage(img, 0, 0);
  img.close();
  const px = cg.getImageData(0, 0, w, h).data;
  c.width = c.height = 0;
  const ground = new Uint8Array(w * h), deck = new Uint8Array(w * h), crown = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) { ground[i] = px[i * 4]; deck[i] = px[i * 4 + 1]; crown[i] = px[i * 4 + 2]; }
  return { w, h, ground, deck, crown };
}

class Occ implements Occlusion {
  /** Mask canvases by layer, threshold, canopy and tile (null: nothing to cut there), least recently used first. */
  private masks = new Map<string, HTMLCanvasElement | null>();
  /** Decoded data tiles, least recently used first; null while loading. Tiles not listed in the meta are empty. */
  private data = new Map<string, DataTile | null>();
  private listed: Set<string>;
  private cells = new Map<number, [number, number][]>();   // cell -> [way id, sample index]

  private m: Meta;
  private prof: Record<string, Profile>;

  constructor(m: Meta, prof: Record<string, Profile>) {
    this.m = m; this.prof = prof; this.listed = new Set(m.tiles);
    for (const [id, p] of Object.entries(prof)) {
      for (let i = 0; i < p.x.length; i++) {
        const k = this.cellKey(Math.floor((p.fx ?? p.x)[i] / CELL), Math.floor((p.fy ?? p.y)[i] / CELL));
        let a = this.cells.get(k);
        if (!a) this.cells.set(k, (a = []));
        a.push([+id, i]);
      }
    }
  }

  private cellKey(cx: number, cy: number) { return cy * 100000 + cx; }

  /** Data tile (dx, dy): the tile, null while loading (it is asked for), or "empty". */
  private tileData(dx: number, dy: number): DataTile | null | "empty" {
    const key = `${dx}_${dy}`;
    if (!this.listed.has(key)) return "empty";
    const t = this.data.get(key);
    if (t === undefined) {
      this.data.set(key, null);
      decodeTile(asset(`/data/occluders/${key}.png`)).then((d) => {
        this.data.set(key, d);
        for (const [k, v] of this.data) {
          if (this.data.size <= KEEP_DATA) break;
          if (v) this.data.delete(k);
        }
      }).catch(() => this.data.delete(key));
      return null;
    }
    if (t) { this.data.delete(key); this.data.set(key, t); }   // most recently used last
    return t;
  }

  /** Layer value at occluder px (i, j), 0 outside the data or while its tile loads. */
  private at(i: number, j: number, layer: Layer | "crown"): number {
    const { w, h, tile } = this.m;
    if (i < 0 || j < 0 || i >= w || j >= h) return 0;
    const t = this.tileData(Math.floor(i / tile), Math.floor(j / tile));
    if (!t || t === "empty") return 0;
    const k = (j % tile) * t.w + (i % tile);
    return (layer === "deck" ? t.deck : layer === "crown" ? t.crown : t.ground)[k];
  }

  heightAt(x: number, y: number, layer: Layer = "ground"): number {
    const { x0, y0, scale, unit } = this.m;
    return this.at(Math.floor((x - x0) / scale), Math.floor((y - y0) / scale), layer) * unit;
  }

  canopyAt(x: number, y: number): number {
    const { x0, y0, scale } = this.m;
    return this.at(Math.floor((x - x0) / scale), Math.floor((y - y0) / scale), "crown") / 255;
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

  cut(g: CanvasRenderingContext2D, view: View, heightM: number, layer: Layer = "ground", canopy = 1,
    rect?: Rect | Rect[]): void {
    const { x0, y0, scale, w, h } = this.m;
    const thr = Math.round(heightM * 10);
    const ck = Math.round(Math.min(Math.max(canopy, 0), 1) * 10);   // canopy strength in tenths (cache key)
    const span = TILE * scale * view.z;  // a tile's size on screen
    // tiles that touch the view, or the given screen rectangles within it (each tile once)
    const rects: Rect[] = !rect ? [[0, 0, view.w, view.h]] : typeof rect[0] === "number" ? [rect as Rect] : rect as Rect[];
    const ntx = Math.ceil(w / TILE);
    const done = rects.length > 1 ? new Set<number>() : null;
    g.save();
    g.globalCompositeOperation = "destination-out";
    g.imageSmoothingEnabled = true;  // soft edges when zoomed in past the mask's resolution
    for (const [rx0, ry0, rx1, ry1] of rects) {
      const tx0 = Math.max(0, Math.floor(((rx0 - view.ox) / view.z - x0) / scale / TILE));
      const ty0 = Math.max(0, Math.floor(((ry0 - view.oy) / view.z - y0) / scale / TILE));
      const tx1 = Math.min(ntx - 1, Math.floor(((rx1 - view.ox) / view.z - x0) / scale / TILE));
      const ty1 = Math.min(Math.ceil(h / TILE) - 1, Math.floor(((ry1 - view.oy) / view.z - y0) / scale / TILE));
      for (let ty = ty0; ty <= ty1; ty++) {
        for (let tx = tx0; tx <= tx1; tx++) {
          if (done) { const k = ty * ntx + tx; if (done.has(k)) continue; done.add(k); }
          const t = this.tile(layer, thr, ck, tx, ty);
          if (!t) continue;
          const sx = (x0 + tx * TILE * scale) * view.z + view.ox, sy = (y0 + ty * TILE * scale) * view.z + view.oy;
          g.drawImage(t, sx, sy, (t.width / TILE) * span, (t.height / TILE) * span);
        }
      }
    }
    g.restore();
  }

  /** Alpha mask of one tile for a threshold and canopy strength (tenths), built on first use once its data tile is
   * in; null when nothing in it is foreground (or its data is still loading, then not kept). */
  private tile(layer: Layer, thr: number, ck: number, tx: number, ty: number): HTMLCanvasElement | null {
    const key = `${layer}:${thr}:${ck}:${tx}:${ty}`;
    const hit = this.masks.get(key);
    if (hit !== undefined) { this.masks.delete(key); this.masks.set(key, hit); return hit; }
    const { w, h, tile: DT } = this.m;
    const px0 = tx * TILE, py0 = ty * TILE;
    const dt = this.tileData(Math.floor(px0 / DT), Math.floor(py0 / DT));
    if (dt === null) return null;                              // loading: try again next frame
    let c: HTMLCanvasElement | null = null;
    if (dt !== "empty") {
      const d = layer === "deck" ? dt.deck : dt.ground, cr = dt.crown, k = ck / 10;
      const tw = Math.min(TILE, w - px0), th = Math.min(TILE, h - py0);
      const ox = px0 % DT, oy = py0 % DT;
      const img = new ImageData(tw, th);
      const a = img.data;
      let any = false;
      for (let j = 0; j < th; j++) {
        let src = (oy + j) * dt.w + ox, dst = j * tw * 4;
        for (let i = 0; i < tw; i++, src++, dst += 4) {
          if (d[src] > thr) { a[dst + 3] = 255; any = true; }
          else if (cr[src] && k) { a[dst + 3] = Math.round(cr[src] * k); any = true; }
        }
      }
      if (any) {
        c = document.createElement("canvas");
        c.width = tw; c.height = th;
        c.getContext("2d")!.putImageData(img, 0, 0);
      }
    }
    this.masks.set(key, c);
    if (this.masks.size > KEEP_MASKS) this.masks.delete(this.masks.keys().next().value!);
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
          const dd = ((p.fx ?? p.x)[i] - x) ** 2 + ((p.fy ?? p.y)[i] - y) ** 2;
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

// ---------------------------------------------------------------------------------------------------------------
// The drivable map (pipeline/build_drivable.py): what lies under a vehicle's drawn ground point, 0.5 m cells in
// tiles loaded on first use.

/** Cell values of the drivable map. */
export const DRIVABLE = { none: 0, road: 1, deck: 2, water: 3, building: 4, hidden: 5, unpainted: 6 } as const;

export interface Drivable {
  /** The cell value at a map px, or -1 while its tile is loading. */
  at(x: number, y: number): number;
}

interface DrivableIndex { cell: number; tile: number; cols: number; rows: number; tiles: string[] }

let drivableLoading: Promise<Drivable> | null = null;

export function loadDrivable(): Promise<Drivable> {
  if (!drivableLoading) {
    drivableLoading = fetch(asset("/data/drivable/index.json")).then((r) => r.json() as Promise<DrivableIndex>)
      .then((idx) => new DrivableMap(idx));
  }
  return drivableLoading;
}

/** Bits of the painted-road masks (pipeline/fit_roads.py, /data/roadfit): asphalt, rail bed, unpainted, the guard
 * (painted road with small gaps closed, grown by 0.5 m: a road vehicle may be shown there) and painted road. */
export const ROADFIT = { asphalt: 1, rail: 2, unpainted: 4, guard: 8, road: 16 } as const;

let roadfitLoading: Promise<Drivable> | null = null;

/** The painted-road masks: at() gives the bits (0 far from every street or off the map, -1 while loading). */
export function loadRoadFit(): Promise<Drivable> {
  if (!roadfitLoading) {
    roadfitLoading = fetch(asset("/data/roadfit/index.json")).then((r) => r.json() as Promise<DrivableIndex>)
      .then((idx) => new DrivableMap(idx, "roadfit", 0, 0));
  }
  return roadfitLoading;
}

/** Tiles kept decoded at most (each 256 KB), least recently used dropped first. */
const DRIVABLE_KEEP = 96;

class DrivableMap implements Drivable {
  private idx: DrivableIndex;
  private have: Set<string>;
  /** Decoded tiles in least recently used order (a Map keeps insertion order); null while loading. */
  private tiles = new Map<string, Uint8Array | null>();

  private dir: string; private outside: number; private off: number;
  /** dir: the data folder; outside: the value where no tile is listed; off: the value off the map. */
  constructor(idx: DrivableIndex, dir = "drivable", outside: number = DRIVABLE.none, off: number = DRIVABLE.unpainted) {
    this.idx = idx; this.have = new Set(idx.tiles); this.dir = dir; this.outside = outside; this.off = off;
  }

  at(x: number, y: number): number {
    const { cell, tile } = this.idx;
    const cx = Math.floor(x / cell), cy = Math.floor(y / cell);
    if (cx < 0 || cy < 0) return this.off;
    const tx = Math.floor(cx / tile), ty = Math.floor(cy / tile), key = `${tx}_${ty}`;
    if (!this.have.has(key)) return tx < this.idx.cols && ty < this.idx.rows ? this.outside : this.off;
    const t = this.tiles.get(key);
    if (t === undefined) { this.fetch(key); return -1; }
    if (t === null) return -1;
    this.tiles.delete(key); this.tiles.set(key, t);   // most recently used last
    return t[(cy - ty * tile) * tile + (cx - tx * tile)];
  }

  private fetch(key: string) {
    this.tiles.set(key, null);
    const img = new Image();
    img.onload = () => {
      const n = this.idx.tile, c = document.createElement("canvas");
      c.width = n; c.height = n;
      const g = c.getContext("2d", { willReadFrequently: true })!;
      g.drawImage(img, 0, 0);
      const px = g.getImageData(0, 0, n, n).data, d = new Uint8Array(n * n);
      for (let i = 0; i < d.length; i++) d[i] = px[i * 4];
      this.tiles.set(key, d);
      while (this.tiles.size > DRIVABLE_KEEP) this.tiles.delete(this.tiles.keys().next().value!);
    };
    img.onerror = () => this.tiles.delete(key);
    img.src = asset(`/data/${this.dir}/${key}.png`);
  }
}
