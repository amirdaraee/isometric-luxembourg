"""The vehicle detector of brief 9 (v1's OWLv2 check, pipeline/repair/find_vehicles.py), run on tiles.

Runs in its own environment, because it needs torch and transformers (the model is google/owlv2-base-patch16-ensemble
from the local Hugging Face cache; nothing is downloaded and nothing is paid for):

    uv run --offline --no-project --with torch --with transformers --with pillow --with numpy \\
        python -I v2/checks/owl_detect.py jobs.json

jobs.json: {"jobs": [{"layer", "path", "tile"}], "queries": [...], "queries_water": [...], "threshold": 0.1,
"box_m": [3, 14], "mpp": 0.125, "out": "owl.json"}. As in v1, each tile (512 px = 64 m) is cut into overlapping
256 px crops enlarged to the model's 960 px (a car is then about 130 px), and a detection counts when its box is
3-14 m long. The water layer is also asked for boats.
"""
import json
import sys
import time

import numpy as np
import torch
from PIL import Image
from transformers import Owlv2ForObjectDetection, Owlv2Processor


def main(path):
    spec = json.load(open(path))
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    name = "google/owlv2-base-patch16-ensemble"
    proc = Owlv2Processor.from_pretrained(name, local_files_only=True)
    model = Owlv2ForObjectDetection.from_pretrained(name, local_files_only=True).to(dev).eval()
    S, crop, overlap = 960, 256, 40
    mean = torch.tensor([0.48145466, 0.4578275, 0.40821073], device=dev).view(1, 3, 1, 1)
    std = torch.tensor([0.26862954, 0.26130258, 0.27577711], device=dev).view(1, 3, 1, 1)
    texts = {}
    for key, qs in (("land", spec["queries"]), ("water", spec["queries"] + spec["queries_water"])):
        texts[key] = (qs, proc.tokenizer(qs, padding="max_length", return_tensors="pt").to(dev))
    post = getattr(proc, "post_process_object_detection", None) or proc.post_process_grounded_object_detection
    t0 = time.time()
    dets, images, maxs = [], 0, 0.0
    lo_m, hi_m = spec["box_m"]
    for job in spec["jobs"]:
        im = np.asarray(Image.open(job["path"]).convert("RGB"))
        H, W = im.shape[:2]
        crops = []
        for y0 in range(0, H - overlap, crop - overlap):
            for x0 in range(0, W - overlap, crop - overlap):
                c = im[y0:y0 + crop, x0:x0 + crop]
                if c.shape[0] < crop or c.shape[1] < crop:
                    c = np.pad(c, ((0, crop - c.shape[0]), (0, crop - c.shape[1]), (0, 0)))
                if (c.sum(-1) == 0).mean() > 0.9:
                    continue                     # nothing of the layer there
                crops.append((x0, y0, c))
        if not crops:
            continue
        qs, text = texts["water" if job["layer"] == "water" else "land"]
        sc = S / crop
        for i in range(0, len(crops), 8):
            part = crops[i:i + 8]
            px = np.stack([np.asarray(Image.fromarray(c).resize((S, S), Image.BICUBIC)) for _, _, c in part])
            pv = (torch.from_numpy(px).to(dev).permute(0, 3, 1, 2).float() / 255 - mean) / std
            with torch.no_grad():
                o = model(input_ids=text["input_ids"].repeat(len(part), 1),
                          attention_mask=text["attention_mask"].repeat(len(part), 1), pixel_values=pv)
            logits = o.logits.sigmoid().max().item()
            maxs = max(maxs, logits)
            res = post(o, threshold=spec["threshold"], target_sizes=torch.tensor([[S, S]] * len(part)))
            for (x0, y0, _), r in zip(part, res):
                for box, s_, lb in zip(r["boxes"].cpu().numpy(), r["scores"].cpu().numpy(), r["labels"].cpu().numpy()):
                    bx0, by0, bx1, by1 = (box / sc).tolist()
                    L = max(bx1 - bx0, by1 - by0) * spec["mpp"]
                    if not (lo_m <= L <= hi_m):
                        continue
                    dets.append({"layer": job["layer"], "tile": job["tile"], "x": round(x0 + bx0, 1), "y": round(y0 + by0, 1),
                                 "w": round(bx1 - bx0, 1), "h": round(by1 - by0, 1), "score": round(float(s_), 3),
                                 "query": qs[int(lb)]})
        images += 1
    json.dump({"model": name, "device": dev, "images": images, "seconds": time.time() - t0, "detections": dets,
               "max_score": round(maxs, 4)}, open(spec["out"], "w"))


if __name__ == "__main__":
    main(sys.argv[1])
