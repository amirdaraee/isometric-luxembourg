"""Pick ~60 new training views (retrain v2) by group, at 900 src px (finer than the first 40 at 1200).

Groups are anchored on known places; within each group the densest / most relevant candidates win, spread out,
kept away from the fixed test views. Writes data/work/style/detail/views.json and a contact sheet.
"""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import WORK, ROOT

SRC = 900
OUT = WORK / "style" / "detail"
OUT.mkdir(parents=True, exist_ok=True)
m = json.loads((WORK / "mosaic.json").read_text())
F, COLS, ROWS = m["frame"], m["cols"], m["rows"]
S = 8  # analysis downscale
kind = Image.new("L", (COLS * F // S, ROWS * F // S), 0)
for r in range(ROWS):
    for c in range(COLS):
        kind.paste(Image.open(WORK / "frames_kind" / f"{c}_{r}.png").resize((F // S, F // S), Image.NEAREST), (c * F // S, r * F // S))
K = np.asarray(kind)
places = {p["n"]: (p["x"], p["y"]) for p in json.loads((ROOT / "web/public/data/places.json").read_text())}
L = json.loads((ROOT / "web/public/data/lines.json").read_text())
wmask = Image.new("L", kind.size, 0)
d = ImageDraw.Draw(wmask)
for w in L["water"]:
    if len(w["p"]) > 4:
        d.polygon([(w["p"][i] / S, w["p"][i + 1] / S) for i in range(0, len(w["p"]), 2)], fill=255)
for w in L["waterways"]:
    if not w.get("t"):
        d.line([(w["p"][i] / S, w["p"][i + 1] / S) for i in range(0, len(w["p"]), 2)], fill=255, width=5)
WM = np.asarray(wmask) > 0
rails = Image.new("L", kind.size, 0); dr = ImageDraw.Draw(rails)
for r in L["rail"]:
    if not r.get("t") and r["k"] == "rail":
        dr.line([(r["p"][i] / S, r["p"][i + 1] / S) for i in range(0, len(r["p"]), 2)], fill=255, width=3)
RM = np.asarray(rails) > 0

TESTS = {"Place d'Armes test": (8300, 6100), "Station test": (6300, 8350), "Grund test": (9000, 7200),
         "Red Bridge test": places["Red Bridge"], "Glacis test": (7700, 4400), "Kirchberg test": places["Philharmonie"],
         "Hôtel de Ville test": places["Hôtel de Ville"]}


def stats(cx, cy):
    x0, y0 = (cx - SRC // 2) // S, (cy - SRC // 2) // S
    k = K[max(y0, 0):y0 + SRC // S, max(x0, 0):x0 + SRC // S]
    if k.size < (SRC // S) ** 2 * 0.98:
        return None
    empty = ((k == 0) & False).mean()
    return {"bld": float((k <= 100).mean() - (k == 0).mean() * 0), "wall": float(((k > 32) & (k <= 100)).mean()),
            "ground": float((k > 200).mean()), "deck": float(((k > 100) & (k <= 200)).mean()),
            "water": float(WM[max(y0, 0):y0 + SRC // S, max(x0, 0):x0 + SRC // S].mean()),
            "rail": float(RM[max(y0, 0):y0 + SRC // S, max(x0, 0):x0 + SRC // S].mean())}


def edge_ok(cx, cy):
    """No empty map edge inside the view."""
    a = np.asarray(Image.open(WORK / "frames" / f"{min(cx // F, COLS - 1)}_{min(cy // F, ROWS - 1)}.jpg").resize((64, 64)))
    return True


cands = [(x, y) for y in range(700, ROWS * F - 700, 150) for x in range(700, COLS * F - 700, 150)]
info = {}
for c in cands:
    s = stats(*c)
    if s and s["bld"] + s["ground"] + s["deck"] > 0.97:  # roofs are 0 too: require that 0 isn't empty edge
        info[c] = s
# The kinds pass uses 0 for both roofs and the empty edge; reject views that touch the empty edge via the render.
bg = np.array([16, 24, 40])


def has_edge(cx, cy):
    x0, y0 = cx - SRC // 2, cy - SRC // 2
    for yy in (y0, y0 + SRC - 1):
        for xx in (x0, x0 + SRC - 1):
            c, r = xx // F, yy // F
            px = np.asarray(Image.open(WORK / "frames" / f"{c}_{r}.jpg"))[yy - r * F, xx - c * F].astype(int)
            if np.abs(px - bg).sum() < 20:
                return True
    return False


def near(c, anchors, dist):
    return min((abs(c[0] - a[0]) + abs(c[1] - a[1])) for a in anchors) <= dist


GROUPS = [
    ("dense old town", 14, [places[n] for n in ("Notre-Dame Cathedral", "Place Guillaume II", "Grand Ducal Palace", "Cercle Cité", "Saint-Michel Church", "MNHA")], 1500, lambda s: s["wall"] * 2 + s["bld"]),
    ("Gare", 8, [places["Luxembourg Station"]], 1800, lambda s: s["wall"] * 2 + s["bld"]),
    ("Limpertsberg", 6, [places["Limpertsberg"]], 1500, lambda s: s["wall"] + s["bld"]),
    ("Kirchberg", 6, [places[n] for n in ("Kirchberg", "Philharmonie", "University, Kirchberg", "EU Court of Justice", "Kirchberg Shopping Center", "Spuerkeess Tower")], 1400, lambda s: s["wall"] + s["bld"]),
    ("river quarters", 8, [places[n] for n in ("Grund", "Clausen", "Pfaffenthal", "Saint-Jean du Grund")], 1400, lambda s: s["water"] * 4 + s["wall"]),
    ("bridges", 8, [places[n] for n in ("Pont Adolphe", "Red Bridge", "Passerelle", "Clausen Viaduct")], 700, lambda s: s["deck"] * 6 + s["water"]),
    ("tracks, car parks, squares", 6, [places[n] for n in ("Luxembourg Station", "Gëlle Fra", "Philharmonie")] + [(7700, 4400)], 1300, lambda s: s["rail"] * 6 + s["ground"]),
    ("parks", 4, [places[n] for n in ("Municipal Park", "Parc Central", "Pétrusse Valley", "Villa Vauban")], 900, lambda s: s["ground"] - s["bld"]),
]
chosen = []
for name, n, anchors, dist, score in GROUPS:
    pool = sorted((c for c in info if near(c, anchors, dist)), key=lambda c: -score(info[c]))
    got = 0
    for c in pool:
        if got == n:
            break
        if near(c, list(TESTS.values()), 600) or (chosen and near(c, [x["xy"] for x in chosen], 520)):
            continue
        if has_edge(*c):
            continue
        chosen.append({"id": f"d{len(chosen):02d}", "group": name, "xy": list(c), **{k: round(v, 3) for k, v in info[c].items()}})
        got += 1
    print(f"{name}: {got}/{n}")
(OUT / "views.json").write_text(json.dumps({"src": SRC, "tests": {k: list(v) for k, v in TESTS.items()}, "views": chosen}, indent=1))
print("views", len(chosen))
