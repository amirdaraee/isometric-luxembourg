// The hour's light as numbers (layers 9 and 10): what the light pass is given for a sun elevation. Pure, so it is
// tested without a browser (src/grade.test.ts). The constants are v2/config/light.json's.
import type { LightConfig } from "../data.ts";

type V3 = [number, number, number];
export interface Grade {
  sun: V3;        // the sun's colour times its gain (multiplies sun.direct)
  amb: V3;        // the sky's colour times its level (multiplies sun.ambient)
  fill: number;   // the low sun's light coming back from the opposite sky (0 by day and at night)
  soft: number;   // how far a long shadow fades with the distance to what casts it (0 by day)
  moon: number;   // the moon's light (0 until the sun is 1 degree down, full at night)
  moonDir: V3;    // towards the moon (E, N, up)
  desat: number;  // how much colour the night takes out
  open: V3;       // the light on a cutaway's opening: the sky's colour times its level there (multiplies sun.ambient)
}

/** The hour's light by the sun's elevation (layer-09 rule 3, layer-10 rule 4; light.json "grade"). Day is one
 * constant; from there every value moves without a step through the golden hour, the blue hour and into the night. */
export function grade(cfg: LightConfig, el: number): Grade {
  const G = cfg.grade;
  const c01 = (t: number) => Math.max(0, Math.min(1, t));
  const mix = (a: number[], b: number[], t: number) => a.map((v, i) => v + (b[i] - v) * c01(t)) as V3;
  const mul = (a: number[], k: number) => a.map((v) => v * k) as V3;
  const [az, me] = G.moon_az_el_deg.map((d) => (d * Math.PI) / 180);
  const moonDir: V3 = [Math.sin(az) * Math.cos(me), Math.cos(az) * Math.cos(me), Math.sin(me)];
  // a cutaway's opening is lit by the sky only (landmark-cutaways.md rule 3; light.json "cutaway"): the hour's sky
  // light times a level for the day, the golden hour and the night, moving between them as the sky's colour does
  const K = cfg.cutaway ?? { sky_day: 1, sky_golden: 1, sky_night: 1 };
  const day: Grade = { sun: G.day_tint as V3, amb: [1, 1, 1], fill: 0, soft: 0, moon: 0, moonDir, desat: 0, open: mul([1, 1, 1], K.sky_day) };
  if (el >= G.golden_deg[1]) return day;
  // golden hour: full from golden_full_deg down to the horizon
  const g = c01((G.golden_deg[1] - el) / (G.golden_deg[1] - G.golden_full_deg));
  const goldSun = mul(mix(G.day_tint, G.golden_tint, g), 1 + (G.golden_sun_gain - 1) * g);
  const goldAmb = mul(mix([1, 1, 1], G.golden_amb_tint, g), 1 + (G.golden_amb_gain - 1) * g);
  if (el >= G.golden_deg[0]) return { ...day, sun: goldSun, amb: goldAmb, fill: G.golden_fill * g, soft: G.golden_shadow_soft * g,
    open: mul(goldAmb, K.sky_day + (K.sky_golden - K.sky_day) * g) };
  // below the horizon: the warm sky cools to the blue hour by half way down, then deepens into the night
  const blue = mul(G.blue_tint, G.blue_level), night = mul(G.night_tint, G.night_level);
  const t = c01(el / G.night_deg);
  const amb = t < 0.5 ? mix(goldAmb, blue, t * 2) : mix(blue, night, t * 2 - 1);
  const m = c01((-el - 1) / (-G.night_deg - 1));
  return { sun: goldSun, amb, fill: G.golden_fill * c01(1 - t * 2), soft: G.golden_shadow_soft, moon: G.moon_direct * m, moonDir, desat: G.night_desaturate * m,
    open: mul(amb, K.sky_golden + (K.sky_night - K.sky_golden) * t) };
}

/** How much the night lights show: none with the sun up (layer-10 rule 3), full from civil twilight's end. */
export function nightFactor(cfg: LightConfig, el: number): number {
  if (el > 0) return 0;
  return Math.max(0, Math.min(1, -el / -cfg.grade.night_deg));
}

/** Share of windows lit by the hour: homes in the evening, few after midnight; shops until 20:00. */
export function litShare(cfg: LightConfig, hour: number) {
  const N = cfg.night;
  const evening = hour >= 16 || hour < 0.5;
  const late = hour >= 0.5 && hour < 6;
  const homes = late ? N.window_lit_share_late : evening ? N.window_lit_share_evening : 0.3;
  const shops = hour >= 7 && hour < 20 ? 0.9 : 0.08;
  return { homes, shops };
}
