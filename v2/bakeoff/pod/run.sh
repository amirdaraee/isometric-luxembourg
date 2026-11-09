#!/usr/bin/env bash
# On the pod (started by v2/bakeoff/runner.py with its watchdog already armed): wait for the laptop to copy the
# inputs and this folder (rsync over ssh, then touch /workspace/READY), set up, run one job, write DONE.
# usage: run.sh <job id>
set -euo pipefail
JOB="$1"
cd /workspace
for i in $(seq 1 120); do [ -f /workspace/READY ] && break; sleep 10; done
[ -f /workspace/READY ] || { echo "no inputs after 20 min: stopping"; exit 1; }
pip install -q "diffusers>=0.36" "transformers>=4.57" accelerate safetensors peft pillow huggingface_hub hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1
case "$JOB" in
  B1)  python pod/b1_materials.py --out out/materials --n 3 ;;
  B2)  bash pod/paint_windows.sh landmarks out/landmarks 8 ;;
  C1p) bash pod/paint_windows.sh targets_pilot out/targets 8 ;;
  C1)  bash pod/paint_windows.sh targets out/targets 8 ;;
  C2p) git clone -q https://github.com/ostris/ai-toolkit && pip install -q -r ai-toolkit/requirements.txt \
         && sed 's/steps: 2000/steps: 200/' pod/c2_train.yaml > c2p.yaml && python ai-toolkit/run.py c2p.yaml ;;
  C2)  python ai-toolkit/run.py pod/c2_train.yaml ;;   # resumes from the pilot's step-200 checkpoint
  C3)  bash pod/paint_windows.sh paint out/painted 8 ;;
  C4)  bash pod/paint_windows.sh facades out/facades 8 ;;
  *) echo "unknown job $JOB"; exit 2 ;;
esac
touch /workspace/DONE
