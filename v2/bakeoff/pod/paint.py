"""On the pod: paint every input window of a job with Qwen-Image-Edit-2511 + the 8-step Lightning LoRA + a style
LoRA, the model loaded once. One window = one 1024 px model pass at one map pixel per model pixel (0.125 m).

The step is v1's painter's (pipeline/gpu_train/tiles/mdpaint.py: the same conditioning, schedule and Euler step),
for one window: control image 1 is the unlit render outlined in red all round (2 px, as every full-view training
example of the style LoRA), control image 2 the layout map (black outlines, dark windows, on white).

    paint.py --inputs DIR --out DIR --prompt-file F --lora STYLE.safetensors --lightning L.safetensors
             [--seeds 1867,1868] [--seed-step 0] [--steps 8]
Inputs: DIR/<name>.unlit.png and DIR/<name>.layout.png. Output: OUT/<name>.png (one seed) or OUT/<name>_<k>.png.
With --seed-step N the i-th input (in name order) is painted with seeds + i x N, so no two inputs share a seed.
Existing outputs are skipped (resume). Prints the seconds per painting.
"""
import argparse
import glob
import json
import os
import time

import numpy as np
import torch
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("--inputs", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--prompt-file", required=True)
ap.add_argument("--lora", required=True)
ap.add_argument("--lightning", required=True)
ap.add_argument("--seeds", default="1867")
ap.add_argument("--seed-step", type=int, default=0)
ap.add_argument("--steps", type=int, default=8)
a = ap.parse_args()
WIN = 1024
PROMPT = open(a.prompt_file).read().strip()
seeds = [int(s) for s in a.seeds.split(",")]
names = sorted(os.path.basename(p)[: -len(".unlit.png")] for p in glob.glob(os.path.join(a.inputs, "*.unlit.png")))
os.makedirs(a.out, exist_ok=True)


def out_path(name, k):
    return os.path.join(a.out, f"{name}.png" if len(seeds) == 1 else f"{name}_{k}.png")


todo = [(n, k) for k in range(len(seeds)) for n in names if not os.path.exists(out_path(n, k))]
print(f"{len(names)} inputs x {len(seeds)} seeds, {len(todo)} to paint; lora {os.path.basename(a.lora)}", flush=True)
if not todo:
    raise SystemExit(0)

from diffusers import QwenImageEditPlusPipeline  # noqa: E402
from diffusers.pipelines.qwenimage.pipeline_qwenimage_edit_plus import CONDITION_IMAGE_SIZE, calculate_dimensions  # noqa: E402

dev = "cuda"
t0 = time.time()
pipe = QwenImageEditPlusPipeline.from_pretrained("Qwen/Qwen-Image-Edit-2511", torch_dtype=torch.bfloat16).to(dev)
pipe.load_lora_weights(os.path.dirname(a.lora), weight_name=os.path.basename(a.lora), adapter_name="lux")
pipe.load_lora_weights(os.path.dirname(a.lightning), weight_name=os.path.basename(a.lightning), adapter_name="extra")
pipe.set_adapters(["lux", "extra"], [1.0, 1.0])
assert "lux" in pipe.transformer.peft_config, "style weights did not attach"
print(f"model loaded in {time.time() - t0:.0f} s", flush=True)
C = pipe.transformer.config.in_channels // 4
ts_ = WIN // 8
# Lightning: 8 steps, cfg 1, a fixed schedule shift of ln 3 (as v1 painted the city)
pipe.scheduler.set_timesteps(sigmas=np.linspace(1.0, 1 / a.steps, a.steps), device=dev, mu=1.0986)
sigmas = [float(s) for s in pipe.scheduler.sigmas]
timesteps = pipe.scheduler.timesteps
assert len(sigmas) == a.steps + 1 and sigmas[-1] == 0.0, sigmas
cw, ch = calculate_dimensions(CONDITION_IMAGE_SIZE, 1.0)
lat_mean = torch.tensor(pipe.vae.config.latents_mean).view(1, C, 1, 1, 1)
lat_std = torch.tensor(pipe.vae.config.latents_std).view(1, C, 1, 1, 1)


def paint(name, seed):
    win = Image.open(os.path.join(a.inputs, f"{name}.unlit.png")).convert("RGB")
    lay = Image.open(os.path.join(a.inputs, f"{name}.layout.png")).convert("RGB")
    assert win.size == (WIN, WIN) and lay.size == (WIN, WIN), (name, win.size)
    d = ImageDraw.Draw(win)
    for k in range(2):
        d.rectangle((k, k, WIN - 1 - k, WIN - 1 - k), outline=(255, 0, 0))
    imgs = [win, lay]
    c_imgs = [pipe.image_processor.resize(im, ch, cw) for im in imgs]
    v_imgs = [pipe.image_processor.preprocess(im, WIN, WIN).unsqueeze(2) for im in imgs]
    with torch.inference_mode():
        pe, pm = pipe.encode_prompt(image=c_imgs, prompt=PROMPT, device=dev, max_sequence_length=512)
        _, il = pipe.prepare_latents(v_imgs, 1, C, WIN, WIN, pe.dtype, dev, None, latents=torch.zeros(1))
        shapes = [[(1, ts_ // 2, ts_ // 2)] * 3]
        x = torch.randn((C, ts_, ts_), generator=torch.Generator().manual_seed(seed))
        for i in range(a.steps):
            lat = pipe._pack_latents(x[None].to(dev, torch.bfloat16), 1, C, ts_, ts_)
            inp = torch.cat([lat, il], dim=1)
            t = (timesteps[i] / 1000).expand(1).to(lat.dtype)
            with pipe.transformer.cache_context("cond"):
                v = pipe.transformer(hidden_states=inp, timestep=t, guidance=None, encoder_hidden_states_mask=pm,
                                     encoder_hidden_states=pe, img_shapes=shapes, attention_kwargs={},
                                     return_dict=False)[0][:, : lat.size(1)]
            v = pipe._unpack_latents(v, WIN, WIN, 8)[0, :, 0].float().cpu()
            x = x + (sigmas[i + 1] - sigmas[i]) * v
        z = (x[None, :, None] * lat_std + lat_mean).to(dev, pipe.vae.dtype)
        im = pipe.vae.decode(z, return_dict=False)[0][0, :, 0]
    arr = ((im.float().cpu() + 1) / 2).clamp(0, 1).permute(1, 2, 0).numpy()
    return Image.fromarray((arr * 255).round().astype(np.uint8))


t1 = time.time()
for j, (name, k) in enumerate(todo):
    p = out_path(name, k)
    paint(name, seeds[k] + names.index(name) * a.seed_step).save(p + ".tmp.png")
    os.replace(p + ".tmp.png", p)
    per = (time.time() - t1) / (j + 1)
    print(f"{j + 1}/{len(todo)} {os.path.basename(p)} {per:.1f} s per painting", flush=True)
    json.dump({"done": j + 1, "of": len(todo), "s_per_painting": round(per, 2), "load_s": round(t1 - t0)},
              open(os.path.join(a.out, "timing.json"), "w"))
print("PAINT FINISHED", flush=True)
