"""Runs on the GPU pod: NYC's trained style on our captures, using its prompt and settings."""
import glob
import json
import os
import time
import torch
from diffusers import QwenImageEditPipeline
from PIL import Image

PROMPT = ("Fill in the outlined section with the missing pixels corresponding to the <isometric nyc pixel art> style, "
          "removing the border and exactly following the shape/style/structure of the surrounding image (if present).")
t0 = time.time()
pipe = QwenImageEditPipeline.from_pretrained("Qwen/Qwen-Image-Edit", torch_dtype=torch.bfloat16)
before = sum(1 for _ in pipe.transformer.named_parameters())
# Unlike the upstream server, a failed style load must stop the test rather than draw without it.
pipe.load_lora_weights("/workspace/lora", weight_name="model.safetensors", adapter_name="isometric")
pipe.set_adapters(["isometric"], adapter_weights=[1.0])
after = sum(1 for _ in pipe.transformer.named_parameters())
assert after > before, "style weights did not attach"
pipe.to("cuda")
print(f"loaded in {time.time() - t0:.0f}s; lora params {after - before}", flush=True)
os.makedirs("/workspace/out", exist_ok=True)
times = {}
for path in sorted(glob.glob("/workspace/in/*.png")):
    name = os.path.basename(path)
    t = time.time()
    with torch.inference_mode():
        out = pipe(prompt=PROMPT, negative_prompt=" ", true_cfg_scale=2.0, image=Image.open(path).convert("RGB"),
                   num_inference_steps=14, guidance_scale=3.0, generator=torch.manual_seed(1234)).images[0]
    out.save(f"/workspace/out/{name}")
    times[name] = round(time.time() - t, 1)
    print(name, times[name], "s", out.size, flush=True)
print("peak gb", round(torch.cuda.max_memory_allocated() / 1e9, 1))
json.dump(times, open("/workspace/out/times.json", "w"))
print("DONE", flush=True)
