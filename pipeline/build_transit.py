"""Real trams and trains for the viewer, from the national GTFS timetable (data.public.lu, CC BY).

For three representative days (a weekday, a Saturday and a Sunday): every tram (Luxtram T1) and train trip that
passes through the map, with its track shape and its stop times as distances along that shape, plus `d`, a mask of
the day types it runs on (1 weekday, 2 Saturday, 4 Sunday; trips identical on several day types are stored once). The
viewer interpolates each vehicle's position from the clock and keeps the trips of today's day type (Sundays and
public holidays: 4).

Track shapes follow the OSM rail lines the painting was drawn from. GTFS shapes are coarse (often straight lines
between stops), so each one is matched onto the OSM rail network (lines.json "rail": rail, tram and light rail,
tunnels included, ways joined where they share a node):
  - a point every 20 m along the GTFS shape, with candidate positions on the network within 40 m;
  - a Viterbi pass (a hidden Markov model): the emission cost is the distance from the GTFS point, moved 2 m towards
    the running side of the line (so the train takes the track of its own direction where tracks run side by side),
    the transition cost the difference between the distance along the network and the straight distance;
  - the matched path is the OSM geometry itself (lines.json px), as runs over the ways;
  - stops are projected onto the path (the nearest point, in order along it).
A shape whose matched path is far longer than the GTFS one is a bad match: it is printed and its trips keep the GTFS
geometry (the old way, with heights from the terrain), or are dropped when the terrain is not at hand. A run between
stops faster than 160 km/h (trains) or 70 km/h (trams) is printed.

Running side, line by line: Luxtram drives on the right; the CFL network runs on the left, as in France and Belgium
(the lines through the city: 10 Ettelbruck/Troisvierges, 30 Wasserbillig/Trier, 50 Kleinbettingen/Arlon, 60 Bettembourg
/Esch/Thionville, 70 Rodange/Longwy, 90 Bettembourg/Metz, 10 via Pfaffenthal-Kirchberg). RUNNING_SIDE below.

Writes web/public/data/transit.json:
  {"days", "source", "shapes": [[x, y, ...] map px], "runs": [[[way id, s from, s to], ...] per shape],
   "trips": [{"s" shape, "k" "tram"|"train", "n" line, "t" [[arr s, dep s, px along the shape], ...], "d" mask}]}
  runs: the shape as consecutive stretches of lines.json rail ways, s in map px along the way's lines.json polyline
  (the same units as road_heights.json and deckLift); a shape that kept its GTFS geometry has no runs ([]).
Also pipeline/data/rail_ways.json (in git): the rail ways' ground positions (LUREF metres), so that the timetable can be
rebuilt from lines.json alone (the monthly GitHub Action) without the raw OSM download.

Usage: build_transit.py [--gtfs DIR] [--days auto | YYYYMMDD,YYYYMMDD,YYYYMMDD] [--out FILE]
"""
import argparse
import csv
import datetime
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from common import ELEV, ORIGIN_E, ORIGIN_N, PILOT_LONLAT, RAW, ROOT, WORK, R, lonlat_to_en

GTFS = RAW / "gtfs" / "20261104" / "gtfs"
DAYS = [("20261110", 1, 1), ("20261114", 5, 2), ("20261115", 6, 4)]  # (date, weekday index, mask): Tue, Sat, Sun
RAIL_KINDS = {"rail", "tram", "light_rail"}
RUNNING_SIDE = {"tram": "right", "train": "left"}
SAMPLE_M = 20.0          # matching samples along the GTFS shape
CAND_M = 40.0            # candidate radius
SIGMA_M = 12.0           # GTFS position error
BETA_M = 25.0            # tolerated detour per step
SIDE_M = 2.0             # pull towards the running side
MAX_CAND = 8
OFF_PATH_M = 150.0       # a stop further than this from the matched path is past its end
GAP_SAMPLES = 5          # samples with no rail nearby (100 m) that split a shape
MAX_KMH = {"tram": 70, "train": 160}
RAIL_EN = ROOT / "pipeline" / "data" / "rail_ways.json"


