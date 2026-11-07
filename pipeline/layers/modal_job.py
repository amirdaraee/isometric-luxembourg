"""Run one painter job on Modal for the layered map, with a hard spending cap and a spend log.

Uploads the inputs to the "iso-lux" volume under inputs/layers/<job>/, runs pipeline/gpu_train/modal_paint.py
(Lightning, 8 steps, the trained style), fetches the canvas, and logs the cost (wall time x GPU price, an upper
bound) to data/work/layers/spend.json. Refuses to start if the logged spend plus this job's cap would pass the
cap of the whole proof of concept.

  modal_job.py <job> --src src.png [--layout layout.png] [--init start.png --strength 0.4] [--max-hours 0.25]
               [--note "..."] [--total-cap 5]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from layers_common import LAYERS, ROOT

PIPE = Path(__file__).resolve().parents[1]
MODAL = str(Path(sys.executable).parent / "modal")  # the modal CLI next to this python
PRICE = {"H200": 4.54, "H100": 3.95}
LIGHTNING = "/vol/loras/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors"
SPEND = LAYERS / "spend.json"


def spent():
    return sum(e["usd"] for e in json.loads(SPEND.read_text())) if SPEND.exists() else 0.0


def log_spend(entry):
    log = json.loads(SPEND.read_text()) if SPEND.exists() else []
    log.append(entry)
    SPEND.write_text(json.dumps(log, indent=1))


def sh(*cmd):
    print("+", " ".join(cmd), flush=True)
    return subprocess.call(list(cmd), cwd=PIPE.parent)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--src", required=True)
    ap.add_argument("--layout")
    ap.add_argument("--init")
    ap.add_argument("--known", help="pixels to hold (with --keep: white where they must stay)")
    ap.add_argument("--keep")
    ap.add_argument("--strength", type=float, default=0.4)
    ap.add_argument("--gpu", default="H200")
    ap.add_argument("--src-cell", type=int, default=512, help="src px per 512 model px (512: src is at model scale)")
    ap.add_argument("--max-hours", type=float, default=0.25)
    ap.add_argument("--total-cap", type=float, default=5.0)
    ap.add_argument("--note", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cap = PRICE[args.gpu] * args.max_hours
    if spent() + cap > args.total_cap:
        sys.exit(f"refused: spent ${spent():.2f} + this job's cap ${cap:.2f} would pass ${args.total_cap}")
    rem = f"inputs/layers/{args.job}"
    if args.max_hours < 0.35:
        print("note: the painter pauses 10 min before its time limit; under ~0.35 h it may pause before finishing")
    files = {"src": args.src, "layout": args.layout, "init": args.init, "known": args.known, "keep": args.keep}
    extra = ["--extra-lora", LIGHTNING, "--mu", "1.0986"]
    for name, path in files.items():
        if path:
            if sh(MODAL, "volume", "put", "-f", "iso-lux", path, f"{rem}/{name}.png"):
                sys.exit(f"upload failed: {path}")
    if args.known:
        extra += ["--known", f"/vol/{rem}/known.png", "--keep", f"/vol/{rem}/keep.png"]
    if args.init:
        extra += ["--init", f"/vol/{rem}/init.png", "--strength", str(args.strength)]
    cmd = [MODAL, "run", "pipeline/gpu_train/modal_paint.py", "--job", args.job, "--src", f"{rem}/src.png",
           "--lora", "loras/luxembourg-ink-v2.safetensors", "--steps", "8", "--cfg", "1.0", "--gpu", args.gpu,
           "--src-cell", str(args.src_cell),
           "--max-hours", str(args.max_hours), "--extra", " ".join(extra)]
    if args.layout:
        cmd += ["--layout", f"{rem}/layout.png"]
    t0 = time.time()
    rc = sh(*cmd)
    secs = time.time() - t0
    usd = round(secs / 3600 * PRICE[args.gpu], 3)
    log_spend({"job": args.job, "gpu": args.gpu, "seconds": round(secs), "usd": usd, "rc": rc, "note": args.note,
               "how": "wall time of the modal run x the GPU price (an upper bound: includes start-up)",
               "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    print(f"job {args.job}: rc {rc}, {secs / 60:.1f} min, about ${usd:.2f}; total spent ${spent():.2f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sh(MODAL, "volume", "get", "--force", "iso-lux", f"md/{args.job}/canvas_full.png", args.out)
    return 0 if Path(args.out).exists() else 1


if __name__ == "__main__":
    sys.exit(main())
