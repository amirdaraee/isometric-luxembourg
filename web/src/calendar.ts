// The event calendar: which city events are on for a day, from the rules in research/05-events/events.json, so the
// map shows the right event in any year without a list of dates to keep up to date. Each event has its own
// feature switch (features.ts); calendar.test.ts checks every rule against the dates in the research notes.
//
// Dates are local calendar days (the time of day is ignored, except for the "evening" events that begin at night).

export type EventId =
  | "winterlights" | "newYear" | "nationalDay" | "schueberfouer" | "octave" | "emaischen" | "marathon"
  | "halloween" | "buergbrennen" | "musicStages";

/** Easter Sunday (Gregorian), by the anonymous Gregorian algorithm. */
export function easter(year: number): Date {
  const a = year % 19, b = Math.floor(year / 100), c = year % 100, d = Math.floor(b / 4), e = b % 4;
  const f = Math.floor((b + 8) / 25), g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31), day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
}

function day(y: number, m: number, d: number): Date {
  return new Date(y, m - 1, d);
}
function plus(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

/** [first day, last day] of an event in a given year (the year it starts in), or null if it has no rule. */
export type Rule = (year: number) => [Date, Date] | null;

export const RULES: Record<EventId, Rule> = {
  // Friday before the last Sunday before Advent .. first Sunday of January
  winterlights: (y) => {
    const xmas = day(y, 12, 25);
    const advent1 = day(y, 12, 25 - ((xmas.getDay() || 7) + 21));
    const jan1 = day(y + 1, 1, 1);
    return [plus(advent1, -9), plus(jan1, (7 - jan1.getDay()) % 7)];
  },
  newYear: (y) => [day(y, 12, 31), day(y + 1, 1, 1)],
  // the eve (torchlight procession, fireworks at 23:00) and the day itself
  nationalDay: (y) => [day(y, 6, 22), day(y, 6, 23)],
  // opens on the Friday between 20 and 26 August, runs 20 days to a Wednesday
  schueberfouer: (y) => {
    const a20 = day(y, 8, 20);
    const start = plus(a20, (5 - a20.getDay() + 7) % 7);
    return [start, plus(start, 19)];
  },
  octave: (y) => [plus(easter(y), 20), plus(easter(y), 35)],
  emaischen: (y) => [plus(easter(y), 1), plus(easter(y), 1)],
  // a Saturday evening in May, not on the Whitsun weekend: the third Saturday, else the one before
  marathon: (y) => {
    const m1 = day(y, 5, 1);
    let sat = plus(m1, ((6 - m1.getDay() + 7) % 7) + 14);
    const whitsun = plus(easter(y), 49);
    if (Math.abs(+plus(sat, 1) - +whitsun) < 864e5 / 2) sat = plus(sat, -7);
    return [sat, sat];
  },
  // the city's Halloween weekend (the Saturday of the week before) to 31 October
  halloween: (y) => {
    const o31 = day(y, 10, 31);
    return [plus(o31, -7 - ((o31.getDay() + 1) % 7)), o31];
  },
  // first Sunday of Lent and the Saturday before (bonfires at dusk)
  buergbrennen: (y) => [plus(easter(y), -43), plus(easter(y), -42)],
  // Fête de la Musique: the city's weekend (Friday to Sunday) whose Sunday is on or before 15 June
  musicStages: (y) => {
    const j15 = day(y, 6, 15);
    const sun = plus(j15, -j15.getDay());
    return [plus(sun, -2), sun];
  },
};

/** Season the map takes when the event is picked (the event patches are drawn on that season's art). */
export const EVENT_SEASON: Partial<Record<EventId, "spring" | "summer" | "autumn" | "winter">> = {
  winterlights: "winter", newYear: "winter", buergbrennen: "winter", emaischen: "spring", octave: "spring",
  marathon: "spring", nationalDay: "summer", musicStages: "summer", schueberfouer: "summer", halloween: "autumn",
};

export const EVENT_NAMES: Record<EventId, string> = {
  winterlights: "Christmas markets", newYear: "New Year's Eve", nationalDay: "National Day",
  schueberfouer: "Schueberfouer", octave: "Octave", emaischen: "Éimaischen", marathon: "Night Marathon",
  halloween: "Halloween", buergbrennen: "Buergbrennen", musicStages: "Fête de la Musique",
};

/** The hour the picker jumps to, for events whose best moment is at a set time (fireworks, torches, dusk). */
export const SHOW_HOUR: Partial<Record<EventId, number>> = {
  nationalDay: 23.05, schueberfouer: 22.05, newYear: 23.97, marathon: 21.0, buergbrennen: 18.3, halloween: 20.5,
};

function sameOrAfter(d: Date, a: Date) {
  return d.getFullYear() * 400 + d.getMonth() * 32 + d.getDate() >= a.getFullYear() * 400 + a.getMonth() * 32 + a.getDate();
}

/** Is the event on that day? Looks at the rule for this year and the year before (events over New Year). */
export function eventOn(id: EventId, d: Date): boolean {
  for (const y of [d.getFullYear() - 1, d.getFullYear()]) {
    const r = RULES[id](y);
    if (r && sameOrAfter(d, r[0]) && sameOrAfter(r[1], d)) return true;
  }
  return false;
}

/** The events on that day, in the order of RULES. */
export function activeEvents(d: Date): EventId[] {
  return (Object.keys(RULES) as EventId[]).filter((id) => eventOn(id, d));
}

/** The next start of an event on or after a day (for the picker's "coming up" note). */
export function nextStart(id: EventId, d: Date): Date | null {
  for (const y of [d.getFullYear() - 1, d.getFullYear(), d.getFullYear() + 1]) {
    const r = RULES[id](y);
    if (r && sameOrAfter(r[1], d)) return r[0];
  }
  return null;
}
