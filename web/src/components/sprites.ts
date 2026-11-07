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
//   const s = await loadSprites();                  // or loadSprites("/sprites/planes.json"), "/events/sprites.json"
//   drawVehicle(g, s, "car", 3, x, y, heading, zoom);
// x, y: screen px of the vehicle's ground centre. heading: direction of travel on screen, Math.atan2(dy, dx) with
// y down (the map is drawn unrotated, so the heading in map pixels is the heading on screen). zoom: screen px per
// map px. The frame nearest the heading is drawn, anchored on its ground centre.
//
// Lamps (lights that the camera can really see): a type may list "lamps", an atlas of the same frames (cells as
// variant 0) holding only the visible lamp pixels, R tail lamps, G headlamps (each with a soft halo) and B window
// glass lit at night; see pipeline/build_sprites.py. Draw them after the vehicle:
//   drawLamps(g, s, "car", x, y, heading, zoom, { tail: 1, brake: 0, head: 1 });
// Each strength is 0..1 and adds light ("lighter"). Far out, where a lamp is under a screen pixel, each visible lamp
// is drawn as one soft dot instead (lamp_dots). Other sprite files (events, planes) may use the same format.
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
  /** Lamp atlas (see above), cells as variant 0. */
  lamps?: string;
  /** Per lamp class and heading, the frame px of each visible lamp. */
  lamp_dots?: { tail?: [number, number][][]; head?: [number, number][][] };
}

export interface Sprites {
  /** metres per sprite px */
  mpp: number;
  /** metres per map px */
  map_mpp: number;
  headings: number;
  types: Record<string, SpriteType>;
  images: Record<string, HTMLImageElement>;
  /** Per type with lamps: the lamp atlas split into one tinted, alpha-masked canvas per class. */
  lamps: Record<string, LampCanvases>;
}

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const im = new Image();
    im.onload = () => resolve(im);
    im.onerror = () => reject(new Error(`sprite atlas failed to load: ${url}`));
    im.src = url;
  });
}

