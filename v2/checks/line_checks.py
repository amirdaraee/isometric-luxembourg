"""Brief 6, straight lines and windows: the line score (L5.2, PLAN_V2 section 8) on the built layer 5 (any method).

The 3D model's lines are projected into the map and sampled every 0.25 m: every crease and outline of the ACT LoD2
buildings (edges where two surfaces of different planes meet, or a surface ends), and the top and bottom edge of
every window of the facade layout (the window rows; an arched window of a place of worship has no straight top, so
its sill alone is sampled). At each sample seen in layer 5 (its building is what layer 5
shows there, at its depth within 0.3 m, at the sample or one pixel either side), the drawn line is looked for across the projected line, along
the line's screen normal within 3 px either side: the luminance steps of the layer's colour of at least
`line_min_step` (out of 255). The sample is on its line when the step nearest the projected line lies within
`line_score_px` of it (a window frame or a cornice beside a line is a second line, not a displaced one). The score is the share of seen samples on their line; the gate is >= `line_score_share` (95%) for building
edges and for window rows, each.

The measure does not know how the layer was made, so it scores A's code lines, B's materials and C's paintings alike.
"""
from __future__ import annotations

import math

import numpy as np

from v2.checks.framework import Report
from v2.checks.layer_checks import TileCache
from v2.layers.common import Scene, TILE, lum, project
from v2.layers import geometry as G


def feature_edges(M, min_len=0.5, crease_deg=20.0):
    """3D segments (a, b) of a mesh where a surface ends, or two surfaces meet at a crease (of different objects or
    classes, or turning by crease_deg or more: the facets of a round tower are one smooth wall, as layer 5 draws it),
    and the object (building) each belongs to."""
    from v2.layers.geometry import tri_normals
    V, T, grp = M["V"], M["T"], M["group"]
    nrm, _ = tri_normals(V, T)
    cls = M["cls"]
    cosc = np.cos(np.radians(crease_deg))
    q = np.round(V * 100).astype(np.int64)
    seen = {}
    for t in range(len(T)):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            ka, kb = tuple(q[T[t, i]]), tuple(q[T[t, j]])
            k = (ka, kb) if ka < kb else (kb, ka)
            seen.setdefault(k, []).append(t)
    A, B, O = [], [], []
    obj = M["obj"]
    for (ka, kb), ts in seen.items():
        groups = {int(grp[t]) for t in ts}
        crease = len(ts) == 1
        if not crease and len(groups) > 1:
            t0, t1 = ts[0], ts[1]
            crease = (obj[t0] != obj[t1]) or (cls[t0] != cls[t1]) or abs(float(nrm[t0] @ nrm[t1])) <= cosc
        if crease:
            a, b = np.array(ka) / 100.0, np.array(kb) / 100.0
            if np.linalg.norm(b - a) >= min_len:
                A.append(a); B.append(b); O.append(int(obj[ts[0]]))
    return np.array(A, float).reshape(-1, 3), np.array(B, float).reshape(-1, 3), np.array(O, np.int64)


def window_rows(scene, offset=0.05):
    """The top and bottom edge of every window of the facade layout, as 3D segments; of an arched window (a wall
    of a place of worship) the bottom edge."""
    from v2.data.scene.facades import window_world
    bidx = {b["id"]: i for i, b in enumerate(scene.buildings)}
    A, B, O = [], [], []
    for w in scene.facades["walls"]:
        nx, ny = w["normal"]
        off = np.array([nx * offset, ny * offset, 0.0])
        bi = bidx.get(w["building"], -1)
        for r in w["windows"]:
            c = np.array(window_world(w, [float(x) for x in r[:4]])) + off
            if w.get("worship"):
                A += [c[0]]; B += [c[1]]; O += [bi]
            else:
                A += [c[0], c[3]]; B += [c[1], c[2]]; O += [bi, bi]
    return np.array(A, float).reshape(-1, 3), np.array(B, float).reshape(-1, 3), np.array(O, np.int64)


