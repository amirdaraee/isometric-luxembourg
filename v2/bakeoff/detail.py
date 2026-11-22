"""Detail transfer (Phase 3 trial T1): v1's painted look on v2's exact geometry, tried on six blocks.

Why. The bake-off's AI routes gave the style model the plain code render and got it back nearly unchanged (C1p,
C4: PHASE2_RESULTS.md). v1's richness came from what its model was given: the photo-textured 3D capture
(pipeline/render.py: ACT's textured buildings on the orthophoto) and a line guide. v2's camera is v1's at twice the
scale (specs/camera.md), so v1's captures and v1's finished paintings lie on v2's map pixel for pixel.

What. A painting is never shown as it is. It gives two things to the code art, building part by building part:
  colour   the walls' and the roofs' colour (the mean of the painting's pixels on that part over a luminance band
           above its shaded and inked pixels), one colour for all walls of a building and one for its roofs
  texture  the painting's brightness against its own local mean inside each face, clipped, faded to nothing at the
           code art's own edges
Everything else stays the code's: shape, ink lines, windows, doors, shutters and trim, ground, roads, rails, water,
trees, light and shadow. So lines stay straight, nothing is lit twice, and no painted car can come through.

A painting drifts a few pixels from the geometry it was painted over (v1's by up to ~20 v2 px here, differently
from building to building), so each building is first registered: the whole-pixel shift at which the painting's
edges best meet the code art's.

Two sources of paintings:
  free   v1's finished day art, as it is on disk (v1 painted at 0.293 m/px; v2's map pixel is 0.125 m)
  T2     T1 again, inputs and seeds, with the prompt asking for even light (jobs.py T2)
  T1     new paintings of the same blocks by v1's style model from v1's capture and v2's own line layout, at two
         scales: p250 (one model pixel = 0.25 m, the scale v1 was painted at, one painting per 256 m block) and
         p125 (0.125 m, v2's own scale, the block's central 128 m). Paid: jobs.py T1, quoted, the owner's to approve.

    python -m v2.bakeoff inputs detail      T1's control images for the six blocks, both scales ($0)
    python -m v2.bakeoff detail [--source free|T1|T2]
                                            register + transfer on the six blocks, the numbers and the sheets
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from v2.config import V2, v1_work, v2_data

Image.MAX_IMAGE_PIXELS = None

AREA = "test"
BLOCK = 2048                                  # a block: 256 m square, in v2 map pixels
WIN = 1024                                    # the model's window
# name -> (x0, y0) of the block in v2 map pixels (even, so v1's pixels are whole). The Bock overlaps the abbey's
# block by half: the trial's seam between two neighbouring paintings.
BLOCKS = {
    "cathedral": (59344, 32032),
    "palace": (60640, 31920),
    "grund_abbey": (61920, 33152),
    "bock": (63072, 32784),
    "pfaffenthal": (63568, 31344),
    "clausen": (65552, 33776),
}
SCALES = {"p250": 2, "p125": 1}               # v2 map pixels per model pixel
SEEDS = (1867, 1868)                          # pod/run.sh T1, T2
PAINTED = {"T1": "painted", "T2": "painted_even", "T3": "painted_evenin"}   # each paid job's paintings (bundle.OUT)
LABEL = {"T1": "T1: as v1 painted", "T2": "T2: even light asked", "T3": "T3: evened input"}
WALL, PART, ROOF = 11, 22, 23                 # layers/common.py CLASS: what a painting may colour
PAINT_LAYERS = (5, 6)                         # which: buildings, structures
P = {
    "sigma": 7.0,                             # px: the painting's local mean is taken over this
    "k_roof": 1.0, "clip_roof": (-0.32, 0.22),
    "k_wall": 0.5, "clip_wall": (-0.07, 0.07),    # walls keep the code's windows: only a faint wash from the painting
    "edge_px": 2,                             # texture fades to nothing this near the code art's edges
    # the luminance band a part's colour is read from. Walls: a painting lights one side and shades the other, and
    # the lit side is the wall's own colour, so the upper band. Roofs: the middle, over the ink and under the glare
    "band_wall": (0.7, 0.95), "band_roof": (0.45, 0.9),
    "min_px": 120,                            # smaller parts keep the code's colour
    "code_mod": (0.55, 1.25),                 # the code's own drawing on a part, kept as a brightness factor
    "ink": 70,                                # the code's ink: darker than this stays as it is
    "reach": 48,                              # px: how far a painting may be shifted to meet a building
    "better": 1.15,                           # a shift is used only if it scores this much over no shift
    "agree_px": 12,                           # a building's shift further than this from its neighbours' median
    "neighbours": 8,                          # (the nearest this many) takes that median instead
}


def base() -> Path:
    return v2_data() / AREA / "bakeoff" / "detail"


def lum(a):
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


# ------------------------------------------------------------------------------------------------ sources
def release() -> Path:
    r = v2_data() / AREA / "release"
    return r / json.loads((r / "current.json").read_text())["folder"]


def code_window(x0, y0, size, rel: Path | None = None):
    """The code art of the built release over a window, no trees: (rgb, geom) as inputs.render_window."""
    from v2.bakeoff.inputs import _Built, render_window
    from v2.layers.common import COLOUR_LAYERS
    rel = rel or release()

    class Built:
        def layer(self, L, tile):
            return _Built(rel, L, tile)

    rgb, _layout, _mask, g = render_window(Built(), x0, y0, size, layers=COLOUR_LAYERS[:6], rel=rel)
    return rgb, g


def trees_over(x0, y0, size, g: dict, rel: Path | None = None) -> np.ndarray:
    """Layer 7 where it stands in front of the window's code art (RGBA): the sheets draw it over a result, as the
    compositor does by depth. The paintings never see it."""
    from v2.bakeoff.inputs import _Built
    from v2.layers.common import TILE, Tile
    rel = rel or release()
    out = np.zeros((size, size, 4), np.uint8)
    for ty in range(y0 // TILE, (y0 + size - 1) // TILE + 1):
        for tx in range(x0 // TILE, (x0 + size - 1) // TILE + 1):
            t = _Built(rel, "trees", Tile(tx, ty, apron=0))
            a0, b0 = max(x0, tx * TILE), max(y0, ty * TILE)
            a1, b1 = min(x0 + size, (tx + 1) * TILE), min(y0 + size, (ty + 1) * TILE)
            sl = (slice(b0 - ty * TILE, b1 - ty * TILE), slice(a0 - tx * TILE, a1 - tx * TILE))
            dl = (slice(b0 - y0, b1 - y0), slice(a0 - x0, a1 - x0))
            m = t.depth[sl] <= g["depth"][dl]
            sub = out[dl]; sub[m, :3] = t.rgb[sl][m]; sub[m, 3] = 255; out[dl] = sub
    return out


def v1_box(x0, y0, size):
    """A v2 window in v1's mosaic pixels (camera.v2_to_v1_px): (x, y, size)."""
    assert x0 % 2 == 0 and y0 % 2 == 0 and size % 2 == 0, (x0, y0, size)
    return x0 // 2 - 22528, y0 // 2 - 10240, size // 2


_open: dict = {}


def _img(p: Path):
    if p not in _open:
        if len(_open) > 2:
            _open.pop(next(iter(_open)))
        _open[p] = Image.open(p).convert("RGB")
    return _open[p]


def v1_painted(x0, y0, size, out_px=None):
    """v1's finished day art over a v2 window (data/work/tiles/painted.json, later blocks over earlier ones, as
    v1's build_tiles.py lays them), resampled to out_px. Returns (rgb, where v1 painted)."""
    a, b, n = v1_box(x0, y0, size)
    out_px = out_px or size
    s = out_px / n
    out = np.zeros((out_px, out_px, 3), np.uint8); have = np.zeros((out_px, out_px), bool)
    tiles = v1_work() / "tiles"
    for p in json.loads((tiles / "painted.json").read_text()):
        X0, Y0, W, H = p["x0"], p["y0"], p["w"], p["h"]
        a0, b0, a1, b1 = max(a, X0), max(b, Y0), min(a + n, X0 + W), min(b + n, Y0 + H)
        if a1 <= a0 or b1 <= b0:
            continue
        im = _img((tiles / p["file"]).resolve())
        k = im.width / W                                   # a canvas is 5120 px for its 6000 mosaic pixels
        tw, th = round((a1 - a0) * s), round((b1 - b0) * s)
        crop = im.resize((tw, th), Image.BICUBIC, box=((a0 - X0) * k, (b0 - Y0) * k, (a1 - X0) * k, (b1 - Y0) * k))
        oy, ox = round((b0 - b) * s), round((a0 - a) * s)
        out[oy:oy + th, ox:ox + tw] = np.asarray(crop); have[oy:oy + th, ox:ox + tw] = True
    return out, have


