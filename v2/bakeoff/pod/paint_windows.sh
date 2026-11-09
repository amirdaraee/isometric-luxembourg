#!/usr/bin/env bash
# On the pod: paint every input window of a set with v1's whole-canvas painter (pipeline/gpu_train/tiles/mdpaint.py,
# kept from v1: MultiDiffusion, hold and repair), Qwen-Image-Edit-2511 + Lightning (8 steps, cfg 1) + a style LoRA.
# usage: paint_windows.sh <set> <out> <steps>
#   set: landmarks (B2: v1's ink LoRA), targets_pilot / targets (C1: v1's ink LoRA, the even-light prompt),
#        paint / facades (C3, C4: the new unshadowed LoRA)
# Inputs: /workspace/inputs/<set>/<name>.unlit.png, .layout.png (python -m v2.bakeoff inputs ...). The prompt is
# in /workspace/inputs/<set>/prompt.txt (from v2/bakeoff/prompts.py). One window = one 1024 px model pass at
# src-cell 512 (0.125 m per model px: one map px per model px).
set -euo pipefail
SET="$1"; OUT="$2"; STEPS="${3:-8}"
case "$SET" in
  landmarks|targets_pilot|targets) LORA=/workspace/lora/luxembourg-ink-v2_000002000.safetensors ;;
  *) LORA=/workspace/lora/luxembourg-ink-unshadowed.safetensors ;;
esac
mkdir -p "$OUT"
for f in /workspace/inputs/"$SET"/*.unlit.png; do
  n=$(basename "$f" .unlit.png)
  [ -f "$OUT/$n.png" ] && continue
  python pipeline/gpu_train/tiles/mdpaint.py --src "$f" --layout "/workspace/inputs/$SET/$n.layout.png" \
    --lora "$LORA" --extra-lora /workspace/lora/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors \
    --steps "$STEPS" --cfg 1.0 --mu 1.0986 --src-cell 512 --seed 1867 --out "$OUT/$n.png" \
    --state "/workspace/md_state/$SET-$n"
done
