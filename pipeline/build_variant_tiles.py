"""Tile pyramids for the painted versions (night, winter, ...): the painted showcase inside, the 3D render outside
graded to match (so switching to night darkens the whole map, not only the painted part).
Usage: build_variant_tiles.py <variant> <painted.png> <x0> <y0> <w>   (w = mosaic px covered, square)
Writes web/public/tiles/map_<variant>_files and adds the variant to tiles/meta.json."""
import json
import shutil
import sys
import pyvips
from common import ROOT, WORK, TILE

variant, painted, X0, Y0, PW = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
OUT = ROOT / "web" / "public" / "tiles"
m = json.loads((WORK / "mosaic.json").read_text())
frames = [pyvips.Image.new_from_file(str(WORK / "frames" / f"{c}_{r}.jpg"), access="sequential")
          for r in range(m["rows"]) for c in range(m["cols"])]
mosaic = pyvips.Image.arrayjoin(frames, across=m["cols"]).cast("float")


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
p = pyvips.Image.new_from_file(painted)[:3]
p = p.resize(PW / p.width, kernel="lanczos3")
graded = graded.insert(p.cast("uchar"), X0, Y0)
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