def v1_capture(x0, y0, size, out_px=None, folder="frames"):
    """v1's 3D capture (photo-textured buildings on the orthophoto, data/work/frames, 2048 px frames at 0.25 m)
    over a v2 window, resampled to out_px."""
    a, b, n = v1_box(x0, y0, size)
    F = json.loads((v1_work() / "mosaic.json").read_text())["frame"]
    out = np.zeros((n, n, 3), np.uint8)
    for c in range(a // F, (a + n - 1) // F + 1):
        for r in range(b // F, (b + n - 1) // F + 1):
            f = v1_work() / folder / f"{c}_{r}.jpg"
            if not f.exists():
                continue
            im = np.asarray(_img(f))
            a0, b0, a1, b1 = max(a, c * F), max(b, r * F), min(a + n, (c + 1) * F), min(b + n, (r + 1) * F)
            out[b0 - b:b1 - b, a0 - a:a1 - a] = im[b0 - r * F:b1 - r * F, a0 - c * F:a1 - c * F]
    if out_px and out_px != n:
        out = np.asarray(Image.fromarray(out).resize((out_px, out_px), Image.BICUBIC))
    return out


# ------------------------------------------------------------------------------------------------ geometry
def segments(g: dict):
    """(bid, cls, face key, seg): building id, class, a key of the face's normal, and all three as one label."""
    ids = g["ids"]
    cls = (ids & 255).astype(np.int64); bid = (ids >> 8).astype(np.int64)
    nq = np.round(np.asarray(g["normal"], float) * 6).astype(np.int64)
    face = (nq[..., 0] + 8) * 400 + (nq[..., 1] + 8) * 20 + (nq[..., 2] + 8)
    return bid, cls, face, (bid * 64 + cls) * 8000 + face


def geometry_edges(g: dict) -> np.ndarray:
    """Where the code art's lines are by construction: the nearest layer, the building, the class or the face
    changes, or the depth jumps."""
    _b, _c, _f, seg = segments(g)
    seg = seg + g["which"].astype(np.int64) * (1 << 50)
    d = np.where(np.isfinite(g["depth"]) & (g["depth"] < 1e8), g["depth"], 1e6)
    e = np.zeros(seg.shape, bool)
    e[:, 1:] |= (seg[:, 1:] != seg[:, :-1]) | (np.abs(np.diff(d, axis=1)) > 0.6)
    e[1:, :] |= (seg[1:, :] != seg[:-1, :]) | (np.abs(np.diff(d, axis=0)) > 0.6)
    return e


def layout_of(g: dict, step=1) -> np.ndarray:
    """The painter's second control image as v1's line guide has it: black lines, grey (120) openings, white.
    step 2: at half scale, a line kept wherever either pixel had one."""
    cls = (g["ids"] & 255)
    lay = np.full(cls.shape, 255, np.uint8)
    lay[np.isin(cls, (12, 13, 14)) & np.isin(g["which"], PAINT_LAYERS)] = 120
    lay[geometry_edges(g)] = 0
    if step > 1:
        h, w = lay.shape
        lay = lay.reshape(h // step, step, w // step, step).min(axis=(1, 3))
    return lay


# ------------------------------------------------------------------------------------------------ the two steps
def _grad(y, s=1.5):
    from scipy import ndimage as ndi
    y = ndi.gaussian_filter(y, s)
    return np.hypot(ndi.sobel(y, 0), ndi.sobel(y, 1))


def register(code, painting, g: dict, p: dict = P):
    """Each building's whole-pixel shift (within p["reach"]) at which the painting's edges best meet the code
    art's, and the painting resampled so every building reads its own shifted pixels. A painting drifts smoothly,
    so a building whose own best shift is not clearly better than none, or lies far from its neighbours', takes
    the median of its nearest neighbours' shifts. Returns (painting, {building: (dx, dy, own or "neighbours")})."""
    from scipy import ndimage as ndi
    code = code.astype(float); src = painting.astype(float)
    bid = (g["ids"] >> 8).astype(np.int64)
    on = np.isin(g["which"], PAINT_LAYERS)
    ec, es = _grad(lum(code)), _grad(lum(src))
    H, W = on.shape
    R = p["reach"]
    found = []                                             # [building, cx, cy, dx, dy, sure]
    for b in np.unique(bid[on]):
        m = on & (bid == b)
        if m.sum() < 400:
            continue
        rows = np.flatnonzero(m.any(1)); cols = np.flatnonzero(m.any(0))
        r0, r1 = max(rows[0] - R, 0), min(rows[-1] + 1 + R, H)
        c0, c1 = max(cols[0] - R, 0), min(cols[-1] + 1 + R, W)
        a = ec[r0:r1, c0:c1] * ndi.binary_dilation(m[r0:r1, c0:c1], iterations=3)
        s = es[r0:r1, c0:c1]
        a = a - a.mean(); s = s - s.mean()
        cc = np.fft.irfft2(np.fft.rfft2(s) * np.conj(np.fft.rfft2(a)), s=a.shape)
        dys = np.arange(-R, R + 1) % a.shape[0]; dxs = np.arange(-R, R + 1) % a.shape[1]
        sub = cc[np.ix_(dys, dxs)]
        i, j = np.unravel_index(np.argmax(sub), sub.shape)
        best, zero = float(sub[i, j]), float(cc[0, 0])
        dy, dx = int(i) - R, int(j) - R
        sure = best > 0 and best >= zero * p["better"] and abs(dx) < R and abs(dy) < R
        if not (dx or dy):
            sure = best > 0
        found.append([int(b), (cols[0] + cols[-1]) / 2, (rows[0] + rows[-1]) / 2, dx, dy, bool(sure)])
    out = painting.copy(); shifts = {}
    if not found:
        return out, shifts
    F = np.array([f[1:5] for f in found], float); sure = np.array([f[5] for f in found])
    for n, f in enumerate(found):
        how = "own"
        dx, dy = f[3], f[4]
        others = np.flatnonzero(sure & (np.arange(len(found)) != n))
        if len(others):
            near = others[np.argsort(np.hypot(F[others, 0] - f[1], F[others, 1] - f[2]))[: p["neighbours"]]]
            mx, my = np.median(F[near, 2]), np.median(F[near, 3])
            if not f[5] or abs(dx - mx) > p["agree_px"] or abs(dy - my) > p["agree_px"]:
                dx, dy, how = int(round(mx)), int(round(my)), "neighbours"
        elif not f[5]:
            dx = dy = 0; how = "none"
        shifts[f[0]] = (dx, dy, how)
        if dx or dy:
            yy, xx = np.nonzero(on & (bid == f[0]))
            out[yy, xx] = painting[np.clip(yy + dy, 0, H - 1), np.clip(xx + dx, 0, W - 1)]
    return out, shifts


def greenish(a):
    """A tree painted in front of a wall: not the wall's colour, not its texture."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return (g > r * 1.06) & (g > b * 1.12)


def band_colour(px, band):
    y = lum(px)
    lo, hi = np.quantile(y, band)
    s = px[(y >= lo) & (y <= hi)]
    return s.mean(0) if len(s) else px.mean(0)


def transfer(code, painting, g: dict, have=None, p: dict = P, colours=None):
    """The code art with each building's wall and roof colour and fine texture taken from the (registered)
    painting. Returns (rgb, {"parts", "skipped", "changed": share of the window's pixels})."""
    from scipy import ndimage as ndi
    code = code.astype(float); src = painting.astype(float)
    bid, cls, face, seg = segments(g)
    on = np.isin(g["which"], PAINT_LAYERS) & np.isin(cls, (WALL, PART, ROOF))
    if have is not None:
        on &= have
    out = code.copy()
    ys, yc = lum(src) + 1.0, lum(code) + 1.0
    lys = np.log(ys)
    tree = greenish(src)
    ink = yc < p["ink"]
    e = geometry_edges(g) | ink
    near = ndi.binary_dilation(e, iterations=p["edge_px"])
    fade = np.clip(ndi.distance_transform_edt(~e) / (p["edge_px"] + 2.0), 0, 1)
    H, W = seg.shape
    pad = int(3 * p["sigma"])
    st = {"parts": 0, "skipped": 0}
    changed = np.zeros(seg.shape, bool)
    for b in np.unique(bid[on]):
        mb = on & (bid == b)
        for kind, classes in (("wall", (WALL, PART)), ("roof", (ROOF,))):
            m = mb & np.isin(cls, classes)
            if m.sum() < p["min_px"]:
                continue
            good = m & ~tree & ~near
            plain = m & ~near
            if good.sum() < p["min_px"] * 0.5 or not plain.any():
                st["skipped"] += 1
                continue
            target = band_colour(src[good], p["band_" + kind])
            if colours and (int(b), kind) in colours:                  # the building's one colour (one_colour)
                target = np.asarray(colours[(int(b), kind)], float)
            base_c = np.median(code[plain], axis=0)
            rows = np.flatnonzero(m.any(1)); cols = np.flatnonzero(m.any(0))
            r0, c0 = max(rows[0] - pad, 0), max(cols[0] - pad, 0)
            r1, c1 = min(rows[-1] + 1 + pad, H), min(cols[-1] + 1 + pad, W)
            sl = (slice(r0, r1), slice(c0, c1))
            D = np.zeros((r1 - r0, c1 - c0))
            for f in np.unique(face[sl][m[sl]]):
                mf = (m[sl] & (face[sl] == f) & ~tree[sl]).astype(float)
                if mf.sum() < 40:
                    continue
                num = ndi.gaussian_filter(lys[sl] * mf, p["sigma"]); den = ndi.gaussian_filter(mf, p["sigma"])
                D += np.where(mf > 0, lys[sl] - num / np.maximum(den, 1e-3), 0)
            lo, hi = p["clip_" + kind]
            D = np.clip(D * p["k_" + kind], lo, hi) * fade[sl]
            mod = np.clip(yc[sl] / (lum(base_c) + 1.0), *p["code_mod"])
            val = target[None, None, :] * (mod * np.exp(D))[..., None]
            w = m[sl] & ~ink[sl]
            sub = out[sl]; sub[w] = val[w]; out[sl] = sub
            sc = changed[sl]; sc[w] = True; changed[sl] = sc
            st["parts"] += 1
    st["changed"] = round(float(changed.mean()), 4)
    return np.clip(np.round(out), 0, 255).astype(np.uint8), st


def photo_shadow(g: dict, meta: dict, rel: Path | None = None) -> np.ndarray:
    """Where the 3D model puts a cast shadow for the aerial photo's sun (params g1.shadow_photo_sun, the sun the
    paintings' input was photographed under), per pixel of a window: layers/light.py's reference on the release's
    own shadow height map."""
    from v2.checks.g1_checks import _when
    from v2.config import params
    from v2.layers.common import unpack_bin, unproject
    from v2.layers.light import HeightMap, shadow_ref, sun_vector
    rel = rel or release()
    li = json.loads((rel / "light.json").read_text())
    shape = (li["height"], li["width"], 4)
    hm = HeightMap.decode(unpack_bin((rel / "shadow_a.bin").read_bytes(), shape, np.uint8),
                          unpack_bin((rel / "shadow_b.bin").read_bytes(), shape, np.uint8),
                          li["e0"], li["n0"], li["step"], li["zbase"])
    az, el, _sv = sun_vector(_when(params()["g1"]["shadow_photo_sun"]))
    n = g["which"].shape[0]; step = meta["size"] / n
    PX, PY = np.meshgrid(meta["x0"] + (np.arange(n) + 0.5) * step, meta["y0"] + (np.arange(n) + 0.5) * step)
    ok = g["depth"] < 1e8
    cast = np.zeros(ok.shape, bool)
    e, nn, z = unproject(PX[ok], PY[ok], g["depth"][ok])
    cast[ok] = shadow_ref(hm, e, nn, z, az, el) > 0
    return cast


def delit(code, painting, g: dict, cast=None, sigma=24.0, clip=(-1.1, 0.5), dark=0.6, p: dict = P, base=None,
          own_windows=True, win_dark=0.3, colours=None, two_tone=None, stats=None):
    """The painting used more directly: inside each face the (registered) painting keeps all its own drawing, its
    windows, dormers and joints, and its colour changes; only the face's light is replaced.

    A face's light is its own tone near each pixel: the mean brightness (of the logarithm) over `sigma` px of the
    face's pixels, leaving out those far darker than their surroundings (by `dark`, about half as bright: the
    windows drawn on it, which would otherwise make a windowed wall come out brighter than a plain one). Beside it
    the surface's own tint, the median over the face's brighter 60%. A tighter `dark` (0.25) measured less even on
    the paintings: on a wall drawn in several tones it follows the highlights, not the surface. Every pixel keeps its brightness and its
    tint relative to those, set on one colour per building part (the walls' from the lit side). So a wall the
    painting shaded comes out as its lit neighbour, its windows still dark and blue, and a shadow cast across a
    face fades out over about sigma. Where `cast` (the model's cast shadow for the photo's sun, photo_shadow) is
    given, the two sides of its edge are levelled apart, so the edge does not smear. The code art keeps the
    ground, the trees and the ink on the borders between faces and buildings; its own windows are not drawn.

    `base`: what stays where the painting is not used (default the code art): a tree the model painted in front
    of a wall, a face too small to measure. `own_windows=False`: the painting's windows are not kept either (a
    wall's pixels darker than its tone by `win_dark`, closed over their glazing bars): the base shows there, for
    a picture that gets the code art's windows drawn in afterwards (target).

    `two_tone`: a face whose tone in the painting differs across it by more than this (the 5th to the 95th
    percentile of the logarithm; 0.25 is a quarter brighter) is not taken from the painting at all, and the base
    shows: the painting has a shadow's edge on it that the model did not predict, or it drew something else
    there (a building it put elsewhere, the ground beside it). `stats`: a dict that gets the count of faces
    used and left out, and their pixels."""
    from scipy import ndimage as ndi
    code = code.astype(float); src = painting.astype(float) + 1.0
    bid, cls, face, _seg = segments(g)
    on = np.isin(g["which"], PAINT_LAYERS)
    roof = np.isin(cls, (ROOF,)).astype(np.int64)
    out = code.copy() if base is None else np.asarray(base, float).copy()
    tree = greenish(src)
    seg2 = (bid * 2 + roof) * 8000 + face + g["which"].astype(np.int64) * (1 << 50)
    e = np.zeros(seg2.shape, bool)
    e[:, 1:] |= seg2[:, 1:] != seg2[:, :-1]; e[1:, :] |= seg2[1:, :] != seg2[:-1, :]
    border = ndi.binary_dilation(e, iterations=1)
    ly = np.log(lum(src))
    chroma = src / lum(src)[..., None]
    side = np.zeros(on.shape, np.int64) if cast is None else cast.astype(np.int64)
    H, W = on.shape; pad = int(2.5 * sigma)
    for b in np.unique(bid[on]):
        mb = on & (bid == b)
        for kind in (0, 1):
            m = mb & (roof == kind)
            if m.sum() < p["min_px"]:
                continue
            good = m & ~tree & ~border & np.isin(cls, (WALL, PART, ROOF))
            if good.sum() < p["min_px"] * 0.5:
                continue
            target = band_colour(src[good] - 1.0, p["band_roof" if kind else "band_wall"])
            if colours and (int(b), "roof" if kind else "wall") in colours:
                target = np.asarray(colours[(int(b), "roof" if kind else "wall")], float)
            rows = np.flatnonzero(m.any(1)); cols = np.flatnonzero(m.any(0))
            r0, c0 = max(rows[0] - pad, 0), max(cols[0] - pad, 0)
            r1, c1 = min(rows[-1] + 1 + pad, H), min(cols[-1] + 1 + pad, W)
            sl = (slice(r0, r1), slice(c0, c1))
            lys, chs = ly[sl], chroma[sl]
            for f in np.unique(face[sl][m[sl]]):
                whole = m[sl] & (face[sl] == f) & ~tree[sl]
                if whole.sum() < 40:
                    continue
                v = lys[whole]
                tint = np.median(chs[whole & (lys >= np.quantile(v, 0.4))], axis=0)
                parts = [whole & (side[sl] == k) for k in (0, 1)]
                if min(x.sum() for x in parts) < 0.15 * whole.sum():
                    parts = [whole]                         # no real shadow edge on this face
                for mf in parts:
                    w = mf.astype(float)
                    m1 = ndi.gaussian_filter(lys * w, sigma) / np.maximum(ndi.gaussian_filter(w, sigma), 1e-3)
                    w2 = w * (lys > m1 - dark)
                    den = ndi.gaussian_filter(w2, sigma)
                    tone = np.where(den > 0.02, ndi.gaussian_filter(lys * w2, sigma) / np.maximum(den, 1e-3), m1)
                    if stats is not None:
                        stats["faces"] = stats.get("faces", 0) + 1; stats["px"] = stats.get("px", 0) + int(mf.sum())
                    if two_tone is not None and mf.sum() >= 400:
                        lo, hi = np.quantile(tone[mf], (0.05, 0.95))
                        if hi - lo > two_tone:
                            if stats is not None:
                                stats["left_out"] = stats.get("left_out", 0) + 1
                                stats["left_out_px"] = stats.get("left_out_px", 0) + int(mf.sum())
                            continue
                    d = np.clip(lys - tone, *clip)
                    crel = np.clip(chs / tint[None, None, :], 0.6, 1.6) ** 0.8
                    val = target[None, None, :] * np.exp(d)[..., None] * crel
                    put = mf
                    if not own_windows and kind == 0:
                        glass = ndi.binary_closing(mf & (lys < tone - win_dark), iterations=2) & mf
                        put = mf & ~ndi.binary_dilation(glass, iterations=1)
                    sub = out[sl]; sub[put] = val[put]; out[sl] = sub
    ink = (lum(code) + 1.0 < p["ink"]) & border & on
    out[ink] = code[ink]
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


# ------------------------------------------------------------------------------------------------ the numbers
def line_scores(source: str = "T1", scene_folder=None) -> dict:
    """Gate #6's line score (the model's building edges and window rows found within 1 px, paintcheck.line_score)
    on each p125 window: the code art, each painting as painted, and each painting registered. Pooled per kind."""
    from v2.bakeoff import paintcheck as PC
    if scene_folder is None:
        from v2.build.stages import graph
        scene_folder = graph().folder("scene", AREA)
    out, pool = {}, {}
    for b in BLOCKS:
        name = f"{b}_p125"
        code, g, meta = load_input(name)
        rows = {"code": PC.line_score(scene_folder, meta["x0"], meta["y0"], code, g)}
        for k in ((0,) if source == "free" else range(len(SEEDS))):
            painting, _have = painting_for(name, source, k)
            if painting is None:
                continue
            rows[f"painting_{k}"] = PC.line_score(scene_folder, meta["x0"], meta["y0"], painting, g)
            rows[f"registered_{k}"] = PC.line_score(scene_folder, meta["x0"], meta["y0"], register(code, painting, g)[0], g)
        out[name] = rows
        for key, r in rows.items():
            for kind, (seen, hit) in r.items():
                a = pool.setdefault(key, {}).setdefault(kind, [0, 0]); a[0] += seen; a[1] += hit
    return {"windows": out, "pooled": {k: {kind: {"seen": v[0], "share": round(v[1] / max(v[0], 1), 4)} for kind, v in r.items()}
                                       for k, r in pool.items()}}


def flat_by_part(rgb, g: dict, min_px=600) -> dict:
    """How even the result is across each building's walls: the spread of the faces' median luminance round the
    building's own (the code art's is 0 by construction where one material covers the walls). A painted shadow or a
    lit side would show here."""
    bid, cls, face, _seg = segments(g)
    on = np.isin(g["which"], PAINT_LAYERS) & np.isin(cls, (WALL, PART))
    y = lum(rgb.astype(float)); worst = []
    for b in np.unique(bid[on]):
        mb = on & (bid == b)
        meds = [np.median(y[mb & (face == f)]) for f in np.unique(face[mb]) if (mb & (face == f)).sum() >= min_px]
        if len(meds) >= 2:
            worst.append((max(meds) - min(meds)) / (np.mean(meds) + 1e-6))
    return {"buildings": len(worst), "worst": round(float(max(worst)), 4) if worst else 0.0,
            "median": round(float(np.median(worst)), 4) if worst else 0.0}


def ink_changed(code, out, p: dict = P) -> int:
    """Pixels of the code art's ink that the result changed: 0 by construction (the lines are the code's)."""
    ink = lum(code.astype(float)) + 1.0 < p["ink"]
    return int((np.abs(out.astype(int) - code.astype(int)).sum(-1)[ink] > 0).sum())


def lit(rgb, g: dict, when=dt.datetime(2026, 6, 24, 11, 0, tzinfo=dt.timezone.utc)):
    """A preview only: the art under the day's sun on each face (no cast shadows), to set an unlit result beside
    v1's painted light. The viewer's own light pass is the real one."""
    from v2.config.sun import direction_en
    s = np.asarray(direction_en(when), float)                # east, north, up: the normals' frame
    n = np.asarray(g["normal"], float)
    k = np.clip(n @ s, 0, 1)
    k = np.where(np.linalg.norm(n, axis=-1) > 0.5, 0.62 + 0.55 * k, 1.0)
    return np.clip(rgb.astype(float) * k[..., None], 0, 255).astype(np.uint8)


# ------------------------------------------------------------------------------------------------ T1's inputs
def input_names() -> list:
    return [f"{b}_{s}" for b in BLOCKS for s in SCALES]


def window_of(name: str):
    """(x0, y0, size in v2 px, v2 px per model px) of an input."""
    b, s = name.rsplit("_", 1)
    x0, y0 = BLOCKS[b]
    if s == "p250":
        return x0, y0, BLOCK, 2
    return x0 + BLOCK // 4, y0 + BLOCK // 4, WIN, 1


def make_inputs(dst: Path | None = None) -> dict:
    """T1's control images: for each block and scale, control 1 = v1's capture at the model's scale
    (<name>.unlit.png, the name pod/paint.py reads), control 2 = v2's line layout (<name>.layout.png); and the
    code art, its geometry and the place (<name>.code.png, .geom.npz, .json) for the transfer afterwards."""
    dst = dst or base() / "inputs"
    dst.mkdir(parents=True, exist_ok=True)
    rel = release()
    out = {}
    for name in input_names():
        x0, y0, size, step = window_of(name)
        code, g = code_window(x0, y0, size, rel)
        cap = v1_capture(x0, y0, size, WIN)
        lay = layout_of(g, step)
        assert cap.shape[:2] == (WIN, WIN) and lay.shape == (WIN, WIN), (name, cap.shape, lay.shape)
        Image.fromarray(cap).save(dst / f"{name}.unlit.png")
        Image.fromarray(lay).save(dst / f"{name}.layout.png")
        Image.fromarray(code).save(dst / f"{name}.code.png")
        Image.fromarray(trees_over(x0, y0, size, g, rel)).save(dst / f"{name}.trees.png")
        np.savez_compressed(dst / f"{name}.geom.npz", ids=g["ids"], which=g["which"],
                            normal=g["normal"].astype(np.float16),
                            depth=np.where(np.isfinite(g["depth"]), g["depth"], 1e9).astype(np.float32))
        meta = {"x0": x0, "y0": y0, "size": size, "v2_px_per_model_px": step, "m_per_model_px": 0.125 * step,
                "release": rel.name, "paint_share": round(float(np.isin(g["which"], PAINT_LAYERS).mean()), 3)}
        (dst / f"{name}.json").write_text(json.dumps(meta))
        out[name] = meta
    (dst.parent / "inputs.json").write_text(json.dumps({"blocks": BLOCKS, "inputs": out, "seeds": SEEDS}, indent=1))
    return out


def load_input(name: str, src: Path | None = None):
    src = src or base() / "inputs"
    code = np.asarray(Image.open(src / f"{name}.code.png").convert("RGB"))
    z = np.load(src / f"{name}.geom.npz")
    g = {"ids": z["ids"], "which": z["which"], "normal": z["normal"].astype(float), "depth": z["depth"]}
    g["trees"] = np.asarray(Image.open(src / f"{name}.trees.png").convert("RGBA")) if (src / f"{name}.trees.png").exists() else None
    return code, g, json.loads((src / f"{name}.json").read_text())


# ------------------------------------------------------------------------------------------------ run it
def one(name: str, painting: np.ndarray, have=None, src: Path | None = None, p: dict = P) -> dict:
    """Register and transfer one painting (given at the input's own size in v2 pixels) on one input."""
    code, g, meta = load_input(name, src)
    assert painting.shape[:2] == code.shape[:2], (name, painting.shape, code.shape)
    reg, shifts = register(code, painting, g, p)
    out, st = transfer(code, reg, g, have, p)
    mv = [abs(v[0]) + abs(v[1]) for v in shifts.values()]
    res = {**st, "buildings": len(shifts), "shifted": int(sum(1 for v in mv if v)),
           "shift_px_median": float(np.median(mv)) if mv else 0.0, "shift_px_max": int(max(mv)) if mv else 0,
           "flat_code": flat_by_part(code, g), "flat_result": flat_by_part(out, g),
           "flat_painting": flat_by_part(reg, g), "ink_changed": ink_changed(code, out, p),
           "by_neighbours": int(sum(1 for v in shifts.values() if v[2] == "neighbours"))}
    return {"code": code, "g": g, "meta": meta, "registered": reg, "out": out, "res": res}


def painting_for(name: str, source: str, k: int = 0):
    """The painting of an input in v2 pixels: v1's finished art ("free"), or T1's k-th candidate."""
    x0, y0, size, step = window_of(name)
    if source == "free":
        return v1_painted(x0, y0, size)
    f = base() / PAINTED[source] / f"{name}_{k}.png"
    if not f.exists():
        return None, None
    im = Image.open(f).convert("RGB")
    assert im.size == (WIN, WIN), (f, im.size)
    if step > 1:
        im = im.resize((size, size), Image.BICUBIC)
    return np.asarray(im), None


def _label(im: np.ndarray, text: str) -> np.ndarray:
    from PIL import ImageDraw
    pim = Image.fromarray(im); d = ImageDraw.Draw(pim)
    d.rectangle((0, 0, 8 + 7 * len(text), 18), fill=(255, 255, 255)); d.text((4, 3), text, fill=(0, 0, 0))
    return np.asarray(pim)


def _row(ims, gap=6):
    h = max(i.shape[0] for i in ims); w = sum(i.shape[1] for i in ims) + gap * (len(ims) - 1)
    c = np.full((h, w, 3), 255, np.uint8); x = 0
    for i in ims:
        c[:i.shape[0], x:x + i.shape[1]] = i; x += i.shape[1] + gap
    return c


def _save(im: np.ndarray, dst: Path, max_bytes=950_000):
    dst.parent.mkdir(parents=True, exist_ok=True)
    pim = Image.fromarray(im)
    for q in (88, 82, 76, 70, 62, 54):
        pim.save(dst, quality=q)
        if dst.stat().st_size <= max_bytes:
            return
    raise RuntimeError(f"{dst} is over {max_bytes} bytes")


def sheet_row(r: dict, crop=None, shown=512) -> np.ndarray:
    """code art | the result | the painting it came from, all under the preview sun except the painting."""
    c = crop or (slice(None), slice(None))

    def shown_as(rgb):
        im = lit(rgb, r["g"]); t = r["g"].get("trees")
        if t is not None:
            im = np.where(t[..., 3:] > 0, t[..., :3], im)
        return im[c]
    ims = [_label(shown_as(r["code"]), "code art"), _label(shown_as(r["out"]), "transfer"),
           _label(r["registered"][c], "painting")]
    ims = [np.asarray(Image.fromarray(i).resize((shown, shown), Image.LANCZOS)) if i.shape[0] != shown else i for i in ims]
    return _row(ims)


def run(source: str = "free", img: Path | None = None, write=True) -> dict:
    """Every input through register and transfer; the numbers (checks/<source>.json) and two sheets per source:
    whole windows, and each p125 window's central 64 m at full size."""
    img = img or V2 / "docs" / "img"
    res, rows, zooms, levels = {}, [], [], []
    cands = (0,) if source == "free" else tuple(range(len(SEEDS)))
    for name in input_names():
        for k in cands:
            painting, have = painting_for(name, source, k)
            if painting is None:
                continue
            r = one(name, painting, have)
            key = name if source == "free" else f"{name}_{k}"
            res[key] = r["res"]
            if k == 0:
                if name.endswith("p250"):
                    rows.append(sheet_row(r, shown=400))
                else:
                    zooms.append(sheet_row(r, crop=(slice(256, 768), slice(256, 768))))
                    if source != "free":                 # four ways: code, transfer, painting without its light, painting
                        c = (slice(256, 768), slice(256, 768))
                        dl = delit(r["code"], r["registered"], r["g"], photo_shadow(r["g"], r["meta"]))
                        res[key]["flat_delit"] = flat_by_part(dl, r["g"])
                        t = r["g"].get("trees")

                        def shown(rgb, r=r, t=t, c=c):
                            im = lit(rgb, r["g"])
                            return (np.where(t[..., 3:] > 0, t[..., :3], im) if t is not None else im)[c]
                        ims = [_label(shown(r["code"]), "code art"), _label(shown(r["out"]), "light transfer"),
                               _label(shown(dl), "painting, light removed"), _label(painting[c], "painting as painted")]
                        levels.append(_row([np.asarray(Image.fromarray(i).resize((448, 448), Image.LANCZOS)) for i in ims]))
    out = {"source": source, "params": P, "inputs": res}
    if source != "free" and res:
        out["lines"] = line_scores(source)
    if write and res:
        (base() / "checks").mkdir(parents=True, exist_ok=True)
        (base() / "checks" / f"{source}.json").write_text(json.dumps(out, indent=1))
        tag = "v1art" if source == "free" else source.lower()
        if rows:
            _save(np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=255) for r in rows]),
                  img / f"test_detail_{tag}_blocks.jpg")
        for i in range(0, len(levels), 3):
            _save(np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=255) for r in levels[i:i + 3]]),
                  img / f"test_detail_{tag}_levels_{i // 3 + 1}.jpg")
        if zooms:
            for i in range(0, len(zooms), 3):
                _save(np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=255) for r in zooms[i:i + 3]]),
                      img / f"test_detail_{tag}_close_{i // 3 + 1}.jpg")
    return out


