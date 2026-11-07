"""Illustrated clouds around the edge of the map, so the empty background outside the 3D data is not left blank.

  build_clouds.py sprites   -> web/public/clouds/c{i}.png and c{i}_n.png (day and night), drawn procedurally
  build_clouds.py place     -> web/public/data/clouds.json: the edge of the data, and where each cloud sits
  build_clouds.py           -> both

The sprites are drawn like the map: flat cel-shaded puffs of cumulus, seen slightly from above, with a thin
grey-blue ink outline round the whole cloud and finer lines where a front puff overlaps one behind it.

Placement: the outline of the data (from the render frames, see city_blocks.data_mask) is walked at an even step.
A dense bank of clouds sits on that line, overlapping the map's ragged edge a little, and further rings thin out
into the background, so at the widest view the whole map floats in a sea of cloud. The viewer
(web/src/components/Clouds.tsx) also fills everything outside the outline with a soft sky gradient.
"""
import json
import sys

import cv2
import numpy as np
from PIL import Image, ImageFilter

from city_blocks import data_mask
from common import WEB

OUT_SPRITES = WEB / "public" / "clouds"
OUT_JSON = WEB / "public" / "data" / "clouds.json"
N_SPRITES = 8
SW, SH = 560, 340          # sprite size (px)
SS = 2                     # supersampling while drawing

# Day palette, light to dark, and the ink.
DAY = [(255, 252, 244), (246, 241, 230), (221, 227, 236), (182, 195, 214), (150, 166, 191)]
DAY_INK = (98, 114, 140)
DAY_INNER = (150, 164, 188)
# Night: the same cloud in dark blue-grey, with a pale moonlit rim.
NIGHT = [(84, 97, 124), (71, 83, 109), (57, 68, 93), (44, 53, 75), (35, 43, 63)]
NIGHT_INK = (22, 28, 44)
NIGHT_INNER = (38, 46, 66)
MOON = (196, 212, 236)


def _puffs(rng, w, h):
    """Circles (cx, cy, r, z) making one cumulus: small puffs on a flat base, bigger ones heaped behind and on top."""
    base = h * 0.84
    span = w * rng.uniform(0.60, 0.72)
    x0 = (w - span) / 2
    puffs = []
    # filler behind everything along the base, so the bank has no holes
    for i in range(7):
        puffs.append((x0 + span * (0.06 + 0.88 * i / 6), base - h * 0.13, h * 0.15, 0.0))
    # crown: two or three big puffs, furthest back (seen from above, the far side shows above the near side)
    k = int(rng.integers(2, 4))
    for i in range(k):
        r = h * rng.uniform(0.20, 0.27)
        cx = w / 2 + (i - (k - 1) / 2) * span * 0.26 + rng.uniform(-0.05, 0.05) * span
        puffs.append((cx, base - h * rng.uniform(0.36, 0.54), r, 0.0))
    # middle row
    n = int(rng.integers(4, 6))
    for i in range(n):
        r = h * rng.uniform(0.13, 0.18)
        cx = x0 + span * (0.08 + 0.84 * i / (n - 1)) + rng.uniform(-0.03, 0.03) * span
        lift = 1 - abs(i / (n - 1) - 0.5) * 2
        puffs.append((cx, base - h * (0.20 + 0.10 * lift) - rng.uniform(0, h * 0.04), r, h * 0.10))
    # front row on the base line, nearest the viewer, overlapping so the base has no gaps
    n = int(rng.integers(4, 7))
    for i in range(n):
        r = h * rng.uniform(0.11, 0.16)
        cx = x0 + span * (0.03 + 0.94 * i / (n - 1)) + rng.uniform(-0.03, 0.03) * span
        puffs.append((cx, base - r * rng.uniform(0.35, 0.75), r, h * 0.20 + rng.uniform(0, h * 0.03)))
    return puffs, base


