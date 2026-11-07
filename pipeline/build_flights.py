"""Flight tracks for the aircraft over the city: departures and arrivals at Findel (ELLX), projected onto the map.

Findel lies just east of the map. Its single runway, 06/24 (4000 m, elevation about 376 m), comes from OpenStreetMap
(aeroway=runway, fetched once from Overpass and kept in data/raw/osm/runway.json). The tracks are simple, believable
procedures, not the published ones:
  dep24n, dep24s  runway 24: lift-off 1800 m down the runway, a straight climb at 7 % to 3000 ft, then a gentle turn to
                  the north (dep24n) or the south (dep24s), climbing on to 6000 ft; they cross the city from the lower
                  right towards the upper left.
  arr06           runway 06: a 3 degree final from 15 km out, which passes low over the city from the west, then the
                  landing roll.
  arr24           runway 24: traffic from the west joins a downwind to the north of the city at 3500 ft and turns
                  onto a final east of the airport (off the map); only its crossing is seen.
  dep06           runway 06: climbs out to the east, off the map (not written; the schedule still counts it).
Each track is sampled every 100 m along the ground and projected with the formula of project_lines.py
(z = elevation + height). Kept only where it is within 6000 map px of the map.

Output web/public/data/flights.json:
  {"elevation": 376, "runway": {"06": [x, y], "24": [x, y]} (threshold ground px),
   "tracks": {name: {"runway": "24" | "06", "kind": "dep" | "arr", "s0": metres along the full track at the first
                     kept sample, "len": full track length in metres (lift-off or threshold to the end, or the start
                     to touchdown), "step": 100, "p": [gx, gy, h, ...]}}}
gx, gy: map px of the ground point under the aircraft (at the terrain height, or the airport's elevation off the
terrain data); h: height above that ground, metres. The aircraft is drawn h * 3.46 map px above (gx, gy).
For a departure, s runs from lift-off; for an arrival, from the start of the track to touchdown and on along the
landing roll (len is the distance to touchdown).

Run: pipeline/.venv/bin/python pipeline/build_flights.py
"""
import json
import math
import urllib.parse
import urllib.request

import numpy as np

from common import ELEV, ORIGIN_E, ORIGIN_N, R, RAW, WEB, WORK, lonlat_to_en

ELEVATION = 376.0
FT = 0.3048
STEP = 100.0
MARGIN = 6000      # map px kept round the map
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
CACHE = RAW / "osm" / "runway.json"

m = json.loads((WORK / "mosaic.json").read_text())
W, H = m["cols"] * m["frame"], m["rows"] * m["frame"]
t = np.load(WORK / "terrain.npz")
tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])


def ground(e, n):
    iy, ix = int((n - tn0) / ts), int((e - te0) / ts)
    if 0 <= iy < tz.shape[0] and 0 <= ix < tz.shape[1]:
        return float(tz[iy, ix])
    return ELEVATION


def to_px(e, n, z):
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R
    sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return (sx - m["sx0"]) / m["mpp"], (m["sy1"] - sy) / m["mpp"]


def runway():
    """The two ends of runway 06/24, (lon, lat): west end (threshold 06) and east end (threshold 24)."""
    if not CACHE.exists():
        q = '[out:json][timeout:25];way["aeroway"="runway"]["ref"="06/24"](49.60,6.17,49.65,6.25);out tags geom;'
        for ep in OVERPASS:
            try:
                req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"User-Agent": "isometric-luxembourg-builder/1.0",
                                                      "Accept": "application/json"})
                CACHE.write_bytes(urllib.request.urlopen(req, timeout=60).read())
                break
            except OSError as e:
                print(f"{ep}: {e}")
        else:
            raise SystemExit("runway: no Overpass server answered")
    way = json.loads(CACHE.read_text())["elements"][0]
    pts = [(g["lon"], g["lat"]) for g in way["geometry"]]
    return min(pts), max(pts)


def path(start, heading_deg, legs):
    """Ground track from `start` (e, n): legs of ("straight", metres) or ("turn", degrees, radius m), each sampled
    every STEP. Headings are true, degrees clockwise from north. Returns an (n, 2) array."""
    e, n = start
    h = math.radians(heading_deg)
    out = [(e, n)]
    for leg in legs:
        if leg[0] == "straight":
            k = int(round(leg[1] / STEP))
            for _ in range(k):
                e += STEP * math.sin(h); n += STEP * math.cos(h)
                out.append((e, n))
        else:
            _, deg, radius = leg
            arc = math.radians(abs(deg)) * radius
            k = max(1, int(round(arc / STEP)))
            dh = math.radians(deg) / k
            for _ in range(k):
                h += dh / 2
                e += STEP * math.sin(h); n += STEP * math.cos(h)
                h += dh / 2
                out.append((e, n))
    return np.array(out)


