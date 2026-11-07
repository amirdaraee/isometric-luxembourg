"""On the pod, after training: run the newest checkpoint on held-out city views."""
import glob
import os
import time
import torch
from diffusers import QwenImageEditPipeline
from PIL import Image

PROMPT = open("/workspace/data/00_a.txt").read().strip()
ckpts = sorted(glob.glob("/workspace/output/luxembourg-ink-v1/*.safetensors"), key=os.path.getmtime)
assert ckpts, "no checkpoint found"
ck = ckpts[-1]
print("checkpoint", os.path.basename(ck), flush=True)
pipe = QwenImageEditPipeline.from_pretrained("Qwen/Qwen-Image-Edit", torch_dtype=torch.bfloat16)
before = sum(1 for _ in pipe.transformer.named_parameters())
pipe.load_lora_weights(os.path.dirname(ck), weight_name=os.path.basename(ck), adapter_name="lux")
assert sum(1 for _ in pipe.transformer.named_parameters()) > before, "style weights did not attach"
pipe.to("cuda")
os.makedirs("/workspace/output/city_check", exist_ok=True)
for p in sorted(glob.glob("/workspace/heldout_city/*.png")):
    t = time.time()
    with torch.inference_mode():
        out = pipe(prompt=PROMPT, negative_prompt=" ", true_cfg_scale=2.0, image=Image.open(p).convert("RGB"),
                   num_inference_steps=25, generator=torch.manual_seed(1867)).images[0]
    out.save("/workspace/output/city_check/" + os.path.basename(p))
    print(os.path.basename(p), f"{time.time() - t:.0f}s", flush=True)
print("CITY CHECK DONE", flush=True)
