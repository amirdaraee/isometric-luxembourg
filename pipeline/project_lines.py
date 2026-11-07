"""Project OSM roads, railways and water onto map pixels (same projection as the render and the pins).

Ground features take the terrain height; bridges are interpolated between their two ends (the deck spans
the valley); tunnels are kept but flagged, so traffic can hide there.
Writes web/public/data/lines.json:
  {"roads": [{"id", "n" name, "k" highway kind, "b" bridge, "t" tunnel, "o" oneway, "l" lanes, "p" [x, y, ...]}],
   "rail": [...same...], "waterways": [...], "water": [{"id", "p": [...]} polygons]}
"""
import json
import math
import numpy as np
from common import RAW, WORK, ROOT, ORIGIN_E, ORIGIN_N, R, ELEV, lonlat_to_en

m = json.loads((WORK / "mosaic.json").read_text())
t = np.load(WORK / "terrain.npz")
tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])
W, H = m["cols"] * m["frame"], m["rows"] * m["frame"]


def ground(e, n):
    iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1)
    ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
    return float(tz[iy, ix])


def to_px(e, n, z):
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R
    sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return round((sx - m["sx0"]) / m["mpp"]), round((m["sy1"] - sy) / m["mpp"])


def project(geom, bridge=False):
    en = [lonlat_to_en(g["lon"], g["lat"]) for g in geom]
    zs = [ground(e, n) for e, n in en]
    if bridge and len(en) > 1:  # straight deck between the abutments
        d = np.concatenate([[0], np.cumsum([math.dist(en[i], en[i + 1]) for i in range(len(en) - 1)])])
        zs = list(np.interp(d, [0, d[-1] or 1], [zs[0], zs[-1]]))
    pts = [to_px(e, n, z) for (e, n), z in zip(en, zs)]
    if all(not (0 <= x < W and 0 <= y < H) for x, y in pts):
        return None
    return [c for p in pts for c in p]


els = json.loads((RAW / "osm" / "lines.json").read_text())["elements"]
out = {"roads": [], "rail": [], "waterways": [], "water": []}
for el in els:
    tg = el.get("tags", {})
    if el["type"] == "way" and "geometry" in el:
        b = tg.get("bridge", "no") != "no"
        p = project(el["geometry"], bridge=b)
        if not p:
            continue
        rec = {"id": el["id"], "p": p}
        if "highway" in tg:
            rec.update(n=tg.get("name", ""), k=tg["highway"], b=b, t=tg.get("tunnel", "no") != "no",
                       o=tg.get("oneway") == "yes", l=tg.get("lanes"))
            out["roads"].append(rec)
        elif "railway" in tg:
            rec.update(n=tg.get("name", ""), k=tg["railway"], b=b, t=tg.get("tunnel", "no") != "no")
            out["rail"].append(rec)
        elif "waterway" in tg:
            rec.update(n=tg.get("name", ""), k=tg["waterway"], t=tg.get("tunnel", "no") != "no")
            out["waterways"].append(rec)
        else:
            out["water"].append(rec)
    elif el["type"] == "relation":
        for mem in el.get("members", []):
            if mem.get("role") == "outer" and "geometry" in mem:
                p = project(mem["geometry"])
                if p:
                    out["water"].append({"id": el["id"], "p": p})
dest = ROOT / "web" / "public" / "data" / "lines.json"
dest.write_text(json.dumps(out, separators=(",", ":")))
print({k: len(v) for k, v in out.items()}, f"{dest.stat().st_size / 1e6:.1f} MB")

# Parking areas: the base art shows them empty (cars come later as a layer). Rooftop and multi-storey car parks
# sit on a roof, so they take the roof height from the 3D buildings; the rest sit on the ground.
pk = json.loads((RAW / "osm" / "parking.json").read_text())["elements"]
B = np.load(WORK / "buildings.npz")
tri = B["tris"][..., :3]  # local E, N, z
cen = tri[..., :2].mean(axis=1)
GRID = 20.0
cell = np.floor(cen / GRID).astype(np.int64)
order = np.lexsort((cell[:, 1], cell[:, 0]))
keys = cell[order, 0] * 1_000_003 + cell[order, 1]
roof_cache = {}


def roof_z(e, n):
    """Highest roof at a point: max z of building triangles near it."""
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    ci, cj = int(math.floor(le / GRID)), int(math.floor(ln / GRID))
    zs = []
    for a in (ci - 1, ci, ci + 1):
        for b in (cj - 1, cj, cj + 1):
            k = a * 1_000_003 + b
            lo, hi = np.searchsorted(keys, k), np.searchsorted(keys, k, side="right")
            if hi > lo:
                t = tri[order[lo:hi]]
                near = (np.abs(t[..., 0].mean(1) - le) < 15) & (np.abs(t[..., 1].mean(1) - ln) < 15)
                if near.any():
                    zs.append(float(t[near][..., 2].max()))
    return max(zs) if zs else None


out["parking"] = []
for el in pk:
    tg = el.get("tags", {})
    if tg.get("parking") == "underground":
        continue
    geoms = [el["geometry"]] if "geometry" in el else [m["geometry"] for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m]
    for geom in geoms:
        if len(geom) < 3:
            continue
        en = [lonlat_to_en(g["lon"], g["lat"]) for g in geom]
        if tg.get("parking") in ("rooftop", "multi-storey"):
            ce, cn = np.mean([p[0] for p in en]), np.mean([p[1] for p in en])
            zr = roof_z(ce, cn)
            zs = [zr if zr is not None else ground(e, n) for e, n in en]
        else:
            zs = [ground(e, n) for e, n in en]
        pts = [to_px(e, n, z) for (e, n), z in zip(en, zs)]
        if all(not (0 <= x < W and 0 <= y < H) for x, y in pts):
            continue
        out["parking"].append({"id": el["id"], "k": tg.get("parking", "surface"), "p": [c for p in pts for c in p]})
dest.write_text(json.dumps(out, separators=(",", ":")))
print("parking areas", len(out["parking"]), f"{dest.stat().st_size / 1e6:.1f} MB")
