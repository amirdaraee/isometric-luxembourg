#!/bin/bash
# On the pod: install ai-toolkit, run the checkpoint check, then stop the pod (also on failure or deadline).
# Usage: run.sh <deadline-epoch>
DEADLINE="$1"
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
stop_pod() {
  echo "GUARD $(date -u +%H:%M:%S) stopping pod: $1"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" https://api.runpod.io/graphql
  echo
}
# Deadline watchdog, independent of everything else.
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do sleep 30; done; stop_pod "deadline reached" ) > /workspace/watchdog.log 2>&1 &

(
set -e
trap 'echo "FAILED at line $LINENO"' ERR
cd /workspace
echo "SETUP START $(date -u +%H:%M:%S)"
mkdir -p output
mkdir -p views lora out
[ -d ai-toolkit ] || git clone -q https://github.com/ostris/ai-toolkit.git
cd ai-toolkit
echo "ai-toolkit $(git rev-parse --short HEAD)"
if [ ! -x /venv/bin/python ]; then
  python3 -m venv /venv
  /venv/bin/pip install -q --no-cache-dir torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
  /venv/bin/pip install -q -r requirements.txt
  /venv/bin/pip install -q hf_transfer
fi
/venv/bin/python -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
export HF_HUB_ENABLE_HF_TRANSFER=1 HF_HOME=/hf
echo "CHECK START $(date -u +%H:%M:%S)"
/venv/bin/python /workspace/ckpt_check.py 1500,2000,2500
echo "FINISHED $(date -u +%H:%M:%S)"
) > /workspace/train.log 2>&1
grep -q "^FINISHED" /workspace/train.log || { sleep 600; stop_pod "training failed (10 min grace to read the log)"; }
# Success: leave 15 minutes to copy the samples off, then stop.
sleep 900; stop_pod "done, grace period over"
