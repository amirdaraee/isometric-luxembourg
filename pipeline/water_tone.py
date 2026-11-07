"""Give painted water the map's river colour, keeping its painted texture.

Only real water is touched: OpenStreetMap water polygons, limited to where the ground is visible from above
(web/public/data/visibility.png) and to pixels already painted bluish (trees over the banks stay green). In CIELAB, the hue and saturation (a, b) of those pixels are moved to the
target colour's, and the lightness keeps its painted variation around the target's lightness. Edges are feathered.

Usage: water_tone.py <painted.png> <x0> <y0> <w> <h> <out.png> [reference.png]
  x0, y0, w, h: mosaic px the painting covers. The target colour is the mean water colour of reference.png (default
  data/work/tiles/v2/day_fixed.png, the showcase, covering 5500, 3700, 6000, 6000), so blocks match the old town.
"""
import json
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

from common import ROOT, WORK

Image.MAX_IMAGE_PIXELS = None
REF = (WORK / "tiles" / "v2" / "day_fixed.png", 5500, 3700, 6000, 6000)


def water_mask(x0, y0, w, h, W, H):
    """Water polygons, visible from above, in the painted image's pixels (W x H)."""
    L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
    sx, sy = W / w, H / h
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    for wtr in L["water"]:
        p = wtr["p"]
        pts = [((p[i] - x0) * sx, (p[i + 1] - y0) * sy) for i in range(0, len(p), 2)]
        if len(pts) >= 3:
            d.polygon(pts, fill=255)
    vis = Image.open(ROOT / "web" / "public" / "data" / "visibility.png").convert("L")  # 1 px = 8 map px
    vx0, vy0 = x0 / 8, y0 / 8
    vis = vis.transform((W, H), Image.AFFINE, (w / 8 / W, 0, vx0, 0, h / 8 / H, vy0), Image.NEAREST)
    mask = (np.asarray(m) > 0) & (np.asarray(vis) == 255)
    return mask


def lab(img):
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2LAB).astype(np.float32)


def target_colour(ref=REF):
    path, x0, y0, w, h = ref
    im = Image.open(path).convert("RGB")
    m = water_mask(x0, y0, w, h, im.width, im.height)
    m = cv2.erode(m.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0  # away from the banks
    return lab(im)[m].mean(axis=0)


def main():
    src, x0, y0, w, h, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
    ref = (sys.argv[7], *REF[1:]) if len(sys.argv) > 7 else REF
    im = Image.open(src).convert("RGB")
    m = water_mask(x0, y0, w, h, im.width, im.height)
    if not m.any():
        im.save(out)
        print("no visible water")
        return
    t = target_colour(ref)
    a = lab(im)
    # inside the outline, only pixels already painted as water (bluish, not dark): trees over the banks are
    # yellow-green (b > 128 in OpenCV's LAB) and are left alone
    m &= (a[..., 2] < 129) & (a[..., 0] > 25)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
    cur = a[m].mean(axis=0)
    new = a.copy()
    new[..., 0] = t[0] + (a[..., 0] - cur[0]) * 0.8          # keep the ripples, at the target's lightness
    new[..., 1] = t[1] + (a[..., 1] - cur[1]) * 0.5
    new[..., 2] = t[2] + (a[..., 2] - cur[2]) * 0.5
    alpha = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 2.0)[..., None]
    mixed = a * (1 - alpha) + new * alpha
    rgb = cv2.cvtColor(np.clip(mixed, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    Image.fromarray(rgb).save(out)
    print(f"water px {int(m.sum())}: LAB {cur.round(1).tolist()} -> {t.round(1).tolist()}")


if __name__ == "__main__":
    main()
