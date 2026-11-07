"""Real trams and trains for the viewer, from the national GTFS timetable (data.public.lu, CC BY).

For one representative weekday: every tram (Luxtram T1) and train trip that passes through the map, as its track
shape (map px, with deck height on bridges/viaducts taken from the OSM rail model) and its stop times as distances
along that shape. The viewer interpolates each vehicle's position from the clock.
Writes web/public/data/transit.json.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from common import ROOT, RAW, WORK, ORIGIN_E, ORIGIN_N, R, ELEV, lonlat_to_en, PILOT_LONLAT

G = RAW / "gtfs" / "20261104" / "gtfs"
DAY = "20261110"  # a Tuesday inside the feed's validity
m = json.loads((WORK / "mosaic.json").read_text())
W, H = m["cols"] * m["frame"], m["rows"] * m["frame"]
t = np.load(WORK / "terrain.npz")
tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])

# OSM rail/tram vertices with their drawn height (bridges at deck height), for snapping GTFS shapes
osm = json.loads((RAW / "osm" / "lines.json").read_text())["elements"]
pts, zs = [], []
for el in osm:
    tg = el.get("tags", {})
    if el["type"] != "way" or "geometry" not in el or tg.get("railway") not in ("rail", "tram", "light_rail"):
        continue
    en = [lonlat_to_en(g["lon"], g["lat"]) for g in el["geometry"]]
    def ground(e, n):
        iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1); ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
        return float(tz[iy, ix])
    gz = [ground(e, n) for e, n in en]
    if tg.get("bridge", "no") != "no" and len(en) > 1:
        d = np.r_[0, np.cumsum([math.dist(en[i], en[i + 1]) for i in range(len(en) - 1)])]
        gz = list(np.interp(d, [0, d[-1] or 1], [gz[0], gz[-1]]))
    for (e, n), z in zip(en, gz):
        pts.append((e, n)); zs.append(z)
pts, zs = np.array(pts), np.array(zs)


def to_px(lon, lat):
    e, n = lonlat_to_en(lon, lat)
    d = np.hypot(pts[:, 0] - e, pts[:, 1] - n)
    i = int(np.argmin(d))
    if d[i] < 25:
        z = zs[i]
    else:
        iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1); ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
        z = float(tz[iy, ix])
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R; sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return (sx - m["sx0"]) / m["mpp"], (m["sy1"] - sy) / m["mpp"]


def rows(name):
    with open(G / name, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


routes = {r["route_id"]: r for r in rows("routes.txt") if r["route_type"] in ("0", "2")}
services = set()
dow = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][1]
for c in rows("calendar.txt"):
    if c["start_date"] <= DAY <= c["end_date"] and c[dow] == "1":
        services.add(c["service_id"])
for c in rows("calendar_dates.txt"):
    if c["date"] == DAY:
        (services.add if c["exception_type"] == "1" else services.discard)(c["service_id"])
trips = {t["trip_id"]: t for t in rows("trips.txt") if t["route_id"] in routes and t["service_id"] in services}
print("trips today", len(trips))
W0, S0, E0, N0 = PILOT_LONLAT
pad = 0.01
stops = {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]), s["stop_name"]) for s in rows("stops.txt")}
st = defaultdict(list)
for r in rows("stop_times.txt"):
    if r["trip_id"] in trips:
        h, mi, se = map(int, (r["arrival_time"] or r["departure_time"]).split(":"))
        h2, m2, s2 = map(int, (r["departure_time"] or r["arrival_time"]).split(":"))
        st[r["trip_id"]].append((int(r["stop_sequence"]), h * 3600 + mi * 60 + se, h2 * 3600 + m2 * 60 + s2, r["stop_id"]))
shape_ids = {trips[t]["shape_id"] for t in st if trips[t].get("shape_id")}
shapes = defaultdict(list)
for r in rows("shapes.txt"):
    if r["shape_id"] in shape_ids:
        shapes[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
inside = lambda lon, lat: W0 - pad <= lon <= E0 + pad and S0 - pad <= lat <= N0 + pad

out_shapes, sid_index = [], {}
for sid, p in shapes.items():
    p.sort()
    ll = [(lon, lat) for _, lon, lat in p]
    keep = [i for i, q in enumerate(ll) if inside(*q)]
    if not keep:
        continue
    a, b = max(keep[0] - 1, 0), min(keep[-1] + 2, len(ll))
    xy = [to_px(*q) for q in ll[a:b]]
    cum = np.r_[0, np.cumsum([math.dist(xy[i], xy[i + 1]) for i in range(len(xy) - 1)])]
    sid_index[sid] = (len(out_shapes), ll[a:b], np.array(xy), cum)
    out_shapes.append([round(c, 1) for q in xy for c in q])
print("shapes", len(out_shapes))

out_trips = []
for tid, seq in st.items():
    tr = trips[tid]
    if tr.get("shape_id") not in sid_index:
        continue
    k, ll, xy, cum = sid_index[tr["shape_id"]]
    seq.sort()
    pts_t = []
    for _, arr, dep, sid in seq:
        lon, lat, _ = stops[sid]
        if not inside(lon, lat) and not pts_t:
            last = (lon, lat, arr, dep)
            continue
        # distance along shape: nearest shape vertex (in lon/lat; fine at this scale)
        j = int(np.argmin([(lon - q[0]) ** 2 + (lat - q[1]) ** 2 for q in ll]))
        pts_t.append([arr, dep, round(float(cum[j]), 1)])
        if not inside(lon, lat):
            break
    if len(pts_t) >= 2 and pts_t[-1][2] != pts_t[0][2]:
        r = routes[tr["route_id"]]
        out_trips.append({"s": k, "k": "tram" if r["route_type"] == "0" else "train", "n": r["route_short_name"], "t": pts_t})
dest = ROOT / "web/public/data/transit.json"
dest.write_text(json.dumps({"day": DAY, "source": "GTFS, Administration des transports publics / data.public.lu, CC BY",
                            "shapes": out_shapes, "trips": out_trips}, separators=(",", ":")))
print("trips", len(out_trips), {k: sum(1 for x in out_trips if x["k"] == k) for k in ("tram", "train")}, f"{dest.stat().st_size / 1e6:.1f} MB")
