"""Guide the painter with the real map: draw OSM water into the render as flat water, remove fake water
(dark shadows the model painted as water where OSM has none) by inpainting it from the surrounding ground, and
empty roads and parking lots (cars come later as a layer) by median-filtering their surface.
Usage: make_hint.py <src.png> <x0> <y0> <invented.npy> <painted_w> <out.png> [kind.png]
kind.png (from render.py --kinds) marks where the ground is really visible; map data is only applied there, so a
road or river behind a building or under a bridge never gets drawn over it."""
import json
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw
from common import ROOT

src, x0, y0, inv_path, pw, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], int(sys.argv[5]), sys.argv[6]
im = Image.open(src).convert("RGB")
W, H = im.size
ground_vis = (np.asarray(Image.open(sys.argv[7]).convert("L")) > 200) if len(sys.argv) > 7 else np.ones((H, W), bool)
L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
WATER = (58, 88, 100)  # the painted Alzette's colour where the model got it right
px_per_m = 4  # render is 0.25 m/px

# 1. Remove fake water: invented mask is in painted pixels; bring it to render pixels and inpaint.
ph = round(H * pw / W)
inv = (np.unpackbits(np.load(inv_path))[: pw * ph].reshape(ph, pw).astype(np.uint8) * 255 if inv_path != "-"
       else np.zeros((ph, pw), np.uint8))  # "-": no painted version yet, nothing to remove
inv = cv2.resize(inv, (W, H), interpolation=cv2.INTER_NEAREST)
inv = cv2.dilate(inv, np.ones((15, 15), np.uint8))
arr = cv2.inpaint(np.asarray(im), inv, 9, cv2.INPAINT_TELEA)
im = Image.fromarray(arr)

# 2. Empty the roads and parking lots: a median filter wider than a car removes cars, keeps the asphalt tone.
LANES_M = {"motorway": 14, "trunk": 12, "primary": 10, "secondary": 9, "tertiary": 8, "residential": 6.5,
           "unclassified": 6, "living_street": 5, "service": 4.5, "motorway_link": 6, "trunk_link": 6,
           "primary_link": 6, "secondary_link": 6, "tertiary_link": 6}
emp = Image.new("L", (W, H), 0)
de = ImageDraw.Draw(emp)
for r in L["roads"]:
    w = LANES_M.get(r["k"])
    if not w or r.get("t"):
        continue
    q = [(r["p"][i] - x0, r["p"][i + 1] - y0) for i in range(0, len(r["p"]), 2)]
    de.line(q, fill=255, width=int(w * px_per_m), joint="curve")
pkm = Image.new("L", (W, H), 0)
dp = ImageDraw.Draw(pkm)
for pk in L.get("parking", []):
    q = [(pk["p"][i] - x0, pk["p"][i + 1] - y0) for i in range(0, len(pk["p"]), 2)]
    if len(q) > 2:
        de.polygon(q, fill=255)
        dp.polygon(q, fill=255)
