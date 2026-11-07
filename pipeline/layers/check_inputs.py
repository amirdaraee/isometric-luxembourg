"""Layered map, step 0: compare the tree sources and the land-use data on today's painted block.

Writes preview images: LiDAR tree survey points vs OpenStreetMap trees on the painted art, and a land-use map.
  check_inputs.py [b00]
"""
import collections
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from layers_common import POC_IMG, block, en_to_map, ground_z, inputs_dir, lonlat_to_map, preview, today


def main():
    bid = sys.argv[1] if len(sys.argv) > 1 else "b00"
    b = block(bid)
    k = 0.25
    base = today(b, k)
    dim = Image.blend(base, Image.new("RGB", base.size, (255, 255, 255)), 0.55)
    trees = json.loads((inputs_dir(bid) / "trees_lidar2024.json").read_text())
    e = np.array([t["e"] for t in trees]); n = np.array([t["n"] for t in trees])
    z = ground_z(e, n)
    x, y = en_to_map(e, n, z)
    x, y = (x - b["x0"]) * k, (y - b["y0"]) * k
    ins = (x >= 0) & (x < base.width) & (y >= 0) & (y < base.height)
    col = {"deciduous_green": (40, 140, 40), "conifer": (20, 80, 90), "deciduous_red": (170, 40, 60), "other": (200, 140, 20)}
    a = dim.copy(); d = ImageDraw.Draw(a)
    for i in np.flatnonzero(ins):
        r = max(1.0, trees[i]["cmean"] * 4 * k)
        d.ellipse((x[i] - r, y[i] - r, x[i] + r, y[i] + r), outline=col.get(trees[i]["type"], (0, 0, 0)))
    n_in = int(ins.sum())
    types = collections.Counter(trees[i]["type"] for i in np.flatnonzero(ins))
    osm = json.loads((inputs_dir(bid) / "osm_extra.json").read_text())["elements"]
    o = dim.copy(); d = ImageDraw.Draw(o)
    n_osm = 0
    rows = 0
    for el in osm:
        tg = el.get("tags", {})
        if tg.get("natural") == "tree" and el["type"] == "node":
            px, py = lonlat_to_map(el["lon"], el["lat"])
            px, py = (px - b["x0"]) * k, (py - b["y0"]) * k
            if 0 <= px < o.width and 0 <= py < o.height:
                n_osm += 1
                d.ellipse((px - 3, py - 3, px + 3, py + 3), outline=(200, 30, 30), width=2)
        if tg.get("natural") == "tree_row" and "geometry" in el:
            q = [tuple(((np.array(lonlat_to_map(p["lon"], p["lat"])) - (b["x0"], b["y0"])) * k)) for p in el["geometry"]]
            d.line(q, fill=(200, 30, 30), width=2)
            rows += 1
    W = base.width
    sheet = Image.new("RGB", (W * 3 + 40, W + 60), (250, 247, 240))
    for i, im in enumerate((base, a, o)):
        sheet.paste(im, (i * (W + 20), 60))
    dd = ImageDraw.Draw(sheet)
    for i, t in enumerate(("Today's painting", f"LiDAR tree survey 2024: {n_in} trees", f"OpenStreetMap: {n_osm} trees, {rows} rows")):
        dd.text((i * (W + 20) + 8, 20), t, fill=(30, 30, 30))
    preview(sheet, POC_IMG / "s0_trees_sources.jpg")
    # close-up: the middle of the block at 4x the scale above
    cx, cy, s = 3000, 3200, 900
    crop = lambda im: im.crop((int(cx * k - s * k / 2), int(cy * k - s * k / 2), int(cx * k + s * k / 2), int(cy * k + s * k / 2))).resize((780, 780), Image.LANCZOS)  # noqa: E731
    big = Image.new("RGB", (780 * 2 + 20, 780), (250, 247, 240))
    big.paste(crop(base), (0, 0)); big.paste(crop(a), (800, 0))
    preview(big, POC_IMG / "s0_trees_closeup.jpg")
    print({"lidar_in_block": n_in, "types": dict(types), "osm_trees": n_osm, "osm_rows": rows})
    tags = collections.Counter()
    for el in osm:
        tg = el.get("tags", {})
        for kk in ("barrier", "historic", "natural", "man_made", "landuse", "leisure", "amenity", "place", "highway", "area:highway"):
            if kk in tg:
                tags[f"{kk}={tg[kk]}"] += 1
    print(tags.most_common(40))


if __name__ == "__main__":
    main()
