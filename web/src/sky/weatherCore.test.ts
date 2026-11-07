/**
 * Checks of the weather model: the WMO code mapping, the ?weather= text and the amounts.
 *
 *   node src/sky/weatherCore.test.ts
 *
 * (Node 22.6+ runs TypeScript directly.) Exits non-zero on the first wrong answer.
 */
import { amountsOf, fromWmo, groundToScreen, parseWeather, type Kind } from "./weatherCore.ts";

let failed = 0;
function check(what: string, ok: boolean, got?: unknown) {
  if (ok) return;
  failed++;
  console.log(`FAIL ${what}${got !== undefined ? `: got ${JSON.stringify(got)}` : ""}`);
}

// WMO codes to kinds
const cases: [number, Kind][] = [
  [0, "clear"], [1, "clear"], [2, "cloudy"], [3, "cloudy"], [45, "fog"], [48, "fog"], [51, "rain"], [55, "rain"],
  [61, "rain"], [63, "rain"], [65, "rain"], [66, "rain"], [71, "snow"], [75, "snow"], [77, "snow"], [80, "rain"],
  [82, "rain"], [85, "snow"], [86, "snow"], [95, "storm"], [96, "storm"], [99, "storm"],
];
for (const [code, kind] of cases) check(`WMO ${code} is ${kind}`, fromWmo({ weather_code: code }).kind === kind, fromWmo({ weather_code: code }).kind);
check("heavy rain is heavier than drizzle", fromWmo({ weather_code: 65 }).intensity > fromWmo({ weather_code: 51 }).intensity);
check("visibility under 1 km is fog", fromWmo({ weather_code: 3, visibility: 400 }).kind === "fog");
check("cloud cover is kept", fromWmo({ weather_code: 1, cloud_cover: 35 }).cloud === 0.35);
check("wind is kept", fromWmo({ weather_code: 0, wind_speed_10m: 7, wind_direction_10m: 80 }).wind.from === 80);

// ?weather= text
const r = parseWeather("rain:0.8,wind:12@250");
check("rain:0.8,wind:12@250", r?.kind === "rain" && r.intensity === 0.8 && r.wind.speed === 12 && r.wind.from === 250, r);
check("storm:1", parseWeather("storm:1")?.kind === "storm");
check("clear,wind:6@80", parseWeather("clear,wind:6@80")?.wind.from === 80);
check("no kind is null", parseWeather("wind:5@10") === null);
check("nonsense is null", parseWeather("tornado:2") === null);
check("intensity is clamped", parseWeather("fog:3")?.intensity === 1);

// amounts
const a = amountsOf(parseWeather("rain:0.8,wind:12@250")!);
check("rain amount", Math.abs(a.rain - 0.8) < 1e-9, a.rain);
// from 250 (west-south-west) the air moves towards 70 degrees: mostly east, a little north
check("wind towards east-north-east", a.windE > 10 && a.windN > 3, [a.windE, a.windN]);
check("storm has lightning", amountsOf(parseWeather("storm:1")!).storm === 1);
check("clear has no rain or fog", amountsOf(parseWeather("clear")!).rain === 0 && amountsOf(parseWeather("clear")!).fog === 0);

// ground to screen: north goes up and to the right, east down and to the right
const [nx, ny] = groundToScreen(0, 1), [ex, ey] = groundToScreen(1, 0);
check("north is up-right on screen", nx > 0 && ny < 0, [nx, ny]);
check("east is down-right on screen", ex > 0 && ey > 0, [ex, ey]);

console.log(failed ? `${failed} check(s) failed` : "weather: all checks passed");
process.exit(failed ? 1 : 0);
