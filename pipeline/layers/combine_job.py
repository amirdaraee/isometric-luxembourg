"""Put the buildings-and-bridges render (objects.py prep) and the tree sheet (trees.py sheet) into one canvas, so
one painter job (one model start-up) paints both. The tree sheet goes in a strip below the block.

  combine_job.py join [b00]                -> <block>/job/src.png, layout.png, known.png, keep.png (model scale)
  combine_job.py split [b00] <canvas.png>  -> <block>/objects/painted.png and <block>/trees/painted_sheet.png
"""
import sys

import numpy as np
from PIL import Image

from layers_common import out_dir

PAINT = 5120


def join(bid):
    d = out_dir(bid)
    o, t = d / "objects", d / "trees"
    j = d / "job"
    j.mkdir(exist_ok=True)
    for name, tname, res in (("src", "sheet_src", Image.LANCZOS), ("layout", "sheet_layout", Image.NEAREST),
                             ("known", "sheet_src", Image.LANCZOS), ("keep", "sheet_keep", Image.NEAREST)):
        top = Image.open(o / f"{name}.png")
        top = top.resize((PAINT, PAINT), res) if top.size != (PAINT, PAINT) else top
        strip = Image.open(t / f"{tname}.png").convert(top.mode)
        im = Image.new(top.mode, (PAINT, PAINT + strip.height))
        im.paste(top, (0, 0)); im.paste(strip, (0, PAINT))
        im.save(j / f"{name}.png")
    print("job inputs in", j, im.size)


def split(bid, canvas):
    d = out_dir(bid)
    im = Image.open(canvas).convert("RGB")
    im.crop((0, 0, PAINT, PAINT)).save(d / "objects" / "painted.png")
    im.crop((0, PAINT, PAINT, im.height)).save(d / "trees" / "painted_sheet.png")
    print("split", im.size)


if __name__ == "__main__":
    bid = next((a for a in sys.argv[2:] if len(a) == 3 and a.startswith("b")), "b00")
    if sys.argv[1] == "join":
        join(bid)
    else:
        split(bid, sys.argv[-1])
