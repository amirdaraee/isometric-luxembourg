// Loading the release: index.json, tiles and data files. Data tiles (g.bin, k.bin, i.bin, h.bin) are rows of bytes
// delta-coded per byte and zlib-compressed (v2/layers/common.py pack_bin): decoded exactly with DecompressionStream.

import type { CutawaysIndex } from "./cutaways.ts";

export interface LayerIndex { levels: number; tiles: Record<string, Record<string, number>>; files: string[]; from_zoom?: number }
export interface ReleaseIndex {
  area: string;
  camera: { origin_en: [number, number]; elevation_deg: number; mpp: number; frame: { sx0: number; sy1: number };
    v1_offset_px: [number, number] };
  tile_px: number;
  levels: number;
  layers: Record<string, LayerIndex>;
  depth_cm: [number, number];
  extent_px: [number, number, number, number];
  light: { e0: number; n0: number; step: number; width: number; height: number; zbase: number;
    encoding: { building_unit_m: number; tree_unit_m: number; structure_unit_m: number } };
  night: { windows: number; lamps: number };
  config: LightConfig;
  palette: Record<string, Record<string, { rgb: [number, number, number] }>>;
  polygon_en: [number, number][];
  /** Tunnel view: the tubes' file and their depth range (releases built before it have none). */
  tunnels?: { file: string; tubes: number; casemates: number; depth_cm: [number, number] };
  /** Landmark cutaways: their tiles under cutaways/<name>/ (releases built before them have none). */
  cutaways?: CutawaysIndex;
}
export interface LightConfig {
  march: { t0_m: number; growth: number; steps: number; bias_m: number };
  sun: { wrap: number; ambient: number; direct: number; shadow_keep: number };
  grade: { golden_deg: [number, number]; golden_full_deg: number; blue_deg: [number, number]; night_deg: number;
    day_tint: number[]; golden_tint: number[]; golden_sun_gain: number; golden_amb_tint: number[]; golden_amb_gain: number;
    golden_shadow_soft: number; golden_fill: number; golden_fill_tint: number[]; golden_fill_el_deg: number; shadow_soft_m: [number, number]; blue_tint: number[]; blue_level: number;
    night_tint: number[]; night_level: number; night_desaturate: number; moon_az_el_deg: [number, number];
    moon_tint: number[]; moon_direct: number; moon_shadow: number };
  night: { window_lit_share_evening: number; window_lit_share_late: number; lamp_height_m: number; lamp_radius_px: number;
    depth_eps_m: number; window_gain: number; window_halo: number; window_halo_grow: number; lamp_gain: number;
    church_glow?: number; church_warm?: number };
  /** The sky's light on a cutaway's opening: its level by day, at golden hour and at night (releases before it: none). */
  cutaway?: { sky_day: number; sky_golden: number; sky_night: number };
  seasons: Record<string, { tree: number[]; green: number[]; sat: number }> & { snow_cos: number };
  look: { sat_max: number; lum_min: number; lum_max: number; ink_depth_m: number; ink_normal_cos: number };
  vehicles: Record<string, number | number[]> & { depth_eps_m: number };
  xray?: { opacity: number; depth_step_m: number; depth_steps: number; deep_share: number; ink_px: number; axis_px: number;
    axis_min_px: number; vehicle_side: number };
}

export const BASE = (typeof location !== "undefined" && new URLSearchParams(location.search).get("data")) || "/data/";

export async function fetchJSON<T>(name: string): Promise<T> {
  const r = await fetch(BASE + name);
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  return r.json() as Promise<T>;
}

export async function fetchBytes(name: string): Promise<ArrayBuffer> {
  const r = await fetch(BASE + name);
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  return r.arrayBuffer();
}

/** Undo the per-byte row delta of pack_bin, in place. */
export function undelta(b: Uint8Array, rows: number, bpp: number): Uint8Array {
  const stride = b.length / rows;
  for (let r = 0; r < rows; r++) {
    const o = r * stride;
    for (let i = o + bpp; i < o + stride; i++) b[i] = (b[i] + b[i - bpp]) & 255;
  }
  return b;
}

export async function inflate(buf: ArrayBuffer): Promise<Uint8Array> {
  const ds = new DecompressionStream("deflate");
  const out = new Response(new Blob([buf]).stream().pipeThrough(ds));
  return new Uint8Array(await out.arrayBuffer());
}

/** A data tile: rows x (cols * bpp) bytes. */
export async function fetchBin(name: string, rows: number, bpp: number): Promise<Uint8Array | null> {
  const r = await fetch(BASE + name);
  if (!r.ok) return null;
  return undelta(await inflate(await r.arrayBuffer()), rows, bpp);
}

export async function fetchImage(name: string): Promise<ImageBitmap | null> {
  const r = await fetch(BASE + name);
  if (!r.ok) return null;
  return createImageBitmap(await r.blob(), { premultiplyAlpha: "none", colorSpaceConversion: "none" });
}
