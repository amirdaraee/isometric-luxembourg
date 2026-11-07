"""Choose the training views: the landmarks, then an even spread of ordinary city, parks and valleys."""
import json
import random
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, ".")
from common import WORK, ROOT

OUT = WORK / "style" / "captures"
OUT.mkdir(parents=True, exist_ok=True)
BG = np.array((16, 24, 40))
SRC = 1200  # 300 m across, the scale the map will be generated at
TARGET = 40
LANDMARKS = ["Notre-Dame Cathedral", "Grand Ducal Palace", "Gëlle Fra", "Pont Adolphe", "Bock Casemates", "Neumünster Abbey",
             "Philharmonie", "Mudam", "Dräi Eechelen", "Red Bridge", "Luxembourg Station", "d'Coque", "EU Court of Justice",
             "European Parliament", "Place d'Armes", "Clausen Viaduct"]
m = json.loads((WORK / "mosaic.json").read_text())
F = m["frame"]
W, H = m["cols"] * F, m["rows"] * F
places = {p["n"]: p for p in json.loads((ROOT / "web/public/data/places.json").read_text())}


def crop(cx, cy):
    x0, y0 = cx - SRC // 2, cy - SRC // 2
    out = Image.new("RGB", (SRC, SRC), tuple(int(v) for v in BG))
    for r in range(max(y0, 0) // F, min(y0 + SRC, H - 1) // F + 1):
        for c in range(max(x0, 0) // F, min(x0 + SRC, W - 1) // F + 1):
            out.paste(Image.open(WORK / "frames" / f"{c}_{r}.jpg"), (c * F - x0, r * F - y0))
    return out


def bg_share(im):
    a = np.asarray(im.resize((128, 128)), np.int16)
    return float((np.abs(a - BG).sum(axis=2) < 6).mean())  # tight: dark roofs and shadows are close to this colour


chosen = []
for name in LANDMARKS:
    p = places[name]
    im = crop(p["x"], p["y"])
    assert bg_share(im) < 0.05, f"{name}: {bg_share(im):.2f}"
    chosen.append((name, p["x"], p["y"], im))

# Fill with an even grid over the map, skipping edges and anything overlapping what's already chosen.
rng = random.Random(1867)
cells = [(x + rng.randint(-250, 250), y + rng.randint(-250, 250)) for x in range(1000, W, 2300) for y in range(1000, H, 1500)]
rng.shuffle(cells)
for cx, cy in cells:
    if len(chosen) >= TARGET:
        break
    if any(abs(cx - c[1]) < 1000 and abs(cy - c[2]) < 1000 for c in chosen):
        continue
    im = crop(cx, cy)
    if bg_share(im) >= 0.05:
        continue
    chosen.append((f"area {cx} {cy}", cx, cy, im))

index = []
for i, (name, x, y, im) in enumerate(chosen):
    f = f"{i:02d}.jpg"
    im.resize((1024, 1024), Image.LANCZOS).save(OUT / f, quality=93)
    index.append({"file": f, "name": name, "x": x, "y": y})
(WORK / "style" / "captures.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
print("views", len(index), "landmarks", len(LANDMARKS))
if len(index) < TARGET:
    print("short of target: fewer clear views than", TARGET)

T = 160
cols = 8
sheet = Image.new("RGB", (cols * T, (len(chosen) // cols + 1) * T))
for i, c in enumerate(chosen):
    sheet.paste(c[3].resize((T, T)), (i % cols * T, i // cols * T))
sheet.save(WORK / "style" / "captures_sheet.jpg", quality=85)
