"""A regular height grid in LUREF metres (terrain, surface), with bilinear sampling."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage


class Grid:
    """z[i, j] is the value at the centre of cell (e0 + (j + 0.5) step, n0 + (i + 0.5) step); row 0 is south."""

    def __init__(self, z: np.ndarray, e0: float, n0: float, step: float):
        self.z, self.e0, self.n0, self.step = z, float(e0), float(n0), float(step)

    @classmethod
    def load(cls, path: Path, name: str = "mnt") -> "Grid":
        d = np.load(path)
        return cls(d[name], d["e0"], d["n0"], d["step"])

    @property
    def shape(self):
        return self.z.shape

    def bounds(self):
        h, w = self.z.shape
        return self.e0, self.n0, self.e0 + w * self.step, self.n0 + h * self.step

    def ij(self, e, n):
        return ((np.asarray(n, float) - self.n0) / self.step - 0.5, (np.asarray(e, float) - self.e0) / self.step - 0.5)

    def inside(self, e, n):
        x0, y0, x1, y1 = self.bounds()
        e, n = np.asarray(e, float), np.asarray(n, float)
        return (e >= x0) & (e < x1) & (n >= y0) & (n < y1)

    def sample(self, e, n, order: int = 1):
        """Bilinear (order 1) or nearest (0) values; NaN outside the grid or where the grid has no data."""
        i, j = self.ij(e, n)
        shape = np.shape(i)
        i, j = np.atleast_1d(i).ravel(), np.atleast_1d(j).ravel()
        if not hasattr(self, "_zz"):
            valid = np.isfinite(self.z)
            self._zz = np.where(valid, self.z, 0.0).astype(np.float32)
            self._valid = valid.astype(np.float32)
        v = ndimage.map_coordinates(self._zz, [i, j], order=order, mode="nearest", prefilter=False)
        w = ndimage.map_coordinates(self._valid, [i, j], order=order, mode="nearest", prefilter=False)
        out = np.where(w > 0.999, v, np.nan)
        out[~self.inside(*self._en(i, j))] = np.nan
        return out.reshape(shape) if shape else float(out[0])

    def _en(self, i, j):
        return self.e0 + (j + 0.5) * self.step, self.n0 + (i + 0.5) * self.step

    def cell_centres(self):
        h, w = self.z.shape
        e = self.e0 + (np.arange(w) + 0.5) * self.step
        n = self.n0 + (np.arange(h) + 0.5) * self.step
        return e, n


def soft_mask(mask, sigma_cells: float) -> np.ndarray:
    """A yes/no grid as a smooth field (0..1). Read between the cells (read_soft) and cut at a half, an area's border
    is a smooth line and not the grid's staircase, which shows as saw teeth in the picture. The field is the grid
    smoothed over sigma_cells; a part narrower than three cells would be smoothed away, so it keeps its cells."""
    mask = np.asarray(mask, bool)
    f = ndimage.gaussian_filter(mask.astype(np.float32), sigma_cells) if sigma_cells > 0 else mask.astype(np.float32)
    thin = mask & ~ndimage.binary_opening(mask, structure=np.ones((3, 3), bool))
    return np.maximum(f, thin.astype(np.float32))


def read_soft(field: np.ndarray, i, j) -> np.ndarray:
    """Whether a soft_mask field is a half or more at grid places (i, j), which need not be whole; False off the
    grid. A place has one answer whoever asks, so tiles agree."""
    i, j = np.nan_to_num(np.asarray(i, float)), np.nan_to_num(np.asarray(j, float))
    v = ndimage.map_coordinates(field, [i.ravel(), j.ravel()], order=1, mode="constant", cval=0.0, prefilter=False)
    return (v >= 0.5).reshape(i.shape)
