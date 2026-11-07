"""Project OSM roads, railways and water onto map pixels (same projection as the render and the pins).

Ground features take the terrain height; bridges are interpolated between their two ends (the deck spans
the valley); tunnels are kept but flagged, so traffic can hide there.
Writes web/public/data/lines.json:
  {"roads": [{"id", "n" name, "k" highway kind, "b" bridge, "t" tunnel, "o" oneway, "l" lanes,
              "a" access flags (A_* below), "p" [x, y, ...]}],
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


# Who may drive a road: the "a" field of each road, a sum of these flags (0 = nobody, e.g. footways).
A_CAR = 1         # private cars and vans
A_BUS = 2         # buses
A_DEST = 4        # cars only to reach or leave a place on it, never through traffic
A_EMERGENCY = 8   # emergency vehicles on a call (slowly, on pedestrian streets)
A_BUS_BACK = 16   # buses may also drive against the one-way direction (contraflow bus lane)

DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
            "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "service", "busway"}
NO = {"no", "private", "agricultural", "forestry", "delivery", "permit", "emergency", "military", "discouraged"}
YES = {"yes", "designated", "permissive", "official"}


def access_flags(tg):
    """The "a" flags from OSM highway and access tags. The most specific tag wins (motorcar over motor_vehicle over
    vehicle over access; bus over psv over the general ones). Conditional tags (delivery hours) are ignored."""
    k = tg.get("highway", "")
    if tg.get("area") == "yes" or k not in DRIVABLE | {"pedestrian"}:
        return A_EMERGENCY if tg.get("emergency") in YES else 0
    general = next((tg[t] for t in ("vehicle", "access") if t in tg), None)
    motor = next((tg[t] for t in ("motor_vehicle", "vehicle", "access") if t in tg), None)
    car_v = next((tg[t] for t in ("motorcar", "motor_vehicle", "vehicle", "access") if t in tg), None)
    bus_v = next((tg[t] for t in ("bus", "psv") if t in tg), None)
    bus_only = k == "busway" or tg.get("service") == "bus" or (k == "service" and bus_v == "designated")
    # Cars: never on pedestrian streets (the old town stays car-free even where deliveries or residents may enter),
    # nor on bus-only roads; otherwise as tagged.
    flags = 0
    if k != "pedestrian" and not bus_only:
        if car_v is None or car_v in YES:
            flags |= A_CAR
        elif car_v in ("destination", "customers"):
            flags |= A_CAR | A_DEST
    # Buses: where tagged for them, else wherever motor traffic may pass through (not to a destination only).
    if bus_v is not None:
        if bus_v in YES:
            flags |= A_BUS
    elif bus_only or (k != "pedestrian" and (motor is None or motor in YES) and (general is None or general in YES)):
        flags |= A_BUS
    # Emergency vehicles: any street a vehicle could physically use, unless explicitly not.
    if tg.get("emergency") != "no":
        flags |= A_EMERGENCY
    if flags & A_BUS and tg.get("oneway") == "yes" and "no" in (tg.get("oneway:bus"), tg.get("oneway:psv")):
        flags |= A_BUS_BACK
    return flags


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
                       o=tg.get("oneway") == "yes", l=tg.get("lanes"), a=access_flags(tg))
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
