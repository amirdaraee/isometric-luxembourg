"""Events other than Christmas (PLAN_NEXT item 13): their painted patches, and the manifest the viewer reads.

  event_patch.py draw <site> <day|night> <cap usd> [--relight]
        the paid call (about $0.06 a drawing): sends the square cut from the newest canvas of the site's version and
        caches what was sent and what came back in data/work/events/<event>/. Refuses to spend past the cap, counted
        over every "events13:" entry of data/work/style/openai_spend.json. --relight (night): send the night art
        with the chosen day drawing laid in, so day and night show the same event (as xmas_v2.py does).
  event_patch.py composite [site,...]
        free: the halo-free patches (patchlib.py) over the CURRENT tiles of each site's versions, into
        web/public/events/<event>/<site>_<day|night>.webp. Rerun whenever those versions' tiles are rebuilt.
  event_patch.py manifest
        free: web/public/events/events.json, every event the viewer knows: its season, its patches (Christmas from
        xmas/xmas.json), and its live effects (fireworks, bonfires, a stream of runners along a route found on the
        street network, bats), all in map px, from the research notes (research/05-events/events.json).

Base-art rule: no people and no vehicles in a patch; crowds and runners are live dots.
"""
import heapq
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(Path(__file__).parent))
from common import ELEV, ORIGIN_E, ORIGIN_N, R, WORK, lonlat_to_en  # noqa: E402
import patchlib  # noqa: E402
import xmas_v2  # noqa: E402

WEB = ROOT / "web/public/events"
TAG = "events13"
SEND = 1024
LM = {c["slug"]: c for c in json.loads((ROOT / "web/public/data/landmarks.json").read_text())}

# ---- map positions ----------------------------------------------------------------------------------------------

_M = json.loads((WORK / "mosaic.json").read_text())
_T = np.load(WORK / "terrain.npz")


def ground(e: float, n: float) -> float:
    tz, te0, tn0, ts = _T["z"], float(_T["e0"]), float(_T["n0"]), float(_T["step"])
    iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1)
    ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
    return float(tz[iy, ix])


def px(lat: float, lon: float, up: float = 0.0) -> tuple[int, int]:
    """Map px of a point `up` metres above the ground at (lat, lon) (as project_lines.py)."""
    e, n = lonlat_to_en(lon, lat)
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R
    sy = (-le + ln) * R * math.sin(ELEV) + (ground(e, n) + up) * math.cos(ELEV)
    return round((sx - _M["sx0"]) / _M["mpp"]), round((_M["sy1"] - sy) / _M["mpp"])


def up_px(metres: float) -> float:
    """Screen height in map px of `metres` straight up."""
    return metres * math.cos(ELEV) / _M["mpp"]


# ---- patch sites (paid drawings) --------------------------------------------------------------------------------

COMMON = xmas_v2.COMMON
SITES = {
    # site: event, centre (map px), crop (map px), versions {day, night}, prompt
    "schueberfouer-glacis": {
        "event": "schueberfouer", "at": (8420, 4320), "crop": 1200, "versions": {"day": "day", "night": "night"},   # the Glacis car park (lines.json)
        "prompt": "On the large open car park in the middle (the Glacis), add the Schueberfouer funfair filling it in a "
                  "dense grid: a tall Ferris wheel as the landmark, a wild-mouse roller coaster, a drop tower, a "
                  "chair-o-planes, a log flume, ghost trains, bumper cars under coloured canopies, food halls with "
                  "striped roofs and rows of small stalls along the edges, all on the asphalt. It is a sunny summer day."},
    "music-knuedler": {
        "event": "musicStages", "at": (LM["place-guillaume-ii"]["x"], LM["place-guillaume-ii"]["y"]), "crop": 760,
        "versions": {"day": "day", "night": "night"},
        "prompt": "On the large paved square in the middle with the equestrian statue (Place Guillaume II), add an "
                  "open-air music festival: a covered concert stage with a truss lighting rig and speaker towers at one "
                  "end of the square, a smaller second stage, a sound desk tent in the middle, a few drinks stalls with "
                  "white tents, crowd barriers. It is a sunny summer day."},
    "octave-knuedler": {
        "event": "octave", "at": (LM["place-guillaume-ii"]["x"], LM["place-guillaume-ii"]["y"]), "crop": 760,
        "versions": {"day": "spring", "night": "night"},
        "prompt": "On the large paved square in the middle with the equestrian statue (Place Guillaume II), add the "
                  "Octave market (Mäertchen): about 40 small wooden food and game stalls with green and white striped "
                  "awnings in rows, around a large covered terrace with a white tent roof and tables, and a small "
                  "children's carousel. It is a spring day."},
    "emaischen-feschmaart": {
        "event": "emaischen", "crop": 600,   # the National Museum stands on the Fëschmaart
        "at": (LM["national-museum-of-history-and-art"]["x"], LM["national-museum-of-history-and-art"]["y"]), "versions": {"day": "spring"},
        "prompt": "On the small old square and the lanes around it in the middle (the Fish Market, Fëschmaart), add the "
                  "Éimaischen Easter Monday market: rows of small stalls with white and coloured canopies selling "
                  "pottery and clay bird whistles, tables of colourful pottery, a small music stage. It is a spring day."},
    "halloween-neimenster": {
        "event": "halloween", "at": (LM["neumunster-abbey"]["x"], LM["neumunster-abbey"]["y"]), "crop": 700,
        "versions": {"day": "autumn", "night": "night"},
        "prompt": "In the paved courtyard and on the front steps of the large old abbey in the middle (Neimënster, in the "
                  "Grund), add a small Halloween decoration at true size: rows of ordinary orange carved pumpkins, each "
                  "only as big as a person's knee, along the steps and the courtyard walls, a few straw bales, a string "
                  "of orange and purple bunting. Nothing on the hillside, the cliffs or the gardens; no giant objects. "
                  "It is an autumn day."},
}
LIGHT = {"day": "Daylight as in the input.",
         "night": "It is night, exactly as dark as the input: the event's lamps, stalls and rides glow in warm and "
                  "coloured light and cast light pools on the ground. No sun shadows."}
