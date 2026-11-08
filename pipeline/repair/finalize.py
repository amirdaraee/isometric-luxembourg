"""Put the item 4 car repair and the item 6 lift repaint into the block canvases (PLAN_NEXT items 4 and 6).

  finalize.py build <block|all> [--lift NAME]   -> data/work/repair/<block>/final_day.png, final_<version>.png
  finalize.py swap <block|all>                  -> backs up data/work/city/<block>/canvas_day_s8.png and every
                                                   version's canvas_<version>_s15.png as *_orig.png next to them
                                                   (once: an existing backup is never overwritten), then writes
                                                   the finals over them

Day: the painter's car repair of the whole block (gpu_repair.py job cars_rp_<block>, data/work/repair/<block>/
cars_rp_<block>.png), and for b00 the lift crop (lift_day_<seed>.png): only the pixels it changed are taken.
Versions: the cars carried from the repaired day by colour transfer (repair_cars.py carry: LAB mean and spread
matched on a ring round each spot, lit pixels left out at night), then the lift version crop (lift_<version>.png).
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import repair_cars as rc  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
VERSIONS = ["night", "golden", "winter", "winter_night", "autumn", "spring"]
OUT = rc.OUT


def changed_onto(base: np.ndarray, new_p: Path, old: np.ndarray) -> np.ndarray:
    new = np.asarray(Image.open(new_p).convert("RGB"))
    m = np.any(new != old, axis=2)
    out = base.copy()
    out[m] = new[m]
    return out


def build(bid, lift):
    st = rc.state()
    d = OUT / bid
    day0 = np.asarray(Image.open(st["done"][bid]).convert("RGB"))
    cars = d / f"cars_rp_{bid}.png"
    day = np.asarray(Image.open(cars).convert("RGB")) if cars.exists() else day0
    if cars.exists():
        # the day with the cars only, for the colour transfer into the versions
        Image.fromarray(day).save(d / "day_cars.png")
    lift_p = d / f"lift_day_{lift}.png" if bid == "b00" and lift else None
    if lift_p and lift_p.exists():
        day = changed_onto(day, lift_p, day0)
    Image.fromarray(day).save(d / "final_day.png")
    print(bid, "day ->", d / "final_day.png", "(cars)" if cars.exists() else "", "(lift)" if lift_p else "")
    for v in VERSIONS:
        if bid not in st.get("done_v", {}).get(v, {}):
            continue
        ver0 = np.asarray(Image.open(st["done_v"][v][bid]).convert("RGB"))
        if cars.exists():
            rc.carry(bid, v, str(d / "day_cars.png"), OUT / f"mask_{bid}_lone.png")
            ver = np.asarray(Image.open(d / f"canvas_{v}_repaired.png").convert("RGB"))
        else:
            ver = ver0
        lv = d / f"lift_{v}.png"
        if lift_p and lv.exists():
            ver = changed_onto(ver, lv, ver0)
        Image.fromarray(ver).save(d / f"final_{v}.png")
        print(bid, v, "->", d / f"final_{v}.png")


def swap(bid):
    st = rc.state()
    d = OUT / bid
    pairs = [(d / "final_day.png", Path(st["done"][bid]))]
    pairs += [(d / f"final_{v}.png", Path(st["done_v"][v][bid])) for v in VERSIONS
              if bid in st.get("done_v", {}).get(v, {})]
    for new, dest in pairs:
        if not new.exists():
            continue
        bak = dest.with_name(dest.stem + "_orig.png")
        if not bak.exists():
            shutil.copy2(dest, bak)
        shutil.copy2(new, dest)
        print(bid, dest.name, "replaced; original kept as", bak.name)


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    lift = sys.argv[sys.argv.index("--lift") + 1] if "--lift" in sys.argv else None
    for b in rc.blocks(arg):
        build(b, lift) if cmd == "build" else swap(b)
