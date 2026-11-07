"""Draw the projected OSM lines over a painted patch to check alignment and spot invented/missing features.
Usage: overlay_check.py <patch.png> <x0> <y0> <src_w> <src_h> <out.jpg>   (x0, y0, src_* in mosaic pixels)"""
import json
import sys
from PIL import Image, ImageDraw
from common import ROOT

patch, x0, y0, sw, sh, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
im = Image.open(patch).convert("RGB")
k = im.width / sw
ov = Image.new("RGBA", im.size)
d = ImageDraw.Draw(ov)


def pts(p):
    return [((p[i] - x0) * k, (p[i + 1] - y0) * k) for i in range(0, len(p), 2)]


for w in L["water"]:
    q = pts(w["p"])
    if len(q) > 2:
        d.polygon(q, fill=(0, 140, 255, 70), outline=(0, 90, 255, 220))
for w in L["waterways"]:
    d.line(pts(w["p"]), fill=(0, 90, 255, 230), width=4)
MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street",
         "service", "pedestrian", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
for r in L["roads"]:
    if r["k"] in MAJOR:
        col = (255, 60, 40, 150) if r["t"] else (255, 220, 0, 230) if r["b"] else (255, 0, 160, 210)
        d.line(pts(r["p"]), fill=col, width=3 if r["k"] in ("service", "pedestrian") else 5)
for r in L["rail"]:
    d.line(pts(r["p"]), fill=(40, 40, 40, 230), width=3)
Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB").save(out, quality=88)
print(out)
