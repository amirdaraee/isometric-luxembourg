"""Where fog lies on the map: the height of the visible surface and the rivers, for the viewer's fog layer.

Fog forms in the valleys first, over the Alzette and the Petrusse, while the old town on its rock and the Kirchberg
plateau stay above it. The viewer (web/src/components/Fog.tsx) fills everything below a fog line that the weather
sets (valley fog at about 260 m), thickest near water. For that it needs, at a coarse scale:

  R  the height above sea level of the surface seen at each point of the map (roofs, trees, the ground), from the
     render's height pass (data/work/frames_height, 16-bit cm above sea level, 0 = empty), as the median of each
     32 x 32 map px block, scaled 200 m .. 420 m -> 0 .. 255. Empty blocks (outside the data) are 255;
  G  "water nearby": 255 on the rivers and ponds (OpenStreetMap water and waterways from web/public/data/lines.json),
     falling off over about 150 m;
  B  unused (0).

Output: web/public/data/fog.png (1 px = 32 map px = 8 m) and its place in web/public/data/fog.json
  {"file", "scale": map px per px, "w", "h", "h0", "h1": metres at R = 0 and 255}.
Usage: build_fog_mask.py [--work DIR] [--out DIR]
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from common import ROOT, WORK

S = 32             # map px per fog px (8 m: fog is soft)
H0, H1 = 200.0, 420.0
WATER_FALL_M = 150.0
MPP = 0.25


def heights(work: Path, mosaic: dict) -> np.ndarray:
    F, cols, rows = mosaic["frame"], mosaic["cols"], mosaic["rows"]
    n = F // S
    out = np.full((rows * n, cols * n), 255, np.uint8)
    for r in range(rows):
        for c in range(cols):
            f = work / "frames_height" / f"{c}_{r}.png"
            if not f.exists():
                continue
            a = cv2.imread(str(f), cv2.IMREAD_UNCHANGED).astype(np.float32)  # cm, 0 = empty
            blocks = a.reshape(n, S, n, S).transpose(0, 2, 1, 3).reshape(n, n, S * S)
            # the median of the non-empty pixels of each block (empty pixels sorted to the end as NaN)
            b = np.where(blocks > 0, blocks, np.nan)
            empty = ~np.isfinite(b).any(axis=2)
            b[empty] = 0  # all-empty blocks: no warning, marked empty below
            med = np.where(empty, np.nan, np.nanmedian(b, axis=2))
            m = np.clip((med / 100.0 - H0) / (H1 - H0) * 255.0, 0, 255)
            out[r * n:(r + 1) * n, c * n:(c + 1) * n] = np.where(np.isfinite(med), m, 255).astype(np.uint8)
    return out


def water(lines: dict, w: int, h: int) -> np.ndarray:
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for poly in lines.get("water", []):
        p = poly["p"]
        pts = [(p[i] / S, p[i + 1] / S) for i in range(0, len(p), 2)]
        if len(pts) >= 3:
            d.polygon(pts, fill=255)
    for wy in lines.get("waterways", []):
        if wy.get("t"):
            continue  # culverts and tunnels
        p = wy["p"]
        pts = [(p[i] / S, p[i + 1] / S) for i in range(0, len(p), 2)]
        if len(pts) >= 2:
            d.line(pts, fill=255, width=3 if wy.get("k") == "river" else 1)
    wet = np.asarray(im) > 0
    # distance to the nearest water, in metres; fog px are 8 m across (but a ground distance on the map is
    # foreshortened up the screen; near enough for a soft falloff)
    dist = cv2.distanceTransform((~wet).astype(np.uint8), cv2.DIST_L2, 5) * S * MPP
    return (255 * np.exp(-dist / WATER_FALL_M)).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, default=WORK, help="data/work with mosaic.json and frames_height")
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "public" / "data")
    a = ap.parse_args()
    mosaic = json.loads((a.work / "mosaic.json").read_text())
    hgt = heights(a.work, mosaic)
    lines = json.loads((a.out / "lines.json").read_text())
    wat = water(lines, hgt.shape[1], hgt.shape[0])
    rgb = np.dstack([hgt, wat, np.zeros_like(hgt)])
    Image.fromarray(rgb, "RGB").save(a.out / "fog.png", optimize=True)
    (a.out / "fog.json").write_text(json.dumps({"file": "/data/fog.png", "scale": S, "w": int(hgt.shape[1]),
                                                "h": int(hgt.shape[0]), "h0": H0, "h1": H1}))
    size = (a.out / "fog.png").stat().st_size
    print(f"fog.png {hgt.shape[1]} x {hgt.shape[0]}, {size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
