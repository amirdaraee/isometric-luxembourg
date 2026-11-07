#!/bin/bash
# Runs on the pod, independent of the laptop: after training, check city views, then stop the pod.
# Stopping keeps /workspace (checkpoints, samples); only the GPU billing ends.
DEADLINE_UTC="$1"   # e.g. 22:55 - stop no matter what at this time
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
stop_pod() {
  echo "GUARD stopping pod: $1 $(date -u +%H:%M:%S)"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" https://api.runpod.io/graphql
  echo
}
while true; do
  now=$(date -u +%H:%M)
  if [[ "$now" > "$DEADLINE_UTC" || "$now" == "$DEADLINE_UTC" ]]; then stop_pod "deadline reached"; exit; fi
  if grep -qE "FAILED at line|Traceback" /workspace/train.log; then stop_pod "training failed"; exit; fi
  if grep -q "^FINISHED" /workspace/train.log; then
    echo "GUARD training finished $(date -u +%H:%M:%S), running city check"
    timeout 1200 /workspace/venv/bin/python /workspace/city_check.py || echo "GUARD city check did not complete"
    stop_pod "stage done"; exit
  fi
  sleep 30
done
