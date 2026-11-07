#!/bin/bash
# Laptop side: copy the day showcase and each finished variant; feed the live dashboard with the current one.
SP="${POD_DIR:-$HOME/.cache/isometric-luxembourg/pods}"
R=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$R/data/work/tiles/v2; mkdir -p $OUT; DST=$R/web/public/live
C="ssh -F $SP/v2.ssh -o ConnectTimeout=20"
while $C pod true 2>/dev/null; do
  [ -f $OUT/day.png ] || { $C pod "grep -q 'PAINT FINISHED' /workspace/paint.log" 2>/dev/null && scp -q -F $SP/v2.ssh pod:/workspace/live/canvas_full.png $OUT/day.png; }
  for t in night winter winter_night golden autumn spring; do
    [ -f $OUT/$t.png ] || { $C pod "grep -q '^$t done' /workspace/variants.log" 2>/dev/null && scp -q -F $SP/v2.ssh pod:/workspace/var_$t/canvas_full.png $OUT/$t.png; }
  done
  if [ -f $OUT/day.png ]; then   # dashboard follows the variant being painted
    for f in status.json canvas.jpg last_in.jpg last_out.jpg; do
      scp -q -F $SP/v2.ssh "pod:/workspace/live_current/$f" "$DST/$f.part" 2>/dev/null && mv "$DST/$f.part" "$DST/$f"
    done
  fi
  $C pod "grep -q 'ALL VARIANTS DONE' /workspace/variants.log" 2>/dev/null && [ -f $OUT/spring.png ] && break
  sleep 45
done
echo "fetch done $(date)" >> $OUT/fetch.log