# ------------------------------------------------------------------------------------------------- the network
def rail_ways(lines):
    """The rail ways of lines.json with their ground positions: {id: (kind, tunnel, EN (n, 2), px (n, 2))}. Ground
    positions come from the raw OSM download when present (and are saved to RAIL_EN), else from RAIL_EN."""
    rail = {w["id"]: w for w in lines["rail"] if w.get("k") in RAIL_KINDS}
    osm_file = RAW / "osm" / "lines.json"
    if osm_file.exists():
        en = {}
        for el in json.loads(osm_file.read_text())["elements"]:
            if el.get("type") == "way" and el["id"] in rail and "geometry" in el:
                en[el["id"]] = [lonlat_to_en(g["lon"], g["lat"]) for g in el["geometry"]]
        RAIL_EN.parent.mkdir(parents=True, exist_ok=True)
        RAIL_EN.write_text(json.dumps({"note": "LUREF (EPSG:2169) metres minus (70000, 65000), in decimetres, of the "
                                       "lines.json rail ways (build_transit.py)",
                                       "ways": {str(i): [int(round((c - o) * 10)) for e, n in v
                                                         for c, o in ((e, ORIGIN_E), (n, ORIGIN_N))]
                                                for i, v in en.items()}}, separators=(",", ":")))
    else:
        raw = json.loads(RAIL_EN.read_text())["ways"]
        en = {int(i): [(v[k] / 10 + ORIGIN_E, v[k + 1] / 10 + ORIGIN_N) for k in range(0, len(v), 2)]
              for i, v in raw.items()}
    out = {}
    for i, w in rail.items():
        if i not in en:
            continue
        px = np.array(w["p"], float).reshape(-1, 2)
        e = np.array(en[i], float)
        if len(e) != len(px) or len(e) < 2:
            continue
        out[i] = (w["k"], bool(w.get("t")), e, px)
    return out


class Network:
    """Rail ways as a graph of their vertices (ways meet where they share a vertex), with a segment index."""

    def __init__(self, ways):
        self.ways = ways
        self.ids = list(ways)
        key, self.node = {}, {}                 # (way idx, vertex) -> node
        for wi, i in enumerate(self.ids):
            e = ways[i][2]
            for k, (x, y) in enumerate(e):
                kk = (round(x, 2), round(y, 2))
                if kk not in key:
                    key[kk] = len(key)
                self.node[(wi, k)] = key[kk]
        n = len(key)
        rows, cols, dist = [], [], []
        self.seg = []                           # (way idx, vertex i): segment i .. i + 1
        self.edge = {}                          # (node a, node b) -> (way idx, vertex i, forward)
        for wi, i in enumerate(self.ids):
            e = ways[i][2]
            for k in range(len(e) - 1):
                a, b = self.node[(wi, k)], self.node[(wi, k + 1)]
                if a == b:
                    continue
                L = float(np.hypot(*(e[k + 1] - e[k])))
                rows += [a, b]; cols += [b, a]; dist += [L, L]
                self.edge[(a, b)] = (wi, k, True)
                self.edge[(b, a)] = (wi, k, False)
                self.seg.append((wi, k))
        self.G = csr_matrix((dist, (rows, cols)), shape=(n, n))
        # metres and map px along every way
        self.cm, self.cp = {}, {}
        for wi, i in enumerate(self.ids):
            e, p = ways[i][2], ways[i][3]
            self.cm[wi] = np.r_[0, np.cumsum(np.hypot(*np.diff(e, axis=0).T))]
            self.cp[wi] = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
        a = np.array([self.ways[self.ids[wi]][2][k] for wi, k in self.seg])
        b = np.array([self.ways[self.ids[wi]][2][k + 1] for wi, k in self.seg])
        self.sa, self.sb = a, b
        self.cell = 60.0
        self.grid = defaultdict(list)
        for s, (p, q) in enumerate(zip(a, b)):
            for cx in range(int(math.floor(min(p[0], q[0]) / self.cell)), int(math.floor(max(p[0], q[0]) / self.cell)) + 1):
                for cy in range(int(math.floor(min(p[1], q[1]) / self.cell)), int(math.floor(max(p[1], q[1]) / self.cell)) + 1):
                    self.grid[(cx, cy)].append(s)

    def near(self, x, y, r):
        """Segments within r m of (x, y): list of (segment, t, distance, point)."""
        c = self.cell
        found = set()
        for cx in range(int(math.floor((x - r) / c)), int(math.floor((x + r) / c)) + 1):
            for cy in range(int(math.floor((y - r) / c)), int(math.floor((y + r) / c)) + 1):
                found.update(self.grid.get((cx, cy), ()))
        out = []
        for s in found:
            p, q = self.sa[s], self.sb[s]
            d = q - p
            L2 = float(d @ d) or 1e-9
            t = min(max(((x - p[0]) * d[0] + (y - p[1]) * d[1]) / L2, 0.0), 1.0)
            pt = p + d * t
            dist = math.hypot(pt[0] - x, pt[1] - y)
            if dist <= r:
                out.append((s, t, dist, pt))
        return out


