"""Paint-over fix for the Red Bridge road surface: the image model insists on red stripes on the deck (in reality
the road is grey; only the girder sides and legs are red). We know exactly where the deck top is from the 3D
model, so inside it (minus a thin rim, which shows the red sides), red pixels are turned into grey of the same
lightness. Usage: fix_redbridge_deck.py <painted.png> <x0> <y0> <src_w> <out.png>"""
import json
import math
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw
from common import WORK, R, ELEV

src, x0, y0, sw, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
m = json.loads((WORK / "mosaic.json").read_text())
im = Image.open(src).convert("RGB")
k = im.width / sw
deck = np.load(WORK / "bridges.npz")["deck_red"].reshape(-1, 3, 3)  # local E, N, z


def px(p):
    sx = (p[0] + p[1]) * R
    sy = (-p[0] + p[1]) * R * math.sin(ELEV) + p[2] * math.cos(ELEV)
    return (((sx - m["sx0"]) / m["mpp"]) - x0) * k, (((m["sy1"] - sy) / m["mpp"]) - y0) * k


mask = Image.new("L", im.size, 0)
d = ImageDraw.Draw(mask)
for tri in deck:
    d.polygon([px(p) for p in tri], fill=255)
mk = np.asarray(mask) > 0
rim = max(2, int(round(1.2 / 0.25 * k)))  # keep ~1.2 m along the edges: that is where the red sides show
mk = cv2.erode(mk.astype(np.uint8), np.ones((2 * rim + 1, 2 * rim + 1), np.uint8)) > 0
a = np.asarray(im).copy()
hsv = cv2.cvtColor(a, cv2.COLOR_RGB2HSV).astype(int)
h, s = hsv[..., 0] * 2, hsv[..., 1]
red = mk & ((h <= 25) | (h >= 335)) & (s >= 60)
red = cv2.dilate(red.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & mk
grey = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
road = np.clip(grey.astype(int) * 0.85 + 20, 0, 255).astype(np.uint8)  # asphalt grey, same light and shade
for ch in range(3):
    a[..., ch][red] = road[red]
Image.fromarray(a).save(out)
print("deck px", int(mk.sum()), "red px recoloured", int(red.sum()))
