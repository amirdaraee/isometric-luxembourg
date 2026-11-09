"""Scene: trees from the ACT LiDAR 2024 tree survey (spec: v2/docs/specs/scene.md, "Trees").

Rules, in order:
  1. keep survey points inside the area with a height from min_height_m to max_height_m (taller ones are survey
     spikes: cranes, masts, bridge parts; no tree in the city is near 50 m);
  2. drop a tree whose crown centre is inside a building footprint (the survey finds roof gardens and roof clutter
     too, but a crown centred on a roof is drawn by the building layer, not as a tree) or inside water;
  3. crown radius r = crown_scale * crown_mean / 2 (the POC found measured crowns read too big); thin it so that at
     most max_overlap_share of the crown disc lies over buildings or water: r is reduced until it does;
  4. the base height is the terrain at the point (LiDAR ground), the top base + height.
trees.npz: e, n, base_z, height, crown_r (after thinning), crown_r_measured, type, uuid; plus counts of what was
dropped and thinned.
"""
from __future__ import annotations

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import Point
from shapely.ops import unary_union

from v2.data.geo import area_polygon
from v2.data.scene.buildings import footprints, load
from v2.data.scene.grid import Grid
from v2.data.scene.water import load_polygons


def overlap_share(cx, cy, r, blockers_union):
    if r <= 0:
        return 0.0
    d = Point(cx, cy).buffer(r, 16)
    return d.intersection(blockers_union).area / d.area


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
    r = r_meas * p["crown_scale"]
    blockers = fps + water
    tree = STRtree(blockers) if blockers else None
    thinned = 0
    for k, i in enumerate(idx):
        if tree is None:
            break
        near = tree.query(Point(e[i], n[i]).buffer(r[k]))
        if len(near) == 0:
            continue
        u = unary_union([blockers[j] for j in near])
        if overlap_share(e[i], n[i], r[k], u) <= p["max_overlap_share"]:
            continue
        lo, hi = 0.0, r[k]
        for _ in range(12):  # largest radius whose overlap is within the limit
            mid = (lo + hi) / 2
            if overlap_share(e[i], n[i], mid, u) <= p["max_overlap_share"]:
                lo = mid
            else:
                hi = mid
        r[k] = lo
        thinned += 1
    terrain = Grid.load(ctx.dep("scene_terrain") / "terrain.npz", "mnt")
    base = terrain.sample(e[idx], n[idx])
    base = np.where(np.isfinite(base), base, T["terrain"][idx])
    np.savez_compressed(ctx.out / "trees.npz", e=e[idx], n=n[idx], base_z=base.astype(np.float32),
                        height=T["h"][idx], crown_r=r.astype(np.float32), crown_r_measured=r_meas.astype(np.float32),
                        type=T["type"][idx], uuid=T["uuid"][idx], type_names=T["type_names"])
    names = [str(s) for s in T["type_names"]]
    return {"trees": int(len(idx)), "dropped": dropped, "crowns_thinned": thinned,
            "by_type": {names[t]: int((T["type"][idx] == t).sum()) for t in range(len(names))},
            "height_m": {"median": float(np.median(T["h"][idx])) if len(idx) else 0,
                         "max": float(T["h"][idx].max()) if len(idx) else 0}}