NIGHT_LIGHT = {"halloween-neimenster": "the carved pumpkins glow orange from inside and the abbey walls are washed in "
                                       "orange and purple light",
               "schueberfouer-glacis": "the rides glow in neon colours, the Ferris wheel lit all over"}


def site_dir(site: str) -> Path:
    return WORK / "events" / SITES[site]["event"]


def box(site: str) -> tuple[int, int, int]:
    s = SITES[site]
    c = s["crop"]
    return int(s["at"][0] - c // 2), int(s["at"][1] - c // 2), c


def spent() -> float:
    return sum(e["usd"] for e in json.loads(xmas_v2.log_path.read_text()) if e["file"].startswith(TAG + ":"))


def pick(site: str, when: str) -> tuple[Path, Path]:
    d = site_dir(site)
    ch = d / "chosen.json"
    chosen = json.loads(ch.read_text()) if ch.exists() else {}
    if f"{site}_{when}" in chosen:
        n = chosen[f"{site}_{when}"]
    else:
        tries = sorted(d.glob(f"{site}_{when}_raw*.png"), key=lambda p: int(p.stem.rsplit("raw", 1)[1]))
        if not tries:
            raise SystemExit(f"no {when} drawing for {site}")
        n = int(tries[-1].stem.rsplit("raw", 1)[1])
    return d / f"{site}_{when}_raw{n}.png", d / f"{site}_{when}_sent{n}.png"


def draw(site: str, when: str, cap: float, relight: bool) -> None:
    s = SITES[site]
    d = site_dir(site)
    d.mkdir(parents=True, exist_ok=True)
    x0, y0, c = box(site)
    base = patchlib.base_crop(x0, y0, c, c, s["versions"][when])
    if relight:
        dr, ds = pick(site, "day")
        day_base = patchlib.base_crop(x0, y0, c, c, s["versions"]["day"])
        base = np.asarray(xmas_v2.unlit(Image.open(dr), Image.open(ds), day_base, base))
        prompt = (f"The event on the square is already drawn, still unlit: keep every stall, ride, stage and decoration "
                  f"exactly where and as it is, and add nothing new. Light it for the night, exactly as dark as the input "
                  f"elsewhere: {NIGHT_LIGHT.get(site, 'its lamps and stalls glow warm and coloured')}, casting light pools "
                  f"on the ground. No sun shadows.\n\n{COMMON}")
    else:
        prompt = f"{s['prompt']}\n\n{LIGHT[when]}\n\n{COMMON}"
    if spent() + 0.08 > cap:
        sys.exit(f"cap reached: ${spent():.3f} of ${cap:.2f} spent")
    sent = Image.fromarray(base).resize((SEND, SEND), Image.LANCZOS)
    n = len(list(d.glob(f"{site}_{when}_raw*.png")))
    old_tag = xmas_v2.TAG
    xmas_v2.TAG = TAG   # log under this item's tag
    try:
        raw = xmas_v2.call(sent, prompt, f"{site}_{when}_{n}")
    finally:
        xmas_v2.TAG = old_tag
    sent.save(d / f"{site}_{when}_sent{n}.png")
    raw.save(d / f"{site}_{when}_raw{n}.png")
    if relight:
        rl = d / "relit.json"
        relit = json.loads(rl.read_text()) if rl.exists() else []
        rl.write_text(json.dumps(relit + [f"{site}_{when}_raw{n}"]))
    print(site, when, "->", d / f"{site}_{when}_raw{n}.png", f"({TAG} total ${spent():.3f})")


def composite(only: list[str]) -> None:
    for site in only:
        s = SITES[site]
        x0, y0, c = box(site)
        out = WEB / s["event"]
        whens = list(s["versions"])
        bases = {w: patchlib.base_crop(x0, y0, c, c, s["versions"][w]) for w in whens}
        picked = {w: pick(site, w) for w in whens}
        if len(whens) == 2:
            rl = site_dir(site) / "relit.json"
            share = picked["night"][0].stem in (json.loads(rl.read_text()) if rl.exists() else [])
            pd, pn, info = patchlib.composite_pair(*[(Image.open(picked[w][0]), Image.open(picked[w][1]), bases[w]) for w in whens],
                                                   share=share)
            patches = {"day": pd, "night": pn}
            bx, by, bw, bh = info.pop("box")
        else:
            p, (bx, by, bw, bh) = patchlib.composite(Image.open(picked["day"][0]), Image.open(picked["day"][1]), bases["day"], False)
            patches, info = {"day": p}, {}
        for w, p in patches.items():
            patchlib.save_patch(p, out / f"{site}_{w}.webp")
        placed = {"site": site, "x0": x0 + bx, "y0": y0 + by, "w": bw, "h": bh, "files": {w: f"{site}_{w}.webp" for w in patches}}
        (out / f"{site}.json").write_text(json.dumps(placed, indent=1))
        sheet = [np.hstack([bases[w], patchlib.over(p, bases[w], (bx, by))]) for w, p in patches.items()]
        Image.fromarray(np.vstack(sheet)).save(WORK / "events" / f"{site}_sheet.jpg", quality=85)
        print(site, info, {w: (out / f"{site}_{w}.webp").stat().st_size // 1024 for w in patches}, "KB")


# ---- live effects -----------------------------------------------------------------------------------------------

DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street",
            "pedestrian", "primary_link", "secondary_link", "tertiary_link", "trunk_link", "service"}


WALKABLE = DRIVABLE | {"footway", "path", "steps", "cycleway"}


def route(waypoints: list, kinds: set = DRIVABLE) -> list[list[int]]:
    """A path along the street network (lines.json) through the waypoints (map px), shortest between each pair,
    simplified to points about 8 m apart. Waypoints snap to the largest connected part of the network; a waypoint
    given as ("bridge", x, y) snaps to a bridge deck (otherwise the valley road under a bridge can be nearer)."""
    L = json.loads((ROOT / "web/public/data/lines.json").read_text())
    adj: dict[tuple[int, int], list[tuple[tuple[int, int], float]]] = {}
    decks: set[tuple[int, int]] = set()
    for r in L["roads"]:
        if r["k"] not in kinds or r.get("t"):
            continue
        p = r["p"]
        pts = [(p[i], p[i + 1]) for i in range(0, len(p), 2)]
        if r.get("b"):
            decks.update(pts)
        for a, b in zip(pts, pts[1:]):
            w = math.dist(a, b)
            adj.setdefault(a, []).append((b, w))
            adj.setdefault(b, []).append((a, w))
    # the largest connected part
    seen, best = set(), []
    for start in adj:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v, _ in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(comp) > len(best):
            best = comp
    nodes = np.array(best)

    deck_nodes = np.array([q for q in best if q in decks]) if decks else nodes

    def snap(q):
        pool = nodes
        if isinstance(q, tuple) and len(q) == 3 and q[0] == "bridge":
            pool, q = deck_nodes, q[1:]
        return tuple(int(v) for v in pool[np.argmin(((pool - np.array(q)) ** 2).sum(1))])

    def shortest(a, b):
        dist, prev, todo = {a: 0.0}, {}, [(0.0, a)]
        while todo:
            d, u = heapq.heappop(todo)
            if u == b:
                break
            if d > dist[u]:
                continue
            for v, w in adj[u]:
                if d + w < dist.get(v, 1e18):
                    dist[v], prev[v] = d + w, u
                    heapq.heappush(todo, (d + w, v))
        out, u = [b], b
        while u != a:
            u = prev[u]
            out.append(u)
        return out[::-1]

    path: list[tuple[int, int]] = []
    snapped = [snap(w) for w in waypoints]
    for a, b in zip(snapped, snapped[1:]):
        seg = shortest(a, b)
        path += seg if not path else seg[1:]
    simple = [path[0]]
    for q in path[1:]:
        if math.dist(q, simple[-1]) >= 32:
            simple.append(q)
    if simple[-1] != path[-1]:
        simple.append(path[-1])
    return [list(q) for q in simple]


def manifest() -> None:
    """web/public/events/events.json: everything the viewer needs per event (see EventLayer.tsx)."""
    def patches(event: str) -> list[dict]:
        out = []
        for site, s in SITES.items():
            f = WEB / s["event"] / f"{site}.json"
            if s["event"] == event and f.exists():
                p = json.loads(f.read_text())
                out.append({"x0": p["x0"], "y0": p["y0"], "w": p["w"],
                            **{w: f"/events/{event}/{name}" for w, name in p["files"].items()}})
        return out
    xmas = [{"x0": e["x0"], "y0": e["y0"], "w": e["w"], "day": f"/events/xmas/{e['site']}_day.webp",
             "night": f"/events/xmas/{e['site']}_night.webp"} for e in json.loads((WEB / "xmas/xmas.json").read_text())]
    adolphe = LM["adolphe-bridge"]
    red = LM["grand-duchess-charlotte-bridge"]
    ev = {
        "winterlights": {"season": "winter", "patches": xmas, "rides": "xmas"},
        "newYear": {"season": "winter", "patches": xmas, "rides": "xmas",
                    # the city bans private fireworks: a few light sparkles over the quarters round midnight
                    "fireworks": [{"kind": "sparkles", "at": [LM[s]["x"], LM[s]["y"]], "spread": 2200, "height": 200,
                                   "from": 23.9, "to": 24.4, "rate": 0.5}
                                  for s in ("place-d-armes", "luxembourg-railway-station", "d-coque", "villa-vauban")]},
        "nationalDay": {"season": "summer",
                        # from Pont Adolphe at 23:00 on the eve, 17 minutes, bursting over the Pétrusse valley
                        "fireworks": [{"kind": "show", "at": [adolphe["x"], adolphe["y"]], "height": round(up_px(45)),
                                       "burst": round(up_px(160)), "from": 23.0, "to": 23.0 + 17 / 60, "rate": 2.2, "day": 0}],
                        # torches along the procession route on the eve
                        "torches": {"route": route([px(49.6118, 6.1316), px(49.6109, 6.1312), px(49.6106, 6.1322), px(49.6101, 6.134)], WALKABLE),
                                    "from": 21.5, "to": 23.0, "day": 0}},
        "schueberfouer": {"season": "summer", "patches": patches("schueberfouer"),
                          # closing night, 22:00, from the Red Bridge
                          "fireworks": [{"kind": "show", "at": [red["x"], red["y"]], "height": round(up_px(75)),
                                         "burst": round(up_px(150)), "from": 22.0, "to": 22.25, "rate": 2.0, "day": -1}]},
        "octave": {"season": "spring", "patches": patches("octave")},
        "emaischen": {"season": "spring", "patches": patches("emaischen")},
        "marathon": {"season": "spring",
                     # a glowing stream of runners from Kirchberg over the Red Bridge, through the Ville Haute to the Gare
                     "runners": {"route": route([px(49.6343, 6.1716), ("bridge", red["x"], red["y"]), (7615, 5801),
                                                 ("bridge", adolphe["x"], adolphe["y"]), px(49.604, 6.132)]),
                                 "from": 19.0, "to": 23.5, "speed": 3.2, "density": 1.2}},
        "halloween": {"season": "autumn", "patches": patches("halloween"),
                      "bats": [{"at": [LM["neumunster-abbey"]["x"], LM["neumunster-abbey"]["y"] - 60], "n": 14, "r": 260},
                               {"at": [LM["bock-casemates"]["x"], LM["bock-casemates"]["y"] - 80], "n": 10, "r": 220}]},
        "buergbrennen": {"season": "winter",
                         # bonfires at dusk on both days, at the city's edges and in the Pétrusse valley
                         "bonfires": [{"at": list(px(lat, lon)), "size": 1.0} for lat, lon in
                                      ((49.6155, 6.169), (49.599, 6.14), (49.6071, 6.1255))],
                         "dusk": [-0.5, 3.0]},
        "musicStages": {"season": "summer", "patches": patches("musicStages")},
    }
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "events.json").write_text(json.dumps(ev, separators=(",", ":")))
    print("events.json:", {k: [x for x in v if x != "season"] for k, v in ev.items()},
          (WEB / "events.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "draw":
        draw(sys.argv[2], sys.argv[3], float(sys.argv[4]), "--relight" in sys.argv)
    elif cmd == "composite":
        composite(sys.argv[2].split(",") if len(sys.argv) > 2 else list(SITES))
    elif cmd == "manifest":
        manifest()
    else:
        sys.exit(__doc__)
