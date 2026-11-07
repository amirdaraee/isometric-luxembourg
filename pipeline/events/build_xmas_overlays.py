"""Christmas market patches for the viewer: keep the market area of each drawn patch, fade out towards the edge,
save as webp with alpha. Placement (map px) in web/public/events/xmas/xmas.json."""
import json
import numpy as np
import cv2
from PIL import Image
from pathlib import Path
R = Path(__file__).resolve().parents[2]
SRC = R / "data/work/events/christmas"
OUT = R / "web/public/events/xmas"
OUT.mkdir(parents=True, exist_ok=True)
sites = json.loads((SRC / "sites.json").read_text())
out = []
for name, s in sites.items():
    # where the patch differs from the original (the market), grown and softened, plus a soft centre disc
    base = np.asarray(Image.open(SRC / f"{name}_base.png").convert("RGB")).astype(int)
    day = np.asarray(Image.open(SRC / f"{name}_day.png").convert("RGB")).astype(int)
    yy, xx = np.mgrid[0:1024, 0:1024]
    disc = np.clip(1.4 - np.hypot(xx - 512, yy - 512) / 512 * 1.4, 0, 1)
    mask = cv2.GaussianBlur(disc.astype(np.float32), (0, 0), 25)
    for when in ("day", "night"):
        im = Image.open(SRC / f"{name}_{when}.png").convert("RGB")
        a = (mask * 255).astype(np.uint8)
        rgba = np.dstack([np.asarray(im), a])
        Image.fromarray(rgba, "RGBA").save(OUT / f"{name}_{when}.webp", quality=85)
    out.append({"site": name, **s})
(OUT / "xmas.json").write_text(json.dumps(out, indent=1))
print(out)
