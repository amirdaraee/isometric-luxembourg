"""Check event patches for halos and edges. For each patch:
  - alpha: whether the file has any non-opaque pixel (it must not: the viewer's WebGL drawer turns any alpha edge
    into a light rim, see patchlib.py);
  - edge: the mean absolute difference between the patch's outer 3 px and the map tiles the viewer shows there
    (the art as built by build_variant_tiles.py), target < 1.5 levels: a step here would show as a straight line;
  - rim: the mean brightness change (L, patch minus tiles) in the 2 to 6 px just outside everything the patch
    changes, target within +-3: a light or dark ring round the market would show here;
  - changed: the share of the box that differs from the tiles.
Writes a contact sheet (tiles | with the patch | difference x4) to data/work/events/patch_check_<dir>.jpg.

Usage: patch_check.py [manifest.json ...]   default web/public/events/xmas/xmas.json
A manifest is a list of {"site", "x0", "y0", "w", "h"}; files are <dir>/<site>_<day|night>.webp, and the art is
winter / winter night for Christmas, or the version given as "day_version" / "night_version" in an entry.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.path.insert(0, str(Path(__file__).parent))
from common import WORK  # noqa: E402
import patchlib  # noqa: E402


def check(path: Path) -> bool:
    entries = json.loads(path.read_text())
    ok = True
    rows = []
    for e in entries:
        for when in ("day", "night"):
            f = path.parent / f"{e['site']}_{when}.webp"
            if not f.exists():
                continue
            version = e.get(f"{when}_version", "winter" if when == "day" else "winter_night")
            im = Image.open(f)
            alpha = im.mode == "RGBA" and int(np.asarray(im)[..., 3].min()) < 255
            p = np.asarray(im.convert("RGB")).astype(int)
            t = patchlib.tiles_crop(version, e["x0"], e["y0"], e["w"], e["h"])
            if t is None:
                print(f"{e['site']:>14} {when:5}  no tiles for {version}")
                continue
            t = t.astype(int)
            diff = np.abs(p - t).mean(2)
            border = np.ones(diff.shape, bool)
            border[3:-3, 3:-3] = False
            edge = float(diff[border].mean())
            changed = (diff > 6).astype(np.uint8)
            changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            d = cv2.distanceTransform(1 - changed, cv2.DIST_L2, 5)
            ring = (d >= 2) & (d <= 6)
            L = lambda a: cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_RGB2LAB)[..., 0].astype(float) * 100 / 255  # noqa: E731
            rim = float((L(p) - L(t))[ring].mean()) if ring.any() else 0.0
            good = not alpha and edge < 1.5 and abs(rim) < 3
            ok &= good
            print(f"{e['site']:>14} {when:5}  alpha {'YES' if alpha else 'no'}  edge {edge:4.2f}  rim {rim:+5.2f} L  "
                  f"changed {changed.mean() * 100:4.1f}%  {'ok' if good else 'CHECK'}")
            rows.append(np.hstack([t, p, np.clip(np.abs(p - t) * 4, 0, 255)]).astype(np.uint8))
    if rows:
        w = max(r.shape[1] for r in rows)
        sheet = np.vstack([np.pad(r, ((0, 4), (0, w - r.shape[1]), (0, 0))) for r in rows])
        out = WORK / "events" / f"patch_check_{path.parent.name}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(sheet).save(out, quality=85)
        print("sheet:", out)
    return ok


if __name__ == "__main__":
    paths = [Path(p) for p in sys.argv[1:]] or [ROOT / "web/public/events/xmas/xmas.json"]
    sys.exit(0 if all([check(p) for p in paths]) else 1)
