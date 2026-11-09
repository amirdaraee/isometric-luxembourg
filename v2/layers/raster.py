"""Rendering primitives for the code layers: every one casts the view ray through each pixel centre.

terrain_scan    a height field seen through the camera, one screen column at a time: along a column the visible
                point at screen height Y is the first (nearest) sample whose screen height reaches Y, found with a
                running maximum and a binary search (exact up to the sample spacing, then interpolated)
raster_tris     triangles with a depth buffer (orthographic, so depth is linear in the pixel), vectorised by
                triangle size
raster_ellipsoids  vertical spheroids (tree crowns) by solving each pixel's ray against them

All take zoom-0 map pixel centres of a Tile and return per-pixel depth (m, inf where empty) and what was hit.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from v2.layers.common import C30, R2, S30, RIGHT, UP, VIEW, cam


class HeightField:
    """A height grid (row 0 south, cell centres, as v2.data.scene.grid.Grid) with bilinear sampling of z and
    its gradient."""

    def __init__(self, z, e0, n0, step):
        self.z = np.asarray(z, np.float32)
        self.e0, self.n0, self.step = float(e0), float(n0), float(step)
        gy, gx = np.gradient(self.z.astype(np.float64), self.step)
        self.gx, self.gy = gx.astype(np.float32), gy.astype(np.float32)

    def ij(self, e, n):
        return (np.asarray(n) - self.n0) / self.step - 0.5, (np.asarray(e) - self.e0) / self.step - 0.5

    def inside(self, e, n):
        h, w = self.z.shape
        i, j = self.ij(e, n)
        return (i >= -0.5) & (i <= h - 0.5) & (j >= -0.5) & (j <= w - 0.5)

    def sample(self, e, n, what="z"):
        i, j = self.ij(e, n)
        a = {"z": self.z, "gx": self.gx, "gy": self.gy}[what]
        return ndimage.map_coordinates(a, [np.ravel(i), np.ravel(j)], order=1, mode="nearest",
                                       prefilter=False).reshape(np.shape(i))

    def curvature(self, e, n):
        """Second derivative of the bilinear surface along a screen column (d2z/df2: -cross term / step^2)."""
        if not hasattr(self, "_cross"):
            z = self.z.astype(np.float64)
            self._cross = (z[:-1, :-1] - z[:-1, 1:] - z[1:, :-1] + z[1:, 1:])
        i, j = self.ij(e, n)
        h, w = self._cross.shape
        ii = np.clip(np.floor(i).astype(np.int64), 0, h - 1)
        jj = np.clip(np.floor(j).astype(np.int64), 0, w - 1)
        return -self._cross[ii, jj] / (self.step * self.step)

    def normal(self, e, n):
        gx, gy = self.sample(e, n, "gx"), self.sample(e, n, "gy")
        v = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        return v / np.linalg.norm(v, axis=-1, keepdims=True)


def column_frame(tile):
    """u (screen metres) of each column and sy of each row of a tile's pixel centres."""
    c = cam()
    px, py = tile.centres
    return c["frame"]["sx0"] + px * c["mpp"], c["frame"]["sy1"] - py * c["mpp"]


