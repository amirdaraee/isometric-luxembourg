"""Put painted results side by side in the local comparison page (web/public/compare, never published).

  make_compare.py "Today (tiler)=data/work/tiles/v2/day_fixed.png" "New, 25 steps=data/work/tiles/md/showcase_md25.png" ...

Each image is scaled to the first one's size and saved as a JPEG with a manifest. Open
http://localhost:3000/compare/index.html : pick left and right, drag the divider, scroll to zoom, drag to pan.
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "compare"
MAX = 6656  # full painted resolution of the showcase; browsers handle it


def main(pairs):
    OUT.mkdir(parents=True, exist_ok=True)
    items, size = [], None
    for arg in pairs:
        label, path = arg.split("=", 1)
        im = Image.open(ROOT / path if not Path(path).is_absolute() else path).convert("RGB")
        if size is None:
            s = min(1.0, MAX / max(im.size))
            size = (round(im.width * s), round(im.height * s))
        im = im.resize(size, Image.LANCZOS)
        name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") + ".jpg"
        im.save(OUT / name, quality=88)
        items.append({"label": label, "file": name})
        print(label, "->", OUT / name)
    (OUT / "manifest.json").write_text(json.dumps({"size": size, "items": items}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
