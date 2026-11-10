#!/usr/bin/env bash
# On the pod: make one kind of work ready, once (a lock serialises callers; a done marker makes it a no-op).
#   paint  the painter's python env, Qwen-Image-Edit-2511 and the 8-step Lightning LoRA
#   t2i    the same env and Qwen-Image (text to image, job B1)
#   train  ai-toolkit in its own env (job C2p/C2); the base model is shared with "paint" (one HF cache)
# The env is v1's (pipeline/gpu_train/pod_session.sh): the same torch, diffusers commit, transformers and peft.
set -u
KIND="$1"
mkdir -p /workspace/state /workspace/logs /workspace/lora /workspace/out
exec 9>/workspace/state/setup.lock
flock 9
export HF_HOME=/hf HF_XET_HIGH_PERFORMANCE=1 HF_HUB_ENABLE_HF_TRANSFER=1
DIFFUSERS="git+https://github.com/huggingface/diffusers.git@c943837899b16cbae2f619b8dd4f7bb6f07dd81a"
cuda_ok() { "$1" -c "import torch;assert torch.cuda.is_available();print('torch',torch.__version__,torch.version.cuda,torch.cuda.get_device_name(0))"; }
# torch 2.13 is built for CUDA 13.0 and needs a driver of 580 or newer; on an older host the image's own torch
# (built for its driver) is used. The check runs every time, so a pod is never marked ready with a torch that cannot
# see its GPU (the first B1 pod, 9 Nov 2026: driver for CUDA 12.8, the job failed at the first model load).
DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | cut -d. -f1)
make_venv() {   # make_venv <dir>
  rm -rf "$1"
  if [ "${DRIVER:-0}" -ge 580 ]; then
    python3 -m venv "$1" && "$1/bin/pip" install -q --no-cache-dir torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 \
      --index-url https://download.pytorch.org/whl/cu130 && cuda_ok "$1/bin/python" && return 0
    rm -rf "$1"
  fi
  python3 -m venv --system-site-packages "$1" && cuda_ok "$1/bin/python" || return 1
  # the image's torch comes without numpy and without torchvision (the Qwen processor needs it): numpy first
  # (torchvision imports it: the second B1 pod, 10 Nov 2026, failed here), then the torchvision that matches
  "$1/bin/pip" install -q --no-cache-dir numpy pillow || return 1
  "$1/bin/python" -c "import torchvision" 2>/dev/null && return 0
  TV=$("$1/bin/python" -c "import torch;v=torch.__version__.split('+')[0].split('.');print(f'0.{int(v[1])+15}.{v[2]}')")
  CU=$("$1/bin/python" -c "import torch;print('cu'+torch.version.cuda.replace('.',''))")
  "$1/bin/pip" install -q --no-cache-dir --no-deps "torchvision==$TV" --index-url "https://download.pytorch.org/whl/$CU" \
    && "$1/bin/python" -c "import torchvision;print('torchvision',torchvision.__version__)"
}
echo "SETUP $KIND $(date -u +%H:%M:%S) driver ${DRIVER:-?}"
if ! { [ -f "/workspace/state/setup_$KIND.ok" ] && cuda_ok /venv/bin/python > /dev/null 2>&1; }; then rm -f "/workspace/state/setup_$KIND.ok"; fi
[ -f "/workspace/state/setup_$KIND.ok" ] && exit 0
if ! { [ -x /venv/bin/python ] && cuda_ok /venv/bin/python > /dev/null 2>&1 && /venv/bin/python -c "import diffusers, peft" 2>/dev/null; }; then
  make_venv /venv || { echo "SETUP FAILED (no torch that sees the GPU)"; exit 1; }
  /venv/bin/pip install -q --no-cache-dir "$DIFFUSERS" transformers==5.5.3 peft==0.18.1 accelerate safetensors pillow \
    numpy sentencepiece protobuf hf_transfer hf_xet || { echo "SETUP FAILED (pip)"; exit 1; }
  cuda_ok /venv/bin/python || { echo "SETUP FAILED (no cuda after the packages)"; exit 1; }
fi
case "$KIND" in
  paint)
    /venv/bin/python -c "from huggingface_hub import snapshot_download; print(snapshot_download('Qwen/Qwen-Image-Edit-2511'))" \
      || { echo "DOWNLOAD FAILED"; exit 1; }
    # the Lightning LoRA: plain HTTPS with a time limit and retries (the xet download of this one file stalled at
    # 231 MB on the first C1p pod, 9 Nov 2026)
    L=/workspace/lora/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors
    if [ ! -s "$L" ]; then
      for i in 1 2 3 4; do
        curl -sfL --max-time 240 -C - -o "$L.part" \
          "https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning/resolve/main/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors" \
          && mv "$L.part" "$L" && break
        sleep 3
      done
    fi
    [ -s "$L" ] || { echo "DOWNLOAD FAILED (Lightning LoRA)"; exit 1; }
    ls -la "$L"
    ;;
  t2i)
    /venv/bin/python -c "from huggingface_hub import snapshot_download; print(snapshot_download('Qwen/Qwen-Image'))" \
      || { echo "DOWNLOAD FAILED"; exit 1; }
    ;;
  train)
    cd /workspace
    [ -d ai-toolkit ] || git clone -q https://github.com/ostris/ai-toolkit.git || { echo "SETUP FAILED (clone)"; exit 1; }
    ( cd ai-toolkit && echo "ai-toolkit $(git rev-parse --short HEAD)" )
    if ! { [ -x /venv-train/bin/python ] && cuda_ok /venv-train/bin/python > /dev/null 2>&1 && /venv-train/bin/python -c "import toolkit" 2>/dev/null; }; then
      make_venv /venv-train || { echo "SETUP FAILED (train: no torch that sees the GPU)"; exit 1; }
      /venv-train/bin/pip install -q -r ai-toolkit/requirements.txt && /venv-train/bin/pip install -q hf_transfer hf_xet \
        || { echo "SETUP FAILED (ai-toolkit env)"; exit 1; }
    fi
    cuda_ok /venv-train/bin/python || { echo "SETUP FAILED (train: no cuda)"; exit 1; }
    ;;
  *) echo "unknown setup $KIND"; exit 2 ;;
esac
touch "/workspace/state/setup_$KIND.ok"
echo "SETUP $KIND DONE $(date -u +%H:%M:%S)"