# ------------------------------------------------------------------------------------------------ the matching
def resample(en, step):
    """Points every `step` m along a polyline, with the unit direction there."""
    seg = np.hypot(*np.diff(en, axis=0).T)
    cum = np.r_[0, np.cumsum(seg)]
    L = cum[-1]
    ds = np.linspace(0, L, max(2, int(math.ceil(L / step)) + 1))
    i = np.clip(np.searchsorted(cum, ds, side="right") - 1, 0, len(seg) - 1)
    t = (ds - cum[i]) / np.maximum(seg[i], 1e-9)
    pts = en[i] + (en[i + 1] - en[i]) * t[:, None]
    dirs = (en[i + 1] - en[i]) / np.maximum(seg[i], 1e-9)[:, None]
    return pts, dirs, L


def match(net, en, kind):
    """Matches a GTFS polyline (EN metres) onto the network. Returns the path as a list of (way idx, metres along
    the way) points in order (way runs and turns at shared vertices) and the GTFS length it covers, or None."""
    pts, dirs, _ = resample(en, SAMPLE_M)
    side = 1.0 if RUNNING_SIDE[kind] == "right" else -1.0
    cands = []
    for p, d in zip(pts, dirs):
        right = np.array([d[1], -d[0]])                     # right of travel (E right, N up)
        target = p + right * SIDE_M * side
        cs = net.near(p[0], p[1], CAND_M)
        scored = sorted(((float(np.sum((c[3] - target) ** 2)) / (2 * SIGMA_M ** 2), c) for c in cs), key=lambda z: z[0])
        cands.append(scored[:MAX_CAND])
    keep = [i for i, c in enumerate(cands) if c]
    # A stretch with no rail nearby for more than GAP_SAMPLES samples is where the line leaves the mapped network
    # (lines.json stops a little past the map edge): the pieces either side are matched apart, the longest kept.
    pieces, cur = [], []
    for i in keep:
        if cur and i - cur[-1] > GAP_SAMPLES:
            pieces.append(cur)
            cur = []
        cur.append(i)
    pieces.append(cur)
    best = None
    for piece in sorted(pieces, key=len, reverse=True):
        if len(piece) < 2:
            break
        path = match_piece(net, pts[piece], [cands[i] for i in piece])
        if path:
            best = path, (piece[-1] - piece[0]) * float(np.hypot(*(pts[1] - pts[0])))
            break
    return best


