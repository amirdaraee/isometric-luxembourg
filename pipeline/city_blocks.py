"""Whole-city painting in blocks (PLAN.md Phase 3).

The map (mosaic px, 0.25 m/px) is cut into 6000 px blocks overlapping by 1200 px (= 1024 model px, one window),
aligned so the old-town showcase (5500, 3700) is one block. Blocks are painted outward from the old town; each new
block holds the pixels its finished neighbours already painted (mdpaint.py --known/--keep), so blocks meet
without seams.

  city_blocks.py plan                 -> data/work/city/blocks.json and blocks.jpg (preview)
  city_blocks.py prepare <id>         -> data/work/city/<id>/src.png, kind.png, layout.png (painter inputs)
  city_blocks.py known <id> [version] -> data/work/city/<id>/known[_version].png, keep[_version].png from the
                                         finished blocks (of that version: night, winter, ...; default the day map)
  city_blocks.py done <id> <canvas> [version] -> registers a painted canvas as finished
  city_blocks.py patches <version>   -> data/work/city/patches_<version>.json for build_variant_tiles.py
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from common import WORK

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).parent
CITY = WORK / "city"
BLOCK, OVERLAP = 6000, 1200
STRIDE = BLOCK - OVERLAP
ANCHOR = (5500, 3700)   # the old-town showcase block
BG = np.array((16, 24, 40))
PY = sys.executable


def data_mask(s=16):
    """Where the map has 3D data, at 1/s scale."""
    m = json.loads((WORK / "mosaic.json").read_text())
    F = m["frame"]
    small = np.zeros((m["rows"] * F // s, m["cols"] * F // s), bool)
    for r in range(m["rows"]):
        for c in range(m["cols"]):
            a = np.asarray(Image.open(WORK / "frames" / f"{c}_{r}.jpg").reduce(s)).astype(int)
            small[r * F // s:(r + 1) * F // s, c * F // s:(c + 1) * F // s] = np.abs(a - BG).sum(2) > 20
    return small, m["cols"] * F, m["rows"] * F


def axis(start, n):
    ps = []
    p = start
    while p > -BLOCK + OVERLAP:
        p -= STRIDE
    p += STRIDE
    while p < n:
        ps.append(p)
        p += STRIDE
    return ps


def plan():
    s = 16
    mask, W, H = data_mask(s)
    blocks = []
    for y0 in axis(ANCHOR[1], H):
        for x0 in axis(ANCHOR[0], W):
            a = mask[max(0, y0) // s:max(0, y0 + BLOCK) // s, max(0, x0) // s:max(0, x0 + BLOCK) // s]
            fill = float(a.mean()) if a.size else 0.0
            if fill < 0.03:
                continue
            cx, cy = x0 + BLOCK / 2 - (ANCHOR[0] + BLOCK / 2), y0 + BLOCK / 2 - (ANCHOR[1] + BLOCK / 2)
            blocks.append({"x0": x0, "y0": y0, "w": BLOCK, "h": BLOCK, "fill": round(fill, 3),
                           "dist": round(float(np.hypot(cx, cy)))})
    blocks.sort(key=lambda b: b["dist"])
    for i, b in enumerate(blocks):
        b["id"] = f"b{i:02d}"
    CITY.mkdir(parents=True, exist_ok=True)
    state = load()
    state["blocks"] = blocks
    save(state)
    # preview
    from PIL import ImageDraw
    k = 1 / 32
    im = Image.fromarray((mask * 255).astype(np.uint8)).resize((round(W * k), round(H * k))).convert("RGB")
    d = ImageDraw.Draw(im)
    for b in blocks:
        box = [b["x0"] * k, b["y0"] * k, (b["x0"] + BLOCK) * k, (b["y0"] + BLOCK) * k]
        d.rectangle(box, outline=(239, 51, 64) if b["id"] == "b00" else (60, 120, 210), width=2)
        d.text((box[0] + 4, box[1] + 4), f"{b['id']} {b['fill']:.0%}", fill=(239, 51, 64))
    im.save(CITY / "blocks.jpg", quality=90)
    total_fill = sum(b["fill"] for b in blocks)
    print(f"{len(blocks)} blocks (b00 = showcase), equivalent to {total_fill:.1f} full blocks of data")
    for b in blocks:
        print(b["id"], b["x0"], b["y0"], f"fill {b['fill']:.0%}", f"dist {b['dist']}")


def load():
    p = CITY / "blocks.json"
    return json.loads(p.read_text()) if p.exists() else {"blocks": [], "done": {}}


def save(state):
    (CITY / "blocks.json").write_text(json.dumps(state, indent=1))


def get(bid):
    st = load()
    return st, next(b for b in st["blocks"] if b["id"] == bid)


def run(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=HERE)


def prepare(bid):
    _, b = get(bid)
    out = CITY / bid
    out.mkdir(parents=True, exist_ok=True)
    cells = BLOCK // 600
    mk = HERE / "gpu_train" / "tiles" / "make_src.py"
    run(PY, mk, b["x0"], b["y0"], cells, cells, out / "raw.png")
    run(PY, mk, b["x0"], b["y0"], cells, cells, out / "kind.png", "kind")
    # true water, clean tracks, no parked cars (no painted version yet, so no fake water to remove: "-")
    run(PY, HERE / "make_hint.py", out / "raw.png", b["x0"], b["y0"], "-", BLOCK, out / "src.png", out / "kind.png")
    run(PY, HERE / "layout.py", b["x0"], b["y0"], BLOCK, BLOCK, out / "layout.png")
    print("inputs ready in", out)


def finished(st, version=None):
    return st["done"] if not version else st.setdefault("done_v", {}).setdefault(version, {})


def known(bid, version=None):
    st, b = get(bid)
    out = CITY / bid
    out.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (BLOCK, BLOCK), tuple(int(v) for v in BG))
    keep = Image.new("L", (BLOCK, BLOCK), 0)
    n = 0
    for oid, path in finished(st, version).items():
        if oid == bid:
            continue
        o = next(x for x in st["blocks"] if x["id"] == oid)
        dx, dy = o["x0"] - b["x0"], o["y0"] - b["y0"]
        if abs(dx) >= BLOCK or abs(dy) >= BLOCK:
            continue
        im = Image.open(path).convert("RGB").resize((BLOCK, BLOCK), Image.LANCZOS)  # model scale -> render px
        canvas.paste(im, (dx, dy))
        keep.paste(255, (max(dx, 0), max(dy, 0), min(dx + BLOCK, BLOCK), min(dy + BLOCK, BLOCK)))
        n += 1
    if not n:
        print(bid, "has no finished neighbours: paint it from scratch")
        return
    sfx = f"_{version}" if version else ""
    canvas.save(out / f"known{sfx}.png")
    keep.save(out / f"keep{sfx}.png")
    print(f"{bid}: {n} finished neighbour(s), {np.asarray(keep).mean() / 255:.0%} of the block is held")


def done(bid, canvas, version=None):
    st = load()
    p = Path(canvas).resolve()
    assert p.exists(), p
    finished(st, version)[bid] = str(p)
    save(st)
    print(bid, version or "day", "registered as finished:", p)


def patches(version):
    st = load()
    out = [{"file": path, "x0": b["x0"], "y0": b["y0"], "w": b["w"], "h": b["h"]}
           for b in st["blocks"] for oid, path in finished(st, version).items() if oid == b["id"]]
    dest = CITY / f"patches_{version}.json"
    dest.write_text(json.dumps(out, indent=1))
    print(dest, len(out), "blocks")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    opt = lambda i: sys.argv[i] if len(sys.argv) > i else None  # noqa: E731
    {"plan": lambda: plan(), "prepare": lambda: prepare(sys.argv[2]), "known": lambda: known(sys.argv[2], opt(3)),
     "done": lambda: done(sys.argv[2], sys.argv[3], opt(4)), "patches": lambda: patches(sys.argv[2])}[cmd]()
