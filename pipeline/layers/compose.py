"""Layered map, step 7: stack the exported layers into one image, in the same order as the viewer's ?layers mode.

  compose.py [b00] [--shadow midday|evening|off] [--trees summer|spring|off] [--only ground,roads,...] --out x.png
"""
import argparse
import json

import numpy as np
from PIL import Image

from layers_common import out_dir


def over(dst, src, x=0, y=0):
    h, w = src.shape[:2]
    a = src[..., 3:].astype(np.float32) / 255
    reg = dst[y:y + h, x:x + w]
    reg[:] = reg * (1 - a) + src[..., :3].astype(np.float32) * a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bid", nargs="?", default="b00")
    ap.add_argument("--shadow", default="midday")
    ap.add_argument("--trees", default="summer")
    ap.add_argument("--only", default="ground,relief,water,roads,shadow,walls,objects,trees")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    w = out_dir(a.bid) / "web"
    meta = json.loads((w / "layers.json").read_text())
    on = set(a.only.split(","))
    S = meta["size"]
    img = np.zeros((S, S, 3), np.float32)
    rd = lambda n: np.asarray(Image.open(w / n).convert("RGBA"))  # noqa: E731
    if "ground" in on:
        img[:] = np.asarray(Image.open(w / "ground.webp").convert("RGB"))
    for n in ("relief", "water", "roads"):
        if n in on:
            over(img, rd(f"{n}.webp"))
    if "shadow" in on and a.shadow != "off":
        over(img, rd(f"shadow_{a.shadow}.webp"))
    if "walls" in on:
        over(img, rd("walls.webp"))
    for band in meta["bands"]:
        if "objects" in on and "obj" in band:
            x, y, _, _ = band["obj"]
            over(img, rd(f"bands/obj_{band['i']}.webp"), x, y)
        tk = f"trees_{a.trees}"
        if "trees" in on and a.trees != "off" and tk in band:
            x, y, _, _ = band[tk]
            over(img, rd(f"bands/{tk}_{band['i']}.webp"), x, y)
    Image.fromarray(img.clip(0, 255).astype(np.uint8)).save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
