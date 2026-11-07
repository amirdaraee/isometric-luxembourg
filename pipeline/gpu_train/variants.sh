#!/bin/bash
# On the style pod after the day showcase is painted: convert it to night, winter, winter night, golden hour,
# autumn and spring with the light model, window by window. Stops the pod when done (or at the deadline).
DEADLINE="$1"; STEPS="${2:-15}"; ONLY="${3:-night winter winter_night golden autumn spring}"
export $(tr "\0" "\n" < /proc/1/environ | grep -E "^RUNPOD_(API_KEY|POD_ID)=" | xargs)
stop_pod() {
  echo "GUARD $(date -u +%H:%M:%S) stopping pod: $1"
  curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -d "{\"query\":\"mutation { podStop(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) { id desiredStatus } }\"}" https://api.runpod.io/graphql
  echo
}
( while [ "$(date +%s)" -lt "$DEADLINE" ]; do sleep 30; done; stop_pod "deadline reached" ) > /workspace/var_watchdog.log 2>&1 &
# reinstall the python env if the pod was stopped (container disk is wiped on stop)
if [ ! -x /venv/bin/python ]; then
  echo "SETUP $(date -u +%H:%M:%S)" >> /workspace/variants.log
  ( cd /workspace/ai-toolkit && python3 -m venv /venv \
    && /venv/bin/pip install -q --no-cache-dir torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130 \
    && /venv/bin/pip install -q -r requirements.txt && /venv/bin/pip install -q hf_transfer ) > /workspace/setup.log 2>&1 \
    || { stop_pod "setup failed"; exit 1; }
  echo "SETUP DONE $(date -u +%H:%M:%S)" >> /workspace/variants.log
fi
# wait for the day painting
[ -f /workspace/day_v2.png ] || while ! grep -q "PAINT FINISHED" /workspace/paint.log 2>/dev/null; do
  grep -q "PAINT FAILED" /workspace/paint.log 2>/dev/null && { stop_pod "day paint failed"; exit 1; }
  sleep 20
done
[ -f /workspace/day_v2.png ] || cp /workspace/live/canvas_full.png /workspace/day_v2.png
export HF_HOME=/hf HF_XET_HIGH_PERFORMANCE=1 SRC=/workspace/day_v2.png
L=/workspace/luxembourg-light-v1.safetensors
declare -A P=(
 [night]="Convert the outlined section to the <isometric luxembourg ink> style at night, warm and cozy, with no sun shadows, matching the surrounding image."
 [golden]="Convert the outlined section to the <isometric luxembourg ink> style at golden hour, matching the surrounding image."
 [winter]="Convert the outlined section to the <isometric luxembourg ink> style on a snowy winter day, matching the surrounding image."
 [winter_night]="Convert the outlined section to the <isometric luxembourg ink> style on a snowy winter night, with no sun shadows, matching the surrounding image."
 [autumn]="Convert the outlined section to the <isometric luxembourg ink> style in autumn, matching the surrounding image."
 [spring]="Convert the outlined section to the <isometric luxembourg ink> style in spring, matching the surrounding image.")
W=$(/venv/bin/python -c "from PIL import Image; print(Image.open('/workspace/day_v2.png').width)")
CELL=$(( W / 10 ))   # 10x10 cells, 81 windows per version
for t in $ONLY; do
  mkdir -p /workspace/var_$t
  ln -sfn /workspace/var_$t /workspace/live_current
  LIVE=/workspace/var_$t PROMPT="${P[$t]}" /venv/bin/python /workspace/tiler.py "$L" "$STEPS" "$CELL" > /workspace/var_$t.log 2>&1 \
    && echo "$t done $(date -u +%H:%M:%S)" >> /workspace/variants.log || echo "$t FAILED" >> /workspace/variants.log
done
echo "ALL VARIANTS DONE $(date -u +%H:%M:%S)" >> /workspace/variants.log
sleep 900; stop_pod "variants done, grace over"
