"""Cut test captures in isometric-nyc's input format: 1024 px at its 0.29 m/px scale, with the red fill outline."""
import json
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, ".")
from common import WORK, ROOT

OUT = WORK / "nyc_style_test" / "inputs"
places = {p["n"]: p for p in json.loads((ROOT / "web/public/data/places.json").read_text())}
PICK = ["Notre-Dame Cathedral", "Grand Ducal Palace", "Neumünster Abbey", "Pont Adolphe", "Bock Casemates",
        "Philharmonie", "EU Court of Justice", "Luxembourg Station", "Red Bridge", "Kirchberg"]
m = json.loads((WORK / "mosaic.json").read_text())
F = m["frame"]
SRC = 1200  # 1200 px at 0.25 m/px is 300 m, NYC's 1024 px view


def crop(cx, cy):
    x0, y0 = cx - SRC // 2, cy - SRC // 2
    out = Image.new("RGB", (SRC, SRC))
    for r in range(y0 // F, (y0 + SRC) // F + 1):
        for c in range(x0 // F, (x0 + SRC) // F + 1):
            if 0 <= c < m["cols"] and 0 <= r < m["rows"]:
                out.paste(Image.open(WORK / "frames" / f"{c}_{r}.jpg"), (c * F - x0, r * F - y0))
    return out


for name in PICK:
    p = places[name]
    im = crop(p["x"], p["y"]).resize((1024, 1024), Image.LANCZOS)
    im.save(OUT.parent / "inputs" / f"{name.replace(' ', '_')}.raw.jpg", quality=92)
    d = ImageDraw.Draw(im)
    for i in range(2):
        d.rectangle((i, i, 1023 - i, 1023 - i), outline=(255, 0, 0))
    im.save(OUT / f"{name.replace(' ', '_')}.png")
    print(name, p["x"], p["y"])
