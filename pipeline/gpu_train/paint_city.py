"""Laptop side of PLAN.md Phase 4: paint the city block by block on Modal, outward from the old town.

For each block in data/work/city/blocks.json (city_blocks.py plan) that is not finished yet:
  prepare inputs -> held pixels from finished neighbours -> upload -> mdpaint on Modal -> fetch -> register.
Blocks run in waves: a block starts only when every overlapping block before it in the order is finished, and
never next to a block that is still painting. Spending is capped: a block's cap is its function timeout x the
GPU's price, and no block starts if the caps could exceed --budget in total.

  paint_city.py --budget 40 [--steps 25 --cfg 3] [--lightning] [--only b03,b01] [--parallel 3] [--dry-run]
  paint_city.py --budget 20 --version night     # a painted version, from each block's finished day canvas
With --version, the light LoRA turns the day canvas into that version (1:1 scale, prompts/<version>.txt, 15 steps
by default), holding the neighbouring blocks already finished in the same version.
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPE = ROOT / "pipeline"
CITY = ROOT / "data" / "work" / "city"
PAINTED = ROOT / "data" / "work" / "tiles" / "painted.json"
MODAL = str(PIPE / ".venv" / "bin" / "modal")
PY = str(PIPE / ".venv" / "bin" / "python")
PRICE = {"H200": 4.54, "H100": 3.95}
LIGHTNING = "/vol/loras/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors"

ap = argparse.ArgumentParser()
ap.add_argument("--budget", type=float, required=True, help="USD, total cap for this run")
ap.add_argument("--steps", type=int, default=None, help="default 25 (day), 15 (versions)")
ap.add_argument("--version", help="night, golden, winter, winter_night, autumn or spring")
ap.add_argument("--cfg", type=float, default=3.0)
ap.add_argument("--lightning", action="store_true", help="8 steps, no CFG, Lightning LoRA (if Phase 2 chose it)")
ap.add_argument("--gpu", default="H200")
ap.add_argument("--sec-per-window", type=float, default=4.0, help="measured in Phase 2; sets each block's time cap")
ap.add_argument("--only", default="")
ap.add_argument("--parallel", type=int, default=3)
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()
if args.lightning:
    args.steps, args.cfg = 8, 1.0
if args.steps is None:
    args.steps = 15 if args.version else 25
V = args.version
LIGHT_LOCAL = ROOT / "data" / "work" / "night" / "lora_light" / "luxembourg-light-v1.safetensors"

lock = threading.Lock()
spent_cap = 0.0


def sh(*cmd, log=None):
    print("+", " ".join(cmd), flush=True)
    if args.dry_run:
        return 0
    with open(log, "a") if log else open("/dev/null", "w") as f:
        return subprocess.call(list(cmd), cwd=ROOT, stdout=f if log else None, stderr=subprocess.STDOUT if log else None)


def state():
    return json.loads((CITY / "blocks.json").read_text())


def overlaps(a, b):
    return abs(a["x0"] - b["x0"]) < a["w"] and abs(a["y0"] - b["y0"]) < a["h"]


def hours_cap(b):
    # windows per step over the data-filled part (empty windows are skipped), x steps x seconds, + 25 min margin
    win = 49 * max(b["fill"], 0.1)
    return round(win * args.steps * args.sec_per_window / 3600 + 25 / 60, 2)


def paint_block(b):
    bid = b["id"]
    d = CITY / bid
    log = str(d / f"paint_city{'_' + V if V else ''}.log")
    d.mkdir(parents=True, exist_ok=True)
    sfx = f"_{V}" if V else ""
    put = lambda local, remote: sh(MODAL, "volume", "put", "-f", "iso-lux", str(local), remote, log=log)  # noqa: E731
    if V:
        put(state()["done"][bid], f"inputs/city/{bid}/day.png")
    elif not (d / "src.png").exists():
        sh(PY, "pipeline/city_blocks.py", "prepare", bid, log=log)
    sh(PY, "pipeline/city_blocks.py", "known", bid, *([V] if V else []), log=log)
    for f in (["known", "keep"] if V else ["src", "layout", "known", "keep"]):
        name = f + (sfx if f in ("known", "keep") else "")
        if (d / f"{name}.png").exists():
            put(d / f"{name}.png", f"inputs/city/{bid}/{name}.png")
    extra = []
    if (d / f"known{sfx}.png").exists():
        extra += ["--known", f"/vol/inputs/city/{bid}/known{sfx}.png", "--keep", f"/vol/inputs/city/{bid}/keep{sfx}.png"]
    if args.lightning:
        extra += ["--extra-lora", LIGHTNING, "--mu", "1.0986"]
    job = f"city_{bid}_{V or 'day'}_s{args.steps}"
    if V:
        inputs = ["--src", f"inputs/city/{bid}/day.png", "--src-cell", "512",
                  "--lora", "loras/luxembourg-light-v1.safetensors", "--prompt-file", f"pipeline/gpu_train/prompts/{V}.txt"]
    else:
        inputs = ["--src", f"inputs/city/{bid}/src.png", "--layout", f"inputs/city/{bid}/layout.png",
                  "--lora", "loras/luxembourg-ink-v2.safetensors"]
    rc = sh(MODAL, "run", "pipeline/gpu_train/modal_paint.py", "--job", job, *inputs, "--steps", str(args.steps),
            "--cfg", str(args.cfg), "--gpu", args.gpu, "--max-hours", str(hours_cap(b)),
            *(["--extra", " ".join(extra)] if extra else []), log=log)
    out = d / f"canvas_{V or 'day'}_s{args.steps}.png"
    sh(MODAL, "volume", "get", "--force", "iso-lux", f"md/{job}/canvas_full.png", str(out), log=log)
    if args.dry_run:
        return True
    if rc != 0 or not out.exists():
        print(f"{bid}: no canvas (rc={rc}); see {log}", flush=True)
        return False
    if not V:  # rivers in the old town's blue, keeping the painted texture
        sh(PY, "pipeline/water_tone.py", str(out), str(b["x0"]), str(b["y0"]), str(b["w"]), str(b["h"]), str(out), log=log)
    sh(PY, "pipeline/city_blocks.py", "done", bid, str(out), *([V] if V else []), log=log)
    if not V:
        with lock:
            painted = json.loads(PAINTED.read_text()) if PAINTED.exists() else []
            painted = [p for p in painted if p.get("block") != bid]
            painted.append({"file": str(Path("..") / "city" / bid / out.name), "x0": b["x0"], "y0": b["y0"],
                            "w": b["w"], "h": b["h"], "block": bid})
            PAINTED.write_text(json.dumps(painted))
    print(f"{bid}: {V or 'day'} painted -> {out}", flush=True)
    return True


def main():
    global spent_cap
    st = state()
    blocks = st["blocks"]
    done = set(st.get("done_v", {}).get(V, {}) if V else st["done"])
    # a version needs the block's day canvas first
    order = [b for b in blocks if b["id"] not in done and (not V or b["id"] in st["done"])]
    if V and not args.dry_run:
        sh(MODAL, "volume", "put", "-f", "iso-lux", str(LIGHT_LOCAL), "loras/luxembourg-light-v1.safetensors")
    if args.only:
        keep = set(args.only.split(","))
        order = [b for b in order if b["id"] in keep]
    rate = PRICE[args.gpu]
    print(f"{len(order)} blocks to paint; caps:", ", ".join(f"{b['id']} ${hours_cap(b) * rate:.2f}" for b in order))
    running: dict[str, threading.Thread] = {}
    failed: set[str] = set()
    finished: set[str] = set()

    def go(b):
        if paint_block(b):
            finished.add(b["id"])
        else:
            failed.add(b["id"])

    while order or running:
        for bid, t in list(running.items()):
            if not t.is_alive():
                del running[bid]
        done |= finished
        started = False
        for b in list(order):
            if len(running) >= args.parallel:
                break
            before = [o for o in blocks if o["id"] != b["id"] and overlaps(o, b) and o["dist"] < b["dist"]]
            if any(o["id"] in failed for o in before):
                order.remove(b)       # its neighbour failed: leave it for a later run
                continue
            if any(o["id"] not in done for o in before) or any(overlaps(o, b) for o in blocks if o["id"] in running):
                continue
            cap = hours_cap(b) * rate
            if spent_cap + cap > args.budget:
                print(f"budget: {b['id']} (cap ${cap:.2f}) would pass ${args.budget}; not starting more", flush=True)
                order.clear()
                break
            spent_cap += cap
            order.remove(b)
            t = threading.Thread(target=go, args=(b,))
            t.start()
            running[b["id"]] = t
            started = True
            if args.dry_run:
                t.join()
        if not started and not running and order:
            print("nothing can start:", [b["id"] for b in order], flush=True)
            break
        if running and not args.dry_run:
            time.sleep(20)
    print(f"city run over. caps used ${spent_cap:.2f} of ${args.budget}; painted {sorted(finished)}; "
          f"failed {sorted(failed) or 'none'}")


if __name__ == "__main__":
    sys.exit(main())
