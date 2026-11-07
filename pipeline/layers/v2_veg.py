"""Layered map v2, layer 3 (painting and cutting): the vegetation painted in place, then cut by the canopy mask.

  v2_veg.py prep [--crop x,y,w] [--tag spring]
        -> b00_v2/veg[_tag]/src.png, known.png, keep.png, layout.png: the context (painted ground, ink lines, the
           version 1 buildings and bridges) with the shaded 3D crowns on top; everything but the crowns is held,
           so the model paints only the trees, but sees the painted surroundings and blends into them.
           --crop paints only part of the block (layer px at 5120 scale), for the season test.
  v2_veg.py cut <painted.png> [--tag spring] [--crop x,y,w]
        -> b00_v2/veg[_tag]/L3_veg.png (RGBA): the painted crowns and trunks, kept only where the 3D canopy is
           visible (after the depth test with buildings and terrain), with a soft edge INSIDE that area only;
           L3_veg_clear.png: the same with the canopy thinned in front of the major landmarks;
           contact.png: the soft ground darkening under the crowns (RGBA), for the ground under the buildings.
"""
import argparse
import json

import cv2
import numpy as np
from PIL import Image

from layers_common import LAYERS, POC_IMG, ROOT, block, preview, unshift
from v2_ground import PAINT, v2_dir

V1 = LAYERS / "b00"
CONTACT = (30, 40, 34)


def canopy():
    z = np.load(v2_dir("canopy") / "canopy_k85.npz")
    return {k: z[k] for k in z.files}


def objects_v1():
    bl = np.asarray(Image.open(V1 / "objects" / "L7_buildings.png")).astype(np.float32)
    br = np.asarray(Image.open(V1 / "objects" / "L5_bridges.png")).astype(np.float32)
    a = np.maximum(bl[..., 3], br[..., 3]) / 255
    rgb = np.where((br[..., 3] > bl[..., 3])[..., None], br[..., :3], bl[..., :3])
    return rgb, a


def context():
    """Painted ground + ink + version 1 buildings and bridges (what the viewer stacks, without trees)."""
    g = np.asarray(Image.open(v2_dir("ground") / "L1_ground.png").convert("RGB")).astype(np.float32)
    ink = np.asarray(Image.open(v2_dir("ink") / "L2_ink.png")).astype(np.float32)
    ai = ink[..., 3:] / 255
    img = g * (1 - ai) + ink[..., :3] * ai
    rgb, a = objects_v1()
    img = img * (1 - a[..., None]) + rgb * a[..., None]
    return img


