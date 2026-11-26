"""Scene: each building's roof covering, read from the orthophoto (spec: v2/docs/specs/scene.md, "Roofs";
layer-05-buildings.md; the owner, 26 Nov 2026: the real roofs, not a share by rule).

The 3D buildings give a roof's shape, not what it is covered with. The orthophoto shows it. As for the ground cover,
the photo is used to *class* the roof only, never as a colour: a roof gets one of the palette's roof colours, so no
shadow and nothing lying on a roof in the photo can reach a layer.

Rules, in order:
  1. the photo is read at a grid of step_m inside the building's footprint drawn in by inset_m (the eaves, the
     gutters and the neighbour's roof stay out), not within crown_grow_m of a surveyed tree's measured crown, and
     not darker than min_lum (deep shadow);
  2. a roof with fewer than min_px such points is *not read*: the art's rule decides (art_a.py);
  3. a point is *warm* by (r - b) / (r + g + b): fired clay is red over blue, slate and zinc are blue over red;
  4. a pitched roof is *tile* where the median warmth is tile_warm or more and tile_share of its points are that
     warm: bright tile from tile_bright up, else brown tile. Every other pitched roof is *slate*, in the shade the
     photo shows: dark under slate_dark_lum (median luminance), else blue at slate_blue or less warmth, warm grey
     at slate_warm or more, else plain;
  5. a flat roof is *planted* where its median excess green is flat_green or more, *gravel* where its warmth is
     flat_gravel or more, else grey.

The thresholds were set on the test area's 1,037 readable roofs: the tile threshold lies in an empty stretch (three
pitched roofs at 0.10 and over, the next at 0.03); the slate shades' are the quartiles of what the photo shows.

roofs.json: {"roofs": {building id: {"roof": palette name, "px", "rgb", "warm", "lum"}}, "counts": {name: n}}.
"""
from __future__ import annotations

import math

import numpy as np
import shapely

from v2.config import raw_dir
from v2.data.geo import area_polygon
from v2.data.scene.buildings import footprints, load
from v2.data.scene.groundcover import _raster, excess_green, luminance, photo

SLATES = ("roof_slate_dark", "roof_slate_blue", "roof_slate_warm", "roof_slate")
TILES = ("roof_tile", "roof_tile_brown")
FLATS = ("roof_flat_green", "roof_flat_gravel", "roof_flat")


def warmth(rgb) -> np.ndarray:
    a = np.asarray(rgb, float)
    return (a[..., 0] - a[..., 2]) / (a.sum(-1) + 1e-6)


def classify(rgb, flat: bool, p: dict):
    """Rules 2 to 5 on one roof's photo points (n, 3), already without crowns: (palette name or None, figures)."""
    a = np.asarray(rgb, float).reshape(-1, 3)
    a = a[luminance(a) > p["min_lum"]]
    if len(a) < p["min_px"]:
        return None, {"px": int(len(a))}
    w = warmth(a)
    med = np.median(a, axis=0)
    wm, lum = float(np.median(w)), float(luminance(med))
    fig = {"px": int(len(a)), "rgb": [int(round(v)) for v in med], "warm": round(wm, 4), "lum": round(lum, 1)}
    if flat:
        if float(np.median(excess_green(a))) >= p["flat_green"]:
            return "roof_flat_green", fig
        return ("roof_flat_gravel" if wm >= p["flat_gravel"] else "roof_flat"), fig
    if wm >= p["tile_warm"] and float((w >= p["tile_warm"]).mean()) >= p["tile_share"]:
        return ("roof_tile" if wm >= p["tile_bright"] else "roof_tile_brown"), fig
    if lum < p["slate_dark_lum"]:
        return "roof_slate_dark", fig
    if wm <= p["slate_blue"]:
        return "roof_slate_blue", fig
    return ("roof_slate_warm" if wm >= p["slate_warm"] else "roof_slate"), fig


def is_flat(b: dict) -> bool:
    """As the art's own test (art_a.Style): the building's roof shape is flat."""
    return b.get("roof_shape", "") == "flat"


def build(ctx):
    p = ctx.params["roofs"]
    step = float(p["step_m"])
    B = load(ctx.dep("scene_buildings"))
    x0, y0, x1, y1 = area_polygon(ctx.area).buffer(60).bounds
    e0, n0 = math.floor(x0 / step) * step, math.floor(y0 / step) * step
    W, H = int(math.ceil((x1 - e0) / step)), int(math.ceil((y1 - n0) / step))
    t = np.load(ctx.dep("scene_trees") / "trees.npz")
    crowns = _raster((H, W), e0, n0, step,
                     discs=zip(t["e"].tolist(), t["n"].tolist(), (t["crown_r_measured"] + p["crown_grow_m"]).tolist()))
    folder = raw_dir() / p["ortho_dir"] / str(p["zoom"])
    out, counts = {}, {}
    for b, fp in zip(B, footprints(B)):
        q = fp.buffer(-p["inset_m"])
        name, fig = None, {"px": 0}
        if not q.is_empty:
            bx0, by0, bx1, by1 = q.bounds
            c0, c1 = int(math.floor((bx0 - e0) / step)), int(math.ceil((bx1 - e0) / step))
            r0, r1 = int(math.floor((by0 - n0) / step)), int(math.ceil((by1 - n0) / step))
            C, R = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
            E, N = e0 + (C + 0.5) * step, n0 + (R + 0.5) * step
            inside = shapely.contains_xy(q, E, N)
            ok = (C >= 0) & (C < W) & (R >= 0) & (R < H)
            inside &= ok
            inside[inside] &= ~crowns[R[inside], C[inside]]
            if inside.any():
                rgb, have = photo(E[inside], N[inside], folder, int(p["zoom"]))
                name, fig = classify(rgb[have], is_flat(b), p)
        out[b["id"]] = {"roof": name, **fig}
        counts[name or "not_read"] = counts.get(name or "not_read", 0) + 1
    ctx.write_json("roofs.json", {"roofs": out, "counts": counts})
    pitched = sum(v for k, v in counts.items() if k in SLATES + TILES)
    return {"buildings": len(B), "read": len(B) - counts.get("not_read", 0), "counts": counts,
            "tile_share_of_pitched": round(sum(counts.get(k, 0) for k in TILES) / max(pitched, 1), 4)}


def load_roofs(folder) -> dict:
    """{building id: palette roof name} for the roofs the photo reads."""
    import json
    d = json.loads((folder / "roofs.json").read_text())["roofs"]
    return {k: v["roof"] for k, v in d.items() if v.get("roof")}
