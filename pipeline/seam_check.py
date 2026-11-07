"""Find visible borders between painted cells.

Along every cell boundary (every 512 px), compare the average colour (CIELAB) of a thin strip just inside each
side, in 64 px chunks. A real seam is a jump much larger than the colour change you see over the same distance
inside a cell, so each chunk is compared with that natural variation measured at the cell centres.
Usage: seam_check.py <painted.png> <out prefix> [cell px]
Writes <prefix>_seams.jpg (bad borders in magenta) and <prefix>_seams.json (cells touching bad borders)."""
import json
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

src, pref = sys.argv[1], sys.argv[2]
CELL = int(sys.argv[3]) if len(sys.argv) > 3 else 512
CH, NEAR, FAR = 64, 4, 60  # chunk length; strips run from NEAR to FAR px off the line (past a 24 px blend)
im = np.asarray(Image.open(src).convert("RGB"))
lab = cv2.cvtColor(im, cv2.COLOR_RGB2LAB).astype(np.float32)
lab[..., 0] *= 100 / 255
lab[..., 1:] -= 128
H, W = im.shape[:2]
bg = (np.abs(im.astype(int) - [16, 24, 40]).sum(axis=2) < 30)


def jump(axis, pos):
    """Per-chunk colour difference across a line at `pos` (axis 1: vertical line x=pos; axis 0: horizontal y=pos)."""
    out = []
    n = H if axis == 1 else W
    for a in range(0, n - CH + 1, CH):
        if axis == 1:
            A, B = lab[a:a + CH, pos - FAR:pos - NEAR], lab[a:a + CH, pos + NEAR:pos + FAR]
            skip = bg[a:a + CH, pos - FAR:pos + FAR].mean() > 0.05
        else:
            A, B = lab[pos - FAR:pos - NEAR, a:a + CH], lab[pos + NEAR:pos + FAR, a:a + CH]
            skip = bg[pos - FAR:pos + FAR, a:a + CH].mean() > 0.05
        vec = A.reshape(-1, 3).mean(0) - B.reshape(-1, 3).mean(0)
        out.append((a, float(np.linalg.norm(vec)), skip, vec))
    return out


# Natural variation: the same measurement on lines through cell centres, where no seam can be.
natural = [d for axis, lim in ((1, W), (0, H)) for p in range(CELL // 2, lim - FAR, CELL) for _, d, s, _v in jump(axis, p) if not s]
ref = float(np.percentile(natural, 90))
thr = max(6.0, 1.6 * ref)
bad, cells = [], set()
OFFSET = int(sys.argv[4]) if len(sys.argv) > 4 else 0  # 256 = control run on cell centres (no seams there)
RUN = 3  # chunks of 64 px
FACTOR = float(sys.argv[5]) if len(sys.argv) > 5 else 1.5
LOCAL = 80  # compare each border chunk with parallel lines this far away on both sides
for axis, lim in ((1, W), (0, H)):
    for p in range(CELL + OFFSET, lim - FAR - LOCAL - 80, CELL):
        side = [jump(axis, p + o) for o in (-LOCAL - 80, -LOCAL, LOCAL, LOCAL + 80)]
        line = jump(axis, p)
        hit = []
        for k, (a, d, skip, vec) in enumerate(line):
            local = float(np.median([sd[k][1] for sd in side]))
            # Candidate: clearly larger than the typical change nearby, or simply large.
            hit.append(not skip and (d > max(3.0, FACTOR * local) or d > thr))
        # A seam runs straight along the border: keep runs of RUN+ consecutive candidates whose colour shift
        # points the same way (picture edges are short and point every which way).
        k = 0
        while k < len(line):
            if not hit[k]:
                k += 1; continue
            j = k
            while j + 1 < len(line) and hit[j + 1]:
                v0, v1 = line[j][3], line[j + 1][3]
                if float(v0 @ v1) / (np.linalg.norm(v0) * np.linalg.norm(v1) + 1e-6) < 0.6:
                    break
                j += 1
            if j - k + 1 >= RUN:
                for q in range(k, j + 1):
                    bad.append((axis, p, line[q][0], line[q][1]))
            k = j + 1
for axis, p, a, _d in bad:
    c0 = a // CELL
    if axis == 1:
        cells |= {(p // CELL - 1, c0), (p // CELL, c0)}
    else:
        cells |= {(c0, p // CELL - 1), (c0, p // CELL)}
out = Image.fromarray(im)
d = ImageDraw.Draw(out)
for axis, p, a, dv in bad:
    w = 3 + int(min(dv / thr, 3) * 2)
    if axis == 1:
        d.line((p, a, p, a + CH), fill=(255, 0, 200), width=w)
    else:
        d.line((a, p, a + CH, p), fill=(255, 0, 200), width=w)
out.save(pref + "_seams.jpg", quality=85)
json.dump({"threshold": round(thr, 1), "natural_p90": round(ref, 1), "bad_chunks": len(bad),
           "cells": sorted([list(c) for c in cells])}, open(pref + "_seams.json", "w"), indent=1)
total = sum(1 for axis, lim in ((1, W), (0, H)) for p in range(CELL, lim - FAR, CELL) for _ in range(0, (H if axis == 1 else W) - CH + 1, CH))
print(f"natural variation p90 {ref:.1f}, threshold {thr:.1f}: {len(bad)} of {total} border chunks look like seams; "
      f"{len(cells)} cells touch them")
