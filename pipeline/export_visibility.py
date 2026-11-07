"""Low-res visibility map for the viewer (1 px = 8 map px = 2 m): 255 ground visible, 128 bridge deck, 0 hidden
(buildings) or outside. The traffic layer only draws vehicles where their road is really visible."""
import json
import numpy as np
from PIL import Image
from common import WORK, ROOT

m = json.loads((WORK / "mosaic.json").read_text())
F, S = m["frame"], 8
out = Image.new("L", (m["cols"] * F // S, m["rows"] * F // S), 0)
for r in range(m["rows"]):
    for c in range(m["cols"]):
        k = np.asarray(Image.open(WORK / "frames_kind" / f"{c}_{r}.png").convert("L"))
        v = np.where(k > 200, 255, np.where((k > 100) & (k <= 200), 128, 0)).astype(np.uint8)
        # a cell counts as visible ground if most of it is
        v = v.reshape(F // S, S, F // S, S)
        g = (v == 255).mean(axis=(1, 3)) > 0.5
        d = (v == 128).mean(axis=(1, 3)) > 0.4
        out.paste(Image.fromarray(np.where(g, 255, np.where(d, 128, 0)).astype(np.uint8)), (c * F // S, r * F // S))
dest = ROOT / "web/public/data/visibility.png"
out.save(dest, optimize=True)
print(dest, out.size, dest.stat().st_size // 1024, "KB")
