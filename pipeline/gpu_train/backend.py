"""Where the painter runs: Modal (modal_paint.py) or a RunPod pod that is already up (launch.sh + pod_session.sh).

Both keep the same layout under a root: inputs/..., loras/..., md/<job>/canvas_full.png. Callers name files by
that relative path and get absolute paths on the GPU side with abs().

  be = backend("modal" | "runpod")
  be.put(local, "inputs/city/b13/day.png"); be.abs("inputs/...") -> "/vol/inputs/..." or "/workspace/inputs/..."
  rc = be.run(job, src=..., lora=..., layout=..., steps=8, src_cell=600, cfg=1, max_hours=0.5,
              prompt_file="pipeline/gpu_train/prompts/day.txt", extra="--known /vol/... ")
  be.get("md/<job>/canvas_full.png", local)

RunPod: the pod is named by $RUNPOD_POD (default "paint"); launch.sh writes its ssh config and price to
$POD_DIR/<name>.ssh and <name>.meta. Each job's wall time x the pod's price is logged to
data/work/city/runpod_spend.json by the callers (spend_log()).
"""
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT if (ROOT / "pipeline/.venv").exists() else (ROOT / "data").resolve().parent   # worktree -> main venv
MODAL = str(MAIN / "pipeline/.venv/bin/modal")
POD_DIR = Path(os.environ.get("POD_DIR", Path.home() / ".cache/isometric-luxembourg/pods"))
LIGHTNING = "loras/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors"


def sh(*cmd, log=None, quiet=False):
    if not quiet:
        print("+", " ".join(map(str, cmd)), flush=True)
    with open(log, "a") if log else open(os.devnull, "w") as f:
        return subprocess.call([str(c) for c in cmd], cwd=ROOT, stdout=f if (log or quiet) else None,
                               stderr=subprocess.STDOUT if (log or quiet) else None)


class Modal:
    name, root = "modal", "/vol"
    price = 4.54   # H200 $/h
    spend_file = ROOT / "data/work/city/modal_spend.json"

    def abs(self, rel):
        return f"{self.root}/{rel}"

    def put(self, local, rel, log=None):
        return sh(MODAL, "volume", "put", "-f", "iso-lux", local, rel, log=log)

    def get(self, rel, local, log=None):
        return sh(MODAL, "volume", "get", "--force", "iso-lux", rel, local, log=log)

    def run(self, job, src, lora, layout="", steps=25, src_cell=600, cfg=3.0, max_hours=2.0, gpu="H200",
            prompt_file="pipeline/gpu_train/prompts/day.txt", extra="", log=None):
        return sh(MODAL, "run", "pipeline/gpu_train/modal_paint.py", "--job", job, "--src", src, "--lora", lora,
                  *(["--layout", layout] if layout else []), "--steps", str(steps), "--src-cell", str(src_cell),
                  "--cfg", str(cfg), "--gpu", gpu, "--max-hours", str(max_hours), "--prompt-file", prompt_file,
                  *(["--extra", extra] if extra else []), log=log)


