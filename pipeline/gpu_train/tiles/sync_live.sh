#!/bin/bash
# Laptop side: copy the pod's live files into the dashboard folder every 20 s, plus cost/balance info.
# Usage: sync_live.sh <ssh config> <pod rate $/h> <pod start epoch> <label>
CFG="$1"; RATE="$2"; START="$3"; LABEL="$4"
DST="$(cd "$(dirname "$0")/../../.." && pwd)/web/public/live"
while true; do
  ok=1
  for f in status.json canvas.jpg last_in.jpg last_out.jpg; do
    scp -q -F "$CFG" -o ConnectTimeout=15 "full:/workspace/live/$f" "$DST/$f.part" 2>/dev/null && mv "$DST/$f.part" "$DST/$f" || ok=0
  done
  BAL=$(runpodctl user 2>/dev/null | grep -oE '"clientBalance": *[0-9.]+' | grep -oE '[0-9.]+$')
  printf '{"rate": %s, "pod_started": %s, "synced_at": %s, "balance": %s, "label": "%s"}\n' \
    "$RATE" "$START" "$(date +%s)" "${BAL:-null}" "$LABEL" > "$DST/job.tmp" && mv "$DST/job.tmp" "$DST/job.json"
  grep -q '"state": "done"' "$DST/status.json" && { scp -q -F "$CFG" "full:/workspace/live/canvas_full.png" "$DST/" 2>/dev/null; exit 0; }
  sleep 20
done
