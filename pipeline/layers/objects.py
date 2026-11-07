"""Layered map, steps 2 and 3: buildings and bridges painted on a flat backdrop, then cut out.

  objects.py prep [b00]    -> <block>/objects/src.png (the 3D render with all visible ground replaced by one flat
                              backdrop colour), layout.png (the painter's layout map, ground also flat),
                              known.png + keep.png (the backdrop is held fixed while painting, so the model only
                              paints buildings and bridges and the windows with nothing but backdrop are skipped)
  objects.py cut [b00] <painted.png>
                           -> L7_buildings.png and L5_bridges.png (RGBA at the painted size), cut by two rules:
                              1. inside the 3D model's outline (walls, roofs, decks) grown by SLACK px, and
                              2. not the backdrop colour;
                              edges get a one-pixel soft alpha. Also foot.png: for every building pixel, the map row
                              of the ground point straight below it (16-bit, layer px), used to sort buildings,
                              trees and vehicles by depth.
"""
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image

from layers_common import ELEV, block, cut, ground_z, heights, kinds, map_to_en, out_dir

BACKDROP = (255, 0, 255)   # magenta: no building, roof or bridge in the old town has this colour
SLACK = 3                  # px at the painted scale: chimneys and eaves may stand a little outside the 3D outline
PAINT = 5120               # painted size of a 6000 px block


def prep(bid):
    b = block(bid)
    d = out_dir(bid) / "objects"
    d.mkdir(parents=True, exist_ok=True)
    src = np.asarray(cut("frames", "jpg", "RGB", (16, 24, 40), b)).copy()
    kd = kinds(b)
    ground = kd > 200
    empty = np.abs(src.astype(int) - (16, 24, 40)).sum(2) < 20
    # small holes in the render's ground (no data in a few terrain cells) are backdrop too; only the large empty
    # area at the edge of the map stays empty
    n, lab, st, _ = cv2.connectedComponentsWithStats(empty.astype(np.uint8))
    big = np.zeros(n, bool); big[1:] = st[1:, cv2.CC_STAT_AREA] > 200_000
    holes = empty & ~big[lab]
    ground = (ground | holes)
    empty = empty & ~holes
    np.save(d / "ground.npy", np.packbits(ground & ~empty))
    src[ground & ~empty] = BACKDROP
    Image.fromarray(src).save(d / "src.png")
    lay = d / "layout_full.png"
    subprocess.run([sys.executable, str(__import__("pathlib").Path(__file__).parents[1] / "layout.py"), str(b["x0"]),
                    str(b["y0"]), str(b["w"]), str(b["h"]), str(lay)], check=True,
                   cwd=str(__import__("pathlib").Path(__file__).parents[1]))
    la = np.asarray(Image.open(lay).convert("RGB")).copy()
    la[ground & ~empty] = BACKDROP
    Image.fromarray(la).save(d / "layout.png")
    # hold the backdrop: known = the src itself, keep = backdrop (the painter adds a free band round objects)
    Image.fromarray(src).resize((PAINT, PAINT), Image.LANCZOS).save(d / "known.png")
    Image.fromarray(((ground & ~empty) * 255).astype(np.uint8)).resize((PAINT, PAINT), Image.NEAREST).save(d / "keep.png")
    print("objects inputs in", d, f"backdrop {ground.mean():.0%} of the block")


def cut_out(bid, painted):
    b = block(bid)
    d = out_dir(bid) / "objects"
    P = np.asarray(Image.open(painted).convert("RGB")).astype(np.int16)
    S = P.shape[0]
    k = S / b["w"]
    kd = kinds(b, k)
    bld = (kd <= 100)            # walls and roofs (and the empty edge and holes, removed below)
    deck = (kd > 100) & (kd <= 200)
    rgb = np.asarray(cut("frames", "jpg", "RGB", (16, 24, 40), b, k, Image.BILINEAR)).astype(int)
    empty = np.abs(rgb - (16, 24, 40)).sum(2) < 30
    gr = np.unpackbits(np.load(d / "ground.npy"))[:b["w"] * b["h"]].reshape(b["h"], b["w"])
    gr = cv2.resize(gr, (S, S), interpolation=cv2.INTER_NEAREST) > 0
    bld &= ~empty & ~gr
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * SLACK + 1, 2 * SLACK + 1))
    # rule 2: far from the backdrop colour (distance in RGB; the model shifts flat colours a little)
    dist = np.abs(P - np.array(BACKDROP)).sum(2)
    notbg = np.clip((dist - 120) / 80, 0, 1)
    out = {}
    for name, m in (("L7_buildings", bld), ("L5_bridges", deck)):
        rule1 = cv2.dilate(m.astype(np.uint8), ker) > 0
        a = notbg * rule1
        # one-pixel soft edge: average with neighbours only at the boundary
        soft = cv2.blur(a.astype(np.float32), (3, 3))
        edge = (cv2.dilate(a.astype(np.float32), np.ones((3, 3))) > 0) & (cv2.erode(a.astype(np.float32), np.ones((3, 3))) < 1)
        a = np.where(edge, np.minimum(a, soft) if False else soft * (a > 0) + soft * 0.5 * (a == 0), a)
        # pull magenta out of edge pixels (despill)
        col = P.astype(np.float32).copy()
        spill = np.clip((col[..., 0] + col[..., 2]) / 2 - col[..., 1] - 40, 0, None)
        col[..., 0] -= spill * 0.6; col[..., 2] -= spill * 0.6
        rgba = np.dstack((col.clip(0, 255), (a * 255).clip(0, 255))).astype(np.uint8)
        Image.fromarray(rgba).save(d / f"{name}.png")
        out[name] = rgba
        print(name, f"{(a > 0.5).mean():.1%} of the block")
    # what rule 1 removed (model inventions outside the outline) and what rule 2 removed inside it, for checking
    inv = (notbg > 0.5) & ~(cv2.dilate((bld | deck).astype(np.uint8), ker) > 0)
    Image.fromarray((inv * 255).astype(np.uint8)).save(d / "removed_outside.png")
    # foot rows: the ground point below each object pixel, as a map row in layer px
    hz = heights(b, k)
    H, W = hz.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    mx, my = b["x0"] + xx / k, b["y0"] + yy / k
    e, n = map_to_en(mx, my, hz)
    zg = ground_z(e, n)
    above = np.clip(hz - zg, 0, None)
    foot = yy + above * np.cos(ELEV) / 0.25 * k
    foot[hz <= 0] = 0
    Image.fromarray(np.clip(foot, 0, 65535).astype(np.uint16)).save(d / "foot.png")
    print("foot rows written", d / "foot.png")


if __name__ == "__main__":
    cmd = sys.argv[1]
    bid = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("b") else "b00"
    if cmd == "prep":
        prep(bid)
    else:
        cut_out(bid, sys.argv[-1])
