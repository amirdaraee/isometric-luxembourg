"""Re-cut every training view from the current frames, at the same positions as before."""
import json
import sys
from PIL import Image

sys.path.insert(0, ".")
from common import WORK

S = WORK / "style"
m = json.loads((WORK / "mosaic.json").read_text())
F = m["frame"]
W, H = m["cols"] * F, m["rows"] * F
SRC = 1200
for it in json.loads((S / "captures.json").read_text()):
    x0, y0 = it["x"] - SRC // 2, it["y"] - SRC // 2
    out = Image.new("RGB", (SRC, SRC), (16, 24, 40))
    for r in range(max(y0, 0) // F, min(y0 + SRC, H - 1) // F + 1):
        for c in range(max(x0, 0) // F, min(x0 + SRC, W - 1) // F + 1):
            out.paste(Image.open(WORK / "frames" / f"{c}_{r}.jpg"), (c * F - x0, r * F - y0))
    out.resize((1024, 1024), Image.LANCZOS).save(S / "captures" / it["file"], quality=93)
print("recut", len(json.loads((S / "captures.json").read_text())))
