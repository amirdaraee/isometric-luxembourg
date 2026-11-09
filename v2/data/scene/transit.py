"""Scene: trams and trains from the national GTFS timetable, matched onto the rail graph
(spec: v2/docs/specs/transport-graph.md, "Transit").

The matching is v1's hidden Markov model (pipeline/build_transit.py, reviewed and kept), now on the unwarped OSM
geometry of the v2 graph (rail, tram and funicular edges, joined at their shared OSM nodes):
  - a point every sample_m along each GTFS shape that touches the area, with candidate positions on the graph
    within cand_m;
  - a Viterbi pass: emission cost = distance from the GTFS point moved side_m towards the running side (trams
    right, CFL trains left), transition cost = |distance along the graph - straight distance| / beta_m;
  - the matched path is a sequence of graph edges.
A shape is "covered" at a sample when the matched path passes within covered_within_m of it. transit.json holds, per
shape inside the area, its kind, lines, trips per day type, the matched edge runs and its coverage.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict

import numpy as np
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from v2.config import raw_dir
from v2.data.geo import area_polygon, lonlat_to_en
from v2.data.scene.transport import load

RAIL_MODES = {"rail", "tram", "funicular"}


class Network:
    """Rail edges as a graph of their sample points (edges meet at shared OSM nodes), with a segment index."""

    def __init__(self, edges):
        self.edges = edges
        key, self.node = {}, {}
        for wi, ed in enumerate(edges):
            pts = ed["_en"]
            for k in range(len(pts)):
                if k == 0:
                    kk = ("n", ed["a"])
                elif k == len(pts) - 1:
                    kk = ("n", ed["b"])
                else:
                    kk = ("p", wi, k)
                key.setdefault(kk, len(key))
                self.node[(wi, k)] = key[kk]
        rows, cols, dist = [], [], []
        self.seg, self.edge = [], {}
        for wi, ed in enumerate(edges):
            e = ed["_en"]
            for k in range(len(e) - 1):
                a, b = self.node[(wi, k)], self.node[(wi, k + 1)]
                if a == b:
                    continue
                L = float(np.hypot(*(e[k + 1] - e[k])))
                rows += [a, b]; cols += [b, a]; dist += [L, L]
                self.edge[(a, b)] = (wi, k, True); self.edge[(b, a)] = (wi, k, False)
                self.seg.append((wi, k))
        n = len(key)
        self.G = csr_matrix((dist, (rows, cols)), shape=(n, n))
        self.cm = {wi: np.r_[0, np.cumsum(np.hypot(*np.diff(ed["_en"], axis=0).T))] for wi, ed in enumerate(edges)}
        self.sa = np.array([edges[wi]["_en"][k] for wi, k in self.seg])
        self.sb = np.array([edges[wi]["_en"][k + 1] for wi, k in self.seg])
        self.cell = 60.0
        self.grid = defaultdict(list)
        for s, (p, q) in enumerate(zip(self.sa, self.sb)):
            for cx in range(int(math.floor(min(p[0], q[0]) / self.cell)), int(math.floor(max(p[0], q[0]) / self.cell)) + 1):
                for cy in range(int(math.floor(min(p[1], q[1]) / self.cell)), int(math.floor(max(p[1], q[1]) / self.cell)) + 1):
                    self.grid[(cx, cy)].append(s)

    def near(self, x, y, r):
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


def resample(en, step):
    seg = np.hypot(*np.diff(en, axis=0).T)
    cum = np.r_[0, np.cumsum(seg)]
    L = cum[-1]
    ds = np.linspace(0, L, max(2, int(math.ceil(L / step)) + 1))
    i = np.clip(np.searchsorted(cum, ds, side="right") - 1, 0, len(seg) - 1)
    t = (ds - cum[i]) / np.maximum(seg[i], 1e-9)
    pts = en[i] + (en[i + 1] - en[i]) * t[:, None]
    dirs = (en[i + 1] - en[i]) / np.maximum(seg[i], 1e-9)[:, None]
    return pts, dirs


def match(net, en, kind, P):
    """Viterbi over the samples of a GTFS polyline. Returns (sample indices matched, path [(edge idx, metres)])."""
    pts, dirs = resample(en, P["sample_m"])
    side = 1.0 if P["running_side"].get(kind, "right") == "right" else -1.0
    cands = []
    for p, d in zip(pts, dirs):
        right = np.array([d[1], -d[0]])
        target = p + right * P["side_m"] * side
        cs = net.near(p[0], p[1], P["cand_m"])
        scored = sorted(((float(np.sum((c[3] - target) ** 2)) / (2 * P["sigma_m"] ** 2), c) for c in cs), key=lambda z: z[0])
        cands.append(scored[:P["max_cand"]])
    keep = [i for i, c in enumerate(cands) if c]
    pieces, cur = [], []
    for i in keep:
        if cur and i - cur[-1] > P["gap_samples"]:
            pieces.append(cur); cur = []
        cur.append(i)
    if cur:
        pieces.append(cur)
    out_idx, out_path = [], []
    while pieces:
        piece = pieces.pop(0)
        if len(piece) < 2:
            continue
        path = viterbi(net, pts[piece], [cands[i] for i in piece], P)
        if path:
            out_idx += piece
            out_path.append(path)
        elif len(piece) >= 4:
            # one impossible step (a missing crossover, a gap in the mapped track) must not lose the whole run:
            # match the halves apart
            h = len(piece) // 2
            pieces[:0] = [piece[:h], piece[h:]]
    return pts, out_idx, out_path


def viterbi(net, pts, cands, P):
    n = len(cands)
    acc = np.array([c[0] for c in cands[0]])
    back, routes = [], []
    for k in range(1, n):
        A, B = cands[k - 1], cands[k]
        straight = float(np.hypot(*(pts[k] - pts[k - 1])))
        src = sorted({net.node[(net.seg[a[1][0]][0], net.seg[a[1][0]][1] + j)] for a in A for j in (0, 1)})
        D, Pr = dijkstra(net.G, indices=src, limit=straight * 3 + 200, return_predecessors=True)
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
                    cost[ia, ib] = abs(best - straight) / P["beta_m"]
                    how[(ia, ib)] = via
        tot = acc[:, None] + cost
        arg = np.argmin(tot, axis=0)
        acc = tot[arg, np.arange(len(B))] + np.array([c[0] for c in B])
        if not np.isfinite(acc).any():
            return None
        back.append(arg)
        routes.append((how, Pr, row))
    ib = int(np.argmin(acc))
    chosen = [ib]
    for arg in reversed(back):
        ib = int(arg[ib]); chosen.append(ib)
    chosen.reverse()
    path = []

    def pos(c):
        wi, v = net.seg[c[0]]
        return wi, net.cm[wi][v] + c[1] * (net.cm[wi][v + 1] - net.cm[wi][v])
    path.append(pos(cands[0][chosen[0]][1]))
    for k in range(1, n):
        ca, cb = cands[k - 1][chosen[k - 1]][1], cands[k][chosen[k]][1]
        how, Pr, row = routes[k - 1]
        via = how[(chosen[k - 1], chosen[k])]
        if via[0] != "same":
            x, y = via
            nodes = [y]
            while nodes[-1] != x:
                nodes.append(Pr[row[x], nodes[-1]])
                if nodes[-1] < 0:
                    break
            nodes.reverse()
            wa, va = net.seg[ca[0]]
            path.append((wa, net.cm[wa][va] if x == net.node[(wa, va)] else net.cm[wa][va + 1]))
            for a, b in zip(nodes[:-1], nodes[1:]):
                wi, v, fwd = net.edge[(a, b)]
                path.append((wi, net.cm[wi][v] if fwd else net.cm[wi][v + 1]))
                path.append((wi, net.cm[wi][v + 1] if fwd else net.cm[wi][v]))
            wb, vb = net.seg[cb[0]]
            path.append((wb, net.cm[wb][vb] if y == net.node[(wb, vb)] else net.cm[wb][vb + 1]))
        path.append(pos(cb))
    return path


def runs_of(path):
    runs = []
    for wi, m in path:
        if runs and runs[-1][0] == wi:
            runs[-1][2] = m
            continue
        runs.append([wi, m, m])
    return [r for r in runs if abs(r[2] - r[1]) > 0.05]


def path_line(net, runs):
    pts = []
    for wi, a, b in runs:
        en, cm = net.edges[wi]["_en"], net.cm[wi]
        s = np.linspace(a, b, max(2, int(abs(b - a) / 2) + 1))
        pts += list(zip(np.interp(s, cm, en[:, 0]), np.interp(s, cm, en[:, 1])))
    return np.array(pts)


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def build(ctx):
    P = ctx.params["transit"]
    g = load(ctx.dep("scene_transport"))
    edges = [e for e in g["edges"] if e["mode"] in RAIL_MODES]
    for e in edges:
        e["_en"] = np.array(e["en"], float)
    net = Network(edges)
    area = area_polygon(ctx.area)
    gdir = raw_dir() / P["gtfs_dir"]
    routes = {r["route_id"]: r for r in rows(gdir / "routes.txt") if r["route_type"] in ("0", "2", "7")}
    cal = list(rows(gdir / "calendar.txt"))
    caldates = list(rows(gdir / "calendar_dates.txt"))
    DOW = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_mask = defaultdict(int)
    for day, wd, bit in P["days"]:
        sv = {c["service_id"] for c in cal if c["start_date"] <= day <= c["end_date"] and c[DOW[wd]] == "1"}
        for c in caldates:
            if c["date"] == day:
                (sv.add if c["exception_type"] == "1" else sv.discard)(c["service_id"])
        for s in sv:
            day_mask[s] |= bit
    trips = defaultdict(lambda: defaultdict(int))
    shape_info = {}
    for t in rows(gdir / "trips.txt"):
        r = routes.get(t["route_id"])
        if r is None or t["service_id"] not in day_mask or not t.get("shape_id"):
            continue
        kind = {"0": "tram", "2": "train", "7": "funicular"}[r["route_type"]]
        shape_info.setdefault(t["shape_id"], {"kind": kind, "lines": set()})["lines"].add(r["route_short_name"])
        for bit in (1, 2, 4):
            if day_mask[t["service_id"]] & bit:
                trips[t["shape_id"]][bit] += 1
    shapes = defaultdict(list)
    for r in rows(gdir / "shapes.txt"):
        if r["shape_id"] in shape_info:
            shapes[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    x0, y0, x1, y1 = area.bounds
    out, tot_in, tot_cov = [], 0, 0
    for sid, pts in shapes.items():
        pts.sort()
        e, n = lonlat_to_en(np.array([p[1] for p in pts]), np.array([p[2] for p in pts]))
        en = np.column_stack((e, n))
        if not ((en[:, 0] > x0 - 200) & (en[:, 0] < x1 + 200) & (en[:, 1] > y0 - 200) & (en[:, 1] < y1 + 200)).any():
            continue
        line = shapely.linestrings(en)
        if not line.intersects(area):
            continue
        # the part of the shape near the area, with 300 m either side, matched
        near = shapely.contains_xy(area.buffer(300), en[:, 0], en[:, 1])
        k = np.flatnonzero(near)
        lo, hi = max(k[0] - 1, 0), min(k[-1] + 2, len(en))
        sub = en[lo:hi]
        kind = shape_info[sid]["kind"]
        samples, idx, paths = match(net, sub, kind, P)
        inside = shapely.contains_xy(area, samples[:, 0], samples[:, 1])
        runs = [runs_of(p) for p in paths]
        covered = np.zeros(len(samples), bool)
        for rr in runs:
            pl = path_line(net, rr)
            if len(pl) >= 2:
                d = shapely.distance(shapely.linestrings(pl), shapely.points(samples))
                covered |= d <= P["covered_within_m"] + P["side_m"]
        # where the GTFS polyline cuts a corner (it is coarse), it is covered when it is matched at all
        matched = np.zeros(len(samples), bool); matched[idx] = True
        n_in, n_cov = int(inside.sum()), int((inside & (covered | matched)).sum())
        tot_in += n_in; tot_cov += n_cov
        out.append({"shape": sid, "kind": kind, "lines": sorted(shape_info[sid]["lines"]),
                    "trips": {"weekday": trips[sid][1], "saturday": trips[sid][2], "sunday": trips[sid][4]},
                    "samples_in_area": n_in, "covered": n_cov, "share": round(n_cov / n_in, 4) if n_in else None,
                    "near_share": round(float((inside & covered).sum() / n_in), 4) if n_in else None,
                    "runs": [[[edges[wi]["id"], round(a, 1), round(b, 1)] for wi, a, b in rr] for rr in runs],
                    "uncovered": [[round(float(x), 1), round(float(y), 1)] for x, y in samples[inside & ~(covered | matched)][:20]]})
    out = [o for o in out if o["samples_in_area"]]
    ctx.write_json("transit.json", {"source": "GTFS, Administration des transports publics / data.public.lu, CC BY",
                                     "days": P["days"], "shapes": out})
    return {"shapes": len(out), "by_kind": {k: sum(1 for o in out if o["kind"] == k) for k in ("tram", "train", "funicular")},
            "samples_in_area": tot_in, "covered": tot_cov, "share": round(tot_cov / tot_in, 4) if tot_in else None,
            "rail_edges": len(edges)}
