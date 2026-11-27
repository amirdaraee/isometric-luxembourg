"""Scene: trees from the ACT LiDAR 2024 tree survey (spec: v2/docs/specs/scene.md, "Trees").

Rules, in order:
  1. keep survey points inside the area with a height from min_height_m to max_height_m (taller ones are survey
     spikes: cranes, masts, bridge parts; no tree in the city is near 50 m);
  2. drop a tree whose crown centre is inside a building footprint (the survey finds roof gardens and roof clutter
     too, but a crown centred on a roof is drawn by the building layer, not as a tree) or inside water;
  3. crown radius: the survey's (crown_scale * crown_mean / 2; the POC found measured crowns read too big) widened to
     the tree's shape by species and age (shape_radius: the LiDAR crowns are a few metres wide on trees 15-25 m
     tall, which draws poplars; the owner asked for rounder crowns at the measured height, 9 Nov 2026); thin it so
     that at most max_overlap_share of the crown disc lies over buildings: r is reduced until it does, but never
     under min_thin_share of the shaped radius (`thin`). Water does not thin a crown: a tree on a bank hangs over
     the river. (Until 26 Nov 2026 water thinned crowns too, and with no least width: of the test area's 265
     thinned trees 222 stood by the water and 51 were left with a crown under 0.6 m, drawn as bare poles; one
     stood in the Alzette by Neumuenster Abbey. The owner, 25 Nov 2026: "the rivers are not good".)
  4. the base height is the terrain at the point (LiDAR ground); the tree is drawn at drawn_height_scale of its
     measured height (the owner, 24 Nov 2026: at the measured height the trees were too big beside the buildings;
     70% of the height, width and place kept). Rules 1 to 3 use the measured height.
trees.npz: e, n, base_z, height (drawn), height_measured, crown_r (drawn: shaped, then thinned), crown_r_shape
(before thinning), crown_r_measured, type, uuid; plus counts of what was dropped, widened and thinned.
"""
from __future__ import annotations

import numpy as np
import shapely
import shapely.ops
from shapely import STRtree
from shapely.ops import unary_union

from v2.data.geo import area_polygon
from v2.data.scene import tree_species
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


def thin(e, n, r, blockers, p):
    """Crown radii thinned for the blocker polygons (buildings): the largest radius, at most r, with at most
    max_overlap_share of the crown disc over them; never under min_thin_share of r (a crown thinned to nothing
    is a pole: a tree against a wall keeps a crown, which leans over the roof). Returns (radius, thinned, held):
    which crowns were narrowed, and which of them are held at their least width and still lie over a building by
    more than the share."""
    e, n, r = np.asarray(e, float), np.asarray(n, float), np.asarray(r, float).copy()
    thinned, held = np.zeros(len(r), bool), np.zeros(len(r), bool)
    if not len(r) or not len(blockers):
        return r, thinned, held
    tree = STRtree(blockers)
    k = np.flatnonzero(overlap_share(e, n, r, blockers, tree) > p["max_overlap_share"])
    lo, hi = np.zeros(len(k)), r[k].copy()
    for _ in range(12):  # the largest radius whose overlap is within the limit (bisection, all at once)
        mid = (lo + hi) / 2
        ok = overlap_share(e[k], n[k], mid, blockers, tree) <= p["max_overlap_share"]
        lo = np.where(ok, mid, lo); hi = np.where(ok, hi, mid)
    least = p["min_thin_share"] * r[k]
    thinned[k] = True
    held[k] = lo < least
    r[k] = np.maximum(lo, least)
    return r, thinned, held


def shape_radius(h, r_survey, typ, e, n, p, names, width=None):
    """The drawn crown radius by species and age: width = height x a ratio that grows from young to mature trees
    (height is the age proxy), capped, and by the room the tree has (at most neighbour_factor x the distance to its
    nearest neighbour, so a stand stays a stand of crowns); never under the survey's radius. The ratios and the cap
    are each tree's species' (`width`: young, mature, widest in m, per tree: tree_species.json) or, without it, its
    type's (params trees.crown_shape.by_type). Returns (radius, allometric radius before the neighbour cap)."""
    from scipy.spatial import cKDTree
    c = p["crown_shape"]
    h = np.asarray(h, float)
    age = np.clip((h - c["young_h_m"]) / max(c["mature_h_m"] - c["young_h_m"], 1e-6), 0, 1)
    allo = np.zeros(len(h))
    if width is not None:
        width = np.asarray(width, float)
        allo = np.minimum(h * (width[:, 0] + (width[:, 1] - width[:, 0]) * age), width[:, 2]) / 2
    for t, name in enumerate(names if width is None else ()):
        k = c["by_type"].get(name, c["by_type"]["other"])
        m = np.asarray(typ) == t
        allo[m] = np.minimum(h[m] * (k["young"] + (k["mature"] - k["young"]) * age[m]), k["max_width_m"]) / 2
    room = np.full(len(h), np.inf)
    if len(h) > 1:
        d, _ = cKDTree(np.column_stack([e, n])).query(np.column_stack([e, n]), k=2)
        room = d[:, 1] * c["neighbour_factor"]
    return np.maximum(r_survey, np.minimum(allo, room)), allo


