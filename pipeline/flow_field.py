"""Dense registration of the painted map against the 3D render it was painted from: where did the painter put what
the render had? (Task T2b; pipeline/flowfield.py reads the result.)

Every painted day block (data/work/tiles/painted.json: the canvas scaled to its w x h map px, as build_tiles.py lays
it) is matched against the render of the same map px (data/work/frames). Both are turned into comparable structure
images: grey, lightly blurred, then normalised by the local mean and contrast over about 10 px (the render is a
photo-like mesh, the painting is ink and flat colour; after this both are "where the light and dark edges are").
The match is normalised cross-correlation (NCC) of windows, for every whole-px move in a search range, done for the
whole block at once with box filters, then read at grid points:

  1. coarse, at half resolution: windows of 96 map px every 16 map px, moves up to 24 map px either way round the
     block's own median move (found first on a sparse grid);
  2. fine, at full resolution: the painting is first pulled back through the coarse field, then windows of 64 map px
     every 8 map px, moves up to 4 px.

Each grid match gives a move (sub-px, by a quadratic fit round the best NCC) and how sure it is in each direction
(the curvature of the NCC round the peak: along a straight road the match is sure across it and unsure along it,
the aperture problem). Matches are kept where the NCC is 0.25 or more and clearly above the next-best peak. The
field is then a robust, smooth combination: at every grid point the move that best agrees with the matches round it
(Gaussian weights, 12 m for the coarse field, 4 m for the fine one; each match weighted by its curvature, so it only
pins the direction it is sure of), with matches far from the result (over 2 px along their sure direction) weighted
down and the fit redone (three rounds). Where the matches say little (water, lawns, under trees: low total weight)
the field falls back on the coarse field, and the coarse field on the block's median move. "conf" (0..1) is that
total weight against the weight that makes the matches count as much as the fallback.

Validation: on features the render shows clearly (building corners and roof edges in the line pass, bridge decks and
river banks in the kinds pass), the painting is matched again, independently, with smaller windows (48 px) after it
is pulled back through the field: the remaining move there is the field's error (data/work/flowfit/validate.json).

Writes data/work/flowfit/:
  <block>.npz     the block's coarse and fine fields, its matches (for checks and pictures)
  field.npz       the whole map's field every 8 map px (flowfield.py), each grid point from the block painted on top
                  there (the last in painted.json that covers it, as build_tiles.py lays them); 0 outside the art
  summary.json    per block: median move, spread, share of grid points with a sure match, time
  validate.json   per block and per feature kind: the remaining error at validation features (median, 90th centile)

Usage: flow_field.py [--blocks b00 b03 ...] [--compose-only] [--validate-only]
About 1-2 minutes and 2 GB per block; one block at a time.
"""
import argparse
import itertools
import json
import time

import cv2
import numpy as np
from PIL import Image

from common import WORK
from flowfield import FLOWFIT, STEP, Field

Image.MAX_IMAGE_PIXELS = None
BG = np.array([16, 24, 40], np.float32)


# ------------------------------------------------------------------------------------------------- inputs
def render_crop(mos, x0, y0, w, h, d="frames", ext="jpg", mode="RGB"):
    F = mos["frame"]
    ch = 3 if mode == "RGB" else 1
    out = np.zeros((h, w, ch), np.uint8)
    for r in range(mos["rows"]):
        for c in range(mos["cols"]):
            fx, fy = c * F, r * F
            ix0, iy0, ix1, iy1 = max(x0, fx), max(y0, fy), min(x0 + w, fx + F), min(y0 + h, fy + F)
            if ix0 >= ix1 or iy0 >= iy1:
                continue
            a = np.asarray(Image.open(WORK / d / f"{c}_{r}.{ext}").convert(mode)).reshape(F, F, ch)
            out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] = a[iy0 - fy:iy1 - fy, ix0 - fx:ix1 - fx]
    return out if ch == 3 else out[..., 0]


def painting(b):
    im = Image.open(WORK / "tiles" / b["file"]).convert("RGB")
    if im.size != (b["w"], b["h"]):
        im = im.resize((b["w"], b["h"]), Image.LANCZOS)
    return np.asarray(im)


def structure(rgb, s1, s2):
    """Grey, blurred by s1, minus the local mean over s2, over the local contrast: comparable between render and
    painting."""
    g = rgb.astype(np.float32).mean(2)
    g = cv2.GaussianBlur(g, (0, 0), s1)
    m = cv2.GaussianBlur(g, (0, 0), s2)
    v = cv2.GaussianBlur((g - m) ** 2, (0, 0), s2)
    return ((g - m) / np.sqrt(v + 25.0)).astype(np.float32)