def samples(A, B, O=None, step=0.25, end_skip=0.25):
    """Points every `step` m along each segment (not within end_skip of its ends), their directions and objects."""
    L = np.linalg.norm(B - A, axis=1)
    O = np.full(len(A), -1, np.int64) if O is None else O
    pts, dirs, objs = [], [], []
    for a, b, l, o in zip(A, B, L, O):
        if l <= 2 * end_skip:
            continue
        s = np.arange(end_skip, l - end_skip + 1e-9, step)
        d = (b - a) / l
        pts.append(a + s[:, None] * d)
        dirs.append(np.repeat(d[None], len(s), 0))
        objs.append(np.full(len(s), o))
    if not pts:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(0, np.int64)
    return np.concatenate(pts), np.concatenate(dirs), np.concatenate(objs)


def score(cache, P, D, max_px, min_step, reach=3, obj=None):
    """(seen, on line) for 3D samples P with 3D directions D (and their objects), against a tile cache of one colour
    layer. A sample is seen where the layer shows its object (if given) at its depth (within 0.3 m)."""
    px, py, d = project(P[:, 0], P[:, 1], P[:, 2])
    qx, qy, _ = project(P[:, 0] + D[:, 0], P[:, 1] + D[:, 1], P[:, 2] + D[:, 2])
    sx, sy = qx - px, qy - py
    ln = np.hypot(sx, sy)
    ok = ln > 1e-6                                       # a line seen end-on has no direction on screen
    nx, ny = np.where(ok, -sy / np.maximum(ln, 1e-9), 0), np.where(ok, sx / np.maximum(ln, 1e-9), 0)
    tx, ty = np.floor(px / TILE).astype(int), np.floor(py / TILE).astype(int)
    seen = np.zeros(len(P), bool)
    on = np.zeros(len(P), bool)
    for key in set(zip(tx.tolist(), ty.tolist())):
        m = np.flatnonzero((tx == key[0]) & (ty == key[1]) & ok)
        if not len(m):
            continue
        # a window of tiles round this one (the normal can reach 3 px into the next tile)
        pieces = {}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                pieces[(dx, dy)] = cache.get(key[0] + dx, key[1] + dy)
        if pieces[(0, 0)] is None:
            continue

        def at(xx, yy, what):
            ix, iy = np.floor(xx).astype(int), np.floor(yy).astype(int)
            out = np.full(len(xx), np.nan)
            ox, oy = np.floor_divide(ix, TILE) - key[0], np.floor_divide(iy, TILE) - key[1]
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    t = pieces[(dx, dy)]
                    mm = (ox == dx) & (oy == dy)
                    if t is None or not mm.any():
                        continue
                    a = t[what] if what != "lum" else t.setdefault("lum", lum(t["rgb"]))
                    out[mm] = a[iy[mm] - (key[1] + dy) * TILE, ix[mm] - (key[0] + dx) * TILE]
            return out
        X, Y, dd = px[m], py[m], d[m]
        NX, NY = nx[m], ny[m]
        near = np.full(len(m), np.inf)
        for k in (-1, 0, 1):
            dep = at(X + k * NX, Y + k * NY, "depth")
            dz = np.abs(dep - dd)
            if obj is not None and "ids" in pieces[(0, 0)]:
                ob = at(X + k * NX, Y + k * NY, "ids")
                dz = np.where(np.isfinite(ob) & ((ob.astype(np.int64) >> 8) == obj[m]), dz, np.inf)
            near = np.fmin(near, dz)
        vis = near < 0.3
        offs = np.arange(-reach, reach + 1)
        L = np.stack([at(X + k * NX, Y + k * NY, "lum") for k in offs], 1)
        steps = np.abs(np.diff(L, axis=1))                  # between offsets k and k+1: at k + 0.5
        steps = np.where(np.isfinite(steps), steps, 0)
        # the drawn line nearest the model's: the step >= min_step closest to the projected line (a frame or a band
        # beside a line is a second line, not a displaced one)
        mids = offs[:-1] + 0.5
        dist = np.where(steps >= min_step, np.abs(mids)[None, :], np.inf)
        near_d = dist.min(1)
        seen[m] = vis
        on[m] = vis & (near_d <= max_px + 0.5)
    return seen, on


