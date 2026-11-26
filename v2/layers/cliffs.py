"""Cliffs and walls. Specs: layer-01-ground.md (rock), layer-02-relief.md (walls).

The owner, 26 Nov 2026, in order: a rock of stacked blocks in v1's manner was first chosen from samples, then, seen
on the Bock, turned down ("no noo, what is this? find a real photo of this cliff and compare"). The photo (the
Bock's south-east face from Neumuenster Abbey, Paul Braun, Wikimedia Commons, CC BY 4.0) shows one massive pale
face with five or six big dark clefts, fine rough bedding, no blocks. The rock here is drawn from it, flat, as a
cartoon ("looks good"). Earlier the same day: no green patches in a rock face; and of the built walls drawn on the
Bock's rock from the wall data, "does not make sense", "simplify it and not stick to reality because you don't
have enough data". So a rock face is one thing, rock, whatever stands on it.

Three drawings, all albedo and all from a pixel's own place in the world (so a tile and its neighbour agree):
  rock      one pale face in three near tones in broad patches; a big cleft about every eleven metres across the
            screen, wandering, opening and closing up the face, its screen-right side a tone darker (a buttress
            in its own shade); faint bedding, short level strokes; faint stains. No blocks, no joints, no ink
  dry stone a low face (a terrace's or a garden's wall): small stones in rough courses, in the rock's own colours
  masonry   a built wall's face where the wall stands on open ground, not on a rock face (the scene's OSM walls):
            level courses of grey stone, patchy as an old wall

And two rules on where rock is:
  rock_zone   a rock face is rock from top to foot: the scene's cliff cells, the steep cells beside them, and the
              small gaps between them (no patches of lawn inside a face)
  face_height how tall the face is at a cell (the terrain's range close by): under LOW_FACE_M it is a low wall
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

from v2.layers.common import R2, pal
from v2.layers.detail import ihash, vnoise

# rock: metres, shares (0..1) and tone factors
ROCK = {"patch": (14.0, 8.0, 0.6),     # the three tones' broad patches: over (across, up) metres, their weight
        "bed": (3.2, 0.8, 9.0),        # ... and the beds' bands: a bed's height, its wave (m) over metres
        "every": 11.0,                 # a big cleft about every so many metres across the screen
        "place": (0.15, 0.7),          # where in its stretch a cleft stands: from, range (shares)
        "wander": (1.2, 8.0),          # a cleft's wander across: metres, over metres up
        "open": (7.0, 0.3, 0.3),       # a cleft opens and closes up the face: over metres, from, range
        "width": (0.5, 1.5),           # an open cleft's width, least and most
        "flank": (2.6, 0.5, 0.15, 0.86),   # the darker side right of a cleft: width, its least share, how open, tone
        "tick": (1.0, 2.6, 1.3, 0.5, 0.15, 0.74),   # bedding strokes: rows, cells, shift (m), share, height, tone
        "tick_wave": (0.3, 6.0),       # the strokes' rows wave: metres, over metres
        "stain": (0.8, 0.91, 1.1, 13.0)}   # stains down the face: threshold, tone, over (across, up) metres
DRY = {"course": 0.45, "stone": 0.8, "joint": 0.05, "patch": (0.9, 0.18, 5.0, 3.0)}
MASONRY = {"course": 0.5, "stone": 1.0, "joint": 0.05, "patch": (0.87, 0.2, 7.0, 4.0)}
LOW_FACE_M = 3.5                       # a face lower than this is a low wall (dry stone), not rock
ZONE = {"reach_m": 2.5, "gap_m2": 60.0, "height_r_m": 2.5,
        "wall_reach_m": 5.0,
        "wall_stub_m": 15.0,        # a piece of wall shorter than this left over beside a face is not drawn either
        "edge_m": 0.5,              # a face's border is smoothed over this (render.rock_soft)
        "way_share": 0.3}           # wall_reach_m: a wall this near a rock face (in plan) is part of the face, not drawn
                                       # as a wall; way_share: a path lying on a face along this share of its length is not drawn


# a casemate's opening in a rock face (metres): half its width, its sill over the gallery's floor, its upright sides'
# height, its arch's rise; and how far before and beyond the branch's outer end its line is followed to the face
OPENING = {"half_m": 0.9, "sill_m": 0.4, "side_m": 1.2, "arch_m": 0.9, "from_m": -3.0, "to_m": 12.0}


def gun_branches(doc):
    """The gun branches of a casemates hand model (v2/data/structures/casemates.json): for each, its outer end
    (E, N), its direction outward (unit, in plan) and its floor's height. The outer end is the one farther from the
    main gallery's line. The model is approximate, placed by hand against the terrain: so are the openings."""
    G = doc.get("galleries", [])
    main = [g for g in G if g.get("kind") == "gallery"]
    if not main:
        return []
    m = np.asarray(main[0]["en"], float)
    ax = (m[-1] - m[0]) / np.linalg.norm(m[-1] - m[0])
    out = []
    for g in G:
        if g.get("kind") != "branch":
            continue
        en = np.asarray(g["en"], float)
        d = [abs((p - m[0])[0] * ax[1] - (p - m[0])[1] * ax[0]) for p in (en[0], en[-1])]
        far, near = (en[-1], en[0]) if d[1] > d[0] else (en[0], en[-1])
        z = g["z"]
        out.append((far, (far - near) / np.linalg.norm(far - near), float(z[0] if isinstance(z, list) else z)))
    return out


