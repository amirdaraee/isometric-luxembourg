#!/bin/bash
set -e
trap 'echo FAILED line $LINENO' ERR
cd /workspace
pip uninstall -y -q --break-system-packages torchaudio
pip install -q -U --break-system-packages torchvision diffusers transformers accelerate peft sentencepiece safetensors pillow huggingface_hub hf_transfer
mkdir -p lora
curl -sS -f -o lora/model.safetensors "https://hub.oxen.ai/api/repos/cannoneyed/isometric-nyc-v02/file/55b9eaff9e93ceae2549c85ba2f10b4f/models/cannoneyed-dark-copper-flea/model.safetensors"
[ "$(stat -c %s lora/model.safetensors)" = "295144520" ] || { echo "weights wrong size"; exit 1; }
export HF_HUB_ENABLE_HF_TRANSFER=1
python run_on_pod.py
echo FINISHED
