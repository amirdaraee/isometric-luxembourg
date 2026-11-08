"""Before/after pictures of the vehicle lines over the painting (task T2b), for the local dashboard web/public/poc/.

For each spot: the painted map (summer day tiles), twice as large, left the lines as before (BEFORE: a lines.json
with the T2 fit, e.g. from git), right as now; traffic lanes in cyan (laid like traffic.ts: two-way streets one lane
each way either side of the line, one-way streets centred, over the width "w"), rail and tram tracks in blue.

Usage: fit_to_art_images.py BEFORE_LINES.json OUT_DIR [--size 360 240]
Writes OUT_DIR/img/t2b_<slug>.jpg and OUT_DIR/img/t2b_spots.json (the list, for status.json).
"""
import argparse
import json
import math
import re

import cv2
import numpy as np
from PIL import Image

from build_drivable import DRIVE, lateral
from common import ROOT

Image.MAX_IMAGE_PIXELS = None
TILES = ROOT / "web/public/tiles/map_files/15"
Z = 2
# (name, map x, y): spread over the city, the owner's list first
SPOTS = [
    ("Hollow Tooth", 9604, 6685), ("Pfaffenthal quay", 9750, 5640), ("Pfaffenthal lift", 9293, 5432),
    ("Red Bridge", 10209, 5253), ("Boulevard Royal", 7827, 5183), ("Boulevard Royal north", 8417, 5304),
    ("Gare station", 4957, 8099), ("Avenue de la Gare", 5584, 7685), ("Place de Paris", 5474, 7243),
    ("Kirchberg, Avenue JFK at Porte de l'Europe", 13102, 5887), ("Kirchberg, Avenue JFK at the Parliament", 14494, 5846),
    ("Kirchberg, Avenue JFK at the Central Park", 17700, 6146), ("Kirchberg, Avenue JFK east", 20500, 6420),
    ("Grund", 9328, 6854), ("Grund, Neumünster", 9040, 6876), ("Clausen", 10757, 7157), ("Clausen, Saint Cunigunde", 11724, 6848),
    ("Limpertsberg", 8918, 3430), ("Limpertsberg, Boulevard de la Foire", 8417, 4511), ("Glacis", 8374, 4373),
    ("Adolphe Bridge", 6272, 6194), ("Passerelle", 6826, 7295), ("Boulevard Patton", 10293, 8278),
    ("Rue de Trèves", 11463, 7415), ("Côte d'Eich", 11497, 4255), ("Rollingergrund", 6269, 3910),
    ("Boulevard Joseph II", 6683, 4642), ("Avenue Marie-Thérèse", 5786, 5750), ("Rue de Hamm", 9834, 9022),
    ("Rotondes", 6016, 8175), ("Hollerich, Den Atelier", 3079, 7561), ("Rue de la Tour Jacob", 9996, 7146),
]
CYAN, BLUE = (0, 230, 255), (40, 90, 255)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower().replace("è", "e").replace("ü", "u").replace("ô", "o")).strip("-")


def art(x0, y0, w, h):
    out = Image.new("RGB", (w, h))
    for ty in range(y0 // 512, (y0 + h - 1) // 512 + 1):
        for tx in range(x0 // 512, (x0 + w - 1) // 512 + 1):
            f = TILES / f"{tx}_{ty}.webp"
            if f.exists():
                out.paste(Image.open(f).convert("RGB"), (tx * 512 - x0, ty * 512 - y0))
    return np.asarray(out)


def offset(p, m):
    """Polyline p (map px) moved m metres to the right of its direction (the 2:1 view's metres)."""
    out = []
    for i in range(len(p)):
        a, b = p[max(i - 1, 0)], p[min(i + 1, len(p) - 1)]
        (lx, ly), _ = lateral(*(b - a))
        out.append(p[i] + np.array([lx, ly]) * m)
    return np.array(out)


def lanes(w):
    """Lane centre offsets (m right of the drawn line) roughly as traffic.ts lays them."""
    wid = w.get("w") or 6.0
    try:
        n = int(str(w.get("l") or "").split(";")[0])
    except ValueError:
        n = 0
    if w.get("o"):
        n = max(1, n or 1)
        return [(i - (n - 1) / 2) * min(wid / n, 3.5) for i in range(n)]
    per = max(1, (n or 2) // 2)
    return [s * (i + 0.5) * min(wid / 2 / per, 3.5) for s in (1, -1) for i in range(per)]


def draw(img, lines, x0, y0, w, h):
    a = cv2.resize(img, (w * Z, h * Z), interpolation=cv2.INTER_CUBIC).copy()
    for kind in ("roads", "rail"):
        for way in lines[kind]:
            key = "q" if "q" in way else "p"
            p = np.array(way[key], float).reshape(-1, 2)
            if len(p) < 2 or p[:, 0].max() < x0 - 40 or p[:, 0].min() > x0 + w + 40 or p[:, 1].max() < y0 - 40 \
                    or p[:, 1].min() > y0 + h + 40:
                continue
            if kind == "roads":
                if way.get("k") not in DRIVE or way.get("t") or not (way.get("a", 1) & 3):
                    continue
                for m in lanes(way):
                    q = offset(p, m)
                    cv2.polylines(a, [np.round((q - [x0, y0] + 0.5) * Z * 4).astype(np.int32)], False, CYAN, 2,
                                  cv2.LINE_AA, shift=2)
            else:
                if way.get("t"):
                    continue
                cv2.polylines(a, [np.round((p - [x0, y0] + 0.5) * Z * 4).astype(np.int32)], False, BLUE, 2,
                              cv2.LINE_AA, shift=2)
    return a


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("out")
    ap.add_argument("--size", type=int, nargs=2, default=(360, 240))
    a = ap.parse_args()
    from pathlib import Path
    out = Path(a.out) / "img"
    out.mkdir(parents=True, exist_ok=True)
    before = json.loads(Path(a.before).read_text())
    now = json.loads((ROOT / "web/public/data/lines.json").read_text())
    w, h = a.size
    spots = []
    for name, cx, cy in SPOTS:
        x0, y0 = cx - w // 2, cy - h // 2
        img = art(x0, y0, w, h)
        pic = np.concatenate([draw(img, before, x0, y0, w, h), np.full((h * Z, 8, 3), 255, np.uint8),
                              draw(img, now, x0, y0, w, h)], 1)
        f = f"t2b_{slug(name)}.jpg"
        Image.fromarray(pic).save(out / f, quality=85)
        spots.append({"src": f"img/{f}", "caption": f"{name} (#{cx},{cy}): left before (T2), right now",
                      "name": name, "x": cx, "y": cy})
    (out / "t2b_spots.json").write_text(json.dumps(spots, indent=1))
    print(f"{len(spots)} pictures in {out}")


if __name__ == "__main__":
    main()
