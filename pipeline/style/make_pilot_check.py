"""Views for choosing a checkpoint: landmarks seen from a shifted crop (new composition), plus ordinary
areas far from every training view. Outlined like full-generation inputs."""
import json
import sys
import numpy as np
from PIL import ImageDraw, Image

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from common import WORK

S = WORK / "style"
OUT = S / "dataset" / "pilot_check"
OUT.mkdir(parents=True, exist_ok=True)
caps = json.loads((S / "captures.json").read_text())
pos = {c["name"]: (c["x"], c["y"]) for c in caps}
m = json.loads((WORK / "mosaic.json").read_text())
F, SRC = m["frame"], 1200
W, H = m["cols"] * F, m["rows"] * F
BG = np.array((16, 24, 40))


def crop(cx, cy):
    x0, y0 = cx - SRC // 2, cy - SRC // 2
    out = Image.new("RGB", (SRC, SRC), tuple(int(v) for v in BG))
    for r in range(max(y0, 0) // F, min(y0 + SRC, H - 1) // F + 1):
        for c in range(max(x0, 0) // F, min(x0 + SRC, W - 1) // F + 1):
            out.paste(Image.open(WORK / "frames" / f"{c}_{r}.jpg"), (c * F - x0, r * F - y0))
    return out


def bg_share(im):
    a = np.asarray(im.resize((128, 128)), np.int16)
    return float((np.abs(a - BG).sum(axis=2) < 6).mean())


views = []
# Shifted by ~half a view so the landmark sits off-centre in a crop the model has not seen.
for name, dx, dy in [("Red Bridge", 500, 250), ("Luxembourg Station", -500, 250), ("Neumünster Abbey", 450, -300),
                     ("Pont Adolphe", -450, -300), ("Bock Casemates", -500, 300), ("Clausen Viaduct", 500, -250)]:
    x, y = pos[name]
    views.append((f"{name} (shifted)", x + dx, y + dy))
used = [(c["x"], c["y"]) for c in caps]
for y in range(1500, H - 1000, 700):
    for x in range(1500, W - 1000, 700):
        if len(views) == 10:
            break
        if min(abs(x - a) + abs(y - b) for a, b in used + [(v[1], v[2]) for v in views]) < 1500:
            continue
        if bg_share(crop(x, y)) > 0.0005:
            continue
        views.append((f"area {x} {y}", x, y))
meta = []
for i, (name, x, y) in enumerate(views):
    im = crop(x, y).resize((1024, 1024), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for k in range(2):
        d.rectangle((k, k, 1023 - k, 1023 - k), outline=(255, 0, 0))
    im.save(OUT / f"p{i:02d}.png")
    meta.append({"file": f"p{i:02d}.png", "name": name, "x": x, "y": y, "edge_bg": round(bg_share(im), 4)})
    print(i, name, x, y)
(OUT / "views.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
