// Review notes (?review): a reader marks a place on the map and writes what is wrong there. A note keeps the map
// pixel, the scale, the hour and the date, so the same view can be opened again; the list is copied as text, and
// the dev server keeps a copy in a file (vite.config.ts, /notes).

export interface Note {
  x: number; y: number;          // the place, in map pixels
  z: number;                     // the scale it was seen at (screen px per map px)
  hour: number;                  // the hour shown, Luxembourg time
  date: string | null;           // ?date=, when the view had one
  what: string;                  // what the map says is there ("wall", "road: Rue Large"), or ""
  text: string;
}

const flag = (s: string) => s.replace(/=(?=&|$)/g, "");          // ?noui, not ?noui=

/** `search` with the view's x, y and z set (and hour, when given): the address of the view, other parameters kept. */
export function viewQuery(search: string, v: { x: number; y: number; z: number; hour?: number | null }): string {
  const q = new URLSearchParams(search);
  q.delete("v1x"); q.delete("v1y");                               // x and y say where now
  q.set("x", String(Math.round(v.x)));
  q.set("y", String(Math.round(v.y)));
  q.set("z", String(+v.z.toFixed(3)));
  if (v.hour !== null && v.hour !== undefined) q.set("hour", String(+v.hour.toFixed(2)));
  return "?" + flag(q.toString());
}

/** The address that opens a note's place as it was seen: `page` is the viewer's address without its query. */
export function noteLink(page: string, n: Note): string {
  const q = viewQuery("", n);
  return page + q + (n.date ? `&date=${n.date}` : "") + "&review";
}

export function clock(hour: number): string {
  const m = Math.round(hour * 60) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/** The notes as text to paste: the note, then what and where it is, and the link to it. */
export function notesText(notes: Note[], page: string): string {
  return notes.map((n, i) => `${i + 1}. ${n.text}\n   ${n.what || "place"} at x=${Math.round(n.x)} y=${Math.round(n.y)}, `
    + `${clock(n.hour)}${n.date ? ` on ${n.date}` : ""}\n   ${noteLink(page, n)}`).join("\n\n");
}

/** The notes kept as JSON, read back: anything that is not a note is left out. */
export function parseNotes(json: string | null): Note[] {
  let v: unknown;
  try { v = JSON.parse(json ?? "[]"); } catch { return []; }
  if (!Array.isArray(v)) return [];
  const num = (n: unknown) => typeof n === "number" && Number.isFinite(n);
  return v.filter((n) => n && num(n.x) && num(n.y) && num(n.z) && n.z > 0 && num(n.hour) && typeof n.text === "string" && n.text.trim() !== "")
    .map((n) => ({ x: n.x, y: n.y, z: n.z, hour: n.hour, date: typeof n.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(n.date) ? n.date : null,
      what: typeof n.what === "string" ? n.what : "", text: n.text }));
}
