"""Layered map v2: automatic boundary checks, one per layer.

Every layer must stay inside its own area, taken from the data, not from the painting:
  ink lines     inside the road, path, rail and water areas of lines.json and the water mask (+2 px soft edge)
  buildings     inside the 3D model's outline of walls, roofs and bridge decks (+2 px slack for eaves, as cut)
  vegetation    inside the visible 3D canopy (after the depth test with buildings and terrain); so never on a
                building except where the tree stands in front of it, never on roads or water except where a real
                crown overhangs them
  contact       the ground darkening under trees only on visible ground
A crossing is a pixel with more than 5% opacity outside its area. The counts go to b00_v2/checks.json and a
highlight picture per layer (crossings in magenta, enlarged so single pixels show) to the progress page.

  v2_checks.py [--tag spring]
"""
import argparse
import json

import cv2
import numpy as np
from PIL import Image

from layers_common import LAYERS, POC_IMG, block, kinds, preview
from v2_ground import PAINT, v2_dir

V1 = LAYERS / "b00"


def highlight(layer_rgba, cross, allowed, path, title):
    S = 1600
    a = layer_rgba[..., 3:].astype(np.float32) / 255
    base = np.full(layer_rgba.shape[:2] + (3,), 236, np.float32)
    base[allowed] = (214, 222, 214)          # the allowed area, pale green-grey
    img = base * (1 - a) + layer_rgba[..., :3] * a
    small = cv2.resize(img, (S, S), interpolation=cv2.INTER_AREA)
    c = cv2.resize(cross.astype(np.uint8), (S, S), interpolation=cv2.INTER_AREA) > 0
    c |= cv2.resize(cross.astype(np.float32), (S, S), interpolation=cv2.INTER_AREA) > 0
    c = cv2.dilate(c.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    small[c] = (255, 0, 200)
    out = Image.fromarray(small.clip(0, 255).astype(np.uint8))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(out)
    dr.rectangle((0, 0, 12 + 7 * len(title), 24), fill=(255, 255, 255))
    dr.text((6, 6), title, fill=(20, 20, 20))
    preview(out, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    b = block("b00")
    k = PAINT / 6000
    res = {}
    # ink
    ink = np.asarray(Image.open(v2_dir("ink") / "L2_ink.png"))
    allowed = np.asarray(Image.open(v2_dir("ink") / "allowed.png")) > 0
    cross = (ink[..., 3] > 13) & ~allowed
    res["ink"] = {"pixels": int((ink[..., 3] > 13).sum()), "crossing": int(cross.sum())}
    highlight(ink, cross, allowed, POC_IMG / "v2_check_ink.jpg", f"Ink lines: {int(cross.sum())} px outside their area")
    # buildings and bridges (version 1's cut, reused)
    kd = kinds(b, k)
    rgb = np.asarray(Image.open(V1 / "objects" / "L7_buildings.png"))
    br = np.asarray(Image.open(V1 / "objects" / "L5_bridges.png"))
    obj = np.where((br[..., 3:] > rgb[..., 3:]), br, rgb)
    outline = (kd <= 200)
    empty = kd == 0
    outline_ok = cv2.dilate(outline.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    cross = (obj[..., 3] > 13) & ~outline_ok
    res["buildings"] = {"pixels": int((obj[..., 3] > 13).sum()), "crossing": int(cross.sum())}
    highlight(obj, cross, outline_ok, POC_IMG / "v2_check_buildings.jpg",
              f"Buildings and bridges: {int(cross.sum())} px outside the 3D outline (+2 px)")
    # vegetation
    C = np.load(v2_dir("canopy") / "canopy_k85.npz")
    vis = C["vis"] > 0
    behind = C["behind"]
    vd = v2_dir("veg" + (f"_{a.tag}" if a.tag else ""))
    for name in ("L3_veg", "L3_veg_clear"):
        p = vd / f"{name}.png"
        if not p.exists():
            continue
        veg = np.asarray(Image.open(p))
        on = veg[..., 3] > 13
        cross = on & ~vis
        key = "vegetation" + ("_clear" if "clear" in name else "")
        res[key] = {"pixels": int(on.sum()), "crossing": int(cross.sum()),
                    "over_buildings_in_front": int((on & (behind == 2)).sum()),
                    "over_buildings_share": round(float((on & (behind == 2)).sum() / max(1, ((behind == 2) & ~empty).sum())), 4)}
        if "clear" not in name:
            highlight(veg, cross, vis, POC_IMG / f"v2_check_vegetation{'_' + a.tag if a.tag else ''}.jpg",
                      f"Vegetation: {int(cross.sum())} px outside the 3D canopy")
    # ground: no painted trees left where the ground is seen (not under a building or a tree)
    from v2_ground import tree_mask
    from terrain_pass import slope_normals
    g = np.asarray(Image.open(v2_dir("ground") / "L1_ground.png").convert("RGB"))
    G = np.load(v2_dir("ground") / "G_k85.npy")
    gentle = slope_normals(G)[..., 2] > np.cos(np.radians(32))
    seen = (obj[..., 3] < 128) & ~vis
    left = tree_mask(g, gentle) & seen
    before = np.asarray(Image.open(v2_dir("ground") / "trees_removed.png")) > 0
    res["ground"] = {"seen_pixels": int(seen.sum()), "painted_trees_removed": int((before & seen).sum()),
                     "tree_like_left": int(left.sum())}
    gl = np.dstack((g, np.full(g.shape[:2], 255, np.uint8)))
    highlight(gl, left, seen, POC_IMG / "v2_check_ground.jpg", f"Ground: {int(left.sum())} tree-like px left where the ground is seen")
    # contact shadows
    p = v2_dir("veg") / "contact.png"
    if p.exists():
        ct = np.asarray(Image.open(p))
        cross = (ct[..., 3] > 13) & (behind != 1)
        res["contact"] = {"pixels": int((ct[..., 3] > 13).sum()), "crossing": int(cross.sum())}
    (LAYERS / "b00_v2" / "checks.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
