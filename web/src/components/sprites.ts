// Vehicle sprites: little box models pre-rendered by pipeline/build_sprites.py with the map's own projection at
// 32 screen headings, inked and shaded like the painting, each with its soft ground shadow (cast towards the lower
// right, from the map's upper-left sun) baked in.
//
// Files: public/sprites/sprites.json and one atlas PNG per type. Sprites are drawn at 0.125 m per sprite pixel,
// twice the map's resolution (0.25 m per map pixel), so they stay sharp when zoomed in.
//
// Types and colour variants (variant index = position in sprites.json "variants"):
//   car          red, blue, white, black, silver, yellow, green, teal   (4.4 m)
//   van          white, silver, blue                                     (5.5 m)
//   bus          avl (light blue), rgtr (green)                          (12 m)
//   police       Luxembourg Police, blue and yellow checks, light bar     (4.5 m)
//   ambulance    CGDIS, yellow and red / yellow and green checks           (5.8 m)
//   fire         CGDIS fire engine, red with white stripes, roof ladder    (9 m)
//   tram_end     Luxtram cab section, nose at the front                  (9 m)
//   tram_mid     Luxtram middle section                                  (9 m)
//   train_cab    CFL double-deck driving car, red nose at the front      (26 m)
//   train_coach  CFL double-deck middle coach                            (26 m)
//   train_loco   CFL electric locomotive, cabs at both ends              (19 m)
// Colours are rendered out in full rather than tinted, so shading and outlines stay right; pick one per vehicle.
//
// Use:
//   const s = await loadSprites();
//   drawVehicle(g, s, "car", 3, x, y, heading, zoom);
// x, y: screen px of the vehicle's ground centre. heading: direction of travel on screen, Math.atan2(dy, dx) with
// y down (the map is drawn unrotated, so the heading in map pixels is the heading on screen). zoom: screen px per
// map px. The frame nearest the heading is drawn, anchored on its ground centre.
//
// Chaining a tram or train: place each section's centre along the track polyline one section length apart
// (length_m / 0.25 map px, see spriteLength), each with its own local heading. A tram is tram_end, 3 x tram_mid,
// tram_end with the last one drawn at heading + PI (its nose pointing backwards). A CFL push-pull set is
// train_cab, n x train_coach, train_loco. Draw the sections from the back of the screen (smallest y) forwards so
// nearer ones overlap farther ones.
import { asset } from "../config";

export interface SpriteType {
  image: string;
  length_m: number;
  /** frame width and height, sprite px */
  frame: [number, number];
  /** sprite px of the ground centre within a frame */
  anchor: [number, number];
  variants: string[];
  /** screen heading of each frame, radians */
  heading: number[];
  /** cells[variant][heading index] = top-left of the frame in the atlas, sprite px */
  cells: [number, number][][];
  note?: string;
}

export interface Sprites {
  /** metres per sprite px */
  mpp: number;
  /** metres per map px */
  map_mpp: number;
  headings: number;
  types: Record<string, SpriteType>;
  images: Record<string, HTMLImageElement>;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error(`sprite atlas failed to load: ${url}`));
    im.src = url;
  });
}

/** Loads sprites.json and every atlas it names. */
export async function loadSprites(): Promise<Sprites> {
  const r = await fetch(asset("/sprites/sprites.json"));
  if (!r.ok) throw new Error(`sprites.json: HTTP ${r.status}`);
  const meta = (await r.json()) as Omit<Sprites, "images">;
  const names = Object.keys(meta.types);
  const imgs = await Promise.all(names.map((n) => loadImage(asset(`/sprites/${meta.types[n].image}`))));
  const images: Record<string, HTMLImageElement> = {};
  names.forEach((n, i) => (images[n] = imgs[i]));
  return { ...meta, images };
}

/** A type's length in map px (handy for spacing tram and train sections). */
export function spriteLength(s: Sprites, type: string): number {
  return s.types[type].length_m / s.map_mpp;
}

/** Index of the frame whose screen heading is nearest `headingScreenRad`. */
export function headingIndex(s: Sprites, headingScreenRad: number): number {
  const n = s.headings;
  const i = Math.round((headingScreenRad / (2 * Math.PI)) * n);
  return ((i % n) + n) % n;
}

/** Draws one vehicle anchored at screen (x, y), its ground centre, scaled for `zoom` screen px per map px.
 * Unknown types are skipped; the variant wraps round the type's variants. */
export function drawVehicle(g: CanvasRenderingContext2D, s: Sprites, type: string, variant: number,
  x: number, y: number, headingScreenRad: number, zoom: number): void {
  const t = s.types[type];
  const im = s.images[type];
  if (!t || !im) return;
  const nv = t.variants.length;
  const v = ((Math.floor(variant) % nv) + nv) % nv;
  const [cx, cy] = t.cells[v][headingIndex(s, headingScreenRad)];
  const [w, h] = t.frame;
  const k = (zoom * s.mpp) / s.map_mpp;  // screen px per sprite px
  g.drawImage(im, cx, cy, w, h, x - t.anchor[0] * k, y - t.anchor[1] * k, w * k, h * k);
}