def valid(rgb):
    """Not the empty background (render or painting)."""
    return (np.abs(rgb.astype(np.float32) - BG).sum(2) > 20).astype(np.float32)


# ------------------------------------------------------------------------------------------------- matching
def ncc_volume(A, B, VA, VB, rad, win, step, off, M=None):
    """NCC of A's window round every grid point (rows off, off + step, ...) against B's window moved by every
    (dy, dx) in [-rad, rad]^2. M (optional, 0..1 per px of A): weights, so only those px of A's window count (one
    layer of the render: its ground, or its buildings). Returns vol (ny, nx, 2rad+1, 2rad+1) float32 (-1 where not
    valid), grid ys, xs."""
    H, W = A.shape
    ys, xs = np.arange(off, H, step), np.arange(off, W, step)
    ny, nx = len(ys), len(xs)
    if win % step == 0 and win >= step:
        # window means at the grid points only: sums over step x step blocks, then over k x k blocks (fast)
        k = win // step
        base = win + off - win // 2

        def box_g(a):
            P = cv2.copyMakeBorder(a, win, win + (k + 1) * step, win, win + (k + 1) * step, cv2.BORDER_CONSTANT,
                                   value=0)
            sub = P[base:base + (ny + k) * step, base:base + (nx + k) * step]
            Bk = sub.reshape(ny + k, step, nx + k, step).sum((1, 3), dtype=np.float64)
            C = np.zeros((ny + k + 1, nx + k + 1))
            C[1:, 1:] = Bk.cumsum(0).cumsum(1)
            return ((C[k:k + ny, k:k + nx] - C[:ny, k:k + nx] - C[k:k + ny, :nx] + C[:ny, :nx]) / win ** 2
                    ).astype(np.float32)
        g = lambda a: a
        box = box_g
    else:
        box = lambda a: cv2.boxFilter(a, cv2.CV_32F, (win, win), normalize=True, borderType=cv2.BORDER_CONSTANT)
        g = lambda a: a[ys][:, xs]
    M = VA if M is None else M * VA
    sw = g(box(M))
    swd = np.maximum(sw, 1e-6)
    MA = M * A
    mA = g(box(MA)) / swd
    sA = g(box(MA * A)) / swd - mA ** 2
    Bp = cv2.copyMakeBorder(B, rad, rad, rad, rad, cv2.BORDER_CONSTANT, value=0)
    VBp = cv2.copyMakeBorder(VB, rad, rad, rad, rad, cv2.BORDER_CONSTANT, value=0)
    vol = np.full((ny, nx, 2 * rad + 1, 2 * rad + 1), -1, np.float32)
    bad0 = sw < 0.3
    for dy in range(-rad, rad + 1):
        for dx in range(-rad, rad + 1):
            sl = (slice(rad + dy, rad + dy + H), slice(rad + dx, rad + dx + W))
            Bs = Bp[sl]
            MBs = M * Bs
            mb = g(box(MBs)) / swd
            mb2 = g(box(MBs * Bs)) / swd
            S = g(box(MA * Bs)) / swd
            c = (S - mA * mb) / np.sqrt(np.maximum(sA * (mb2 - mb * mb), 1e-6))
            c[bad0 | (g(box(VBp[sl])) < 0.8)] = -1
            vol[:, :, dy + rad, dx + rad] = c
    return vol, ys, xs


