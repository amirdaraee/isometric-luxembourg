"""On the pod: paint a render region cell by cell with the trained style, NYC-style.

The region (src.png, render pixels) is split into 600 px cells; each generation covers a 2x2-cell window
(1200 src px -> 1024 model px, the training scale). Already painted cells are pasted in as context and the
cells still to paint keep the render, outlined in red, exactly like the omni training inputs. Windows go in
raster order, so the new part is always a rectangle: full, right half, bottom half or bottom-right quadrant.

Writes /workspace/live/{canvas.jpg,last_in.jpg,last_out.jpg,status.json} after every generation.
Usage: tiler.py <lora file> [steps] [src px per cell, default 600 = 300 m per window; 450 = finer detail]
"""
import json
import os
import sys
import time
import numpy as np
import torch
from diffusers import QwenImageEditPlusPipeline
from PIL import Image, ImageDraw
from paint_util import drift_correct, context_mask, paste_soft

CELL = 512
SRC_CELL = int(sys.argv[3]) if len(sys.argv) > 3 else 600
BG = np.array((16, 24, 40))
LIVE = os.environ.get("LIVE", "/workspace/live")
os.makedirs(LIVE, exist_ok=True)
lora = sys.argv[1]
steps = int(sys.argv[2]) if len(sys.argv) > 2 else 25
PROMPT = os.environ.get("PROMPT") or open("/workspace/prompt.txt").read().strip()

src = Image.open(os.environ.get("SRC", "/workspace/src.png")).convert("RGB")
NC, NR = src.width // SRC_CELL, src.height // SRC_CELL
render = src.resize((NC * CELL, NR * CELL), Image.LANCZOS)
# Optional second input (style v2): the layout map of the same region, aligned with src.
LAY = os.environ.get("LAYOUT")
layout = Image.open(LAY).convert("RGB").resize((NC * CELL, NR * CELL), Image.NEAREST) if LAY else None
canvas = render.copy()
painted = np.zeros((NR, NC), bool)
rarr = np.asarray(render.resize((NC * 16, NR * 16)), np.int16)
empty = np.zeros((NR, NC), bool)
for r in range(NR):
    for c in range(NC):
        blk = rarr[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
        empty[r, c] = (np.abs(blk - BG).sum(axis=2) < 6).mean() > 0.97
for r, c in zip(*np.nonzero(empty)):
    canvas.paste(tuple(int(v) for v in BG), (c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL))
    painted[r, c] = True

windows = [(i, j) for j in range(NR - 1) for i in range(NC - 1)]
todo = [w for w in windows if not painted[w[1]:w[1] + 2, w[0]:w[0] + 2].all()]
status = {"total": len(todo), "done": 0, "cells": [NC, NR], "started": time.time(), "per_gen_s": None,
          "state": "loading model", "lora": os.path.basename(lora), "steps": steps}


def save_status(**kw):
    status.update(kw)
    with open(LIVE + "/status.tmp", "w") as f:
        json.dump(status, f)
    os.replace(LIVE + "/status.tmp", LIVE + "/status.json")


def save_canvas():
    im = canvas if canvas.width <= 4096 else canvas.resize((4096, round(canvas.height * 4096 / canvas.width)))
    im.save(LIVE + "/canvas.tmp.jpg", quality=85)
    os.replace(LIVE + "/canvas.tmp.jpg", LIVE + "/canvas.jpg")


save_status(); save_canvas()
pipe = QwenImageEditPlusPipeline.from_pretrained("Qwen/Qwen-Image-Edit-2511", torch_dtype=torch.bfloat16).to("cuda")
pipe.load_lora_weights(os.path.dirname(lora), weight_name=os.path.basename(lora), adapter_name="lux")
assert "lux" in pipe.transformer.peft_config, "style weights did not attach"
save_status(state="painting", started=time.time())

drifts = []
for n, (i, j) in enumerate(todo):
    sub = painted[j:j + 2, i:i + 2]
    new = [(r, c) for r in range(2) for c in range(2) if not sub[r, c]]
    rs, cs = [r for r, _ in new], [c for _, c in new]
    box = (min(cs) * CELL, min(rs) * CELL, (max(cs) + 1) * CELL, (max(rs) + 1) * CELL)
    assert len(new) == (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1), "new region is not a rectangle"
    x0, y0 = i * CELL, j * CELL
    inp = canvas.crop((x0, y0, x0 + 2 * CELL, y0 + 2 * CELL))
    inp.paste(render.crop((x0 + box[0], y0 + box[1], x0 + box[2], y0 + box[3])), box[:2])
    d = ImageDraw.Draw(inp)
    for k in range(2):
        d.rectangle((box[0] + k, box[1] + k, box[2] - 1 - k, box[3] - 1 - k), outline=(255, 0, 0))
    t = time.time()
    with torch.inference_mode():
        images = [inp] + ([layout.crop((x0, y0, x0 + 2 * CELL, y0 + 2 * CELL))] if layout is not None else [])
        out = pipe(prompt=PROMPT, negative_prompt=" ", true_cfg_scale=3.0, image=images, num_inference_steps=steps,
                   generator=torch.manual_seed(1867 + n), height=1024, width=1024).images[0].convert("RGB")
    # Painted context in this window = cells already painted (not the new box).
    ctxpx = np.zeros((1024, 1024), bool)
    for r in range(2):
        for c in range(2):
            if sub[r, c]:
                ctxpx[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] = True
    out, drift0, drift1 = drift_correct(inp, out, box, context_mask(box, ctxpx))
    sides = ("l" if box[0] > 0 else "") + ("t" if box[1] > 0 else "")
    paste_soft(canvas, out, box, x0, y0, sides)
    drifts.append({"window": [i, j], "drift": drift0, "after": drift1})
    for r, c in new:
        painted[j + r, i + c] = True
    inp.save(LIVE + "/last_in.jpg", quality=85)
    out.save(LIVE + "/last_out.jpg", quality=85)
    save_canvas()
    el = time.time() - status["started"]
    save_status(done=n + 1, per_gen_s=round(el / (n + 1), 1), window=[i, j], last_gen_s=round(time.time() - t, 1),
                last_drift=drift0, seams_flagged=sum(1 for d in drifts if (d["drift"] or 0) > 4))
    json.dump(drifts, open(LIVE + "/drift.json", "w"))
    print(f"{n + 1}/{len(todo)} window {i},{j} new {len(new)} cells {time.time() - t:.0f}s", flush=True)

canvas.save(LIVE + "/canvas_full.png")
save_status(state="done")
print("TILES DONE", flush=True)
