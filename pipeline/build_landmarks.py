"""Landmark cards from research/ (01-landmarks, 02-buildings-interiors): facts, photos with credits, interiors,
plus a small 3D model of each landmark building from the CityGML data.

Writes web/public/data/landmarks.json, web/public/landmarks/<slug>/*.webp (1200 px) and <slug>/model.bin
(float32 xyz triangles in metres, centred, z up; then uint8 kind per triangle: 1 roof, 2 wall).

Optional rows in a README section: Quarter, Facts (one per line, separated by <br>), Visiting, Sources (markdown links), Model ("no" for monuments and sites without a building of their own),
Interior ("none" when the name-based match with 02-buildings-interiors would pick a different building).
The downloaded originals in research/*/images are not under version control: when one is missing but its .webp was
built before, the existing .webp is used as it is.
"""
import json
import math
import re
from pathlib import Path
import numpy as np
from PIL import Image
from common import ROOT, WORK, ORIGIN_E, ORIGIN_N, R, ELEV, lonlat_to_en, landmark_slug, readme_sections

RES = ROOT / "research"
OUT = ROOT / "web/public/landmarks"
OUT.mkdir(parents=True, exist_ok=True)
m = json.loads((WORK / "mosaic.json").read_text())
t = np.load(WORK / "terrain.npz")
tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])


def to_px(lat, lon):
    e, n = lonlat_to_en(lon, lat)
    iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1); ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
    z = float(tz[iy, ix]); le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R; sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return round((sx - m["sx0"]) / m["mpp"]), round((m["sy1"] - sy) / m["mpp"]), e, n, z


slug, sections = landmark_slug, readme_sections


def md_links(s):
    return re.findall(r"\[`([^`]+)`\]\([^)]*\): ([^<\n]+)", s)


