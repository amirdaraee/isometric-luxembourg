"""Drawn detail shared by the code layers (phase 3, "enrich A in code"): paving, lawns, rock, stone courses.

Everything here is albedo. Each pattern is a function of the pixel's world position on its surface (E, N, z), plus a
hash, so it is fixed to the 3D model, the same from tile to tile (no seams), deterministic, and knows nothing of the
sun or of the slope's direction: a pattern never lightens or darkens one side of anything (brief 5). Tones are
symmetric about 1 and lines are a minority of the pixels, so a material's median stays its palette colour, which is
what the shadow detector (L5.1) measures.

Thin lines are drawn by coverage (soft_band): a joint narrower than a pixel darkens its pixel by the share of the
pixel it covers, so courses and joints stay continuous lines instead of breaking into dots.
"""
from __future__ import annotations

import numpy as np

from v2.layers.common import R2, grain, pal

PX = 0.125            # metres per map pixel across the screen; a horizontal surface is sampled every 0.25 m away from it


def ihash(*a):
    """A deterministic 0..1 hash of integer arrays."""
    h = np.zeros(np.broadcast(*a).shape, np.uint64)
    for k, x in enumerate(a):
        h = h ^ (np.asarray(x).astype(np.int64).astype(np.uint64) * np.uint64([0x9E3779B1, 0x85EBCA77, 0xC2B2AE3D, 0x27D4EB2F][k % 4]))
        h = (h ^ (h >> np.uint64(15))) * np.uint64(0x2C1B3C6D)
    h = h ^ (h >> np.uint64(13))
    return (h & np.uint64(0xFFFF)).astype(np.float64) / 65535.0


def gp(px, py, amount, seed):
    """Paper grain at the pixels (px[i], py[i]) (common.grain, pointwise)."""
    px, py = np.asarray(px), np.asarray(py)
    if not px.size:
        return np.ones(0)
    return grain(px[None, :], py[None, :], amount, seed=seed)[0]


def band(x, period, width, phase=0.0):
    """True where x lies within `width` of a multiple of `period` (+ phase): lines every period."""
    r = np.mod(x - phase, period)
    return (r < width / 2) | (r > period - width / 2)


def soft_band(x, period, width, px=PX, phase=0.0):
    """Coverage (0..1) of lines `width` wide every `period`, by samples `px` apart: the share of each sample's
    footprint that the line covers."""
    r = np.mod(x - phase + period / 2, period) - period / 2          # signed distance to the nearest line
    lo = np.maximum(r - px / 2, -width / 2)
    hi = np.minimum(r + px / 2, width / 2)
    return np.clip((hi - lo) / px, 0, 1)


