"""Fit the streets and tracks that vehicles use to the roads and rails as they are painted (no repainting).

The painter did not put every road exactly where OpenStreetMap has it. Two parts:
  1. A global offset per painted block. The painter moves its whole output a few px down (LAYERS_POC.md: about 6-7 px
     at painting scale). Measured block by block in two ways: phase correlation of the edges of the painted block
     against the 3D render it was painted from (mostly buildings), and from the roads themselves: cross-sections of
     the OSM roads against the painted asphalt (as in part 2, up to 5 m), each a sideways constraint, solved for one
     2D shift per block by trimmed least squares. The road measure is used (it is what vehicles need; it comes out
     about 3 px further down than the edge one and 1-4 px right); blocks with fewer than 500 clear road sections
     take the median of the others. The rail measure is printed as a check only (few clear rail sections).
     A map px takes the offset of the block whose painting is on top there (the last in data/work/tiles/painted.json
     that covers it, as build_tiles.py lays them).
  2. A local fit along every street and track. Painted asphalt and painted rail beds are found by colour, with a
     colour model learnt from the art itself (cells on the shifted centrelines against the ground beside them), within
     a band round each line. Every 4 m along a way, a cross-section of the mask is matched against the expected
     layout across it (this way and its neighbours at their widths: a template, so parallel carriageways and multiple
     tracks keep their spacing); the best sideways move within 3 m is kept where the match is clear. The moves are
     filtered (median, then a Gaussian, 6 m) and fall back to the block offset where nothing is clear (trees, a
     building in front, a painted car). Bridges and tunnels take the block offset only.
     Where ways meet, the displacement is one vector (a least-squares fit to each way's sideways move), so junctions
     stay joined; it blends into each way's own fit over 12 m.

Writes (keeping every original field):
  web/public/data/lines.json   roads that carry traffic (build_drivable.DRIVE) and rail ways get
                               "q": the fitted polyline (map px, 0.1 px), densified to at most 16 px between points,
                               "qi": for each vertex of "p", its index in "q" (the points between are the segment's
                               even subdivisions, moved). Consumers build the graph from "p" and draw on "q".
                               "qw" (roads, where clear): the painted carriageway's width in m; for information only,
                               traffic keeps "w" (with "qw" fewer cars sat on asphalt: the run often takes in the
                               pavement).
  web/public/data/transit.json "fit": per shape, the fitted points (shapes are densified, geometry unchanged, so stop
                               distances stay valid); build_transit.py writes it too when lines.json has "q".
  web/public/data/road_heights.json  "fx", "fy" per deck profile: its sample points moved like its way.
  web/public/data/roadfit/     index.json and <tx>_<ty>.png tiles (like drivable/) of the painted masks: bit 1 asphalt,
                               2 rail bed, 4 unpainted, 16 painted road (asphalt, gaps up to 3.5 m closed), 8 the guard
                               (16 grown by GUARD_M: Overlay fades a car outside it); for the guard, ?roaddebug and the
                               headless check.
  data/work/roadfit/shifts.json  the measured block offsets (the edge offsets are cached; --remeasure redoes them).

With the render -> painting field (flow_field.py, data/work/flowfit/field.npz; task T2b), which is the default when it
exists: part 1 is replaced by the field's road layer (a dense move per 8 map px instead of one per block; shifts.json
then records what the cross-sections still find left over per block), and part 2 moves at most 1 m (FIELD_MAXOFF_M).
The asphalt colour model also has a second model among dark cells (asphalt in the shade of buildings). The guard is
the painted road grown by GUARD_M (2 m). --no-field gives the T2 behaviour.

Order: project_lines.py -> flow_field.py -> build_drivable.py -> build_occlusion.py -> fit_roads.py (build_transit.py
may run any time after); fit_to_art.py runs them all.
Re-run after the day art changes (e.g. painted cars repaired) or after project_lines.py rewrites lines.json:
    cd pipeline && .venv/bin/python fit_to_art.py        (everything: the field, drivable, occlusion, this, checks)
(about 50 minutes, 4.7 GB at most; fit_roads.py alone: 2 minutes, 3.8 GB; `node src/sim/roadfit.test.ts` in web/ checks.)
Usage: fit_roads.py [--shifts-only] [--remeasure] [--no-field] [--debug OUT X0 Y0 X1 Y1]
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter1d

from build_drivable import CELL, DRIVE, art, default_width, lateral, load_grid, osm_tags, painted_water, VALUES
from common import ROOT, WORK
from flowfield import Field as FlowField
from roadfit_geom import Field, densify, pts, transit_fit

Image.MAX_IMAGE_PIXELS = None
RAIL = {"rail", "tram", "light_rail", "funicular"}
OUT = WORK / "roadfit"
DATA = ROOT / "web/public/data"
TILE = 512
STEP_M = 4.0            # stations along a way
WALK_M = 0.25           # sample step across it
MAXOFF_M = 3.0          # largest local move (on the block offsets)
FIELD_MAXOFF_M = 1.0    # largest local move on the field (flow_field.py)
SHADOW_V = 90            # darker than this (max of R, G, B): in shade
GUARD_M = 2.0           # the guard: the painted road grown by this (with the field the lines are on it; the guard
                        # only has to catch streets the painter left out)
BLEND_M = 12.0          # junction blend
RAIL_HALF_M = 1.5       # half the painted bed of one track
WHY = {"clear": 0, "no template": 0, "blocked": 0, "little asphalt": 0, "flat": 0}   # station outcomes, for the log


# ------------------------------------------------------------------------------------------------- blocks
def blocks():
    return json.loads((WORK / "tiles" / "painted.json").read_text())


def owner_grid(shape, bl):
    """Per cell: index of the block painted on top (-1 none)."""
    H, W = shape
    own = np.full((H, W), -1, np.int8)
    for i, b in enumerate(bl):
        x0, y0 = max(b["x0"] // CELL, 0), max(b["y0"] // CELL, 0)
        x1, y1 = min((b["x0"] + b["w"]) // CELL, W), min((b["y0"] + b["h"]) // CELL, H)
        own[y0:y1, x0:x1] = i
    return own


def render_crop(mos, x0, y0, w, h):
    F = mos["frame"]
    out = np.zeros((h, w), np.float32)
    for r in range(mos["rows"]):
        for c in range(mos["cols"]):
            fx, fy = c * F, r * F
            ix0, iy0, ix1, iy1 = max(x0, fx), max(y0, fy), min(x0 + w, fx + F), min(y0 + h, fy + F)
            if ix0 >= ix1 or iy0 >= iy1:
                continue
            a = np.asarray(Image.open(WORK / "frames" / f"{c}_{r}.jpg").convert("L"), np.float32)
            out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] = a[iy0 - fy:iy1 - fy, ix0 - fx:ix1 - fx]
    return out


def phase_shift(b, mos, tile=512, step=400):
    """Median (dx, dy, n) in map px of the painted block against the render, by phase correlation of edges."""
    P = np.asarray(Image.open(WORK / "tiles" / b["file"]).convert("L"), np.float32)
    P = cv2.resize(P, (b["w"], b["h"]), interpolation=cv2.INTER_AREA)
    Rr = render_crop(mos, b["x0"], b["y0"], b["w"], b["h"])
    win = cv2.createHanningWindow((tile, tile), cv2.CV_64F)

    def ed(a):
        return cv2.Laplacian(cv2.GaussianBlur(a, (0, 0), 1.5), cv2.CV_32F).astype(np.float64)
    got = []
    for y in range(0, b["h"] - tile + 1, step):
        for x in range(0, b["w"] - tile + 1, step):
            if (Rr[y:y + tile, x:x + tile] < 5).mean() > 0.3 or (P[y:y + tile, x:x + tile] < 5).mean() > 0.3:
                continue
            (dx, dy), r = cv2.phaseCorrelate(ed(Rr[y:y + tile, x:x + tile]), ed(P[y:y + tile, x:x + tile]), win)
            if r > 0.08 and abs(dx) < 25 and abs(dy) < 25:
                got.append((dx, dy))
    if not got:
        return 0.0, 0.0, 0
    g = np.array(got)
    return float(np.median(g[:, 0])), float(np.median(g[:, 1])), len(g)


def block_shift(cons):
    """Robust least-squares 2D shift (map px) from sideways constraints [(ux, uy, v)]: u a unit vector (map px), v the
    measured move along it (map px). Rounds dropping constraints far off the fit. Returns (dx, dy, n kept, median
    residual px, n) or None where too few or one direction is poorly covered."""
    c = np.array(cons, float).reshape(-1, 3)
    if len(c) < 200:
        return None
    keep = np.ones(len(c), bool)
    for _ in range(4):
        e = np.linalg.lstsq(c[keep, :2], c[keep, 2], rcond=None)[0]
        r = np.abs(c[:, :2] @ e - c[:, 2])
        keep = r < max(2.5, float(np.percentile(r, 50)))
    r = np.abs(c[keep, :2] @ e - c[keep, 2])
    ev = np.linalg.eigvalsh(c[keep, :2].T @ c[keep, :2] / keep.sum())
    if ev.min() < 0.1:
        return None
    return float(e[0]), float(e[1]), int(keep.sum()), float(np.median(r)), len(c)


# ------------------------------------------------------------------------------------------------- geometry helpers

def raster(ways, shape, half_m, key=None):
    """Union of bands along the polylines (key: a function giving the (n, 2) points), half_m(way) metres either side,
    at cell resolution, with round joins."""
    m = np.zeros(shape, np.uint8)
    for w in ways:
        p = key(w) if key else pts(w)
        hm = half_m(w)
        for (ax, ay), (bx, by) in zip(p[:-1], p[1:]):
            (lx, ly), _ = lateral(bx - ax, by - ay)
            ox, oy = lx * hm, ly * hm
            quad = np.array([[ax + ox, ay + oy], [bx + ox, by + oy], [bx - ox, by - oy], [ax - ox, ay - oy]])
            cv2.fillPoly(m, [np.round(quad / CELL * 4).astype(np.int32)], 1, shift=2)
        r = max(1, int(round(hm * 3 / CELL)))
        for x, y in p:
            cv2.circle(m, (int(round(x / CELL * 4)), int(round(y / CELL * 4))), r * 4, 1, -1, shift=2)
    return m.astype(bool)


class Shifts:
    """The block offset at any map px."""

    def __init__(self, own, bl, sh, field=None):
        self.own, self.v = own, np.array([sh[b["block"]] for b in bl] + [np.median([sh[b["block"]] for b in bl], 0)])
        self.field = field                # flowfield.Field (ground layer): replaces the block offsets

    def at(self, p):
        if self.field is not None:
            return self.field.at(p)
        H, W = self.own.shape
        cx = np.clip((p[:, 0] / CELL).astype(int), 0, W - 1)
        cy = np.clip((p[:, 1] / CELL).astype(int), 0, H - 1)
        o = self.own[cy, cx].astype(int)
        o[o < 0] = len(self.v) - 1
        return self.v[o]


# ------------------------------------------------------------------------------------------------- the masks
def colour_mask(rgb, pos, neg, own=None, ratio=1.3, min_hits=10, min_pos=20000, shadow=False):
    """Cells whose colour (4096 bins) is clearly likelier on `pos` than on `neg`. With `own` (the block grid), one
    model per painted block (the blocks were painted apart and their tones differ), the whole map's model for blocks
    with too few positive cells."""
    q = rgb >> 4
    ci = (q[..., 0].astype(np.int32) << 8) | (q[..., 1].astype(np.int32) << 4) | q[..., 2]
    del q

    def model(p, n):
        hp = np.bincount(ci[p], minlength=4096).astype(np.float64)
        hn = np.bincount(ci[n], minlength=4096).astype(np.float64)
        pp = (hp + 5 * hp.sum() / 4096) / (hp.sum() * 2)
        pn = (hn + 5 * hn.sum() / 4096) / (hn.sum() * 2)
        return (pp / pn > ratio) & (hp >= min_hits)
    good = model(pos, neg)
    m = good[ci]
    sizes = [int(good.sum())]
    if own is not None:
        for i in range(int(own.max()) + 1):
            r = own == i
            if (pos & r).sum() < min_pos:
                continue
            g = model(pos & r, neg & r)
            m[r] = g[ci[r]]
            sizes.append(int(g.sum()))
    if shadow:
        # in the shade of buildings the painted asphalt is a dark blue that the model above, against all the ground
        # beside the streets, does not pick out: a second model among dark cells only (shaded road against shaded
        # pavement, verge, square)
        dark = rgb.max(2) < SHADOW_V
        if (pos & dark).sum() >= 2000:
            gd = model(pos & dark, neg & dark)
            m |= dark & gd[ci]
            sizes.append(int(gd.sum()))
    del ci
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    print(f"  colour model: {pos.sum()} positive cells, {neg.sum()} negative; {sizes[0]} of 4096 colours"
          + (f", per block {min(sizes[1:])}..{max(sizes[1:])}" if len(sizes) > 1 else ""), flush=True)
    return m


# ------------------------------------------------------------------------------------------------- the local fit
def stations(p, step_m):
    """Points every step_m metres (ground) along polyline p (map px): (points (k, 2), unit lateral px/m (k, 2),
    station distance in m (k,))."""
    out, lat, dist = [], [], []
    carry, at = step_m / 2, 0.0
    for (ax, ay), (bx, by) in zip(p[:-1], p[1:]):
        (lx, ly), mpp = lateral(bx - ax, by - ay)
        L = math.hypot(bx - ax, by - ay) * mpp
        s = carry
        while s < L:
            f = s / L
            out.append((ax + (bx - ax) * f, ay + (by - ay) * f)); lat.append((lx, ly)); dist.append(at + s)
            s += step_m
        carry = s - L
        at += L
    return np.array(out).reshape(-1, 2), np.array(lat).reshape(-1, 2), np.array(dist)


def sample(grid, P):
    H, W = grid.shape
    cx, cy = (P[..., 0] / CELL).astype(int), (P[..., 1] / CELL).astype(int)
    ok = (cx >= 0) & (cy >= 0) & (cx < W) & (cy < H)
    out = np.zeros(P.shape[:-1], grid.dtype)
    out[ok] = grid[cy[ok], cx[ok]]
    return out


def fit_way(q, mask, tmpl, half_m, blocked, maxoff=None):
    """Sideways move (m, along the lateral of `lateral`) per station of shifted polyline q: (stations, lat, dist,
    move or nan, painted width m or nan)."""
    S, L, D = stations(q, STEP_M)
    if not len(S):
        return S, L, D, np.zeros(0), np.zeros(0)
    O = int(round((maxoff or MAXOFF_M) / WALK_M))
    Kw = int(math.ceil((half_m + 3.0) / WALK_M))
    k = np.arange(-Kw - O, Kw + O + 1) * WALK_M
    P = S[:, None, :] + L[:, None, :] * k[None, :, None]
    M = sample(mask, P).astype(np.float32)
    T = sample(tmpl, P[:, O:O + 2 * Kw + 1]).astype(np.float32)
    B = sample(blocked, P).astype(bool)
    nT = T.sum(1)
    sc = np.stack([(T * (2 * M[:, O + o:O + o + 2 * Kw + 1] - 1)).sum(1) for o in range(-O, O + 1)], 1)
    best = sc.max(1)
    plateau = sc >= (best - 0.04 * nT)[:, None]
    idx = np.arange(-O, O + 1)
    # centre of the plateau around the best (contiguous run through the argmax)
    am = sc.argmax(1)
    move = np.full(len(S), np.nan)
    width = np.full(len(S), np.nan)
    for i in range(len(S)):
        if nT[i] < half_m / WALK_M:
            WHY["no template"] += 1
            continue
        a = b = am[i]
        while a > 0 and plateau[i, a - 1]:
            a -= 1
        while b < 2 * O and plateau[i, b + 1]:
            b += 1
        share = (best[i] / nT[i] + 1) / 2                     # share of template cells on the mask at the move
        why = ("blocked" if (B[i, O:O + 2 * Kw + 1] * T[i]).sum() > 0.4 * nT[i] else "little asphalt" if share < 0.6
               else "flat" if a == 0 and b == 2 * O else None)
        if why:
            WHY[why] += 1
            continue
        WHY["clear"] += 1
        move[i] = (idx[a] + idx[b]) / 2 * WALK_M
        # the painted carriageway's width: the run of mask through the moved centre (gaps up to 0.75 m bridged)
        c = O + Kw + (idx[a] + idx[b]) // 2
        row, gap = M[i], 3
        lo = hi = c
        if row[c]:
            while lo > 0 and row[max(lo - gap, 0):lo].any():
                lo -= 1
            while hi < len(row) - 1 and row[hi + 1:hi + 1 + gap].any():
                hi += 1
            if lo > 0 and hi < len(row) - 1:
                width[i] = (hi - lo + 1) * WALK_M
    return S, L, D, move, width


def smooth_moves(D, move):
    """Fill and filter the moves along a way: a running median over the clear stations (15 m either side), then a
    Gaussian of 6 m; stations with no clear move within 15 m take 0 (the block offset alone). Returns per station."""
    n = len(move)
    ok = ~np.isnan(move)
    if ok.sum() < 2 or ok.mean() < 0.15:
        return np.zeros(n)
    out = np.zeros(n)
    have = np.zeros(n, bool)
    for i in range(n):
        near = ok & (np.abs(D - D[i]) <= 15)
        if near.sum() >= 2:
            out[i] = np.median(move[near]); have[i] = True
    if have.any() and not have.all():
        idx = np.flatnonzero(have)
        # ease from the nearest measured value back to 0 over 15 m
        for i in np.flatnonzero(~have):
            j = idx[np.argmin(np.abs(D[idx] - D[i]))]
            out[i] = out[j] * max(0.0, 1 - (abs(D[j] - D[i]) - 15) / 15)
    if n >= 3:
        out = gaussian_filter1d(out, 6 / STEP_M, mode="nearest")
    return np.clip(out, -MAXOFF_M, MAXOFF_M)


def build_q(ways, shifts, fits):
    """Displacement (map px) for every densified point of every way: block offset + fitted sideways move, one vector
    per shared vertex. fits: {way id: (station points on the shifted line, lateral px/m, station distance m,
    smoothed moves m)}. Returns {way id: (q (n, 2), qi)}."""
    # each way's own displacement at its densified points
    own = {}
    for w in ways:
        p = pts(w)
        d, qi = densify(p)
        base = shifts.at(d)
        f = fits.get(w["id"])
        lat_move = np.zeros_like(d)
        if f is not None and len(f[0]):
            S, L, D, mv = f
            # distance (m) of every densified point along the way, as the stations measure it
            seg = np.diff(d, axis=0)
            mpp = np.array([lateral(dx, dy)[1] for dx, dy in seg]) if len(seg) else np.zeros(0)
            dd = np.r_[0, np.cumsum(np.hypot(seg[:, 0], seg[:, 1]) * mpp)]
            m_at = np.interp(dd, D, mv) if len(D) > 1 else np.full(len(dd), mv[0])
            # the lateral vector (px per m) at each point
            lat = np.array([lateral(*(d[min(i + 1, len(d) - 1)] - d[max(i - 1, 0)]))[0] for i in range(len(d))])
            lat_move = lat * m_at[:, None]
            dist = dd
        else:
            seg = np.diff(d, axis=0)
            mpp = np.array([lateral(dx, dy)[1] for dx, dy in seg]) if len(seg) else np.zeros(0)
            dist = np.r_[0, np.cumsum(np.hypot(seg[:, 0], seg[:, 1]) * mpp)]
        own[w["id"]] = (p, d, qi, base, lat_move, dist)
    # shared vertices: least squares over the incident ways' moves at that vertex
    inc = {}
    for wid, (p, d, qi, base, lm, dist) in own.items():
        for j, v in enumerate(p):
            inc.setdefault((int(round(v[0])), int(round(v[1]))), []).append((wid, qi[j]))
    node = {}
    for key, lst in inc.items():
        if len(lst) < 2:
            continue
        A, b = [], []
        for wid, k in lst:
            lm = own[wid][4][k]
            n = np.hypot(*lm)
            if n < 1e-6:
                # no move: a soft constraint towards none along this way's lateral
                d = own[wid][1]
                (lx, ly), _ = lateral(*(d[min(k + 1, len(d) - 1)] - d[max(k - 1, 0)]))
                u = np.array([lx, ly]) / (math.hypot(lx, ly) or 1)
                A.append(u); b.append(0.0)
            else:
                A.append(lm / n); b.append(n)
        A, b = np.array(A), np.array(b)
        lam = 0.05
        e = np.linalg.solve(A.T @ A + lam * np.eye(2), A.T @ b)
        node[key] = e
    out = {}
    for wid, (p, d, qi, base, lm, dist) in own.items():
        disp = base + lm
        total = dist[-1] if len(dist) else 0
        for j in (0, len(p) - 1):
            key = (int(round(p[j][0])), int(round(p[j][1])))
            if key not in node:
                continue
            e = node[key]
            k = qi[j]
            dd = np.abs(dist - dist[k])
            reach = min(BLEND_M, total / 2)
            t = np.clip(dd / max(reach, 1e-6), 0, 1)[:, None]
            near = dd < reach
            disp[near] = (base + e * (1 - t) + lm * t)[near]
        # interior shared vertices (a way passing through a junction) take the node vector exactly
        for j in range(1, len(p) - 1):
            key = (int(round(p[j][0])), int(round(p[j][1])))
            if key in node:
                k = qi[j]
                dd = np.abs(dist - dist[k])
                t = np.clip(dd / BLEND_M, 0, 1)[:, None]
                near = dd < BLEND_M
                disp[near] = (disp * t + (base + node[key]) * (1 - t))[near]
        out[wid] = (d + disp, qi)
    return out


# ------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiles", type=Path, default=ROOT / "web/public/tiles/map_files")
    ap.add_argument("--shifts-only", action="store_true")
    ap.add_argument("--remeasure", action="store_true", help="measure the block offsets again (else cached)")
    ap.add_argument("--debug", nargs=5, metavar=("OUT", "X0", "Y0", "X1", "Y1"))
    ap.add_argument("--no-field", action="store_true", help="block offsets and 3 m local moves (as T2), not the field")
    a = ap.parse_args()
    global MAXOFF_M
    FF = None if a.no_field else FlowField.load("road")
    if FF is not None:
        MAXOFF_M = FIELD_MAXOFF_M
        print(f"base: the road layer of data/work/flowfit/field.npz; local moves up to {MAXOFF_M} m", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    mos = json.loads((WORK / "mosaic.json").read_text())
    shape = (mos["rows"] * mos["frame"] // CELL, mos["cols"] * mos["frame"] // CELL)
    bl = blocks()
    lines = json.loads((DATA / "lines.json").read_text())
    tags = osm_tags()
    roads = [w for w in lines["roads"] if w.get("k") in DRIVE and len(w["p"]) >= 4]
    rails = [w for w in lines["rail"] if w.get("k") in RAIL and len(w["p"]) >= 4]
    w0 = {w["id"]: (w.get("w") or default_width(w, tags)) for w in roads}

    # 1a. edge offsets
    sf = OUT / "shifts.json"
    rec = json.loads(sf.read_text()) if sf.exists() and not a.remeasure else {}
    if FF is not None:
        # the field replaces the block offsets: no edge offsets needed (shifts.json records what is left over)
        rec = {b["block"]: {"phase": [0.0, 0.0, 99]} for b in bl}
    for b in bl:
        if b["block"] not in rec or "phase" not in rec[b["block"]]:
            dx, dy, n = phase_shift(b, mos)
            rec[b["block"]] = {"phase": [round(dx, 2), round(dy, 2), n]}
            print(f"{b['block']}: edges dx {dx:.2f} dy {dy:.2f} px ({n} tiles)", flush=True)
    good = [v["phase"][:2] for v in rec.values() if v["phase"][2] >= 20]
    med = np.median(good, 0)
    phase = {k: (v["phase"][:2] if v["phase"][2] >= 20 else list(med)) for k, v in rec.items()}
    own = owner_grid(shape, bl)
    sh0 = Shifts(own, bl, phase, FF)

    # 1b. the art and the colour models (learnt on lines moved by the edge offsets)
    rgb = art(shape, a.tiles)
    unpainted = np.abs(rgb.astype(np.int16) - [16, 24, 40]).max(axis=2) <= 8
    water = painted_water(shape, DATA)
    print("art", flush=True)
    main_k = ("primary", "secondary", "tertiary", "residential", "unclassified")
    ok = ~water & ~unpainted
    reach = lambda w: min(max(w0[w["id"]] * 0.75 + 1.5, 3.0), 14.0)

    def masks(key):
        """Asphalt and rail bed masks, the colour models learnt on the lines placed by key(way) -> points."""
        centre = raster([w for w in roads if w.get("k") in main_k and not w.get("b") and not w.get("t")], shape,
                        lambda w: 1.0, key)
        near = raster(roads, shape, lambda w: reach(w) + 3.0, key)
        ring = raster(roads, shape, lambda w: reach(w) + 7.0, key) & ~near
        asp = colour_mask(rgb, centre & ok, ring & ok, own, shadow=True) & ok
        del centre, ring
        core = raster([w for w in rails if not w.get("t") and not w.get("b")], shape, lambda w: 0.6, key)
        neart = raster(rails, shape, lambda w: RAIL_HALF_M + 4.0, key)
        rring = raster(rails, shape, lambda w: RAIL_HALF_M + 9.0, key) & ~neart & ~near
        bed = colour_mask(rgb, core & ok, rring & ok, own, ratio=1.5, min_pos=5000) & ok
        return asp, bed, near, neart
    asphalt, railbed, near_r, near_t = masks(lambda w: pts(w) + sh0.at(pts(w)))

    # 1c. road and rail offsets per block: cross-sections of the unshifted lines against the masks, each a sideways
    # constraint on the block's 2D shift (with the field: of the lines moved through it, so what is left over)
    grid, _ = load_grid(DATA)
    blocked = (grid == VALUES["hidden"]) | (grid == VALUES["building"]) | (grid == VALUES["unpainted"])
    del grid
    cons = {"road": [[] for _ in bl], "rail": [[] for _ in bl]}
    k0 = (lambda w: pts(w) + sh0.at(pts(w))) if FF else None
    tm0 = raster([w for w in roads if not w.get("t")], shape, lambda w: w0[w["id"]] / 2, k0)
    tt0 = raster([w for w in rails if not w.get("t")], shape, lambda w: RAIL_HALF_M, k0)
    H, W = shape
    for kind, ways, mask, tmpl in (("road", roads, asphalt, tm0), ("rail", rails, railbed, tt0)):
        for w in ways:
            if w.get("t") or w.get("b"):
                continue
            hm = w0[w["id"]] / 2 if kind == "road" else RAIL_HALF_M
            S, L, D, mv, wd = fit_way(pts(w) + (sh0.at(pts(w)) if FF else 0), mask, tmpl, hm, blocked, maxoff=5.0)
            for i in np.flatnonzero(np.isfinite(mv)):
                n = math.hypot(*L[i])
                o = own[min(int(S[i, 1] / CELL), H - 1), min(int(S[i, 0] / CELL), W - 1)]
                if o >= 0:
                    cons[kind][o].append((L[i, 0] / n, L[i, 1] / n, mv[i] * n))
    del tm0, tt0
    shifts = {}
    # blocks with too few clear road sections (mostly unpainted) take the median of the blocks measured on roads
    rs = [block_shift(cons["road"][i]) for i in range(len(bl))]
    fallback = list(np.median([r[:2] for r in rs if r and r[2] >= 500], 0)) if any(r and r[2] >= 500 for r in rs) else list(med)
    print("block offsets (map px; + is right / down)" + (", left over after the field:" if FF else ":"), flush=True)
    for i, b in enumerate(bl):
        r = block_shift(cons["road"][i])
        t = block_shift(cons["rail"][i])
        ph = rec[b["block"]]["phase"]
        if r:
            rec[b["block"]]["roads"] = [round(r[0], 2), round(r[1], 2), r[2], round(r[3], 2), r[4]]
        if t:
            rec[b["block"]]["rails"] = [round(t[0], 2), round(t[1], 2), t[2], round(t[3], 2), t[4]]
        use = [0.0, 0.0] if FF else [r[0], r[1]] if r and r[2] >= 500 else fallback
        shifts[b["block"]] = use
        rec[b["block"]]["used"] = [round(float(use[0]), 2), round(float(use[1]), 2)]
        print(f"  {b['block']}: edges ({ph[0]:+.1f}, {ph[1]:+.1f}) from {ph[2]} tiles; roads " +
              (f"({r[0]:+.1f}, {r[1]:+.1f}) from {r[2]} of {r[4]} sections, residual {r[3]:.1f} px" if r else "too few") +
              "; rails " + (f"({t[0]:+.1f}, {t[1]:+.1f}) from {t[2]} of {t[4]}" if t else "too few") +
              f"; used ({use[0]:+.1f}, {use[1]:+.1f})", flush=True)
    sf.write_text(json.dumps(rec, indent=1))
    if a.shifts_only:
        return
    sh = Shifts(own, bl, shifts, FF)

    # 2. local fit, twice: the second time with colour models learnt on the lines of the first
    moved = lambda w: pts(w) + sh.at(pts(w))
    tmpl_r = raster([w for w in roads if not w.get("t")], shape, lambda w: w0[w["id"]] / 2, moved)
    tmpl_t = raster([w for w in rails if not w.get("t")], shape, lambda w: RAIL_HALF_M, moved)
    for rnd in (1, 2):
        fits, stats, qw = {}, {"road": [], "rail": []}, {}
        for kind, ways, mask, tmpl in (("road", roads, asphalt, tmpl_r), ("rail", rails, railbed, tmpl_t)):
            for k in WHY:
                WHY[k] = 0
            for w in ways:
                if w.get("t") or w.get("b"):
                    continue
                hm = w0[w["id"]] / 2 if kind == "road" else RAIL_HALF_M
                S, L, D, mv, wd = fit_way(moved(w), mask, tmpl, hm, blocked)
                if not len(S):
                    continue
                sm = smooth_moves(D, mv)
                fits[w["id"]] = (S, L, D, sm)
                good = wd[np.isfinite(wd)]
                if kind == "road" and len(good) >= 3:
                    d0 = default_width(w, tags)
                    qw[w["id"]] = round(float(min(max(np.median(good), 0.6 * d0), 1.4 * d0)), 1)
                stats[kind].append((np.isfinite(mv).mean(), np.abs(sm).mean(), len(S)))
            tot = max(sum(WHY.values()), 1)
            print(f"round {rnd}, {kind} stations: " + ", ".join(f"{k} {v / tot:.0%}" for k, v in WHY.items()), flush=True)
        for k, s in stats.items():
            s = np.array(s)
            if len(s):
                wsum = s[:, 2].sum()
                print(f"round {rnd}, {k}: {len(s)} ways fitted; clear match at "
                      f"{(s[:, 0] * s[:, 2]).sum() / wsum:.0%} of stations; mean local move "
                      f"{(s[:, 1] * s[:, 2]).sum() / wsum:.2f} m", flush=True)
        qs = build_q(roads + rails, sh, fits)
        if rnd == 1:
            del asphalt, railbed
            asphalt, railbed, near_r, near_t = masks(lambda w: qs[w["id"]][0])
    del tmpl_r, tmpl_t, blocked
    for w in roads + rails:
        q, qi = qs[w["id"]]
        w["q"] = [round(float(c), 1) for v in q for c in v]
        w["qi"] = qi
        w.pop("qw", None)
        if w["id"] in qw:
            w["qw"] = qw[w["id"]]
    for w in lines["roads"] + lines["rail"]:
        if w["id"] not in qs:
            w.pop("q", None); w.pop("qi", None); w.pop("qw", None)
    (DATA / "lines.json").write_text(json.dumps(lines, separators=(",", ":")))
    print(f"lines.json: q for {len(roads)} roads and {len(rails)} rail ways, "
          f"{(DATA / 'lines.json').stat().st_size / 1e6:.2f} MB", flush=True)

    # transit shapes and deck profiles
    tj = DATA / "transit.json"
    transit = json.loads(tj.read_text())
    tf = transit_fit(transit["shapes"], lines)
    if tf:
        transit["shapes"], transit["fit"] = tf
        tj.write_text(json.dumps(transit, separators=(",", ":")))
        print(f"transit.json: {len(tf[1])} fitted shapes", flush=True)
    rh = DATA / "road_heights.json"
    prof = json.loads(rh.read_text())
    byid = {w["id"]: w for w in roads + rails}
    for k, p in prof.items():
        w = byid.get(int(k))
        if not w:
            p.pop("fx", None); p.pop("fy", None)
            continue
        F = Field([(pts(w), w["qi"], np.array(w["q"], float).reshape(-1, 2))])
        P = np.stack([p["x"], p["y"]], 1).astype(float)
        Q = P + F.at(P)
        p["fx"] = [round(float(v), 1) for v in Q[:, 0]]
        p["fy"] = [round(float(v), 1) for v in Q[:, 1]]
    rh.write_text(json.dumps(prof, separators=(",", ":")))

    # masks for the overlay, the guard and the checks, near the lines only: bit 1 asphalt, bit 2 rail bed, bit 4
    # unpainted (the empty map edge), bit 16 painted road: asphalt with gaps up to 3.5 m closed (painted cars,
    # markings, manholes), bit 8 the same grown by GUARD_M: where the viewer may show a road vehicle (the guard)
    closed = cv2.morphologyEx(asphalt.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    g = 2 * int(round(GUARD_M / 0.5)) + 1
    road = cv2.dilate(closed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (g, g))).astype(bool)
    m = ((asphalt & near_r).astype(np.uint8) | ((railbed & near_t).astype(np.uint8) << 1)
         | ((unpainted & (near_r | near_t)).astype(np.uint8) << 2) | ((road & near_r).astype(np.uint8) << 3)
         | ((closed.astype(bool) & near_r).astype(np.uint8) << 4))
    del road, closed
    od = DATA / "roadfit"
    od.mkdir(parents=True, exist_ok=True)
    for f in od.glob("*.png"):
        f.unlink()
    rows, cols = -(-shape[0] // TILE), -(-shape[1] // TILE)
    names, total = [], 0
    for ty in range(rows):
        for tx in range(cols):
            t = m[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE]
            if not t.any():
                continue
            name = f"{tx}_{ty}"
            Image.fromarray(t).save(od / f"{name}.png", optimize=True, compress_level=9)
            total += (od / f"{name}.png").stat().st_size
            names.append(name)
    (od / "index.json").write_text(json.dumps({"cell": CELL, "tile": TILE, "cols": cols, "rows": rows, "w": shape[1],
                                               "h": shape[0], "tiles": names, "bits": {"asphalt": 1, "rail": 2, "unpainted": 4, "guard": 8, "road": 16},
                                               "shifts": {k: [round(float(v[0]), 2), round(float(v[1]), 2)]
                                                          for k, v in shifts.items()}},
                                              separators=(",", ":")))
    print(f"roadfit masks: {len(names)} tiles, {total / 1e6:.2f} MB", flush=True)
    if a.debug:
        debug_image(Path(a.debug[0]), tuple(map(int, a.debug[1:])), m, lines, a.tiles)


def debug_image(dest, box, m, lines, tiles):
    x0, y0, x1, y1 = box
    img = Image.new("RGB", (x1 - x0, y1 - y0))
    for ty in range(y0 // 512, (y1 - 1) // 512 + 1):
        for tx in range(x0 // 512, (x1 - 1) // 512 + 1):
            f = tiles / "15" / f"{tx}_{ty}.webp"
            if f.exists():
                img.paste(Image.open(f).convert("RGB"), (tx * 512 - x0, ty * 512 - y0))
    a = np.asarray(img).astype(np.float32)
    g = m[y0 // CELL:y1 // CELL, x0 // CELL:x1 // CELL]
    g = np.repeat(np.repeat(g, CELL, 0), CELL, 1)[:a.shape[0], :a.shape[1]]
    a[(g & 1) > 0] = a[(g & 1) > 0] * 0.6 + np.array([0, 200, 0]) * 0.4
    a[(g & 2) > 0] = a[(g & 2) > 0] * 0.6 + np.array([200, 0, 200]) * 0.4
    a = a.clip(0, 255).astype(np.uint8)
    for w in lines["roads"] + lines["rail"]:
        if "q" not in w:
            continue
        for key, col in (("p", (255, 60, 60)), ("q", (255, 255, 0))):
            p = np.array(w[key], float).reshape(-1, 2)
            if p[:, 0].max() < x0 or p[:, 0].min() > x1 or p[:, 1].max() < y0 or p[:, 1].min() > y1:
                continue
            cv2.polylines(a, [np.round((p - [x0, y0]) * 4).astype(np.int32)], False, col, 1, cv2.LINE_AA, shift=2)
    Image.fromarray(a).save(dest)
    print("debug", dest)


if __name__ == "__main__":
    main()