def peaks(vol, rad, min_ncc=0.25, margin=0.04):
    """Per grid point: move (dx, dy) sub-px, the information matrix (2x2, from the NCC curvature at the peak, times
    the peak's strength), the NCC; info 0 where the match is not clear."""
    ny, nx = vol.shape[:2]
    n = 2 * rad + 1
    flat = vol.reshape(ny, nx, -1)
    am = flat.argmax(-1)
    best = np.take_along_axis(flat, am[..., None], -1)[..., 0]
    py, px = am // n, am % n
    inner = (py > 0) & (py < n - 1) & (px > 0) & (px < n - 1)
    pyc, pxc = np.clip(py, 1, n - 2), np.clip(px, 1, n - 2)
    I, J = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
    c = lambda a, b: vol[I, J, pyc + a, pxc + b]
    c0 = c(0, 0)
    gx, gy = (c(0, 1) - c(0, -1)) / 2, (c(1, 0) - c(-1, 0)) / 2
    hxx, hyy = c(0, 1) - 2 * c0 + c(0, -1), c(1, 0) - 2 * c0 + c(-1, 0)
    hxy = (c(1, 1) - c(1, -1) - c(-1, 1) + c(-1, -1)) / 4
    # second-best peak: the best other local maximum (higher than its 8 neighbours) more than 2 px from the first.
    # A ridge (a straight road or edge: sure across, unsure along) is not a second peak; its curvature says it.
    pad = np.pad(vol, ((0, 0), (0, 0), (1, 1), (1, 1)), constant_values=-2)
    nb = np.full_like(vol, -2)
    for a, b in itertools.product((-1, 0, 1), (-1, 0, 1)):
        if a or b:
            np.maximum(nb, pad[:, :, 1 + a:1 + a + n, 1 + b:1 + b + n], out=nb)
    Y, X = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    far = (np.abs(Y[None, None] - py[..., None, None]) > 2) | (np.abs(X[None, None] - px[..., None, None]) > 2)
    second = np.where(far & (vol > nb), vol, -1).reshape(ny, nx, -1).max(-1)
    del pad, nb, far
    # information: minus the Hessian, made positive semi-definite
    Hm = -np.stack([np.stack([hxx, hxy], -1), np.stack([hxy, hyy], -1)], -2).astype(np.float64)
    ev, evec = np.linalg.eigh(Hm)
    ev = np.clip(ev, 0, None)
    Hp = np.einsum("...ij,...j,...kj->...ik", evec, ev, evec)
    # A peak: sure in both directions (the smaller curvature at least 0.15 of the larger), inside the search range.
    # A ridge (the aperture problem: a straight road or edge): sure across only; it may run out of the search range
    # along its length (not across it), and pins only the direction across.
    l1, l2 = ev[..., 1], ev[..., 0]
    e1 = evec[..., :, 1]                                 # the sure direction (x, y)
    ridge = (l2 < 0.15 * l1) & (l1 > 1e-4)
    py_edge, px_edge = (py == 0) | (py == n - 1), (px == 0) | (px == n - 1)
    ridge_ok = ridge & ~(py_edge & (np.abs(e1[..., 1]) > 0.5)) & ~(px_edge & (np.abs(e1[..., 0]) > 0.5))
    full = inner & ~ridge & (l2 > 1e-6)
    ok = (full | ridge_ok) & (best >= min_ncc) & (best - second >= margin)
    # sub-px move: a Newton step (along the sure direction only, on a ridge), at most half a px
    G =np.stack([gx, gy], -1)
    Hinv_g = np.einsum("...ij,...j,...kj,...k->...i", evec, 1 / np.maximum(ev, 1e-9), evec, G)
    along = np.einsum("...i,...i->...", e1, G) / np.maximum(l1, 1e-9)
    s = np.where(full[..., None], Hinv_g, e1 * along[..., None])
    s = np.where(ok[..., None], np.clip(s, -0.5, 0.5), 0)
    d = np.stack([px - rad + s[..., 0], py - rad + s[..., 1]], -1).astype(np.float64)
    strength = np.clip((best - min_ncc) / (1 - min_ncc), 0, 1) * np.clip((best - second) / 0.15, 0, 1)
    Hr = np.einsum("...i,...j->...ij", e1, e1) * l1[..., None, None]
    info = np.where(ridge[..., None, None], Hr, Hp) * (strength * ok)[..., None, None]
    return d, info, best, ok


def smooth_field(d, info, prior, sigma, lam, rounds=3, c_px=2.0):
    """Robust combination of grid matches d (ny, nx, 2) with information info (ny, nx, 2, 2): at every grid point
    the move that best agrees with the matches within ~sigma grid cells, and prior (ny, nx, 2) with weight lam.
    Returns (field, conf 0..1)."""
    w = np.ones(d.shape[:2])
    gb = lambda a: cv2.GaussianBlur(a.astype(np.float32), (0, 0), sigma, borderType=cv2.BORDER_REFLECT)
    for _ in range(rounds):
        Iw = info * w[..., None, None]
        bx = Iw[..., 0, 0] * d[..., 0] + Iw[..., 0, 1] * d[..., 1]
        by = Iw[..., 1, 0] * d[..., 0] + Iw[..., 1, 1] * d[..., 1]
        a, b, c = gb(Iw[..., 0, 0]), gb(Iw[..., 0, 1]), gb(Iw[..., 1, 1])
        rx, ry = gb(bx), gb(by)
        a, c = a + lam, c + lam
        rx, ry = rx + lam * prior[..., 0], ry + lam * prior[..., 1]
        det = a * c - b * b
        F = np.stack([(c * rx - b * ry) / det, (a * ry - b * rx) / det], -1)
        # residuals along each match's sure direction (px), Cauchy weights
        e = d - F
        tr = info[..., 0, 0] + info[..., 1, 1] + 1e-12
        m2 = np.einsum("...i,...ij,...j->...", e, info, e) / tr * 2
        w = 1 / (1 + m2 / c_px ** 2)
    ev = np.linalg.eigvalsh(np.stack([np.stack([a - lam, b], -1), np.stack([b, c - lam], -1)], -2))
    conf = np.clip(ev[..., 0] / (ev[..., 0] + lam), 0, 1)
    return F, conf