pkm = np.asarray(pkm) > 0
a0 = np.asarray(im).astype(int)
veg = (a0[..., 1] > a0[..., 0] + 6) & (a0[..., 1] >= a0[..., 2])  # leaves over a road stay leaves
veg = cv2.dilate(veg.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
emp = (np.asarray(emp) > 0) & ground_vis & ~veg
arr = np.asarray(im).copy()
med = cv2.medianBlur(arr, 31)  # the asphalt without anything car-sized on it
# Only remove car-shaped blobs: compact patches that stand out from the asphalt around them. Lane markings,
# crossings and kerbs are long and thin (or large and regular), so they stay and the painter keeps them.
diff = np.abs(arr.astype(int) - med.astype(int)).sum(axis=2)
cand = ((diff > 60) & emp).astype(np.uint8)
cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(cand)
cars = np.zeros(cand.shape, bool)
area_px = st[:, cv2.CC_STAT_AREA]; w_ = st[:, cv2.CC_STAT_WIDTH]; h_ = st[:, cv2.CC_STAT_HEIGHT]
fill = area_px / np.maximum(w_ * h_, 1)
aspect = np.maximum(w_, h_) / np.maximum(np.minimum(w_, h_), 1)
in_pk = np.bincount(lab.ravel(), weights=pkm.ravel().astype(float), minlength=n) / np.maximum(area_px, 1) > 0.5
one_car = (area_px >= 25) & (area_px <= 700) & (np.maximum(w_, h_) <= 48) & (aspect <= 3.5) & (fill >= 0.35)
# In car parks, a row of parked cars merges into one long solid blob; bay lines are thin (low fill) and stay.
car_row = in_pk & (area_px >= 25) & (area_px <= 6000) & (np.minimum(w_, h_) <= 40) & (fill >= 0.3)
keep = one_car | car_row
keep[0] = False
cars = keep[lab]
cars = cv2.dilate(cars.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
cars &= emp
arr[cars] = med[cars]
im = Image.fromarray(arr)
print("car blobs removed:", int(keep.sum()), "px:", int(cars.sum()))
print("road and parking px emptied:", int(emp.sum()))

# 2b. Railway tracks drawn cleanly (gravel bed, sleepers, two rails), only where the ground is visible.
trk = np.asarray(im).copy()
bed = Image.new("L", (W, H), 0); slp = Image.new("L", (W, H), 0); rl = Image.new("L", (W, H), 0)
db, ds, dr = ImageDraw.Draw(bed), ImageDraw.Draw(slp), ImageDraw.Draw(rl)
for r in L["rail"]:
    if r.get("t") or r["k"] != "rail":
        continue
    q = np.array([(r["p"][i] - x0, r["p"][i + 1] - y0) for i in range(0, len(r["p"]), 2)], float)
    if len(q) < 2:
        continue
    db.line([tuple(p) for p in q], fill=255, width=int(3.2 * px_per_m), joint="curve")
    seg = np.hypot(*np.diff(q, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
    for s_ in np.arange(0, cum[-1], 0.65 * px_per_m):
        i = max(min(np.searchsorted(cum, s_), len(q) - 1), 1)
        dvec = (q[i] - q[i - 1]) / max(seg[i - 1], 1e-3); pt = q[i - 1] + dvec * (s_ - cum[i - 1])
        nv = np.array([-dvec[1], dvec[0]]) * 1.25 * px_per_m
        ds.line([tuple(pt - nv), tuple(pt + nv)], fill=255, width=2)
    dd = np.diff(q, axis=0); dd /= (np.linalg.norm(dd, axis=1, keepdims=True) + 1e-6)
    nn = np.r_[dd[:1], (dd[1:] + dd[:-1]) / 2, dd[-1:]]; nn = np.stack([-nn[:, 1], nn[:, 0]], 1)
    nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-6
    for sg in (-1, 1):
        dr.line([tuple(p) for p in q + nn * sg * 0.72 * px_per_m], fill=255, width=2)
for mk, col in ((bed, (138, 126, 112)), (slp, (92, 76, 62)), (rl, (70, 72, 78))):
    m = (np.asarray(mk) > 0) & ground_vis
    trk[m] = col
im = Image.fromarray(trk)

# 3. Draw the real water, only where the ground is visible.
wl = Image.new("L", (W, H), 0)
d = ImageDraw.Draw(wl)
for w in L["water"]:
    q = [(w["p"][i] - x0, w["p"][i + 1] - y0) for i in range(0, len(w["p"]), 2)]
    if len(q) > 2:
        d.polygon(q, fill=255)
for w in L["waterways"]:
    if w.get("t"):
        continue
    q = [(w["p"][i] - x0, w["p"][i + 1] - y0) for i in range(0, len(w["p"]), 2)]
    d.line(q, fill=255, width=(10 if w["k"] == "river" else 3) * px_per_m, joint="curve")
wm = (np.asarray(wl) > 0) & ground_vis
arr = np.asarray(im).copy()
arr[wm] = WATER
im = Image.fromarray(arr)
im.save(out)
print(out, "fake-water px removed:", int((inv > 0).sum()))
