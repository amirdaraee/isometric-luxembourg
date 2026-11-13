"""The viewer's non-tile data for layers 10 (night), 12 (vehicles) and 15 (labels).

night.bin      windows, doors and shop fronts facing the camera (float32 x 8 each: x, y, z of the lower-left
               corner relative to the camera origin, the along-wall vector (ux, uy), height, building index, kind:
               0 window, 1 door, 2 shop front, + 4 in a building with a shop; 8 to 13 a window of a place of
               worship (stained glass, layer-10 rule 5): 8 and 9 a lancet, round and pointed, 10 and 11 a
               traceried window, round and pointed, 12 a rose, 13 an oculus; 16 a row that is never lit. A
               belfry opening has no glass and no row)
lamps.bin      OSM street lamps (float32 x 3: x, y, z of the lamp head)
vehicles.json  the drivable roads in the v1 simulation's input form (RoadLine, units of 0.25 m in the plan,
               y = -north) and every edge's height profile; transit.json in v1's TransitData form, on the matched
               graph edges, with each GTFS trip's times as distances along its matched path
labels.json    landmarks, places, quarters and street names with their height, v2 pixel and priority
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import LineString, Point, shape

from v2.config import CONFIG, raw_dir
from v2.config.camera import camera
from v2.layers.common import R2, project
from v2.layers.light import LIGHT

UNIT = 0.25            # simulation units: v1's map pixel was 0.25 m
NIGHT_CHURCH = {("lancet", "round"): 8, ("lancet", "pointed"): 9, ("traceried", "round"): 10, ("traceried", "pointed"): 11,
                ("rose", "round"): 12, ("rose", "pointed"): 12, ("oculus", "round"): 13, ("oculus", "pointed"): 13}
NIGHT_DARK = 16


def cam_origin():
    return tuple(camera()["origin_en"])


def _h(s):
    return int(hashlib.blake2s(s.encode(), digest_size=4).hexdigest(), 16) / 0xFFFFFFFF


# ------------------------------------------------------------------------------------------------ night
def night_data(R):
    sc = R.scene
    oe, on = cam_origin()
    bidx = {b["id"]: i for i, b in enumerate(sc.buildings)}
    shops = defaultdict(bool)
    for w in sc.facades["walls"]:
        if w["shopfronts"] or (w.get("house_rule") or {}).get("shopfronts"):
            shops[w["building"]] = True
    rows, church = [], []
    tc = np.array([R2, -R2])                      # horizontal direction towards the camera (south-east)
    for w in sc.facades["walls"]:
        nx, ny = w["normal"]
        bi = bidx.get(w["building"])
        seen = nx * tc[0] + ny * tc[1] > 0.02
        hr = w.get("house_rule")
        if hr and bi is not None:
            # a church's wall. The rows the house rule had here stay as rows that are never lit: a window's seed in
            # the viewer is its row number, so every other window is lit or dark as it was. They were rows when
            # the wall faced the camera in the house rule's frame (the church rule may have turned the wall round)
            was = -1.0 if "outline" in hr else 1.0
            if was * (nx * tc[0] + ny * tc[1]) > 0.02:
                rows += [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, bi, NIGHT_DARK]] * (len(hr["windows"]) + hr["doors"] + hr["shopfronts"])
        if not seen or bi is None:
            continue
        (e0, n0, z0), (e1, n1, _) = w["base"]
        L = w["length"] or 1.0
        ux, uy = (e1 - e0) / L, (n1 - n0) / L
        if w.get("worship"):
            # a church's wall: its windows go to the end of the list, and its doors are dark
            for r in w["windows"]:
                code = NIGHT_CHURCH.get((r[4] if len(r) > 4 else "lancet", w["worship"]))
                if code is None:                              # a belfry opening: louvres, no glass
                    continue
                u0, v0, u1, v1 = (float(x) for x in r[:4])
                church.append([e0 + ux * u0 + nx * 0.06 - oe, n0 + uy * u0 + ny * 0.06 - on, z0 + v0, ux * (u1 - u0),
                               uy * (u1 - u0), v1 - v0, bi, code])
            continue
        for kind, rects in ((0, w["windows"]), (1, w["doors"]), (2, w["shopfronts"])):
            for r in rects:
                u0, v0, u1, v1 = (float(x) for x in r[:4])
                ex, ny_ = e0 + ux * u0 + nx * 0.06, n0 + uy * u0 + ny * 0.06
                code = kind + (4 if shops[w["building"]] else 0)
                rows.append([ex - oe, ny_ - on, z0 + v0, ux * (u1 - u0), uy * (u1 - u0), v1 - v0, bi, code])
    win = np.array(rows + church, np.float32).reshape(-1, 8)
    lamps = []
    g = json.loads(R.ground_osm_path.read_text()) if R.ground_osm_path else {"elements": []}
    from v2.data.geo import lonlat_to_en
    pts = [(el["lon"], el["lat"]) for el in g["elements"] if el["type"] == "node" and el.get("tags", {}).get("highway") == "street_lamp"]
    if pts:
        e, n = lonlat_to_en(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))
        inside = shapely.contains_xy(sc.polygon, e, n)
        e, n = e[inside], n[inside]
        z = R.hf.sample(e, n) + LIGHT["night"]["lamp_height_m"]
        lamps = np.column_stack([e - oe, n - on, z]).astype(np.float32)
    else:
        lamps = np.zeros((0, 3), np.float32)
    return win, np.asarray(lamps, np.float32)


# ------------------------------------------------------------------------------------------------ vehicles
def plan_xy(e, n):
    oe, on = cam_origin()
    return (np.asarray(e) - oe) / UNIT, -(np.asarray(n) - on) / UNIT


def vehicles_data(sc):
    g = sc.graph
    edges, roads = [], []
    for i, e in enumerate(g["edges"]):
        en = np.array(e["en"], float)
        edges.append({"m": e["mode"], "st": e["structure"], "s": [round(v / UNIT, 2) for v in e["s"]],
                      "z": [round(v, 2) for v in e["z"]], "id": e["id"]})
        if e["mode"] != "road":
            continue
        x, y = plan_xy(en[:, 0], en[:, 1])
        r = {"id": i, "k": e.get("cls", ""), "o": str(e.get("oneway")) == "True",
             "b": e["structure"] == "bridge", "t": e["structure"] == "tunnel",
             "l": e.get("layer"), "w": float(e["width"]),
             "p": [round(float(v), 2) for xy in zip(x, y) for v in xy]}
        if e.get("name"):
            r["n"] = e["name"]
        roads.append(r)
    return {"unit_m": UNIT, "origin_en": list(cam_origin()), "edges": edges, "roads": roads}


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def _sec(t):
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def transit_data(sc, transit_params):
    """v1's TransitData on the v2 graph: one 'shape' per matched run (its path over graph edges), trips as
    [arrival s, departure s, distance along the path] at every stop (extrapolated past the path's ends)."""
    from v2.data.geo import lonlat_to_en
    g = sc.graph
    eidx = {e["id"]: i for i, e in enumerate(g["edges"])}
    T = sc.transit
    gdir = raw_dir() / transit_params["gtfs_dir"]
    want = {s["shape"] for s in T["shapes"]}
    # GTFS: shapes, trips, stops, stop times for the shapes that touch the area
    gshape = defaultdict(list)
    for r in _rows(gdir / "shapes.txt"):
        if r["shape_id"] in want:
            gshape[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    glines = {}
    for sid, pts in gshape.items():
        pts.sort()
        e, n = lonlat_to_en(np.array([p[1] for p in pts]), np.array([p[2] for p in pts]))
        glines[sid] = LineString(np.column_stack([e, n]))
    routes = {r["route_id"]: r for r in _rows(gdir / "routes.txt")}
    cal = list(_rows(gdir / "calendar.txt"))
    caldates = list(_rows(gdir / "calendar_dates.txt"))
    DOW = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_mask = defaultdict(int)
    for day, wd, bit in transit_params["days"]:
        sv = {c["service_id"] for c in cal if c["start_date"] <= day <= c["end_date"] and c[DOW[wd]] == "1"}
        for c in caldates:
            if c["date"] == day:
                (sv.add if c["exception_type"] == "1" else sv.discard)(c["service_id"])
        for s in sv:
            day_mask[s] |= bit
    trips = {}
    for t in _rows(gdir / "trips.txt"):
        if t.get("shape_id") in want and day_mask.get(t["service_id"]):
            r = routes.get(t["route_id"], {})
            trips[t["trip_id"]] = {"shape": t["shape_id"], "mask": day_mask[t["service_id"]],
                                   "line": r.get("route_short_name", ""), "type": r.get("route_type", "")}
    stops = {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"])) for s in _rows(gdir / "stops.txt")}
    st = defaultdict(list)
    for r in _rows(gdir / "stop_times.txt"):
        if r["trip_id"] in trips:
            st[r["trip_id"]].append((int(r["stop_sequence"]), _sec(r["arrival_time"]), _sec(r["departure_time"]), r["stop_id"]))
    # stop positions along each GTFS shape (in order: never going back along it)
    stop_en = {}
    if stops:
        ids = list(stops)
        e, n = lonlat_to_en(np.array([stops[i][0] for i in ids]), np.array([stops[i][1] for i in ids]))
        stop_en = {i: (float(a), float(b)) for i, a, b in zip(ids, e, n)}
    out = {"shapes": [], "runs": [], "tunnels": [], "trips": []}
    tunnels = set()
    shape_runs = {}
    for s in T["shapes"]:
        sid = s["shape"]
        line = glines.get(sid)
        if line is None:
            continue
        for run in s["runs"]:
            pts, rr, cum = [], [], 0.0
            for eid, a, b in run:
                i = eidx[eid]
                e = g["edges"][i]
                en = np.array(e["en"], float)
                es = np.array(e["s"], float)
                ss = np.linspace(a, b, max(2, int(abs(b - a) / 2) + 1))
                x = np.interp(ss, es, en[:, 0]); y = np.interp(ss, es, en[:, 1])
                seg = np.column_stack([x, y])
                if pts and np.hypot(*(np.array(pts[-1]) - seg[0])) < 0.5:
                    seg = seg[1:]
                pts.extend(seg.tolist())
                rr.append([i, round(a / UNIT, 2), round(b / UNIT, 2)])
                if e["structure"] == "tunnel":
                    tunnels.add(i)
            if len(pts) < 2:
                continue
            P = np.array(pts)
            pc = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
            gd = np.array([line.project(Point(p)) for p in P])
            gd = np.maximum.accumulate(gd) if gd[-1] >= gd[0] else np.minimum.accumulate(gd)
            k = len(out["shapes"])
            x, y = plan_xy(P[:, 0], P[:, 1])
            out["shapes"].append([round(float(v), 2) for xy in zip(x, y) for v in xy])
            out["runs"].append(rr)
            shape_runs.setdefault(sid, []).append((k, pc / UNIT, gd))
    out["tunnels"] = sorted(tunnels)
    kind_of = {"0": "tram", "2": "train", "7": "funicular"}
    for tid, info in trips.items():
        sid = info["shape"]
        if sid not in shape_runs or tid not in st:
            continue
        line = glines[sid]
        seq = sorted(st[tid])
        sd, last = [], -1.0
        for _, arr, dep, stop in seq:
            p = stop_en.get(stop)
            if p is None:
                continue
            d = line.project(Point(p))
            d = max(d, last)
            last = d
            sd.append((arr, dep, d))
        if len(sd) < 2:
            continue
        for k, pcu, gd in shape_runs[sid]:
            lo, hi = min(gd[0], gd[-1]), max(gd[0], gd[-1])
            if sd[-1][2] < lo - 50 or sd[0][2] > hi + 50:
                continue
            # GTFS distance -> path distance (linear past the ends: a train comes in and leaves at speed)
            fwd = gd[-1] >= gd[0]
            gx, px_ = (gd, pcu) if fwd else (gd[::-1], pcu[::-1])
            uniq = np.r_[True, np.diff(gx) > 1e-6]
            gx, px_ = gx[uniq], px_[uniq]
            if len(gx) < 2:
                continue

            def to_path(d):
                if d <= gx[0]:
                    return px_[0] + (d - gx[0]) / UNIT * (1 if fwd else -1)
                if d >= gx[-1]:
                    return px_[-1] + (d - gx[-1]) / UNIT * (1 if fwd else -1)
                return float(np.interp(d, gx, px_))
            tt = [[a, b, round(to_path(d), 1)] for a, b, d in sd]
            # keep the stops around the path (one either side of it)
            L = pcu[-1]
            inside = [i for i, (_, _, d) in enumerate(tt) if -400 <= d <= L + 400]
            if not inside:
                # passes through without a stop near: keep the stops either side of the path
                before = [i for i, (_, _, d) in enumerate(tt) if d < 0]
                after = [i for i, (_, _, d) in enumerate(tt) if d > L]
                if not before or not after:
                    continue
                inside = [before[-1], after[0]]
            i0, i1 = max(min(inside) - 1, 0), min(max(inside) + 1, len(tt) - 1)
            kind = kind_of.get(info["type"], "train")
            out["trips"].append({"s": k, "k": kind, "n": info["line"], "t": tt[i0:i1 + 1], "d": info["mask"]})
    return out


# ------------------------------------------------------------------------------------------------ labels
def labels_data(R):
    sc = R.scene
    out = []
    for p in sc.places:
        if not shapely.contains_xy(sc.polygon, p["e"], p["n"]):
            continue
        cat = p.get("category", "")
        prio = 1 if p.get("featured") else (2 if p.get("source") == "landmark" else 4)
        out.append({"name": p["name"], "slug": p.get("slug", ""), "cat": cat, "src": p.get("source", ""),
                    "e": p["e"], "n": p["n"], "z": p["z"], "prio": prio, "v1_px": p.get("v1_px")})
    q = json.loads((CONFIG / "areas" / "commune_quarters.geojson").read_text())
    from v2.data.geo import to_en_geom
    for f in q["features"]:
        g = to_en_geom(shape(f["geometry"]))
        inter = g.intersection(sc.polygon)
        if inter.is_empty or inter.area < 20000:
            continue
        p = inter.representative_point()
        name = f["properties"].get("name") or f["properties"].get("name:lb") or ""
        if not name:
            continue
        out.append({"name": name, "cat": "quarter", "src": "quarter", "e": p.x, "n": p.y,
                    "z": float(R.hf.sample(p.x, p.y)), "prio": 3})
    best = {}
    for i, e in enumerate(sc.graph["edges"]):
        if e["mode"] != "road" or not e.get("name") or e["structure"] == "tunnel" or e.get("cls") in ("service",):
            continue
        L = float(e["length"])
        if L > best.get(e["name"], (0, None))[0]:
            best[e["name"]] = (L, i)
    for name, (L, i) in best.items():
        if L < 40:
            continue
        e = sc.graph["edges"][i]
        en = np.array(e["en"], float)
        z = np.array(e["z"], float)
        k = len(en) // 2
        if not shapely.contains_xy(sc.polygon, en[k, 0], en[k, 1]):
            continue
        a = en[max(k - 1, 0)]
        b = en[min(k + 1, len(en) - 1)]
        pa = project(a[0], a[1], z[max(k - 1, 0)])
        pb = project(b[0], b[1], z[min(k + 1, len(en) - 1)])
        ang = math.degrees(math.atan2(pb[1] - pa[1], pb[0] - pa[0]))
        if ang > 90:
            ang -= 180
        if ang < -90:
            ang += 180
        out.append({"name": name, "cat": "street", "src": "osm", "e": float(en[k, 0]), "n": float(en[k, 1]),
                    "z": float(z[k]), "prio": 5, "angle": round(ang, 1), "len_m": round(L)})
    for o in out:
        px, py, d = project(o["e"], o["n"], o["z"])
        o["px"], o["py"], o["depth"] = round(float(px), 1), round(float(py), 1), round(float(d), 2)
        o["e"], o["n"], o["z"] = round(o["e"], 2), round(o["n"], 2), round(o["z"], 2)
    out.sort(key=lambda o: (o["prio"], o["name"]))
    return out
