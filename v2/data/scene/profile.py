"""Height profiles: the lowest-cost height path through sampled heights with the grade capped.

For samples i = 0..n-1, ds metres apart, with observed heights h_i (NaN where nothing is observed), weights w_i,
optional bounds lo_i <= z_i <= hi_i and pinned end heights, the profile minimises

    sum_i w_i |z_i - h_i|  +  prior_w * sum_i |z_i - prior_i|      subject to |z_{i+1} - z_i| <= grade * ds

by dynamic programming over height bins (Pixel Singapore's per-road profile, OTHERS.md section 6 P4.1). The L1
cost ignores outliers (a parked lorry on a bridge deck in the surface model, a wall next to a road in the ground
model), and the grade cap guarantees no jumps. A light moving average then removes the bin steps (it cannot
increase any slope). Returns None when the bounds, the pins and the cap cannot all be met.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import minimum_filter1d


def solve(h, ds, grade, w=None, lo=None, hi=None, z0=None, z1=None, prior=None, prior_w=0.0, bin_m=0.05,
          smooth_n=3, lo_soft=None, hi_soft=None, soft_w=50.0):
    """lo_soft / hi_soft: bounds that cost soft_w per metre of violation instead of forbidding it (a tunnel should be
    under the terrain, a deck above it; where the data cannot meet that, the check reports it)."""
    h = np.asarray(h, float)
    n = len(h)
    if n == 0:
        return np.zeros(0)
    w = np.ones(n) if w is None else np.asarray(w, float)
    lo = np.full(n, -np.inf) if lo is None else np.asarray(lo, float)
    hi = np.full(n, np.inf) if hi is None else np.asarray(hi, float)
    vals = [x for x in (np.nanmin(h) if np.isfinite(h).any() else None, np.nanmax(h) if np.isfinite(h).any() else None,
                        z0, z1) if x is not None and np.isfinite(x)]
    if prior is not None:
        prior = np.asarray(prior, float)
        vals += [float(np.nanmin(prior)), float(np.nanmax(prior))]
    for soft in (lo_soft, hi_soft):
        if soft is not None and np.isfinite(soft).any():
            vals += [float(np.nanmin(soft)), float(np.nanmax(soft))]
    finite_lo = lo[np.isfinite(lo)]; finite_hi = hi[np.isfinite(hi)]
    if finite_lo.size:
        vals.append(float(finite_lo.max()))
    if finite_hi.size:
        vals.append(float(finite_hi.min()))
    if not vals:
        return None
    zmin, zmax = min(vals) - 3.0, max(vals) + 3.0
    bin_m = max(bin_m, (zmax - zmin) / 20000)
    if grade * ds > 0:
        # a whole number k of bins per step, exactly the cap: the cap is never rounded down
        k = max(4, int(math.ceil(grade * ds / bin_m)))
        bin_m = grade * ds / k
    else:
        k = 1
    nb = int(math.ceil((zmax - zmin) / bin_m)) + 1
    zb = zmin + np.arange(nb) * bin_m
    INF = 1e18

    def cost(i):
        c = np.zeros(nb)
        if np.isfinite(h[i]) and w[i] > 0:
            c += w[i] * np.abs(zb - h[i])
        if prior is not None and prior_w > 0 and np.isfinite(prior[i]):
            c += prior_w * np.abs(zb - prior[i])
        if lo_soft is not None and np.isfinite(lo_soft[i]):
            c += soft_w * np.maximum(0.0, lo_soft[i] - zb)
        if hi_soft is not None and np.isfinite(hi_soft[i]):
            c += soft_w * np.maximum(0.0, zb - hi_soft[i])
        c[(zb < lo[i] - 1e-9) | (zb > hi[i] + 1e-9)] = INF
        return c

    D = np.empty((n, nb))
    D[0] = cost(0)
    if z0 is not None and np.isfinite(z0):
        pin = np.full(nb, INF); pin[int(round((z0 - zmin) / bin_m))] = 0
        D[0] = np.minimum(D[0] + pin, INF)
    for i in range(1, n):
        D[i] = np.minimum(cost(i) + minimum_filter1d(D[i - 1], 2 * k + 1, mode="constant", cval=INF), INF)
    if z1 is not None and np.isfinite(z1):
        b = int(round((z1 - zmin) / bin_m))
    else:
        b = int(np.argmin(D[-1]))
    if D[-1][b] >= INF / 2:
        return None
    idx = np.empty(n, int); idx[-1] = b
    for i in range(n - 1, 0, -1):
        a0, a1 = max(0, idx[i] - k), min(nb, idx[i] + k + 1)
        idx[i - 1] = a0 + int(np.argmin(D[i - 1][a0:a1]))
    z = zb[idx]
    if z0 is not None and np.isfinite(z0):
        z[0] = z0
    if z1 is not None and np.isfinite(z1):
        z[-1] = z1
    if smooth_n > 1 and n > 2:
        m = smooth_n
        pad = np.r_[np.full(m // 2, z[0]), z, np.full(m // 2, z[-1])]
        zs = np.convolve(pad, np.ones(m) / m, mode="valid")
        zs[0], zs[-1] = z[0], z[-1]
        z = np.clip(zs, lo, hi) if (np.isfinite(lo).any() or np.isfinite(hi).any()) else zs
    return z


def resample(en: np.ndarray, step: float):
    """Points evenly spaced along a polyline, no more than `step` apart, keeping both ends. Returns (pts, s)."""
    seg = np.hypot(*np.diff(en, axis=0).T)
    cum = np.r_[0, np.cumsum(seg)]
    L = float(cum[-1])
    m = max(1, int(math.ceil(L / step)))
    s = np.linspace(0, L, m + 1)
    e = np.interp(s, cum, en[:, 0]); n = np.interp(s, cum, en[:, 1])
    return np.column_stack((e, n)), s


def normals(pts: np.ndarray):
    d = np.gradient(pts, axis=0) if len(pts) > 1 else np.array([[1.0, 0.0]])
    L = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)
    return np.column_stack((-d[:, 1] / L, d[:, 0] / L))
