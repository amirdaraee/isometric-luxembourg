"""Layered map v2: export the layers for the viewer's local ?layers=v2 mode (web/public/layers/b00_v2, a link to
data/work/layers/b00_v2/web; never published).

  ground.webp     the painted ground (trees the painter drew into it removed)
  roads.webp      the ink lines (roads, paths, rails, tram tracks, river banks)
  contact.webp    soft ground darkening under the tree crowns
  shadow_*.webp   version 1's sun shadows (optional in the viewer; the painted ground has the photo's own shadows)
  bands/obj_<i>.webp, bands/trees_<season>[_clear]_<i>.webp
                  buildings and bridges (version 1's cut) and the painted trees, cut into depth bands by the map row
                  of the ground point below them (for the vehicles); the trees were already depth-tested against
                  the buildings per pixel, so their order against buildings is exact
  layers.json     as version 1, plus "version": 2
"""
import json

import numpy as np
from PIL import Image

from layers_common import LAYERS, block
from v2_ground import canopy_path, v2_dir

V1 = LAYERS / "b00"
SHADOW = (38, 44, 86)


def save(arr, path, q=88):
    Image.fromarray(arr).save(path, "WEBP", quality=q, method=4)


def main(band=128):
    b = block("b00")
    w = v2_dir("web")
    (w / "bands").mkdir(exist_ok=True)
    g = np.asarray(Image.open(v2_dir("ground") / "L1_ground.png").convert("RGB"))
    S = g.shape[0]
    save(g, w / "ground.webp", 90)
    save(np.asarray(Image.open(v2_dir("ink") / "L2_ink.png")), w / "roads.webp", 92)
    save(np.asarray(Image.open(v2_dir("veg") / "contact.png")), w / "contact.webp")
    for n in ("midday", "evening"):
        a = np.asarray(Image.open(V1 / "shadows" / f"L6_shadow_{n}.png"))
        rgba = np.zeros((S, S, 4), np.uint8)
        rgba[..., :3] = SHADOW
        rgba[..., 3] = (a.astype(np.float32) * 0.42).astype(np.uint8)
        save(rgba, w / f"shadow_{n}.webp")
    o = V1 / "objects"
    bl = np.asarray(Image.open(o / "L7_buildings.png")).astype(np.uint16)
    br = np.asarray(Image.open(o / "L5_bridges.png")).astype(np.uint16)
    a_b, a_r = bl[..., 3:], br[..., 3:]
    obj = np.concatenate((np.where(a_r > a_b, br[..., :3], bl[..., :3]), np.maximum(a_b, a_r)), 2).astype(np.uint8)
    foot = np.asarray(Image.open(o / "foot.png")).astype(np.int32)
    C = np.load(canopy_path())
    trow = C["foot"].astype(np.int32)
    layers = [("obj", obj, foot)]
    seasons = []
    for season, folder in (("summer", "veg"), ("spring", "veg_spring")):
        d = LAYERS / "b00_v2" / folder
        if (d / "L3_veg.png").exists():
            seasons.append(season)
            layers.append((f"trees_{season}", np.asarray(Image.open(d / "L3_veg.png")), trow))
            layers.append((f"trees_{season}_clear", np.asarray(Image.open(d / "L3_veg_clear.png")), trow))
    nb = (S + band - 1) // band + 2
    bands = []
    for i in range(nb):
        lo, hi = i * band, (i + 1) * band
        entry = {"i": i}
        for kind, img, rows in layers:
            m = (rows >= lo) & (rows < hi) & (img[..., 3] > 0)
            if i == nb - 1:
                m |= (rows >= hi) & (img[..., 3] > 0)
            if i == 0:
                m |= (rows < 0) & (img[..., 3] > 0)
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
    meta = {"x0": b["x0"], "y0": b["y0"], "w": b["w"], "h": b["h"], "size": S, "style": "painted", "version": 2,
            "seasons": seasons, "bands": bands}
    (w / "layers.json").write_text(json.dumps(meta))
    print(w, len(bands), "bands", seasons)


if __name__ == "__main__":
    main()
