"""On the pod: run chosen checkpoints over the pilot check views. Output: /workspace/out/<step>/<view>.png"""
import glob
import os
import sys
import time
import torch
from diffusers import QwenImageEditPlusPipeline
from PIL import Image

PROMPT = open("/workspace/prompt.txt").read().strip()
steps = sys.argv[1].split(",")
pipe = QwenImageEditPlusPipeline.from_pretrained("Qwen/Qwen-Image-Edit-2511", torch_dtype=torch.bfloat16).to("cuda")
views = sorted(glob.glob("/workspace/views/*.png"))
for s in steps:
    w = f"luxembourg-ink-2511_{int(s):09d}.safetensors" if s != "final" else "luxembourg-ink-2511.safetensors"
    pipe.load_lora_weights("/workspace/lora", weight_name=w, adapter_name=f"s{s}")
    pipe.set_adapters([f"s{s}"])
    assert f"s{s}" in pipe.transformer.peft_config, "style weights did not attach"
    os.makedirs(f"/workspace/out/{s}", exist_ok=True)
    for p in views:
        t = time.time()
        with torch.inference_mode():
            out = pipe(prompt=PROMPT, negative_prompt=" ", true_cfg_scale=3.0, image=[Image.open(p).convert("RGB")],
                       num_inference_steps=25, generator=torch.manual_seed(1867), height=1024, width=1024).images[0]
        out.save(f"/workspace/out/{s}/{os.path.basename(p)}")
        print(s, os.path.basename(p), f"{time.time() - t:.0f}s", flush=True)
    pipe.delete_adapters([f"s{s}"])
print("CHECK DONE", flush=True)