def match_piece(net, pts, cands):
    """The Viterbi pass over one connected stretch of samples and their candidates."""
    n = len(cands)
    acc = np.array([c[0] for c in cands[0]])
    back = []
    routes = []
    for k in range(1, n):
        A, B = cands[k - 1], cands[k]
        straight = float(np.hypot(*(pts[k] - pts[k - 1])))
        src = sorted({net.node[(net.seg[a[1][0]][0], net.seg[a[1][0]][1] + j)] for a in A for j in (0, 1)})
        D, P = dijkstra(net.G, indices=src, limit=straight * 3 + 200, return_predecessors=True)
        row = {s: i for i, s in enumerate(src)}
        cost = np.full((len(A), len(B)), np.inf)
        how = {}
        for ia, (_, ca) in enumerate(A):
            sa, ta = ca[0], ca[1]
            wa, va = net.seg[sa]
            La = net.cm[wa][va + 1] - net.cm[wa][va]
            ua_n, va_n = net.node[(wa, va)], net.node[(wa, va + 1)]
            for ib, (_, cb) in enumerate(B):
                sb, tb = cb[0], cb[1]
                wb, vb = net.seg[sb]
                Lb = net.cm[wb][vb + 1] - net.cm[wb][vb]
                best, via = math.inf, None
                if sa == sb:
                    best, via = abs(tb - ta) * La, ("same",)
                for x, dx in ((ua_n, ta * La), (va_n, (1 - ta) * La)):
                    for y, dy in ((net.node[(wb, vb)], tb * Lb), (net.node[(wb, vb + 1)], (1 - tb) * Lb)):
                        r = dx + D[row[x], y] + dy
                        if r < best:
                            best, via = r, (x, y)
                if best < math.inf:
                    cost[ia, ib] = abs(best - straight) / BETA_M
                    how[(ia, ib)] = via
        tot = acc[:, None] + cost
        arg = np.argmin(tot, axis=0)
        acc = tot[arg, np.arange(len(B))] + np.array([c[0] for c in B])
        if not np.isfinite(acc).any():
            return None                                         # the network is broken here
        back.append(arg)
        routes.append((how, P, row))
    # backtrack
    ib = int(np.argmin(acc))
    chosen = [ib]
    for arg in reversed(back):
        ib = int(arg[ib])
        chosen.append(ib)
    chosen.reverse()
    # the path: positions on ways (way idx, metres along it)
    path = []

    def pos(c):
        s, t = c[0], c[1]
        wi, v = net.seg[s]
        return wi, net.cm[wi][v] + t * (net.cm[wi][v + 1] - net.cm[wi][v])

    path.append(pos(cands[0][chosen[0]][1]))
    for k in range(1, n):
        ca, cb = cands[k - 1][chosen[k - 1]][1], cands[k][chosen[k]][1]
        how, P, row = routes[k - 1]
        via = how[(chosen[k - 1], chosen[k])]
        if via[0] != "same":
            x, y = via
            nodes = [y]
            while nodes[-1] != x:
                nodes.append(P[row[x], nodes[-1]])
                if nodes[-1] < 0:
                    break
            nodes.reverse()
            # leave a's segment through x, then each edge of the node path
            wa, va = net.seg[ca[0]]
            xa = net.cm[wa][va] if x == net.node[(wa, va)] else net.cm[wa][va + 1]
            path.append((wa, xa))
            for a, b in zip(nodes[:-1], nodes[1:]):
                wi, v, fwd = net.edge[(a, b)]
                path.append((wi, net.cm[wi][v] if fwd else net.cm[wi][v + 1]))
                path.append((wi, net.cm[wi][v + 1] if fwd else net.cm[wi][v]))
            wb, vb = net.seg[cb[0]]
            path.append((wb, net.cm[wb][vb] if y == net.node[(wb, vb)] else net.cm[wb][vb + 1]))
        path.append(pos(cb))
    return path


def runs_of(net, path):
    """Path points to runs: [(way idx, metres from, metres to)], consecutive points on one way merged."""
    runs = []
    for wi, m in path:
        if runs and runs[-1][0] == wi:
            r = runs[-1]
            # a turn back on the same way would need a reversing train: keep going the way it went
            if (r[2] - r[1]) * (m - r[2]) >= -1e-6 or abs(r[2] - r[1]) < 1e-6:
                r[2] = m
                continue
        if runs and abs(runs[-1][2] - runs[-1][1]) < 1e-6:
            runs.pop()
        runs.append([wi, m, m])
    return [r for r in runs if abs(r[2] - r[1]) > 0.05]


