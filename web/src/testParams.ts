// Test parameters in the address, so that every screenshot can be repeated. For development and headless tests;
// each one changes nothing unless it is present.
//
//   ?hour=21.5                      fixes the clock at that hour (the "Live" button starts off)
//   ?season=winter                  the season shown (spring, summer, autumn or winter)
//   ?date=2026-08-25                "today" for the season, Christmas, the timetable's day type and the event calendar
//   ?weather=rain:0.8,wind:12@250   the weather (read by Sky and WeatherControl)
//   ?event=schueberfouer            the event shown (read by EventLayer)
//   ?seed=42                        the traffic seed (TrafficOptions.seed)
//
// They work with the feature switches: ?hour needs timeOfDay and ?season needs seasons, so in a release build add
// ?on=timeOfDay,seasons as well.
import type { Season } from "./scene";

const q = new URLSearchParams(location.search);

function num(name: string): number | null {
  const v = q.get(name);
  if (v === null || v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const SEASONS: Season[] = ["spring", "summer", "autumn", "winter"];
const hour = num("hour");
const season = q.get("season") as Season | null;
const dateText = q.get("date");
const dateMatch = dateText?.match(/^(\d{4})-(\d{2})-(\d{2})$/);

export const testParams = {
  /** Fixed hour of the day, 0 to 24, or null for the live clock. */
  hour: hour !== null && hour >= 0 && hour < 24 ? hour : null,
  /** Fixed season, or null for the season of "today". */
  season: season && SEASONS.includes(season) ? season : null,
  /** Fixed calendar day (year, month 1-12, day), or null for the real date. */
  date: dateMatch ? { y: +dateMatch[1], m: +dateMatch[2], d: +dateMatch[3] } : null,
  /** The raw ?weather= text, or null. Parsed by stream C's weather code. */
  weather: q.get("weather"),
  /** The ?event= id, or null. */
  event: q.get("event"),
  /** Traffic seed, or null for the built-in one. */
  seed: num("seed"),
};

/** "Now", unless ?date= is given: then that day, at ?hour= if given (else noon), local time. */
export function today(): Date {
  const d = testParams.date;
  if (!d) return new Date();
  const h = testParams.hour ?? 12;
  return new Date(d.y, d.m - 1, d.d, Math.floor(h), Math.round((h % 1) * 60));
}