def vnoise(x, y, scale, seed=0):
    """Smooth value noise in 0..1: hashed values on a lattice of `scale` metres, blended smoothly between."""
    qx, qy = np.asarray(x, float) / scale, np.asarray(y, float) / scale
    ix, iy = np.floor(qx), np.floor(qy)
    fx, fy = qx - ix, qy - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = ihash(ix, iy, seed), ihash(ix + 1, iy, seed)
    c, d = ihash(ix, iy + 1, seed), ihash(ix + 1, iy + 1, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def slabs(x, y, w, h, px=PX, joint=0.06, tone=0.04, seed=0):
    """Stones w x h in rows with staggered joints: (each stone's tone factor, the joints' coverage)."""
    row = np.floor(y / h)
    xs = x + np.mod(row, 2) * w / 2
    col = np.floor(xs / w)
    t = 1 + (ihash(row, col, seed) - 0.5) * 2 * tone
    return t, np.maximum(soft_band(y, h, joint, px), soft_band(xs, w, joint, px))


def ashlar(P, nrm, course=0.45, length=0.95, tone=0.06, joint=0.22, seed=0):
    """Coursed stone on a vertical face: the factor (stone tones and joints) at world points P with normals nrm; 1 on
    faces that are not vertical."""
    h = np.linalg.norm(nrm[:, :2], axis=1)
    d = np.where(h[:, None] > 1e-6, nrm[:, :2] / np.maximum(h, 1e-6)[:, None], 0)
    along = P[:, 0] * -d[:, 1] + P[:, 1] * d[:, 0]
    t, j = slabs(along, P[:, 2], length, course, PX, joint=0.05, tone=tone, seed=seed)
    return np.where(h > 0.7, t * (1 - joint * j), 1.0)


def rock(e, n, z, seed=3):
    """Bedded sandstone (the Bock, the valley cliffs): level beds that undulate gently, each with its own tone, some
    of them ledges; upright joints at each bed's own spacing; a tone per block. Returns the factor on the rock colour."""
    u = (np.asarray(e, float) + np.asarray(n, float)) * R2              # across the screen
    f = (np.asarray(n, float) - np.asarray(e, float)) * R2
    zz = np.asarray(z, float) + 0.7 * (vnoise(u, f, 7.0, seed) - 0.5)
    bed_h = 0.9
    bed = np.floor(zz / bed_h)
    hb = ihash(bed, seed)
    ledge = hb < 0.3
    lines = soft_band(zz, bed_h, np.where(ledge, 0.2, 0.09), PX)
    w = 1.3 + 2.4 * ihash(bed, seed + 1)
    xs = u + 9.0 * ihash(bed, seed + 2)
    col = np.floor(xs / w)
    joints = soft_band(xs, w, 0.09, PX) * (ihash(bed, col, seed + 3) < 0.75)
    tone = 1 + (ihash(bed, col, seed + 4) - 0.5) * 0.14 + (hb - 0.5) * 0.08 + (vnoise(u, zz, 5.0, seed + 5) - 0.5) * 0.08
    return tone * (1 - np.where(ledge, 0.42, 0.26) * lines) * (1 - 0.24 * joints)


# Ground classes' detail: smooth tone over (large, small) patches in metres with their strengths, and the share of
# pixels drawn as darker and lighter flecks (blades, leaves, gravel).
GREEN = {"grass": ((4.0, 0.9), (0.05, 0.04), 0.035, 0.03), "meadow": ((5.0, 1.1), (0.06, 0.05), 0.05, 0.04),
         "garden": ((2.5, 0.8), (0.07, 0.06), 0.05, 0.04), "cemetery": ((3.0, 0.9), (0.05, 0.04), 0.03, 0.03),
         "scrub": ((3.0, 1.2), (0.08, 0.07), 0.07, 0.04), "wood": ((4.0, 1.4), (0.09, 0.08), 0.08, 0.03),
         "pitch": ((6.0, 1.0), (0.02, 0.02), 0.02, 0.02)}
FLOWERS = ("flower_red", "flower_yellow", "flower_white", "flower_violet")


def ground_detail(rgb, k, names, e, n, z, px, py):
    """The ground's drawn detail by class: stone slabs on paved land, setts on squares, gravel on car parks, rail
    ground and building sites, patchy lawns with flecks, flowers in gardens, mown stripes on pitches, bedded rock.
    rgb (m, 3) float, k (m,) class indexes into names; e, n, z world; px, py map pixels. In place."""
    def of(c):
        return k == names.index(c) if c in names else np.zeros(len(k), bool)
    fine = ihash(px, py, 9)                                   # one hash per map pixel
    m = of("paved")
    if m.any():
        t, j = slabs(e[m], n[m], 1.5, 0.75, 0.2, joint=0.07, tone=0.035, seed=1)
        rgb[m] *= (t * (1 - 0.13 * j))[:, None]
    m = of("square")
    if m.any():
        t, j = slabs(e[m], n[m], 0.9, 0.9, 0.2, joint=0.08, tone=0.05, seed=2)
        rgb[m] *= (t * (1 - 0.16 * j))[:, None]
    for c, amount in (("parking", 0.05), ("railground", 0.09), ("buildsite", 0.07)):
        m = of(c)
        if m.any():
            rgb[m] *= (1 + (fine[m] - 0.5) * 2 * amount)[:, None]
    for c, ((s1, s2), (a1, a2), dark, light) in GREEN.items():
        m = of(c)
        if not m.any():
            continue
        t = 1 + (vnoise(e[m], n[m], s1, 11) - 0.5) * 2 * a1 + (vnoise(e[m], n[m], s2, 12) - 0.5) * 2 * a2
        t = t * np.where(fine[m] < dark, 0.84, np.where(fine[m] > 1 - light, 1.08, 1.0))
        if c == "pitch":
            t = t * np.where(np.mod(np.floor((e[m] + n[m]) * R2 / 3.0), 2) == 0, 1.03, 0.97)
        rgb[m] *= t[:, None]
        if c == "garden":
            ce, cn = np.floor(e[m] / 0.3), np.floor(n[m] / 0.3)
            fl = ihash(ce, cn, 21) < 0.02
            if fl.any():
                which = (ihash(ce, cn, 22) * len(FLOWERS)).astype(int).clip(0, len(FLOWERS) - 1)
                cols = np.array([pal("ground", f) for f in FLOWERS])
                sub = rgb[m]
                sub[fl] = cols[which[fl]]
                rgb[m] = sub
    m = of("rock")
    if m.any():
        rgb[m] *= rock(e[m], n[m], z[m])[:, None]
    return rgb
