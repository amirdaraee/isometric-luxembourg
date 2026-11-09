"""Checks of the code layers' tiles (specs layer-01..04, 08, palette.md), on the built release.

L1.1  every pixel of the area has a ground class            L1.2  no shading: a class is as bright on north and
L2.1  flat ground untouched by the relief                          south slopes (within 2%)
L2.2  every OSM wall with a drop >= 1.5 m drawn (>= 90%)      L3.1  water exactly where OSM has it (+- 1 px)
L4.1  100% of road, rail and tram centre lines inside the      L4.3  no drawn pixel of a tunnel
      drawn surface (brief 7)
L4.6  every bridge's ends are continuous with the ways that leave them: no gap and no step over 2 px in the drawn
      transport surface (colour and depth) within 6 m of each abutment
L8.1  every colour layer's depth equals layer 8's where it is the nearest (<= 1 cm)
L8.2  normals unit length and facing the camera                L8.3  every id exists in the scene
P-1   no colour literal in the layer code: every colour from the palette
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import shapely

from v2.checks.framework import Report
from v2.config import V2
from v2.layers.common import (BUILDING_CLASSES, CLASS, COLOUR_LAYERS, TILE, Scene, Tile, VIEW, lum, project, read_tile, unproject)
from v2.layers.render import GROUND_CLASSES, Renderer


def release_tiles(rel: Path, layer: str, z: int = 0):
    idx = json.loads((rel / "index.json").read_text())
    return idx["layers"][layer]["tiles"].get(str(z), {})


def load(rel: Path, layer: str, name: str, z: int = 0):
    d = release_tiles(rel, layer, z)
    if name not in d:
        return None
    return read_tile(rel / layer / str(z), name, d[name], z=z)


def pixel_of(px, py):
    """Zoom-0 map pixel -> (tile name, row, col)."""
    tx, ty = np.floor(px / TILE).astype(int), np.floor(py / TILE).astype(int)
    return tx, ty, (np.floor(py) - ty * TILE).astype(int), (np.floor(px) - tx * TILE).astype(int)


class TileCache:
    def __init__(self, rel, layer, maxn=48):
        self.rel, self.layer, self.c, self.maxn = rel, layer, {}, maxn

    def get(self, tx, ty):
        k = (tx, ty)
        if k not in self.c:
            if len(self.c) >= self.maxn:
                self.c.pop(next(iter(self.c)))
            self.c[k] = load(self.rel, self.layer, f"{tx}_{ty}")
        return self.c[k]

    def lookup(self, px, py, what):
        """Values of `what` at zoom-0 pixels (arrays); None where the layer has no tile."""
        tx, ty, r, c = pixel_of(np.asarray(px, float), np.asarray(py, float))
        out = [None] * len(tx)
        for k in set(zip(tx.tolist(), ty.tolist())):
            t = self.get(*k)
            m = np.flatnonzero((tx == k[0]) & (ty == k[1]))
            for i in m:
                out[i] = None if t is None or what not in t else t[what][r[i], c[i]]
        return out


def check_layers(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    sc = Scene(ctx.dep("scene"))
    R = Renderer(sc, ctx.dep("fetch_osm_ground") / "ground.json", ctx.dep("fetch_osm_transport") / "transport.json")
    rep = Report("layers")
    names = sorted(release_tiles(rel, "buffers"))
    # ------------------------------------------------------------------ L1.1, L1.2, L2.1, L8.1, L8.2, L8.3
    missing_cls, area_px = 0, 0
    miss_ex = []
    slope_lum = {}
    flat_bad, flat_n, flat_ex = 0, 0, []
    align_bad, align_n, align_ex = 0, 0, []
    nrm_bad, nrm_n = 0, 0
    id_bad, id_ex = 0, []
    nb, ne, nt = len(sc.buildings), len(sc.graph["edges"]), len(sc.trees["e"])
    seen_b = set()
    cosmin = math.sin(math.radians(P["ground_slope_min_deg"]))
    for name in names:
        tx, ty = (int(v) for v in name.split("_"))
        tile = Tile(tx, ty, apron=0)
        t = R.terrain(tile)
        g = load(rel, "ground", name)
        if g is not None:
            m = t["inarea"]
            area_px += int(m.sum())
            bad = m & ((g["k"] == 0) | ~np.isfinite(g["depth"]))
            missing_cls += int(bad.sum())
            if bad.any() and len(miss_ex) < 8:
                miss_ex.append({"tile": name, "pixels": int(bad.sum())})
            ok = np.isfinite(g["depth"]) & (g["k"] > 0)
            kk = g["k"]
            border = np.zeros(kk.shape, bool)
            border[:, :-1] |= kk[:, :-1] != kk[:, 1:]; border[:, 1:] |= kk[:, :-1] != kk[:, 1:]
            border[:-1, :] |= kk[:-1, :] != kk[1:, :]; border[1:, :] |= kk[:-1, :] != kk[1:, :]
            from scipy.ndimage import binary_dilation
            ok &= ~binary_dilation(border, iterations=2)       # the ink line and the coding's blur round it
            n = g["normal"]
            horiz = np.hypot(n[..., 0], n[..., 1])
            steep = ok & (horiz >= cosmin)
            north = steep & (n[..., 1] > 0.5 * horiz)
            south = steep & (n[..., 1] < -0.5 * horiz)
            L = lum(g["rgb"])
            for k in np.unique(g["k"][steep]):
                s = slope_lum.setdefault(int(k), [0.0, 0, 0.0, 0])
                mn, ms = north & (g["k"] == k), south & (g["k"] == k)
                s[0] += float(L[mn].sum()); s[1] += int(mn.sum()); s[2] += float(L[ms].sum()); s[3] += int(ms.sum())
        r = load(rel, "relief", name)
        if r is not None:
            n = r["normal"]
            flat = np.isfinite(r["depth"]) & (r["k"] == 1) & (n[..., 2] > math.cos(math.radians(P["relief_flat_deg"])))
            f = r["rgb"].astype(float) / 255
            badf = flat & (np.abs(f - 1).max(-1) > P["relief_flat_tol"] + 0.5 / 255)
            flat_n += int(flat.sum()); flat_bad += int(badf.sum())
            if badf.any() and len(flat_ex) < 8:
                flat_ex.append({"tile": name, "pixels": int(badf.sum()), "min_factor": round(float(f[badf].min()), 3)})
        b = load(rel, "buffers", name)
        if b is None:
            continue
        which = b["k"]
        for li, L in enumerate(COLOUR_LAYERS):
            lt = load(rel, L, name)
            if lt is None:
                continue
            m = (which == li + 1) & np.isfinite(lt["depth"])
            if L == "relief":
                m &= lt["k"] == 3
            dd = np.abs(lt["depth"][m] - b["depth"][m])
            align_n += int(m.sum())
            nbad = int((dd > P["align_cm"] / 100 + 1e-6).sum())
            align_bad += nbad
            if nbad and len(align_ex) < 8:
                align_ex.append({"tile": name, "layer": L, "pixels": nbad, "max_cm": round(float(dd.max()) * 100, 2)})
        okb = np.isfinite(b["depth"])
        nn = b["normal"][okb]
        nrm_n += int(okb.sum())
        facing = nn @ (-VIEW)
        nrm_bad += int(((np.abs(np.linalg.norm(nn, axis=1) - 1) > P["normal_unit_tol"]) | (facing < -0.02)).sum())
        ids = b["ids"][okb]
        cls, obj = ids & 255, ids >> 8
        bad_ids = ((np.isin(cls, [CLASS[c] for c in BUILDING_CLASSES]) & (obj >= nb)) |
                   (np.isin(cls, [CLASS["road"], CLASS["rail"], CLASS["tram"], CLASS["path"], CLASS["steps"], CLASS["deck"],
                                  CLASS["portal"]]) & ((obj < 1) | (obj > ne))) |
                   ((cls == CLASS["tree"]) & (obj >= nt)))
        id_bad += int(bad_ids.sum())
        if bad_ids.any() and len(id_ex) < 8:
            id_ex.append({"tile": name, "ids": [int(x) for x in ids[bad_ids][:3]]})
        seen_b.update(obj[np.isin(cls, [CLASS[c] for c in BUILDING_CLASSES])].tolist())
    rep.at_most("L1.1", "ground pixels of the area without a class (of %d)" % area_px, missing_cls, 0, miss_ex)
    worst, wex = 0.0, []
    for k, (sn, nn_, ss, ns) in sorted(slope_lum.items()):
        if nn_ < 2000 or ns < 2000:
            continue
        d = abs(sn / nn_ - ss / ns) / max(ss / ns, 1e-9)
        wex.append({"class": GROUND_CLASSES[k], "north": round(sn / nn_, 2), "south": round(ss / ns, 2), "diff": round(d, 4)})
        worst = max(worst, d)
    rep.at_most("L1.2", "no shading: worst relative luminance difference of a ground class, north vs south slopes",
                round(worst, 4), P["ground_slope_lum_max"], sorted(wex, key=lambda e: -e["diff"]))
    rep.at_most("L2.1", f"flat ground changed by the relief (of {flat_n} flat pixels)", flat_bad, 0, flat_ex)
    rep.at_most("L8.1", f"pixels where a layer's depth differs from layer 8's by > {P['align_cm']} cm (of {align_n})", align_bad, 0, align_ex)
    rep.at_most("L8.2", f"normals not unit or facing away from the camera (of {nrm_n})", nrm_bad, 0)
    rep.at_most("L8.3", "ids not in the scene", id_bad, 0, id_ex)
    rep.info("L8.3b", "buildings with at least one pixel in layer 8", f"{len(seen_b)} of {nb}")
    # ------------------------------------------------------------------ L2.2 walls
    _l22(rep, R, rel, P)
    # ------------------------------------------------------------------ L3.1 water
    _l31(rep, R, rel, P)
    # ------------------------------------------------------------------ L4.1, L4.3
    _l41(rep, R, rel, P)
    # ------------------------------------------------------------------ L4.6 bridge ends
    _l46(rep, R, rel, P)
    # ------------------------------------------------------------------ P-1 palette
    _palette(rep)
    return rep.result()


def _l22(rep, R, rel, P):
    relief = TileCache(rel, "relief")
    sc = R.scene
    bad, total, ex = 0, 0, []
    for wi, w in enumerate(sc.walls):
        if (w.get("drop_m") or 0) < P["wall_min_drop_m"]:
            continue
        en = np.array(w["en"], float)
        seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
        if seg[-1] < 1:
            continue
        s = np.arange(0.25, seg[-1], 0.5)
        e, n = np.interp(s, seg, en[:, 0]), np.interp(s, seg, en[:, 1])
        inside = shapely.contains_xy(sc.polygon, e, n)
        if inside.sum() < 4:
            continue
        e, n = e[inside], n[inside]
        top = np.array([np.nan if v is None else v for v in w["top_m"]], float)
        L = seg[-1]
        st = np.minimum(np.arange(len(top)) * 5.0 * L / max(int(L), 1), L)
        ok = np.isfinite(top)
        if ok.sum() < 2:
            continue
        from scipy.ndimage import median_filter, uniform_filter1d
        sd = np.r_[np.arange(0, L, 0.5), L]
        td = np.interp(sd, st, np.where(ok, top, np.nanmedian(top)))
        if len(top) >= 3:
            td = uniform_filter1d(median_filter(td, 11, mode="nearest"), 11, mode="nearest")
        z = np.interp(s[inside], sd, td)
        g = R.hf.sample(e, n)
        z = np.where(np.isfinite(g), np.maximum(z, g), z)            # as drawn: never under the terrain at the line
        px, py, d = project(e, n, z)
        drawn = np.zeros(len(e), bool)
        seen = np.zeros(len(e), bool)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                ks = relief.lookup(px + dx, py + dy, "k")
                ds = relief.lookup(px + dx, py + dy, "depth")
                for i in range(len(e)):
                    if ks[i] is None:
                        continue
                    if ks[i] == 3:
                        drawn[i] = True
                    if dx == 0 and dy == 0 and ds[i] is not None and ds[i] > d[i] - 1.0:
                        seen[i] = True          # its own pixel shows nothing nearer than the wall's top
        vis = seen | drawn
        if vis.sum() < 4:
            continue
        share = float((drawn & vis).sum() / vis.sum())
        total += 1
        if share < P["wall_drawn_share"]:
            bad += 1
            if len(ex) < 8:
                ex.append({"wall": w["osm"], "kind": w["kind"], "drawn_share": round(share, 3), "visible_samples": int(vis.sum())})
    rep.at_most(f"L2.2", f"walls (drop >= {P['wall_min_drop_m']} m, in the area, in view) drawn along < "
                f"{P['wall_drawn_share']:.0%} of their visible length (of {total})", bad, 0, ex)


def _l31(rep, R, rel, P):
    water = release_tiles(rel, "water")
    tol = P["water_px_tol"] * 0.125 * 2.5          # 1 px of screen is up to ~0.3 m of plan on the ground
    polys = R.water_polys
    if not polys:
        rep.info("L3.1", "water areas", 0)
        return
    from shapely.ops import unary_union
    W = unary_union(polys).intersection(R.scene.polygon)
    inner, outer = W.buffer(-tol), W.buffer(tol)
    bad_in, bad_out, n = 0, 0, 0
    names = set(water) | {nm for nm in release_tiles(rel, "buffers")}
    for name in sorted(names):
        tx, ty = (int(v) for v in name.split("_"))
        t = R.terrain(Tile(tx, ty, apron=0))
        m = t["inarea"]
        if not m.any():
            continue
        e, nn = t["e"][m], t["n"][m]
        must = shapely.contains_xy(inner, e, nn)
        may = shapely.contains_xy(outer, e, nn)
        if not may.any():
            continue
        wt = load(rel, "water", name)
        isw = np.zeros(m.shape, bool) if wt is None else (wt["k"] > 0) & np.isfinite(wt["depth"])
        isw = isw[m]
        bad_in += int((must & ~isw).sum())
        bad_out += int((isw & ~may).sum())
        n += int(must.sum())
    rep.at_most("L3.1", f"OSM water pixels not drawn as water, and water pixels outside OSM water (+- {P['water_px_tol']} px; "
                f"{n} water pixels)", bad_in + bad_out, 0, [{"missing": bad_in, "outside": bad_out}])


def abutment_samples(sc, span, step):
    """Centre-line samples next to every bridge end (an abutment: a node joining a bridge and a ground way): the
    bridge's last `span` metres and the first `span` metres of every drawn way leaving the node (not tunnels, steps
    or lifts), from the node outwards. Rows: (edge, node, e, n, profile z, run, distance from the node, grazing),
    where grazing is the cosine between the way's top and the direction to the camera (near 0: seen edge-on; below
    0: a steep ramp turned away from the camera, its top not seen at all)."""
    from v2.layers.common import VIEW
    edges = sc.graph["edges"]
    ends = {int(e[k]) for e in edges if e["structure"] == "bridge" for k in ("a", "b")}
    by_node = {}
    for i, e in enumerate(edges):
        for k in ("a", "b"):
            if int(e[k]) in ends:
                by_node.setdefault(int(e[k]), []).append((i, k))
    out, run = [], 0
    for nid, inc in sorted(by_node.items()):
        if "ground" not in {edges[i]["structure"] for i, _ in inc}:
            continue                                   # bridges joining bridges: no abutment
        for i, k in inc:
            e = edges[i]
            if e["structure"] in ("tunnel", "indoor", "elevator") or e["mode"] in ("steps", "elevator"):
                continue
            en, s0, z0 = np.array(e["en"], float), np.array(e["s"], float), np.array(e["z"], float)
            if len(en) < 2:
                continue
            L = s0[-1]
            dist = np.arange(0, min(span, L) + 1e-9, step)
            ss = dist if k == "a" else L - dist
            E, N, Z = np.interp(ss, s0, en[:, 0]), np.interp(ss, s0, en[:, 1]), np.interp(ss, s0, z0)
            h = 0.5
            t = np.column_stack([np.interp(ss + h, s0, en[:, 0]) - np.interp(ss - h, s0, en[:, 0]),
                                 np.interp(ss + h, s0, en[:, 1]) - np.interp(ss - h, s0, en[:, 1]),
                                 np.interp(ss + h, s0, z0) - np.interp(ss - h, s0, z0)])
            left = np.column_stack([-t[:, 1], t[:, 0], np.zeros(len(t))])
            nrm = np.cross(t, left)
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
            nrm *= np.where(nrm[:, 2] < 0, -1.0, 1.0)[:, None]          # the way's top
            graze = -(nrm @ VIEW)                # how squarely its top faces the camera (<= 0: turned away)
            out += [(i, nid, E[j], N[j], Z[j], run, dist[j], graze[j]) for j in range(len(ss))]
            run += 1
    return np.array(out, float).reshape(-1, 8)


def abutment_continuity(sc, get, terrain, span, step, max_px, graze_min=0.15, detail=False, ground_depth=None,
                        skip_ways=()):
    """L4.6 on transport tiles (`get(tx, ty)` -> dict with depth and ids, or None; `terrain(e, n)` the drawn terrain).

    The drawn way at each sample is found where it can be: at its profile (a deck) or on the terrain (a drape); a
    candidate matches when the transport layer draws a surface there within max_px pixels of height of it. A sample
    fails as a *gap* when neither is drawn (and no nearer transport surface covers both), and as a *step* when the
    drawn height changes faster than both the profile and the terrain by more than max_px pixels and stays changed
    (medians of 4 samples, 1 m, either side), or the ways meeting at the node are drawn at heights apart by more. Samples where the way's top is seen edge-on or not at all (cos < graze_min)
    are not judged. Heights for the steps are read at the sample's own pixel only (a neighbouring pixel of a sloping
    surface shows another point of it); the neighbours count for the gap test, as L4.1's edge rule."""
    from v2.config.camera import camera
    mpp = camera()["mpp"]
    k = math.sqrt(3) / 2 / mpp                           # screen pixels per metre of height
    rows = abutment_samples(sc, span, step)
    if len(rows):
        rows = rows[shapely.contains_xy(sc.polygon.buffer(-1.0), rows[:, 2], rows[:, 3])]
    n_skipped = 0
    if len(rows) and skip_ways:
        way = np.array([int(sc.graph["edges"][int(i)]["way"]) for i in rows[:, 0]])
        keep = ~np.isin(way, list(skip_ways))
        n_skipped = int((~keep).sum())
        rows = rows[keep]
    nrow = len(rows)
    allowed = {}
    for i, e in enumerate(sc.graph["edges"]):
        for kk in ("a", "b"):
            allowed.setdefault(int(e[kk]), set()).add(i)
    zc = np.stack([rows[:, 4], terrain(rows[:, 2], rows[:, 3])], 1)        # candidates: profile, terrain
    drawn = np.full(nrow, np.nan)
    seen_any = np.zeros(nrow, bool)
    state = np.zeros(nrow, np.int8)                      # 0 gap, 1 drawn, 2 hidden, 3 edge-on
    best = np.full(nrow, np.inf)
    covered = np.ones(nrow, bool)
    def look(px, py):
        tx, ty, r, cc = pixel_of(px, py)
        dd = np.full(len(px), np.inf); iv = np.zeros(len(px), np.int64); front = np.full(len(px), np.inf)
        for key in set(zip(tx.tolist(), ty.tolist())):
            m = np.flatnonzero((tx == key[0]) & (ty == key[1]))
            t = get(*key)
            if t is not None:
                dd[m] = t["depth"][r[m], cc[m]]
                iv[m] = t["ids"][r[m], cc[m]]
            g = ground_depth(*key) if ground_depth is not None else None
            if g is not None:
                front[m] = g[r[m], cc[m]]
        return dd, iv, front

    edge_px = np.zeros(nrow, bool)
    for c in range(2):
        z = np.where(np.isfinite(zc[:, c]), zc[:, c], rows[:, 4])
        px, py, d = project(rows[:, 2], rows[:, 3], z)
        # the pixel itself, then its neighbours (rounding at a surface's edge, as L4.1 accepts)
        for dx, dy in [(0, 0)] + [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]:
            dd, iv, front = look(px + dx, py + dy)
            ok = np.isfinite(dd) & (iv != 0)
            # the way itself, or a way meeting it at the node (they share the node's surface)
            pe = (iv >> 8) - 1
            own = ok & np.array([int(p) in allowed[int(n)] for p, n in zip(pe, rows[:, 1])], bool)
            _, _, zd = unproject(px + dx, py + dy, np.where(ok, dd, d))
            off = np.abs(zd - z) * k
            got = ok & (off <= max_px)
            if dx or dy:
                edge_px |= got & ~seen_any
            seen_any |= got                                 # a transport surface at the way's level is drawn here
            hit = own & (off <= max_px) & (off < best)      # ... and it is the way's own (or its junction's)
            best[hit] = off[hit]
            drawn[hit] = zd[hit]
            if not (dx or dy):
                # covered: a transport surface in front of it (a deck over it, a way it joins drawn over it at a
                # junction), or the terrain (a hill, a wall's top)
                covered &= (ok & (dd < d - 0.1)) | (front < d - 1.0)
    state[seen_any] = 1
    state[(state == 0) & covered] = 2
    state[(state == 0) & (rows[:, 7] < graze_min)] = 3
    # steps: along each run (from the node outwards) the drawn height may rise or fall as fast as the way's profile or
    # the terrain it is draped on (it follows one or the other, and passes from one to the other where they meet);
    # a step is a change beyond both, that stays: medians of the next `w` samples against the previous `w` (one
    # sample read off a neighbouring pixel is not a step). Between the runs meeting at a node: the medians of their
    # first `w` samples' offsets from the node's height.
    w = 4
    terr = zc[:, 1]
    step_bad = np.zeros(nrow, bool)
    worst = 0.0
    first = {}
    for run in np.unique(rows[:, 5]):
        m = np.flatnonzero(rows[:, 5] == run)
        m = m[np.argsort(rows[m, 6])]
        m = m[np.isfinite(drawn[m])]
        if not len(m):
            continue
        dz, pz, tz = drawn[m], rows[m, 4], np.where(np.isfinite(terr[m]), terr[m], rows[m, 4])
        first.setdefault(int(rows[m[0], 1]), []).append(float(np.median(dz[:w] - pz[:w])))
        for j in range(1, len(m)):
            a, b = slice(max(0, j - w), j), slice(j, j + w)
            ch = abs(float(np.median(dz[b]) - np.median(dz[a])))
            allow = max(abs(float(np.median(pz[b]) - np.median(pz[a]))), abs(float(np.median(tz[b]) - np.median(tz[a]))))
            jump = max(ch - allow, 0.0) * k
            worst = max(worst, jump)
            if jump > max_px:
                step_bad[m[j]] = True
    for nid, meds in first.items():
        if len(meds) >= 2:
            spread = (max(meds) - min(meds)) * k
            worst = max(worst, spread)
            if spread > max_px:
                step_bad[(rows[:, 1] == nid) & (rows[:, 6] == 0)] = True
    bad = (state == 0) | step_bad
    ex = []
    for nid in np.unique(rows[bad, 1]):
        m = (rows[:, 1] == nid) & bad
        j = np.flatnonzero(m)[0]
        ex.append({"node": int(nid), "edge": sc.graph["edges"][int(rows[j, 0])]["id"], "mode": sc.graph["edges"][int(rows[j, 0])]["mode"], "gaps": int((m & (state == 0)).sum()),
                   "steps": int((m & step_bad).sum()), "e": round(float(rows[j, 2]), 1), "n": round(float(rows[j, 3]), 1)})
    ex.sort(key=lambda x: -(x["gaps"] + x["steps"]))
    if detail:
        return rows, state, step_bad, drawn
    return {"samples": int((state != 2).sum() - (state == 3).sum()), "gaps": int((state == 0).sum()),
            "edge_px": int(edge_px.sum()), "excepted": n_skipped,
            "steps": int(step_bad.sum()), "hidden": int((state == 2).sum()), "edge_on": int((state == 3).sum()),
            "worst_step_px": round(worst, 2), "nodes": len(np.unique(rows[:, 1])), "bad_nodes": len(ex), "examples": ex}