def upsample(field, ys, xs, H, W):
    """Grid field (ny, nx, 2) at rows ys, cols xs to every px (H, W, 2), bilinear (edges held)."""
    gy = ((np.arange(H) - ys[0]) / (ys[1] - ys[0])).astype(np.float32)
    gx = ((np.arange(W) - xs[0]) / (xs[1] - xs[0])).astype(np.float32)
    out = []
    for k in range(2):
        out.append(cv2.remap(field[..., k].astype(np.float32), np.broadcast_to(gx[None], (H, W)).copy(),
                             np.broadcast_to(gy[:, None], (H, W)).copy(), cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE))
    return np.stack(out, -1)


def shifted(a, m):
    """a moved so that out(x) = a(x + m), 0 outside."""
    H, W = a.shape
    M = np.float32([[1, 0, m[0]], [0, 1, m[1]]])
    return cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP, borderValue=0)


def pull_back(img, D):
    """img sampled at x + D(x): the painting moved back onto the render's positions."""
    H, W = img.shape[:2]
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(img, X + D[..., 0], Y + D[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


# ------------------------------------------------------------------------------------------------- one block
LAYERS = ("ground", "built")


def layer_masks(K):
    """The render's layers from the kinds pass (0..100 walls and roofs, 101..200 bridge decks, over 200 ground):
    ground (terrain and decks: where vehicles are) and built (walls and roofs: what hides them)."""
    return {"ground": (K > 100).astype(np.float32), "built": (K <= 100).astype(np.float32)}


def layer_field(A2, B2, V2a, V2b, M2, Rrgb, Prgb, VR, VP, M, w, h, P):
    """The field of one layer of the render (weights M at full resolution, M2 at half): coarse then fine.
    Returns (fine field (ny, nx, 2) every STEP px, conf, stats, matches)."""
    # 0. the median move, sparse (quarter resolution, windows of 128 map px every 128, moves up to 32)
    q = lambda a: cv2.resize(a, (a.shape[1] // 2, a.shape[0] // 2), interpolation=cv2.INTER_AREA)
    vol, _, _ = ncc_volume(q(A2), q(B2), q(V2a), q(V2b), 8, 32, 32, 16, q(M2))     # quarter resolution
    d0, _, _, ok0 = peaks(vol, 8, min_ncc=0.3)
    del vol
    med = np.median(d0[ok0], 0) * 4 if ok0.sum() >= 5 else np.array([0.0, 8.0])
    # 1. coarse: half resolution, windows of P["cwin"] half px every 8 (16 map px), moves up to 12 (24 map px)
    m2 = np.round(med / 2).astype(int)
    B2s, V2bs = shifted(B2, m2), shifted(V2b, m2)
    vol, ys1, xs1 = ncc_volume(A2, B2s, V2a, V2bs, 12, P["cwin"], 8, 4, M2)
    d1, i1, s1, ok1 = peaks(vol, 12)
    del vol, B2s, V2bs
    d1 = (d1 + m2) * 2
    i1 = i1 / 4                                           # information per map px^2
    if ok1.sum() >= 20:
        med = np.median(d1[ok1], 0)
    prior = np.broadcast_to(med, d1.shape).copy()
    F1, c1 = smooth_field(d1, i1, prior, sigma=P["csig"], lam=0.02)
    ys1, xs1 = ys1 * 2 + 0.5, xs1 * 2 + 0.5                # map px within the block (half px centre)
    D1 = upsample(F1, ys1, xs1, h, w)
    # 2. fine: full resolution, the painting pulled back through the coarse field
    A = structure(Rrgb, 1.0, 10)
    B = structure(pull_back(Prgb, D1), 1.0, 10)
    VBb = pull_back(VP, D1)
    vol, ys2, xs2 = ncc_volume(A, B, VR, VBb, P["frad"], P["fwin"], STEP, STEP // 2, M)
    del A, B, VBb
    d2, i2, s2, ok2 = peaks(vol, P["frad"])
    del vol
    base = np.stack([D1[ys2][:, xs2, 0], D1[ys2][:, xs2, 1]], -1)
    del D1
    F2r, c2 = smooth_field(d2, i2, np.zeros_like(d2), sigma=P["fsig"], lam=0.04)
    F2 = base + F2r
    st = {"median": [round(float(med[0]), 2), round(float(med[1]), 2)],
          "coarse_sure": round(float(ok1.mean()), 3), "fine_sure": round(float(ok2.mean()), 3),
          "field_p05": [round(float(np.percentile(F2[..., k], 5)), 2) for k in (0, 1)],
          "field_p50": [round(float(np.percentile(F2[..., k], 50)), 2) for k in (0, 1)],
          "field_p95": [round(float(np.percentile(F2[..., k], 95)), 2) for k in (0, 1)],
          "fine_residual_px": round(float(np.median(np.hypot(*(d2[ok2] - F2r[ok2]).T))) if ok2.any() else -1, 2)}
    return F2, c2, st, {"d2": d2 + base, "ok2": ok2}


ROAD_LAM = 0.0001
PARAMS = {"cwin": 48, "csig": 3.0, "frad": 4, "fwin": 64, "fsig": 2.0}


def block_field(b, mos, P=PARAMS):
    t0 = time.time()
    x0, y0, w, h = b["x0"], b["y0"], b["w"], b["h"]
    Rrgb = render_crop(mos, x0, y0, w, h)
    Prgb = painting(b)
    VR, VP = valid(Rrgb), valid(Prgb)
    masks = layer_masks(render_crop(mos, x0, y0, w, h, "frames_kind", "png", "L"))
    half = lambda a: cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    A2, B2 = structure(half(Rrgb), 0.7, 5), structure(half(Prgb), 0.7, 5)
    V2a, V2b = half(VR), half(VP)
    out, stats = {}, {}
    for layer in LAYERS:
        F, conf, st, m = layer_field(A2, B2, V2a, V2b, half(masks[layer]), Rrgb, Prgb, VR, VP, masks[layer], w, h, P)
        stats[layer] = st
        out[f"{layer}_dx"], out[f"{layer}_dy"] = F[..., 0].astype(np.float32), F[..., 1].astype(np.float32)
        out[f"{layer}_conf"] = conf.astype(np.float32)
        out[f"{layer}_d2"], out[f"{layer}_ok2"] = m["d2"].astype(np.float32), m["ok2"]
        print(f"  {b['block']} {layer}: {json.dumps(st)}", flush=True)
    stats["seconds"] = round(time.time() - t0, 1)
    np.savez_compressed(FLOWFIT / f"{b['block']}.npz", x0=x0, y0=y0, step=STEP, off=STEP // 2,
                        painted=(VP[STEP // 2::STEP, STEP // 2::STEP] > 0), **out)
    return stats


# ------------------------------------------------------------------------------------------------- the whole map
def compose(bl, mos):
    """field.npz: the map's field every STEP map px, each grid point from the block painted on top there."""
    H, W = mos["rows"] * mos["frame"] // STEP, mos["cols"] * mos["frame"] // STEP
    arr = {f"{l}_{k}": np.zeros((H, W), np.float32) for l in LAYERS for k in ("dx", "dy", "conf")}
    owner = np.full((H, W), -1, np.int8)
    for i, b in enumerate(bl):
        f = FLOWFIT / f"{b['block']}.npz"
        if not f.exists():
            continue
        z = np.load(f)
        # block grid point (r, c) is at map px (x0 + off + c*STEP, ...) = map grid ((x0 + off) / STEP + c)
        gx0, gy0 = (b["x0"] + STEP // 2) // STEP, (b["y0"] + STEP // 2) // STEP
        assert (b["x0"] + STEP // 2) % STEP == 0 and (b["y0"] + STEP // 2) % STEP == 0
        h, w = z["ground_dx"].shape
        sy0, sx0 = max(0, -gy0), max(0, -gx0)
        ty0, tx0 = max(0, gy0), max(0, gx0)
        hh, ww = min(h - sy0, H - ty0), min(w - sx0, W - tx0)
        if hh <= 0 or ww <= 0:
            continue
        sl = (slice(ty0, ty0 + hh), slice(tx0, tx0 + ww))
        ss = (slice(sy0, sy0 + hh), slice(sx0, sx0 + ww))
        for k, a in arr.items():
            a[sl] = z[k][ss]
        owner[sl] = i
    # where the art is not painted (the empty edge inside a block) keep the block's field: harmless, nothing drives
    meta = {"step": STEP, "blocks": [b["block"] for b in bl], "layers": list(LAYERS)}
    np.savez_compressed(FLOWFIT / "field.npz", owner=owner, meta=json.dumps(meta), **arr)
    for l in LAYERS:
        print(f"field.npz {l}: {W} x {H} grid, |D| median "
              f"{np.median(np.hypot(arr[l + '_dx'], arr[l + '_dy'])[owner >= 0]):.2f} px", flush=True)


# ------------------------------------------------------------------------------------------------- validation
def features(b, mos):
    """Validation points in a block (map px within the block, kind): building corners (strong corners of the line
    pass), bridge decks (deck pixels of the kinds pass with an edge), river banks (edges of the render's water)."""
    x0, y0, w, h = b["x0"], b["y0"], b["w"], b["h"]
    L = render_crop(mos, x0, y0, w, h, "frames_line", "png", "L")
    K = render_crop(mos, x0, y0, w, h, "frames_kind", "png", "L")
    out = []
    # corners of the line pass where the kinds pass has a building (wall or roof: 1..100)
    ink = cv2.GaussianBlur(255 - L, (0, 0), 1.5)
    pts = cv2.goodFeaturesToTrack(ink, 3000, 0.05, 60)
    if pts is not None:
        for x, y in pts.reshape(-1, 2):
            k = K[int(y), int(x)]
            out.append((x, y, "corner" if k <= 100 else "ground"))
    # bridge decks: deck pixels (101..200) on the deck's edge
    deck = ((K > 100) & (K <= 200)).astype(np.uint8)
    edge = deck - cv2.erode(deck, np.ones((5, 5), np.uint8))
    ys, xs = np.nonzero(edge[::4, ::4])
    if len(xs):
        sel = np.random.default_rng(0).choice(len(xs), min(400, len(xs)), replace=False)
        out += [(xs[i] * 4, ys[i] * 4, "deck") for i in sel]
    return out, L, K


def river_banks(b, mos, Rrgb):
    """Points on the render's river banks: the edge of the OSM water polygons (lines.json "water")."""
    from common import ROOT
    lines = json.loads((ROOT / "web/public/data/lines.json").read_text())
    x0, y0, w, h = b["x0"], b["y0"], b["w"], b["h"]
    m = np.zeros((h, w), np.uint8)
    for wy in lines["water"]:
        p = np.array(wy["p"], float).reshape(-1, 2) - [x0, y0]
        if len(p) >= 3 and p[:, 0].max() > 0 and p[:, 1].max() > 0 and p[:, 0].min() < w and p[:, 1].min() < h:
            cv2.fillPoly(m, [np.round(p * 4).astype(np.int32)], 1, shift=2)
    edge = m - cv2.erode(m, np.ones((5, 5), np.uint8))
    ys, xs = np.nonzero(edge[::4, ::4])
    if not len(xs):
        return []
    sel = np.random.default_rng(1).choice(len(xs), min(400, len(xs)), replace=False)
    return [(xs[i] * 4, ys[i] * 4, "bank") for i in sel]


def validate(b, mos):
    """Remaining move at validation features after pulling the painting back through the field (smaller windows,
    48 px, NCC as above). Returns {kind: [n, median px, p90 px]} plus the same before (block median move only)."""
    x0, y0, w, h = b["x0"], b["y0"], b["w"], b["h"]
    z = np.load(FLOWFIT / f"{b['block']}.npz")
    Rrgb = render_crop(mos, x0, y0, w, h)
    Prgb = painting(b)
    fe, L, K = features(b, mos)
    fe += river_banks(b, mos, Rrgb)
    if not fe:
        return {}
    ys, xs = np.arange(STEP // 2, h, STEP), np.arange(STEP // 2, w, STEP)
    A = structure(Rrgb, 1.0, 10)
    VR, VP = valid(Rrgb), valid(Prgb)
    res = {"block": {}, "field": {}}
    # the one offset for the whole block (as T2 had it) against the field; buildings against the built layer, the
    # rest against the ground layer
    for name, (layer, kinds) in itertools.product(("block", "field"), (("built", ("corner",)),
                                                                        ("ground", ("ground", "deck", "bank")))):
        F =np.stack([z[f"{layer}_dx"], z[f"{layer}_dy"]], -1)
        if name == "block":
            med = np.median(F[z["painted"]].reshape(-1, 2), 0) if z["painted"].any() else np.zeros(2)
            Dm = np.broadcast_to(med, (h, w, 2)).astype(np.float32)
        else:
            Dm = upsample(F, ys, xs, h, w)
        B = structure(pull_back(Prgb, Dm), 1.0, 10)
        VB = pull_back(VP, Dm)
        del Dm
        r, win = 12, 48
        per = {}
        for x, y, kind in fe:
            if kind not in kinds:
                continue
            x, y = int(x), int(y)
            if x < win + r or y < win + r or x >= w - win - r or y >= h - win - r:
                continue
            a = A[y - win // 2:y + win // 2, x - win // 2:x + win // 2]
            if VR[y, x] == 0 or VB[y, x] == 0 or a.std() < 0.3:
                continue
            s = B[y - win // 2 - r:y + win // 2 + r, x - win // 2 - r:x + win // 2 + r]
            c = cv2.matchTemplate(s, a, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(c)
            if mx < 0.4 or loc[0] in (0, 2 * r) or loc[1] in (0, 2 * r):
                continue
            # sub-px
            cx, cy = loc
            ddx = (c[cy, cx + 1] - c[cy, cx - 1]) / (2 * (2 * c[cy, cx] - c[cy, cx + 1] - c[cy, cx - 1]) + 1e-9)
            ddy = (c[cy + 1, cx] - c[cy - 1, cx]) / (2 * (2 * c[cy, cx] - c[cy + 1, cx] - c[cy - 1, cx]) + 1e-9)
            e = np.hypot(cx - r + np.clip(ddx, -.5, .5), cy - r + np.clip(ddy, -.5, .5))
            per.setdefault(kind, []).append(e)
        res[name].update({k: [len(v), round(float(np.median(v)), 2), round(float(np.percentile(v, 90)), 2)]
                          for k, v in per.items()})
    return res


# ------------------------------------------------------------------------------------------------- the road layer
def road_layer(mos, band=768):
    """The road layer: the ground field refined on the roads and tracks themselves. The painter often redrew a street
    a little apart from the ground round it (a boulevard pushed down, a building drawn smaller), which the ground
    texture does not show. Structure images: the carriageways and rail beds as the render has them (lines.json
    roads at their width "w", rails 3 m wide, moved by the ground field) against the painted asphalt and rail bed
    (colour models learnt from the art on those lines, as fit_roads.py does). Same NCC and robust smoothing as above,
    at 0.5 m cells: windows of 16 m every 8 map px, moves up to 3 m, smoothing over 6 m; where no road says
    anything, the ground field. Adds road_dx, road_dy, road_conf to field.npz."""
    import fit_roads as fr
    from build_drivable import CELL, DRIVE, art, default_width, osm_tags, painted_water
    from common import ROOT
    from roadfit_geom import pts
    t0 = time.time()
    z = dict(np.load(FLOWFIT / "field.npz"))
    Fg = Field(z["ground_dx"], z["ground_dy"])
    data = ROOT / "web/public/data"
    shape = (mos["rows"] * mos["frame"] // CELL, mos["cols"] * mos["frame"] // CELL)
    bl = json.loads((WORK / "tiles" / "painted.json").read_text())
    lines = json.loads((data / "lines.json").read_text())
    tags = osm_tags()
    roads = [w for w in lines["roads"] if w.get("k") in DRIVE and len(w["p"]) >= 4 and not w.get("t")]
    rails = [w for w in lines["rail"] if w.get("k") in fr.RAIL and len(w["p"]) >= 4 and not w.get("t")]
    w0 = {w["id"]: (w.get("w") or default_width(w, tags)) for w in roads}
    moved = {w["id"]: Fg.move(pts(w)) for w in roads + rails}
    key = lambda w: moved[w["id"]]
    rgb = art(shape, ROOT / "web/public/tiles/map_files")
    ok = ~(np.abs(rgb.astype(np.int16) - [16, 24, 40]).max(axis=2) <= 8) & ~painted_water(shape, data)
    own = fr.owner_grid(shape, bl)
    main_k = ("primary", "secondary", "tertiary", "residential", "unclassified")
    reach = lambda w: min(max(w0[w["id"]] * 0.75 + 1.5, 3.0), 14.0)
    centre = fr.raster([w for w in roads if w.get("k") in main_k and not w.get("b")], shape, lambda w: 1.0, key)
    near = fr.raster(roads, shape, lambda w: reach(w) + 3.0, key)
    ring = fr.raster(roads, shape, lambda w: reach(w) + 7.0, key) & ~near
    asp = fr.colour_mask(rgb, centre & ok, ring & ok, own, shadow=True) & ok
    del centre, ring
    core = fr.raster([w for w in rails if not w.get("b")], shape, lambda w: 0.6, key)
    neart = fr.raster(rails, shape, lambda w: fr.RAIL_HALF_M + 4.0, key)
    rring = fr.raster(rails, shape, lambda w: fr.RAIL_HALF_M + 9.0, key) & ~neart & ~near
    bed = fr.colour_mask(rgb, core & ok, rring & ok, own, ratio=1.5, min_pos=5000) & ok
    del rgb, core, rring
    P = cv2.GaussianBlur((asp | bed).astype(np.float32), (0, 0), 1.0)
    V = ok.astype(np.float32)
    del asp, bed, ok
    R = (fr.raster(roads, shape, lambda w: w0[w["id"]] / 2, key) | fr.raster(rails, shape, lambda w: fr.RAIL_HALF_M, key))
    R = cv2.GaussianBlur(R.astype(np.float32), (0, 0), 1.0)
    W8 = cv2.dilate((R > 0.05).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(np.float32)   # near the lines
    print(f"road layer: masks in {time.time() - t0:.0f} s", flush=True)
    # cost volume in bands of rows (cells), grid every 4 cells (8 map px) = the field grid
    G = STEP // CELL
    rad, win = 6, 32
    H, W = shape
    D, I = [], []
    for r0 in range(0, H, band):
        r1 = min(H, r0 + band)
        m0, m1 = max(0, r0 - 40), min(H, r1 + 40)          # margin: a whole number of grid rows
        vol, ys, xs = ncc_volume(R[m0:m1], P[m0:m1], V[m0:m1], V[m0:m1], rad, win, G, 0, W8[m0:m1])
        keep = (ys + m0 >= r0) & (ys + m0 < r1)
        d, info, best, okk = peaks(vol[keep], rad, min_ncc=0.3)
        del vol
        D.append(d * CELL); I.append(info / CELL ** 2)
        near_rows = W8[r0:r1:G, ::G] > 0
        print(f"  rows {r0}-{r1}: sure at {okk[near_rows[:len(okk)]].mean() if near_rows.any() else 0:.0%} of grid points "
              f"near the lines", flush=True)
    d = np.concatenate(D); info = np.concatenate(I)
    ny, nx = z["ground_dx"].shape
    d, info = d[:ny, :nx], info[:ny, :nx]
    np.savez_compressed(FLOWFIT / "road_matches.npz", d=d.astype(np.float32), info=info.astype(np.float32))
    res, conf = smooth_field(d, info, np.zeros_like(d), sigma=4.0, lam=ROAD_LAM)
    res = np.clip(res, -12, 12)
    z["road_dx"] = (z["ground_dx"] + res[..., 0]).astype(np.float32)
    z["road_dy"] = (z["ground_dy"] + res[..., 1]).astype(np.float32)
    z["road_conf"] = conf.astype(np.float32)
    meta = json.loads(str(z["meta"]))
    meta["layers"] = list(LAYERS) + ["road"]
    z["meta"] = json.dumps(meta)
    np.savez_compressed(FLOWFIT / "field.npz", **z)
    sure = info[..., 0, 0] + info[..., 1, 1] > 0
    c3 = conf > 0.3
    st = {"sure": int(sure.sum()), "conf_over_0.3": int(c3.sum()),
          "residual_median": [round(float(np.median(res[c3][:, k])), 2) if c3.any() else 0 for k in (0, 1)],
          "residual_p90_len": round(float(np.percentile(np.hypot(*res[c3].T), 90)), 2) if c3.any() else 0,
          "seconds": round(time.time() - t0, 1)}
    print("road layer:", json.dumps(st), flush=True)
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blocks", nargs="*")
    ap.add_argument("--compose-only", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--road-only", action="store_true", help="only the road layer (on the ground field as it is)")
    a = ap.parse_args()
    FLOWFIT.mkdir(parents=True, exist_ok=True)
    mos = json.loads((WORK / "mosaic.json").read_text())
    bl = json.loads((WORK / "tiles" / "painted.json").read_text())
    todo = [b for b in bl if not a.blocks or b["block"] in a.blocks]
    sf, vf = FLOWFIT / "summary.json", FLOWFIT / "validate.json"
    summ = json.loads(sf.read_text()) if sf.exists() else {}
    val = json.loads(vf.read_text()) if vf.exists() else {}
    if not a.compose_only and not a.validate_only and not a.road_only:
        for b in todo:
            st = block_field(b, mos)
            summ[b["block"]] = st
            sf.write_text(json.dumps(summ, indent=1))
            print(b["block"], json.dumps(st), flush=True)
    if a.road_only:
        summ["road"] = road_layer(mos)
        sf.write_text(json.dumps(summ, indent=1))
        return
    if not a.validate_only:
        compose(bl, mos)
    if not a.validate_only:
        summ["road"] = road_layer(mos)
        sf.write_text(json.dumps(summ, indent=1))
    if not a.compose_only and not a.no_validate:
        for b in todo:
            v = validate(b, mos)
            val[b["block"]] = v
            vf.write_text(json.dumps(val, indent=1))
            print(b["block"], "validation", json.dumps(v), flush=True)


if __name__ == "__main__":
    main()
