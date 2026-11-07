#!/bin/bash
# After the day drawings: about 50 pairs per target, rotating through the 40 old + 59 new day drawings.
cd "$(dirname "$0")/../.."
OLD=data/work/style/examples_openai
NEW=data/work/style/detail/drawn
OUT=data/work/night/transforms
PY=pipeline/.venv/bin/python
CAP=24   # $ for all night + transform pairs together (40 night pairs already ~ $2.5)
mkdir -p $OUT
mapfile_old=($(ls $OLD/*.png | sort))
mapfile_new=($(ls $NEW/*.png | sort))
pick() {  # $1 = offset; 25 old + 25 new, every other one shifted by offset
  local o=$1; local list=()
  for i in $(seq 0 24); do list+=("${mapfile_old[$(( (i * 8 / 5 + o) % ${#mapfile_old[@]} ))]}"); done
  for i in $(seq 0 24); do list+=("${mapfile_new[$(( (i * 59 / 25 + o) % ${#mapfile_new[@]} ))]}"); done
  printf '%s\n' "${list[@]}" | sort -u
}
# all six targets in parallel (the spend log is locked); each stops at the shared cap
$PY pipeline/night/transform_teacher.py night $OUT $CAP $(pick 0 | grep detail | head -25) > $OUT/log_night.txt 2>&1 &
$PY pipeline/night/transform_teacher.py golden $OUT $CAP $(pick 1) > $OUT/log_golden.txt 2>&1 &
$PY pipeline/night/transform_teacher.py winter $OUT $CAP $(pick 2) > $OUT/log_winter.txt 2>&1 &
$PY pipeline/night/transform_teacher.py winter_night $OUT $CAP $(pick 3) > $OUT/log_winter_night.txt 2>&1 &
$PY pipeline/night/transform_teacher.py autumn $OUT $CAP $(pick 4) > $OUT/log_autumn.txt 2>&1 &
$PY pipeline/night/transform_teacher.py spring $OUT $CAP $(pick 5) > $OUT/log_spring.txt 2>&1 &
wait
tail -n 1 $OUT/log_*.txt
echo ALL TRANSFORMS DONE
