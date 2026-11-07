#!/bin/bash
# Copies the finer-scale test patch and run logs off the pod once it is painted, until the pod is gone.
while ssh -F ${POD_DIR:-$HOME/.cache/isometric-luxembourg/pods}/ssh_tiles -o ConnectTimeout=20 full true 2>/dev/null; do
  scp -q -F ${POD_DIR:-$HOME/.cache/isometric-luxembourg/pods}/ssh_tiles "full:/workspace/live_ab/canvas_full.png" $(cd "$(dirname "$0")/../../.." && pwd)/data/work/tiles/ab/ab_450.png 2>/dev/null && scp -q -F ${POD_DIR:-$HOME/.cache/isometric-luxembourg/pods}/ssh_tiles full:/workspace/train.log full:/workspace/live/drift.json $(cd "$(dirname "$0")/../../.." && pwd)/data/work/tiles/ab/ 2>/dev/null && break
  sleep 120
done