def pairs(a: str = "T1", b: str = "T2", img: Path | None = None, write=True) -> dict:
    """Two paid runs that differ by one thing (T1 and T2 by the prompt, T2 and T3 by the first control image),
    painting by painting (same block, scale and seed): how even
    each is across a building's walls as painted (flat_by_part of the registered painting), and sheets of the
    first candidate: each p125 window's central 64 m (a, b, b with its light removed, the code art; the last two
    under the preview sun) and each whole block (a, b)."""
    img = img or V2 / "docs" / "img"
    res, close, blocks = {}, [], []
    for name in input_names():
        code, g, meta = load_input(name)
        for k in range(len(SEEDS)):
            pa, pb = painting_for(name, a, k)[0], painting_for(name, b, k)[0]
            if pa is None or pb is None:
                continue
            ra, rb = register(code, pa, g)[0], register(code, pb, g)[0]
            fa, fb = flat_by_part(ra, g), flat_by_part(rb, g)
            ya, yb = lum(pa.astype(float)), lum(pb.astype(float))
            on = np.isin(g["which"], PAINT_LAYERS)
            res[f"{name}_{k}"] = {a: fa, b: fb, "luminance": {a: round(float(ya[on].mean()), 1), b: round(float(yb[on].mean()), 1)},
                                  "differ_mean": round(float(np.abs(pa.astype(float) - pb.astype(float)).mean()), 2)}
            if k:
                continue
            if name.endswith("p250"):
                blocks.append(_row([np.asarray(Image.fromarray(_label(i, t)).resize((640, 640), Image.LANCZOS))
                                    for i, t in ((pa, LABEL[a]), (pb, LABEL[b]))]))
            else:
                c = (slice(256, 768), slice(256, 768))
                dl = delit(code, rb, g, photo_shadow(g, meta))
                t = g.get("trees")

                def shown(rgb, g=g, t=t, c=c):
                    im = lit(rgb, g)
                    return (np.where(t[..., 3:] > 0, t[..., :3], im) if t is not None else im)[c]
                ims = [_label(pa[c], LABEL[a]), _label(pb[c], LABEL[b]),
                       _label(shown(dl), f"{b}, light removed"), _label(shown(code), "code art")]
                close.append(_row([np.asarray(Image.fromarray(i).resize((448, 448), Image.LANCZOS)) for i in ims]))
    out = {"a": a, "b": b, "inputs": res}
    if write and res:
        (base() / "checks").mkdir(parents=True, exist_ok=True)
        (base() / "checks" / f"pairs_{a}_{b}.json").write_text(json.dumps(out, indent=1))
        tag = f"{a}_{b}".lower()
        for kind, rows, per in (("close", close, 3), ("blocks", blocks, 2)):
            for i in range(0, len(rows), per):
                _save(np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=255) for r in rows[i:i + per]]),
                      img / f"test_detail_{tag}_{kind}_{i // per + 1}.jpg")
    return out


