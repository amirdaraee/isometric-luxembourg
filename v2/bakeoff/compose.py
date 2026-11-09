"""Painted inputs back into layer tiles (methods B and C). Geometry, depth, normals and ids always come from the
scene's meshes (method A's / Phase 1's rasteriser); only the colour comes from the paintings, cut to the mesh's
coverage. Nothing is warped or moved: a painting that does not fit fails its checks and is repainted (brief 1).

C: each window's painting (painted/<x0>_<y0>.png, 1024 px over the map pixels it was rendered from) is sampled at the
   pixel, windows blended where they overlap by a tent weight (1 at a window's centre, falling to 0 at its edge), and
   kept only where layer 5 (or 6) covers, grown by <= 2 px (the POC cut rule, L5.3).
B: method A's render, with each generated pattern replaced by its material image (materials/<name>.png, picked by
   the owner): walls, roofs, windows, doors and shop fronts sampled at the pixel's place on its surface (the same
   coordinates A uses); landmark portraits (landmarks/<building>.png, painted from that building's unlit crop)
   replace that building's pixels, cut to its mesh.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from v2.layers.common import TILE

WIN = 1024


@lru_cache(maxsize=None)
def _windows(folder: str):
    d = Path(folder)
    out = []
    for p in sorted(d.glob("*.png")):
        x0, y0 = (int(v) for v in p.stem.split("_")[:2])
        out.append((x0, y0, p))
    return out


@lru_cache(maxsize=8)
def _img(path: str):
    return np.asarray(Image.open(path).convert("RGB"), np.float64)


def tent(n):
    t = 1 - np.abs((np.arange(n) + 0.5) / n * 2 - 1)
    return np.maximum(t, 1e-3)


def painted_rgb(folder: Path, px0, py0, W, H):
    """The blended painting over map pixels [px0, px0 + W) x [py0, py0 + H); weight 0 where nothing is painted."""
    acc = np.zeros((H, W, 3)); wsum = np.zeros((H, W))
    tw = tent(WIN)
    for x0, y0, p in _windows(str(folder)):
        a0, b0, a1, b1 = max(px0, x0), max(py0, y0), min(px0 + W, x0 + WIN), min(py0 + H, y0 + WIN)
        if a1 <= a0 or b1 <= b0:
            continue
        img = _img(str(p))
        sub = img[b0 - y0:b1 - y0, a0 - x0:a1 - x0]
        w = np.outer(tw[b0 - y0:b1 - y0], tw[a0 - x0:a1 - x0])
        acc[b0 - py0:b1 - py0, a0 - px0:a1 - px0] += sub * w[..., None]
        wsum[b0 - py0:b1 - py0, a0 - px0:a1 - px0] += w
    out = np.where(wsum[..., None] > 0, acc / np.maximum(wsum, 1e-9)[..., None], 0)
    return out, wsum > 0


def layer(R, method, layer_name, tile, folder: Path):
    from v2.layers.bakeoff import cut_to
    from v2.layers.render import Renderer
    plain = Renderer(R.scene, R.ground_osm_path, R.transport_osm_path, frozenset(R.omit), art="a" if method == "b" else "plain")
    base = plain.layer(layer_name, tile)
    if method == "c":
        sub = folder / ("painted" if layer_name != "trees" else "canopy")
        if not sub.exists():
            return base                          # C's trees: code crowns unless a canopy was painted
        rgb, has = painted_rgb(sub, tile.px0, tile.py0, tile.size, tile.size)
        mask = np.isfinite(base.depth)
        cut, keep = cut_to(mask, rgb, grow=0)    # colour only where the mesh is; the outline is the mesh's
        use = mask & has
        out_rgb = base.rgb.copy()
        out_rgb[use] = np.clip(np.round(cut[use]), 0, 255).astype(np.uint8)
        base.rgb = out_rgb
        return base
    if method == "b":
        if layer_name != "buildings":
            return base
        lm = folder / "landmarks"
        picks = json.loads((folder / "picked.json").read_text()) if (folder / "picked.json").exists() else {}
        out_rgb = base.rgb.copy()
        bidx = base.ids >> 8
        for bid, info in picks.get("landmarks", {}).items():
            bi = int(info["building_index"])
            m = (bidx == bi) & np.isfinite(base.depth)
            if not m.any():
                continue
            img = _img(str(lm / info["file"]))
            x0, y0 = info["x0"], info["y0"]
            rr, cc = np.nonzero(m)
            X, Y = cc + tile.px0 - x0, rr + tile.py0 - y0
            ok = (X >= 0) & (Y >= 0) & (X < img.shape[1]) & (Y < img.shape[0])
            out_rgb[rr[ok], cc[ok]] = np.clip(np.round(img[Y[ok], X[ok]]), 0, 255).astype(np.uint8)
        base.rgb = out_rgb
        return base
    raise ValueError(method)
