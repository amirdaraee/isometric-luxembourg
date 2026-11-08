// Time of day and season: which painted map versions to show and how strongly, plus a colour grade for the
// moments we don't paint separately (morning, noon, blue hour, spring/autumn nights...).
import { today } from "./testParams.ts";

export type Season = "spring" | "summer" | "autumn" | "winter";
export type Variant = "day" | "golden" | "night" | "winter" | "winter_night" | "autumn" | "spring";
export interface SceneState {
  hour: number; season: Season; christmas: boolean;
  /** an event picked in the Events menu (a preview, any day of the year), or null to follow the calendar */
  event?: string | null;
}

// Luxembourg (49.6 N): sunrise/sunset by month, local time (rough, enough for lighting)
const SUN: [number, number][] = [[8.3, 16.9], [7.7, 17.7], [7.0, 18.5], [6.9, 20.4], [6.1, 21.1], [5.5, 21.7],
  [5.7, 21.6], [6.4, 20.9], [7.2, 19.8], [8.0, 18.7], [7.8, 16.9], [8.4, 16.5]];

export function sunTimes(d = today()): [number, number] {
  return SUN[d.getMonth()];
}

export function seasonOf(d = today()): Season {
  const m = d.getMonth();
  return m <= 1 || m === 11 ? "winter" : m <= 4 ? "spring" : m <= 7 ? "summer" : "autumn";
}

/** The middle month of each season (0 = January), for its sunrise and sunset. */
const SEASON_MONTH: Record<Season, number> = { winter: 0, spring: 3, summer: 6, autumn: 9 };

/**
 * Sunrise and sunset for the season shown: today's while the season is today's (or the month next to it: late
 * November with the Christmas markets in winter), else the middle month of that season, so that winter picked in
 * July has dark evenings and summer picked in December light ones.
 */
export function sunFor(season: Season, d = today()): [number, number] {
  const m = d.getMonth(), mid = SEASON_MONTH[season];
  const near = [mid - 2, mid - 1, mid, mid + 1, mid + 2].some((x) => (x + 12) % 12 === m);
  return SUN[near ? m : mid];
}

/** Season each event belongs to (its patches are painted on that season's art); calendar.ts EVENT_SEASON. */
type EventSeasons = Partial<Record<string, Season>>;

/**
 * The scene after a change from the controls, kept consistent so that no button is lit for something not shown:
 *   - Christmas switched on brings winter (the markets are painted on the winter art);
 *   - a season other than winter switches Christmas off;
 *   - an event that belongs to another season than the one now shown is dropped.
 * The clock is not touched here: only a change of hour leaves live time (App.tsx).
 */
export function changeScene(s: SceneState, c: Partial<SceneState>, eventSeason: EventSeasons): SceneState {
  const next: SceneState = { ...s, ...c };
  if (c.christmas && c.season === undefined) next.season = "winter";
  if (c.season !== undefined && c.season !== "winter" && c.christmas === undefined) next.christmas = false;
  if (next.event && (eventSeason[next.event] ?? next.season) !== next.season) next.event = null;
  return next;
}

/** Winterlights: Friday before the last Sunday before Advent .. first Sunday of January (research/05-events). */
export function christmasOn(d = today()): boolean {
  const y = d.getMonth() === 0 ? d.getFullYear() - 1 : d.getFullYear();
  const xmas = new Date(y, 11, 25);
  const advent1 = new Date(y, 11, 25 - ((xmas.getDay() || 7) + 21));   // 4th Sunday before Christmas
  const start = new Date(advent1); start.setDate(advent1.getDate() - 9);
  const jan1 = new Date(y + 1, 0, 1);
  const end = new Date(y + 1, 0, 1 + ((7 - jan1.getDay()) % 7));      // first Sunday of January
  end.setHours(23, 59);
  return d >= start && d <= end;
}

export interface Mix { layers: { v: Variant; a: number }[]; grade: string; night: number }

/** How to mix the painted versions for an hour and season. Only versions in `have` are used. */
export function mix(s: SceneState, have: Set<Variant>, sun: [number, number]): Mix {
  const [rise, set] = sun;
  const h = s.hour;
  // night amount: 0 by day, 1 at night, ramps over ~45 min around sunset/sunrise (blue hour in between)
  const ramp = (x: number) => Math.min(Math.max(x, 0), 1);
  const night = Math.max(ramp((h - set) / 0.75), ramp((rise - h) / 0.75), h >= 0 && h < rise - 0.75 ? 1 : 0);
  const golden = night < 1 ? ramp(1 - Math.abs(h - (set - 0.6)) / 1.2) * (1 - night) : 0;
  const winter = s.season === "winter";
  const dayV: Variant = winter && have.has("winter") ? "winter" : s.season === "autumn" && have.has("autumn") ? "autumn"
    : s.season === "spring" && have.has("spring") ? "spring" : "day";
  const nightV: Variant | null = winter && have.has("winter_night") ? "winter_night" : have.has("night") ? "night" : null;
  const layers: { v: Variant; a: number }[] = [{ v: dayV, a: 1 }];
  if (golden > 0.01 && have.has("golden") && !winter) layers.push({ v: "golden", a: golden });
  if (night > 0.01 && nightV) layers.push({ v: nightV, a: night });
  // CSS grade on top: morning a touch cool and soft, noon neutral, missing night version -> dark blue filter
  let grade = "";
  const morning = ramp(1 - Math.abs(h - (rise + 1)) / 1.5) * (1 - night);
  if (morning > 0) grade += ` saturate(${1 - 0.12 * morning}) brightness(${1 + 0.04 * morning}) hue-rotate(${-6 * morning}deg)`;
  if (night > 0 && !nightV) grade += ` brightness(${1 - 0.65 * night}) saturate(${1 - 0.4 * night}) hue-rotate(${15 * night}deg)`;
  if (golden > 0 && !have.has("golden")) grade += ` sepia(${0.25 * golden}) saturate(${1 + 0.2 * golden})`;
  return { layers, grade: grade.trim(), night };
}
