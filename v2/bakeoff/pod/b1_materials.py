"""On the pod (job B1): the material library, text to image with Qwen-Image, 1024 x 1024, n candidates each.
The prompts come from v2/bakeoff/prompts.py (copied with this folder); the owner picks one per material."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, "/workspace")
from v2.bakeoff.prompts import COMMON_NEGATIVE, MATERIAL_BRIEF, MATERIALS  # noqa: E402
from v2.layers.common import pal  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--steps", type=int, default=30)
a = ap.parse_args()

import torch  # noqa: E402
from diffusers import DiffusionPipeline  # noqa: E402

pipe = DiffusionPipeline.from_pretrained("Qwen/Qwen-Image", torch_dtype=torch.bfloat16).to("cuda")
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
for name, (what, key, _size) in MATERIALS.items():
    rgb = tuple(int(x) for x in pal(*key.split(".")))
    prompt = MATERIAL_BRIEF.format(what=what, rgb=rgb)
    for k in range(a.n):
        p = out / f"{name}_{k}.png"
        if p.exists():
            continue
        g = torch.Generator("cuda").manual_seed(1867 + k)
        img = pipe(prompt=prompt, negative_prompt=COMMON_NEGATIVE, width=1024, height=1024, num_inference_steps=a.steps,
                   true_cfg_scale=4.0, generator=g).images[0]
        img.save(p)
        print(name, k, flush=True)