def _l46(rep, R, rel, P):
    tr = TileCache(rel, "transport")
    gr = TileCache(rel, "ground")

    def ground_depth(tx, ty):
        t = gr.get(tx, ty)
        return None if t is None else t["depth"]
    from v2.checks.data_checks import excepted
    skip = excepted("L4.6")
    res = abutment_continuity(R.scene, tr.get, R.hf.sample, P["abutment_span_m"], P["abutment_step_m"],
                              P["abutment_step_px"], ground_depth=ground_depth, skip_ways=set(skip))
    rep.at_most("L4.6", f"samples within {P['abutment_span_m']} m of the {res['nodes']} bridge ends in the area where the "
                f"drawn way has a gap, or a step over {P['abutment_step_px']} px (of {res['samples']}; {res['hidden']} under "
                f"another deck, {res['edge_on']} seen edge-on; largest step {res['worst_step_px']} px)",
                res["gaps"] + res["steps"], 0, res["examples"])
    rep.info("L4.6b", "samples of ways excepted from L4.6 (v2/data/exceptions.json)",
             {"samples": res["excepted"], "ways": sorted(f"way/{w}" for w in skip)})


def _l41(rep, R, rel, P):
    sc = R.scene
    tr = TileCache(rel, "transport")
    gr = TileCache(rel, "ground")
    step = P["centreline_step_m"]
    n_in, n_hidden, bad, ex, n_edge = 0, 0, 0, [], 0
    tunnel_px = 0
    for i, e in enumerate(sc.graph["edges"]):
        if e["mode"] not in ("road", "rail", "tram") or e["structure"] in ("tunnel", "indoor"):
            continue
        en = np.array(e["en"], float)
        s0 = np.array(e["s"], float)
        z0 = np.array(e["z"], float)
        if len(en) < 2 or s0[-1] < step:
            continue
        s = np.arange(step / 2, s0[-1], step)
        ee, nn = np.interp(s, s0, en[:, 0]), np.interp(s, s0, en[:, 1])
        ok = shapely.contains_xy(sc.polygon.buffer(-0.5), ee, nn)
        if not ok.any():
            continue
        ee, nn, s = ee[ok], nn[ok], s[ok]
        # ground ways are drawn on the terrain, decks at their profile
        from v2.layers.geometry import deck_at
        deck = deck_at(R.dense_edges[i], R.deck_masks[i], s)
        z = np.where(deck, np.interp(s, s0, z0), R.hf.sample(ee, nn))
        px, py, d = project(ee, nn, z)
        tdep = tr.lookup(px, py, "depth")
        near = [tr.lookup(px + dx, py + dy, "depth") for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        tx_, ty_ = (px // TILE).astype(int), (py // TILE).astype(int)
        gdep = np.full(len(px), np.inf)
        for key in set(zip(tx_.tolist(), ty_.tolist())):
            mm = (tx_ == key[0]) & (ty_ == key[1])
            T = R.terrain(Tile(key[0], key[1], apron=0))          # the terrain seen (also outside the area)
            gdep[mm] = T["depth"][(py[mm] - key[1] * TILE).astype(int), (px[mm] - key[0] * TILE).astype(int)]
        for k in range(len(ee)):
            drawn = tdep[k] is not None and np.isfinite(tdep[k])
            if not drawn and any(v[k] is not None and np.isfinite(v[k]) and abs(v[k] - d[k]) < 2.0 for v in near):
                n_edge += 1                       # on the surface's edge: the pixel next to it is drawn
                drawn = True
            if not drawn:
                # a drape is drawn where its terrain is seen: behind a hill it is not in view at all
                g = gdep[k]
                if not deck[k] and np.isfinite(g) and g < d[k] - 0.5:
                    n_hidden += 1
                    continue
                if deck[k] and tdep[k] is not None and np.isfinite(tdep[k]) and tdep[k] < d[k] - 0.5:
                    n_hidden += 1
                    continue
            n_in += 1
            if not drawn:
                bad += 1
                if len(ex) < 8:
                    ex.append({"edge": e["id"], "mode": e["mode"], "e": round(float(ee[k]), 2), "n": round(float(nn[k]), 2)})
    rep.at_least("L4.1", f"road, rail and tram centre-line samples (every {step} m) inside the drawn surface "
                 f"(of {n_in}; {n_hidden} behind the terrain; {n_edge} within 1 px of the surface's edge)", round(1 - bad / max(n_in, 1), 6), P["centreline_share"], ex)
    tun = {i for i, e in enumerate(sc.graph["edges"]) if e["structure"] == "tunnel"}
    for name in release_tiles(rel, "transport"):
        t = load(rel, "transport", name)
        ids = t["ids"]
        cls = ids & 255
        obj = (ids >> 8).astype(np.int64) - 1
        m = (cls != CLASS["portal"]) & (obj >= 0)
        if m.any():
            tunnel_px += int(np.isin(obj[m], list(tun)).sum())
    rep.at_most("L4.3", "drawn pixels of tunnel ways (portals are drawn, tunnels are not)", tunnel_px, 0)


RGB_LITERAL = re.compile(r"\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)")


def _palette(rep):
    bad = []
    for p in sorted((V2 / "layers").glob("*.py")):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            code = line.split("#")[0]
            for m in RGB_LITERAL.finditer(code):
                v = [int(x) for x in m.groups()]
                if max(v) > 1:
                    bad.append(f"{p.name}:{i}: {m.group(0)}")
    rep.at_most("P-1", "colour literals in the layer code (every colour comes from palette.json)", len(bad), 0, bad)
