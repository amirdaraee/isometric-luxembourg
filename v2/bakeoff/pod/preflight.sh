#!/usr/bin/env bash
# On the pod, in its first minute, before anything is installed or downloaded (v2/bakeoff/runner.py runs this as
# soon as ssh answers, and terminates the pod at once if it fails): the things that sank the first B1 pod on
# 9 Nov 2026 after 5.5 minutes, found here in seconds.
#   1. the GPU answers and the image's own torch sees it (setup.sh falls back to that torch on an older driver);
#   2. a tensor really goes to the GPU and back;
#   3. the disk has room for the model; python can make a venv; Hugging Face answers for the job's model.
# usage: preflight.sh <hf model id> [min free GB]
set -u
MODEL="${1:-Qwen/Qwen-Image}"
NEED_GB="${2:-90}"
fail() { echo "PREFLIGHT FAILED: $*"; exit 1; }
G=$(nvidia-smi --query-gpu=driver_version,name,memory.total --format=csv,noheader 2>&1 | head -1) || fail "nvidia-smi: $G"
echo "gpu: $G"
python3 - <<'PY' || fail "the image's torch does not see the GPU"
import torch
assert torch.cuda.is_available(), "torch.cuda.is_available() is false"
x = torch.arange(8, device="cuda", dtype=torch.float32)
assert float((x * 2).sum().cpu()) == 56.0
print("torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.get_device_name(0),
      f"{torch.cuda.get_device_properties(0).total_memory / 2**30:.0f} GB")
PY
FREE=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
echo "disk free: ${FREE} GB (need ${NEED_GB})"
[ "${FREE:-0}" -ge "$NEED_GB" ] || fail "only ${FREE} GB of disk free, ${NEED_GB} needed"
python3 -c "import venv, ensurepip" 2>/dev/null || fail "python cannot make a venv"
curl -sf -m 20 -o /dev/null "https://huggingface.co/api/models/$MODEL" || fail "Hugging Face does not answer for $MODEL"
echo "PREFLIGHT OK $(date -u +%H:%M:%S)"