def along(cm, xs, s):
    """Point of polyline xs (n, 2) at metres s, given its cumulative metres cm."""
    s = min(max(s, 0.0), cm[-1])
    i = min(int(np.searchsorted(cm, s, side="right")) - 1, len(cm) - 2)
    t = (s - cm[i]) / max(cm[i + 1] - cm[i], 1e-9)
    return xs[i] + (xs[i + 1] - xs[i]) * t, i, t


def geometry(net, runs):
    """The path's px and EN polylines (same vertices) and its runs in px: [way id, s from, s to]."""
    px, en, out = [], [], []
    for wi, a, b in runs:
        w = net.ways[net.ids[wi]]
        cm, cp = net.cm[wi], net.cp[wi]
        pa, ia, ta = along(cm, w[3], a)
        pb, ib, tb = along(cm, w[3], b)
        ea, _, _ = along(cm, w[2], a)
        eb, _, _ = along(cm, w[2], b)
        inner = range(ia + 1, ib + 1) if b >= a else range(ia, ib, -1)
        P = [pa] + [w[3][k] for k in inner] + [pb]
        E = [ea] + [w[2][k] for k in inner] + [eb]
        if px and np.hypot(*(np.array(px[-1]) - P[0])) < 0.05:
            P, E = P[1:], E[1:]
        px += [list(p) for p in P]
        en += [list(e) for e in E]
        sa = cp[ia] + ta * (cp[ia + 1] - cp[ia])
        sb = cp[ib] + tb * (cp[ib + 1] - cp[ib])
        out.append([net.ids[wi], round(float(sa), 1), round(float(sb), 1)])
    return np.array(px), np.array(en), out