def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def draw_sprite(seed):
    rng = np.random.default_rng(seed)
    w, h = SW * SS, SH * SS
    puffs, base = _puffs(rng, w, h * 0.92)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    height = np.full((h, w), -1e9, np.float32)
    owner = np.full((h, w), -1, np.int32)
    gx = np.zeros((h, w), np.float32)
    gy = np.zeros((h, w), np.float32)
    for i, (cx, cy, r, z) in enumerate(puffs):
        d2 = (xx - cx) ** 2 + ((yy - cy) * 1.08) ** 2
        inside = d2 < r * r
        cap = np.sqrt(np.maximum(r * r - d2, 0)) + z
        take = inside   # puffs come back to front, so a nearer one covers those behind it
        height[take] = cap[take]
        owner[take] = i
        # unit normal of the sphere: (x - cx, y - cy, cap) / r
        gx[take] = ((xx - cx) / r)[take]
        gy[take] = ((yy - cy) / r)[take]
    wobble = np.sin(xx / w * 9 + seed) * h * 0.008
    solid = (owner >= 0) & (yy < base + wobble)
    nz = np.sqrt(np.maximum(1 - gx ** 2 - gy ** 2, 0))

    # Light from the upper left and towards the viewer; the lower part of the cloud is in its own shade.
    L = np.array([-0.45, -0.75, 0.50])
    L /= np.linalg.norm(L)
    lit = gx * L[0] + gy * L[1] + nz * L[2]
    top = yy[solid].min() if solid.any() else 0
    vert = (yy - top) / max(base - top, 1)
    tone = 0.26 * lit + 0.74 * (1 - vert) + 0.06
    tone = cv2.GaussianBlur(tone, (0, 0), SS * 1.5)
    # cel shading: flat steps with narrow soft edges; the lowest two only on the underside
    steps = [0.74, 0.50, 0.26, 0.12]
    idx = np.zeros((h, w), np.float32)
    for s in steps:
        idx += 1 - _smoothstep(s - 0.012, s + 0.012, tone)

    drawn = (rng.random(len(puffs)) < 0.35) & (np.arange(len(puffs)) >= 7)  # which puffs get an inner line: not all, so it reads as drawn by hand

    def paint(pal, ink, inner, rim):
        pal = np.array(pal, np.float32)
        lo = np.clip(np.floor(idx).astype(int), 0, len(pal) - 1)
        hi = np.clip(lo + 1, 0, len(pal) - 1)
        f = (idx - np.floor(idx))[..., None]
        rgb = pal[lo] * (1 - f) + pal[hi] * f
        a = solid.astype(np.float32)
        # fine inner lines where a nearer puff overlaps one behind it
        # (on the upper rim of the nearer puff only, as an artist would draw it)
        jump = np.zeros((h, w), bool)
        for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            o2 = np.roll(owner, (dy, dx), (0, 1))
            jump |= (o2 >= 0) & (o2 < owner) & (gy < -0.45) & (np.abs(gx) < 0.6) & solid & np.roll(solid, (dy, dx), (0, 1))
        jump &= drawn[np.maximum(owner, 0)]
        # drop short scraps, which read as specks rather than lines
        nl, lab, st, _ = cv2.connectedComponentsWithStats(jump.astype(np.uint8), connectivity=8)
        jump = np.isin(lab, 1 + np.flatnonzero(st[1:, cv2.CC_STAT_AREA] >= 40 * SS))
        inner_line = cv2.dilate(jump.astype(np.uint8), np.ones((2 * SS, 2 * SS), np.uint8)) > 0
        rgb[inner_line] = rgb[inner_line] * 0.3 + np.array(inner, np.float32) * 0.7
        # outer ink: a band just inside the silhouette
        k = int(SS * 2.6)
        eroded = cv2.erode(solid.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))) > 0
        if rim is not None:
            # moonlit rim: a pale band inside the ink on the upper side
            k2 = int(SS * 7)
            er2 = cv2.erode(solid.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k2 + 1, 2 * k2 + 1))) > 0
            band = (solid & ~er2).astype(np.float32)
            band = cv2.GaussianBlur(band, (0, 0), SS * 1.5) * np.clip(-gy * 0.9 + 0.35 * gx + 0.2, 0, 1) * (1 - vert * 0.8)
            band = np.clip(band, 0, 1)[..., None] * 0.75
            rgb = rgb * (1 - band) + np.array(rim, np.float32) * band
        edge = solid & ~eroded
        rgb[edge] = np.array(ink, np.float32)
        img = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
        im = Image.fromarray(img, "RGBA").resize((SW, SH), Image.LANCZOS)
        # a soft shadow below and to the right, as if on the ground far beneath
        sh = Image.fromarray((solid * 255).astype(np.uint8)).resize((SW, SH), Image.BILINEAR)
        sh = sh.transform(sh.size, Image.AFFINE, (1, 0, -SW * 0.03, 0, 1, -SH * 0.07)).filter(ImageFilter.GaussianBlur(SW * 0.018))
        shadow = Image.new("RGBA", (SW, SH), (14, 20, 36, 0))
        shadow.putalpha(sh.point(lambda v: int(v * 0.22)))
        return Image.alpha_composite(shadow, im)

    return paint(DAY, DAY_INK, DAY_INNER, None), paint(NIGHT, NIGHT_INK, NIGHT_INNER, MOON)