def check_lines(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    sc = Scene(ctx.dep("scene"))
    rep = Report("lines")
    cache = TileCache(rel, "buildings", maxn=64)
    bm = G.buildings_mesh(sc)
    for name, (A, B, O) in (("edges", feature_edges(bm)), ("windows", window_rows(sc))):
        Ps, Ds, Os = samples(A, B, O)
        seen, on = score(cache, Ps, Ds, P["line_score_px"], P["line_min_step"], obj=Os)
        n = int(seen.sum())
        share = float(on.sum() / max(n, 1))
        bad = np.flatnonzero(seen & ~on)
        ex = [{"e": round(float(Ps[i, 0]), 2), "n": round(float(Ps[i, 1]), 2), "z": round(float(Ps[i, 2]), 2)}
              for i in bad[:: max(len(bad) // 8, 1)][:8]]
        what = "building edges (creases and outlines of the 3D model)" if name == "edges" else "window rows (top and bottom of every window)"
        rep.at_least(f"L5.2-{name}", f"line score, {what}: share of {n} seen samples (every 0.25 m, of {len(Ps)}) whose "
                     f"drawn line is within {P['line_score_px']} px of the model's", round(share, 4), P["line_score_share"], ex)
    worship_pixels(rep, rel, sc)
    return rep.result()


def worship_pixels(rep, rel, sc):
    """L5.7 (the owner's decision of 13 Nov 2026): what layer 5 draws on the places of worship. A building that is
    a church all over has no shutter and no shop front pixel; its window glass is the church's (dark leaded glass
    with stained panes), not the house window's."""
    import json
    from v2.layers.common import CLASS, pal, read_tile
    wor = sc.facades.get("worship", {})
    bidx = {b["id"]: i for i, b in enumerate(sc.buildings)}
    church_walls, all_walls = {}, {}
    for w in sc.facades["walls"]:
        all_walls[w["building"]] = all_walls.get(w["building"], 0) + 1
        church_walls[w["building"]] = church_walls.get(w["building"], 0) + bool(w.get("worship"))
    whole = sorted(bidx[b] for b in wor if b in bidx and church_walls.get(b, 0) == all_walls.get(b, -1))
    tiles = json.loads((rel / "index.json").read_text())["layers"]["buildings"]["tiles"]["0"]
    n = {"shutter": 0, "shopfront": 0, "window": 0, "house_glass": 0, "all": 0}
    house = np.round(pal("buildings", "window")).astype(int)
    for name, dmin in tiles.items():
        t = read_tile(rel / "buildings" / "0", name, dmin)
        on = np.isin(t["ids"] >> 8, whole) & np.isfinite(t["depth"])
        if not on.any():
            continue
        cls = (t["ids"] & 255)[on]
        n["all"] += int(on.sum())
        n["shutter"] += int((cls == CLASS["shutter"]).sum())
        n["shopfront"] += int((cls == CLASS["shopfront"]).sum())
        glass = cls == CLASS["window"]
        n["window"] += int(glass.sum())
        # a house window's glass is the palette's window colour in one tone per window (0.86 to 1.16 of it)
        rgb = t["rgb"][on][glass].astype(float)
        k = rgb.sum(1) / max(float(house.sum()), 1.0)
        n["house_glass"] += int(((k > 0.84) & (k < 1.18) & (np.abs(rgb - house * k[:, None]).max(1) <= 2.5)).sum())
    rep.info("L5.7", "places of worship in the scene; of them churches all over (every wall); their pixels in layer 5; "
             "their window glass pixels", [len(wor), len(whole), n["all"], n["window"]])
    rep.at_most("L5.7-shutters", "shutter pixels on buildings that are a church all over", n["shutter"], 0)
    rep.at_most("L5.7-shopfronts", "shop front pixels on buildings that are a church all over", n["shopfront"], 0)
    rep.at_most("L5.7-house-windows", "window glass pixels in a house window's colour on buildings that are a church all "
                "over", n["house_glass"], 0)
