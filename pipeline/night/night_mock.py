"""Night mock-ups from the painted day map plus the 3D/OSM data (no image model).

A "live filter": what the browser could do in real time: grade to a warm-cozy night (deep blue, keep the ink
lines), lit windows on walls, warm street-lamp pools along roads, floodlit landmarks, light streaks on water,
car head/tail lights, valley mist, stars at the map edge.
B "precomputed": A plus what is too heavy for every frame: bloom around every light, light spill onto
nearby walls and ground, softer mist.

Usage: night_mock.py <painted.png> <kind.png> <x0> <y0> <src_w> <crop x0,y0,size in src px> <out prefix>
"""
import json
import math
import sys
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from common import ROOT

painted, kindp = sys.argv[1], sys.argv[2]
X0, Y0, SW = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
cx0, cy0, cs = map(int, sys.argv[6].split(","))
pref = sys.argv[7]
rng = np.random.default_rng(7)

day = Image.open(painted).convert("RGB")
k = day.width / SW
box = tuple(int(round(v * k)) for v in (cx0, cy0, cx0 + cs, cy0 + cs))
day = np.asarray(day.crop(box).resize((1024, 1024), Image.LANCZOS)).astype(np.float32) / 255
kind = np.asarray(Image.open(kindp).convert("L").crop((cx0, cy0, cx0 + cs, cy0 + cs)).resize((1024, 1024), Image.NEAREST))
S = 1024 / cs  # output px per src (mosaic) px
mpp = 0.25 / S  # metres per output px
ground, bridge, wall, roof = kind > 200, (kind > 100) & (kind <= 200), (kind > 32) & (kind <= 100), kind <= 32
L = json.loads((ROOT / "web/public/data/lines.json").read_text())


def pts(p):
    return np.array([((p[i] - X0 - cx0) * S, (p[i + 1] - Y0 - cy0) * S) for i in range(0, len(p), 2)], np.float32)


# ---- base grade: warm cozy night ----------------------------------------------------------------------------
lum = day @ np.array([0.3, 0.55, 0.15], np.float32)
night = np.empty_like(day)
tint = np.array([0.20, 0.27, 0.50], np.float32)  # moonlit blue
night[:] = (lum[..., None] ** 1.15) * tint + day * 0.06
# keep the ink: darken outlines a touch more so the drawing still reads
edges = cv2.Canny((lum * 255).astype(np.uint8), 60, 140) > 0
night[edges] *= 0.6
# water: deeper, a bit of moon sheen
water = np.zeros((1024, 1024), np.uint8)
for w in L["water"]:
    q = pts(w["p"])
    if len(q) > 2:
        cv2.fillPoly(water, [q.astype(np.int32)], 255)
for w in L["waterways"]:
    if not w.get("t"):
        cv2.polylines(water, [pts(w["p"]).astype(np.int32)], False, 255, max(2, int(10 / mpp)))
water = (water > 0) & ground
night[water] = night[water] * 0.8 + np.array([0.02, 0.05, 0.12])

light = np.zeros((1024, 1024, 3), np.float32)  # additive light, linear-ish
WARM, LAMP, WHITE, RED = (np.array(c, np.float32) for c in ((1.0, 0.72, 0.35), (1.0, 0.62, 0.25), (0.95, 0.95, 1.0), (1.0, 0.1, 0.05)))

