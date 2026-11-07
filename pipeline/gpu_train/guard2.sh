#!/bin/bash
# Runs on the pod, independent of the laptop.
# Stage 1 ends -> city check -> wait up to 20 min for a GO file (written only after a human-quality review)
# -> stage 2 resumes to 3000 steps -> final city check -> stop. Any failure or the deadline -> stop.
# Stopping keeps /workspace (checkpoints, samples); only GPU billing ends.
DEADLINE="$1"   # epoch seconds: stop no matter what
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
log() { echo "GUARD $(date -u +%H:%M:%S) $*"; }
stop_pod() {
  log "stopping pod: $1"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" https://api.runpod.io/graphql
  echo; exit
}
past_deadline() { [ "$(date +%s)" -ge "$DEADLINE" ]; }
wait_for() {   # $1 log file
  while true; do
    past_deadline && stop_pod "deadline reached"
    grep -qE "FAILED at line|Traceback|out of memory" "$1" && stop_pod "training failed ($1)"
    grep -q "^FINISHED" "$1" && return
    sleep 30
  done
}
city_check() {   # $1 output folder name
  timeout 1200 /workspace/venv/bin/python /workspace/city_check.py > "/workspace/$1.log" 2>&1 || log "city check incomplete"
  rm -rf "/workspace/output/$1"; mv /workspace/output/city_check "/workspace/output/$1" 2>/dev/null
}
log "watching stage 1"
wait_for /workspace/train.log
log "stage 1 finished"; city_check city_step500
log "waiting up to 20 min for GO_STAGE2"
for i in $(seq 1 40); do
  [ -f /workspace/GO_STAGE2 ] && break
  [ -f /workspace/STOP ] && stop_pod "review said stop"
  past_deadline && stop_pod "deadline reached"
  sleep 30
done
[ -f /workspace/GO_STAGE2 ] || stop_pod "no go decision for stage 2"
log "stage 2 starting"
cd /workspace/ai-toolkit
( HF_HUB_ENABLE_HF_TRANSFER=1 /workspace/venv/bin/python run.py /workspace/stage2.yaml; echo "FINISHED $(date -u +%H:%M:%S)" ) > /workspace/train2.log 2>&1 &
sleep 60
wait_for /workspace/train2.log
log "stage 2 finished"; city_check city_final
stop_pod "all done"
