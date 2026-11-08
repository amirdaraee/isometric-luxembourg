"""Put everything that moves on the map where the painting has it (task T2b): one command after any repaint.

    cd pipeline && .venv/bin/python fit_to_art.py            (about 45 minutes, up to 4 GB; one step at a time)
    cd pipeline && .venv/bin/python fit_to_art.py --from drivable   (skip the field, e.g. after changing lines.json)

Steps, in order (each is its own script and can be run alone):
  1. flow_field.py      the render -> painting displacement field, block by block: ground, built and road layers
                        (data/work/flowfit/field.npz), with its validation (data/work/flowfit/validate.json)
  2. build_drivable.py  the drivable map, its render parts (kinds pass, footprints, corridors) moved through the field
  3. build_occlusion.py the occluders (from the render), then occluders_to_art() below moves their built layers (R, G)
                        through the built field; the tree canopy (B) is found in the painting and stays
  4. fit_roads.py       lines.json "q" (roads and tracks: the road layer of the field, then a colour fit of at most
                        1 m), transit.json "fit", road_heights.json "fx"/"fy", the painted-road masks and the guard
  5. the checks: web/src/sim/roadfit.test.ts (on-road shares) -> data/work/flowfit/check.json
The water mask (build_water_mask.py) is found in the painting itself and needs nothing here; landmark pins and
statues keep their positions (the field moves them by 1.5-3 m at most, under a pin's size).
"""
import argparse
import json
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

from common import ROOT, WORK
from flowfield import FLOWFIT, Field

HERE = ROOT / "pipeline"
DATA = ROOT / "web/public/data"
STEPS = ("field", "drivable", "occlusion", "roads", "check")


def run(*cmd, cwd=HERE):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def occluders_to_art():
    """Move the R and G channels of data/occluders/*.png (heights of built surfaces, from the render) through the
    built field. The render's tiles are kept in data/work/flowfit/occluders_render/ so this can run twice; a fresh
    build_occlusion.py (occluders.json without "field") replaces them."""
    meta_f = DATA / "occluders.json"
    meta = json.loads(meta_f.read_text())
    keep = FLOWFIT / "occluders_render"
    if not meta.get("field"):
        if keep.exists():
            shutil.rmtree(keep)
        keep.mkdir(parents=True)
        for n in meta["tiles"]:
            shutil.copy(DATA / "occluders" / f"{n}.png", keep / f"{n}.png")
        shutil.copy(meta_f, keep / "occluders.json")
    FB = Field.load("built")
    S, T, x0, y0 = meta["scale"], meta["tile"], meta["x0"], meta["y0"]
    assert x0 % S == 0 and y0 % S == 0
    W, H = meta["w"], meta["h"]
    img = np.zeros((H, W, 3), np.uint8)
    for n in meta["tiles"]:
        tx, ty = map(int, n.split("_"))
        a = np.asarray(Image.open(keep / f"{n}.png").convert("RGB"))
        img[ty * T:ty * T + a.shape[0], tx * T:tx * T + a.shape[1]] = a
    moved = FB.warp(np.ascontiguousarray(img[..., :2]), S, nearest=True, y0=y0 // S, x0=x0 // S)
    img[..., :2] = moved
    for f in (DATA / "occluders").glob("*.png"):
        f.unlink()
    names = []
    for ty in range(-(-H // T)):
        for tx in range(-(-W // T)):
            t = img[ty * T:(ty + 1) * T, tx * T:(tx + 1) * T]
            if t.any():
                Image.fromarray(t).save(DATA / "occluders" / f"{tx}_{ty}.png", optimize=True)
                names.append(f"{tx}_{ty}")
    meta["tiles"], meta["field"] = names, "built"
    meta_f.write_text(json.dumps(meta))
    print(f"occluders moved to the painting: {len(names)} tiles", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", choices=STEPS, default="field")
    ap.add_argument("--only", choices=STEPS + ("occluders",))
    a = ap.parse_args()
    py = sys.executable
    todo = [a.only] if a.only else STEPS[STEPS.index(a.start):]
    for s in todo:
        if s == "field":
            run(py, "flow_field.py")
        elif s == "drivable":
            run(py, "build_drivable.py")
        elif s == "occlusion":
            run(py, "build_occlusion.py")
            occluders_to_art()
        elif s == "occluders":
            occluders_to_art()
        elif s == "roads":
            run(py, "fit_roads.py", "--remeasure")
        elif s == "check":
            run("node", "src/sim/roadfit.test.ts", "5", "0.75", "--min", "0", "--json",
                FLOWFIT / "check.json", cwd=ROOT / "web")


if __name__ == "__main__":
    main()
