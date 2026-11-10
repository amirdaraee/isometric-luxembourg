// Landmark cutaways in the viewer (v2/docs/specs/landmark-cutaways.md rule 5): which are on, where their tiles
// lie, and what the slice took. The drawing is in gl/compositor.ts; this file is the logic without WebGL.
//
// A cutaway is a small tile set of its own (release cutaways/<name>/<zoom>/<tile>), listed in index.json under
// "cutaways". While a landmark's cutaway is on, layer 5's pixels of the buildings it replaces are left out (by
// their id) and the cutaway's tiles are drawn as layer 5, at their own depth.

export interface CutPlane { origin: [number, number]; normal: [number, number]; extent: [number, number] }
export interface CutLandmark {
  name: string; slug: string; replaces: string[]; replaces_index: number[]; planes: CutPlane[]; floor_z: number;
  bbox_px: [number, number, number, number]; levels: number; tiles: Record<string, Record<string, number>>;
}
export interface CutawaysIndex {
  files: string[]; k: Record<string, number>; opening_k: number[]; classes: Record<string, number>;
  landmarks: Record<string, CutLandmark>;
}

/** The classes of a building's own pixels in the id tiles (v2/layers/common.py BUILDING_CLASSES). */
export const BUILDING_CLASSES = new Set([11, 12, 13, 14, 22, 23, 24, 25]);

/** The landmarks ?cutaway asks for: absent = none; "?cutaway" alone = all; "?cutaway=a,b" = those that exist. */
export function parseCutaway(value: string | null, names: string[]): string[] {
  if (value === null) return [];
  const want = value.split(",").map((s) => s.trim()).filter(Boolean);
  return want.length ? names.filter((n) => want.includes(n)) : [...names];
}

/** The value of ?cutaway for a set of landmarks: null (none: no parameter), "" (all) or "a,b". */
export function cutawayParam(on: string[], names: string[]): string | null {
  const set = names.filter((n) => on.includes(n));
  return set.length === 0 ? null : set.length === names.length ? "" : set.join(",");
}

/** Does a tile (tx, ty at zoom z) meet a landmark's extent? */
export function tileMeets(bbox: [number, number, number, number], z: number, tx: number, ty: number): boolean {
  const s = 512 * 2 ** z;
  return tx * s <= bbox[2] && (tx + 1) * s > bbox[0] && ty * s <= bbox[3] && (ty + 1) * s > bbox[1];
}

/**
 * The removed slice as half-planes of local (E, N) (relative to the camera's origin): rows (a, b, c), inside where
 * a E + b N > c for every row. As v2/layers/cutaways.py Region: in front of every plane, within its extent.
 */
export function sliceHalfPlanes(lm: CutLandmark, origin: [number, number]): [number, number, number][] {
  const out: [number, number, number][] = [];
  for (const p of lm.planes) {
    const l = Math.hypot(p.normal[0], p.normal[1]);
    const n = [p.normal[0] / l, p.normal[1] / l], t = [-n[1], n[0]];
    const o = [p.origin[0] - origin[0], p.origin[1] - origin[1]];
    const no = n[0] * o[0] + n[1] * o[1], to = t[0] * o[0] + t[1] * o[1];
    out.push([n[0], n[1], no], [t[0], t[1], to + p.extent[0]], [-t[0], -t[1], -(to + p.extent[1])]);
  }
  return out;
}

export function inSlice(half: [number, number, number][], floorZ: number, e: number, n: number, z: number): boolean {
  if (z <= floorZ) return false;
  for (const [a, b, c] of half) if (!(a * e + b * n > c)) return false;
  return true;
}

/**
 * The depth a label or a pointer meets at a pixel while cutaways are on. `buffer` is layer 8 there (the nearest
 * surface of the whole map and its id); when that surface is a replaced building's, the cutaway's own depth at the
 * pixel takes its place (Infinity where the cutaway has nothing: the slice is open to what lies behind).
 */
export function depthWithCutaways(buffer: { depth: number; id: number }, replaced: Set<number>, cutDepth: number): number {
  const cls = buffer.id & 255, obj = buffer.id >>> 8;
  if (!BUILDING_CLASSES.has(cls) || !replaced.has(obj)) return buffer.depth;
  return cutDepth;
}