def sprites():
    OUT_SPRITES.mkdir(parents=True, exist_ok=True)
    seeds = [3, 11, 19, 27, 41, 58, 73, 90][:N_SPRITES]
    total = 0
    for i, s in enumerate(seeds):
        day, night = draw_sprite(s)
        for im, name in ((day, f"c{i}.png"), (night, f"c{i}_n.png")):
            p = OUT_SPRITES / name
            im.save(p, optimize=True)
            total += p.stat().st_size
    print(f"{2 * len(seeds)} sprites, {total / 1024:.0f} KB")


# --- placement ---------------------------------------------------------------------------------------------------

S = 16                  # mask scale
STEP = 1050             # map px between clouds along the edge
OVERLAP = 450           # how far the edge bank reaches over the data (map px)
EDGE_RINGS = [          # (gap beyond the first ring, map px; size range, map px; parallax range)
    (0, (2000, 2900), (0.00, 0.02)),
    (800, (2100, 3100), (0.01, 0.03)),
]
SEA = 30000             # the sea of clouds reaches this far beyond the data (map px)
# The visible body of a sprite, as half-axes of an ellipse in units of its width (the puffs fill ~2/3 of the width).
BODY = (0.34, 0.20)


def outline():
    mask, W, H = data_mask(S)
    m = mask.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = (lab == big).astype(np.uint8)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(np.float64) * S + S / 2
    return c, m, W, H