def links(s):
    return [{"title": t, "url": u} for t, u in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", s)]


def webp(src, dst):
    """Convert a research image once; True when the card can show it."""
    if not dst.exists() and src.exists():
        im = Image.open(src).convert("RGB"); im.thumbnail((1200, 1200)); im.save(dst, quality=80)
    return dst.exists()


credits = {}
for folder in ("01-landmarks", "02-buildings-interiors"):
    for r in json.loads((RES / folder / "sources.json").read_text()):
        credits[f"{folder}/{r['file']}"] = {"author": r.get("author", ""), "licence": r.get("licence", ""),
                                            "licence_url": r.get("licence_url", ""), "source": r.get("source_page", "")}

inter = {}
for title, rows, blk in sections((RES / "02-buildings-interiors/README.md").read_text()):
    key = title.split("(")[0].strip()
    imgs = [(f, cap.split(" (")[0].strip()) for f, cap in re.findall(r"^- \[`([^`]+)`\]\([^)]*\): (.+)$", blk, re.M)]
    inter[key] = {"rows": rows, "images": imgs}

B = np.load(WORK / "buildings.npz")
tris, kind, bld, g = B["tris"][..., :3], B["tri_kind"], B["tri_bld"], B["bld_ground"]

cards = []
for title, rows, blk in sections((RES / "01-landmarks/README.md").read_text()):
    if "Coordinates" not in rows:
        continue
    lat, lon = map(float, rows["Coordinates"].split(","))
    x, y, e, n, z = to_px(lat, lon)
    if not (0 <= x < m["cols"] * m["frame"] and 0 <= y < m["rows"] * m["frame"]):
        continue
    s = slug(title.split("(")[0])
    d = OUT / s
    d.mkdir(exist_ok=True)
    photos = []
    for f, cap in md_links(rows.get("Images", "")):
        src = RES / "01-landmarks/images" / f
        dst = d / (Path(f).stem.split("__")[-1] + ".webp")
        if webp(src, dst):
            photos.append({"src": f"/landmarks/{s}/{dst.name}", "caption": cap, **credits.get(f"01-landmarks/images/{f}", {})})
    # interiors: match on the first two words of the name
    ALIAS = {"City Hall": "Hôtel de Ville", "National Museum of History and Art": "Nationalmusée um Fëschmaart",
             "Luxembourg City History Museum": "Lëtzebuerg City Museum", "St. Michael's Church": "Saint-Michel Church",
             "Neumünster Abbey": "Neimënster Abbey", "Church of St. John the Baptist, Grund": "Saint-Jean du Grund",
             "National Museum of Natural History": "Natur Musée", "Luxembourg railway station": "Gare Centrale",
             "Court of Justice of the European Union": "Court of Justice of the European Union",
             "Philharmonie Luxembourg": "Philharmonie Luxembourg", "Spuerkeess": "Spuerkeess"}
    nm = title.split("(")[0].strip()
    ik = next((k for k in inter if ALIAS.get(nm) and k.startswith(ALIAS[nm])), None) or next((k for k in inter if k.lower().split()[:2] == title.lower().split()[:2] or title.lower().split("(")[0].strip() in k.lower()), None)
    if rows.get("Interior") == "none":  # the name-based match above would pick a different building
        ik = None
    interior = None
    if ik:
        iv = inter[ik]
        ips = []
        for f, cap in iv["images"]:
            src = RES / "02-buildings-interiors/images" / f
            dst = d / ("in-" + Path(f).stem.split("__")[-1] + ".webp")
            if webp(src, dst):
                ips.append({"src": f"/landmarks/{s}/{dst.name}", "caption": cap, **credits.get(f"02-buildings-interiors/images/{f}", {})})
        interior = {k.lower().replace(", ", "_").replace(" ", "_"): v for k, v in iv["rows"].items()}
        interior["photos"] = ips
    # 3D model: the CityGML building whose ground centre is nearest (within 45 m)
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    dist = np.hypot(g[:, 0] - le, g[:, 1] - ln)
    has_model = False
    near = np.where(dist < 45)[0]
    if len(near) and rows.get("Category", "") not in ("square", "bridge", "park", "valley", "fortification") and rows.get("Model", "") != "no":
        ids = near[np.argsort(dist[near])][:1]
        # landmarks are often split into several CityGML buildings: take all within 25 m of the nearest
        ids = np.where(np.hypot(g[:, 0] - g[ids[0], 0], g[:, 1] - g[ids[0], 1]) < 25)[0]
        sel = np.isin(bld, ids) & (kind != 0)
        if sel.sum() > 20:
            T = tris[sel].astype(np.float32)
            c = T.reshape(-1, 3).mean(0); c[2] = T[..., 2].min()
            T -= c
            (d / "model.bin").write_bytes(T.tobytes() + kind[sel].astype(np.uint8).tobytes())
            has_model = True
    wiki = re.findall(r"\((https?://[^)]+)\)", rows.get("Wikipedia", ""))
    cards.append({"slug": s, "name": title.split("(")[0].strip(), "local": rows.get("Local name", ""),
                  "category": rows.get("Category", ""), "x": x, "y": y, "about": rows.get("About", ""),
                  "photos": photos, "interior": interior, "model": f"/landmarks/{s}/model.bin" if has_model else None,
                  "wikipedia": wiki[0] if wiki else None})
    if (d / "cutaway.webp").exists():
        cards[-1]["cutaway"] = f"/landmarks/{s}/cutaway.webp"
    for key, row in (("quarter", "Quarter"), ("visiting", "Visiting")):
        if rows.get(row):
            cards[-1][key] = rows[row]
    if rows.get("Facts"):
        cards[-1]["facts"] = [f.strip() for f in rows["Facts"].split("<br>") if f.strip()]
    if rows.get("Sources"):
        cards[-1]["sources"] = links(rows["Sources"])
(ROOT / "web/public/data/landmarks.json").write_text(json.dumps(cards, ensure_ascii=False, indent=0))
print(len(cards), "landmarks;", sum(1 for c in cards if c["interior"]), "with interiors;", sum(1 for c in cards if c["model"]), "with 3D models;",
      sum(len(c["photos"]) for c in cards), "photos")
