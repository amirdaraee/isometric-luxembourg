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
PAINTED = {"T1": "painted", "T2": "painted_even"}   # where each paid job's paintings are (bundle.OUT)
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


def transfer(code, painting, g: dict, have=None, p: dict = P):
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


def delit(code, painting, g: dict, cast=None, sigma=24.0, clip=(-1.1, 0.5), dark=0.6, p: dict = P):
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
    ground, the trees and the ink on the borders between faces and buildings; its own windows are not drawn."""
    from scipy import ndimage as ndi
    code = code.astype(float); src = painting.astype(float) + 1.0
    bid, cls, face, _seg = segments(g)
    on = np.isin(g["which"], PAINT_LAYERS)
    roof = np.isin(cls, (ROOF,)).astype(np.int64)
    out = code.copy()
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
                    d = np.clip(lys - tone, *clip)
                    crel = np.clip(chs / tint[None, None, :], 0.6, 1.6) ** 0.8
                    val = target[None, None, :] * np.exp(d)[..., None] * crel
                    sub = out[sl]; sub[mf] = val[mf]; out[sl] = sub
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
    from v2.config.sun import direction_screen
    s = direction_screen(when)
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