def off_walls(e, n, blockers, clear_m):
    """Trunks off the walls of buildings (params trees.wall_clear): a tree nearer than clear_m to a building's
    outline is put straight out from the wall, clear_m from it; if that place is nearer than clear_m to any
    building (a gap too narrow for a tree), the tree is left out. Returns (e, n, moved, keep)."""
    e, n = np.asarray(e, float).copy(), np.asarray(n, float).copy()
    moved, keep = np.zeros(len(e), bool), np.ones(len(e), bool)
    if not len(e) or not len(blockers):
        return e, n, moved, keep
    tree = STRtree(blockers)
    pts = shapely.points(e, n)
    (ti, bi), d = tree.query_nearest(pts, max_distance=clear_m, return_distance=True, all_matches=False)
    near = d < clear_m - 1e-6
    for t, b_, dist in zip(ti[near], bi[near], d[near]):
        q = shapely.ops.nearest_points(blockers[b_].boundary, pts[t])[0]
        v = np.array([e[t] - q.x, n[t] - q.y])
        if dist < 1e-3 or not np.hypot(*v) > 1e-6:                # on the outline itself: no way out is known
            keep[t] = False
            continue
        v = v / np.hypot(*v) * clear_m
        e[t], n[t] = q.x + v[0], q.y + v[1]
        moved[t] = True
    m = np.flatnonzero(moved)
    if len(m):
        (ti, _), d = tree.query_nearest(shapely.points(e[m], n[m]), max_distance=clear_m, return_distance=True, all_matches=False)
        tight = m[ti[d < clear_m - 1e-3]]
        keep[tight] = False
        moved[tight] = False
    return e, n, moved, keep


def off_faces(e, n, h, r_meas, mnt, cls, e0, n0, step, p):
    """Trunks off the faces of walls and cliffs (params trees.off_faces): for each tree whose point lies on a cliff
    cell (terrain class 2) the nearest cell that is not one, within reach: above the point if there is one that
    leaves the tree at least the least height, else below it (at most the greatest height). The crown's top keeps
    its height above the sea. Returns (keep, e, n, h, moved): trees with no such ground are not kept."""
    f = p["off_faces"]
    e, n, h = np.asarray(e, float).copy(), np.asarray(n, float).copy(), np.asarray(h, float).copy()
    H, W = cls.shape
    jj = np.clip(np.floor((e - e0) / step).astype(int), 0, W - 1)
    ii = np.clip(np.floor((n - n0) / step).astype(int), 0, H - 1)
    keep, moved = np.ones(len(e), bool), np.zeros(len(e), bool)
    for k in np.flatnonzero(cls[ii, jj] == 2):
        reach = float(np.clip(r_meas[k] + f["margin_m"], f["min_reach_m"], f["max_reach_m"]))
        R = int(np.ceil(reach / step))
        i0, i1, j0, j1 = max(ii[k] - R, 0), min(ii[k] + R + 1, H), max(jj[k] - R, 0), min(jj[k] + R + 1, W)
        ce = e0 + (np.arange(j0, j1) + 0.5) * step
        cn = n0 + (np.arange(i0, i1) + 0.5) * step
        d = np.hypot(ce[None, :] - e[k], cn[:, None] - n[k])
        z = mnt[i0:i1, j0:j1].astype(float)
        z0 = float(mnt[ii[k], jj[k]])
        ok = (cls[i0:i1, j0:j1] != 2) & np.isfinite(z) & (d <= reach)
        hn = h[k] + z0 - z                                   # the tree's height above each candidate foot
        up = ok & (z >= z0) & (hn >= p["min_height_m"])
        down = ok & (z < z0) & (hn <= p["max_height_m"])
        cand = up if up.any() else down
        if not np.isfinite(z0) or not cand.any():
            keep[k] = False
            continue
        a, b = np.unravel_index(np.argmin(np.where(cand, d, np.inf)), d.shape)
        e[k], n[k], h[k], moved[k] = ce[b], cn[a], hn[a, b], True
    return keep, e, n, h, moved


