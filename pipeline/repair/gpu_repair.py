"""Method (b) of PLAN_NEXT item 4: repaint spots with the painter's own patch repair (mdpaint.py --known/--keep),
at the day settings (ink LoRA, Lightning 8 steps), on a crop of a block (or the whole block), on Modal or on a
RunPod pod that is already up (--backend runpod, see gpu_train/backend.py).

  gpu_repair.py <block> <x0,y0,w,h map px> --mask mask.png --job NAME --max-hours H [--band 32] [--seed N]
                [--base canvas.png] [--backend modal|runpod]
  # the lift (PLAN_NEXT item 6): the painter's input drawn by lift_model.py instead of the block's render
  gpu_repair.py b00 8560,4720,1200,1200 --mask data/work/lift/mask_b00.png --src-override data/work/lift/src.png \\
                --layout-override data/work/lift/layout.png --band 48 --job lift_day_s1 ...
  # a painted version of a repaired spot: the light LoRA turns the repaired day crop into the version, holding the
  # version's own pixels outside the mask (15 steps, CFG 3, prompts/<version>.txt, 1:1 scale)
  gpu_repair.py b00 8560,4720,1200,1200 --mask ... --version night --day data/work/repair/b00/lift_day_s1.png ...

Inputs written to data/work/repair/<block>/<job>/ and uploaded:
  src.png     day: the painter's input (the block's src, or the showcase hint for b00) for the crop, with every spot
              emptied again (a wide median, as make_hint.py does for roads), so the painter sees bare ground;
              or --src-override as it is. Version: the repaired day canvas crop (output scale).
  layout.png  day only: the layout map for the crop (or --layout-override)
  known.png   the current canvas for the crop (output scale), keep.png white everywhere except the spots
The result is pasted into a copy of the block's canvas (day, or the version's, or --base):
data/work/repair/<block>/<job>.png.
Spending: the job's cap (max hours x price) is printed before it starts; the time actually used is logged to the
backend's spend file (data/work/city/modal_spend.json or runpod_spend.json), and the run refuses to start if the
logged total for the tag would pass --budget.
"""
import argparse
import json
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
sys.path.insert(0, str(ROOT / "pipeline" / "gpu_train"))
from backend import LIGHTNING, backend, spend_log, spent  # noqa: E402
Image.MAX_IMAGE_PIXELS = None


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
    ap.add_argument("--base", help="canvas to paste into (default: the block's day or version canvas)")
    ap.add_argument("--src-override", help="the painter's input for the crop (render scale), used as it is")
    ap.add_argument("--layout-override", help="the layout map for the crop (render scale)")
    ap.add_argument("--version", help="repaint a version (night, golden, ...) from --day with the light LoRA")
    ap.add_argument("--day", help="with --version: the repaired day canvas of the block (canvas scale)")
    ap.add_argument("--init-from", help="start from this canvas (block canvas scale), e.g. the free fill of every spot "
                    "(repair_cars.py free --all), instead of pure noise: the painter re-textures it")
    ap.add_argument("--strength", type=float, default=0.5, help="with --init-from: noise level to start at")
    ap.add_argument("--no-clean", action="store_true", help="day: leave the spots in the painter's input as rendered")
    ap.add_argument("--tag", default="item4-cars")
    ap.add_argument("--budget", type=float, default=16.0, help="USD cap over every run logged with this tag")
    ap.add_argument("--backend", default="modal", choices=["modal", "runpod"])
    a = ap.parse_args()
    be = backend(a.backend)
    st = json.loads((CITY / "blocks.json").read_text())
    b = next(x for x in st["blocks"] if x["id"] == a.block)
    x0, y0, w, h = map(int, a.box.split(","))
    rx0, ry0 = x0 - b["x0"], y0 - b["y0"]                      # render px in the block
    cap = a.max_hours * be.price
    if spent(be, a.tag) + cap > a.budget:
        sys.exit(f"budget: ${spent(be, a.tag):.2f} logged for {a.tag}; this job's cap ${cap:.2f} would pass ${a.budget:.2f}")
    V = a.version
    canvas = Image.open(a.base or (st["done_v"][V][a.block] if V else st["done"][a.block])).convert("RGB")
    k = canvas.width / b["w"]
    cbox = tuple(int(round(v * k)) for v in (rx0, ry0, rx0 + w, ry0 + h))
    d = OUT / a.block / a.job
    d.mkdir(parents=True, exist_ok=True)
    m_c = np.asarray(Image.open(a.mask).convert("L").crop(cbox)) > 0
    if not m_c.any():
        sys.exit("no spots in the box")
    if V:
        Image.open(a.day).convert("RGB").crop(cbox).save(d / "src.png")
    elif a.src_override:
        Image.open(a.src_override).convert("RGB").resize((w, h), Image.LANCZOS).save(d / "src.png")
    else:
        src_p, _ = inputs(a.block)
        src = np.asarray(Image.open(src_p).convert("RGB").crop((rx0, ry0, rx0 + w, ry0 + h))).copy()
        m_r = cv2.resize(m_c.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        m_r = cv2.dilate(m_r.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        med = cv2.medianBlur(src, 31)
        if not a.no_clean:
            src[m_r] = med[m_r]
        Image.fromarray(src).save(d / "src.png")
    if not V:
        lay = Image.open(a.layout_override) if a.layout_override else \
            Image.open(inputs(a.block)[1]).crop((rx0, ry0, rx0 + w, ry0 + h))
        lay.convert("RGB").resize((w, h), Image.NEAREST).save(d / "layout.png")
    known = canvas.crop(cbox)
    known.save(d / "known.png")
    Image.fromarray(np.where(m_c, 0, 255).astype(np.uint8)).save(d / "keep.png")
    print(f"crop {w}x{h} map px, canvas {known.size}, spots {m_c.mean() * 100:.1f}% of it; cap ${cap:.2f} ({be.name})")
    remote = f"inputs/repair/{a.job}"
    files = ["src", "known", "keep"] if V else ["src", "layout", "known", "keep"]
    if a.init_from:
        Image.open(a.init_from).convert("RGB").crop(cbox).save(d / "init.png")
        files.append("init")
    for f in files:
        if be.put(str(d / f"{f}.png"), f"{remote}/{f}.png"):
            sys.exit("upload failed")
    extra = f"--known {be.abs(remote)}/known.png --keep {be.abs(remote)}/keep.png --band {a.band} --seed {a.seed}"
    if a.init_from:
        extra += f" --init {be.abs(remote)}/init.png --strength {a.strength}"
    if V:
        run = dict(src=f"{remote}/src.png", lora="loras/luxembourg-light-v1.safetensors", steps=15, cfg=3.0,
                   src_cell=512, prompt_file=f"pipeline/gpu_train/prompts/{V}.txt")
    else:
        extra += f" --extra-lora {be.abs(LIGHTNING)} --mu 1.0986"
        run = dict(src=f"{remote}/src.png", layout=f"{remote}/layout.png", lora="loras/luxembourg-ink-v2.safetensors",
                   steps=8, cfg=1.0)
    t0 = time.time()
    rc = be.run(a.job, **run, gpu="H200", max_hours=a.max_hours, extra=extra)
    usd = spend_log(be, a.tag, a.job, time.time() - t0)
    print(f"logged ${usd:.3f}; {a.tag} total ${spent(be, a.tag):.3f}")
    res = d / "result.png"
    be.get(f"md/{a.job}/canvas_full.png", str(res))
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
