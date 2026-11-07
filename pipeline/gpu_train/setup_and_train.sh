#!/bin/bash
# Follows ai-toolkit's README install steps, with the environment on the persistent volume.
set -e
trap 'echo "FAILED at line $LINENO"' ERR
cd /workspace
echo "SETUP START $(date -u +%H:%M:%S)"
mkdir -p output
if [ ! -d data ]; then
  rm -rf heldout toolkit
  tar -xf dataset.tar -C /workspace
  mv toolkit data
fi
echo "data: $(ls data/*.png | wc -l) targets, $(ls data/control/*.png | wc -l) controls, $(ls data/*.txt | wc -l) captions"
if [ ! -d ai-toolkit ]; then git clone -q https://github.com/ostris/ai-toolkit.git; fi
cd ai-toolkit
echo "ai-toolkit $(git rev-parse --short HEAD)"
if [ ! -x /workspace/venv/bin/python ]; then
  python3 -m venv /workspace/venv
  /workspace/venv/bin/pip install -q --no-cache-dir torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
  /workspace/venv/bin/pip install -q -r requirements.txt
  /workspace/venv/bin/pip install -q hf_transfer
fi
/workspace/venv/bin/python -c "import torch,torchvision;print('torch',torch.__version__,'cuda',torch.cuda.is_available())"
export HF_HUB_ENABLE_HF_TRANSFER=1
echo "TRAIN START $(date -u +%H:%M:%S)"
/workspace/venv/bin/python run.py /workspace/stage1.yaml
echo "FINISHED $(date -u +%H:%M:%S)"