def openings(e, n, z, branches, p=OPENING):
    """True at the world points (on a rock face) that lie in a casemate's opening: an arched hole on the line of
    a gun branch, where that line comes out of the rock (the owner, 26 Nov 2026, of two samples: the openings,
    without the wall on top). A function of the point's place only."""
    e, n, z = (np.asarray(v, float) for v in (e, n, z))
    hole = np.zeros(len(e), bool)
    for far, u, zf in branches:
        de, dn = e - far[0], n - far[1]
        along, across = de * u[0] + dn * u[1], np.abs(de * u[1] - dn * u[0])
        h = z - zf - p["sill_m"]
        top = p["side_m"] + p["arch_m"] * np.sqrt(np.clip(1 - (across / p["half_m"]) ** 2, 0, 1))
        hole |= (along > p["from_m"]) & (along < p["to_m"]) & (across < p["half_m"]) & (h > 0) & (h < top)
    return hole


def _tones(group, names):
    return np.array([pal(group, n) for n in names], float)


def rock(e, n, z):
    """Rock colours (m, 3) at world points, and nothing else of them: no light, no side."""
    e, n, z = (np.asarray(v, float) for v in (e, n, z))
    R = ROCK
    a0 = (e + n) * R2                                                  # the place across the screen
    T = _tones("relief", ("rock_1", "rock_2", "rock_3"))
    # three near tones in broad patches, and the beds' faint bands
    px, pz, pw = R["patch"]
    bh, bw, bx = R["bed"]
    v = pw * vnoise(a0, z * px / pz, px, 301) + (1 - pw) * ihash(np.floor((z + bw * (vnoise(a0, z, bx, 302) - 0.5)) / bh), 303)
    c = T[np.clip((v * len(T)).astype(int), 0, len(T) - 1)].copy()
    # a few big clefts: each wanders, opens and closes up the face; its screen-right side is in shade
    wm, wz = R["wander"]
    a = a0 + wm * 2 * (vnoise(z, np.zeros_like(z), wz, 304) - 0.5)
    E = R["every"]

    def at(k):
        return (k + R["place"][0] + R["place"][1] * ihash(k, 305)) * E
    k0 = np.floor(a / E)
    k = np.where(a >= at(k0), k0, k0 - 1)                              # the cleft to the left
    oz, o0, o1 = R["open"]
    fw, f0, fo, ft = R["flank"]
    cleft = np.zeros(len(a), bool)
    for kk, side in ((k, 1), (k + 1, -1)):
        d = (a - at(kk)) * side                                        # how far from the cleft, on this side
        open_ = np.clip((vnoise(z, kk * 3.1 * oz, oz, 306) - o0) / o1, 0, 1)
        w = (R["width"][0] + (R["width"][1] - R["width"][0]) * ihash(kk, 307)) * open_
        if side == 1:
            c[(d < fw * (f0 + ihash(kk, 308))) & (open_ > fo)] *= ft
        cleft |= d < w / 2
    # faint bedding: short level strokes, a tone darker; and stains
    row, cell, shift, share, th, tt = R["tick"]
    zz = z + R["tick_wave"][0] * (vnoise(a0, z, R["tick_wave"][1], 309) - 0.5)
    r = np.floor(zz / row)
    x = (a0 + shift * ihash(r, 310)) / cell
    q = np.floor(x)
    u = x - q
    s0 = 0.1 + 0.4 * ihash(r, q, 311)
    tick = (ihash(r, q, 313) < share) & (u > s0) & (u < s0 + 0.25 + 0.5 * ihash(r, q, 312)) & ((zz / row - r) * row < th)
    c[tick] *= tt
    s_, st, sx, sz = R["stain"]
    c[vnoise(a0, z * sx / sz, sx, 314) > s_] *= st
    c[cleft] = pal("relief", "rock_cleft")
    return np.minimum(c, 255.0)


