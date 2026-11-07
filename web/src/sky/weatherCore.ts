// The weather model without the browser: kinds, the ?weather= text, the WMO weather codes of the live forecast,
// and the amounts each layer draws. Kept free of DOM and Vite imports so that weatherCore.test.ts runs in Node.

export type Kind = "clear" | "cloudy" | "rain" | "storm" | "snow" | "fog";
export const KINDS: Kind[] = ["clear", "cloudy", "rain", "storm", "snow", "fog"];

export interface Wind {
  /** metres per second */
  speed: number;
  /** degrees the wind comes from (meteorological: 0 north, 90 east, 270 west) */
  from: number;
}

export interface Weather {
  kind: Kind;
  /** 0 .. 1: how much rain, snow or fog */
  intensity: number;
  wind: Wind;
  /** 0 .. 1 cloud cover */
  cloud: number;
  /** km */
  visibilityKm: number;
}

/** What the layers draw, each 0 .. 1, plus the wind. Blended over time between two weathers. */
export interface Amounts {
  rain: number;
  snow: number;
  /** lightning */
  storm: number;
  fog: number;
  /** dull, overcast light */
  overcast: number;
  /** wind, as a vector the air moves towards: m/s east and north */
  windE: number;
  windN: number;
}

/** The usual weather here: light south-west wind, a few clouds. */
export const CLEAR: Weather = { kind: "clear", intensity: 0, wind: { speed: 3, from: 240 }, cloud: 0.2, visibilityKm: 30 };

/** Typical cloud and visibility for a kind, when only the kind and intensity are known. */
export function weatherOf(kind: Kind, intensity = 0.7, wind: Wind = CLEAR.wind): Weather {
  const i = Math.max(0, Math.min(1, intensity));
  switch (kind) {
    case "clear": return { kind, intensity: 0, wind, cloud: 0.15, visibilityKm: 30 };
    case "cloudy": return { kind, intensity: i, wind, cloud: 0.5 + 0.5 * i, visibilityKm: 20 };
    case "rain": return { kind, intensity: i, wind, cloud: 0.9, visibilityKm: 12 - 8 * i };
    case "storm": return { kind, intensity: i, wind: { ...wind, speed: Math.max(wind.speed, 8 + 8 * i) }, cloud: 1, visibilityKm: 6 - 3 * i };
    case "snow": return { kind, intensity: i, wind, cloud: 0.95, visibilityKm: 6 - 4 * i };
    case "fog": return { kind, intensity: i, wind: { ...wind, speed: Math.min(wind.speed, 2) }, cloud: 0.6, visibilityKm: Math.max(0.1, 1.5 - 1.4 * i) };
  }
}

/**
 * Parses the ?weather= text: a kind with an optional intensity, then an optional wind in m/s from a direction,
 * separated by commas. Examples: "rain:0.8,wind:12@250", "storm:1", "fog:0.9", "clear,wind:6@80". Unknown parts
 * are ignored; null when no kind is given.
 */
export function parseWeather(text: string | null | undefined): Weather | null {
  if (!text) return null;
  let kind: Kind | null = null, intensity = 0.7;
  let wind: Wind | null = null;
  for (const part of text.split(",").map((s) => s.trim().toLowerCase())) {
    const m = part.match(/^wind:([\d.]+)(?:@([\d.]+))?$/);
    if (m) { wind = { speed: Number(m[1]), from: Number(m[2] ?? CLEAR.wind.from) % 360 }; continue; }
    const k = part.match(/^([a-z]+)(?::([\d.]+))?$/);
    if (k && (KINDS as string[]).includes(k[1])) { kind = k[1] as Kind; if (k[2] !== undefined) intensity = Number(k[2]); }
  }
  if (!kind) return null;
  return weatherOf(kind, intensity, wind ?? (kind === "storm" ? { speed: 14, from: 250 } : CLEAR.wind));
}

/** The current conditions of the Open-Meteo forecast API ("current" block), the fields asked for. */
export interface OpenMeteoCurrent {
  weather_code: number;
  precipitation?: number;   // mm in the last hour
  wind_speed_10m?: number;  // asked for in m/s
  wind_direction_10m?: number;
  cloud_cover?: number;     // %
  visibility?: number;      // m
}

