"""Scene: vegetated ground where OSM says nothing, read from the orthophoto (spec: v2/docs/specs/scene.md, "Ground
cover"; layer-01-ground.md rule 1; the owner, 23 Nov 2026: v1's ground).

OSM classes a part of the land. The rest was drawn as paving inside the built-up area, which made gardens and
planted slopes bare. The orthophoto shows them. It is used to *class* the land only, never as a colour, so no car
and no shadow in the photo can reach a layer (layer-01's own rule).

Rules, in order:
  1. a grid of step_m over the area (margin_m round it), each cell the photo's colour there (the orthophoto's web
     mercator tiles at `zoom`);
  2. a cell is *readable* where the photo has a tile, shows the ground and can be told: not under a building's
     footprint, not within crown_grow_m of a surveyed tree's measured crown (a crown is green over paving too: a
     street tree must not turn its pavement into lawn), and not darker than min_lum (deep shadow);
  3. a readable cell is *green* where its excess green, (2g - r - b) / (r + g + b), is over exg;
  4. a cell is *vegetated* where the green share of the readable land round it (a Gaussian of sigma_m) is share or
     more. One cell's colour does not decide: a lawn has dry patches, paths and shadows, a square has a planter. A
     cell with too little readable land in reach (deep under crowns, inside a courtyard's shadow) takes the nearest
     decided cell's answer;
  5. vegetated patches smaller than min_area_m2 are dropped, and holes that small are closed.

The thresholds were set on the land OSM does class in the test area, and the data checks GC2 and GC3 measure the
same on every build: of OSM's gardens 83% came out vegetated, of its lawns 52% (the photo is of a dry summer: a
straw-coloured lawn is not told from paving, and stays paved), of its squares, car parks and rail ground 9%.

groundcover.npz: veg (uint8, 1 vegetated; row 0 south, as scene/grid.py), photo (uint8, 1 where the photo has a
tile), e0, n0, step.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from v2.config import raw_dir
from v2.data.geo import area_polygon, en_to_lonlat
from v2.data.scene.buildings import footprints, load
from v2.data.scene.grid import Grid

Image.MAX_IMAGE_PIXELS = None


def excess_green(rgb) -> np.ndarray:
    a = np.asarray(rgb, float)
    return (2 * a[..., 1] - a[..., 0] - a[..., 2]) / (a.sum(-1) + 1e-6)


def luminance(rgb) -> np.ndarray:
    return np.asarray(rgb, float) @ np.array([0.299, 0.587, 0.114])


def classify(rgb, readable, p: dict, step: float) -> np.ndarray:
    """Rules 3 to 5 on a grid: `rgb` (H, W, 3), `readable` (H, W) bool. Returns the vegetated cells (bool)."""
    readable = readable & (luminance(rgb) > p["min_lum"])
    green = readable & (excess_green(rgb) > p["exg"])
    sg = p["sigma_m"] / step
    num = ndi.gaussian_filter(green.astype(np.float32), sg)
    den = ndi.gaussian_filter(readable.astype(np.float32), sg)
    decided = den > 0.05
    veg = decided & (num >= p["share"] * den)
    if decided.any() and not decided.all():                 # no readable land in reach: the nearest decided cell's
        idx = ndi.distance_transform_edt(~decided, return_distances=False, return_indices=True)
        veg = veg[idx[0], idx[1]]
    k = max(int(round(p["min_area_m2"] / (step * step))), 1)
    for want in (True, False):                              # small patches out, then small holes closed
        lab, n = ndi.label(veg == want)
        if n:
            small = np.flatnonzero(np.bincount(lab.ravel(), minlength=n + 1)[1:] < k) + 1
            if len(small):
                veg = np.where(np.isin(lab, small), not want, veg)
    return veg


def photo(e, n, folder, zoom: int):
    """The orthophoto's colour at LUREF points (any shape): (rgb uint8, has a tile bool). Nearest photo pixel."""
    shape = np.shape(e)
    lon, lat = en_to_lonlat(np.ravel(e), np.ravel(n))
    t = 2 ** zoom * 256
    mx = (np.asarray(lon) + 180) / 360 * t
    my = (1 - np.arcsinh(np.tan(np.radians(np.asarray(lat)))) / math.pi) / 2 * t
    tx, ty = (mx // 256).astype(np.int64), (my // 256).astype(np.int64)
    out = np.zeros((len(mx), 3), np.uint8); have = np.zeros(len(mx), bool)
    key = tx * (1 << 32) + ty
    order = np.argsort(key, kind="stable")
    cuts = np.flatnonzero(np.diff(key[order])) + 1
    for g in np.split(order, cuts):
        f = folder / f"{tx[g[0]]}_{ty[g[0]]}.jpg"
        if not f.exists():
            continue
        im = np.asarray(Image.open(f).convert("RGB"))
        out[g] = im[np.clip((my[g] - ty[g] * 256).astype(int), 0, 255), np.clip((mx[g] - tx[g] * 256).astype(int), 0, 255)]
        have[g] = True
    return out.reshape(shape + (3,)), have.reshape(shape)


def _raster(shape, e0, n0, step, polys=(), discs=()):
    """Polygons and discs (e, n, r) as a mask on the grid (row 0 south)."""
    H, W = shape
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    for g in polys:
        for q in (g.geoms if hasattr(g, "geoms") else [g]):
            if q.is_empty or q.geom_type != "Polygon":
                continue
            d.polygon([((x - e0) / step, (y - n0) / step) for x, y in q.exterior.coords], fill=1)
    for e, n, r in discs:
        cx, cy, pr = (e - e0) / step, (n - n0) / step, r / step
        d.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=1)
    return np.asarray(im) > 0


