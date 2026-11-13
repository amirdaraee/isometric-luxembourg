"""What each paid job takes to the pod and brings back (all made locally at $0 before the job starts).

    build(job)      the job's bundle folder <data>/v2/test/bakeoff/_bundles/<job>/: its inputs, prompt and lists
    uploads(job)    (source, place on the pod, rsync flags): the bundle, and the LoRAs or checkpoints it needs
    local_out(job)  where the job's results are copied to

  B1   materials.json (every material's prompt from prompts.py)          -> b/materials/<name>_<k>.png
  B2   each landmark's unlit crop and layout                              -> b/landmarks/<building>_<k>.png
  C1p  the 8 pilot training crops; C1 the other 72                        -> c/targets/<window>_<k>.png
  C2p  dataset.tar (the kept pairs: dataset.build_dataset)                -> c/train_pilot/ (step 200, samples)
  C2   (the same dataset and the pilot's checkpoint, already on the pod)  -> c/train/ (the LoRA, samples)
  C3   all windows with buildings                                         -> c/painted/<window>.png
  C4   the trial buildings' facades, front-on                             -> c/facades/<facade>_<k>.png
       (painted with v1's style model unless C's unshadowed one exists)
  K1   the cathedral's cut render, as built and with its opening cleared  -> cutaways/painted/<input>_<k>.png
       (Phase 3, cutaway_paint.py; v1's style model)
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from v2.config import v1_work, v2_data

AREA = "test"
SETUP = {"B1": "t2i", "B2": "paint", "C1p": "paint", "C1": "paint", "C2p": "train", "C2": "train", "C3": "paint", "C4": "paint",
         "K1": "paint"}
OUT = {"B1": "b/materials", "B2": "b/landmarks", "C1p": "c/targets", "C1": "c/targets", "C2p": "c/train_pilot",
       "C2": "c/train", "C3": "c/painted", "C4": "c/facades", "K1": "cutaways/painted"}
# the training job keeps a checkpoint every 200 steps (295 MB each): only two of them, the final LoRA and the
# optimizer state come back
PULL_FILTER = {"C2p": ("--include=*_000000200.safetensors", "--exclude=*_0000*.safetensors"),
               "C2": ("--include=*_000001000.safetensors", "--include=*_000001600.safetensors", "--exclude=*_0000*.safetensors")}
# the model each job's setup needs from Hugging Face (preflight.sh asks for it before anything is installed)
MODEL = {"t2i": "Qwen/Qwen-Image", "paint": "Qwen/Qwen-Image-Edit-2511", "train": "Qwen/Qwen-Image-Edit-2511"}
V1_LORA = "style/lora_v2/luxembourg-ink-v2_000002000.safetensors"
NEW_LORA = "luxembourg-ink-unshadowed.safetensors"


def base() -> Path:
    return v2_data() / AREA / "bakeoff"


def local_out(job: str) -> Path:
    return base() / OUT[job]


def new_lora() -> Path:
    return base() / "c" / "train" / NEW_LORA


def _link(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _windows(d: Path, names, src: Path):
    for n in names:
        for ext in ("unlit.png", "layout.png"):
            _link(src / f"{n}.{ext}", d / "inputs" / f"{n}.{ext}")


def build(job: str) -> Path:
    from v2.bakeoff import prompts as P
    d = base() / "_bundles" / job
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    c = base() / "c"
    if job == "B1":
        from v2.layers.common import pal
        mats = {name: P.MATERIAL_BRIEF.format(what=what, rgb=tuple(int(x) for x in pal(*key.split("."))))
                for name, (what, key, _size) in P.MATERIALS.items()}
        (d / "materials.json").write_text(json.dumps({"negative": P.COMMON_NEGATIVE, "n": 3, "seed": 1867, "materials": mats}, indent=1))
    elif job == "B2":
        src = base() / "b" / "landmark_inputs"
        names = sorted(p.name[: -len(".unlit.png")] for p in src.glob("*.unlit.png"))
        if not names:
            raise SystemExit("B2: no landmark inputs (python -m v2.bakeoff inputs b --crops)")
        _windows(d, names, src)
        (d / "prompt.txt").write_text(P.C_PAINT_PROMPT if new_lora().exists() else P.LANDMARK_BRIEF)
    elif job in ("C1p", "C1", "C3"):
        wj = json.loads((c / "windows.json").read_text())
        pilot = [f"{x}_{y}" for x, y in wj["pilot_crops"]]
        if job == "C1p":
            names = pilot
        elif job == "C1":
            names = [f"{x}_{y}" for x, y in wj["train_crops"] if f"{x}_{y}" not in pilot]
        else:
            names = [f"{x}_{y}" for x, y in wj["windows"]]
        _windows(d, names, c / "inputs")
        (d / "prompt.txt").write_text(P.C_PAINT_PROMPT if job == "C3" else P.C_TARGET_PROMPT)
    elif job == "C2p":
        from v2.bakeoff.dataset import build_dataset
        build_dataset(c, d / "dataset.tar")
    elif job == "C2":
        pass
    elif job == "C4":
        src = c / "facade_inputs"
        names = sorted(p.name[: -len(".unlit.png")] for p in src.glob("*.unlit.png"))
        if not names:
            raise SystemExit("C4: no facade inputs (python -m v2.bakeoff inputs facades)")
        _windows(d, names, src)
        (d / "prompt.txt").write_text(P.C_FACADE_PROMPT if new_lora().exists() else P.C_FACADE_PROMPT_V1)
    elif job == "K1":
        from v2.bakeoff import cutaway_paint as CP
        src = base() / "cutaways" / "inputs"
        names = CP.input_names("cathedral")
        if not all((src / f"{n}.{ext}").exists() for n in names for ext in ("unlit.png", "layout.png")):
            raise SystemExit("K1: no cutaway inputs (python -m v2.bakeoff inputs cutaway)")
        _windows(d, names, src)
        (d / "prompt.txt").write_text(CP.PROMPTS["cathedral"])
    (d / "job.json").write_text(json.dumps({"job": job}))
    return d


def uploads(job: str, bdir: Path) -> list:
    """(source, destination on the pod, extra rsync flags). Big files go with --size-only: on a pod that already
    has them (the session's earlier jobs) nothing is sent."""
    ups = [(str(bdir) + "/", f"/workspace/job/{job}/", ("-c",))]
    big = ("--size-only",)
    if job in ("C1p", "C1", "K1") or (job in ("B2", "C4") and not new_lora().exists()):
        ups.append((str(v1_work() / V1_LORA), "/workspace/lora/", big))
    if job == "C3" or (job in ("B2", "C4") and new_lora().exists()):
        ups.append((str(new_lora()), "/workspace/lora/", big))
    if job == "C2":
        ups.append((str(base() / "_bundles" / "C2p" / "dataset.tar"), "/workspace/job/C2p/", big))
        pil = base() / "c" / "train_pilot"
        for f in (NEW_LORA, "optimizer.pt"):
            if (pil / f).exists():
                ups.append((str(pil / f), "/workspace/output/luxembourg-ink-unshadowed/", big))
    return ups
