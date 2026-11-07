"""Layered map v2, layer 1: the painted ground.

The bare terrain (no buildings, no bridge decks) with the aerial photo draped on it, in the map projection, with
the things that must not be painted into the ground taken out of the photo first:
  - building roofs (the photo shows them flattened onto the ground): filled from the surrounding ground;
  - bridge decks (a ghost of the deck on the valley floor): filled the same way;
  - tree crowns from the LiDAR tree survey (the trees come back as their own painted layer): filled with the
    ground round them, so the ground under a tree reads as lawn, path or woodland floor, not as a second tree;
  - parked and moving cars on roads: a median filter along the road surfaces.
That image is painted by the trained style through mdpaint (Modal), exactly like today's map, with a ground-only
layout map. The painter's few-pixel shift is measured against the input and undone.

  v2_ground.py prep [--k K]                -> b00_v2/ground/src.png, layout.png, masks.npz, previews
  v2_ground.py finish <painted.png>        -> b00_v2/ground/L1_painted.png (shift undone), shift.txt, and
                                              L1_ground.png (trees the painter drew anyway removed)
K is the scale of the 6000 px block (default 5120/6000, the painted size).
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from layers_common import (ORIGIN_E, ORIGIN_N, POC_IMG, RAW, ROOT, WORK, block, en_to_lonlat, inputs_dir,
                           painter_shift, preview, today, unshift, LAYERS)
from terrain_pass import block_en, ground_pass, sample, slope_normals

PAINT = 5120
GRID = 0.5          # m per px of the north-up mask grid
ORTHO_Z = 18
BG = (16, 24, 40)


def canopy_path():
    """The canopy used to cut the trees: the trimmed one if it was rendered, else the full one."""
    d = LAYERS / "b00_v2" / "canopy"
    t = d / "canopy_k85_trim85.npz"
    return t if t.exists() else d / "canopy_k85.npz"


def v2_dir(sub=""):
    d = LAYERS / "b00_v2" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def merc_px(lon, lat, z=ORTHO_Z):
    t = 2 ** z * 256
    return (lon + 180) / 360 * t, (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * t


def load_ortho_box(mx0, my0, mx1, my1):
    """The z18 orthophoto tiles covering a web-mercator pixel box, as one array, and its origin."""
    d = RAW / "ortho2023" / str(ORTHO_Z)
    tx0, ty0, tx1, ty1 = int(mx0 // 256), int(my0 // 256), int(mx1 // 256), int(my1 // 256)
    im = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), np.uint8)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            p = d / f"{tx}_{ty}.jpg"
            if p.exists():
                im[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = np.asarray(
                    Image.open(p).convert("RGB"))
    return im, tx0 * 256, ty0 * 256


def grid_masks(box):
    """North-up masks over box at GRID m: building footprints, bridge decks, tree crowns (0/255)."""
    e0, e1, n0, n1 = box
    W, H = int((e1 - e0) / GRID) + 1, int((n1 - n0) / GRID) + 1

    def to_px(en):
        return np.round(np.column_stack(((en[..., 0] + ORIGIN_E - e0) / GRID, (n1 - en[..., 1] - ORIGIN_N) / GRID))
                        * 4).astype(np.int32)

    bld = np.zeros((H, W), np.uint8)
    d = np.load(WORK / "buildings.npz")
    tris, kind = d["tris"][..., :2], d["tri_kind"]
    sel = (kind != 0)
    t = tris[sel]
    inb = ((t[..., 0] + ORIGIN_E > e0) & (t[..., 0] + ORIGIN_E < e1) & (t[..., 1] + ORIGIN_N > n0)
           & (t[..., 1] + ORIGIN_N < n1)).any(1)
    t = t[inb]
    polys = to_px(t.reshape(-1, 2)).reshape(-1, 3, 2)
    cv2.fillPoly(bld, list(polys), 255, shift=2)
    # walls are upright: in plan they are lines, which fillPoly draws one px wide; that is the outline we want
    deck = np.zeros((H, W), np.uint8)
    br = np.load(WORK / "bridges.npz")
    for key in ("deck", "deck_red"):
        if key in br.files and len(br[key]):
            dp = br[key][:, :2].reshape(-1, 3, 2)
            cv2.fillPoly(deck, list(to_px(dp.reshape(-1, 2)).reshape(-1, 3, 2)), 255, shift=2)
    crown = np.zeros((H, W), np.uint8)
    trees = json.loads((inputs_dir("b00") / "trees_lidar2024.json").read_text())
    for tr in trees:
        if not (e0 < tr["e"] < e1 and n0 < tr["n"] < n1):
            continue
        r = max(1.2, tr["cmean"] * 1.1) / GRID
        cv2.circle(crown, (int((tr["e"] - e0) / GRID), int((n1 - tr["n"]) / GRID)), int(round(r)), 255, -1)
    return bld, deck, crown


def inpaint_big(img, mask, f=4):
    """Fill large masked areas with the local average colour of the ground round them (normalised convolution at
    two scales, so small holes take their near surroundings and large ones a wider average), plus a little grain so
    the painter sees calm paving or ground, not a smear or a dark blob."""
    h, w = mask.shape
    sm = cv2.resize(img, (w // f, h // f), interpolation=cv2.INTER_AREA).astype(np.float32)
    valid = (cv2.resize(mask, (w // f, h // f), interpolation=cv2.INTER_AREA) < 20).astype(np.float32)
    # dark pixels (roof shadows on the street) count less, so the fill is not dragged towards black
    lum = sm @ np.array((0.3, 0.59, 0.11), np.float32)
    wgt = valid * np.clip((lum - 40) / 60, 0.15, 1)
    fill = np.zeros_like(sm)
    acc = np.zeros(sm.shape[:2], np.float32)
    for sig in (3.0, 10.0, 30.0):   # m
        sp = sig * 4 * (w / 6000) / f
        num = cv2.GaussianBlur(sm * wgt[..., None], (0, 0), sp)
        den = cv2.GaussianBlur(wgt, (0, 0), sp)
        ok = (den > 0.05) & (acc < 0.5)
        fill[ok] = num[ok] / den[ok][..., None]
        acc[ok] = 1
    fill[acc < 0.5] = np.median(sm[valid > 0], axis=0)
    fill = cv2.resize(fill, (w, h), interpolation=cv2.INTER_CUBIC)
    rng = np.random.default_rng(3)
    grain = (cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 1.2) * 5
             + cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 6) * 8)
    fill += grain[..., None]
    a = cv2.GaussianBlur((mask > 0).astype(np.float32), (0, 0), 1.0)[..., None]
    return (img.astype(np.float32) * (1 - a) + fill * a).clip(0, 255).astype(np.uint8)


def road_masks(b, k, shape):
    from draw_ground import draw_roads
    L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
    return draw_roads(L, b, k, shape)


def prep(k):
    b = block("b00")
    d = v2_dir("ground")
    G = ground_pass(b, k)
    H, W = G.shape[:2]
    ok = ~np.isnan(G[..., 0])
    e = np.nan_to_num(G[..., 0]) + ORIGIN_E
    n = np.nan_to_num(G[..., 1]) + ORIGIN_N
    np.save(d / f"G_k{round(k * 100)}.npy", G.astype(np.float32))
    # 1. the photo, draped
    lon, lat = en_to_lonlat(e.ravel(), n.ravel())
    mx, my = merc_px(np.asarray(lon).reshape(H, W), np.asarray(lat).reshape(H, W))
    sel = ok
    ortho, ox, oy = load_ortho_box(mx[sel].min() - 2, my[sel].min() - 2, mx[sel].max() + 2, my[sel].max() + 2)
    print("ortho box", ortho.shape, flush=True)
    photo = np.zeros((H, W, 3), np.uint8)
    for c in range(3):
        photo[..., c] = np.clip(sample(ortho[..., c], mx - ox, my - oy), 0, 255).astype(np.uint8)
    del ortho
    photo[~ok] = BG
    # 2. what must not be painted into the ground, on the north-up grid, then looked up per pixel
    box = block_en(b)
    e0, e1, n0, n1 = box
    bld, deck, crown = grid_masks(box)
    gx, gy = (e - e0) / GRID, (n1 - n) / GRID
    ker = lambda m: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(m / GRID) + 1,) * 2)  # noqa: E731
    bld_d = cv2.dilate(bld, ker(1.5))      # roofs lean a little in the photo
    deck_d = cv2.dilate(deck, ker(4.0))
    crown_d = cv2.dilate(crown, ker(0.8))
    m_bld = sample(bld_d, gx, gy, nearest=True) > 0
    m_deck = sample(deck_d, gx, gy, nearest=True) > 0
    m_crown = sample(crown_d, gx, gy, nearest=True) > 0
    # water: the photo's river is fine (no trees over it are filled from the bank)
    rm = road_masks(b, k, (H, W))
    road = np.maximum(rm["road"], rm["ped"]) > 0.3
    # 3. cars: median along the roads
    med = cv2.medianBlur(photo, max(3, int(round(15 * k / (PAINT / 6000))) | 1))
    rd = cv2.GaussianBlur(road.astype(np.float32), (0, 0), 1.0)[..., None]
    clean = (photo * (1 - rd) + med * rd).astype(np.uint8)
    lc = np.load(LAYERS / "b00" / "k85" / "landcover.npy")
    if lc.shape != (H, W):
        lc = cv2.resize(lc, (W, H), interpolation=cv2.INTER_NEAREST)
    # 4. tree crowns over green ground (lawns, woods, gardens): a plain lawn or woodland-floor texture shaded by
    #    the terrain, so the painter paints ground there, not a second tree; crowns over paving, roads and water
    #    are filled from their surroundings like the buildings
    hard = np.isin(lc, [0, 8, 9, 10, 12]) | road
    # the crowns' own shadows next to them (dark pixels within 4 m of a crown) go too, or they get painted as trees
    near = cv2.dilate(m_crown.astype(np.uint8), np.ones((int(8 * 4 * k * 0.5) | 1,) * 2, np.uint8)) > 0
    plum = clean.astype(np.float32) @ np.array((0.3, 0.59, 0.11), np.float32)
    # (only on gentle ground: on cliffs and walls the dark is the rock face in shade, which must stay)
    gentle = slope_normals(G)[..., 2] > np.cos(np.radians(32))
    m_crown = m_crown | (near & (plum < 72) & ~road & gentle)
    green = m_crown & ~hard & ok & ~m_bld & ~m_deck
    gsrc = clean.astype(np.float32)
    lawn_px = np.isin(lc, [1, 4, 5, 6, 7]) & ~m_crown & ~m_bld & ok
    # a sunny lawn (the brighter lawn pixels of the photo), so the painter reads open grass, not a wood
    if lawn_px.sum() > 100:
        lp = gsrc[lawn_px]
        lum = lp @ np.array((0.3, 0.59, 0.11), np.float32)
        exg = 2 * lp[:, 1] - lp[:, 0] - lp[:, 2]
        lawn = np.median(lp[(exg > np.percentile(exg, 60)) & (lum > np.percentile(lum, 40))], axis=0)
    else:
        lawn = np.array((140, 150, 90), np.float32)
    nrm = slope_normals(G)
    L = np.array((-0.62, 0.25, 0.74), np.float32); L /= np.linalg.norm(L)
    shade = np.clip(0.92 + 0.35 * ((nrm @ L) - L[2]), 0.7, 1.12)
    rng = np.random.default_rng(5)
    def nz(sig, amp):
        return cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), sig) * amp
    tex = (nz(0.7 * k * 4, 3.5) + nz(3 * k * 4, 3) + nz(14 * k * 4, 3))[..., None]
    base = np.where(np.isin(lc, [2, 3])[..., None], lawn * np.array((0.97, 0.92, 0.8), np.float32), lawn)
    gfill = (base * shade[..., None] + tex * np.array((0.9, 1.0, 0.7), np.float32)).clip(0, 255)
    ga = cv2.GaussianBlur(green.astype(np.float32), (0, 0), 1.2)[..., None]
    clean = (gsrc * (1 - ga) + gfill * ga).astype(np.uint8)
    hole = ((m_bld | m_deck | (m_crown & ~green)) & ok).astype(np.uint8) * 255
    src = inpaint_big(clean, hole, 4 if k > 0.5 else 2)
    src[~ok] = BG
    Image.fromarray(src).save(d / "src.png")
    Image.fromarray(photo).save(d / "photo_draped.png")
    np.savez_compressed(d / "masks.npz", bld=np.packbits(m_bld), deck=np.packbits(m_deck),
                        crown=np.packbits(m_crown), road=np.packbits(road), ok=np.packbits(ok), shape=np.array((H, W)))
    # 5. layout: ground classes from version 1's land cover (same grid as k85), roads and rails, no buildings
    lay = np.zeros((H, W, 3), np.uint8)
    lay[:] = (226, 218, 198)
    lay[np.isin(lc, [1, 2, 3, 4, 5, 6, 7])] = (110, 170, 90)
    # under the crowns of woods the layout says plain ground: a green layout there makes the painter draw trees
    lay[m_crown & np.isin(lc, [2, 3])] = (226, 218, 198)
    lay[lc == 9] = (185, 185, 190)
    lay[lc == 12] = (60, 120, 210)
    lay[rm["road"] > 0.5] = (150, 150, 155)
    lay[rm["ped"] > 0.5] = (205, 190, 160)
    lay[rm["dash"] > 0.5] = (250, 250, 250)
    lay[rm["rbed"] > 0.5] = (150, 110, 70)
    lay[(rm["rail"] > 0.5) | (rm["tram"] > 0.5)] = (40, 36, 34)
    lay[~ok] = BG
    Image.fromarray(lay).save(d / "layout.png")
    # previews: photo as draped, what was taken out, the painter's input
    s = 1600 / W
    show = lambda a: cv2.resize(np.asarray(a), (1600, round(H * s)), interpolation=cv2.INTER_AREA)  # noqa: E731
    over = photo.astype(np.float32).copy()
    over[m_bld & ok] = over[m_bld & ok] * 0.4 + np.array((230, 60, 60)) * 0.6
    over[m_crown & ok & ~m_bld] = over[m_crown & ok & ~m_bld] * 0.4 + np.array((60, 220, 90)) * 0.6
    over[m_deck & ok] = over[m_deck & ok] * 0.4 + np.array((80, 120, 255)) * 0.6
    over[road & ok & ~m_bld] = over[road & ok & ~m_bld] * 0.6 + np.array((250, 220, 60)) * 0.4
    trip = np.concatenate([show(photo), show(over.clip(0, 255).astype(np.uint8)), show(src)], 1)
    preview(trip, POC_IMG / "v2_s1_inputs.jpg")
    print("ground inputs in", d, flush=True)


def tree_mask(P, gentle=None, protect=None):
    """Where the painter drew trees into the ground: clumps of dark, clearly green paint (painted crowns are dark
    green with light leaves and ink outlines; painted lawns, hedges and garden beds are lighter or smaller), plus
    their dark painted shadows on gentle ground. `protect` (roads, rails, water) is never touched."""
    f = P.astype(np.float32)
    r, g, bl = f[..., 0], f[..., 1], f[..., 2]
    lum = f @ np.array((0.3, 0.59, 0.11), np.float32)
    core = ((g > r + 8) & (g > bl + 14) & (lum < 92)).astype(np.uint8)
    core = cv2.morphologyEx(core, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(core)
    big = np.zeros(n, bool); big[1:] = st[1:, cv2.CC_STAT_AREA] >= 40
    tree = big[lab].astype(np.uint8)
    tree = cv2.dilate(tree, np.ones((5, 5), np.uint8))      # the light leaves and ink round the dark core
    near = cv2.dilate(tree, np.ones((9, 9), np.uint8)) > 0
    shadow = near & (lum < 70)
    if gentle is not None:
        shadow &= gentle
    m = tree.astype(bool) | shadow
    if protect is not None:
        m &= ~protect
    return m


def untree(P, m, f=4):
    """Replace painted trees by the painting's own lawn: the local average of the smooth green ground round them
    (or the block's lawn colour where there is none), a little darker (shade under trees), with a fine grain."""
    h, w = m.shape
    fp = P.astype(np.float32)
    lum = fp @ np.array((0.3, 0.59, 0.11), np.float32)
    m1 = cv2.blur(lum, (7, 7))
    sd = np.sqrt(np.clip(cv2.blur(lum * lum, (7, 7)) - m1 * m1, 0, None))
    lawnpx = (~m) & (fp[..., 1] > fp[..., 0] + 4) & (fp[..., 1] > fp[..., 2] + 12) & (sd < 18) & (lum > 85)
    lawn = np.median(fp[lawnpx], axis=0) if lawnpx.sum() > 500 else np.array((128, 150, 70), np.float32)
    sm = cv2.resize(fp, (w // f, h // f), interpolation=cv2.INTER_AREA)
    wv = cv2.resize(lawnpx.astype(np.float32), (w // f, h // f), interpolation=cv2.INTER_AREA)
    fill = np.zeros_like(sm); acc = np.zeros(wv.shape, bool)
    for sig in (6.0, 20.0):
        sp = sig * 4 * (w / 6000) / f
        num = cv2.GaussianBlur(sm * wv[..., None], (0, 0), sp); den = cv2.GaussianBlur(wv, (0, 0), sp)
        okk = (den > 0.04) & ~acc
        fill[okk] = num[okk] / den[okk][..., None]; acc |= okk
    fill[~acc] = lawn
    fill = cv2.resize(fill, (w, h), interpolation=cv2.INTER_CUBIC) * 0.93
    rng = np.random.default_rng(9)
    gr = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), 0.9) * 6
    fill += gr[..., None] * np.array((0.8, 1.0, 0.6), np.float32)
    a = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2)[..., None]
    return (fp * (1 - a) + fill * a).clip(0, 255).astype(np.uint8)


def finish(painted):
    d = v2_dir("ground")
    P = np.asarray(Image.open(painted).convert("RGB"))
    S = P.shape[0]
    ref = np.asarray(Image.open(d / "src.png").convert("L").resize((S, S), Image.LANCZOS)).astype(np.float32)
    dx, dy = painter_shift(np.asarray(Image.fromarray(P).convert("L")).astype(np.float32), ref, n=6)
    print(f"painter shift: dx {dx:.2f}, dy {dy:.2f} px", flush=True)
    (d / "shift.txt").write_text(f"{dx} {dy}\n")
    out = unshift(P, dx, dy)
    # check: the shift left after undoing it
    dx2, dy2 = painter_shift(np.asarray(Image.fromarray(out).convert("L")).astype(np.float32), ref, n=6)
    print(f"after undoing: dx {dx2:.2f}, dy {dy2:.2f} px", flush=True)
    (d / "shift_after.txt").write_text(f"{dx2} {dy2}\n")
    Image.fromarray(out).save(d / "L1_painted.png")
    clean(out)


def clean(P=None):
    """The ground layer must not show trees: the trees the painter drew into the ground anyway (and their painted
    shadows) are found where the ground is actually seen (not under a building or a real tree) and replaced by the
    painting's own lawn, a little shaded. Roads, rails and water are never touched.
    -> L1_ground.png, trees_removed.png"""
    d = v2_dir("ground")
    if P is None:
        P = np.asarray(Image.open(d / "L1_painted.png").convert("RGB"))
    S = P.shape[0]
    G = np.load(d / "G_k85.npy")
    gentle = slope_normals(G)[..., 2] > np.cos(np.radians(32))
    mk = np.load(d / "masks.npz")
    road = np.unpackbits(mk["road"])[:S * S].reshape(S, S).astype(bool)
    wm = np.asarray(Image.open(LAYERS / "b00" / "k85" / "water_mask.png").convert("L")) > 127
    protect = cv2.dilate((road | wm).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    seen = np.ones((S, S), bool)
    cp = canopy_path()
    if cp.exists():
        seen &= np.load(cp)["vis"] == 0
    for n in ("L7_buildings", "L5_bridges"):
        seen &= np.asarray(Image.open(LAYERS / "b00" / "objects" / f"{n}.png"))[..., 3] < 128
    seen = cv2.dilate(seen.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    m = tree_mask(P, gentle, protect) & seen
    out = untree(P, m)
    Image.fromarray(out).save(d / "L1_ground.png")
    Image.fromarray((m * 255).astype(np.uint8)).save(d / "trees_removed.png")
    print(f"painted trees removed from the ground: {m.mean():.1%} of the block", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--k", type=float, default=PAINT / 6000)
    a = ap.parse_args()
    if a.cmd == "prep":
        prep(a.k)
    elif a.cmd == "clean":
        clean()
    elif a.cmd == "finish":
        finish(a.args[0])
    else:
        sys.exit("prep | finish <painted.png>")