def resample(c, step):
    seg = np.hypot(*np.diff(np.vstack([c, c[:1]]), axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    n = int(cum[-1] // step)
    t = np.linspace(0, cum[-1], n, endpoint=False)
    closed = np.vstack([c, c[:1]])
    return np.column_stack([np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])])


def place():
    c, m, W, H = outline()
    # a smooth version of the edge to walk along (the raw one zig-zags pixel by pixel)
    smooth = resample(c, 200)
    k = 3
    pad = np.vstack([smooth[-k:], smooth, smooth[:k]])
    ker = np.ones(2 * k + 1) / (2 * k + 1)
    smooth = np.column_stack([np.convolve(pad[:, 0], ker, "valid"), np.convolve(pad[:, 1], ker, "valid")])
    centre = smooth.mean(0)

    rng = np.random.default_rng(1867)
    clouds = []

    def add(x, y, w, par, ring):
        clouds.append({
            "x": round(float(x)), "y": round(float(y)), "w": round(float(w)),
            "s": int(rng.integers(0, N_SPRITES)),
            "f": int(rng.random() < 0.5),                         # mirrored
            "p": round(float(rng.uniform(*par)), 3),              # parallax: 0 on the ground .. higher moves more
            "v": round(float(rng.uniform(3, 9)), 1),              # drift speed, map px per second
            "ph": round(float(rng.uniform(0, 6.283)), 2),         # drift phase
            "r": ring,                                            # 0 on the edge, larger further out
        })

    # 1. The bank on the edge: walk the outline, each cloud reaching OVERLAP px over the data.
    pts = resample(smooth, STEP)
    nxt = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    normal = np.column_stack([nxt[:, 1], -nxt[:, 0]])
    normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-9
    flip = ((pts - centre) * normal).sum(1) < 0      # point the normals away from the middle of the map
    normal[flip] *= -1
    for ri, (off, size, par) in enumerate(EDGE_RINGS):
        for p, nrm in zip(pts, normal):
            w = rng.uniform(*size)
            # distance from the cloud's centre to its body's edge, towards the map
            support = w * np.hypot(BODY[0] * nrm[0], BODY[1] * nrm[1])
            tangent = np.array([-nrm[1], nrm[0]])
            o = support - OVERLAP + off + rng.uniform(-0.15, 0.3) * max(off, 400)
            x, y = p + nrm * o + tangent * (rng.uniform(-0.35, 0.35) + ri * 0.5) * STEP
            add(x, y, w, par, ri)

    # 2. The sea: random darts over a wide field round the map, kept apart by a spacing that grows with the
    # distance from the data, so the clouds thin out into the open sky.
    T = 64                                           # field scale, map px per cell
    pad = SEA // T + 4
    small = cv2.resize(m, (m.shape[1] * S // T, m.shape[0] * S // T), interpolation=cv2.INTER_AREA)
    field = np.zeros((small.shape[0] + 2 * pad, small.shape[1] + 2 * pad), np.uint8)
    field[pad:pad + small.shape[0], pad:pad + small.shape[1]] = small > 0
    dist = cv2.distanceTransform(1 - field, cv2.DIST_L2, 5) * T
    # a smooth random field, so the sea gathers into banks and clumps with open sky between them
    noise = cv2.GaussianBlur(rng.random(field.shape).astype(np.float32), (0, 0), 5000 / T)
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    placed = np.array([[c["x"], c["y"]] for c in clouds], float)
    sea = []
    for _ in range(150000):
        gx, gy = rng.uniform(0, field.shape[1]), rng.uniform(0, field.shape[0])
        d = dist[int(gy), int(gx)]
        if d < 1600 or d > SEA:
            continue
        x, y = (gx - pad) * T, (gy - pad) * T
        n = noise[int(gy), int(gx)]
        # near the edge the bank is solid; further out, clouds only where the field is high
        if d > 3000 and n < 0.45 + 0.25 * min(d / SEA, 1):
            continue
        spacing = (1500 + d * 0.32) * (1.6 - n)
        allp = np.vstack([placed, np.array(sea).reshape(-1, 2)]) if sea else placed
        dd = np.hypot(allp[:, 0] - x, (allp[:, 1] - y) / 0.6)    # clouds are wide: pack them closer vertically
        if dd.min() < spacing:
            continue
        sea.append((x, y))
        t = min(d / SEA, 1)
        w = rng.uniform(1800, 3200) + t * rng.uniform(0, 2000)
        add(x, y, w, (0.02 + 0.06 * t, 0.04 + 0.08 * t), 2 + int(t * 6))

    # lower (less parallax) first, so higher clouds are drawn over them; the edge ring on top of its neighbours
    clouds.sort(key=lambda d: (d["p"], -d["r"]))
    edge = cv2.approxPolyDP(c.astype(np.float32).reshape(-1, 1, 2), 24, True)[:, 0, :]
    out = {
        "width": W, "height": H, "sprites": N_SPRITES, "spriteSize": [SW, SH],
        "centre": [round(float(centre[0])), round(float(centre[1]))],
        # outline of the data, map px: the sky is painted outside it
        "edge": [int(v) for v in np.round(edge).reshape(-1)],
        "clouds": clouds,
    }
    OUT_JSON.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(clouds)} clouds, edge of {len(edge)} points, {OUT_JSON.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("sprites", "all"):
        sprites()
    if what in ("place", "all"):
        place()
