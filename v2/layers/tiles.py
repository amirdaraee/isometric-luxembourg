"""Writing a layer's tile set: zoom 0 from the renderer (in parallel), then the zoom pyramid, then index.json.

Zoom z > 0 is made from the four tiles of zoom z - 1 below it: colour by the mean of the pixels that hold something,
the geometry (depth, normal, class, ids) from the nearest of the four pixels, never averaged (layer-08-buffers.md).
"""
from __future__ import annotations

import json
import math
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from v2.layers.common import EMPTY, TILE, Tile, pack_bin, read_tile, unpack_bin, write_tile

_R = None


def _init(scene_folder, ground_osm, transport_osm, omit):
    global _R
    from v2.layers.common import Scene
    from v2.layers.render import Renderer
    _R = Renderer(Scene(Path(scene_folder)), Path(ground_osm) if ground_osm else None,
                  Path(transport_osm) if transport_osm else None, frozenset(omit))


def _render_one(args):
    fn, tile, folder, q = args
    out = fn(_R, tile)
    if out is None:
        return tile.name, None
    return tile.name, out(folder, tile, q)


def run_tiles(scene_folder, ground_osm, transport_osm, tiles, job, folder, q=90, workers=2, omit=()):
    """Run job(renderer, tile) -> writer(folder, tile, q) -> dmin (or None) over tiles; returns {name: dmin}."""
    folder.mkdir(parents=True, exist_ok=True)
    args = [(job, t, folder, q) for t in tiles]
    out = {}
    if workers <= 1:
        _init(scene_folder, ground_osm, transport_osm, omit)
        for a in args:
            n, d = _render_one(a)
            if d is not None:
                out[n] = d
        return out
    with ProcessPoolExecutor(max_workers=workers, initializer=_init,
                             initargs=(str(scene_folder), str(ground_osm) if ground_osm else None,
                                       str(transport_osm) if transport_osm else None, tuple(omit))) as ex:
        for n, d in ex.map(_render_one, args, chunksize=4):
            if d is not None:
                out[n] = d
    return out


def layer_writer(name, lossless=False):
    """A job for run_tiles drawing one colour layer."""
    return _LayerJob(name, lossless)


class _LayerJob:
    def __init__(self, name, lossless):
        self.name, self.lossless = name, lossless

    def __call__(self, R, tile):
        L = R.layer(self.name, tile)
        if not np.isfinite(L.depth).any():
            return None
        c = tile.crop
        rgb, depth, normal = c(L.rgb), c(L.depth), c(L.normal)
        k = c(L.k) if L.k is not None else None
        ids = c(L.ids) if (L.ids is not None and self.name in ("transport", "buildings", "structures", "trees")) else None
        if not np.isfinite(depth).any():
            return None

        def write(folder, tile, q):
            return write_tile(folder, tile.name, rgb=rgb, depth=depth, normal=normal, k=k, ids=ids,
                              q=101 if self.lossless else q)
        return write


# ------------------------------------------------------------------------------------------------ pyramid
def pyramid(folder: Path, index0: dict, levels: int, lossless=False, q=90, has_k=True, has_ids=False,
            has_h=False):
    """Build zoom 1..levels from zoom 0 in folder/0. Returns {z: {name: dmin}}."""
    from PIL import Image
    idx = {0: dict(index0)}
    for z in range(1, levels + 1):
        prev = idx[z - 1]
        parents = sorted({(int(n.split("_")[0]) >> 1, int(n.split("_")[1]) >> 1) for n in prev})
        out = {}
        src, dst = folder / str(z - 1), folder / str(z)
        dst.mkdir(parents=True, exist_ok=True)
        for (px, py) in parents:
            big = {"rgb": np.zeros((2 * TILE, 2 * TILE, 3)), "depth": np.full((2 * TILE, 2 * TILE), np.inf),
                   "oct": np.zeros((2 * TILE, 2 * TILE, 2), np.uint8), "k": np.zeros((2 * TILE, 2 * TILE), np.uint8),
                   "ids": np.zeros((2 * TILE, 2 * TILE), np.uint32), "h": np.zeros((2 * TILE, 2 * TILE), np.uint16)}
            for dy in (0, 1):
                for dx in (0, 1):
                    n = f"{2 * px + dx}_{2 * py + dy}"
                    if n not in prev:
                        continue
                    t = read_tile(src, n, prev[n], z=z - 1)
                    sl = (slice(dy * TILE, (dy + 1) * TILE), slice(dx * TILE, (dx + 1) * TILE))
                    if "rgb" in t:
                        big["rgb"][sl] = t["rgb"]
                    big["depth"][sl] = t["depth"]
                    big["oct"][sl] = t["oct"]
                    if "k" in t:
                        big["k"][sl] = t["k"]
                    if "ids" in t:
                        big["ids"][sl] = t["ids"]
                    hp = src / f"{n}.h.bin"
                    if hp.exists():
                        big["h"][sl] = unpack_bin(hp.read_bytes(), (TILE, TILE), np.uint16)
            d4 = big["depth"].reshape(TILE, 2, TILE, 2).transpose(0, 2, 1, 3).reshape(TILE, TILE, 4)
            arg = np.argmin(d4, axis=2)
            dmin = np.take_along_axis(d4, arg[..., None], 2)[..., 0]
            if not np.isfinite(dmin).any():
                continue

            def pick(a):
                s = a.shape[2:] if a.ndim > 2 else ()
                a4 = a.reshape((TILE, 2, TILE, 2) + s).swapaxes(1, 2).reshape((TILE, TILE, 4) + s)
                return np.take_along_axis(a4, arg.reshape(TILE, TILE, 1, *([1] * len(s))), 2)[:, :, 0]
            valid = np.isfinite(big["depth"]).astype(float)
            v4 = valid.reshape(TILE, 2, TILE, 2).sum((1, 3))
            rgb = (big["rgb"] * valid[..., None]).reshape(TILE, 2, TILE, 2, 3).sum((1, 3)) / np.maximum(v4, 1)[..., None]
            from v2.layers.common import oct_decode
            name = f"{px}_{py}"
            dm = write_tile(dst, name, rgb=np.round(rgb).astype(np.uint8), depth=dmin, normal=oct_decode(pick(big["oct"])),
                            k=pick(big["k"]) if has_k else None, ids=pick(big["ids"]) if has_ids else None,
                            q=101 if lossless else q, z=z)
            if has_h:
                (dst / f"{name}.h.bin").write_bytes(pack_bin(pick(big["h"])))
            out[name] = dm
        idx[z] = out
    return idx


def levels_for(tiles) -> int:
    xs = [t.tx for t in tiles]
    ys = [t.ty for t in tiles]
    span = max(max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)
    return max(1, int(math.ceil(math.log2(span))))


def write_index(folder: Path, layer: str, idx: dict, extra=None):
    d = {"layer": layer, "tile_px": TILE, "levels": max(idx), "tiles": {str(z): v for z, v in idx.items()},
         "files": ["c.webp", "g.bin"] + (extra or [])}
    (folder / "index.json").write_text(json.dumps(d, separators=(",", ":")))
    return d