/**
 * The weather from a WMO weather code (as Open-Meteo reports it) and the other current values. Codes:
 * 0 clear; 1-3 mainly clear to overcast; 45, 48 fog; 51-57 drizzle; 61-67 rain; 71-77 snow; 80-82 rain showers;
 * 85, 86 snow showers; 95-99 thunderstorm. Visibility under 1 km is fog too.
 */
export function fromWmo(c: OpenMeteoCurrent): Weather {
  const code = c.weather_code;
  const wind: Wind = { speed: c.wind_speed_10m ?? CLEAR.wind.speed, from: c.wind_direction_10m ?? CLEAR.wind.from };
  const cloud = c.cloud_cover !== undefined ? c.cloud_cover / 100 : null;
  const vis = c.visibility !== undefined ? c.visibility / 1000 : null;
  const mm = c.precipitation ?? 0;
  let w: Weather;
  if (code >= 95) w = weatherOf("storm", code >= 96 ? 1 : 0.7, wind);
  else if ((code >= 71 && code <= 77) || code === 85 || code === 86) w = weatherOf("snow", code === 75 || code === 86 ? 0.9 : code === 73 ? 0.6 : 0.35, wind);
  else if (code >= 51 && code <= 67) {
    // drizzle light, rain by its last digit (1 slight, 3 moderate, 5 heavy), or by the measured amount
    const base = code <= 57 ? 0.2 : code % 10 === 5 ? 0.9 : code % 10 === 3 ? 0.6 : 0.35;
    w = weatherOf("rain", Math.max(base, Math.min(1, mm / 6)), wind);
  } else if (code >= 80 && code <= 82) w = weatherOf("rain", code === 82 ? 1 : code === 81 ? 0.65 : 0.4, wind);
  else if (code === 45 || code === 48 || (vis !== null && vis < 1)) w = weatherOf("fog", vis !== null ? Math.min(1, Math.max(0.4, 1 - vis)) : 0.8, wind);
  else if (code === 3) w = weatherOf("cloudy", 0.9, wind);
  else if (code === 2) w = weatherOf("cloudy", 0.4, wind);
  else w = weatherOf("clear", 0, wind);
  if (cloud !== null) w.cloud = cloud;
  if (vis !== null) w.visibilityKm = vis;
  return w;
}

/** What each layer draws for a weather. */
export function amountsOf(w: Weather): Amounts {
  const rad = ((w.wind.from + 180) % 360) * Math.PI / 180; // the direction the air moves towards
  const i = w.intensity;
  return {
    rain: w.kind === "rain" ? i : w.kind === "storm" ? 0.6 + 0.4 * i : 0,
    snow: w.kind === "snow" ? i : 0,
    storm: w.kind === "storm" ? i : 0,
    fog: w.kind === "fog" ? i : Math.max(0, Math.min(1, (3 - w.visibilityKm) / 3)) * 0.4,
    overcast: Math.max(0, Math.min(1, (w.cloud - 0.4) / 0.6)) * (w.kind === "clear" ? 0.3 : 1),
    windE: Math.sin(rad) * w.wind.speed,
    windN: Math.cos(rad) * w.wind.speed,
  };
}

/** Moves `a` towards `b` by the fraction f (0 .. 1). */
export function blend(a: Amounts, b: Amounts, f: number): Amounts {
  const o = {} as Amounts;
  for (const k of Object.keys(b) as (keyof Amounts)[]) o[k] = a[k] + (b[k] - a[k]) * f;
  return o;
}

/**
 * A movement on the ground (metres east and north) as screen pixels per metre of the map's view from the south-east
 * (as pipeline/project_lines.py: x grows with east + north, y with east - north, halved). Returns [x, y] per metre,
 * at 0.25 m per map pixel.
 */
export function groundToScreen(e: number, n: number): [number, number] {
  const R = Math.SQRT1_2 / 0.25;
  return [(e + n) * R, (e - n) * R * 0.5];
}
