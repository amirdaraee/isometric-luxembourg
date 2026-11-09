// The bake-off viewer (PLAN_V2 section 7): the same view of every art method side by side, each column the real
// viewer (code light, night, seasons, vehicles) on that method's release. Methods whose release is not built yet show
// what they wait for. The releases come from the dev server's /bake/index.json (python -m v2.bakeoff register <m>).

export type View = { id: string; label: string; x: number; y: number; z: number; hour: number; date?: string; season?: string };

// v2 map pixels (zoom 0) of the fixed views; z = screen px per map px
export const VIEWS: View[] = [
  { id: "grund-day", label: "Grund, day 13:00", x: 62648, y: 34244, z: 0.5, hour: 13 },
  { id: "grund-golden", label: "Grund, golden hour", x: 62648, y: 34244, z: 0.5, hour: 21.3 },
  { id: "grund-night", label: "Grund, night", x: 62648, y: 34244, z: 0.5, hour: 23.25 },
  { id: "abbey", label: "Neumünster Abbey 1:1", x: 63135, y: 34267, z: 1, hour: 14 },
  { id: "bock", label: "The Bock, close", x: 63327, y: 33697, z: 0.75, hour: 15 },
  { id: "facade", label: "Facades 2:1 (straight windows)", x: 62281, y: 34323, z: 2, hour: 11 },
  { id: "red-bridge", label: "Red bridge, east end", x: 66670, y: 30911, z: 0.75, hour: 16 },
  { id: "pfaffenthal", label: "Pfaffenthal and the viaduct", x: 64459, y: 31607, z: 0.4, hour: 10 },
  { id: "area", label: "The whole test area", x: 64345, y: 33744, z: 0.12, hour: 15 },
];

export const METHODS = [
  { id: "a", label: "A: all code" },
  { id: "b", label: "B: code + AI materials" },
  { id: "c", label: "C: code + AI-painted buildings" },
] as const;

export function viewerUrl(method: string, v: View, extra = ""): string {
  const q = new URLSearchParams({ data: `/bake/${method}/`, x: String(v.x), y: String(v.y), z: String(v.z),
    hour: String(v.hour), date: v.date ?? "2026-06-24", nosim: "", noui: "" });
  if (v.season) q.set("season", v.season);
  return `/?${q.toString().replace(/=(&|$)/g, "$1")}${extra}`;
}

type Index = Record<string, { release: string | null; note?: string }>;

async function main() {
  const grid = document.getElementById("grid")!;
  const sel = document.getElementById("view") as HTMLSelectElement;
  const hour = document.getElementById("hour") as HTMLInputElement;
  const season = document.getElementById("season") as HTMLSelectElement;
  for (const v of VIEWS) sel.add(new Option(v.label, v.id));
  const q = new URLSearchParams(location.search);
  sel.value = q.get("view") ?? VIEWS[0].id;
  let index: Index = {};
  try { index = await (await fetch("/bake/index.json")).json(); } catch { /* no releases registered yet */ }
  const draw = () => {
    const base = VIEWS.find((v) => v.id === sel.value) ?? VIEWS[0];
    const v: View = { ...base, hour: hour.value === "" ? base.hour : +hour.value, season: season.value === "auto" ? undefined : season.value };
    (document.getElementById("hourOut") as HTMLElement).textContent = v.hour.toFixed(2);
    grid.innerHTML = "";
    for (const m of METHODS) {
      const col = document.createElement("section");
      const h = document.createElement("h2");
      h.textContent = m.label;
      col.append(h);
      const info = index[m.id];
      if (info?.release) {
        const f = document.createElement("iframe");
        f.src = viewerUrl(m.id, v);
        f.title = m.label;
        col.append(f);
        const a = document.createElement("a");
        a.href = viewerUrl(m.id, v).replace("&noui", "");
        a.target = "_blank";
        a.textContent = "open on its own";
        col.append(a);
      } else {
        const p = document.createElement("p");
        p.className = "wait";
        p.textContent = info?.note ?? "Not painted yet: waits for the owner's approval of its quote (v2/docs/PHASE2_QUOTE.md).";
        col.append(p);
      }
      grid.append(col);
    }
    history.replaceState(null, "", `?view=${v.id}`);
  };
  sel.onchange = () => { hour.value = ""; draw(); };
  hour.onchange = draw;
  season.onchange = draw;
  draw();
}

if (typeof document !== "undefined") void main();
