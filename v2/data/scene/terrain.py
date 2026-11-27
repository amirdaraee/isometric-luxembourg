"""Scene: terrain and relief (spec: v2/docs/specs/scene.md, "Terrain").

From the LiDAR 2024 ground model (MNT) and surface model (MNS), over the area plus its margin:
  terrain.npz   mnt (ground, m), mns (surface, m), slope (deg), cls (0 ground, 1 steep, 2 cliff), e0, n0, step
  walls.json    OSM retaining walls, city walls, cliffs and embankments, with their top and foot heights
                measured on the terrain either side of the line
Small holes in the MNT (under buildings the survey has no ground there) are filled from their edges and counted.
Small deep pits inside paved squares (stairs and ramps down to what lies under the square) are filled to the
square's level and counted (fill_pits).
"""
from __future__ import annotations

import json

import numpy as np
from scipy import ndimage

from v2.data.geo import osm_area_en, way_en
from v2.data.scene.grid import Grid


def fill_holes(z):
    bad = ~np.isfinite(z)
    if not bad.any():
        return z, 0
    idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
    return z[tuple(idx)], int(bad.sum())


def squares(transport_osm):
    """The paved squares of the transport data: areas of pedestrian streets (highway=pedestrian, area=yes), as the
    ground layer draws them."""
    out = []
    for el in transport_osm["elements"]:
        tg = el.get("tags", {})
        if el["type"] == "way" and tg.get("area") == "yes" and tg.get("highway") == "pedestrian":
            g = osm_area_en(el)
            if g is not None and not g.is_empty:
                out.append(g)
    return out


