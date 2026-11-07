"""Layout map: a colour-coded second input for the painter, built from data, aligned pixel-for-pixel with the render.

Colours (only where that surface is really visible, from the render's visibility pass):
  empty map edge  (16, 24, 40)        ground (other)   (226, 218, 198)
  green areas     (110, 170, 90)      water            (60, 120, 210)
  roads           (150, 150, 155) + white centre/lane dashes; pedestrian streets (205, 190, 160)
  car parks       (185, 185, 190)     rail             (150, 110, 70) bed, dark rails
  tram tracks     thin dark double line on whatever is under them
  bridge decks    (120, 120, 132)     walls (232, 196, 140), roofs (96, 108, 150), with the line guide drawn in
                                      (edges black, windows dark)
Usage: layout.py <x0> <y0> <w> <h> <out.png>   (mosaic px; render frames, frames_kind, frames_line must exist)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw
from common import ROOT, RAW, WORK

x0, y0, W, H, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
m = json.loads((WORK / "mosaic.json").read_text())
F = m["frame"]


def cut(folder, ext, mode, fill):
    im = Image.new(mode, (W, H), fill)
    for r in range(max(y0, 0) // F, (y0 + H) // F + 1):
        for c in range(max(x0, 0) // F, (x0 + W) // F + 1):
            p = WORK / folder / f"{c}_{r}.{ext}"
            if p.exists():
                im.paste(Image.open(p).convert(mode), (c * F - x0, r * F - y0))
    return np.asarray(im)


kind = cut("frames_kind", "png", "L", 0)
line = cut("frames_line", "png", "L", 255)
ground, deck = kind > 200, (kind > 100) & (kind <= 200)
wall, roof = (kind > 32) & (kind <= 100), kind <= 32
# Empty map edge and anything off the map: the visibility pass draws them dark like roofs, so take them from the
# colour render instead (background colour there).
rgb = cut("frames", "jpg", "RGB", (16, 24, 40)).astype(np.int16)
empty = np.abs(rgb - np.array((16, 24, 40))).sum(axis=2) < 20
roof &= ~empty
L = json.loads((ROOT / "web/public/data/lines.json").read_text())
ppm = 4  # mosaic px per metre


def P(p):
    return [(p[i] - x0, p[i + 1] - y0) for i in range(0, len(p), 2)]


def layer(draw_fn):
    im = Image.new("L", (W, H), 0)
    draw_fn(ImageDraw.Draw(im))
    return np.asarray(im) > 0


img = np.zeros((H, W, 3), np.uint8)
img[:] = (16, 24, 40)
img[ground] = (226, 218, 198)

# green areas
green_els = json.loads((RAW / "osm" / "green.json").read_text())["elements"] if (RAW / "osm" / "green.json").exists() else []
from common import lonlat_to_en, ORIGIN_E, ORIGIN_N, R, ELEV  # noqa: E402
import math  # noqa: E402
t = np.load(WORK / "terrain.npz")
tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])


def to_px(lon, lat):
    e, n = lonlat_to_en(lon, lat)
    iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1); ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
    z = float(tz[iy, ix]); le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R; sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return (sx - m["sx0"]) / m["mpp"] - x0, (m["sy1"] - sy) / m["mpp"] - y0


def greens(d):
    for el in green_els:
        geoms = [el["geometry"]] if "geometry" in el else [mm["geometry"] for mm in el.get("members", []) if mm.get("role") == "outer" and "geometry" in mm]
        for g in geoms:
            if len(g) > 2:
                q = [to_px(p["lon"], p["lat"]) for p in g]
                if any(-500 < x < W + 500 and -500 < y < H + 500 for x, y in q):
                    d.polygon(q, fill=255)


img[layer(greens) & ground] = (110, 170, 90)

# car parks and squares
img[layer(lambda d: [d.polygon(P(p["p"]), fill=255) for p in L.get("parking", []) if len(p["p"]) > 4]) & ground] = (185, 185, 190)

# water
def water(d):
    for w in L["water"]:
        if len(w["p"]) > 4:
            d.polygon(P(w["p"]), fill=255)
    for w in L["waterways"]:
        if not w.get("t"):
            d.line(P(w["p"]), fill=255, width=(10 if w["k"] == "river" else 3) * ppm, joint="curve")
img[layer(water) & ground] = (60, 120, 210)

# roads (ground and on bridges)
WIDTH = {"motorway": 7.5, "trunk": 7.5, "primary": 7.5, "secondary": 7.0, "tertiary": 6.5, "unclassified": 5.0,
         "residential": 5.5, "living_street": 4.5, "service": 3.5, "pedestrian": 5.0, "motorway_link": 5.0,
         "trunk_link": 5.0, "primary_link": 5.0, "secondary_link": 5.0, "tertiary_link": 5.0}
for on_bridge, vis in ((False, ground), (True, deck | ground)):
    def roads(d, ped=False):
        for r in L["roads"]:
            w = WIDTH.get(r["k"])
            if w and not r.get("t") and bool(r.get("b")) == on_bridge and (r["k"] == "pedestrian") == ped:
                d.line(P(r["p"]), fill=255, width=int(w * ppm), joint="curve")
    img[layer(roads) & vis] = (150, 150, 155)
    img[layer(lambda d: roads(d, True)) & vis] = (205, 190, 160)
    def dashes(d):
        for r in L["roads"]:
            if r["k"] in ("motorway", "trunk", "primary", "secondary", "tertiary") and not r.get("t") and not r.get("o") and bool(r.get("b")) == on_bridge:
                q = np.array(P(r["p"]), float)
                seg = np.hypot(*np.diff(q, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
                for s in np.arange(0, cum[-1], 9 * ppm):
                    a = [np.interp(s, cum, q[:, i]) for i in (0, 1)]; b = [np.interp(min(s + 3 * ppm, cum[-1]), cum, q[:, i]) for i in (0, 1)]
                    d.line([tuple(a), tuple(b)], fill=255, width=2)
    img[layer(dashes) & vis] = (250, 250, 250)

# bridges decks (where no road was drawn on them)
dk = deck & (img.sum(axis=2) == (16 + 24 + 40))
img[deck & ~((img == (150, 150, 155)).all(axis=2) | (img == (250, 250, 250)).all(axis=2))] = (120, 120, 132)

# rail and tram
for r in L["rail"]:
    if r.get("t"):
        continue
    q = np.array(P(r["p"]), float)
    if len(q) < 2:
        continue
    dd = np.diff(q, axis=0); dd /= (np.linalg.norm(dd, axis=1, keepdims=True) + 1e-6)
    nn = np.r_[dd[:1], (dd[1:] + dd[:-1]) / 2, dd[-1:]]; nn = np.stack([-nn[:, 1], nn[:, 0]], 1)
    nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-6
    vis = (ground | deck) if r.get("b") else ground
    if r["k"] == "rail":
        img[layer(lambda d: d.line([tuple(p) for p in q], fill=255, width=int(3.2 * ppm), joint="curve")) & vis] = (150, 110, 70)
    rails = layer(lambda d: [d.line([tuple(p) for p in q + nn * s * 0.72 * ppm], fill=255, width=2) for s in (-1, 1)])
    img[rails & vis] = (40, 36, 34)

# buildings: two tones, then the line guide
img[wall] = (232, 196, 140)
img[roof] = (96, 108, 150)
bld = wall | roof
img[bld & (line < 160) & (line > 60)] = (70, 60, 50)      # windows
img[(line < 60) & (bld | deck)] = (20, 18, 16)            # edges
img[empty] = (16, 24, 40)
Image.fromarray(img).save(out)
print(out, img.shape)