def build(ctx):
    p = ctx.params["groundcover"]
    step = float(p["step_m"])
    x0, y0, x1, y1 = area_polygon(ctx.area).buffer(p["margin_m"]).bounds
    e0, n0 = math.floor(x0 / step) * step, math.floor(y0 / step) * step
    W, H = int(math.ceil((x1 - e0) / step)), int(math.ceil((y1 - n0) / step))
    E, N = np.meshgrid(e0 + (np.arange(W) + 0.5) * step, n0 + (np.arange(H) + 0.5) * step)
    rgb, have = photo(E, N, raw_dir() / p["ortho_dir"] / str(p["zoom"]), int(p["zoom"]))
    t = np.load(ctx.dep("scene_trees") / "trees.npz")
    crowns = _raster((H, W), e0, n0, step,
                     discs=zip(t["e"].tolist(), t["n"].tolist(), (t["crown_r_measured"] + p["crown_grow_m"]).tolist()))
    roofs = _raster((H, W), e0, n0, step, polys=footprints(load(ctx.dep("scene_buildings"))))
    readable = have & ~crowns & ~roofs
    veg = classify(rgb, readable, p, step) & have
    np.savez_compressed(ctx.out / "groundcover.npz", veg=veg.astype(np.uint8), photo=have.astype(np.uint8),
                        e0=e0, n0=n0, step=step)
    return {"cells": int(veg.size), "step_m": step, "photo_share": round(float(have.mean()), 4),
            "readable_share": round(float(readable.mean()), 4), "vegetated_share": round(float(veg.mean()), 4)}


def load_grid(folder) -> Grid:
    d = np.load(folder / "groundcover.npz")
    return Grid(d["veg"].astype(np.float32), d["e0"], d["n0"], d["step"])


def vegetated(grid: Grid, e, n) -> np.ndarray:
    """Whether the ground at LUREF points is vegetated by the photo (False outside the grid)."""
    i, j = grid.ij(e, n)
    i, j = np.rint(i).astype(np.int64), np.rint(j).astype(np.int64)
    h, w = grid.shape
    ok = (i >= 0) & (i < h) & (j >= 0) & (j < w)
    out = np.zeros(np.shape(i), bool)
    out[ok] = grid.z[i[ok], j[ok]] > 0.5
    return out
