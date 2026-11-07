#!/bin/bash
# Rent an H100 (US first), upload files, start a job, and keep copying results back until the pod is gone.
# Usage: launch.sh <name> <hours deadline> <local results dir> <remote results glob> <script> <script args...> -- <files to upload...>
# Writes $SP/<name>.ssh, <name>.id, <name>.meta. Uploads go to /workspace/ (rsync with resume).
set -e
SP="${POD_DIR:-$HOME/.cache/isometric-luxembourg/pods}"; mkdir -p "$SP"   # ssh configs and pod ids
NAME=$1; HOURS=$2; RES=$3; RGLOB=$4; SCRIPT=$5; shift 5
ARGS=(); while [ "$1" != "--" ]; do ARGS+=("$1"); shift; done; shift
FILES=("$@")
ok=0
for cc in US CA DE NL SE; do
  for g in "NVIDIA H100 80GB HBM3" "NVIDIA H100 NVL" "NVIDIA H200"; do
    if runpodctl pod create --name "iso-lux-$NAME" --image runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404 --gpu-id "$g" \
        --cloud-type SECURE --country-code $cc --public-ip --container-disk-in-gb 150 --volume-in-gb 40 --ports 22/tcp \
        --wait --wait-timeout 7m > $SP/$NAME.json 2> $SP/$NAME.err && python3 -I -c "import json;json.load(open('$SP/$NAME.json'))" 2>/dev/null; then
      ok=1; break 2
    fi
  done
done
[ $ok = 1 ] || { echo "NO GPU AVAILABLE"; exit 1; }
read id cost ip port <<< "$(python3 -I -c "
import json;d=json.load(open('$SP/$NAME.json'));s=d['ssh'];print(d['id'],d['costPerHr'],s['ip'],s['port'])")"
echo $id > $SP/$NAME.id; echo "$cost $(date +%s)" > $SP/$NAME.meta
sed -e "s/^Host .*/Host pod/" -e "s/HostName .*/HostName $ip/" -e "s/Port .*/Port $port/" $SP/ssh_full > $SP/$NAME.ssh
echo "pod $id \$$cost/h $ip:$port"
for f in "${FILES[@]}" "$SCRIPT"; do
  for i in 1 2 3 4; do rsync --partial --timeout=90 -e "ssh -F $SP/$NAME.ssh" "$f" pod:/workspace/ 2>/dev/null && break; sleep 5; done
done
DL=$(( $(date +%s) + HOURS * 3600 ))
ssh -F $SP/$NAME.ssh pod "chmod +x /workspace/$(basename $SCRIPT); setsid nohup /workspace/$(basename $SCRIPT) $DL ${ARGS[*]} > /workspace/guard.log 2>&1 < /dev/null &"
mkdir -p "$RES"
# results copier, detached: every 3 min until the pod is gone
nohup bash -c "while ssh -F $SP/$NAME.ssh -o ConnectTimeout=20 pod true 2>/dev/null; do
  rsync -a --timeout=120 -e 'ssh -F $SP/$NAME.ssh' 'pod:$RGLOB' '$RES/' 2>/dev/null
  scp -q -F $SP/$NAME.ssh pod:/workspace/train.log pod:/workspace/guard.log '$RES/' 2>/dev/null
  sleep 180; done; echo pod gone \$(date) >> '$RES/pull.log'" > /dev/null 2>&1 &
echo "started $NAME; deadline $(date -r $DL)"
