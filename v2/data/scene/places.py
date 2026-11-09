"""Scene: places and landmarks, reused from v1 (spec: v2/docs/specs/scene.md, "Places").

v1 stores its 129 landmark cards (web/public/data/landmarks.json) and 1,035 places, streets and pins
(web/public/data/places.json) as v1 map pixels on the ground. They are turned back into LUREF metres exactly, with
v1's own terrain (data/work/terrain.npz, the heights the pixels were made with), then given the v2 terrain height and
v2 pixels. Card contents (facts, photos, credits) stay in v1's files and are joined by slug.
"""
from __future__ import annotations

import json

import numpy as np
import shapely

from v2.config import REPO, v1_work
from v2.config.camera import en_to_px, v1_px_to_en
from v2.data.geo import area_polygon, en_to_lonlat
from v2.data.scene.grid import Grid


def v1_ground():
    t = np.load(v1_work() / "terrain.npz")
    tz, e0, n0, s = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])

    def g(e, n):  # v1's sampler: the cell's value (pipeline/build_landmarks.py to_px)
        iy = np.clip(((np.asarray(n) - n0) / s).astype(int), 0, tz.shape[0] - 1)
        ix = np.clip(((np.asarray(e) - e0) / s).astype(int), 0, tz.shape[1] - 1)
        return tz[iy, ix].astype(float)
    return g


def build(ctx):
    lm = json.loads((REPO / "web/public/data/landmarks.json").read_text())
    pl = json.loads((REPO / "web/public/data/places.json").read_text())
    g = v1_ground()
    terrain = Grid.load(ctx.dep("scene_terrain") / "terrain.npz", "mnt")
    poly = area_polygon(ctx.area)
    out = []
    for src, items in (("landmark", lm), ("place", pl)):
        x = np.array([i["x"] for i in items], float); y = np.array([i["y"] for i in items], float)
        e, n, z1 = v1_px_to_en(x, y, g)
        keep = shapely.contains_xy(poly, e, n)
        z2 = terrain.sample(e, n)
        px, py = en_to_px(e, n, np.where(np.isfinite(z2), z2, z1))
        lon, lat = en_to_lonlat(e, n)
        for k in np.flatnonzero(keep):
            it = items[k]
            out.append({"source": src, "slug": it.get("slug"), "name": it.get("name") or it.get("n"),
                        "category": it.get("category") or it.get("c"), "featured": bool(it.get("f", src == "landmark")),
                        "e": round(float(e[k]), 2), "n": round(float(n[k]), 2), "lon": round(float(lon[k]), 6),
                        "lat": round(float(lat[k]), 6), "z_v1": round(float(z1[k]), 2),
                        "z": round(float(z2[k]), 2) if np.isfinite(z2[k]) else None,
                        "v1_px": [it["x"], it["y"]], "px": [round(float(px[k]), 1), round(float(py[k]), 1)]})
    ctx.write_json("places.json", {"places": out})
    return {"places": len(out), "landmarks": sum(1 for p in out if p["source"] == "landmark"),
            "by_category": {c: sum(1 for p in out if p["category"] == c) for c in sorted({p["category"] for p in out})}}
