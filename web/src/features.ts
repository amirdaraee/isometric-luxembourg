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
  /** Police cars, ambulances and fire engines in the traffic, some on a call with blue lights (needs traffic). */
  emergency: true,
  /** Tiny traffic lights at signalised junctions when zoomed in (needs traffic). */
  signals: true,
  /** Trams and trains on today's timetable (GTFS). */
  transit: true,
  /** Light glinting on the rivers and ponds (animated, drawn over the painted water). */
  water: true,
  /** Flocks of birds over the valleys (by day). */
  birds: true,
  /** A soft sea of cloud seen from above, filling everything outside the map. */
  clouds: true,
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
  /** "Mark a spot" button: draw a box on the map and send the author a private note (needs the feedback worker). */
  comments: true,

  // Vehicles and rail
  // (The fixes for cars and trains sit inside traffic, transit and emergency, so they need no new switch.)

  // Art and events
  /** The moving cabin of the Pfaffenthal Panoramic Lift. */
  liftCabin: true,
  /** Moving rides and twinkling lights in event patches (Christmas first). */
  eventRides: true,
  /** The event calendar and picker for events other than Christmas (master switch for the events below). */
  events: true,
  /** New Year's Eve: Christmas still up, light sparkles at midnight. */
  newYear: true,
  /** National Day (22 and 23 June): flags, torches along the procession route, fireworks over the Pétrusse. */
  nationalDay: true,
  /** Schueberfouer, the funfair on the Glacis (late August to early September). */
  schueberfouer: true,
  /** Octave and its Mäertchen: stalls and a covered terrace on the Knuedler (spring). */
  octave: true,
  /** Éimaischen, the Easter Monday pottery and craft market on the Fëschmaart. */
  emaischen: true,
  /** ING Night Marathon: a glowing stream of runners through the city. */
  marathon: true,
  /** Halloween: pumpkins, an orange-lit Neimënster at night, bats. */
  halloween: true,
  /** Buergbrennen: bonfires at dusk, with smoke. */
  buergbrennen: true,
  /** Music stages with lighting rigs (Fête de la Musique and Rock um Knuedler). */
  musicStages: true,
  /** Firework displays (National Day, Schueberfouer closing night, New Year's Eve). */
  fireworks: true,

  // Performance, weather and sky
  /** Rain, storm, wind and snow from the live weather or the picker. */
  weather: true,
  /** Valley fog and haze (needs weather). */
  fog: true,
  /** Cargolux and Luxair aircraft over the city. */
  planes: true,
  /** Automatically lowers the effect quality on slow devices. */
  adaptiveQuality: true,
  /** Layered-map proof of concept for the old town (LAYERS_POC.md): local dev server only, with ?layers. */
  layersPoc: true,
  /** Frame-time readout for testing. Off everywhere unless asked for with ?on=perfHud. */
  perfHud: false,
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
