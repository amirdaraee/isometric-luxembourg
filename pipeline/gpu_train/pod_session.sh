#!/bin/bash
# On a RunPod pod: get it ready for a session of painter jobs sent one by one from the laptop (backend.py RunPod),
# each run by md_on_pod.sh. Started once by launch.sh.
#  - a deadline watchdog TERMINATES the pod at the session deadline (the laptop copies every result back as soon as
#    its job ends, so nothing on the pod is needed after it; a stopped pod would keep billing its disks);
#  - /workspace/KEEP is created, so no single job stops the pod;
#  - the python env is (re)installed in /venv if missing, the base model and the Lightning LoRA are downloaded
#    (US pod, HF_XET_HIGH_PERFORMANCE: downloads stalled in other regions);
#  - /workspace/READY is written when jobs can start (the laptop waits for it).
# Usage: pod_session.sh <deadline-epoch>
set -u
DEADLINE="$1"
LOG=/workspace/session.log
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
end_pod() {
  echo "GUARD $(date -u +%H:%M:%S) terminating pod: $1" >> "$LOG"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podTerminate(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) }\"}" https://api.runpod.io/graphql >> "$LOG"
}
# the laptop may move the deadline by writing another epoch into /workspace/DEADLINE
echo "$DEADLINE" > /workspace/DEADLINE
( while [ "$(date +%s)" -lt "$(cat /workspace/DEADLINE 2>/dev/null || echo "$DEADLINE")" ]; do sleep 30; done
  end_pod "session deadline reached" ) > /workspace/session_watchdog.log 2>&1 &
touch /workspace/KEEP
mkdir -p /workspace/inputs /workspace/loras /workspace/md /workspace/prompts /workspace/tiles
echo "SESSION $(date -u +%H:%M:%S) deadline $(date -u -d @"$DEADLINE" +%H:%M:%S)" >> "$LOG"

DIFFUSERS="git+https://github.com/huggingface/diffusers.git@c943837899b16cbae2f619b8dd4f7bb6f07dd81a"  # = Modal
if [ ! -x /venv/bin/python ]; then
  echo "SETUP $(date -u +%H:%M:%S)" >> "$LOG"
  python3 -m venv /venv
  # the same packages as the Modal image (modal_paint.py); torch built for CUDA 12.8 first (every pod's driver
  # runs it), then 13.0, then whatever the image has
  ok=0
  for idx in cu128 cu130; do
    /venv/bin/pip install -q --no-cache-dir torch==2.13.0 torchvision==0.28.0 \
      --index-url https://download.pytorch.org/whl/$idx >> /workspace/setup.log 2>&1 && ok=1 && break
  done
  if [ $ok = 0 ]; then
    rm -rf /venv && python3 -m venv --system-site-packages /venv
  fi
  /venv/bin/pip install -q --no-cache-dir "$DIFFUSERS" transformers==5.5.3 peft==0.18.1 accelerate safetensors pillow \
    numpy hf_transfer hf_xet >> /workspace/setup.log 2>&1 || { echo "SETUP FAILED" >> "$LOG"; exit 1; }
  /venv/bin/python -c "import torch;assert torch.cuda.is_available();print('torch',torch.__version__,torch.version.cuda)" \
    >> "$LOG" 2>&1 || { echo "SETUP FAILED (no cuda)" >> "$LOG"; exit 1; }
  echo "SETUP DONE $(date -u +%H:%M:%S)" >> "$LOG"
fi
export HF_HOME=/hf HF_XET_HIGH_PERFORMANCE=1 HF_HUB_ENABLE_HF_TRANSFER=1
/venv/bin/python - >> "$LOG" 2>&1 <<'EOF' || { echo "DOWNLOAD FAILED" >> "$LOG"; exit 1; }
from huggingface_hub import hf_hub_download, snapshot_download
print(snapshot_download("Qwen/Qwen-Image-Edit-2511"))
print(hf_hub_download("lightx2v/Qwen-Image-Edit-2511-Lightning",
                      "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors", local_dir="/workspace/loras"))
EOF
echo "READY $(date -u +%H:%M:%S)" >> "$LOG"
touch /workspace/READY