def drawn_height(h, p):
    """The height a tree is drawn at: a fixed share of the measured one (params trees.drawn_height_scale)."""
    return np.asarray(h, np.float32) * np.float32(p["drawn_height_scale"])


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
    # trunks off the faces of walls and cliffs (the survey's point is the crown's top); a tree whose new foot would
    # be in a building or in water is left out
    tz = np.load(ctx.dep("scene_terrain") / "terrain.npz")
    keep, E, N, Hm, moved = off_faces(e[idx], n[idx], T["h"][idx], T["cmean"][idx] / 2, tz["mnt"], tz["cls"],
                                      float(tz["e0"]), float(tz["n0"]), float(tz["step"]), p)
    for geoms in (fps, water):
        if geoms and moved.any():
            keep &= ~(moved & np.asarray(shapely.contains_xy(unary_union(geoms), E, N)))
    dropped["on_a_face"] = int((~keep).sum())
    idx, E, N, Hm, moved = idx[keep], E[keep], N[keep], Hm[keep], moved[keep]
    # trunks off the walls of buildings; a tree with no room, or whose new place is in water or on a face, is left out
    E, N, off_wall, keep = off_walls(E, N, list(fps), p["wall_clear"]["clear_m"])
    if water and off_wall.any():
        keep &= ~(off_wall & np.asarray(shapely.contains_xy(unary_union(water), E, N)))
    if off_wall.any():                                            # nor on the face of a wall or a cliff
        cj = np.clip(np.floor((E - float(tz["e0"])) / float(tz["step"])).astype(int), 0, tz["cls"].shape[1] - 1)
        ci = np.clip(np.floor((N - float(tz["n0"])) / float(tz["step"])).astype(int), 0, tz["cls"].shape[0] - 1)
        keep &= ~(off_wall & (tz["cls"][ci, cj] == 2))
    dropped["against_a_wall"] = int((~keep).sum())
    idx, E, N, Hm, moved, off_wall = idx[keep], E[keep], N[keep], Hm[keep], moved[keep], off_wall[keep]
    r_meas = (T["cmean"][idx] / 2).astype(np.float64)
    names = [str(s) for s in T["type_names"]]
    r_survey = r_meas * p["crown_scale"]
    # the species each tree is drawn as (by rule: tree_species.py), and its crown's width from it
    S = tree_species.config()
    register = tree_species.load_register(ctx.dep("fetch_city_trees") / "city_trees.json", S)
    sp, rule, sp_names = tree_species.assign(
        E, N, T["type"][idx], Hm, names, S,
        tree_species.context(ctx.dep("fetch_osm_ground") / "ground.json", ctx.dep("fetch_osm_transport") / "transport.json", S),
        water=water, register=register)
    # a tree the register names takes its type from its species (the register knows a pine from a lime; the
    # survey's type is a guess from the LiDAR colours)
    typ = np.asarray(T["type"][idx]).copy()
    known = rule == tree_species.RULES.index("register")
    kind = np.where(np.isin(sp_names, S["assign"]["conifers"]), names.index("conifer"),
                    np.where(np.isin(sp_names, S["assign"]["red"]), names.index("deciduous_red"), names.index("deciduous_green")))
    retyped = int((known & (kind[sp] != typ) & ~((typ == names.index("other")) & (kind[sp] == names.index("deciduous_green")))).sum())
    typ[known] = kind[sp][known]
    widths = np.array([{**S["defaults"], **S["list"][k]}["width"] for k in sp_names], float)[sp]
    r, _ = shape_radius(Hm, r_survey, typ, E, N, p, names, width=widths)
    r_shape = r.copy()
    widened = int((r > r_survey + 1e-6).sum())
    r, was_thinned, held = thin(E, N, r, list(fps), p)
    thinned = int(was_thinned.sum())
    terrain = Grid.load(ctx.dep("scene_terrain") / "terrain.npz", "mnt")
    base = terrain.sample(E, N)
    base = np.where(np.isfinite(base), base, T["terrain"][idx])
    np.savez_compressed(ctx.out / "trees.npz", e=E, n=N, base_z=base.astype(np.float32),
                        height=drawn_height(Hm, p), height_measured=Hm.astype(np.float32),
                        crown_r=r.astype(np.float32), crown_r_shape=r_shape.astype(np.float32),
                        crown_r_measured=r_meas.astype(np.float32),
                        type=typ, type_survey=T["type"][idx], uuid=T["uuid"][idx], type_names=T["type_names"],
                        species=sp.astype(np.int8), species_names=np.array(sp_names), species_rule=rule.astype(np.int8),
                        species_rules=np.array(tree_species.RULES), moved_off_a_face=moved)
    hw = drawn_height(Hm, p) / np.maximum(2 * r, 1e-3)
    return {"trees": int(len(idx)), "dropped": dropped, "moved_off_a_face": int(moved.sum()), "moved_off_a_wall": int(off_wall.sum()), "crowns_thinned": thinned, "crowns_held_at_least_width": int(held.sum()), "crowns_widened": widened,
            "height_over_width_median": float(np.median(hw)) if len(idx) else 0,
            "by_type": {names[t]: int((typ == t).sum()) for t in range(len(names))},
            "register": {"trees": register["trees"], "with_a_drawn_species": register["drawn"],
                         "in_the_area": int(shapely.contains_xy(poly, register["e"], register["n"]).sum()),
                         "matched": int(known.sum()), "type_changed": retyped},
            "by_species": {k: int((sp == i).sum()) for i, k in enumerate(sp_names)},
            "by_species_rule": {k: int((rule == i).sum()) for i, k in enumerate(tree_species.RULES)},
            "height_m": {"median": float(np.median(Hm)) if len(idx) else 0,
                         "max": float(Hm.max()) if len(idx) else 0},
            "drawn_height_m": {"scale": p["drawn_height_scale"],
                               "median": float(np.median(drawn_height(Hm, p))) if len(idx) else 0}}
