"""Draw roads, tracks and water from OSM directly over the painted map, in the ink style.

Geometry is exact (OSM, projected with terrain height; bridge roads at deck height). Occlusion: ground features only
where the 3D visibility pass shows ground, bridge roads only on visible decks, and painted foliage stays on top.
The painting's own light (blurred luminance) is multiplied in, so shadows still fall across roads and water.
Drawn at 2x and downsampled for clean anti-aliased edges.

Usage: vector_overlay.py <painted.png> <kind.png> <x0> <y0> <src_w> <crop x,y,w,h in painted px> <out.jpg>
"""
import json
import sys
import numpy as np
import cv2
from PIL import Image
from common import ROOT

painted, kindp = sys.argv[1], sys.argv[2]
X0, Y0, SW = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
cx, cy, cw, ch = map(int, sys.argv[6].split(","))
out_path = sys.argv[7]
SS = 2  # supersampling

full = Image.open(painted).convert("RGB")
k = full.width / SW                       # painted px per mosaic px
ppm = k * 4                               # painted px per metre (mosaic is 0.25 m/px)
img = np.asarray(full.crop((cx, cy, cx + cw, cy + ch))).astype(np.float32)
kind_full = Image.open(kindp).convert("L")
kind = np.asarray(kind_full.resize(full.size, Image.NEAREST).crop((cx, cy, cx + cw, cy + ch)))
ground, deck = kind > 200, (kind > 100) & (kind <= 200)
L = json.loads((ROOT / "web/public/data/lines.json").read_text())
W2, H2 = cw * SS, ch * SS


def pts(p):
    a = np.array(p, np.float32).reshape(-1, 2)
    a[:, 0] = ((a[:, 0] - X0) * k - cx) * SS
    a[:, 1] = ((a[:, 1] - Y0) * k - cy) * SS
    return a


def onscreen(a, pad=200):
    return ((a[:, 0] > -pad) & (a[:, 0] < W2 + pad) & (a[:, 1] > -pad) & (a[:, 1] < H2 + pad)).any()


def stroke(mask, a, width_m):
    cv2.polylines(mask, [np.round(a).astype(np.int32)], False, 255, max(1, int(round(width_m * ppm * SS))), cv2.LINE_8)


# ---- road classes: carriageway width (m), surface colour --------------------------------------------------------
ASPHALT, PAVING = np.array([132, 131, 134.]), np.array([196, 186, 166.])
WIDTH = {"motorway": 7.5, "trunk": 7.5, "primary": 7.5, "secondary": 7.0, "tertiary": 6.5, "unclassified": 5.0,
         "residential": 5.5, "living_street": 4.5, "service": 3.5, "pedestrian": 5.0, "motorway_link": 5.0,
         "trunk_link": 5.0, "primary_link": 5.0, "secondary_link": 5.0, "tertiary_link": 5.0}
CENTRE_LINE = {"motorway", "trunk", "primary", "secondary", "tertiary"}

road = {False: np.zeros((H2, W2), np.uint8), True: np.zeros((H2, W2), np.uint8)}   # by on-bridge
edge = {False: np.zeros((H2, W2), np.uint8), True: np.zeros((H2, W2), np.uint8)}
pave = np.zeros((H2, W2), np.uint8)
dash = np.zeros((H2, W2), np.uint8)
for r in L["roads"]:
    w = WIDTH.get(r["k"])
    if not w or r.get("t"):
        continue
    a = pts(r["p"])
    if not onscreen(a):
        continue
    if r.get("l"):
        try:
            w = max(w, float(str(r["l"]).split(";")[0]) * 3.2)
        except ValueError:
            pass
    b = bool(r.get("b"))
    stroke(edge[b], a, w + 0.6)
    stroke(road[b], a, w)
    if r["k"] == "pedestrian":
        stroke(pave, a, w)
    if r["k"] in CENTRE_LINE and not r.get("o"):
        # dashes: 3 m on, 6 m off
        seg = np.hypot(*np.diff(a, axis=0).T)
        cum = np.r_[0, np.cumsum(seg)]
        on, off = 3 * ppm * SS, 6 * ppm * SS
        s = 0.0
        while s < cum[-1]:
            e = min(s + on, cum[-1])
            q = np.array([np.interp(t, cum, a[:, 0]) for t in (s, e)]), np.array([np.interp(t, cum, a[:, 1]) for t in (s, e)])
            cv2.line(dash, (int(q[0][0]), int(q[1][0])), (int(q[0][1]), int(q[1][1])), 255, max(1, int(0.15 * ppm * SS)))
            s += on + off

