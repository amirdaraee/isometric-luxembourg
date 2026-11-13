#!/usr/bin/env bash
# On the pod: run one job of the bake-off from its bundle (/workspace/job/<JOB>/: this folder as pod/, the inputs,
# job.json), write its exit code to /workspace/state/<JOB>.rc. The laptop (v2/bakeoff/runner.py) copies the bundle,
# starts this, copies /workspace/out/<JOB>/ back while it runs, and terminates the pod. The pod's watchdog
# (watchdog.sh) terminates it at the job's time cap whatever happens here.
# usage: run.sh <job id>
set -u
JOB="$1"
J=/workspace/job/$JOB
OUT=/workspace/out/$JOB
mkdir -p /workspace/state /workspace/logs "$OUT"
rm -f "/workspace/state/$JOB.rc"
export HF_HOME=/hf HF_XET_HIGH_PERFORMANCE=1 HF_HUB_ENABLE_HF_TRANSFER=1
V1=/workspace/lora/luxembourg-ink-v2_000002000.safetensors
NEW=/workspace/lora/luxembourg-ink-unshadowed.safetensors
LIGHT=/workspace/lora/Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors
paint() {   # paint <lora> <seeds> [<seed step per input>]
  bash "$J/pod/setup.sh" paint && /venv/bin/python "$J/pod/paint.py" --inputs "$J/inputs" --out "$OUT" \
    --prompt-file "$J/prompt.txt" --lora "$1" --lightning "$LIGHT" --seeds "$2" --seed-step "${3:-0}" --steps 8
}
train() {   # train <steps> <sample_every>
  bash "$J/pod/setup.sh" train || return 1
  if [ ! -d /workspace/data ]; then      # C2 on the pilot's pod finds the dataset (and the checkpoint) in place
    tar --no-same-owner -xf /workspace/job/C2p/dataset.tar -C /workspace || return 1
  fi
  echo "data: $(ls /workspace/data/*.png | wc -l) targets, $(ls /workspace/control/*.png | wc -l) controls, $(ls /workspace/layout/*.png | wc -l) layouts, $(ls /workspace/data/*.txt | wc -l) captions"
  sed -e "s/steps: 2000/steps: $1/" -e "s/sample_every: 600/sample_every: $2/" "$J/pod/c2_train.yaml" > "/workspace/$JOB.yaml"
  [ "$JOB" = C2 ] && sed -i "s/skip_first_sample: false/skip_first_sample: true/" "/workspace/$JOB.yaml"
  T=/workspace/output/luxembourg-ink-unshadowed
  mkdir -p "$T" "$OUT/samples"
  # samples and checkpoints are copied to the job's output as they appear, so a run cut by the time cap keeps them
  ( while sleep 45; do cp -u "$T"/samples/* "$OUT/samples/" 2>/dev/null; cp -u "$T"/*.safetensors "$OUT/" 2>/dev/null; done ) &
  COPIER=$!
  date +%s > "$OUT/train_start"
  ( cd /workspace/ai-toolkit && /venv-train/bin/python run.py "/workspace/$JOB.yaml" ); TR=$?
  date +%s > "$OUT/train_end"
  kill $COPIER 2>/dev/null
  cp -u "$T"/samples/* "$OUT/samples/" 2>/dev/null
  cp -u "$T"/*.safetensors "$T"/optimizer.pt "$OUT/" 2>/dev/null
  [ $TR = 0 ] && cp -f "$T/luxembourg-ink-unshadowed.safetensors" "$NEW"
  ls -la "$OUT"
  return $TR
}
case "$JOB" in
  B1)  bash "$J/pod/setup.sh" t2i && /venv/bin/python "$J/pod/b1_materials.py" --spec "$J/materials.json" --out "$OUT" ;;
  B2)  if [ -f "$NEW" ]; then paint "$NEW" 1867,1868; else paint "$V1" 1867,1868; fi ;;
  C1p|C1) paint "$V1" 1867,1868 ;;
  C2p) train 200 200 ;;
  C2)  train 2000 600 ;;
  C3)  paint "$NEW" 1867 ;;
  C4)  if [ -f "$NEW" ]; then paint "$NEW" 1867,1868; else paint "$V1" 1867,1868; fi ;;
  K1)  paint "$V1" 1867,1868 2 ;;
  *) echo "unknown job $JOB"; false ;;
esac
RC=$?
echo "JOB $JOB ended rc=$RC $(date -u +%H:%M:%S)"
echo $RC > "/workspace/state/$JOB.rc"
