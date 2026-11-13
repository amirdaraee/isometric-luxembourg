// Test parameters in the address (v1's testParams, kept and extended), so every view can be repeated:
//
//   ?hour=13.5             the clock fixed at that hour, Luxembourg time (default: now)
//   ?date=2026-06-21       "today" (the sun, the season, the timetable's day type)
//   ?season=winter         spring, summer, autumn or winter (default: from the date)
//   ?snow                  snow on up-facing surfaces (layer 11)
//   ?off=trees,buildings   layers switched off (compositor.md design 5): ground, relief, water, transport,
//                          buildings, structures, trees, light, night, seasons, vehicles, look, labels;
//                          cutlight: a cutaway's opening lit as any building, not by the sky only (for the checks)
//   ?seed=42               the traffic seed
//   ?x=61000&y=33500&z=1   the view: centre in v2 map pixels (zoom 0) and the scale (screen px per map px)
//   ?v1x=&v1y=             a v1 link's centre (v1 map pixels), converted exactly (camera.md)
//   ?debug=albedo|layer|shadow|depth|normal|vehicles   what the final pass shows (checks and screenshots)
//   ?simtime=3600          seconds to run the traffic before the first frame (busy streets at once)
//   ?nosim                 no vehicles moving (still frames)
//   ?xray                  tunnel view on (tunnel-view.md): the city faded, the tunnels and what moves in them shown;
//                          ?off=casemates leaves the Bock casemates out; ?debug=xid|xdepth for its checks
//   ?cutaway               the landmark cutaways on (landmark-cutaways.md): each landmark cut open in place;
//                          ?cutaway=cathedral,palace only those

export type Season = "spring" | "summer" | "autumn" | "winter";
export const LAYERS = ["ground", "relief", "water", "transport", "buildings", "structures", "trees"] as const;
export type LayerName = (typeof LAYERS)[number];

const q = new URLSearchParams(typeof location === "undefined" ? "" : location.search);

function num(name: string): number | null {
  const v = q.get(name);
  if (v === null || v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

const SEASONS: Season[] = ["spring", "summer", "autumn", "winter"];
const hour = num("hour");
const season = q.get("season") as Season | null;
const dm = q.get("date")?.match(/^(\d{4})-(\d{2})-(\d{2})$/);

export const params = {
  hour: hour !== null && hour >= 0 && hour < 24 ? hour : null,
  date: dm ? { y: +dm[1], m: +dm[2], d: +dm[3] } : null,
  season: season && SEASONS.includes(season) ? season : null,
  snow: q.has("snow"),
  off: new Set((q.get("off") ?? "").split(",").map((s) => s.trim()).filter(Boolean)),
  seed: num("seed"),
  x: num("x"), y: num("y"), z: num("z"),
  v1x: num("v1x"), v1y: num("v1y"),
  debug: q.get("debug") ?? "",
  simtime: num("simtime") ?? 600,
  nosim: q.has("nosim"),
  xray: q.has("xray"),
  cutaway: q.get("cutaway"),          // null: off; "": every landmark; "a,b": those
  ui: !q.has("noui"),
};

/** "Now", unless ?date= is given: then that day at ?hour= (else noon), Luxembourg time. */
export function today(): Date {
  const d = params.date;
  if (!d) return new Date();
  const h = params.hour ?? 12;
  return luxDate(d.y, d.m, d.d, h);
}

/** The instant of a Luxembourg wall-clock time (Europe/Luxembourg, with summer time). */
export function luxDate(y: number, m: number, d: number, hour: number): Date {
  const guess = Date.UTC(y, m - 1, d) + Math.round(hour * 3600_000);   // to the millisecond
  for (const off of [1, 2]) {
    const t = new Date(guess - off * 3600_000);
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Luxembourg", hour: "2-digit", hourCycle: "h23" })
      .formatToParts(t).find((p) => p.type === "hour");
    if (parts && +parts.value === Math.floor(hour)) return t;
  }
  return new Date(guess - 3600_000);
}

export function seasonOf(date: Date): Season {
  const m = date.getUTCMonth() + 1;
  return m >= 3 && m <= 5 ? "spring" : m >= 6 && m <= 8 ? "summer" : m >= 9 && m <= 11 ? "autumn" : "winter";
}
