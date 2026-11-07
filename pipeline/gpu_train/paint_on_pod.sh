#!/bin/bash
# On a pod that already has /venv and the base model cached (a finished training pod): paint, then stop the pod.
# Usage: paint_on_pod.sh <deadline-epoch> <lora file> <src cell px> <src.png> <layout.png or -> <live dir> [extra env...]
DEADLINE="$1"; LORA="$2"; CELLPX="$3"; SRCP="$4"; LAYP="$5"; LIVEP="$6"
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
stop_pod() {
  echo "GUARD $(date -u +%H:%M:%S) stopping pod: $1"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" https://api.runpod.io/graphql
  echo
}
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do sleep 30; done; stop_pod "deadline reached" ) > /workspace/paint_watchdog.log 2>&1 &
export HF_HOME=/hf SRC="$SRCP" LIVE="$LIVEP"
[ "$LAYP" != "-" ] && export LAYOUT="$LAYP"
cd /workspace
( /venv/bin/python /workspace/tiler.py "$LORA" 25 "$CELLPX" && echo "PAINT FINISHED $(date -u +%H:%M:%S)" || echo "PAINT FAILED" ) > /workspace/paint.log 2>&1
grep -q "PAINT FINISHED" /workspace/paint.log || { sleep 600; stop_pod "paint failed (10 min grace)"; exit; }
[ -f /workspace/KEEP ] && exit 0      # another job will follow on this pod
sleep 1200; stop_pod "paint done, grace over"