# ------------------------------------------------------------------------------------------------ T3's inputs
EVEN = {"min_face": 150, "top": 0.15, "ambient": 0.3, "explain": (1.6, 0.08), "gain": (0.0, 0.8), "dark": 0.5, "split": 0.15, "soften": 0.45,
        "reach": 24, "sigma": 32.0, "ground_dark": 0.22, "ground_gain": 0.9, "ring": 10, "min_region": 60}


def _tone(lys, m, dark):
    """A face's tone: the median brightness (logarithm) of its pixels, leaving out those far darker than the face
    (the windows on it)."""
    v = lys[m]
    med = np.median(v)
    keep = v > med - dark
    return float(np.median(v[keep])) if keep.any() else float(med)


def photo_sun():
    """The aerial photo's sun (params g1.shadow_photo_sun) as a unit vector (east, north, up): the frame a
    window's normals are in. (T3's inputs were made with the camera-frame vector by mistake: PHASE3_REPORT.md
    section 18.1.)"""
    from v2.checks.g1_checks import _when
    from v2.config import params
    from v2.layers.light import sun_vector
    return np.asarray(sun_vector(_when(params()["g1"]["shadow_photo_sun"]))[2], float)


def even_capture(cap, g: dict, cast=None, sun=None, p: dict = EVEN):
    """v1's capture with the aerial photo's light taken down, as an input for the painter (T3). Nothing is
    redrawn: a piece is made brighter as a whole, and keeps its own texture.

    Buildings: on each building, its wall faces, and separately its roof faces, are compared with the faces the
    photo's sun (`sun`, photo_sun) lit most. A face is raised to their tone, but never by more than the
    sun's direction explains, with the allowance `explain` (a face turned from the sun, or one the model puts in
    cast shadow for that sun, `cast` from photo_shadow; a face partly in it is split there). So a dark face that faced the sun stays dark:
    that is its material. A raised face takes the lit faces' tint for the blue of its shade, and its contrast is
    softened (`soften`), since a shaded part of a photo is noisy.
    Ground and everything else: where a shadow is expected (cast, grown by `reach`) and the photo is darker than
    the open ground around it, each connected patch takes the colour of the ground just outside it, keeping its
    own (softened) brightness detail.
    Returns (rgb, {"faces", "raised", "ground_patches", "ground_share"})."""
    from scipy import ndimage as ndi
    src = cap.astype(float) + 1.0
    bid, cls, face, _seg = segments(g)
    on = np.isin(g["which"], PAINT_LAYERS)
    roof = np.isin(cls, (ROOF,)).astype(np.int64)
    ysrc = lum(src); ly = np.log(ysrc)
    lsrc = np.log(src)
    tree = greenish(src)
    side = np.zeros(on.shape, np.int64) if cast is None else cast.astype(np.int64)
    nrm = np.asarray(g["normal"], float)
    facing = np.clip(nrm @ sun, 0, 1) if sun is not None else np.ones(on.shape)
    out = src.copy()
    st = {"faces": 0, "raised": 0, "ground_patches": 0, "ground_share": 0.0}
    key = (bid * 2 + roof) * 8000 + face
    amb = p["ambient"]
    for b in np.unique(bid[on]):
        mb = on & (bid == b)
        rows = np.flatnonzero(mb.any(1)); cols = np.flatnonzero(mb.any(0))
        sl = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1))
        mbs, lys, ks, sds, trs = mb[sl], ly[sl], key[sl], side[sl], tree[sl]
        sub = out[sl]
        for kind in (0, 1):
            mk = mbs & (roof[sl] == kind)
            pieces = []
            for f in np.unique(ks[mk]):
                whole = mk & (ks == f)
                parts = [(whole & (sds == k), k) for k in (0, 1)]
                if min(x.sum() for x, _k in parts) < p["split"] * whole.sum():
                    parts = [(whole, int(sds[whole].mean() > 0.5))]
                for mf, shaded in parts:
                    use = mf & ~trs
                    if use.sum() < p["min_face"]:
                        continue
                    e = amb + (1 - amb) * (0.0 if shaded else float(np.median(facing[sl][use])))
                    pieces.append((mf, use, _tone(lys, use, p["dark"]), int(use.sum()), e))
            if len(pieces) < 2:
                continue
            emax = max(x[4] for x in pieces)
            top = [x for x in pieces if x[4] >= emax - p["top"]]
            wts = np.array([x[3] for x in top], float)
            ref = float(np.sum([x[2] * x[3] for x in top]) / wts.sum())
            eref = float(np.sum([x[4] * x[3] for x in top]) / wts.sum())
            tint = np.sum([np.median(lsrc[sl][x[1]], axis=0) * x[3] for x in top], axis=0) / wts.sum()
            tint = tint - tint.mean()                                  # the lit faces' colour, brightness apart
            for mf, use, t, _n, e in pieces:
                k = float(np.clip(min(ref - t, p["explain"][0] * np.log(eref / e) + p["explain"][1]), *p["gain"]))
                st["faces"] += 1
                if k <= 0.02:
                    continue
                a = k / p["gain"][1]                                   # how much of a shaded face this is
                med = np.median(lsrc[sl][use], axis=0)
                own = med - med.mean()
                keep = 1.0 - p["soften"] * a
                val = (med.mean() + k) + (1 - a) * own + a * tint + (lsrc[sl] - med) * keep
                sub[mf] = np.exp(val)[mf]
                st["raised"] += 1
        out[sl] = sub
    # the ground
    off = ~on
    if cast is not None and cast.any():
        near = ndi.binary_dilation(cast, iterations=p["reach"]) & off
        w = (off & ~near & ~tree).astype(float)
        den = ndi.gaussian_filter(w, p["sigma"])
        wide = ndi.gaussian_filter(ly * w, p["sigma"] * 4) / np.maximum(ndi.gaussian_filter(w, p["sigma"] * 4), 1e-3)
        tone = np.where(den > 0.02, ndi.gaussian_filter(ly * w, p["sigma"]) / np.maximum(den, 1e-3), wide)
        sh = ndi.binary_opening(near & (ly < tone - p["ground_dark"]) & ~tree, iterations=1)
        lab, _n = ndi.label(sh)
        new = np.zeros(src.shape); did = np.zeros(on.shape, bool)
        keep = 1.0 - p["soften"]
        for i, bx in enumerate(ndi.find_objects(lab), start=1):
            r = p["ring"] + 2
            sl = (slice(max(bx[0].start - r, 0), bx[0].stop + r), slice(max(bx[1].start - r, 0), bx[1].stop + r))
            m = lab[sl] == i
            if m.sum() < p["min_region"]:
                continue
            ring = ndi.binary_dilation(m, iterations=p["ring"]) & ~ndi.binary_dilation(m, iterations=2)
            ring &= off[sl] & ~sh[sl] & ~tree[sl]
            if ring.sum() < 30:
                continue
            colour = np.median(lsrc[sl][ring], axis=0)                 # the ground just outside, per channel
            outside = float(np.log(lum(np.exp(colour))))
            mine = float(np.median(ly[sl][m]))
            lift = min(outside - mine, p["ground_gain"])
            if lift <= 0.02:
                continue
            c0 = colour - outside                                      # its tint
            val = (mine + lift) + c0[None, None, :] + ((ly[sl] - mine) * keep)[..., None]
            nw = new[sl]; nw[m] = np.exp(val)[m]; new[sl] = nw
            dd = did[sl]; dd[m] = True; did[sl] = dd
            st["ground_patches"] += 1
        out = np.where(did[..., None], new, out)
        st["ground_share"] = round(float(did.mean()), 4)
    return np.clip(np.round(out - 1.0), 0, 255).astype(np.uint8), st


