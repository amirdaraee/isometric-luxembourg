"""Layered map, step 6: export one block's layers for the viewer's local ?layers mode.

Writes <block>/web/ (served as web/public/layers/<block>/ in a local checkout, never published):
  ground.webp, relief.webp, water.webp, roads.webp, walls.webp   L1-L4 and the walls (the ground stack)
  shadow_midday.webp, shadow_evening.webp                          L6, already in the shadow colour with alpha
  bands/obj_<i>.webp, bands/trees_<season>_<i>.webp                buildings + bridges (L7, L5) and trees (L8), cut
                                                                   into horizontal depth bands by the row of the
                                                                   ground point below each pixel; the viewer draws
                                                                   band 0 (far) to the last (near), objects then
                                                                   trees in each band, so a tree in front of a
                                                                   house covers it and one behind is hidden
  layers.json   {"x0", "y0", "w", "h" (map px), "size" (layer px), "bands": [{"i", "box": [x, y, w, h], ...}]}

  export_web.py [b00] [--style A|B] [--band 128]
"""
import argparse
import json

import numpy as np
from PIL import Image

from layers_common import block, out_dir

SHADOW = (38, 44, 86)   # cool blue-violet, like the painting's shadows


def save(arr, path, q=88):
    Image.fromarray(arr).save(path, "WEBP", quality=q, method=4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bid", nargs="?", default="b00")
    ap.add_argument("--style", default="A")
    ap.add_argument("--band", type=int, default=128)
    args = ap.parse_args()
    b = block(args.bid)
    d = out_dir(args.bid)
    g = d / "k85"
    w = d / "web"
    (w / "bands").mkdir(parents=True, exist_ok=True)
    L1 = np.asarray(Image.open(g / ("L1_B.png" if args.style == "B" else "L1_ground.png")).convert("RGB"))
    S = L1.shape[0]
    save(L1, w / "ground.webp")
    for src, name in (("L2_relief", "relief"), ("L3_water", "water"), ("L4_roads", "roads"), ("L2_walls", "walls")):
        save(np.asarray(Image.open(g / f"{src}.png").convert("RGBA")), w / f"{name}.webp")
    for n in ("midday", "evening"):
        a = np.asarray(Image.open(d / "shadows" / f"L6_shadow_{n}.png"))
        rgba = np.zeros((S, S, 4), np.uint8)
        rgba[..., :3] = SHADOW
        rgba[..., 3] = (a.astype(np.float32) * 0.42).astype(np.uint8)
        save(rgba, w / f"shadow_{n}.webp")
    # objects: buildings and bridges together, banded by foot row
    o = d / "objects"
    bl = np.asarray(Image.open(o / "L7_buildings.png")).astype(np.uint16)
    br = np.asarray(Image.open(o / "L5_bridges.png")).astype(np.uint16)
    a_b, a_r = bl[..., 3:], br[..., 3:]
    obj = np.concatenate((np.where(a_r > a_b, br[..., :3], bl[..., :3]), np.maximum(a_b, a_r)), 2).astype(np.uint8)
    foot = np.asarray(Image.open(o / "foot.png")).astype(np.int32)
    trees = {}
    for season in ("summer", "spring"):
        p = d / "trees" / f"L8_trees_{season}_k85.png"
        if p.exists():
            trees[season] = np.asarray(Image.open(p))
    trow = np.asarray(Image.open(d / "trees" / "tree_rows_k85.png")).astype(np.int32) if trees else None
    nb = (S + args.band - 1) // args.band + 2
    bands = []
    for i in range(nb):
        lo, hi = i * args.band, (i + 1) * args.band
        entry = {"i": i}
        for kind, img, rows in [("obj", obj, foot)] + [(f"trees_{s}", t, trow) for s, t in trees.items()]:
            m = (rows >= lo) & (rows < hi) & (img[..., 3] > 0)
            if i == nb - 1:
                m |= (rows >= hi) & (img[..., 3] > 0)
            if not m.any():
                continue
            ys, xs = np.nonzero(m)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            cut = img[y0:y1, x0:x1].copy()
            cut[..., 3] = np.where(m[y0:y1, x0:x1], cut[..., 3], 0)
            save(cut, w / "bands" / f"{kind}_{i}.webp", 90)
            entry[kind] = [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]
        if len(entry) > 1:
            bands.append(entry)
    meta = {"x0": b["x0"], "y0": b["y0"], "w": b["w"], "h": b["h"], "size": S, "style": args.style,
            "seasons": list(trees), "bands": bands}
    (w / "layers.json").write_text(json.dumps(meta))
    print(w, len(bands), "bands")


if __name__ == "__main__":
    main()
