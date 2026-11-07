"""Layered map, step 1, style B: the code drawing given a light repaint by the trained model, exact edges put back.

  style_b.py prep <dir>     -> <dir>/b_layout.png: a ground-only layout map in the painter's colours (green,
                               water, roads, ground; no buildings, so the model does not invent any)
  style_b.py finish <dir> <painted.png>  -> <dir>/stack_B.png and L1_B.png: the repaint at the layer size, with
                               the water and the roads' inked edges from L3/L4 put back exactly on top
The repaint itself runs on Modal (modal_job.py, --init stack_A.png --strength ~0.45).
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

GREEN = {1, 2, 3, 4, 5, 6, 7}   # draw_ground land cover classes that read as green
WATER = 12


def prep(d):
    d = Path(d)
    cls = np.load(d / "landcover.npy")
    roads = np.asarray(Image.open(d / "L4_roads.png"))[..., 3] > 128
    stack = np.asarray(Image.open(d / "stack_A.png"))
    lay = np.zeros(cls.shape + (3,), np.uint8)
    lay[:] = (226, 218, 198)
    lay[np.isin(cls, list(GREEN))] = (110, 170, 90)
    lay[cls == 9] = (185, 185, 190)
    lay[cls == WATER] = (60, 120, 210)
    lay[roads] = (150, 150, 155)
    lay[(np.abs(stack.astype(int) - (16, 24, 40)).sum(2) < 6)] = (16, 24, 40)
    Image.fromarray(lay).save(d / "b_layout.png")
    print(d / "b_layout.png")


def finish(d, painted):
    d = Path(d)
    A = Image.open(d / "stack_A.png")
    P = np.asarray(Image.open(painted).convert("RGB").resize(A.size, Image.LANCZOS)).astype(np.float32)
    L3 = np.asarray(Image.open(d / "L3_water.png")).astype(np.float32)
    L4 = np.asarray(Image.open(d / "L4_roads.png")).astype(np.float32)
    LW = np.asarray(Image.open(d / "L2_walls.png")).astype(np.float32)
    out = P.copy()
    # water: exact mask; inside keep a little of the painted texture
    a3 = L3[..., 3:] / 255
    out = out * (1 - a3) + (L3[..., :3] * 0.7 + P * 0.3) * a3
    # roads: exact outline (the ink casing) on top; the surface keeps some of the painted texture
    a4 = L4[..., 3:] / 255
    casing = (L4[..., :3].sum(2, keepdims=True) < 200).astype(np.float32) * a4
    out = out * (1 - a4) + (L4[..., :3] * 0.75 + P * 0.25) * a4
    out = out * (1 - casing) + L4[..., :3] * casing
    del LW
    out = out.clip(0, 255).astype(np.uint8)
    Image.fromarray(out).save(d / "stack_B.png")
    # the repainted ground alone (for the viewer's L1 in style B): the repaint without the exact layers
    Image.fromarray(P.clip(0, 255).astype(np.uint8)).save(d / "L1_B.png")
    print(d / "stack_B.png")


if __name__ == "__main__":
    {"prep": lambda: prep(sys.argv[2]), "finish": lambda: finish(sys.argv[2], sys.argv[3])}[sys.argv[1]]()