def terrain_scan(hf: HeightField, tile, zmin, zmax, df=0.125):
    """The height field as seen in a tile. Returns dict: hit (bool), e, n, z, depth (inf where no terrain), f.

    Along a screen column the terrain is sampled every df metres of f, and also where the column crosses a grid line
    of the height field (the bilinear surface has a crease there) and at the top of each step's parabola (between
    creases the surface along a column is a parabola). So each step's highest screen point is exact: a ridge whose
    crest lies between two samples is not missed. A pixel's crossing is solved on these points."""
    c = cam()
    oe, on = c["origin_en"]
    u, sy = column_frame(tile)
    H, W = len(sy), len(u)
    f_lo = (sy.min() - zmax * C30) / S30 - 1.0
    f_hi = (sy.max() - zmin * C30) / S30 + 1.0
    fs = np.arange(f_lo, f_hi + df, df)
    N = len(fs)
    U = u[:, None]
    F = fs[None, :]

    def at(f):
        E, Nn = oe + (U - f) * R2, on + (U + f) * R2
        zz = hf.sample(E, Nn)
        return zz, hf.inside(E, Nn), f * S30 + zz * C30

    z, ok, s = at(F)
    low = sy.min() - 1e3
    s = np.where(ok, s, low)
    # extra points inside each step k (samples k-1, k): the crossings of the grid lines, the parabola's top
    E0, N0 = oe + (U - F) * R2, on + (U + F) * R2
    gi, gj = hf.ij(E0, N0)
    pts = []
    for g in (gi, gj):
        a0, a1 = g[:, :-1], g[:, 1:]
        lo_, hi_ = np.minimum(a0, a1), np.maximum(a0, a1)
        line = np.floor(hi_)
        has = line > lo_
        t = np.where(has, (line - a0) / np.where(np.abs(a1 - a0) > 1e-12, a1 - a0, 1.0), 0.0)
        pts.append(np.where(has, np.clip(t, 0, 1), 0.0))
    kap = hf.curvature(oe + (U - F[:, :-1] - df / 2) * R2, on + (U + F[:, :-1] + df / 2) * R2)
    a2 = C30 * kap * df * df / 2
    s0, s1 = s[:, :-1], s[:, 1:]
    tv = np.where(a2 < -1e-12, (a2 - (s1 - s0)) / np.where(a2 < -1e-12, 2 * a2, 1.0), 0.0)
    pts.append(np.clip(tv, 0, 1))
    extra_s = []
    for t in pts:
        _, okx, sx_ = at(F[:, :-1] + t * df)
        extra_s.append(np.where(okx, sx_, low))
    smax = np.maximum(s0, s1)
    for es in extra_s:
        smax = np.maximum(smax, es)
    smax = np.concatenate([s[:, :1], smax], axis=1)          # step 0 is the first sample itself
    M = np.maximum.accumulate(smax, axis=1)
    BIG = 1e5
    off = (np.arange(W) * BIG)[:, None]
    Mg = (M - low + off).ravel()
    Y = (sy[None, :] - low + off)                       # (W, H)
    k = np.searchsorted(Mg, Y.ravel(), side="left").reshape(W, H) - np.arange(W)[:, None] * N
    hit = (k >= 1) & (k < N)
    kk = np.clip(k, 1, N - 1)
    col = np.arange(W)[:, None]
    # the crossing inside step kk: through its points in order of t, the first where s reaches Y
    T = np.stack([np.zeros(kk.shape)] + [p[col, kk - 1] for p in pts] + [np.ones(kk.shape)], -1)
    Sv = np.stack([s[col, kk - 1]] + [es[col, kk - 1] for es in extra_s] + [s[col, kk]], -1)
    o = np.argsort(T, axis=-1)
    T = np.take_along_axis(T, o, -1)
    Sv = np.take_along_axis(Sv, o, -1)
    Yr = np.broadcast_to(sy[None, :], kk.shape)
    reach = Sv >= Yr[..., None]
    first = np.argmax(reach, axis=-1)
    fi = np.clip(first, 1, Sv.shape[-1] - 1)
    sa = np.take_along_axis(Sv, (fi - 1)[..., None], -1)[..., 0]
    sb = np.take_along_axis(Sv, fi[..., None], -1)[..., 0]
    ta = np.take_along_axis(T, (fi - 1)[..., None], -1)[..., 0]
    tb = np.take_along_axis(T, fi[..., None], -1)[..., 0]
    w = np.where(sb > sa, (Yr - sa) / np.maximum(sb - sa, 1e-12), 1.0)
    t = np.where(first == 0, 0.0, ta + np.clip(w, 0, 1) * (tb - ta))
    fsol = fs[kk - 1] + t * df
    E1, N1 = oe + (u[:, None] - fsol) * R2, on + (u[:, None] + fsol) * R2
    zz = hf.sample(E1, N1)
    okc = hf.inside(E1, N1)
    hit &= okc & reach.any(-1)
    # transpose to (rows, cols); the view ray fixes (u, sy): recompute f from z exactly on the ray
    hit = hit.T
    zz = zz.T
    f = ((sy[:, None] - zz * C30) / S30)
    e = oe + (u[None, :] - f) * R2
    n = on + (u[None, :] + f) * R2
    depth = np.where(hit, f * C30 - zz * S30, np.inf)
    return {"hit": hit, "e": e, "n": n, "z": zz, "f": f, "u": np.broadcast_to(u[None, :], hit.shape), "depth": depth}


