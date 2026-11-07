"""Compare painted water with OSM water: flag water the model invented, and real water it left out.
Usage: water_check.py <patch.png> <x0> <y0> <src_w> <src_h> <out prefix>
Writes <prefix>_water.jpg (red = invented, yellow = missing) and <prefix>_water.json (flagged tiler windows)."""
import json
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw
from common import ROOT

patch, x0, y0, sw, sh, pref = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
im = Image.open(patch).convert("RGB")
k = im.width / sw
W, H = im.size
CELL = 512  # tiler cell size in painted pixels

# OSM water mask: polygons, plus rivers/streams drawn at a plausible width (rivers ~ 14 m, streams ~ 4 m).
osm = Image.new("L", (W, H), 0)
d = ImageDraw.Draw(osm)
px_per_m = k / 0.25
for w in L["water"]:
    q = [((w["p"][i] - x0) * k, (w["p"][i + 1] - y0) * k) for i in range(0, len(w["p"]), 2)]
    if len(q) > 2:
        d.polygon(q, fill=255)
for w in L["waterways"]:
    if w.get("t"):
        continue
    q = [((w["p"][i] - x0) * k, (w["p"][i + 1] - y0) * k) for i in range(0, len(w["p"]), 2)]
    d.line(q, fill=255, width=max(2, int((14 if w["k"] == "river" else 4) * px_per_m)))
osm = np.asarray(osm) > 0

# Painted water: dark, blue-green, fairly flat colour.
hsv = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2HSV).astype(int)
h, s, v = hsv[..., 0] * 2, hsv[..., 1], hsv[..., 2]
gray = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2GRAY).astype(float)
tex = np.sqrt(np.maximum(cv2.blur(gray ** 2, (21, 21)) - cv2.blur(gray, (21, 21)) ** 2, 0))
# Painted water is a smooth, dark, saturated blue-green; shadows are less saturated, trees and roofs are textured.
water = (h >= 150) & (h <= 230) & (s >= 45) & (v >= 30) & (v <= 130) & (tex < 12)
bgd = np.abs(np.asarray(im).astype(int) - np.array([16, 24, 40])).sum(axis=2) < 30
water &= ~(cv2.dilate(bgd.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0)  # not the empty map edge
water = cv2.morphologyEx(water.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
water = cv2.morphologyEx(water, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)) > 0

near = cv2.dilate(osm.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0  # allow ~10 m slack
invented = water & ~near
painted_near = cv2.dilate(water.astype(np.uint8), np.ones((25, 25), np.uint8)) > 0
missing = osm & ~painted_near

flags = []
for name, mask, min_m2 in (("invented", invented, 600), ("missing", missing, 600)):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    for i in range(1, n):
        area_m2 = stats[i, cv2.CC_STAT_AREA] / px_per_m ** 2
        if area_m2 < min_m2:
            continue
        x, y, w_, h_ = stats[i, :4]
        cx, cy = x + w_ / 2, y + h_ / 2
        flags.append({"kind": name, "area_m2": round(float(area_m2)), "box": [int(x), int(y), int(w_), int(h_)],
                      "cell": [int(cx // CELL), int(cy // CELL)],
                      "mosaic_xy": [round(x0 + cx / k), round(y0 + cy / k)]})

ov = np.asarray(im).copy()
ov[invented] = (0.45 * ov[invented] + 0.55 * np.array([255, 40, 40])).astype(np.uint8)
ov[missing] = (0.45 * ov[missing] + 0.55 * np.array([255, 220, 0])).astype(np.uint8)
out = Image.fromarray(ov)
dd = ImageDraw.Draw(out)
for f in flags:
    x, y, w_, h_ = f["box"]
    dd.rectangle((x - 6, y - 6, x + w_ + 6, y + h_ + 6), outline=(255, 0, 0) if f["kind"] == "invented" else (255, 200, 0), width=5)
out.save(pref + "_water.jpg", quality=85)
# Cells worth repainting: any 512 px cell where flagged pixels cover more than 1.5 % of it.
cells = []
for r in range(H // CELL):
    for c in range(W // CELL):
        sl = (slice(r * CELL, (r + 1) * CELL), slice(c * CELL, (c + 1) * CELL))
        fi, fm = invented[sl].mean(), missing[sl].mean()
        if fi > 0.015 or fm > 0.015:
            cells.append({"cell": [c, r], "invented": round(float(fi), 3), "missing": round(float(fm), 3)})
json.dump({"flags": flags, "cells": cells}, open(pref + "_water.json", "w"), indent=1)
np.save(pref + "_invented.npy", np.packbits(invented))
print(len(cells), "cells to repaint:", [c["cell"] for c in cells])
print(len([f for f in flags if f["kind"] == "invented"]), "invented,", len([f for f in flags if f["kind"] == "missing"]), "missing")
for f in sorted(flags, key=lambda f: -f["area_m2"]):
    print(f["kind"], f["area_m2"], "m2 at cell", f["cell"])
