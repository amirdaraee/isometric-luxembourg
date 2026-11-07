"""On the pod: repaint chosen cells of an already painted area, each with painted context all around.

For cell (c, r) the model sees a 2x2-cell window centred on it: the painted canvas everywhere, except the
cell itself, which shows the (hinted) render inside a red outline: a centred rectangle infill, as in training.
The new cell is blended back with a soft edge. Live files as in tiler.py.
Usage: repaint.py <lora file> <cells.json> [steps]
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

SRC_CELL, CELL, FEATHER = 600, 512, 24
LIVE = "/workspace/live"
os.makedirs(LIVE, exist_ok=True)
lora, cells = sys.argv[1], json.load(open(sys.argv[2]))
SRC_CELL = int(os.environ.get("SRC_CELL", "600"))
steps = int(sys.argv[3]) if len(sys.argv) > 3 else 25
PROMPT = open("/workspace/prompt.txt").read().strip()

canvas = Image.open("/workspace/canvas.png").convert("RGB")
before = canvas.copy()
src = Image.open("/workspace/src.png").convert("RGB")
render = src.resize(canvas.size, Image.LANCZOS)
LAY = os.environ.get("LAYOUT")
layout = Image.open(LAY).convert("RGB").resize(canvas.size, Image.NEAREST) if LAY else None
W, H = canvas.size
status = {"total": len(cells), "done": 0, "cells": [W // CELL, H // CELL], "started": time.time(), "per_gen_s": None,
          "state": "loading model", "lora": os.path.basename(lora), "steps": steps, "mode": "repaint"}


def save_status(**kw):
    status.update(kw)
    with open(LIVE + "/status.tmp", "w") as f:
        json.dump(status, f)
    os.replace(LIVE + "/status.tmp", LIVE + "/status.json")


def save_canvas():
    im = canvas if canvas.width <= 4096 else canvas.resize((4096, round(canvas.height * 4096 / canvas.width)))
    im.save(LIVE + "/canvas.tmp.jpg", quality=85)
    os.replace(LIVE + "/canvas.tmp.jpg", LIVE + "/canvas.jpg")


# Soft-edged mask for pasting a cell back.
m = np.ones((CELL, CELL), np.float32)
ramp = np.linspace(0, 1, FEATHER, dtype=np.float32)
m[:FEATHER] *= ramp[:, None]; m[-FEATHER:] *= ramp[::-1, None]
m[:, :FEATHER] *= ramp[None]; m[:, -FEATHER:] *= ramp[::-1][None]
MASK = Image.fromarray((m * 255).astype(np.uint8))

save_status(); save_canvas()
pipe = QwenImageEditPlusPipeline.from_pretrained("Qwen/Qwen-Image-Edit-2511", torch_dtype=torch.bfloat16).to("cuda")
pipe.load_lora_weights(os.path.dirname(lora), weight_name=os.path.basename(lora), adapter_name="lux")
assert "lux" in pipe.transformer.peft_config, "style weights did not attach"
save_status(state="painting", started=time.time())

drifts = []
for n, (c, r) in enumerate(cells):
    cx, cy = c * CELL, r * CELL
    x0 = min(max(cx - CELL // 2, 0), W - 2 * CELL)
    y0 = min(max(cy - CELL // 2, 0), H - 2 * CELL)
    bx, by = cx - x0, cy - y0  # the cell inside the window
    inp = canvas.crop((x0, y0, x0 + 2 * CELL, y0 + 2 * CELL))
    inp.paste(render.crop((cx, cy, cx + CELL, cy + CELL)), (bx, by))
    d = ImageDraw.Draw(inp)
    for k in range(2):
        d.rectangle((bx + k, by + k, bx + CELL - 1 - k, by + CELL - 1 - k), outline=(255, 0, 0))
    t = time.time()
    with torch.inference_mode():
        images = [inp] + ([layout.crop((x0, y0, x0 + 2 * CELL, y0 + 2 * CELL))] if layout is not None else [])
        out = pipe(prompt=PROMPT, negative_prompt=" ", true_cfg_scale=3.0, image=images, num_inference_steps=steps,
                   generator=torch.manual_seed(4242 + n), height=1024, width=1024).images[0].convert("RGB")
    box = (bx, by, bx + CELL, by + CELL)
    ctxpx = np.ones((1024, 1024), bool)
    out, drift0, drift1 = drift_correct(inp, out, box, context_mask(box, ctxpx))
    paste_soft(canvas, out, box, x0, y0, "ltrb")
    drifts.append({"cell": [c, r], "drift": drift0, "after": drift1})
    inp.save(LIVE + "/last_in.jpg", quality=85)
    out.save(LIVE + "/last_out.jpg", quality=85)
    save_canvas()
    el = time.time() - status["started"]
    save_status(done=n + 1, per_gen_s=round(el / (n + 1), 1), window=[c, r], last_gen_s=round(time.time() - t, 1),
                last_drift=drift0, seams_flagged=sum(1 for d in drifts if (d["drift"] or 0) > 4))
    json.dump(drifts, open(LIVE + "/drift.json", "w"))
    print(f"{n + 1}/{len(cells)} cell {c},{r} {time.time() - t:.0f}s", flush=True)

canvas.save(LIVE + "/canvas_full.png")
save_status(state="done")
print("TILES DONE", flush=True)
