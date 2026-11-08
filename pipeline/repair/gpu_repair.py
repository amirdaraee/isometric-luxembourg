"""Method (b) of PLAN_NEXT item 4: repaint spots with the painter's own patch repair on Modal (mdpaint.py
--known/--keep), at the day settings (ink LoRA, Lightning 8 steps), on a crop of a block.

  gpu_repair.py <block> <x0,y0,w,h map px> --mask mask.png --job NAME --max-hours H [--band 32] [--seed N]
                [--base canvas.png]

Inputs written to data/work/repair/<block>/<job>/ and uploaded to the iso-lux volume:
  src.png     the painter's input (the block's src, or the showcase hint for b00) for the crop, with every spot
              emptied again (a wide median, as make_hint.py does for roads), so the painter sees bare ground
  layout.png  the layout map for the crop
  known.png   the current canvas for the crop (output scale), keep.png white everywhere except the spots
The result is pasted into a copy of the block's day canvas (or --base): data/work/repair/<block>/<job>.png.
Spending: the job's cap (max hours x price) is printed before it starts; the time actually used is logged to
data/work/city/modal_spend.json with its cost at the H200 price, and the run refuses to start if the logged
total for the tag would pass --budget.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
CITY = WORK / "city"
OUT = WORK / "repair"
MAIN = ROOT if (ROOT / "pipeline/.venv").exists() else (ROOT / "data").resolve().parent   # a worktree uses the main checkout's venv
MODAL = str(MAIN / "pipeline/.venv/bin/modal")
SPEND = CITY / "modal_spend.json"
PRICE = 4.54   # H200, $/h (modal_paint.py)
LIGHTNING = "/vol/loras/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors"
Image.MAX_IMAGE_PIXELS = None


def spent(tag):
    return sum(e["usd"] for e in (json.loads(SPEND.read_text()) if SPEND.exists() else []) if e["tag"] == tag)


def log_spend(tag, job, seconds, note=""):
    log = json.loads(SPEND.read_text()) if SPEND.exists() else []
    usd = round(seconds / 3600 * PRICE, 3)
    log.append({"tag": tag, "job": job, "gpu": "H200", "seconds": round(seconds), "usd": usd,
                "note": note or "wall time of the modal run x the H200 price (an upper bound: includes start-up)",
                "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    SPEND.write_text(json.dumps(log, indent=1))
    return usd


def sh(*cmd):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.call([str(c) for c in cmd], cwd=ROOT)


def inputs(bid):
    """The painter's day inputs for a block at render scale (6000 px)."""
    d = CITY / bid
    if (d / "src.png").exists():
        return d / "src.png", d / "layout.png"
    showcase = Path("/Users/amirdaraee/00/projects/isometric-luxembourg/pipeline/gpu_train/tiles")
    for base in (ROOT / "pipeline/gpu_train/tiles", showcase):
        if (base / "src_showcase_hint.png").exists():
            return base / "src_showcase_hint.png", base / "layout_showcase.png"
    raise SystemExit(f"no painter inputs for {bid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("block")
    ap.add_argument("box")
    ap.add_argument("--mask", required=True, help="spots, canvas scale, white = repaint")
    ap.add_argument("--job", required=True)
    ap.add_argument("--max-hours", type=float, required=True)
    ap.add_argument("--band", type=int, default=32)
    ap.add_argument("--seed", type=int, default=1867)
    ap.add_argument("--base", help="canvas to paste into (default: the block's day canvas)")
    ap.add_argument("--tag", default="item4-cars")
    ap.add_argument("--budget", type=float, default=16.0, help="USD cap over every run logged with this tag")
    a = ap.parse_args()
    st = json.loads((CITY / "blocks.json").read_text())
    b = next(x for x in st["blocks"] if x["id"] == a.block)
    x0, y0, w, h = map(int, a.box.split(","))
    rx0, ry0 = x0 - b["x0"], y0 - b["y0"]                      # render px in the block
    cap = a.max_hours * PRICE
    if spent(a.tag) + cap > a.budget:
        sys.exit(f"budget: ${spent(a.tag):.2f} logged for {a.tag}; this job's cap ${cap:.2f} would pass ${a.budget:.2f}")
    canvas = Image.open(a.base or st["done"][a.block]).convert("RGB")
    k = canvas.width / b["w"]
    cbox = tuple(int(round(v * k)) for v in (rx0, ry0, rx0 + w, ry0 + h))
    d = OUT / a.block / a.job
    d.mkdir(parents=True, exist_ok=True)
    src_p, lay_p = inputs(a.block)
    src = np.asarray(Image.open(src_p).convert("RGB").crop((rx0, ry0, rx0 + w, ry0 + h))).copy()
    m_c = np.asarray(Image.open(a.mask).convert("L").crop(cbox)) > 0
    m_r = cv2.resize(m_c.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
    m_r = cv2.dilate(m_r.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    med = cv2.medianBlur(src, 31)
    src[m_r] = med[m_r]
    Image.fromarray(src).save(d / "src.png")
    Image.open(lay_p).convert("RGB").crop((rx0, ry0, rx0 + w, ry0 + h)).save(d / "layout.png")
    known = canvas.crop(cbox)
    known.save(d / "known.png")
    Image.fromarray(np.where(m_c, 0, 255).astype(np.uint8)).save(d / "keep.png")
    if not m_c.any():
        sys.exit("no spots in the box")
    print(f"crop {w}x{h} map px, canvas {known.size}, spots {m_c.mean() * 100:.1f}% of it; cap ${cap:.2f}")
    remote = f"inputs/repair/{a.job}"
    for f in ("src", "layout", "known", "keep"):
        if sh(MODAL, "volume", "put", "-f", "iso-lux", d / f"{f}.png", f"{remote}/{f}.png"):
            sys.exit("upload failed")
    extra = (f"--known /vol/{remote}/known.png --keep /vol/{remote}/keep.png --band {a.band} --seed {a.seed} "
             f"--extra-lora {LIGHTNING} --mu 1.0986")
    t0 = time.time()
    rc = sh(MODAL, "run", "pipeline/gpu_train/modal_paint.py", "--job", a.job, "--src", f"{remote}/src.png",
            "--layout", f"{remote}/layout.png", "--lora", "loras/luxembourg-ink-v2.safetensors", "--steps", "8",
            "--cfg", "1", "--gpu", "H200", "--max-hours", str(a.max_hours), "--extra", extra)
    usd = log_spend(a.tag, a.job, time.time() - t0)
    print(f"logged ${usd:.3f}; {a.tag} total ${spent(a.tag):.3f}")
    res = d / "result.png"
    sh(MODAL, "volume", "get", "--force", "iso-lux", f"md/{a.job}/canvas_full.png", res)
    if rc != 0 or not res.exists():
        sys.exit(f"no result (rc={rc})")
    r = Image.open(res).convert("RGB").resize(known.size, Image.LANCZOS)
    full = canvas.copy()
    full.paste(r, cbox[:2])
    dest = OUT / a.block / f"{a.job}.png"
    full.save(dest)
    print("->", dest)


if __name__ == "__main__":
    main()
