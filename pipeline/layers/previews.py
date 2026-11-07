"""Preview images of the layers for the local progress page (web/public/poc/img).

  previews.py layers <dir> <k> <prefix>          each layer alone (on a light checkerboard) and the stack
  previews.py pair <k> <a.png> <b.png> <out> [x y w] [labels]  two images side by side (crop in full-res block px);
                                                  a or b may be "today"
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

from layers_common import POC_IMG, block, preview, today

SPOTS = {  # full-res block px (x, y, size): the owner's problem spots and a few typical places
    "grund": (2600, 2400, 1400),
    "bock": (3700, 2300, 900),
    "pfaffenthal": (3500, 700, 1300),
    "redbridge": (3600, 500, 1000),
    "petrusse": (900, 2300, 1300),
}


def checker(size, n=16):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    c = (((yy // n) + (xx // n)) % 2).astype(np.uint8)
    a = np.where(c[..., None] > 0, (236, 236, 236), (250, 250, 250)).astype(np.uint8)
    return Image.fromarray(a).convert("RGBA")


def flat(path, bg=True):
    im = Image.open(path).convert("RGBA")
    if bg:
        base = checker(im.size)
        base.alpha_composite(im)
        return base.convert("RGB")
    return im.convert("RGB")


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 8 + 7 * len(text), 22), fill=(255, 255, 255))
    d.text((5, 5), text, fill=(20, 20, 20))
    return im


def pair(k, a, b, out, crop=None, labels=("Today", "Layers")):
    blk = block("b00")
    ims = [today(blk, k) if p == "today" else flat(p) for p in (a, b)]
    if crop:
        x, y, w = crop
        box = (int(x * k), int(y * k), int((x + w) * k), int((y + w) * k))
        ims = [im.crop(box) for im in ims]
    s = 790 / ims[0].width
    ims = [label(im.resize((790, round(im.height * s)), Image.LANCZOS), t) for im, t in zip(ims, labels)]
    sheet = Image.new("RGB", (1600, ims[0].height), (255, 255, 255))
    sheet.paste(ims[0], (0, 0)); sheet.paste(ims[1], (810, 0))
    preview(sheet, POC_IMG / out)


def layers(d, k, prefix):
    from pathlib import Path
    d = Path(d)
    names = [("L1_ground", "L1 ground"), ("L2_relief", "L2 slopes and cliffs"), ("L2_walls", "L2 walls"),
             ("L3_water", "L3 water"), ("L4_roads", "L4 roads, paths, rails")]
    tiles = [label(flat(d / f"{n}.png").resize((790, 790), Image.LANCZOS), t) for n, t in names if (d / f"{n}.png").exists()]
    rows = (len(tiles) + 1) // 2
    sheet = Image.new("RGB", (1600, rows * 800), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * 810, (i // 2) * 800))
    preview(sheet, POC_IMG / f"{prefix}_layers.jpg")


if __name__ == "__main__":
    if sys.argv[1] == "layers":
        layers(sys.argv[2], float(sys.argv[3]), sys.argv[4])
    else:
        k = float(sys.argv[2]); a, b, out = sys.argv[3:6]
        crop = SPOTS.get(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] in SPOTS else (
            tuple(int(v) for v in sys.argv[6:9]) if len(sys.argv) > 8 else None)
        labs = tuple(sys.argv[-1].split("|")) if "|" in sys.argv[-1] else ("Today", "Layers")
        pair(k, a, b, out, crop, labs)