rail_bed = np.zeros((H2, W2), np.uint8); rail_edge = np.zeros((H2, W2), np.uint8)
rails = np.zeros((H2, W2), np.uint8); sleepers = np.zeros((H2, W2), np.uint8)
for r in L["rail"]:
    if r.get("t") or r["k"] not in ("rail", "tram", "light_rail"):
        continue
    a = pts(r["p"])
    if not onscreen(a):
        continue
    if r["k"] == "rail":
        stroke(rail_edge, a, 3.8); stroke(rail_bed, a, 3.2)
        # sleepers every 1.3 m (drawn), 2.4 m long
        seg = np.hypot(*np.diff(a, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
        for s in np.arange(0, cum[-1], 1.3 * ppm * SS):
            i = min(np.searchsorted(cum, s), len(a) - 1); i = max(i, 1)
            d = (a[i] - a[i - 1]) / max(seg[i - 1], 1e-3)
            p = a[i - 1] + d * (s - cum[i - 1])
            n = np.array([-d[1], d[0]]) * 1.2 * ppm * SS
            cv2.line(sleepers, tuple(np.round(p - n).astype(int)), tuple(np.round(p + n).astype(int)), 255, 1)
    # two rails at +-0.72 m
    seg = np.hypot(*np.diff(a, axis=0).T) + 1e-3
    d = np.diff(a, axis=0) / seg[:, None]
    nrm = np.r_[d[:1], (d[1:] + d[:-1]) / 2, d[-1:]]
    nrm = np.stack([-nrm[:, 1], nrm[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-6
    for s in (-1, 1):
        cv2.polylines(rails, [np.round(a + nrm * s * 0.72 * ppm * SS).astype(np.int32)], False, 255, max(1, int(0.12 * ppm * SS)))

water = np.zeros((H2, W2), np.uint8)
for w in L["water"]:
    a = pts(w["p"])
    if len(a) > 2 and onscreen(a, 2000):
        cv2.fillPoly(water, [np.round(a).astype(np.int32)], 255)
for w in L["waterways"]:
    if w.get("t"):
        continue
    a = pts(w["p"])
    if onscreen(a, 2000):
        stroke(water, a, 10 if w["k"] == "river" else 3)


def down(m):
    return cv2.resize(m.astype(np.float32) / 255, (cw, ch), interpolation=cv2.INTER_AREA)


# ---- occlusion -----------------------------------------------------------------------------------------------
hsv = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(int)
foliage = (hsv[..., 0] * 2 >= 55) & (hsv[..., 0] * 2 <= 170) & (hsv[..., 1] >= 55) & (hsv[..., 2] >= 25)
foliage = cv2.morphologyEx(foliage.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0
gvis = (ground & ~foliage).astype(np.float32)
gvis = cv2.GaussianBlur(gvis, (3, 3), 0)
dvis = cv2.GaussianBlur((deck & ~foliage).astype(np.float32), (3, 3), 0)

# ---- light from the painting: shadows survive ------------------------------------------------------------------
lum = img @ np.array([0.3, 0.55, 0.15], np.float32)
light = cv2.medianBlur(np.clip(lum, 0, 255).astype(np.uint8), 15).astype(np.float32)
road_ref = np.percentile(light[(down(road[False]) > 0.5) & ground], 70) if (down(road[False]) > 0.5).any() else 140
shade = np.clip(light / max(road_ref, 1), 0.35, 1.1)[..., None]

out = img.copy()
INK = np.array([52, 48, 56.])


def lay(mask, colour, vis, use_shade=True, alpha=1.0):
    global out
    m = (down(mask) * vis * alpha)[..., None]
    c = colour * (shade if use_shade else 1)
    out = out * (1 - m) + c * m


# water first, then roads/tracks on top (bridges cross water)
wm = down(water)
water_col = np.median(img[(wm > 0.9) & ground], axis=0) if ((wm > 0.9) & ground).sum() > 200 else np.array([57, 88, 102.])
bank = (cv2.dilate(water, np.ones((5, 5), np.uint8)) > 0) & ~(water > 0)
lay(bank.astype(np.uint8) * 255, INK, gvis, alpha=0.8)
lay(water, water_col, gvis)
for b, vis in ((False, gvis), (True, np.maximum(dvis, gvis))):
    lay(edge[b], INK, vis, alpha=0.9)
    lay(road[b], ASPHALT, vis)
lay(pave, PAVING, gvis)
lay(dash, np.array([236, 232, 220.]), np.maximum(gvis, dvis), alpha=0.85)
lay(rail_edge, INK, gvis, alpha=0.9)
lay(rail_bed, np.array([128, 116, 104.]), gvis)
lay(sleepers, np.array([78, 64, 52.]), gvis, alpha=0.8)
lay(rails, np.array([62, 64, 70.]), np.maximum(gvis, dvis))

Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(out_path, quality=92)
print("saved", out_path)