def fill_pits(z, e0, n0, step, areas, p):
    """Pits in paved squares filled to the square's level (params terrain.square_pits). The square's level at a
    cell is the median ground within level_window_m around it. A dip (cells of the square more than edge_m under
    the level, joined) is a pit when it goes more than min_depth_m under the level and covers at most max_area_m2:
    its cells are put at the level. Returns (z, pits filled, cells filled)."""
    import shapely
    z = np.array(z, np.float32)
    H, W = z.shape
    win = max(3, int(round(p["level_window_m"] / step)) | 1)
    pad = win // 2 + 1
    pits = cells = 0
    for g in areas:
        x0, y0, x1, y1 = g.bounds
        j0, j1 = max(0, int((x0 - e0) / step) - pad), min(W, int((x1 - e0) / step) + pad + 1)
        i0, i1 = max(0, int((y0 - n0) / step) - pad), min(H, int((y1 - n0) / step) + pad + 1)
        if j1 - j0 < 3 or i1 - i0 < 3:
            continue
        sub = z[i0:i1, j0:j1]
        ee, nn = np.meshgrid(e0 + (np.arange(j0, j1) + 0.5) * step, n0 + (np.arange(i0, i1) + 0.5) * step)
        inside = shapely.contains_xy(g, ee, nn)
        if not inside.any():
            continue
        coarse = max(1, win // 20)                                 # the level on a coarser grid: it varies slowly
        for _ in range(8):                                         # a filled pit moves the level a little: until none is left
            level = ndimage.median_filter(sub[::coarse, ::coarse], size=max(3, (win // coarse) | 1), mode="nearest")
            level = np.repeat(np.repeat(level, coarse, 0), coarse, 1)[:sub.shape[0], :sub.shape[1]]
            lab, k = ndimage.label(inside & (sub < level - p["edge_m"]))
            idx = np.arange(1, k + 1)
            deepest = ndimage.maximum(level - sub, lab, idx) if k else np.zeros(0)
            size = ndimage.sum(np.ones_like(lab), lab, idx) * step * step if k else np.zeros(0)
            hit = idx[(deepest > p["min_depth_m"]) & (size <= p["max_area_m2"])]
            if not len(hit):
                break
            m = np.isin(lab, hit)
            sub[m] = level[m]
            pits += len(hit); cells += int(m.sum())
    return z, pits, cells


def slope_deg(z, step):
    gy, gx = np.gradient(z, step)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def classify(z, step, p):
    s = slope_deg(z, step)
    cls = np.zeros(z.shape, np.uint8)
    cls[s >= p["steep_deg"]] = 1
    # a cliff: very steep and a real drop (max - min over a 3 m neighbourhood), not a kerb or a step in the data
    k = max(3, int(round(3.0 / step)) | 1)
    drop = ndimage.maximum_filter(z, k) - ndimage.minimum_filter(z, k)
    cls[(s >= p["cliff_deg"]) & (drop >= p["cliff_min_drop_m"])] = 2
    return s, cls


def wall_features(ground_osm, grid: Grid, p):
    tags = p["osm_wall_tags"]
    out = []
    for el in ground_osm["elements"]:
        if el["type"] != "way" or "geometry" not in el:
            continue
        tg = el.get("tags", {})
        kind = next((f"{k}={tg[k]}" for k, vs in tags.items() if tg.get(k) in vs), None)
        if not kind:
            continue
        en = way_en(el)
        if not grid.inside(en[:, 0], en[:, 1]).any():
            continue
        # densify every 1 m, measure the terrain 1.5 m either side: top and foot of the wall
        seg = np.hypot(*np.diff(en, axis=0).T)
        L = float(seg.sum())
        if L < 1:
            continue
        s = np.linspace(0, L, max(2, int(L) + 1))
        cum = np.r_[0, np.cumsum(seg)]
        e = np.interp(s, cum, en[:, 0]); n = np.interp(s, cum, en[:, 1])
        d = np.gradient(np.column_stack((e, n)), axis=0)
        d /= np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)[:, None]
        nx, ny = -d[:, 1], d[:, 0]
        a = grid.sample(e + nx * 1.5, n + ny * 1.5)
        b = grid.sample(e - nx * 1.5, n - ny * 1.5)
        top, foot = np.fmax(a, b), np.fmin(a, b)
        ok = np.isfinite(top) & np.isfinite(foot)
        out.append({"osm": f"way/{el['id']}", "kind": kind, "name": tg.get("name", ""), "length_m": round(L, 1),
                    "en": [[round(x, 2), round(y, 2)] for x, y in en],
                    "top_m": [round(float(v), 2) if np.isfinite(v) else None for v in top[::5]],
                    "foot_m": [round(float(v), 2) if np.isfinite(v) else None for v in foot[::5]],
                    "drop_m": round(float(np.median(top[ok] - foot[ok])), 2) if ok.any() else None})
    return out


def build(ctx):
    d = np.load(ctx.dep("fetch_lidar") / "lidar.npz")
    e0, n0, step = float(d["e0"]), float(d["n0"]), float(d["step"])
    mnt, holes_mnt = fill_holes(d["mnt"].astype(np.float32))
    mns, holes_mns = fill_holes(d["mns"].astype(np.float32))
    sq = squares(json.loads((ctx.dep("fetch_osm_transport") / "transport.json").read_text()))
    mnt, pits, pit_cells = fill_pits(mnt, e0, n0, step, sq, ctx.params["terrain"]["square_pits"])
    s, cls = classify(mnt, step, ctx.params["terrain"])
    np.savez_compressed(ctx.out / "terrain.npz", mnt=mnt, mns=mns, slope=s.astype(np.float16), cls=cls,
                        e0=e0, n0=n0, step=step)
    ground = json.loads((ctx.dep("fetch_osm_ground") / "ground.json").read_text())
    walls = wall_features(ground, Grid(mnt, e0, n0, step), ctx.params["terrain"])
    ctx.write_json("walls.json", {"walls": walls})
    cell = step * step
    return {"shape": list(mnt.shape), "step_m": step, "z_range": [float(mnt.min()), float(mnt.max())],
            "holes_filled": {"mnt": holes_mnt, "mns": holes_mns}, "squares": len(sq), "square_pits_filled": pits,
            "square_pit_cells": pit_cells, "steep_m2": float((cls == 1).sum() * cell),
            "cliff_m2": float((cls == 2).sum() * cell), "walls": len(walls),
            "walls_km": round(sum(w["length_m"] for w in walls) / 1000, 2)}
