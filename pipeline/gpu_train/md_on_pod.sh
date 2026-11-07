#!/bin/bash
# On a RunPod pod: paint one job with the whole-canvas painter (tiles/mdpaint.py), then stop the pod.
# Rules learned the hard way (see PLAN.md, "Lessons"):
#  - each job has its own folder /workspace/md/<job>/ (state, output, log, live status): nothing is shared;
#  - the python env is reinstalled if a stop wiped it (/venv and /hf live on the container disk);
#  - a watchdog stops the pod at the deadline; the painter pauses 10 min before it with its state saved;
#  - the pod is NOT stopped at the end if /workspace/KEEP exists (another job follows).
# Usage: md_on_pod.sh <deadline-epoch> <job> <src.png> <layout.png|-> <lora> [steps] [src-cell] [extra mdpaint args...]
set -u
DEADLINE="$1"; JOB="$2"; SRCP="$3"; LAYP="$4"; LORA="$5"; STEPS="${6:-25}"; CELLPX="${7:-600}"; shift 7 2>/dev/null || shift $#
J=/workspace/md/$JOB; mkdir -p "$J"
LOG=$J/run.log
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
stop_pod() {
  echo "GUARD $(date -u +%H:%M:%S) stopping pod: $1" >> "$LOG"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" https://api.runpod.io/graphql
}
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do sleep 30; done; stop_pod "deadline reached" ) > "$J/watchdog.log" 2>&1 &

if [ ! -x /venv/bin/python ]; then
  echo "SETUP $(date -u +%H:%M:%S)" >> "$LOG"
  ( cd /workspace && { [ -d ai-toolkit ] || git clone -q https://github.com/ostris/ai-toolkit.git; } && cd ai-toolkit \
    && python3 -m venv /venv \
    && /venv/bin/pip install -q --no-cache-dir torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130 \
    && /venv/bin/pip install -q -r requirements.txt && /venv/bin/pip install -q hf_transfer ) > "$J/setup.log" 2>&1 \
    || { stop_pod "setup failed"; exit 1; }
  echo "SETUP DONE $(date -u +%H:%M:%S)" >> "$LOG"
fi

export HF_HOME=/hf HF_XET_HIGH_PERFORMANCE=1 LIVE=$J/live
ln -sfn "$J/live" /workspace/live_current     # the laptop dashboard follows the running job
LAYARG=(); [ "$LAYP" != "-" ] && LAYARG=(--layout "$LAYP")
cd /workspace/tiles
/venv/bin/python mdpaint.py --src "$SRCP" "${LAYARG[@]}" --lora "$LORA" --out "$J/canvas_full.png" \
  --steps "$STEPS" --src-cell "$CELLPX" --state "$J/state" --deadline "$DEADLINE" "$@" >> "$LOG" 2>&1
RC=$?
case $RC in
  0) echo "MD FINISHED $(date -u +%H:%M:%S)" >> "$LOG" ;;
  3) echo "MD PAUSED $(date -u +%H:%M:%S) (resume: run this again with a later deadline)" >> "$LOG" ;;
  *) echo "MD FAILED rc=$RC" >> "$LOG"; sleep 600; stop_pod "paint failed (10 min grace)"; exit 1 ;;
esac
[ -f /workspace/KEEP ] && exit 0
sleep 1200; stop_pod "job $JOB ended, grace over"