class RunPod:
    name, root = "runpod", "/workspace"
    spend_file = ROOT / "data/work/city/runpod_spend.json"

    def __init__(self):
        self.pod = os.environ.get("RUNPOD_POD", "paint")
        self.cfg = POD_DIR / f"{self.pod}.ssh"
        assert self.cfg.exists(), f"no pod: {self.cfg} missing (start one with launch.sh)"
        self.price = float((POD_DIR / f"{self.pod}.meta").read_text().split()[0])
        self._dirs = set()

    def ssh(self, cmd, capture=False):
        args = ["ssh", "-F", str(self.cfg), "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=30", "pod", cmd]
        for i in range(4):
            r = subprocess.run(args, capture_output=True, text=True)
            if r.returncode != 255:     # 255 = ssh itself failed: retry
                return r.stdout if capture else r.returncode
            time.sleep(10)
        return "" if capture else 255

    def abs(self, rel):
        return f"{self.root}/{rel}"

    def put(self, local, rel, log=None):
        d = str(Path(self.abs(rel)).parent)
        if d not in self._dirs:
            self.ssh(f"mkdir -p {shlex.quote(d)}")
            self._dirs.add(d)
        for i in range(4):
            if sh("rsync", "--partial", "--timeout=120", "-e", f"ssh -F {self.cfg}", local, f"pod:{self.abs(rel)}",
                  log=log) == 0:
                return 0
            time.sleep(5)
        return 1

    def get(self, rel, local, log=None):
        for i in range(4):
            if sh("rsync", "--partial", "--timeout=120", "-e", f"ssh -F {self.cfg}", f"pod:{self.abs(rel)}", local,
                  log=log) == 0:
                return 0
            time.sleep(5)
        return 1

    def ready(self, wait_s=3600):
        t0 = time.time()
        while time.time() - t0 < wait_s:
            if self.ssh("test -f /workspace/READY") == 0:
                return True
            print("pod not ready yet:", self.ssh("tail -n 2 /workspace/session.log", capture=True).strip(), flush=True)
            time.sleep(30)
        return False

    def run(self, job, src, lora, layout="", steps=25, src_cell=600, cfg=3.0, max_hours=2.0, gpu=None,
            prompt_file="pipeline/gpu_train/prompts/day.txt", extra="", log=None):
        if not self.ready():
            return 1
        pf = f"prompts/{Path(prompt_file).name}"
        self.put(ROOT / prompt_file, pf, log=log)
        # the painter pauses 10 min before its deadline: give it the cap plus those 10 min
        deadline = int(time.time() + max_hours * 3600 + 600)
        args = [deadline, job, self.abs(src), self.abs(layout) if layout else "-", self.abs(lora), steps, src_cell,
                "--cfg", cfg, *extra.split()]
        cmd = (f"rm -f /workspace/md/{job}/rc; PROMPT_FILE={self.abs(pf)} setsid nohup /workspace/md_on_pod.sh "
               + " ".join(shlex.quote(str(a)) for a in args) + f" > /workspace/md_{job}.out 2>&1 < /dev/null &")
        print(f"+ [runpod {self.pod}] {job}: cap {max_hours} h (${max_hours * self.price:.2f})", flush=True)
        self.ssh(cmd)
        hard = time.time() + max_hours * 3600 + 900
        last = ""
        while True:
            time.sleep(20)
            rc = self.ssh(f"cat /workspace/md/{job}/rc 2>/dev/null", capture=True).strip()
            if rc:
                break
            line = self.ssh(f"grep -E '^step|canvas|Error|error' /workspace/md/{job}/run.log 2>/dev/null | tail -n 1",
                            capture=True).strip()
            if line and line != last:
                print(f"  {job}: {line}", flush=True)
                last = line
            if time.time() > hard:
                print(f"  {job}: over its cap, killing it", flush=True)
                self.ssh("pkill -f mdpaint.py")
                return 124
        if log:
            self.get(f"md/{job}/run.log", str(log) + f".{job}.pod.log")
        return int(rc)


def backend(name):
    return {"modal": Modal, "runpod": RunPod}[name]()


def spend_log(be, tag, job, seconds, note=""):
    """Wall time of one job x the backend's price (an upper bound: includes model loading)."""
    f = be.spend_file
    log = json.loads(f.read_text()) if f.exists() else []
    usd = round(seconds / 3600 * be.price, 3)
    log.append({"tag": tag, "job": job, "backend": be.name, "price_per_h": be.price, "seconds": round(seconds),
                "usd": usd, "note": note or "wall time of the job x the GPU price (includes model loading)",
                "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    f.write_text(json.dumps(log, indent=1))
    return usd


def spent(be, tag):
    f = be.spend_file
    return sum(e["usd"] for e in (json.loads(f.read_text()) if f.exists() else []) if e.get("tag") == tag)
