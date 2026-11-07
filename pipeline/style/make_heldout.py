"""Two fresh views the model never trains on, outlined like full-generation inputs, for honest progress samples."""
import json
import sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, ".")
from common import WORK

S = WORK / "style"
OUT = S / "dataset" / "heldout"
OUT.mkdir(parents=True, exist_ok=True)
m = json.loads((WORK / "mosaic.json").read_text())
F = m["frame"]
W, H = m["cols"] * F, m["rows"] * F
used = [(i["x"], i["y"]) for i in json.loads((S / "captures.json").read_text())]
BG = np.array((16, 24, 40))


def crop(cx, cy, src=1200):
    x0, y0 = cx - src // 2, cy - src // 2
    out = Image.new("RGB", (src, src), (16, 24, 40))
    for r in range(max(y0, 0) // F, min(y0 + src, H - 1) // F + 1):
        for c in range(max(x0, 0) // F, min(x0 + src, W - 1) // F + 1):
            out.paste(Image.open(WORK / "frames" / f"{c}_{r}.jpg"), (c * F - x0, r * F - y0))
    return out


# Old-town fringe (Pfaffenthal side) and the Kirchberg edge, away from every training view.
picks = []
cands = [(9800, 5900), (8600, 4700), (16500, 6900), (11800, 7600), (6800, 7400)]
cands += [(x, y) for y in range(1500, H - 1000, 500) for x in range(1500, W - 1000, 500)]
for cx, cy in cands:
    if min(abs(cx - x) + abs(cy - y) for x, y in used) < 1300:
        continue
    im = crop(cx, cy)
    a = np.asarray(im.resize((256, 256)), np.int16)
    if (np.abs(a - BG).sum(axis=2) < 6).mean() > 0.0005:
        continue
    picks.append((cx, cy, im))
    if len(picks) == 2:
        break
assert len(picks) == 2, f"only {len(picks)} clean held-out views"
for i, (cx, cy, im) in enumerate(picks):
    im = im.resize((1024, 1024), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for k in range(2):
        d.rectangle((k, k, 1023 - k, 1023 - k), outline=(255, 0, 0))
    im.save(OUT / f"heldout_{i}.png")
    print("held-out", i, cx, cy)
