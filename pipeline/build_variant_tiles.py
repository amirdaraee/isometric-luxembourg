"""Tile pyramids for the painted versions (night, winter, ...): the painted showcase inside, the 3D render outside
graded to match (so switching to night darkens the whole map, not only the painted part).
Usage: build_variant_tiles.py <variant> <painted.png> <x0> <y0> <w>   (w = mosaic px covered, square)
       build_variant_tiles.py <variant> <patches.json>     (whole city: [{"file", "x0", "y0", "w", "h"}, ...])
Outside the painted version, the graded base is the painted DAY map (data/work/tiles/painted.json laid over the
render), so a block painted by day but not yet in this version still looks like the same drawing.
Writes web/public/tiles/map_<variant>_files and adds the variant to tiles/meta.json."""
import json
import shutil
import sys
import pyvips
from common import ROOT, WORK, TILE

variant = sys.argv[1]
if sys.argv[2].endswith(".json"):
    patches = json.loads(open(sys.argv[2]).read())
else:
    w = int(sys.argv[5])
    patches = [{"file": sys.argv[2], "x0": int(sys.argv[3]), "y0": int(sys.argv[4]), "w": w, "h": w}]
OUT = ROOT / "web" / "public" / "tiles"
m = json.loads((WORK / "mosaic.json").read_text())
frames = [pyvips.Image.new_from_file(str(WORK / "frames" / f"{c}_{r}.jpg"), access="sequential")
          for r in range(m["rows"]) for c in range(m["cols"])]
mosaic = pyvips.Image.arrayjoin(frames, across=m["cols"])
# the painted day map underneath (as in build_tiles.py), so grading starts from the drawing, not the photo-render
pj = WORK / "tiles" / "painted.json"
for d in (json.loads(pj.read_text()) if pj.exists() else []):
    im = pyvips.Image.new_from_file(str(WORK / "tiles" / d["file"]))[:3]
    im = im.resize(d["w"] / im.width, vscale=d["h"] / im.height, kernel="lanczos3")
    mosaic = mosaic.insert(im.cast(mosaic.format), d["x0"], d["y0"])
mosaic = mosaic.cast("float")


def bj(b):
    return b[0].bandjoin(b[1:])


def lum(im):
    return im[0] * 0.3 + im[1] * 0.55 + im[2] * 0.15


def snow(im, k=0.55):
    l = lum(im)
    return (im * (1 - k) + (l * 0.35 + 165) * k)


GRADE = {
    "night": lambda im: bj([lum(im) * 0.16 + 4, lum(im) * 0.2 + 8, lum(im) * 0.34 + 18]),
    "winter": lambda im: snow(im),
    "winter_night": lambda im: (lambda s: bj([lum(s) * 0.2 + 6, lum(s) * 0.25 + 10, lum(s) * 0.42 + 22]))(snow(im)),
    "golden": lambda im: bj([im[0] * 1.12 + 10, im[1] * 0.98 + 2, im[2] * 0.72]),
    "autumn": lambda im: bj([im[0] * 1.08 + 6, im[1] * 0.98, im[2] * 0.85]),
    "spring": lambda im: bj([im[0] * 1.0, im[1] * 1.06 + 4, im[2] * 0.98]),
}
graded = GRADE[variant](mosaic).cast("uchar")
# keep the empty map edge dark for every version
bg = (mosaic[0] - 16).abs() + (mosaic[1] - 24).abs() + (mosaic[2] - 40).abs() < 20
graded = bg.ifthenelse([16, 24, 40] if "night" not in variant else [6, 9, 18], graded)
FEATHER = 600  # map px: painted blocks fade into the graded map (or a painted neighbour) instead of a hard edge


def ramp(w, h, f):
    """Alpha 0..1 rising linearly over f px from every border of a w x h image."""
    xy = pyvips.Image.xyz(w, h)
    x, y = xy[0], xy[1]
    dx = (x < (w - 1 - x)).ifthenelse(x, w - 1 - x)      # distance to the nearer side
    dy = (y < (h - 1 - y)).ifthenelse(y, h - 1 - y)      # distance to the nearer top or bottom
    d = (dx < dy).ifthenelse(dx, dy).cast("float") / f
    return (d > 1).ifthenelse(1, d)


W_, H_ = graded.width, graded.height
for q in patches:
    p = pyvips.Image.new_from_file(str(q["file"]))[:3]
    p = p.resize(q["w"] / p.width, vscale=q.get("h", q["w"]) / p.height, kernel="lanczos3").cast("float")
    x0, y0 = q["x0"], q["y0"]
    # clip to the map (edge blocks start off the map)
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x0 + p.width, W_), min(y0 + p.height, H_)
    if cx1 <= cx0 or cy1 <= cy0:
        continue
    a = ramp(p.width, p.height, FEATHER).crop(cx0 - x0, cy0 - y0, cx1 - cx0, cy1 - cy0)
    pc = p.crop(cx0 - x0, cy0 - y0, cx1 - cx0, cy1 - cy0)
    under = graded.crop(cx0, cy0, cx1 - cx0, cy1 - cy0).cast("float")
    mixed = (pc * a + under * (1 - a)).cast("uchar")
    graded = graded.insert(mixed, cx0, cy0)
dest = OUT / f"map_{variant}"
shutil.rmtree(str(dest) + "_files", ignore_errors=True)
graded.dzsave(str(dest), tile_size=TILE, overlap=0, suffix=".webp[Q=82,effort=4]", layout="dz")
for d in (OUT / f"map_{variant}_files").iterdir():
    if d.is_dir() and int(d.name) < 9:
        shutil.rmtree(d)
(OUT / f"map_{variant}.dzi").unlink(missing_ok=True)
meta = json.loads((OUT / "meta.json").read_text())
meta.setdefault("variants", {})[variant] = f"map_{variant}_files"
(OUT / "meta.json").write_text(json.dumps(meta))
print("variant", variant, "done")