/** Loads a sprite file (a path inside public/) and every atlas it names. Atlas paths are relative to the file. */
export async function loadSprites(file = "/sprites/sprites.json"): Promise<Sprites> {
  const r = await fetch(asset(file));
  if (!r.ok) throw new Error(`${file}: HTTP ${r.status}`);
  const meta = (await r.json()) as Omit<Sprites, "images">;
  const dir = file.slice(0, file.lastIndexOf("/") + 1);
  const names = Object.keys(meta.types);
  const imgs = await Promise.all(names.map((n) => loadImage(asset(`${dir}${meta.types[n].image}`))));
  const images: Record<string, HTMLImageElement> = {};
  names.forEach((n, i) => (images[n] = imgs[i]));
  const lamps: Record<string, LampCanvases> = {};
  await Promise.all(names.filter((n) => meta.types[n].lamps).map(async (n) => {
    try { lamps[n] = tintLamps(await loadImage(asset(`${dir}${meta.types[n].lamps}`))); } catch { /* no lamps then */ }
  }));
  return { ...meta, images, lamps };
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

// ---------------------------------------------------------------------------------------------------------------
// Lamps

export interface LampCanvases { tail: HTMLCanvasElement; head: HTMLCanvasElement; glass: HTMLCanvasElement }
export interface LampStrengths {
  /** Tail lamps (on at night). */
  tail?: number;
  /** Brake lights: the tail lamps brighter. */
  brake?: number;
  /** Headlamps. */
  head?: number;
  /** Lit windows (trams and trains at night). */
  glass?: number;
}

/** Lamp colours, rgb. */
const LAMP_TINT = { tail: [255, 34, 24], head: [255, 238, 196], glass: [255, 196, 112] } as const;

/** Splits a lamp atlas (R tail, G head, B glass) into one canvas per class: the lamp colour, the channel as alpha. */
function tintLamps(im: HTMLImageElement): LampCanvases {
  const w = im.width, h = im.height;
  const src = document.createElement("canvas");
  src.width = w; src.height = h;
  const sg = src.getContext("2d", { willReadFrequently: true })!;
  sg.drawImage(im, 0, 0);
  const px = sg.getImageData(0, 0, w, h).data;
  src.width = src.height = 0;
  const one = (ch: number, rgb: readonly number[]) => {
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d")!;
    const out = g.createImageData(w, h), d = out.data;
    for (let i = 0; i < d.length; i += 4) {
      const a = px[i + ch];
      if (!a) continue;
      d[i] = rgb[0]; d[i + 1] = rgb[1]; d[i + 2] = rgb[2]; d[i + 3] = a;
    }
    g.putImageData(out, 0, 0);
    return c;
  };
  return { tail: one(0, LAMP_TINT.tail), head: one(1, LAMP_TINT.head), glass: one(2, LAMP_TINT.glass) };
}

/** Screen px per sprite px below which lamps are drawn as soft dots (a lamp is then under about half a pixel). */
const DOTS_BELOW = 0.25;

/**
 * Lights the lamps of one vehicle drawn with drawVehicle at the same (x, y, heading, zoom): only the lamp pixels the
 * camera sees at that heading, added on top ("lighter"). Types without a lamp atlas are skipped.
 */
export function drawLamps(g: CanvasRenderingContext2D, s: Sprites, type: string, x: number, y: number,
  headingScreenRad: number, zoom: number, on: LampStrengths): void {
  const t = s.types[type], lc = s.lamps[type];
  if (!t || !lc) return;
  const tail = Math.min(1, (on.tail ?? 0) + (on.brake ?? 0)), brake = on.brake ?? 0, head = on.head ?? 0, glass = on.glass ?? 0;
  if (tail <= 0.01 && head <= 0.01 && glass <= 0.01) return;
  const hi = headingIndex(s, headingScreenRad);
  const [cx, cy] = t.cells[0][hi];
  const [w, h] = t.frame;
  const k = (zoom * s.mpp) / s.map_mpp;  // screen px per sprite px
  const x0 = x - t.anchor[0] * k, y0 = y - t.anchor[1] * k;
  const prevOp = g.globalCompositeOperation, prevA = g.globalAlpha;
  g.globalCompositeOperation = "lighter";
  // strengths multiply the alpha the vehicle itself is drawn with (a vehicle fading out takes its lights along)
  const sheet = (c: HTMLCanvasElement, a: number) => {
    if (a <= 0.01) return;
    g.globalAlpha = Math.min(1, a) * prevA;
    g.drawImage(c, cx, cy, w, h, x0, y0, w * k, h * k);
  };
  if (k >= DOTS_BELOW) {
    sheet(lc.tail, tail);
    sheet(lc.tail, brake * 0.7);   // brake lights: the same lamps, brighter
    sheet(lc.head, head);
    sheet(lc.glass, glass);
  } else {
    // Far out: one soft dot per visible lamp, at its place on the body.
    const dots = (list: [number, number][] | undefined, rgb: readonly number[], a: number) => {
      if (!list || a <= 0.01) return;
      const r = 1.6;
      for (const [dx, dy] of list) {
        const px = x0 + dx * k, py = y0 + dy * k;
        const gr = g.createRadialGradient(px, py, 0, px, py, r);
        gr.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${Math.min(1, a)})`);
        gr.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
        g.globalAlpha = prevA;
        g.fillStyle = gr;
        g.fillRect(px - r, py - r, 2 * r, 2 * r);
      }
    };
    dots(t.lamp_dots?.tail?.[hi], LAMP_TINT.tail, tail * 0.8 + brake * 0.4);
    dots(t.lamp_dots?.head?.[hi], LAMP_TINT.head, head * 0.8);
    sheet(lc.glass, glass);
  }
  g.globalCompositeOperation = prevOp;
  g.globalAlpha = prevA;
}