# ------------------------------------------------------------------------------------------------ triangles
def raster_tris(P, D, tris, W, H, zbuf, tbuf, tri_offset=0, bias=None, max_cand=3_000_000):
    """Rasterise triangles into a depth buffer (in place).

    P: (V, 2) pixel coordinates in the buffer's frame (pixel i covers [i, i + 1), centre i + 0.5); D: (V,) depth;
    tris: (T, 3) vertex indices; zbuf: (H, W) float (inf = empty); tbuf: (H, W) int (-1 = empty) receives
    tri_offset + triangle index. bias: optional per-triangle depth added (negative = pulled nearer) for decals."""
    if len(tris) == 0:
        return
    x = P[tris, 0]
    y = P[tris, 1]
    d = D[tris]
    ix0 = np.ceil(x.min(1) - 0.5).astype(np.int64)
    ix1 = np.floor(x.max(1) - 0.5).astype(np.int64)
    iy0 = np.ceil(y.min(1) - 0.5).astype(np.int64)
    iy1 = np.floor(y.max(1) - 0.5).astype(np.int64)
    ix0 = np.maximum(ix0, 0); iy0 = np.maximum(iy0, 0)
    ix1 = np.minimum(ix1, W - 1); iy1 = np.minimum(iy1, H - 1)
    area = (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    keep = (ix0 <= ix1) & (iy0 <= iy1) & (np.abs(area) > 1e-9)
    idx = np.flatnonzero(keep)
    if not len(idx):
        return
    bw = ix1[idx] - ix0[idx] + 1
    bh = iy1[idx] - iy0[idx] + 1
    order = np.lexsort((bh, bw))
    idx, bw, bh = idx[order], bw[order], bh[order]
    i = 0
    n = len(idx)
    while i < n:
        # a chunk of similar triangles whose bounding boxes together stay under max_cand candidate pixels
        j = i + 1
        mw, mh = bw[i], bh[i]
        while j < n:
            nw, nh = max(mw, bw[j]), max(mh, bh[j])
            if (j - i + 1) * nw * nh > max_cand:
                break
            mw, mh = nw, nh
            j += 1
        sel = idx[i:j]
        oy, ox = np.mgrid[0:mh, 0:mw]
        cx = ix0[sel][:, None, None] + ox[None] + 0.5
        cy = iy0[sel][:, None, None] + oy[None] + 0.5
        inb = (cx < ix1[sel][:, None, None] + 1) & (cy < iy1[sel][:, None, None] + 1)
        X = x[sel][:, :, None, None]
        Y = y[sel][:, :, None, None]
        A = area[sel][:, None, None]
        w0 = ((X[:, 1] - cx) * (Y[:, 2] - cy) - (X[:, 2] - cx) * (Y[:, 1] - cy)) / A
        w1 = ((X[:, 2] - cx) * (Y[:, 0] - cy) - (X[:, 0] - cx) * (Y[:, 2] - cy)) / A
        w2 = 1 - w0 - w1
        eps = -1e-9
        inside = inb & (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        dd = d[sel]
        dep = w0 * dd[:, 0, None, None] + w1 * dd[:, 1, None, None] + w2 * dd[:, 2, None, None]
        if bias is not None:
            dep = dep + bias[sel][:, None, None]
        t_i, r_i, c_i = np.nonzero(inside)
        if len(t_i):
            pix = (cy[t_i, r_i, c_i] - 0.5).astype(np.int64) * W + (cx[t_i, r_i, c_i] - 0.5).astype(np.int64)
            dv = dep[t_i, r_i, c_i]
            tv = sel[t_i] + tri_offset
            o = np.lexsort((dv, pix))
            pix, dv, tv = pix[o], dv[o], tv[o]
            first = np.r_[True, pix[1:] != pix[:-1]]
            pix, dv, tv = pix[first], dv[first], tv[first]
            zf = zbuf.reshape(-1)
            tf = tbuf.reshape(-1)
            better = dv < zf[pix]
            zf[pix[better]] = dv[better]
            tf[pix[better]] = tv[better]
        i = j


def bary(P, tris, tri_idx, cx, cy):
    """Barycentric weights of pixel centres (cx, cy) in triangles tri_idx."""
    a, b, c = P[tris[tri_idx, 0]], P[tris[tri_idx, 1]], P[tris[tri_idx, 2]]
    A = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])
    w0 = ((b[:, 0] - cx) * (c[:, 1] - cy) - (c[:, 0] - cx) * (b[:, 1] - cy)) / A
    w1 = ((c[:, 0] - cx) * (a[:, 1] - cy) - (a[:, 0] - cx) * (c[:, 1] - cy)) / A
    return np.stack([w0, w1, 1 - w0 - w1], -1)