# ---- lit windows on walls ------------------------------------------------------------------------------------
# A grid of window cells over wall pixels; ~30% lit, in warm yellows; skip the darkest (shadowed) wall noise.
wy, wx = np.nonzero(wall)
cell = max(3, int(round(2.6 / mpp)))  # a window every ~2.6 m
gx, gy = wx // cell, wy // cell
keys = np.unique(gx * 100000 + gy)
lit = set(keys[rng.random(len(keys)) < 0.32].tolist())
win = np.zeros((1024, 1024), np.float32)
ww, wh = max(1, int(cell * 0.45)), max(1, int(cell * 0.6))
sel = np.fromiter(((a * 100000 + b) in lit for a, b in zip(gx, gy)), bool, len(gx))
inx, iny = (wx % cell) < ww, (wy % cell) < wh
win[wy[sel & inx & iny], wx[sel & inx & iny]] = 1.0
hue = rng.uniform(0.85, 1.15, (1024 // cell + 2, 1024 // cell + 2)).astype(np.float32)
win *= hue[np.clip(np.arange(1024)[:, None] // cell, 0, hue.shape[0] - 1), np.clip(np.arange(1024)[None] // cell, 0, hue.shape[1] - 1)]
light += win[..., None] * WARM * 1.1

# ---- street lamps along roads --------------------------------------------------------------------------------
lamps = np.zeros((1024, 1024), np.float32)
LIT_ROADS = {"primary", "secondary", "tertiary", "residential", "unclassified", "living_street", "pedestrian",
             "trunk", "service", "primary_link", "secondary_link", "tertiary_link"}
step = 28 / mpp
for r in L["roads"]:
    if r["k"] not in LIT_ROADS or r.get("t"):
        continue
    q = pts(r["p"])
    if not ((q[:, 0] > -50) & (q[:, 0] < 1074) & (q[:, 1] > -50) & (q[:, 1] < 1074)).any():
        continue
    seg = np.hypot(*np.diff(q, axis=0).T)
    cum = np.r_[0, np.cumsum(seg)]
    for s in np.arange(step / 2, cum[-1], step):
        i = min(np.searchsorted(cum, s), len(q) - 1)
        f = (s - cum[i - 1]) / max(seg[i - 1], 1e-3) if i > 0 else 0
        p = q[max(i - 1, 0)] + (q[i] - q[max(i - 1, 0)]) * f
        x, y = int(p[0]), int(p[1])
        if 0 <= x < 1024 and 0 <= y < 1024 and (ground[y, x] or bridge[y, x]):
            lamps[y, x] = 1.0
pool = cv2.GaussianBlur(lamps, (0, 0), 7 / mpp / 4) * (7 / mpp / 4) ** 2 * 2 * math.pi  # ~7 m pools
pool = np.clip(pool, 0, 1.4)
light += (pool * 0.55)[..., None] * LAMP * (ground | bridge)[..., None]
light += cv2.GaussianBlur(lamps, (0, 0), 1.2)[..., None] * 6 * LAMP  # the lamp heads

# ---- floodlit landmarks: Neumünster abbey walls and the viaduct/bridges ---------------------------------------
places = json.loads((ROOT / "web/public/data/places.json").read_text())
flood = np.zeros((1024, 1024), np.float32)
for p in places:
    if not p.get("f"):
        continue
    x, y = (p["x"] - X0 - cx0) * S, (p["y"] - Y0 - cy0) * S
    if -100 < x < 1124 and -100 < y < 1124:
        yy, xx = np.mgrid[0:1024, 0:1024]
        flood += np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * (45 / mpp) ** 2)).astype(np.float32)
flood = np.clip(flood, 0, 1) * (wall | bridge)
light += (flood * 0.5)[..., None] * day * WARM  # floodlight shows the real colours of the stone

# ---- water reflections of nearby lights ----------------------------------------------------------------------
src_l = cv2.GaussianBlur(light.max(axis=2), (0, 0), 2)
streak = cv2.GaussianBlur(np.roll(src_l, int(6 / mpp), axis=0), (3, 31), 0)  # vertical shimmer below lights
light += (streak * 0.9 * water)[..., None] * WARM

# ---- traffic lights: a few cars on the drive network ---------------------------------------------------------
cars = np.zeros((1024, 1024, 3), np.float32)
for r in L["roads"]:
    if r["k"] not in {"primary", "secondary", "tertiary", "trunk"} or r.get("t"):
        continue
    q = pts(r["p"])
    seg = np.hypot(*np.diff(q, axis=0).T)
    for i in range(len(seg)):
        if seg[i] < 1 or rng.random() > 0.35:
            continue
        f = rng.random()
        p = q[i] + (q[i + 1] - q[i]) * f
        d = (q[i + 1] - q[i]) / seg[i]
        for sign, col in ((1, WHITE * 1.6), (-1, RED * 1.4)):
            x, y = (p + d * sign * 2.2 / mpp).astype(int)
            if 0 <= x < 1024 and 0 <= y < 1024 and ground[y, x]:
                cv2.circle(cars, (x, y), 1, col.tolist(), -1)
light += cv2.GaussianBlur(cars, (0, 0), 1.0) * 3

# ---- valley mist and stars -----------------------------------------------------------------------------------
near_w = cv2.GaussianBlur(water.astype(np.float32), (0, 0), 60 / mpp / 6)
mist = np.clip(near_w * 2.2, 0, 1) * 0.16
edge_bg = (np.abs(day - np.array([16, 24, 40]) / 255).sum(axis=2) < 0.1)


def finish(img, light, bloom, pref_name):
    out = img + light
    if bloom:
        bright = np.clip(light - 0.15, 0, None)
        out += cv2.GaussianBlur(bright, (0, 0), 6) * 0.9 + cv2.GaussianBlur(bright, (0, 0), 22) * 0.6
        # spill: lamps light up the walls and ground near them a little
        out += cv2.GaussianBlur(light, (0, 0), 14) * 0.35 * day
    m = cv2.GaussianBlur(mist, (0, 0), 3 if not bloom else 9)[..., None]
    out = out * (1 - m) + m * np.array([0.42, 0.45, 0.6])
    out[edge_bg] = np.array([0.03, 0.04, 0.09])
    stars = (rng.random((1024, 1024)) > 0.9985) & edge_bg
    out[stars] = rng.uniform(0.5, 1.0, (stars.sum(), 1)) * np.array([0.95, 0.95, 1.0])
    out = out / (1 + out * 0.25)  # gentle tone-map so bright lights don't clip harshly
    Image.fromarray((np.clip(out, 0, 1) ** (1 / 1.05) * 255).astype(np.uint8)).save(pref_name, quality=92)


finish(night.copy(), light.copy(), False, pref + "_A_live.jpg")
finish(night.copy(), light.copy(), True, pref + "_B_precomputed.jpg")
Image.fromarray((day * 255).astype(np.uint8)).save(pref + "_day.jpg", quality=92)
print("done", pref)
