"""On the pod (job B1): the material library, text to image with Qwen-Image, 1024 x 1024.

    b1_materials.py --spec materials.json --out DIR [--steps 30]
materials.json (written by the laptop from v2/bakeoff/prompts.py): {"negative": str, "n": 3, "seed": 1867,
"materials": {name: prompt}}. Candidate 0 of every material is made first, then candidate 1, then 2, so a run cut
short by the job's time cap still leaves a whole library. Existing images are skipped (resume).
"""
import argparse
import json
import os
import time

import torch
from diffusers import DiffusionPipeline

ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--steps", type=int, default=30)
a = ap.parse_args()
spec = json.load(open(a.spec))
os.makedirs(a.out, exist_ok=True)
todo = [(k, n) for k in range(spec["n"]) for n in spec["materials"] if not os.path.exists(os.path.join(a.out, f"{n}_{k}.png"))]
print(f"{len(todo)} images to make", flush=True)
if not todo:
    raise SystemExit(0)
t0 = time.time()
pipe = DiffusionPipeline.from_pretrained("Qwen/Qwen-Image", torch_dtype=torch.bfloat16).to("cuda")
print(f"model loaded in {time.time() - t0:.0f} s", flush=True)
t1 = time.time()
for j, (k, name) in enumerate(todo):
    g = torch.Generator("cuda").manual_seed(spec["seed"] + k)
    img = pipe(prompt=spec["materials"][name], negative_prompt=spec["negative"], width=1024, height=1024,
               num_inference_steps=a.steps, true_cfg_scale=4.0, generator=g).images[0]
    p = os.path.join(a.out, f"{name}_{k}.png")
    img.save(p + ".tmp.png")
    os.replace(p + ".tmp.png", p)
    per = (time.time() - t1) / (j + 1)
    print(f"{j + 1}/{len(todo)} {name}_{k} {per:.1f} s per image", flush=True)
    json.dump({"done": j + 1, "of": len(todo), "s_per_image": round(per, 2), "load_s": round(t1 - t0)},
              open(os.path.join(a.out, "timing.json"), "w"))
print("MATERIALS FINISHED", flush=True)