def prep(tag, crop):
    d = v2_dir("veg" + (f"_{tag}" if tag else ""))
    C = canopy()
    vis = C["vis"] > 0
    ctx = context()
    src = ctx.copy()
    src[vis] = C["shade"][vis]
    # layout: version 1's layout map (with the buildings), crowns in the painter's green
    lay = np.asarray(Image.open(V1 / "objects" / "layout_full.png").convert("RGB").resize((PAINT, PAINT), Image.NEAREST)).copy()
    gl = np.asarray(Image.open(v2_dir("ground") / "layout.png").convert("RGB"))
    ground = C["behind"] == 1
    lay[ground] = gl[ground]
    lay[vis] = (110, 170, 90)
    lay[C["trunk"] & vis] = (110, 90, 70)
    keep = ~cv2.dilate(vis.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    if tag:  # a season pass starts from the painted summer trees
        summer = np.asarray(Image.open(v2_dir("veg") / "L3_veg.png")).astype(np.float32)
        a = summer[..., 3:] / 255
        src = src * (1 - a) + summer[..., :3] * a
    if crop:
        x, y, w = crop
        src, lay, keep, ctx = (arr[y:y + w, x:x + w] for arr in (src, lay, keep, ctx))
    Image.fromarray(src.clip(0, 255).astype(np.uint8)).save(d / "src.png")
    Image.fromarray(ctx.clip(0, 255).astype(np.uint8)).save(d / "known.png")
    Image.fromarray((keep * 255).astype(np.uint8)).save(d / "keep.png")
    Image.fromarray(lay).save(d / "layout.png")
    print("veg inputs in", d, f"painting {(~keep).mean():.0%} of the area")


def measure_shift(P, ref, vis, tile=384):
    """The painter's shift, measured only on tiles that are mostly painted trees (held pixels do not move)."""
    def ed(a):
        return cv2.Laplacian(cv2.GaussianBlur(a, (0, 0), 1.5), cv2.CV_32F).astype(np.float64)
    H, W = vis.shape
    win = cv2.createHanningWindow((tile, tile), cv2.CV_64F)
    got = []
    for y in range(0, H - tile, tile // 2):
        for x in range(0, W - tile, tile // 2):
            if vis[y:y + tile, x:x + tile].mean() < 0.55:
                continue
            (dx, dy), r = cv2.phaseCorrelate(ed(ref[y:y + tile, x:x + tile]), ed(P[y:y + tile, x:x + tile]), win)
            if r > 0.08 and abs(dx) < 20 and abs(dy) < 20:
                got.append((dx, dy))
    if not got:
        return 0.0, 0.0, 0
    g = np.array(got)
    return float(np.median(g[:, 0])), float(np.median(g[:, 1])), len(got)


def landmark_zone(k):
    """Building pixels of the major landmarks (churches, palace, abbey...): within 40 m of the landmark's map point."""
    b = block("b00")
    L = json.loads((ROOT / "web" / "public" / "data" / "landmarks.json").read_text())
    z = np.zeros((PAINT, PAINT), np.uint8)
    for lm in L:
        if lm.get("category") != "landmark":
            continue
        x, y = (lm["x"] - b["x0"]) * k, (lm["y"] - b["y0"]) * k
        if 0 <= x < PAINT and 0 <= y < PAINT:
            cv2.ellipse(z, (int(x), int(y)), (int(40 * 4 * k), int(40 * 4 * k)), 0, 0, 360, 1, -1)
    return z > 0


def cut(painted, tag, crop):
    d = v2_dir("veg" + (f"_{tag}" if tag else ""))
    C = canopy()
    vis_id = C["vis"]
    if crop:
        x, y, w = crop
        sl = (slice(y, y + w), slice(x, x + w))
    else:
        sl = (slice(None), slice(None))
    vis = vis_id[sl] > 0
    P = np.asarray(Image.open(painted).convert("RGB"))
    if P.shape[:2] != vis.shape:
        P = np.asarray(Image.open(painted).convert("RGB").resize(vis.shape[::-1], Image.LANCZOS))
    src = np.asarray(Image.open(d / "src.png").convert("L")).astype(np.float32)
    dx, dy, nt = measure_shift(np.asarray(Image.fromarray(P).convert("L")).astype(np.float32), src, vis)
    print(f"painter shift on the trees: dx {dx:.2f}, dy {dy:.2f} px ({nt} tiles); undone", flush=True)
    (d / "shift.txt").write_text(f"{dx} {dy} {nt}\n")
    P = unshift(P, dx, dy).astype(np.float32)
    # alpha: 1 inside the visible canopy, fading to 0 over the last 1.5 px INSIDE it; 0 everywhere outside
    dist = cv2.distanceTransform(vis.astype(np.uint8), cv2.DIST_L2, 3)
    a = np.clip(dist / 1.5, 0, 1) * vis
    # tiny crowns (street trees far off) keep their core even if thinner than the soft edge
    a = np.where(vis & (a < 0.45) & (cv2.erode(vis.astype(np.uint8), np.ones((3, 3), np.uint8)) == 0), np.maximum(a, 0.45) * vis, a)
    full_a = np.zeros(vis_id.shape, np.float32); full_a[sl] = a
    full_rgb = np.zeros(vis_id.shape + (3,), np.float32); full_rgb[sl] = P
    if tag:  # outside the crop, keep the summer layer (the test only paints part of the block)
        summer = np.asarray(Image.open(v2_dir("veg") / "L3_veg.png")).astype(np.float32)
        out_rgb, out_a = summer[..., :3].copy(), summer[..., 3] / 255
        out_rgb[sl] = P; out_a[sl] = a
        full_rgb, full_a = out_rgb, out_a
    rgba = np.dstack((full_rgb.clip(0, 255), (full_a * 255).round())).astype(np.uint8)
    Image.fromarray(rgba).save(d / "L3_veg.png")
    # keep landmarks clear: no canopy over the building pixels of the major landmarks
    lz = landmark_zone(PAINT / 6000) & (C["behind"] == 2)
    clear = rgba.copy()
    clear[..., 3] = np.where(lz, 0, clear[..., 3])
    Image.fromarray(clear).save(d / "L3_veg_clear.png")
    if not tag:
        c = C["contact"].astype(np.float32) * (C["behind"] == 1)
        ca = np.dstack([np.full(c.shape, v, np.uint8) for v in CONTACT] + [(np.clip(c, 0, 1) * 0.42 * 255).astype(np.uint8)])
        Image.fromarray(ca).save(d / "contact.png")
    print("vegetation layer", f"{(full_a > 0.5).mean():.1%} of the block", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--tag", default="")
    ap.add_argument("--crop", help="x,y,w in layer px (5120 scale)")
    a = ap.parse_args()
    crop = tuple(int(v) for v in a.crop.split(",")) if a.crop else None
    if a.cmd == "prep":
        prep(a.tag, crop)
    elif a.cmd == "cut":
        cut(a.args[0], a.tag, crop)
