#!/bin/bash
# On the finished light pod: convert a 3x3-cell day patch to night / golden / winter / winter_night, window by window.
export HF_HOME=/hf SRC=/workspace/patch_day.png
L=$(ls -t /workspace/output/luxembourg-light-v1/*.safetensors | head -1)
declare -A P=(
 [night]="Convert the outlined section to the <isometric luxembourg ink> style at night, warm and cozy, with no sun shadows, matching the surrounding image."
 [golden]="Convert the outlined section to the <isometric luxembourg ink> style at golden hour, matching the surrounding image."
 [winter]="Convert the outlined section to the <isometric luxembourg ink> style on a snowy winter day, matching the surrounding image."
 [winter_night]="Convert the outlined section to the <isometric luxembourg ink> style on a snowy winter night, with no sun shadows, matching the surrounding image.")
for t in night golden winter winter_night; do
  LIVE=/workspace/lt_$t PROMPT="${P[$t]}" /venv/bin/python /workspace/tiler.py "$L" 25 512 > /workspace/lt_$t.log 2>&1
done
echo LIGHT TEST DONE > /workspace/lt_done
