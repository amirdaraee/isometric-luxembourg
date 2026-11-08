/**
 * Checks of the event calendar: every rule against the 2026 and 2027 dates in research/05-events/events.json.
 *
 *   node src/calendar.test.ts
 *
 * (Node 22.6+ runs TypeScript directly.) Exits non-zero on any wrong answer.
 */
import { readFileSync } from "node:fs";
import { activeEvents, easter, eventOn, RULES, type EventId } from "./calendar.ts";

let failed = 0;
function check(what: string, ok: boolean, got?: unknown) {
  if (ok) return;
  failed++;
  console.log(`FAIL ${what}${got !== undefined ? `: got ${JSON.stringify(got)}` : ""}`);
}
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };

check("Easter 2026", iso(easter(2026)) === "2026-04-05", iso(easter(2026)));
check("Easter 2027", iso(easter(2027)) === "2027-03-28", iso(easter(2027)));
check("Easter 2028", iso(easter(2028)) === "2028-04-16", iso(easter(2028)));

// research id -> calendar id
const MAP: Record<string, EventId> = {
  winterlights: "winterlights", "new-years-eve": "newYear", "national-day": "nationalDay",
  schueberfouer: "schueberfouer", octave: "octave", emaischen: "emaischen", "ing-night-marathon": "marathon",
  halloween: "halloween", buergbrennen: "buergbrennen", "fete-de-la-musique": "musicStages",
};
interface Dates { start: string; end: string; status: string }
const research = JSON.parse(readFileSync(new URL("../../research/05-events/events.json", import.meta.url), "utf8")) as
  { id: string; dates_2026: Dates | null; dates_2027: Dates | null }[];
let n = 0;
for (const e of research) {
  const id = MAP[e.id];
  if (!id) continue;
  for (const [year, dates] of [[2026, e.dates_2026], [2027, e.dates_2027]] as const) {
    // only full dates (a month such as "2027-05" means not yet published)
    if (!dates || !/^\d{4}-\d\d-\d\d$/.test(dates.start)) continue;
    const r = RULES[id](year)!;
    check(`${id} ${year} start`, iso(r[0]) === dates.start, iso(r[0]));
    check(`${id} ${year} end`, iso(r[1]) === dates.end, iso(r[1]));
    check(`${id} ${year} on at start`, eventOn(id, parse(dates.start)));
    check(`${id} ${year} on at end`, eventOn(id, parse(dates.end)));
    n++;
  }
}
check("all ten events have research dates", n >= 18, n);

// a few days
check("2026-11-08 nothing", activeEvents(parse("2026-11-08")).length === 0, activeEvents(parse("2026-11-08")));
check("2026-11-20 Christmas", activeEvents(parse("2026-11-20")).join() === "winterlights");
check("2026-12-31 Christmas and New Year", activeEvents(parse("2026-12-31")).join() === "winterlights,newYear");
check("2027-01-01 Christmas and New Year", activeEvents(parse("2027-01-01")).join() === "winterlights,newYear");
check("2027-01-04 nothing", activeEvents(parse("2027-01-04")).length === 0);
check("2027-06-22 National Day", activeEvents(parse("2027-06-22")).join() === "nationalDay");
check("2027-08-25 Schueberfouer", activeEvents(parse("2027-08-25")).join() === "schueberfouer");
check("2027 marathon not on Whitsun weekend", iso(RULES.marathon(2027)![0]) === "2027-05-08", iso(RULES.marathon(2027)![0]));

if (failed) {
  console.log(`${failed} check(s) failed`);
  process.exit(1);
}
console.log(`calendar: all checks passed (${n} research date ranges)`);