def write(name, kind, rwy, ground_en, heights, s_end, tracks):
    """Projects and trims one track; heights in metres above the airport's elevation (absolute = 376 + h)."""
    rows = []
    for (e, n), hh in zip(ground_en, heights):
        gz = ground(e, n)
        gx, gy = to_px(e, n, gz)
        rows.append((gx, gy, max(0.0, ELEVATION + hh - gz)))
    keep = [i for i, (x, y, _) in enumerate(rows) if -MARGIN <= x <= W + MARGIN and -MARGIN <= y <= H + MARGIN]
    if not keep:
        print(f"{name}: off the map")
        return
    i0, i1 = keep[0], keep[-1]
    flat = []
    for x, y, hh in rows[i0:i1 + 1]:
        flat += [round(x), round(y), round(hh, 1)]
    tracks[name] = {"runway": rwy, "kind": kind, "s0": i0 * STEP, "len": s_end, "step": STEP, "p": flat}
    on = [r for r in rows if 0 <= r[0] <= W and 0 <= r[1] <= H]
    lo = min((r[2] for r in on), default=float("nan"))
    hi = max((r[2] for r in on), default=float("nan"))
    print(f"{name}: {len(rows)} samples, kept {i1 - i0 + 1}; on the map {len(on)} (height {lo:.0f} to {hi:.0f} m)")


def main():
    (wlon, wlat), (elon, elat) = runway()
    w_en, e_en = np.array(lonlat_to_en(wlon, wlat)), np.array(lonlat_to_en(elon, elat))
    d = w_en - e_en
    length = float(np.linalg.norm(d))
    hdg24 = math.degrees(math.atan2(d[0], d[1])) % 360       # from the east end towards the west end
    hdg06 = (hdg24 + 180) % 360
    u24 = d / length
    print(f"runway {length:.0f} m, 24 heading {hdg24:.1f}, 06 heading {hdg06:.1f} (grid)")
    tracks = {}

    # departures 24: lift-off 1800 m from the 24 threshold, 7 % to 3000 ft, then a gentle turn while climbing on
    lift = e_en + u24 * 1800
    level = 3000 * FT - ELEVATION                       # 3000 ft above sea level, in metres above the field
    to_level = level / 0.07
    top = 6000 * FT - ELEVATION
    for name, turn in (("dep24n", 70), ("dep24s", -75)):
        g = path(lift, hdg24, [("straight", round(to_level, -2)), ("turn", turn, 6000), ("straight", 20000)])
        s = np.arange(len(g)) * STEP
        heights = [min(top, 0.07 * x if x < to_level else level + 0.045 * (x - to_level)) for x in s]
        write(name, "dep", "24", g, heights, float(s[-1]), tracks)

    # arrivals 06: a 3 degree final from 15 km out, touchdown 300 m past the 06 threshold, a 2000 m roll
    touch = w_en - u24 * 300
    start = touch + u24 * 15000
    g = path(start, hdg06, [("straight", 15000 + 2000)])
    s = np.arange(len(g)) * STEP
    heights = [max(0.0, (15000 - x) * math.tan(math.radians(3))) for x in s]
    write("arr06", "arr", "06", g, heights, 15000.0, tracks)

    # arrivals 24: from the west, a high downwind north of the city at 5000 ft, turning to a final east of the field
    north = np.array([-u24[1], u24[0]])
    if north[1] < 0:
        north = -north
    # a line parallel to the runway, 2.5 km to its north-west, flown towards the east, then a right turn of 180
    # degrees onto the final for 24, east of the field
    entry = w_en + north * 2500 + u24 * 16000
    g = path(entry, hdg06, [("straight", 26000), ("turn", 180, 1250), ("straight", 6000)])
    s = np.arange(len(g)) * STEP
    tot = float(s[-1])
    heights = [3500 * FT - ELEVATION - max(0.0, x - 24000) * 0.04 for x in s]
    write("arr24", "arr", "24", g, heights, tot, tracks)

    thr = {k: [round(v) for v in to_px(*en, ELEVATION)] for k, en in (("06", w_en), ("24", e_en))}
    out = {"elevation": ELEVATION, "runway": thr, "heading": {"24": round(hdg24, 1), "06": round(hdg06, 1)},
           "tracks": tracks}
    dst = WEB / "public" / "data" / "flights.json"
    dst.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {dst.relative_to(WEB.parent)} ({dst.stat().st_size // 1024} KB); thresholds {thr}")


if __name__ == "__main__":
    main()
