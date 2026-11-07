"""Run the whole-canvas painter (tiles/mdpaint.py) on Modal instead of a RunPod pod.

Same painter, same inputs. Model weights, inputs, LoRAs, painter state and outputs live on the Modal Volume
"iso-lux", so a job that stops (timeout, preemption) resumes from its last step when run again.

One-time setup (laptop):
  modal setup                                              # sign in
  modal volume create iso-lux
  modal volume put iso-lux pipeline/gpu_train/tiles/src_showcase_hint.png inputs/src_showcase.png
  modal volume put iso-lux pipeline/gpu_train/tiles/layout_showcase.png inputs/layout_showcase.png
  modal volume put iso-lux data/work/style/lora_v2/luxembourg-ink-v2_000002000.safetensors loras/luxembourg-ink-v2.safetensors
  modal run pipeline/gpu_train/modal_paint.py::download    # base model into the volume, on CPU (~1 h, cents)
Paint (prints the cost cap first; it is enforced by the function timeout):
  modal run pipeline/gpu_train/modal_paint.py --job showcase_md25 --src inputs/src_showcase.png \
      --layout inputs/layout_showcase.png --lora loras/luxembourg-ink-v2.safetensors --steps 25 --max-hours 2
Fetch the result:
  modal volume get iso-lux md/showcase_md25/canvas_full.png data/work/tiles/md/
"""
import os
import subprocess
import threading
import time
from pathlib import Path

import modal

HERE = Path(__file__).parent
DIFFUSERS = "git+https://github.com/huggingface/diffusers.git@c943837899b16cbae2f619b8dd4f7bb6f07dd81a"  # = pods
PRICE_PER_HOUR = {"H200": 4.54, "H100": 3.95, "A100-80GB": 2.50, "B200": 6.25}  # modal.com/pricing, 7 Nov 2026

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install("torch==2.13.0", "torchvision==0.28.0")
    .pip_install(DIFFUSERS, "transformers==5.5.3", "peft==0.18.1", "accelerate", "safetensors", "pillow", "numpy",
                 "hf_transfer")
    .env({"HF_HOME": "/vol/hf", "HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_XET_HIGH_PERFORMANCE": "1"})
    .add_local_file(HERE / "tiles" / "md_core.py", "/root/tiles/md_core.py")
    .add_local_file(HERE / "tiles" / "mdpaint.py", "/root/tiles/mdpaint.py")
)
vol = modal.Volume.from_name("iso-lux", create_if_missing=True)
app = modal.App("iso-lux-paint", image=image)


@app.function(volumes={"/vol": vol}, timeout=2 * 3600, cpu=4)
def download() -> str:
    """Fetch the base model into the volume on a cheap CPU container, so no GPU time is spent downloading."""
    from huggingface_hub import hf_hub_download, snapshot_download
    p = snapshot_download("Qwen/Qwen-Image-Edit-2511")
    os.makedirs("/vol/loras", exist_ok=True)
    lt = hf_hub_download("lightx2v/Qwen-Image-Edit-2511-Lightning",
                         "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors", local_dir="/vol/loras")
    vol.commit()
    return f"{p}\n{lt}"


@app.function(gpu="H200", volumes={"/vol": vol}, timeout=3 * 3600)
def paint(job: str, argv: list[str], prompt: str, deadline: float) -> str:
    out = f"/vol/md/{job}"
    os.makedirs(f"{out}/live", exist_ok=True)
    done = threading.Event()

    def keep_committing():  # the state must reach the volume even if the container is killed
        while not done.wait(60):
            vol.commit()
    threading.Thread(target=keep_committing, daemon=True).start()
    env = dict(os.environ, PROMPT=prompt, LIVE=f"{out}/live")
    cmd = ["python", "mdpaint.py", *argv, "--out", f"{out}/canvas_full.png", "--state", f"{out}/state",
           "--deadline", str(deadline)]
    with open(f"{out}/run.log", "a") as log:
        rc = subprocess.call(cmd, cwd="/root/tiles", env=env, stdout=log, stderr=subprocess.STDOUT)
    done.set()
    vol.commit()
    return {0: "finished", 3: "paused at the time limit: run the same command again to resume"}.get(rc, f"failed rc={rc}")


@app.local_entrypoint()
def main(job: str, src: str, lora: str, layout: str = "", steps: int = 25, src_cell: int = 600, cfg: float = 3.0,
         gpu: str = "H200", max_hours: float = 2.0, prompt_file: str = "pipeline/gpu_train/prompts/day.txt",
         extra: str = ""):
    rate = PRICE_PER_HOUR.get(gpu)
    cap = f"${rate * max_hours:.2f}" if rate else "unknown rate"
    print(f"job {job}: {gpu}, at most {max_hours} h -> cost cap {cap}")
    prompt = Path(prompt_file).read_text().strip()
    argv = ["--src", f"/vol/{src}", "--lora", f"/vol/{lora}", "--steps", str(steps), "--src-cell", str(src_cell),
            "--cfg", str(cfg)]
    if layout:
        argv += ["--layout", f"/vol/{layout}"]
    if extra:
        argv += extra.split()
    secs = int(max_hours * 3600)
    # the painter pauses 10 min before the deadline, leaving time to save; the timeout is the hard cap
    deadline = time.time() + secs - 120
    print(paint.with_options(gpu=gpu, timeout=secs).remote(job, argv, prompt, deadline))
