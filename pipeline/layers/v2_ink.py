"""Layered map v2, layer 2: exact inked lines on the painted ground.

Roads, paths, steps, rail and tram tracks come from web/public/data/lines.json, the same lines the vehicles drive
on (drawn with draw_ground.draw_roads at their measured widths); river banks from version 1's exact water mask.
Instead of flat vector fills they are drawn as a light touch over the painting:
  - a thin ink line along both edges of every road and path, lane dashes and step treads;
  - rails, sleepers and tram rails in ink, the ballast bed edged;
  - an ink line along the river banks;
  - an asphalt (or paving) tone only where the painted road surface is missing (the painter put grass, a bush or a
    roof there), so the road is always readable but the painted texture shows through everywhere else.
The layer is RGBA, drawn over the painted ground and under shadows, buildings and trees.

  v2_ink.py [--painted b00_v2/ground/L1_painted.png]   -> b00_v2/ink/L2_ink.png, allowed.png (where ink may be)
"""
import argparse
import json

import cv2
import numpy as np
from PIL import Image

from layers_common import LAYERS, ROOT, block
from v2_ground import PAINT, v2_dir

INK = np.array((48, 40, 36), np.float32)


def ring(m, r=1):
    m8 = (m > 0.5).astype(np.uint8)
    k = np.ones((2 * r + 1, 2 * r + 1), np.uint8)
    return ((cv2.dilate(m8, k) > 0) & ~(cv2.erode(m8, k) > 0)).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--painted", default=str(LAYERS / "b00_v2" / "ground" / "L1_painted.png"))
    a = ap.parse_args()
    from draw_ground import draw_roads
    b = block("b00")
    k = PAINT / 6000
    S = PAINT
    L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
    m = draw_roads(L, b, k, (S, S))
    P = np.asarray(Image.open(a.painted).convert("RGB")).astype(np.float32)
    rgb = np.zeros((S, S, 3), np.float32)
    alpha = np.zeros((S, S), np.float32)

    def put(mask, col, op):
        nonlocal rgb, alpha
        aa = np.clip(mask, 0, 1) * op
        rgb = rgb * (1 - aa[..., None]) + np.asarray(col, np.float32) * aa[..., None]
        alpha = alpha + aa * (1 - alpha)

    car = np.clip(m["road"], 0, 1)
    ped = np.clip(m["ped"], 0, 1)
    path = np.clip(np.maximum(m["path"], m["steps"]), 0, 1)
    fill = np.maximum(np.maximum(car, ped), path)
    # 1. surface tone only where the painting lost the road: green or far from the road's own painted colour
    tone = np.zeros((S, S), np.float32)
    for mm, op in ((car, 0.62), (ped, 0.5)):
        sel = mm > 0.8
        ref = np.median(P[sel], axis=0)
        dist = np.abs(P - ref).sum(2)
        green = (P[..., 1] - np.maximum(P[..., 0], P[..., 2])) > 10
        miss = ((dist > 95) | green).astype(np.float32)
        miss = cv2.GaussianBlur(cv2.morphologyEx(miss, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), (0, 0), 1.2)
        t = miss * (mm > 0.5)
        put(t * mm, ref, op)
        tone += t * mm
    # 2. ink along the road and path edges (the casing outside the fill)
    casing = np.clip(m["case"] - fill, 0, 1)
    put(casing, INK, 0.72)
    # 3. lane dashes and step treads
    put(m["dash"] * (fill > 0.3), (238, 234, 222), 0.8)
    # 4. rail: ballast bed edge, sleepers, rails; tram rails
    put(np.clip(m["rcase"] - m["rbed"], 0, 1), INK, 0.6)
    put(m["sleep"] * (m["rbed"] > 0.3), (78, 62, 50), 0.6)
    put(m["rail"], (36, 32, 30), 0.92)
    put(m["tram"], (58, 54, 52), 0.75)
    # 5. river banks
    wm = np.asarray(Image.open(LAYERS / "b00" / "k85" / "water_mask.png").convert("L"))
    if wm.shape != (S, S):
        wm = cv2.resize(wm, (S, S), interpolation=cv2.INTER_NEAREST)
    bank = cv2.GaussianBlur(ring(wm > 127, 1), (0, 0), 0.5)
    put(bank, (36, 52, 64), 0.6)
    d = v2_dir("ink")
    rgba = np.dstack((rgb.clip(0, 255), (alpha * 255).clip(0, 255))).astype(np.uint8)
    Image.fromarray(rgba).save(d / "L2_ink.png")
    # where ink may be: the road, path, rail and water areas of the data, grown by 2 px (soft edges)
    allowed = (np.maximum.reduce([m["case"], m["rcase"], m["rail"], m["tram"], m["rbed"]]) > 0.02) | (wm > 127)
    allowed = cv2.dilate(allowed.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    Image.fromarray((allowed * 255).astype(np.uint8)).save(d / "allowed.png")
    np.save(d / "tone.npy", (tone * 255).clip(0, 255).astype(np.uint8))
    print("ink layer", f"{(alpha > 0.05).mean():.1%} of the block,", f"surface tone added on {(tone > 0.3).sum() / max(1, (fill > 0.5).sum()):.1%} of road area")


if __name__ == "__main__":
    main()
