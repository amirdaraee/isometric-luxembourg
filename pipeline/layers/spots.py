"""Layered map, step 7: the owner's problem spots, today vs layers, with the lines vehicles and trains follow
(web/public/data/lines.json) drawn on top, so it is clear whether they sit on the painted road or track.

  spots.py [b00]   -> web/public/poc/img/s7_<spot>.jpg
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from layers_common import POC_IMG, ROOT, WORK, block, out_dir, preview
from previews import SPOTS, label

DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
         "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}


def lines_on(im, b, k, box, L):
    x0, y0, w = box
    s = 790 / (w * k)
    d = ImageDraw.Draw(im, "RGBA")

    def P(p):
        a = np.array(p, float).reshape(-1, 2)
        return [tuple(v) for v in ((a - (b["x0"] + x0, b["y0"] + y0)) * k * s)]
    for r in L["roads"]:
        if r["k"] in DRIVE and not r.get("t") and r.get("a", 1) & 1:
            d.line(P(r["p"]), fill=(255, 40, 40, 200), width=2)
    for r in L["rail"]:
        if not r.get("t"):
            d.line(P(r["p"]), fill=(40, 120, 255, 220), width=2)


def main():
    bid = sys.argv[1] if len(sys.argv) > 1 else "b00"
    b = block(bid)
    k = 5120 / 6000
    d = out_dir(bid)
    L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
    pics = {
        "today": Image.open(WORK / "city" / bid / "canvas_day_s8.png").convert("RGB"),
        "layers": Image.open(d / "composite_midday_summer.png").convert("RGB"),
    }
    for spot in ("hollowtooth", "pfaffenthal", "redbridge", "grund"):
        x0, y0, w = SPOTS[spot]
        box = (int(x0 * k), int(y0 * k), int((x0 + w) * k), int((y0 + w) * k))
        tiles = []
        for name, im in pics.items():
            c = im.crop(box).resize((790, 790), Image.LANCZOS)
            lines_on(c, b, k, (x0, y0, w), L)
            tiles.append(label(c, f"{'Today' if name == 'today' else 'Layers'}: red = car lanes, blue = rail and tram lines"))
        sheet = Image.new("RGB", (1600, 790), "white")
        sheet.paste(tiles[0], (0, 0)); sheet.paste(tiles[1], (810, 0))
        preview(sheet, POC_IMG / f"s7_{spot}.jpg")
    # spring: today's painted spring version vs the layers' spring tree swap
    sp = Image.open(WORK / "city" / bid / "canvas_spring_s15.png").convert("RGB")
    ls = Image.open(d / "composite_midday_spring.png").convert("RGB")
    for spot in ("grund", "petrusse"):
        x0, y0, w = SPOTS[spot]
        box = (int(x0 * k), int(y0 * k), int((x0 + w) * k), int((y0 + w) * k))
        a = label(sp.crop(box).resize((790, 790), Image.LANCZOS), "Today's spring version (whole map repainted)")
        c = label(ls.crop(box).resize((790, 790), Image.LANCZOS), "Layers: spring = tree layer swapped")
        sheet = Image.new("RGB", (1600, 790), "white")
        sheet.paste(a, (0, 0)); sheet.paste(c, (810, 0))
        preview(sheet, POC_IMG / f"s7_spring_{spot}.jpg")
    print("spots done")


if __name__ == "__main__":
    main()
