"""Cut a render region from the mosaic frames for the tiler: make_src.py <x0> <y0> <cells_x> <cells_y> <out.png> [kind]
(mosaic pixels; cells are 600 px). With "kind", cut the visibility frames instead (white ground, grey bridges,
black buildings)."""
import json
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import WORK

x0, y0, nx, ny, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
m = json.loads((WORK / "mosaic.json").read_text())
F = m["frame"]
W, H = m["cols"] * F, m["rows"] * F
w, h = nx * 600, ny * 600
mode = sys.argv[6] if len(sys.argv) > 6 else "rgb"   # rgb | kind | line
kind = mode in ("kind", "line")
im = Image.new("L", (w, h), 255 if mode == "line" else 0) if kind else Image.new("RGB", (w, h), (16, 24, 40))
for r in range(max(y0, 0) // F, min(y0 + h, H) // F + 1):
    for c in range(max(x0, 0) // F, min(x0 + w, W) // F + 1):
        p = WORK / {"rgb": "frames", "kind": "frames_kind", "line": "frames_line"}[mode] / f"{c}_{r}.{'png' if kind else 'jpg'}"
        if p.exists():
            im.paste(Image.open(p), (c * F - x0, r * F - y0))
im.save(out)
print(out, im.size)
