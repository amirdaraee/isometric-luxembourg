/**
 * Checks of the time and season controls' rules (scene.ts): every change keeps the buttons and the map in step.
 *
 *   node src/scene.test.ts
 *
 * Exits non-zero on any wrong answer.
 */
import { changeScene, mix, sunFor, type SceneState, type Variant } from "./scene.ts";
import { EVENT_SEASON } from "./calendar.ts";

let failed = 0;
function check(what: string, ok: boolean, got?: unknown) {
  if (ok) return;
  failed++;
  console.log(`FAIL ${what}${got !== undefined ? `: got ${JSON.stringify(got)}` : ""}`);
}

const autumn: SceneState = { hour: 13, season: "autumn", christmas: false, event: null };
const ch = (s: SceneState, c: Partial<SceneState>) => changeScene(s, c, EVENT_SEASON);

// Christmas brings winter; another season then switches it off (the markets are on the winter art only)
const xmas = ch(autumn, { christmas: true });
check("Christmas brings winter", xmas.season === "winter" && xmas.christmas, xmas);
const summer = ch(xmas, { season: "summer" });
check("summer switches Christmas off", summer.season === "summer" && !summer.christmas, summer);
check("winter keeps Christmas", ch(xmas, { season: "winter" }).christmas);
check("Christmas off keeps the season", ch(xmas, { christmas: false }).season === "winter");

// an event belongs to its season: picking another season drops it, the same season keeps it
const hall = ch(autumn, { event: "halloween", season: "autumn", christmas: false, hour: 20.5 });
check("Halloween picked", hall.event === "halloween" && hall.hour === 20.5, hall);
check("spring drops Halloween", ch(hall, { season: "spring" }).event === null);
check("autumn keeps Halloween", ch(hall, { season: "autumn" }).event === "halloween");
check("Christmas drops Halloween (winter)", ch(hall, { christmas: true }).event === null);
const ny = ch(autumn, { event: "newYear", season: "winter", christmas: true });
check("New Year keeps Christmas and winter", ny.christmas && ny.season === "winter" && ny.event === "newYear", ny);
check("Christmas off keeps New Year", ch(ny, { christmas: false }).event === "newYear");

// a change that does not touch the hour leaves it alone (live time is not stopped by the season buttons)
check("season keeps the hour", ch({ ...autumn, hour: 7.25 }, { season: "winter" }).hour === 7.25);

// sun times: today's for today's season (and the month next to it), else the season's own
const nov = new Date(2026, 10, 8), jul = new Date(2026, 6, 10), dec = new Date(2026, 11, 10);
check("autumn in November: November's sun", sunFor("autumn", nov)[1] === 16.9, sunFor("autumn", nov));
check("winter in November (Christmas): November's sun", sunFor("winter", nov)[0] === 7.8, sunFor("winter", nov));
check("winter in July: dark at 18:00", sunFor("winter", jul)[1] < 17.5, sunFor("winter", jul));
check("summer in December: light at 21:00", sunFor("summer", dec)[1] > 21, sunFor("summer", dec));

// night amount: no jumps across the day (every 3 minutes, at most a 0.1 step), for each season
const have = new Set<Variant>(["day", "golden", "night", "winter", "winter_night", "autumn", "spring"]);
for (const season of ["spring", "summer", "autumn", "winter"] as const) {
  const sun = sunFor(season, nov);
  let prev = mix({ hour: 0, season, christmas: false }, have, sun);
  for (let h = 0.05; h < 24; h += 0.05) {
    const m = mix({ hour: h, season, christmas: false }, have, sun);
    const jump = Math.abs(m.night - prev.night);
    if (jump > 0.1) { check(`${season}: night jumps at ${h.toFixed(2)} h`, false, jump); break; }
    prev = m;
  }
}

if (failed) { console.log(`${failed} failed`); process.exit(1); }
console.log("scene: all checks passed");