# ------------------------------------------------------------------------------------------------------- GTFS
def gtfs_rows(g, name):
    with open(g / name, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def auto_days(g):
    """The next Tuesday, Saturday and Sunday from today that the feed covers."""
    cal = list(gtfs_rows(g, "calendar.txt"))
    start = max(datetime.date.today(), min(datetime.datetime.strptime(c["start_date"], "%Y%m%d").date() for c in cal))
    out = []
    for wd, mask in ((1, 1), (5, 2), (6, 4)):
        d = start + datetime.timedelta(days=(wd - start.weekday()) % 7)
        out.append((d.strftime("%Y%m%d"), wd, mask))
    return out


class TerrainPx:
    """The old projection of a GTFS point (terrain height, OSM rail heights nearby): for shapes that fail to match.
    Needs data/work (mosaic.json, terrain.npz) and the raw OSM download."""

    def __init__(self, ways):
        self.m = json.loads((WORK / "mosaic.json").read_text())
        t = np.load(WORK / "terrain.npz")
        self.tz, self.te0, self.tn0, self.ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])
        self.pts = np.concatenate([w[2] for w in ways.values()])
        self.zs = np.concatenate([self.ground(w[2]) for w in ways.values()])

    def ground(self, en):
        iy = np.clip(((en[:, 1] - self.tn0) / self.ts).astype(int), 0, self.tz.shape[0] - 1)
        ix = np.clip(((en[:, 0] - self.te0) / self.ts).astype(int), 0, self.tz.shape[1] - 1)
        return self.tz[iy, ix].astype(float)

    def px(self, en):
        out = []
        for e, n in en:
            d = np.hypot(self.pts[:, 0] - e, self.pts[:, 1] - n)
            i = int(np.argmin(d))
            z = self.zs[i] if d[i] < 25 else float(self.ground(np.array([[e, n]]))[0])
            le, ln = e - ORIGIN_E, n - ORIGIN_N
            sx = (le + ln) * R
            sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
            out.append([(sx - self.m["sx0"]) / self.m["mpp"], (self.m["sy1"] - sy) / self.m["mpp"]])
        return np.array(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gtfs", type=Path, default=GTFS, help="unpacked GTFS folder")
    ap.add_argument("--days", default=None, help="auto, or three dates YYYYMMDD (a Tuesday, Saturday, Sunday)")
    ap.add_argument("--out", type=Path, default=ROOT / "web/public/data/transit.json")
    ap.add_argument("--lines", type=Path, default=ROOT / "web/public/data/lines.json")
    a = ap.parse_args()
    g = a.gtfs
    days = DAYS
    if a.days == "auto":
        days = auto_days(g)
    elif a.days:
        ds = a.days.split(",")
        days = [(d, datetime.datetime.strptime(d, "%Y%m%d").weekday(), m) for d, m in zip(ds, (1, 2, 4))]
    print("days", [d for d, _, _ in days])

    lines = json.loads(a.lines.read_text())
    ways = rail_ways(lines)
    net = Network(ways)
    print(f"rail network: {len(ways)} ways, {net.G.shape[0]} nodes, {len(net.seg)} segments", flush=True)
    try:
        old = TerrainPx(ways)
    except (FileNotFoundError, OSError):
        old = None

    routes = {r["route_id"]: r for r in gtfs_rows(g, "routes.txt") if r["route_type"] in ("0", "2")}
    cal = list(gtfs_rows(g, "calendar.txt"))
    cal_dates = list(gtfs_rows(g, "calendar_dates.txt"))
    DOW = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_mask = defaultdict(int)          # service_id -> day types it runs on
    for day, wd, bit in days:
        services = {c["service_id"] for c in cal if c["start_date"] <= day <= c["end_date"] and c[DOW[wd]] == "1"}
        for c in cal_dates:
            if c["date"] == day:
                (services.add if c["exception_type"] == "1" else services.discard)(c["service_id"])
        for sv in services:
            day_mask[sv] |= bit
    trips = {t["trip_id"]: t for t in gtfs_rows(g, "trips.txt") if t["route_id"] in routes and t["service_id"] in day_mask}
    print("trips on the three days", len(trips))
    W0, S0, E0, N0 = PILOT_LONLAT
    pad = 0.01
    stops = {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]), s["stop_name"]) for s in gtfs_rows(g, "stops.txt")}
    st = defaultdict(list)
    for r in gtfs_rows(g, "stop_times.txt"):
        if r["trip_id"] in trips:
            h, mi, se = map(int, (r["arrival_time"] or r["departure_time"]).split(":"))
            h2, m2, s2 = map(int, (r["departure_time"] or r["arrival_time"]).split(":"))
            st[r["trip_id"]].append((int(r["stop_sequence"]), h * 3600 + mi * 60 + se, h2 * 3600 + m2 * 60 + s2, r["stop_id"]))
    shape_kind = {}
    for tid in st:
        tr = trips[tid]
        if tr.get("shape_id"):
            shape_kind[tr["shape_id"]] = "tram" if routes[tr["route_id"]]["route_type"] == "0" else "train"
    shapes = defaultdict(list)
    for r in gtfs_rows(g, "shapes.txt"):
        if r["shape_id"] in shape_kind:
            shapes[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    inside = lambda lon, lat: W0 - pad <= lon <= E0 + pad and S0 - pad <= lat <= N0 + pad

    out_shapes, out_runs, sid_index, failed = [], [], {}, []
    for sid, p in shapes.items():
        p.sort()
        ll = [(lon, lat) for _, lon, lat in p]
        keep = [i for i, q in enumerate(ll) if inside(*q)]
        if not keep:
            continue
        lo, hi = max(keep[0] - 1, 0), min(keep[-1] + 2, len(ll))
        gen = np.array([lonlat_to_en(*q) for q in ll[lo:hi]])
        glen = float(np.hypot(*np.diff(gen, axis=0).T).sum())
        matched = match(net, gen, shape_kind[sid])
        path, px = None, None
        if matched:
            path, glen = matched
            runs = runs_of(net, path)
            if runs:
                px, en, rr = geometry(net, runs)
                mlen = float(np.hypot(*np.diff(en, axis=0).T).sum())
                if mlen > glen * 1.25 + 300 or mlen < glen * 0.6 - 300:
                    failed.append((sid, shape_kind[sid], round(glen), round(mlen)))
                    px = None
        if px is None:
            if path is None:
                failed.append((sid, shape_kind[sid], round(glen), None))
            if old is None:
                continue
            en, px, rr = gen, old.px(gen), []
        cum_px = np.r_[0, np.cumsum(np.hypot(*np.diff(px, axis=0).T))]
        cum_m = np.r_[0, np.cumsum(np.hypot(*np.diff(en, axis=0).T))]
        sid_index[sid] = (len(out_shapes), en, cum_px, cum_m)
        out_shapes.append([round(float(c), 1) for q in px for c in q])
        out_runs.append(rr)
    print("shapes", len(out_shapes), "matched", sum(1 for r in out_runs if r), flush=True)
    for f in failed:
        print(f"  shape {f[0]} ({f[1]}): {'no match' if f[3] is None else f'matched {f[3]} m against {f[2]} m'}"
              f"{', kept the GTFS geometry' if old else ', dropped'}")

    out_trips, fast = [], []
    for tid, seq in st.items():
        tr = trips[tid]
        if tr.get("shape_id") not in sid_index:
            continue
        k, en, cum_px, cum_m = sid_index[tr["shape_id"]]
        seq.sort()
        pts_t, prev = [], 0.0
        segs_a, segs_b = en[:-1], en[1:]
        dvec = segs_b - segs_a
        L2 = np.maximum((dvec ** 2).sum(1), 1e-9)
        for _, arr, dep, sid in seq:
            lon, lat, _ = stops[sid]
            if not inside(lon, lat) and not pts_t:
                continue
            # the nearest point of the path, no earlier than the previous stop
            e = np.array(lonlat_to_en(lon, lat))
            t = np.clip(((e - segs_a) * dvec).sum(1) / L2, 0, 1)
            q = segs_a + dvec * t[:, None]
            dist = np.hypot(*(q - e).T)
            m_at = cum_m[:-1] + t * np.sqrt(L2)
            dist[m_at < prev - 1] = np.inf
            j = int(np.argmin(dist))
            off = dist[j] > OFF_PATH_M                      # beyond the matched path (off the mapped network)
            if off and not pts_t:
                continue
            prev = float(m_at[j])
            f = t[j]
            pts_t.append([arr, dep, round(float(cum_px[j] + f * (cum_px[j + 1] - cum_px[j])), 1), prev])
            if off or not inside(lon, lat):
                break
        if len(pts_t) >= 2 and pts_t[-1][2] != pts_t[0][2]:
            r = routes[tr["route_id"]]
            kind = "tram" if r["route_type"] == "0" else "train"
            for x, y in zip(pts_t[:-1], pts_t[1:]):
                v = (y[3] - x[3]) / max(y[0] - x[1], 1) * 3.6
                if v > MAX_KMH[kind]:
                    fast.append((r["route_short_name"], tid, round(v)))
            out_trips.append({"s": k, "k": kind, "n": r["route_short_name"], "t": [q[:3] for q in pts_t],
                              "d": day_mask[tr["service_id"]]})
    if fast:
        print(f"{len(fast)} runs between stops faster than the limit, e.g. {fast[:5]}")
    # the same trip on several day types (same track and times) is stored once with the masks combined
    merged = {}
    for tr in out_trips:
        key = (tr["s"], tr["k"], tr["n"], json.dumps(tr["t"]))
        if key in merged:
            merged[key]["d"] |= tr["d"]
        else:
            merged[key] = tr
    out_trips = list(merged.values())
    a.out.write_text(json.dumps({"days": [d for d, _, _ in days],
                                 "source": "GTFS, Administration des transports publics / data.public.lu, CC BY",
                                 "shapes": out_shapes, "runs": out_runs, "trips": out_trips}, separators=(",", ":")))
    print("trips", len(out_trips), {k: sum(1 for x in out_trips if x["k"] == k) for k in ("tram", "train")},
          f"{a.out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