def _courses(along, z, p, tones, joint, seed):
    """Level courses of stones, each course's upright joints set off from the next; patchy."""
    r = np.floor(z / p["course"])
    aa = along / p["stone"] + 0.5 * np.mod(r, 2) + 0.25 * (ihash(r, seed) - 0.5)
    q = np.floor(aa)
    c = tones[np.minimum((ihash(q, r, seed + 1) * len(tones)).astype(int), len(tones) - 1)].copy()
    p0, p1, px, pz = p["patch"]
    c *= (p0 + p1 * vnoise(along, z * px / pz, px, seed + 2))[:, None]
    c[((aa - q) * p["stone"] < p["joint"]) | ((z / p["course"] - r) * p["course"] < p["joint"])] = joint
    return np.minimum(c, 255.0)


def dry_stone(e, n, z):
    """A low face's colours (m, 3) at world points: dry stone, in the rock's own colours."""
    e, n, z = (np.asarray(v, float) for v in (e, n, z))
    return _courses((e + n) * R2, z, DRY, _tones("relief", ("drystone_1", "drystone_2", "drystone_3")),
                    pal("relief", "drystone_joint"), 31)


def masonry(P, nrm):
    """A built wall's colours (m, 3) at world points P (m, 3) on faces with normals nrm: coursed grey stone along
    the wall; the wall's flat top (not upright) is its coping."""
    P, nrm = np.asarray(P, float), np.asarray(nrm, float)
    h = np.linalg.norm(nrm[:, :2], axis=1)
    d = np.where(h[:, None] > 1e-6, nrm[:, :2] / np.maximum(h, 1e-6)[:, None], 0)
    along = P[:, 0] * -d[:, 1] + P[:, 1] * d[:, 0]
    c = _courses(along, P[:, 2], MASONRY, _tones("relief", ("masonry_1", "masonry_2", "masonry_3")),
                 pal("relief", "masonry_joint"), 41)
    c[h <= 0.7] = pal("relief", "coping")
    return c


def rock_zone(cls, slope, step, steep_deg, p=ZONE):
    """Where a rock face is, on the terrain's grid: the cliff cells (cls 2), the steep cells within reach_m of them,
    and the gaps between them smaller than gap_m2 (a patch of lawn inside a face is rock; a real ledge stays)."""
    cliff = np.asarray(cls) == 2
    r = max(int(round(p["reach_m"] / step)), 1)
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disc = xx * xx + yy * yy <= r * r
    zone = cliff | (ndi.binary_dilation(cliff, structure=disc) & (np.asarray(slope, float) >= steep_deg))
    lab, n = ndi.label(~zone)
    if n:
        size = np.bincount(lab.ravel(), minlength=n + 1)
        edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        small = size < p["gap_m2"] / (step * step)
        small[0] = False
        small[edge] = False                                             # open to the grid's edge: not a gap
        near = ndi.binary_dilation(cliff, structure=disc, iterations=2)  # ... and only beside a cliff
        touch = np.zeros(n + 1, bool)
        touch[np.unique(lab[near])] = True
        zone |= (small & touch)[lab]
    return zone


def face_height(z, step, p=ZONE):
    """The terrain's range (m) within height_r_m of each cell: about the height of the face a cell lies on."""
    r = max(int(round(p["height_r_m"] / step)), 1)
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    disc = xx * xx + yy * yy <= r * r
    z = np.asarray(z, float)
    return ndi.maximum_filter(z, footprint=disc) - ndi.minimum_filter(z, footprint=disc)


def wall_on_face(near, step_m, p=ZONE):
    """Along one wall sampled every step_m: the samples that are part of a rock face, so not drawn as a wall. They
    are the samples on or within wall_reach_m of a face (`near`), and any stretch of the wall between or beside them
    shorter than wall_stub_m: a short piece left standing alone reads as a thing of its own (26 Nov 2026: the
    vehicle detector took one of 8 m, left of a long wall along a cliff, for a bus)."""
    near = np.asarray(near, bool)
    out = near.copy()
    if near.any():
        lab, k = ndi.label(~near)
        short = np.flatnonzero(np.bincount(lab, minlength=k + 1)[1:] * step_m < p["wall_stub_m"]) + 1
        out |= np.isin(lab, short)
    return out
