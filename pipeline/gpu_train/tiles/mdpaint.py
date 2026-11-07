"""On a GPU: paint a whole render region in one pass (overlapping windows, shifted grid), with resume.

Same model, style LoRA, prompt, scale and inputs as tiler.py; only the way windows are combined changes (see
md_core.py). Every window sees its crop of the render outlined in red all round (and the layout map, style v2),
exactly like a full-view training example (about 20% of the style v2 training set).

Usage:
  mdpaint.py --src src.png [--layout layout.png] --lora luxembourg-ink-v2.safetensors --out canvas_full.png
             [--steps 25] [--cfg 3.0] [--src-cell 600] [--state DIR] [--deadline EPOCH]
             [--known painted.png --keep keep_mask.png [--band 64]]     # neighbours / patch repair
             [--init start.png --strength 0.4]                          # light repaint of an existing image
Scale: --src-cell render px become 512 model px (600 = 300 m per 1024 px window, the training scale).
Repair: --known is an image at the output scale; --keep is white where it must stay. Black areas are repainted,
with a --band px free margin that is feathered back at the end.
Exit codes: 0 done, 3 paused at the deadline (run again with the same --state to resume).
Writes LIVE/status.json (LIVE env, default /workspace/live) after every step for the dashboard.
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
from PIL import Image, ImageDraw

from md_core import Plan, blend_tiles, feather, grid, hold_mask, paint

CELL = 512
WIN_PX = 1024
BG = np.array((16, 24, 40))

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True)
ap.add_argument("--layout")
ap.add_argument("--lora", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--steps", type=int, default=25)
ap.add_argument("--cfg", type=float, default=3.0)
ap.add_argument("--src-cell", type=int, default=600)
ap.add_argument("--state", default="/workspace/md_state")
ap.add_argument("--deadline", type=float, default=0, help="epoch seconds; pause (state saved) 10 min before")
ap.add_argument("--known")
ap.add_argument("--keep")
ap.add_argument("--band", type=int, default=64)
ap.add_argument("--seed", type=int, default=1867)
ap.add_argument("--init", help="start from this image instead of pure noise (light repaint); any size, resized")
ap.add_argument("--strength", type=float, default=0.4, help="with --init: noise level to start at (0 = keep, 1 = "
                "repaint from scratch); the first step is the one whose noise level is nearest")
ap.add_argument("--extra-lora", help="optional second LoRA (e.g. Lightning, for fewer steps)")
ap.add_argument("--mu", type=float, help="fixed schedule shift (Lightning: ln 3 = 1.0986, with --cfg 1 --steps 8); "
                "default: the pipeline's dynamic shift for one 1024 px window")
args = ap.parse_args()

LIVE = os.environ.get("LIVE", "/workspace/live")
os.makedirs(LIVE, exist_ok=True)
os.makedirs(args.state, exist_ok=True)
PROMPT = os.environ.get("PROMPT") or open("/workspace/prompt.txt").read().strip()
status = {"state": "loading", "started": time.time(), "steps": args.steps, "step": 0, "mode": "mdpaint"}


def save_status(**kw):
    status.update(kw)
    with open(LIVE + "/status.tmp", "w") as f:
        json.dump(status, f)
    os.replace(LIVE + "/status.tmp", LIVE + "/status.json")


# --- inputs at model scale (multiple of 16 px so latents pack into 2x2 patches)
src = Image.open(args.src).convert("RGB")
k = CELL / args.src_cell
Wpx, Hpx = (max(WIN_PX, round(src.width * k / 16) * 16), max(WIN_PX, round(src.height * k / 16) * 16))
render = src.resize((Wpx, Hpx), Image.LANCZOS)
layout = Image.open(args.layout).convert("RGB").resize((Wpx, Hpx), Image.NEAREST) if args.layout else None
H, W = Hpx // 8, Wpx // 8
save_status(size=[Wpx, Hpx], latent=[W, H])
print(f"canvas {Wpx}x{Hpx} px, latent {W}x{H}", flush=True)

from diffusers import QwenImageEditPlusPipeline  # noqa: E402  (after arg checks: import is slow)
from diffusers.pipelines.qwenimage.pipeline_qwenimage_edit_plus import (  # noqa: E402
    CONDITION_IMAGE_SIZE, calculate_dimensions, calculate_shift)

dev = "cuda"
pipe = QwenImageEditPlusPipeline.from_pretrained("Qwen/Qwen-Image-Edit-2511", torch_dtype=torch.bfloat16).to(dev)
pipe.load_lora_weights(os.path.dirname(args.lora), weight_name=os.path.basename(args.lora), adapter_name="lux")
names = ["lux"]
if args.extra_lora:
    pipe.load_lora_weights(os.path.dirname(args.extra_lora), weight_name=os.path.basename(args.extra_lora),
                           adapter_name="extra")
    names.append("extra")
    pipe.set_adapters(names, [1.0] * len(names))
assert "lux" in pipe.transformer.peft_config, "style weights did not attach"
C = pipe.transformer.config.in_channels // 4
tsize = WIN_PX // 8  # window, latent px

# --- noise schedule, as the pipeline sets it for one 1024 px window
seq = (WIN_PX // 16) ** 2
sc = pipe.scheduler.config
mu = calculate_shift(seq, sc.get("base_image_seq_len", 256), sc.get("max_image_seq_len", 4096),
                     sc.get("base_shift", 0.5), sc.get("max_shift", 1.15))
if args.mu is not None:
    mu = args.mu
pipe.scheduler.set_timesteps(sigmas=np.linspace(1.0, 1 / args.steps, args.steps), device=dev, mu=mu)
sigmas = [float(s) for s in pipe.scheduler.sigmas]
timesteps = pipe.scheduler.timesteps
assert len(sigmas) == args.steps + 1 and sigmas[-1] == 0.0, sigmas

# --- per-window conditioning (prompt embeddings depend on the images, so one set per window), cached
cw, ch = calculate_dimensions(CONDITION_IMAGE_SIZE, 1.0)
cache = {}


def cond(key):
    if key in cache:
        return cache[key]
    y, x = key
    box = (x * 8, y * 8, x * 8 + WIN_PX, y * 8 + WIN_PX)
    win = render.crop(box)
    d = ImageDraw.Draw(win)  # full-view training examples are outlined in red all round (2 px), like tiler.py
    for k in range(2):
        d.rectangle((k, k, WIN_PX - 1 - k, WIN_PX - 1 - k), outline=(255, 0, 0))
    imgs = [win] + ([layout.crop(box)] if layout is not None else [])
    c_imgs = [pipe.image_processor.resize(im, ch, cw) for im in imgs]
    v_imgs = [pipe.image_processor.preprocess(im, WIN_PX, WIN_PX).unsqueeze(2) for im in imgs]
    with torch.inference_mode():
        pe, pm = pipe.encode_prompt(image=c_imgs, prompt=PROMPT, device=dev, max_sequence_length=512)
        ne, nm = pipe.encode_prompt(image=c_imgs, prompt=" ", device=dev, max_sequence_length=512)
        _, il = pipe.prepare_latents(v_imgs, 1, C, WIN_PX, WIN_PX, pe.dtype, dev, None, latents=torch.zeros(1))
    shapes = [[(1, tsize // 2, tsize // 2)] * (1 + len(imgs))]
    cache[key] = (pe, pm, ne, nm, il, shapes)
    return cache[key]


windows_run = {"n": 0, "t": 0.0}


def velocity(key, xw, i):
    t0 = time.time()
    pe, pm, ne, nm, il, shapes = cond(key)
    with torch.inference_mode():
        lat = pipe._pack_latents(xw[None].to(dev, torch.bfloat16), 1, C, tsize, tsize)
        inp = torch.cat([lat, il], dim=1)
        ts = (timesteps[i] / 1000).expand(1).to(lat.dtype)

        def run(e, m, tag):
            with pipe.transformer.cache_context(tag):
                return pipe.transformer(hidden_states=inp, timestep=ts, guidance=None, encoder_hidden_states_mask=m,
                                        encoder_hidden_states=e, img_shapes=shapes, attention_kwargs={},
                                        return_dict=False)[0][:, : lat.size(1)]
        v = run(pe, pm, "cond")
        if args.cfg > 1:
            nv = run(ne, nm, "uncond")
            comb = nv + args.cfg * (v - nv)
            v = comb * (torch.norm(v, dim=-1, keepdim=True) / torch.norm(comb, dim=-1, keepdim=True))
        v = pipe._unpack_latents(v, WIN_PX, WIN_PX, 8)[0, :, 0]
    windows_run["n"] += 1
    windows_run["t"] += time.time() - t0
    return v.float().cpu()


# --- VAE helpers: encode/decode in overlapping 1024 px pieces, blended
lat_mean = torch.tensor(pipe.vae.config.latents_mean).view(1, C, 1, 1, 1)
lat_std = torch.tensor(pipe.vae.config.latents_std).view(1, C, 1, 1, 1)


def encode(img: Image.Image) -> torch.Tensor:
    tiles = []
    for y, x in grid(H, W, tsize, tsize * 3 // 4, False):
        crop = img.crop((x * 8, y * 8, x * 8 + WIN_PX, y * 8 + WIN_PX))
        t = pipe.image_processor.preprocess(crop, WIN_PX, WIN_PX).unsqueeze(2).to(dev, torch.bfloat16)
        with torch.inference_mode():
            z = pipe._encode_vae_image(t, None)[0, :, 0]
        tiles.append((y, x, z.float().cpu()))
    return blend_tiles((C, H, W), tiles, tsize, tsize // 4)


def decode(z: torch.Tensor) -> np.ndarray:
    tiles = []
    for y, x in grid(H, W, tsize, tsize * 3 // 4, False):
        zt = z[:, y:y + tsize, x:x + tsize][None, :, None]
        zt = (zt * lat_std + lat_mean).to(dev, pipe.vae.dtype)
        with torch.inference_mode():
            im = pipe.vae.decode(zt, return_dict=False)[0][0, :, 0]
        tiles.append((y * 8, x * 8, ((im.float().cpu() + 1) / 2).clamp(0, 1)))
    out = blend_tiles((3, Hpx, Wpx), tiles, WIN_PX, WIN_PX // 4)
    return (out.permute(1, 2, 0).numpy() * 255).round().astype(np.uint8)


# --- known pixels (finished neighbours or the area outside a repair)
known = hold = keep_px = known_img = None
# Empty map edge (no 3D data) is held as background, so windows with nothing in them cost nothing.
rarr = np.asarray(render, np.int16)
bg_px = np.abs(rarr - BG).sum(axis=2) < 6
if args.known:
    known_img = Image.open(args.known).convert("RGB").resize((Wpx, Hpx), Image.LANCZOS)
    keep_np = np.asarray(Image.open(args.keep).convert("L").resize((Wpx, Hpx), Image.NEAREST)) > 127
elif bg_px.mean() > 0.01:
    known_img, keep_np = render, np.zeros((Hpx, Wpx), bool)
if known_img is not None:
    ka = np.asarray(known_img).copy()
    ka[bg_px] = BG
    known_img = Image.fromarray(ka)
    keep_px = torch.from_numpy(keep_np | bg_px)
    save_status(state="encoding known pixels")
    known = encode(known_img)
    hold = hold_mask(keep_px, args.band)
    print(f"holding {hold.float().mean() * 100:.0f}% of the canvas", flush=True)

init = None
first = 0
if args.init:
    save_status(state="encoding the start image")
    init = encode(Image.open(args.init).convert("RGB").resize((Wpx, Hpx), Image.LANCZOS))
    first = int(np.argmin([abs(s_ - args.strength) for s_ in sigmas[:-1]]))
    print(f"light repaint: starting at step {first} of {args.steps} (noise {sigmas[first]:.2f})", flush=True)

plan = Plan(H=H, W=W, sigmas=sigmas, size=tsize, stride=tsize * 3 // 4, fade=tsize // 4, seed=args.seed)
state_path = os.path.join(args.state, "state.pt")
save_status(state="painting", started=time.time())


def on_step(i, steps, ran):
    el = time.time() - status["started"]
    per = windows_run["t"] / max(1, windows_run["n"])
    save_status(step=i, windows_last_step=ran, per_window_s=round(per, 2), elapsed_s=round(el))
    print(f"step {i}/{steps}: {ran} windows, {per:.2f} s per window, {el / 60:.1f} min", flush=True)


stop = (lambda: time.time() > args.deadline - 600) if args.deadline else None
z = paint(plan, velocity, channels=C, known=known, hold=hold, state_path=state_path, on_step=on_step, stop=stop,
          init=init, first=first)
if z is None:
    save_status(state="paused")
    print("PAINT PAUSED (deadline): run again with the same --state to resume", flush=True)
    sys.exit(3)

save_status(state="decoding")
out = decode(z)
if args.known:  # put the finished neighbours back, feathered across the free band (background is set below)
    a = feather(torch.from_numpy(keep_np), args.band).numpy()[..., None]
    out = (np.asarray(known_img) * a + out * (1 - a)).round().astype(np.uint8)
out[bg_px] = BG  # outside the 3D data stays background
Image.fromarray(out).save(args.out + ".tmp.png")
os.replace(args.out + ".tmp.png", args.out)
prev = Image.fromarray(out)
prev.thumbnail((4096, 4096))
prev.save(LIVE + "/canvas.jpg", quality=85)
save_status(state="done", out=args.out)
print("PAINT FINISHED", flush=True)
