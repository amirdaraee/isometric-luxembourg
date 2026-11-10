"""Scene: trees from the ACT LiDAR 2024 tree survey (spec: v2/docs/specs/scene.md, "Trees").

Rules, in order:
  1. keep survey points inside the area with a height from min_height_m to max_height_m (taller ones are survey
     spikes: cranes, masts, bridge parts; no tree in the city is near 50 m);
  2. drop a tree whose crown centre is inside a building footprint (the survey finds roof gardens and roof clutter
     too, but a crown centred on a roof is drawn by the building layer, not as a tree) or inside water;
  3. crown radius: the survey's (crown_scale * crown_mean / 2; the POC found measured crowns read too big) widened to
     the tree's shape by species and age (shape_radius: the LiDAR crowns are a few metres wide on trees 15-25 m
     tall, which draws poplars; the owner asked for rounder crowns at the measured height, 9 Nov 2026); thin it so
     that at most max_overlap_share of the crown disc lies over buildings or water: r is reduced until it does;
  4. the base height is the terrain at the point (LiDAR ground), the top base + height (never changed).
trees.npz: e, n, base_z, height, crown_r (drawn: shaped, then thinned), crown_r_shape (before thinning),
crown_r_measured, type, uuid; plus counts of what was dropped, widened and thinned.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely import STRtree
from shapely.ops import unary_union

from v2.data.geo import area_polygon
from v2.data.scene.buildings import footprints, load
from v2.data.scene.grid import Grid
from v2.data.scene.water import load_polygons


def overlap_share(e, n, r, blockers, tree=None):
    """Share of each crown disc (centre e, n; radius r) lying over the blocker polygons (vectorised)."""
    e, n, r = np.asarray(e, float), np.asarray(n, float), np.asarray(r, float)
    out = np.zeros(len(e))
    if not len(e) or not len(blockers):
        return out
    tree = tree or STRtree(blockers)
    discs = shapely.buffer(shapely.points(e, n), np.maximum(r, 1e-3), quad_segs=8)
    di, bi = tree.query(discs, predicate="intersects")
    if len(di):
        a = shapely.area(shapely.intersection(discs[di], np.asarray(blockers, dtype=object)[bi]))
        out = np.bincount(di, weights=a, minlength=len(e)) / shapely.area(discs)
    return np.where(r > 0, out, 0.0)


def shape_radius(h, r_survey, typ, e, n, p, names):
    """The drawn crown radius by species and age: width = height x a ratio that grows from young to mature trees
    (params trees.crown_shape; height is the age proxy), capped per type, and by the room the tree has (at most
    neighbour_factor x the distance to its nearest neighbour, so a stand stays a stand of crowns); never under the
    survey's radius. Returns (radius, allometric radius before the neighbour cap)."""
    from scipy.spatial import cKDTree
    c = p["crown_shape"]
    h = np.asarray(h, float)
    age = np.clip((h - c["young_h_m"]) / max(c["mature_h_m"] - c["young_h_m"], 1e-6), 0, 1)
    allo = np.zeros(len(h))
    for t, name in enumerate(names):
        k = c["by_type"].get(name, c["by_type"]["other"])
        m = np.asarray(typ) == t
        allo[m] = np.minimum(h[m] * (k["young"] + (k["mature"] - k["young"]) * age[m]), k["max_width_m"]) / 2
    room = np.full(len(h), np.inf)
    if len(h) > 1:
        d, _ = cKDTree(np.column_stack([e, n])).query(np.column_stack([e, n]), k=2)
        room = d[:, 1] * c["neighbour_factor"]
    return np.maximum(r_survey, np.minimum(allo, room)), allo


def build(ctx):
    p = ctx.params["trees"]
    T = np.load(ctx.dep("fetch_trees") / "trees.npz")
    poly = area_polygon(ctx.area)
    e, n = T["e"], T["n"]
    x0, y0, x1, y1 = poly.bounds
    pre = (e >= x0) & (e <= x1) & (n >= y0) & (n <= y1)
    idx = np.flatnonzero(pre)
    inside = shapely.contains_xy(poly, e[idx], n[idx])
    idx = idx[inside]
    h = T["h"][idx]
    tall = h >= p["min_height_m"]
    sane = h <= p["max_height_m"]          # the survey has a few spikes (cranes, masts, bridge parts)
    dropped = {"low": int((~tall).sum()), "implausibly_tall": int((tall & ~sane).sum())}
    idx = idx[tall & sane]
    fps = footprints(load(ctx.dep("scene_buildings")))
    water = load_polygons(ctx.dep("scene_water") / "water.json")
    in_b = np.zeros(len(idx), bool); in_w = np.zeros(len(idx), bool)
    if fps:
        in_b = np.asarray(shapely.contains_xy(unary_union(fps), e[idx], n[idx]))
    if water:
        in_w = np.asarray(shapely.contains_xy(unary_union(water), e[idx], n[idx])) & ~in_b
    dropped["in_building"] = int(in_b.sum()); dropped["in_water"] = int(in_w.sum())
    idx = idx[~in_b & ~in_w]
    r_meas = (T["cmean"][idx] / 2).astype(np.float64)
    names = [str(s) for s in T["type_names"]]
    r_survey = r_meas * p["crown_scale"]
    r, _ = shape_radius(T["h"][idx], r_survey, T["type"][idx], e[idx], n[idx], p, names)
    r_shape = r.copy()
    widened = int((r > r_survey + 1e-6).sum())
    blockers = list(fps) + list(water)
    tree = STRtree(blockers) if blockers else None
    thinned = 0
    if tree is not None:
        share = overlap_share(e[idx], n[idx], r, blockers, tree)
        k = np.flatnonzero(share > p["max_overlap_share"])
        thinned = len(k)
        lo, hi = np.zeros(len(k)), r[k].copy()
        for _ in range(12):  # the largest radius whose overlap is within the limit (bisection, all at once)
            mid = (lo + hi) / 2
            ok = overlap_share(e[idx][k], n[idx][k], mid, blockers, tree) <= p["max_overlap_share"]
            lo = np.where(ok, mid, lo); hi = np.where(ok, hi, mid)
        r[k] = lo
    terrain = Grid.load(ctx.dep("scene_terrain") / "terrain.npz", "mnt")
    base = terrain.sample(e[idx], n[idx])
    base = np.where(np.isfinite(base), base, T["terrain"][idx])
    np.savez_compressed(ctx.out / "trees.npz", e=e[idx], n=n[idx], base_z=base.astype(np.float32),
                        height=T["h"][idx], crown_r=r.astype(np.float32), crown_r_shape=r_shape.astype(np.float32),
                        crown_r_measured=r_meas.astype(np.float32),
                        type=T["type"][idx], uuid=T["uuid"][idx], type_names=T["type_names"])
    hw = T["h"][idx] / np.maximum(2 * r, 1e-3)
    return {"trees": int(len(idx)), "dropped": dropped, "crowns_thinned": thinned, "crowns_widened": widened,
            "height_over_width_median": float(np.median(hw)) if len(idx) else 0,
            "by_type": {names[t]: int((T["type"][idx] == t).sum()) for t in range(len(names))},
            "height_m": {"median": float(np.median(T["h"][idx])) if len(idx) else 0,
                         "max": float(T["h"][idx].max()) if len(idx) else 0}}
