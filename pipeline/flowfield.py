"""The render -> painting displacement field (pipeline/flow_field.py writes it): load it and move points and rasters
through it.

A painted block was painted from the 3D render of the same area, and the painter did not keep every pixel where the
render had it: a feature at map px x in the render is at x + D(x) in the painted map. D is stored on a grid every
STEP map px over the whole map (data/work/flowfit/field.npz: dx, dy float32 (rows, cols), the grid point (i, j) at map
px (j * STEP, i * STEP); conf, how much the painting itself said there, 0..1; owner, the painted block on top).
Outside the painted blocks D is 0 (the render shows there).

  Field.load()              the field, or None when flow_field.py has not run
  F.at(P)                   D at map px points P (n, 2), bilinear
  F.move(P)                 P + D(P): where the painting has what the render has at P
  F.pull(shape, cell)       for a raster of `shape` cells of `cell` map px in render positions: per output cell, the
                            source cell (map_x, map_y float32 for cv2.remap), so out(y) = in(y - D(y)) puts it where
                            the painting is (D is smooth, so y - D(y) inverts y = x + D(x) to well under a px)
  F.warp(grid, cell, nearest=True)  that remap applied to a 2D (or HxWxC) raster
"""
import json

import cv2
import numpy as np

from common import WORK

FLOWFIT = WORK / "flowfit"
STEP = 8


class Field:
    def __init__(self, dx, dy, conf=None, owner=None, meta=None):
        self.dx, self.dy, self.conf, self.owner, self.meta = dx, dy, conf, owner, meta or {}

    @classmethod
    def load(cls, layer="ground", path=FLOWFIT / "field.npz"):
        """layer: "ground" (terrain and bridge decks: roads, rails, water) or "built" (walls and roofs)."""
        if not path.exists():
            return None
        z = np.load(path)
        meta = json.loads(str(z["meta"])) if "meta" in z else {}
        return cls(z[f"{layer}_dx"], z[f"{layer}_dy"], z[f"{layer}_conf"], z["owner"], meta)

    def at(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 2)
        if not len(P):
            return np.zeros((0, 2))
        gx, gy = P[:, 0] / STEP, P[:, 1] / STEP
        out = np.empty((len(P), 2))
        mx = gx.astype(np.float32).reshape(1, -1)
        my = gy.astype(np.float32).reshape(1, -1)
        for k, a in enumerate((self.dx, self.dy)):
            # in chunks: remap takes at most 32767 columns
            v = np.empty(len(P), np.float32)
            for s in range(0, len(P), 30000):
                v[s:s + 30000] = cv2.remap(a, mx[:, s:s + 30000], my[:, s:s + 30000], cv2.INTER_LINEAR,
                                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)[0]
            out[:, k] = v
        return out

    def move(self, P):
        P = np.asarray(P, np.float64).reshape(-1, 2)
        return P + self.at(P)

    def pull(self, shape, cell, y0=0, x0=0):
        """Source coordinates (in cells) for every cell of a raster of `shape` starting at cell (y0, x0)."""
        H, W = shape
        xs = (np.arange(W, dtype=np.float32) + x0 + 0.5) * cell        # cell centres, map px
        ys = (np.arange(H, dtype=np.float32) + y0 + 0.5) * cell
        # D at the cell centres, by resizing the field grid
        mx = np.broadcast_to(xs[None, :] / STEP, (H, W)).astype(np.float32)
        my = np.broadcast_to(ys[:, None] / STEP, (H, W)).astype(np.float32)
        out = []
        for a in (self.dx, self.dy):
            out.append(np.empty((H, W), np.float32))
            for s in range(0, W, 30000):
                out[-1][:, s:s + 30000] = cv2.remap(a, mx[:, s:s + 30000], my[:, s:s + 30000], cv2.INTER_LINEAR,
                                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        sx = (xs[None, :] - out[0]) / cell - 0.5 - x0
        sy = (ys[:, None] - out[1]) / cell - 0.5 - y0
        return sx.astype(np.float32), sy.astype(np.float32)

    def warp(self, grid, cell, nearest=True, y0=0, x0=0):
        """grid (cells of `cell` map px, in render positions; its cell (0, 0) at cell (y0, x0) of the map) moved to
        where the painting has it. Strips of rows keep memory down."""
        H, W = grid.shape[:2]
        out = np.empty_like(grid)
        interp = cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR
        band = max(1, 4_000_000 // max(W, 1))
        pad = int(np.ceil(max(np.abs(self.dx).max(), np.abs(self.dy).max()) / cell)) + 2
        for r0 in range(0, H, band):
            r1 = min(H, r0 + band)
            sx, sy = self.pull((r1 - r0, W), cell, y0 + r0, x0)
            s0, s1 = max(0, r0 - pad), min(H, r1 + pad)
            src = grid[s0:s1]
            for c0 in range(0, W, 30000):
                c1 = min(W, c0 + 30000)
                out[r0:r1, c0:c1] = cv2.remap(src, sx[:, c0:c1], sy[:, c0:c1] - s0, interp,
                                              borderMode=cv2.BORDER_REPLICATE)
        return out
