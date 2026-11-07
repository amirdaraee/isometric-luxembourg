// One weather for every layer (rain, lightning, snow, fog, the clouds' drift, the water's glints, the runway the
// planes use). It comes, in order of precedence, from:
//   1. ?weather=rain:0.8,wind:12@250 in the address (tests; shown at once, no blending);
//   2. the picker (WeatherControl): a kind, or "Live";
//   3. the live forecast for the city: Open-Meteo (free, no key, CC BY 4.0), fetched at most every 15 minutes and
//      kept in sessionStorage, so a visitor makes one request per quarter of an hour.
// Without the weather switch it is always clear, with the usual light south-west wind.
// Changes blend over 20 s for the live weather and 3 s for the picker, so rain starts softly.
//
//   const w = currentAmounts();          // what to draw now: rain, snow, storm, fog, overcast, wind (eased)
//   const off = onWeather(() => ...);    // the target weather changed
import { on } from "./features";
import { testParams } from "./testParams";
import { CLEAR, amountsOf, blend, fromWmo, parseWeather, weatherOf, type Amounts, type Kind, type Weather } from "./sky/weatherCore";

export type { Amounts, Kind, Weather } from "./sky/weatherCore";

export type Mode = "live" | Kind;

const URL_LIVE = "https://api.open-meteo.com/v1/forecast?latitude=49.61&longitude=6.13" +
  "&current=weather_code,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,visibility&wind_speed_unit=ms";
const CACHE_KEY = "isolux.weather";
const EVERY_MS = 15 * 60 * 1000;

const fixed = on("weather") ? parseWeather(testParams.weather) : null;

let mode: Mode = "live";
let live: Weather = CLEAR;
let liveOk = false;
let picked: Weather = CLEAR;
let windOverride: number | null = null;   // m/s from the picker's slider

let target: Weather = fixed ?? CLEAR;
let from: Amounts = amountsOf(target);
let to: Amounts = from;
let since = 0, blendMs = 0;
const listeners = new Set<() => void>();

function now() { return performance.now(); }

function retarget(ms: number) {
  const w = fixed ?? (!on("weather") ? CLEAR : mode === "live" ? live : picked);
  const next = windOverride !== null && !fixed ? { ...w, wind: { ...w.wind, speed: windOverride } } : w;
  from = currentAmounts();
  target = next;
  to = amountsOf(next);
  since = now();
  blendMs = ms;
  for (const fn of listeners) fn();
}

/** The weather being shown (or blended towards). */
export function weather(): Weather { return target; }
/** Live or a picked kind. */
export function weatherMode(): Mode { return mode; }
/** True when the address fixes the weather (?weather=): the picker is then for show only. */
export const weatherFixed = fixed !== null;
/** True once the live forecast has answered. */
export function liveAvailable(): boolean { return liveOk; }
/** The wind speed set with the picker's slider, or null for the weather's own. */
export function windSetting(): number | null { return windOverride; }

/** What to draw now, blended between the previous weather and the current one. */
export function currentAmounts(): Amounts {
  if (blendMs <= 0) return to;
  const f = Math.min(1, (now() - since) / blendMs);
  // smooth start and end
  return blend(from, to, f * f * (3 - 2 * f));
}

/** Calls `fn` whenever the weather changes. Returns an unsubscribe. */
export function onWeather(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/** The picker: "live", or a kind at a moderate intensity. */
export function setWeatherMode(m: Mode) {
  mode = m;
  if (m !== "live") picked = weatherOf(m, m === "storm" ? 0.9 : m === "fog" ? 0.85 : m === "cloudy" ? 0.8 : 0.65, live.wind);
  retarget(3000);
}

/** The picker's wind slider, m/s (null: the weather's own wind). */
export function setWind(speed: number | null) {
  windOverride = speed;
  retarget(3000);
}

async function fetchLive() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) ?? "null") as { t: number; w: Weather } | null;
    if (cached && Date.now() - cached.t < EVERY_MS) { live = cached.w; liveOk = true; if (mode === "live") retarget(0); return; }
  } catch { /* no storage: fetch */ }
  try {
    const r = await fetch(URL_LIVE);
    if (!r.ok) return;
    const d = await r.json() as { current?: Parameters<typeof fromWmo>[0] };
    if (!d.current) return;
    const first = !liveOk;
    live = fromWmo(d.current);
    liveOk = true;
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), w: live })); } catch { /* private mode */ }
    if (mode === "live") retarget(first ? 0 : 20000);
  } catch { /* offline: stay as it is */ }
}

if (on("weather") && !fixed) {
  fetchLive();
  setInterval(fetchLive, EVERY_MS);
}
