"""Geometry shared by fit_roads.py and build_transit.py (numpy and scipy only, so the monthly timetable build can use
it): densifying polylines the way fit_roads.py does, and moving points that lie on the fitted ways ("q" in
lines.json) by the same displacement."""
import math

import numpy as np

DENSE_PX = 16.0         # fit_roads.py densifies q to this spacing


def pts(w):
    return np.array(w["p"], float).reshape(-1, 2)


def densify(p):
    """Points of polyline p (n, 2) with even subdivisions so no gap exceeds DENSE_PX; and the index of each vertex."""
    out, qi = [p[0]], [0]
    for a, b in zip(p[:-1], p[1:]):
        n = max(1, int(math.ceil(math.hypot(*(b - a)) / DENSE_PX)))
        for t in range(1, n + 1):
            out.append(a + (b - a) * t / n)
        qi.append(len(out) - 1)
    return np.array(out), qi


class Field:
    """Displacement at any point on (or next to) a set of fitted ways [(p (n, 2), qi, q (m, 2))]: projected onto the
    nearest original densified segment and interpolated between its two ends."""

    def __init__(self, items):
        from scipy.spatial import cKDTree
        A, B, DA, DB = [], [], [], []
        for p, qi, q in items:
            d, _ = densify(p)
            disp = q - d
            A.append(d[:-1]); B.append(d[1:]); DA.append(disp[:-1]); DB.append(disp[1:])
        self.a, self.b = np.concatenate(A), np.concatenate(B)
        self.da, self.db = np.concatenate(DA), np.concatenate(DB)
        self.tree = cKDTree((self.a + self.b) / 2)

    def at(self, P, k=8):
        P = np.asarray(P, float).reshape(-1, 2)
        _, idx = self.tree.query(P, k=min(k, len(self.a)))
        idx = idx.reshape(len(P), -1)
        a, b = self.a[idx], self.b[idx]
        ab = b - a
        t = np.clip(((P[:, None] - a) * ab).sum(-1) / np.maximum((ab ** 2).sum(-1), 1e-9), 0, 1)
        c = a + ab * t[..., None]
        dist = np.hypot(c[..., 0] - P[:, None, 0], c[..., 1] - P[:, None, 1])
        j = dist.argmin(1)
        r = np.arange(len(P))
        tt = t[r, j][:, None]
        return self.da[idx[r, j]] * (1 - tt) + self.db[idx[r, j]] * tt


def transit_fit(shapes, lines):
    """For transit.json shapes (flat [x, y, ...] lists, on the lines.json rail ways): the densified shapes (same
    geometry, so distances along them do not change) and their copies moved like the fitted rail ways. None when
    lines.json has no fitted rail ways."""
    items = [(pts(w), w["qi"], np.array(w["q"], float).reshape(-1, 2)) for w in lines["rail"] if "q" in w]
    if not items:
        return None
    F = Field(items)
    out_s, out_f = [], []
    for s in shapes:
        d, _ = densify(np.array(s, float).reshape(-1, 2))
        q = d + F.at(d)
        out_s.append([round(float(c), 1) for v in d for c in v])
        out_f.append([round(float(c), 1) for v in q for c in v])
    return out_s, out_f
