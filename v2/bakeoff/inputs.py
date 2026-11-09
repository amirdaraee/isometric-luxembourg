"""The inputs of methods B and C, made locally at $0: the windows to paint, their unlit renders, the layout images,
the masks, and the test area's landmark list.

Unlit render: the area as the code draws it with Phase 1's plain, evenly lit buildings (art "plain": flat material
colours, ink outlines, the facade layout's windows, doors and shop fronts), over the code ground, relief, water and
transport, no light pass at all (no sun, no shadow, no night) and nothing that moves. Layout: black outlines and dark
windows on white (v1's second control image). Mask: where layers 5 and 6 cover (what a painting may replace).

Trees are left out of the inputs (PAINT_LAYERS): a building is painted whole, not through the crowns in front of
it, and layer 7 is drawn over it by its own depth as in every method. Each window also keeps the depth, ids and
normals of what is seen at every pixel (geom.npz), so a painting is used only where its own layer is what was seen.

Windows are 1024 x 1024 map pixels (0.125 m/px: one model pixel per map pixel, so a 1.1 m window is ~9 model px, at
least 2 latent cells, layer-05 rule 4), on a grid with stride 768 over every tile that has a building.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from v2.layers.common import COLOUR_LAYERS, TILE, Tile, project

WIN = 1024
STRIDE = 768
PAINT_LAYERS = COLOUR_LAYERS[:6]          # ground, relief, water, transport, buildings, structures: no trees


def windows(scene, building_tiles):
    """(x0, y0) of every 1024 px window meeting a tile with buildings, stride 768 (zoom-0 map pixels)."""
    xs = [int(n.split("_")[0]) for n in building_tiles]
    ys = [int(n.split("_")[1]) for n in building_tiles]
    if not xs:
        return []
    have = set(building_tiles)
    x0, x1 = min(xs) * TILE, (max(xs) + 1) * TILE
    y0, y1 = min(ys) * TILE, (max(ys) + 1) * TILE
    def steps(a, b):
        v = list(range(a, max(b - WIN, a) + 1, STRIDE))
        if v[-1] + WIN < b:
            v.append(v[-1] + STRIDE)                     # the last window reaches past the end
        return v
    out = []
    for y in steps(y0, y1):
        for x in steps(x0, x1):
            tiles = {f"{tx}_{ty}" for tx in range(x // TILE, (x + WIN - 1) // TILE + 1)
                     for ty in range(y // TILE, (y + WIN - 1) // TILE + 1)}
            if tiles & have:
                out.append((x, y))
    return out


class _Built:
    """A built tile of a release as a LayerTile-like object (rgb, depth, normal, k, ids), empty where none."""

    def __init__(self, rel, layer, tile):
        from v2.checks.layer_checks import load
        t = load(rel, layer, tile.name)
        n = TILE
        self.rgb = t["rgb"] if t and "rgb" in t else np.zeros((n, n, 3), np.uint8)
        self.depth = t["depth"] if t and "depth" in t else np.full((n, n), np.inf)
        self.normal = t["normal"] if t and "normal" in t else np.zeros((n, n, 3))
        self.k = t["k"] if t and "k" in t else np.zeros((n, n), np.uint8)
        self.ids = t.get("ids") if t else None


def render_window(R_plain, x0, y0, size=WIN, layers=PAINT_LAYERS, rel=None):
    """Unlit render, layout and mask of one window, composited by depth (ties to the later layer), relief
    multiplied onto the ground under it. With `rel` (a built release), layers 1-4 are read from its tiles (they are
    the same for every art method) and only layers 5-7 are drawn here, plain."""
    rgb = np.zeros((size, size, 3)); depth = np.full((size, size), np.inf)
    which = np.zeros((size, size), np.uint8); edge = np.zeros((size, size), bool); win = np.zeros((size, size), bool)
    ids = np.zeros((size, size), np.uint32); nrm = np.zeros((size, size, 3))
    for ty in range(y0 // TILE, (y0 + size - 1) // TILE + 1):
        for tx in range(x0 // TILE, (x0 + size - 1) // TILE + 1):
            tile = Tile(tx, ty, apron=0)
            a0, b0 = max(x0, tx * TILE), max(y0, ty * TILE)
            a1, b1 = min(x0 + size, (tx + 1) * TILE), min(y0 + size, (ty + 1) * TILE)
            if a1 <= a0 or b1 <= b0:
                continue
            sl = (slice(b0 - ty * TILE, b1 - ty * TILE), slice(a0 - tx * TILE, a1 - tx * TILE))
            dl = (slice(b0 - y0, b1 - y0), slice(a0 - x0, a1 - x0))
            for li, L in enumerate(layers):
                t = _Built(rel, L, tile) if rel is not None and L in COLOUR_LAYERS[:4] else R_plain.layer(L, tile)
                d = t.depth[sl]; c = t.rgb[sl].astype(float)
                if L == "relief":
                    k = t.k[sl]
                    on = (k != 3) & np.isfinite(d) & (which[dl] == 1)
                    sub = rgb[dl]; sub[on] = sub[on] * c[on] / 255; rgb[dl] = sub
                    d = np.where(k == 3, d, np.inf)
                m = d <= depth[dl]
                for arr, val in ((rgb, c), (depth, d)):
                    sub = arr[dl]; sub[m] = val[m]; arr[dl] = sub
                sw = which[dl]; sw[m] = li + 1; which[dl] = sw
                if L in ("buildings", "structures") and t.ids is not None:
                    cls = (t.ids[sl] & 255)
                    sw2 = win[dl]; sw2[m] = np.isin(cls[m], (12, 13, 14)); win[dl] = sw2
                si = ids[dl]; si[m] = (t.ids[sl][m] if t.ids is not None else 0); ids[dl] = si
                sn = nrm[dl]; sn[m] = t.normal[sl][m]; nrm[dl] = sn
    mask = np.isin(which, (COLOUR_LAYERS.index("buildings") + 1, COLOUR_LAYERS.index("structures") + 1))
    # layout: outlines where the nearest layer, or the depth, changes; windows dark
    w8 = which.astype(np.int32) * 1000 + 0
    dz = np.where(np.isfinite(depth), depth, 1e6)
    edge[:, 1:] |= (w8[:, 1:] != w8[:, :-1]) | (np.abs(np.diff(dz, axis=1)) > 0.6)
    edge[1:, :] |= (w8[1:, :] != w8[:-1, :]) | (np.abs(np.diff(dz, axis=0)) > 0.6)
    lum = rgb.mean(-1)
    edge |= np.abs(np.diff(lum, axis=1, prepend=lum[:, :1])) > 40
    edge |= np.abs(np.diff(lum, axis=0, prepend=lum[:1, :])) > 40
    layout = np.full((size, size), 255, np.uint8)
    layout[win] = 90
    layout[edge] = 0
    return np.clip(np.round(rgb), 0, 255).astype(np.uint8), layout, mask, {"ids": ids, "which": which, "normal": nrm,
                                                                              "depth": depth}


def landmarks(scene, max_dist=5.0):
    """The test area's landmarks (v1's landmark cards) with the building each stands in (or the nearest within
    max_dist m): the list B paints as portraits."""
    import shapely
    from shapely.geometry import Point, Polygon
    fps = []
    for i, b in enumerate(scene.buildings):
        for poly in b.get("footprint") or []:              # a list of polygons, each [outer ring, holes...]
            if poly and len(poly[0]) >= 4:
                fps.append((i, Polygon(poly[0], poly[1:])))
    out, seen = [], set()
    for p in scene.places:
        if p.get("source") != "landmark":
            continue
        e, n = p.get("e"), p.get("n")
        if e is None or not shapely.contains_xy(scene.polygon, e, n) or p.get("name") in seen:
            continue
        seen.add(p.get("name"))
        best = None
        for i, poly in fps:
            d = poly.distance(Point(e, n))
            if d <= max_dist and (best is None or d < best[1]):
                best = (i, d)
        out.append({"name": p.get("name"), "e": round(e, 1), "n": round(n, 1),
                    "building": None if best is None else scene.buildings[best[0]]["id"],
                    "building_index": None if best is None else best[0]})
    return out


def write_window(folder: Path, name, rgb, layout, mask, meta, extra=None):
    folder.mkdir(parents=True, exist_ok=True)
    if extra is not None:
        np.savez_compressed(folder / f"{name}.geom.npz", ids=extra["ids"], which=extra["which"],
                            normal=extra["normal"].astype(np.float16),
                            depth=np.where(np.isfinite(extra["depth"]), extra["depth"], 1e9).astype(np.float32))
    Image.fromarray(rgb).save(folder / f"{name}.unlit.png")
    Image.fromarray(layout).save(folder / f"{name}.layout.png")
    Image.fromarray((mask * 255).astype(np.uint8)).save(folder / f"{name}.mask.png")
    (folder / f"{name}.json").write_text(json.dumps(meta))