def make_even_inputs(dst: Path | None = None, img: Path | None = None) -> dict:
    """T3's first control image: T1's capture with the photo's light taken down (even_capture), at the same place
    and size (<data>/.../detail/inputs_even/<name>.unlit.png; the line layout stays T1's). Worked out at v2's
    pixels, where the geometry is, and applied to the capture as T1 had it, so nothing else about it changes.
    Also the numbers (inputs_even.json) and sheets of each whole block, capture beside evened capture."""
    dst = dst or base() / "inputs_even"
    dst.mkdir(parents=True, exist_ok=True)
    img = img or V2 / "docs" / "img"
    sun = photo_sun()
    out, rows = {}, []
    for name in input_names():
        x0, y0, size, step = window_of(name)
        _code, g, meta = load_input(name)
        cap = v1_capture(x0, y0, size, size)
        ev, st = even_capture(cap, g, photo_shadow(g, meta), sun)
        was = np.asarray(Image.open(base() / "inputs" / f"{name}.unlit.png").convert("RGB")).astype(float)
        k = (ev.astype(float) + 1.0) / (cap.astype(float) + 1.0)
        if step > 1:
            k = k.reshape(WIN, step, WIN, step, 3).mean(axis=(1, 3))
        new = np.clip(np.round((was + 1.0) * k - 1.0), 0, 255).astype(np.uint8)
        Image.fromarray(new).save(dst / f"{name}.unlit.png")
        out[name] = {**st, "flat_capture": flat_by_part(cap, g), "flat_evened": flat_by_part(ev, g),
                     "changed": round(float((np.abs(new.astype(int) - was.astype(int)).sum(-1) > 6).mean()), 4)}
        if step > 1:
            rows.append(_row([np.asarray(Image.fromarray(_label(i, t)).resize((640, 640), Image.LANCZOS))
                              for i, t in ((was.astype(np.uint8), f"{name}: capture (T1, T2)"), (new, "evened (T3)"))]))
    (dst.parent / "inputs_even.json").write_text(json.dumps({"params": EVEN, "inputs": out}, indent=1))
    for i in range(0, len(rows), 2):
        _save(np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=255) for r in rows[i:i + 2]]),
              img / f"test_detail_evenin_inputs_{i // 2 + 1}.jpg")
    return out


