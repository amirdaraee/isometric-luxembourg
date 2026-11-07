/**
 * Feature switches. Every optional part of the map can be turned off without touching the code that uses it.
 *
 * Three ways to turn a feature off, later ones win:
 *   1. Edit DEFAULTS below (the release default).
 *   2. At build time: VITE_FEATURES_OFF="christmas,transit" npm run build   (or VITE_FEATURES_ON to force on).
 *   3. In the browser, for testing: ?off=christmas,transit  or  ?on=christmas
 */
export const DEFAULTS = {
  /** Time slider and live Luxembourg clock: night, golden hour, cross-fades. Off = always day. */
  timeOfDay: true,
  /** Spring / summer / autumn / winter buttons and the painted season versions. Off = always summer. */
  seasons: true,
  /** Christmas market toggle (Winterlights) on the old-town squares. */
  christmas: true,
  /** Falling snow in winter. */
  snow: true,
  /** Cars on the streets. */
  traffic: true,
  /** Trams and trains on today's timetable (GTFS). */
  transit: true,
  /** Light glinting on the rivers and ponds (animated, drawn over the painted water). */
  water: true,
  /** Flocks of birds over the valleys (by day). */
  birds: true,
  /** Tilt-shift: the screen's top and bottom edges softly blurred, like a miniature photo. */
  tiltShift: true,
  /** "Streets" layer with street names. */
  streets: true,
  /** Place pins with labels. */
  pins: true,
  /** Search box for places, streets and addresses. */
  search: true,
  /** "Surprise me" button. */
  surprise: true,
  /** Share button (copies the link to the current view). */
  share: true,
  /** Landmark cards (story, inside, 3D, photos). Off = a short name card instead. */
  landmarks: true,
  /** Inside tab of landmark cards: interiors and cutaway drawings. */
  interiors: true,
  /** 3D tab of landmark cards (loads three.js on demand). */
  models3d: true,
  /** Photos tab of landmark cards. */
  photos: true,
  /** "Preview" badge in the corner while the art is not final. */
  previewBadge: true,
};

export type Feature = keyof typeof DEFAULTS;

function list(s: string | null | undefined): string[] {
  return (s ?? "").split(",").map((x) => x.trim()).filter(Boolean);
}

function resolve(): Record<Feature, boolean> {
  const f = { ...DEFAULTS };
  const q = new URLSearchParams(location.search);
  const apply = (names: string[], on: boolean) => {
    for (const n of names) if (n in f) f[n as Feature] = on;
  };
  apply(list(import.meta.env.VITE_FEATURES_OFF), false);
  apply(list(import.meta.env.VITE_FEATURES_ON), true);
  apply(list(q.get("off")), false);
  apply(list(q.get("on")), true);
  return f;
}

export const features = resolve();
export const on = (f: Feature) => features[f];