# ------------------------------------------------------------------------------------------------ ellipsoids
def raster_ellipsoids(C, r, b, tile, zbuf, ibuf, nbuf=None, max_cand=3_000_000):
    """Vertical spheroids: centres C (k, 3) world (E, N, z), horizontal radius r, vertical semi-axis b.

    Fills zbuf (depth), ibuf (index) and nbuf (world normal, (H, W, 3)) where a spheroid is nearer."""
    from v2.layers.common import project
    if len(C) == 0:
        return
    c = cam()
    px, py, dc = project(C[:, 0], C[:, 1], C[:, 2])
    # screen half-extents of a spheroid: projection of its axes
    hx = r * 1.0 / c["mpp"]                                   # horizontal extent along screen x
    hy = np.sqrt((r * S30) ** 2 + (b * C30) ** 2) / c["mpp"]  # vertical extent
    H = W = tile.size
    lx = px - tile.px0
    ly = py - tile.py0
    ix0 = np.maximum(np.ceil(lx - hx - 0.5), 0).astype(np.int64)
    ix1 = np.minimum(np.floor(lx + hx - 0.5), W - 1).astype(np.int64)
    iy0 = np.maximum(np.ceil(ly - hy - 0.5), 0).astype(np.int64)
    iy1 = np.minimum(np.floor(ly + hy - 0.5), H - 1).astype(np.int64)
    keep = np.flatnonzero((ix0 <= ix1) & (iy0 <= iy1))
    if not len(keep):
        return
    # rows of the world-offset transform: world = RIGHT * X + UP * Y + VIEW * t (screen metres)
    M = np.stack([RIGHT, UP, VIEW], 1)                       # (3, 3): columns are the screen axes in world
    bw = ix1[keep] - ix0[keep] + 1
    bh = iy1[keep] - iy0[keep] + 1
    order = np.lexsort((bh, bw))
    keep, bw, bh = keep[order], bw[order], bh[order]
    i, n = 0, len(keep)
    mpp = c["mpp"]
    while i < n:
        j = i + 1
        mw, mh = bw[i], bh[i]
        while j < n:
            nw, nh = max(mw, bw[j]), max(mh, bh[j])
            if (j - i + 1) * nw * nh > max_cand:
                break
            mw, mh = nw, nh
            j += 1
        sel = keep[i:j]
        oy, ox = np.mgrid[0:mh, 0:mw]
        cx = ix0[sel][:, None, None] + ox[None] + 0.5
        cy = iy0[sel][:, None, None] + oy[None] + 0.5
        inb = (cx < ix1[sel][:, None, None] + 1) & (cy < iy1[sel][:, None, None] + 1)
        X = (cx - lx[sel][:, None, None]) * mpp               # screen metres from the centre
        Y = -(cy - ly[sel][:, None, None]) * mpp
        rr = r[sel][:, None, None]
        bb = b[sel][:, None, None]
        # world offset w = M @ (X, Y, t); quadratic in t of sum (w_i / s_i)^2 = 1
        s2 = [rr ** 2, rr ** 2, bb ** 2]
        qa = sum(M[k, 2] ** 2 / s2[k] for k in range(3))
        qb = sum(2 * M[k, 2] * (M[k, 0] * X + M[k, 1] * Y) / s2[k] for k in range(3))
        qc = sum((M[k, 0] * X + M[k, 1] * Y) ** 2 / s2[k] for k in range(3)) - 1
        disc = qb * qb - 4 * qa * qc
        hitm = inb & (disc >= 0)
        t = (-qb - np.sqrt(np.maximum(disc, 0))) / (2 * qa)
        dep = dc[sel][:, None, None] + t
        t_i, r_i, c_i = np.nonzero(hitm)
        if len(t_i):
            pix = (cy[t_i, r_i, c_i] - 0.5).astype(np.int64) * W + (cx[t_i, r_i, c_i] - 0.5).astype(np.int64)
            dv = dep[t_i, r_i, c_i]
            o = np.lexsort((dv, pix))
            first = np.r_[True, pix[o][1:] != pix[o][:-1]]
            o = o[first]
            pix, dv = pix[o], dv[o]
            ti, ri, ci = t_i[o], r_i[o], c_i[o]
            zf = zbuf.reshape(-1)
            better = dv < zf[pix]
            pix, dv = pix[better], dv[better]
            ti, ri, ci = ti[better], ri[better], ci[better]
            zf[pix] = dv
            ibuf.reshape(-1)[pix] = sel[ti]
            if nbuf is not None:
                Xs, Ys, ts = X[ti, ri, ci], Y[ti, ri, ci], t[ti, ri, ci]
                w = (M[:, 0][None] * Xs[:, None] + M[:, 1][None] * Ys[:, None] + M[:, 2][None] * ts[:, None])
                g = w / np.stack([rr[ti, 0, 0] ** 2, rr[ti, 0, 0] ** 2, bb[ti, 0, 0] ** 2], 1)
                g /= np.linalg.norm(g, axis=1, keepdims=True)
                nbuf.reshape(-1, 3)[pix] = g
        i = j