# ------------------------------------------------------------------------------------------------ training pictures
def level(rgb, g: dict, min_px=150, colours=None):
    """Each building's walls, and its roofs, brought to one median brightness over the four ways its faces turn
    (each side multiplied by one factor; the largest side is the reference). The sides and the pixels are the
    ones the build's own check of a painting measures (dataset.flat_light), so this passes it by construction: it
    says nothing about light left inside a side.

    With `colours` (one_colour), a building in the table is brought to its colour's brightness instead, on every
    side that can be measured, also when it shows one side only: so two paintings of it come out alike."""
    from scipy import ndimage as ndi

    from v2.layers.common import VIEW
    out = rgb.astype(float)
    L = lum(out)
    ids = np.where(np.isin(g["which"], PAINT_LAYERS), g["ids"], 0)
    normal = np.asarray(g["normal"], float)
    cls = ids & 255; obj = ids >> 8
    h = np.hypot(normal[..., 0], normal[..., 1])
    quad = (((np.degrees(np.arctan2(normal[..., 0], normal[..., 1])) % 360 + 45) % 360) // 90).astype(int)
    key = ids.astype(np.int64) * 4 + quad
    edge = np.zeros(key.shape, bool)
    edge[:, 1:] |= key[:, 1:] != key[:, :-1]; edge[:, :-1] |= key[:, 1:] != key[:, :-1]
    edge[1:, :] |= key[1:, :] != key[:-1, :]; edge[:-1, :] |= key[1:, :] != key[:-1, :]
    inner = ~ndi.binary_dilation(edge, iterations=2) & (-(normal @ VIEW) > 0.3)
    for c in (WALL, ROOF):
        m = (cls == c) & (h > (0.7 if c == WALL else 0.1))
        for o in np.unique(obj[m & inner]):
            mo = m & (obj == o)
            sides = [(q, mo & inner & (quad == q)) for q in range(4)]
            qs = [(q, np.median(L[sel]), int(sel.sum())) for q, sel in sides if sel.sum() >= min_px]
            key = (int(o), "wall" if c == WALL else "roof")
            if colours and key in colours and qs:
                ref = float(lum(np.asarray(colours[key], float)))
            elif len(qs) >= 2:
                ref = max(qs, key=lambda x: x[2])[1]
            else:
                continue
            for q, med, _n in qs:
                out[mo & (quad == q)] *= ref / max(med, 1e-6)
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def part_colours(reg, g: dict, p: dict = P) -> dict:
    """What a (placed) painting gives each building for a colour: {(building, "wall" | "roof"): (rgb, pixels)},
    the colour delit would set it on (the painting's brighter band, trees and borders left out)."""
    from scipy import ndimage as ndi
    src = np.asarray(reg, float)
    bid, cls, face, _seg = segments(g)
    on = np.isin(g["which"], PAINT_LAYERS)
    roof = np.isin(cls, (ROOF,)).astype(np.int64)
    seg2 = (bid * 2 + roof) * 8000 + face + g["which"].astype(np.int64) * (1 << 50)
    e = np.zeros(seg2.shape, bool)
    e[:, 1:] |= seg2[:, 1:] != seg2[:, :-1]; e[1:, :] |= seg2[1:, :] != seg2[:-1, :]
    good = on & ~greenish(src + 1.0) & ~ndi.binary_dilation(e, iterations=1) & np.isin(cls, (WALL, PART, ROOF))
    key = np.where(good, bid * 2 + roof + 1, 0)
    u, inv = np.unique(key, return_inverse=True)
    lab = inv.reshape(key.shape)
    out = {}
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        if sl is None or i >= len(u) or u[i] == 0:
            continue
        m = lab[sl] == i
        if m.sum() < p["min_px"] * 0.5:
            continue
        k = int(u[i]) - 1
        kind = "roof" if k % 2 else "wall"
        out[(k // 2, kind)] = (band_colour(src[sl][m], p["band_" + kind]), int(m.sum()))
    return out


def one_colour(tables: dict) -> dict:
    """One colour per building part for all the paintings that show it: the colour of the painting that shows the
    most of it (a painting at v2's own scale counts a tenth more than one at half scale; then the first). A
    building is not averaged between paintings: two paintings may give it two hues, and their mean is neither.
    `tables`: {painting name: part_colours}. Returns {(building, kind): rgb}."""
    best = {}
    for name in sorted(tables, key=lambda n: (not n.rsplit("_", 1)[0].endswith("p125"), n)):
        w = 1.1 if name.rsplit("_", 1)[0].endswith("p125") else 1.0
        for key, (rgb, n) in tables[name].items():
            if key not in best or n * w > best[key][1]:
                best[key] = (np.asarray(rgb, float), n * w, name)
    return {k: v[0] for k, v in best.items()}


TWO_TONE = 0.25                                  # delit's two_tone for a target


def target(code, painting, g: dict, meta: dict, colours=None, reg=None, two_tone=TWO_TONE) -> dict:
    """A painting made into a picture the build's checks of a painting can pass: placed per building (register),
    its light removed (delit), each building's sides levelled (level), and the code art's own windows drawn in
    (the painting's windows drift from the model's, so they are left out). Where the painting cannot be used (its
    own windows, a tree it painted in front of a wall) the code art shows in the painting's colours (transfer).
    With `colours` (one_colour) each building takes its one colour, whichever painting this is. `reg`: the
    painting already placed. Returns every stage."""
    from scipy import ndimage as ndi
    if reg is None:
        reg = register(code, painting, g)[0]
    under = transfer(code, reg, g, colours=colours)[0]  # the code art in the painting's colours: what shows where
    st = {}
    dl = delit(code, reg, g, photo_shadow(g, meta), base=under, own_windows=False, colours=colours,    # it is not used
               two_tone=two_tone, stats=st)
    lv = level(dl, g, colours=colours)
    on = np.isin(g["which"], PAINT_LAYERS)
    win = ndi.binary_dilation(np.isin(g["ids"] & 255, (12, 13, 14)) & on, iterations=1) & on
    out = lv.copy(); out[win] = code[win]
    return {"registered": reg, "delit": dl, "levelled": lv, "target": out, "faces": st}


def painting_checks(rgb, g: dict, meta: dict, scene_folder) -> dict:
    """The build's own checks of a painting that need no detector (paintcheck): flat light per building (5%), and
    on a window at v2's scale the line score (95% of building edges and of window rows)."""
    from v2.bakeoff import paintcheck as PC
    from v2.bakeoff.dataset import flat_light
    ids = np.where(g["which"] == PC.B_LAYER, g["ids"], 0)
    worst, bad = flat_light(rgb, ids, g["normal"])
    r = {"flat_worst": worst, "flat_failing": len(bad), "buildings": int(len(np.unique((ids >> 8)[ids > 0])))}
    if rgb.shape[0] == WIN:
        for k, (seen, hit) in PC.line_score(scene_folder, meta["x0"], meta["y0"], rgb, g).items():
            r[k] = round(hit / seen, 4) if seen else None
    return r


def targets(source: str = "T1", img: Path | None = None, write=True, one=True) -> dict:
    """Every painting of a paid run as painted (placed), with its light removed, levelled, and as a target: the
    build's checks on each (checks/targets_<source>.json), and sheets of the first candidate of each p125 window
    (as painted, levelled, target, code art; none lit). `one`: each building takes one colour for all the
    paintings of the run that show it (one_colour); without it, each painting's own."""
    from v2.build.stages import graph
    img = img or V2 / "docs" / "img"
    scene_folder = graph().folder("scene", AREA)
    res, rows = {}, []
    # first every painting placed, and what it would give each building for a colour; then one colour a building
    rdir = base() / "registered" / source
    rdir.mkdir(parents=True, exist_ok=True)
    tables = {}
    for name in input_names():
        code, g, meta = load_input(name)
        for k in range(len(SEEDS)):
            painting = painting_for(name, source, k)[0]
            if painting is None:
                continue
            reg = register(code, painting, g)[0]
            Image.fromarray(reg).save(rdir / f"{name}_{k}.png")
            tables[f"{name}_{k}"] = part_colours(reg, g)
    colours = one_colour(tables) if one else None
    for name in input_names():
        code, g, meta = load_input(name)
        for k in range(len(SEEDS)):
            if f"{name}_{k}" not in tables:
                continue
            reg = np.asarray(Image.open(rdir / f"{name}_{k}.png").convert("RGB"))
            t = target(code, None, g, meta, colours=colours, reg=reg)
            res[f"{name}_{k}"] = {s: painting_checks(t[s], g, meta, scene_folder) for s in t if s != "faces"}
            res[f"{name}_{k}"]["faces"] = t["faces"]
            if write:                                      # kept for the detector, the seams and the viewer
                (base() / "targets" / source).mkdir(parents=True, exist_ok=True)
                Image.fromarray(t["target"]).save(base() / "targets" / source / f"{name}_{k}.png")
            if k == 0 and name.endswith("p125"):
                c = (slice(256, 768), slice(256, 768))
                ims = [_label(t["registered"][c], f"{source}: as painted"), _label(t["levelled"][c], "light removed, levelled"),
                       _label(t["target"][c], "with the code's windows"), _label(code[c], "code art")]
                rows.append(_row([np.asarray(Image.fromarray(i).resize((448, 448), Image.LANCZOS)) for i in ims]))
    out = {"source": source, "one_colour": bool(one), "building_parts_coloured": len(colours or {}), "inputs": res}
    if write and res:
        (base() / "checks").mkdir(parents=True, exist_ok=True)
        (base() / "checks" / f"targets_{source}.json").write_text(json.dumps(out, indent=1))
        for i in range(0, len(rows), 3):
            _save(np.concatenate([np.pad(r, ((0, 6), (0, 0), (0, 0)), constant_values=255) for r in rows[i:i + 3]]),
                  img / f"test_detail_targets_{source.lower()}_{i // 3 + 1}.jpg")
    return out


def _target_png(source, name, k):
    f = base() / "targets" / source / f"{name}_{k}.png"
    return np.asarray(Image.open(f).convert("RGB")) if f.exists() else None


def cars(source: str = "T1") -> dict:
    """The build's vehicle detector (paintcheck.owl: v1's OWLv2, the gate's queries, threshold and box sizes) on
    every target of a run. Only the painted layers come from a painting, so this finds what a painting put on a
    building or a structure, not what it painted on a road."""
    from v2.bakeoff import paintcheck as PC
    d = base() / "targets" / source
    files = sorted(d.glob("*.png"))
    det = PC.owl(files, base() / "checks" / f"owl_{source}", mpp=0.125)
    out = {"images": len(files), "with_vehicles": {k: len(v) for k, v in det["by_file"].items()}, "max_score": det["max_score"]}
    (base() / "checks" / f"cars_{source}.json").write_text(json.dumps(out, indent=1))
    return out


def seams(source: str = "T1", min_px=600) -> dict:
    """What makes a seam: how far one building's colour differs between two paintings of it. Per building part
    (walls, roofs) with at least min_px pixels, the difference of its median brightness, relative, between (a) the
    two candidates of a window, (b) the p125 window and the same ground in the p250 window, and (c) two blocks on
    the ground they share (five pairs of the trial's six blocks overlap: these are paintings of neighbouring
    windows in the real sense)."""
    def parts(rgb, g):
        bid, cls, _f, _s = segments(g)
        on = np.isin(g["which"], PAINT_LAYERS)
        y = lum(rgb.astype(float)); out = {}
        for kind, classes in (("wall", (WALL, PART)), ("roof", (ROOF,))):
            m = on & np.isin(cls, classes)
            for b in np.unique(bid[m]):
                mb = m & (bid == b)
                if mb.sum() >= min_px:
                    out[(int(b), kind)] = float(np.median(y[mb]))
        return out

    def diff(a, b):
        return [abs(a[k] - b[k]) / (0.5 * (a[k] + b[k]) + 1e-6) for k in a if k in b]

    pairs_, scales = [], []
    for name in input_names():
        _code, g, _meta = load_input(name)
        t0, t1 = _target_png(source, name, 0), _target_png(source, name, 1)
        if t0 is None or t1 is None:
            continue
        pairs_ += diff(parts(t0, g), parts(t1, g))
        if name.endswith("p125"):
            big = _target_png(source, name.replace("p125", "p250"), 0)
            if big is not None:
                c = (slice(BLOCK // 4, BLOCK // 4 + WIN), slice(BLOCK // 4, BLOCK // 4 + WIN))
                scales += diff(parts(t0, g), parts(big[c], g))

    def summary(v):
        v = np.asarray(v)
        return {"parts": int(len(v)), "median": round(float(np.median(v)), 4), "p90": round(float(np.quantile(v, 0.9)), 4),
                "over_5_percent": round(float((v > 0.05).mean()), 4)} if len(v) else {"parts": 0}
    blocks_ = []
    names = list(BLOCKS)
    for i, a in enumerate(names):                          # two blocks' paintings of the ground they share
        for b in names[i + 1:]:
            (ax, ay), (bx, by) = BLOCKS[a], BLOCKS[b]
            x0, y0, x1, y1 = max(ax, bx), max(ay, by), min(ax, bx) + BLOCK, min(ay, by) + BLOCK
            ta, tb = _target_png(source, f"{a}_p250", 0), _target_png(source, f"{b}_p250", 0)
            if x1 <= x0 or y1 <= y0 or ta is None or tb is None:
                continue
            _c, g, _m = load_input(f"{a}_p250")
            sa = (slice(y0 - ay, y1 - ay), slice(x0 - ax, x1 - ax)); sb = (slice(y0 - by, y1 - by), slice(x0 - bx, x1 - bx))
            ga = {k: g[k][sa] for k in ("ids", "which", "normal", "depth")}
            blocks_ += diff(parts(ta[sa], ga), parts(tb[sb], ga))
    out = {"two_candidates": summary(pairs_), "two_scales": summary(scales), "two_blocks": summary(blocks_)}
    (base() / "checks" / f"seams_{source}.json").write_text(json.dumps(out, indent=1))
    return out


def variant_release(source: str = "T1", k: int = 0, area: str = "test_painted", whole_share=0.98) -> Path:
    """The built release with the six blocks' buildings and structures in their target colours, as an area of its
    own for the viewer (python -m v2.view test_painted): every file of the release is linked, only the colour tiles
    of layers 5 and 6 over the blocks are written anew, at every zoom. Each block shows the p250 target; a building
    that lies whole (whole_share of its pixels) inside the block's centre is taken from the p125 target instead,
    so no building is split between two paintings. Where two blocks overlap, a building comes from the block that
    shows the most of it. Depth, normals, ids, windows, light and every other layer are the release's own,
    so the viewer's moving light and its night fall on the targets as on the code art. The merged far-zoom tiles
    are not remade: zoomed far out, the view is the code art."""
    import shutil

    from v2.layers.common import COLOUR_LAYERS, TILE, read_tile, write_tile
    rel = release()
    idx = json.loads((rel / "index.json").read_text())
    dst = v2_data() / area / "release" / f"{rel.name}_{source.lower()}_{k}"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    layers = [COLOUR_LAYERS[i - 1] for i in PAINT_LAYERS]
    for p in rel.iterdir():
        if p.name in layers:
            continue
        if p.is_symlink() or p.is_dir():
            os.symlink(p.resolve(), dst / p.name)
        else:
            shutil.copy2(p, dst / p.name)
    # the targets as one picture per block, and where they have a say
    blocks = {}
    for b, (x0, y0) in BLOCKS.items():
        big = _target_png(source, f"{b}_p250", k); small = _target_png(source, f"{b}_p125", k)
        if big is None:
            continue
        big = big.copy()
        _c, g, _m = load_input(f"{b}_p250")
        if small is not None:                              # a building is never split between two paintings
            q = BLOCK // 4
            inside = np.zeros(g["which"].shape, bool); inside[q:q + WIN, q:q + WIN] = True
            bid = (g["ids"] >> 8).astype(np.int64)
            on = np.isin(g["which"], PAINT_LAYERS)
            u, n_all = np.unique(bid[on], return_counts=True)
            ui, ni = np.unique(bid[on & inside], return_counts=True)
            n_in = dict(zip(ui.tolist(), ni.tolist()))
            whole = [int(v) for v, n in zip(u.tolist(), n_all.tolist()) if n_in.get(v, 0) >= whole_share * n]
            m = on & inside & np.isin(bid, whole)
            big[m] = np.pad(small, ((q, BLOCK - q - WIN), (q, BLOCK - q - WIN), (0, 0)))[m]
        blocks[b] = (x0, y0, big, g["which"], (g["ids"] >> 8).astype(np.int64))
    # the trial's blocks overlap on the map: a building two blocks show is taken from the block that shows the
    # most of it, and from another only where that block does not reach
    seen = {}
    for b, (x0, y0, _pic, which, bid) in blocks.items():
        u, n = np.unique(bid[np.isin(which, PAINT_LAYERS)], return_counts=True)
        for v, c in zip(u.tolist(), n.tolist()):
            if v not in seen or c > seen[v][0]:
                seen[v] = (c, b)
    mine = {}
    for b, (x0, y0, _pic, which, bid) in blocks.items():
        u, inv = np.unique(bid, return_inverse=True)
        ob = [seen.get(v, (0, b))[1] for v in u.tolist()]
        ox = np.array([blocks[o][0] for o in ob])[inv].reshape(bid.shape)
        oy = np.array([blocks[o][1] for o in ob])[inv].reshape(bid.shape)
        is_me = np.array([o == b for o in ob])[inv].reshape(bid.shape)
        Y, X = np.mgrid[y0:y0 + BLOCK, x0:x0 + BLOCK]
        reached = (X >= ox) & (X < ox + BLOCK) & (Y >= oy) & (Y < oy + BLOCK)
        mine[b] = is_me | ~reached
    changed = 0
    for L, layer in zip(PAINT_LAYERS, layers):
        src = rel / layer; out = dst / layer
        tiles = idx["layers"][layer]["tiles"]
        touched = set()
        for z in sorted(tiles, key=int):
            (out / z).mkdir(parents=True)
            for f in (src / z).iterdir():
                os.symlink(f.resolve(), out / z / f.name)
        for name, dmin in tiles["0"].items():
            tx, ty = (int(v) for v in name.split("_"))
            t = None
            for bname, (x0, y0, pic, which, _bid) in blocks.items():
                a0, b0 = max(x0, tx * TILE), max(y0, ty * TILE)
                a1, b1 = min(x0 + BLOCK, (tx + 1) * TILE), min(y0 + BLOCK, (ty + 1) * TILE)
                if a1 <= a0 or b1 <= b0:
                    continue
                if t is None:
                    t = read_tile(src / "0", name, dmin, z=0)
                    rgb = t["rgb"].copy()
                sl = (slice(b0 - ty * TILE, b1 - ty * TILE), slice(a0 - tx * TILE, a1 - tx * TILE))
                wl = (slice(b0 - y0, b1 - y0), slice(a0 - x0, a1 - x0))
                m = (which[wl] == L) & np.isfinite(t["depth"][sl]) & mine[bname][wl]
                sub = rgb[sl]; sub[m] = pic[wl][m]; rgb[sl] = sub
            if t is not None:
                (out / "0" / f"{name}.c.webp").unlink()
                write_tile(out / "0", name, rgb=rgb, q=101, z=0)
                touched.add((tx, ty)); changed += 1
        for z in sorted((int(v) for v in tiles if int(v) > 0)):
            parents = {(x // 2, y // 2) for x, y in touched}
            for px, py in parents:
                name = f"{px}_{py}"
                if name not in tiles[str(z)]:
                    continue
                acc = np.zeros((2 * TILE, 2 * TILE, 3)); valid = np.zeros((2 * TILE, 2 * TILE))
                for dy in (0, 1):
                    for dx in (0, 1):
                        n = f"{2 * px + dx}_{2 * py + dy}"
                        if n not in tiles[str(z - 1)]:
                            continue
                        c = read_tile(out / str(z - 1), n, tiles[str(z - 1)][n], z=z - 1)
                        sl = (slice(dy * TILE, (dy + 1) * TILE), slice(dx * TILE, (dx + 1) * TILE))
                        acc[sl] = c["rgb"]; valid[sl] = np.isfinite(c["depth"])
                v4 = valid.reshape(TILE, 2, TILE, 2).sum((1, 3))
                rgb = (acc * valid[..., None]).reshape(TILE, 2, TILE, 2, 3).sum((1, 3)) / np.maximum(v4, 1)[..., None]
                (out / str(z) / f"{name}.c.webp").unlink()
                write_tile(out / str(z), name, rgb=np.round(rgb).astype(np.uint8), q=101, z=z)
            touched = parents
    (dst.parent / "current.json").write_text(json.dumps({"key": f"{rel.name}:{source}:{k}", "folder": dst.name, "status": "ok",
                                                         "of": rel.name, "tiles_rewritten": changed}))
    return dst
