#!/bin/bash
# Rent an H100/H200 (US first), upload files, start a job, and keep copying results back until the pod is gone.
# Usage: launch.sh <name> <hours deadline> <local results dir> <remote results glob> <script> <script args...> -- <files to upload...>
# Writes $SP/<name>.ssh, <name>.known_hosts, <name>.id, <name>.meta. Uploads go to /workspace/ (rsync with resume).
# When the pod is deleted, delete <name>.known_hosts too (a new pod gets a fresh one here anyway).
# Env: OFFERS = "cloud:gpu-id" pairs to try in order (default: the cheapest first, community H100 at the time of
#      writing; community pods need a public IP); COUNTRIES (default "US CA DE NL SE").
# For a painter session (jobs sent one by one from the laptop with gpu_train/backend.py):
#   launch.sh paint 3 data/work/city/pod '/workspace/md/*/run.log' pipeline/gpu_train/pod_session.sh -- \
#       pipeline/gpu_train/md_on_pod.sh
set -e
SP="${POD_DIR:-$HOME/.cache/isometric-luxembourg/pods}"; mkdir -p "$SP"   # ssh configs and pod ids
NAME=$1; HOURS=$2; RES=$3; RGLOB=$4; SCRIPT=$5; shift 5
ARGS=(); while [ "$1" != "--" ]; do ARGS+=("$1"); shift; done; shift
FILES=("$@")
OFFERS="${OFFERS:-COMMUNITY:NVIDIA_H100_80GB_HBM3 SECURE:NVIDIA_H100_80GB_HBM3 COMMUNITY:NVIDIA_H200 SECURE:NVIDIA_H200 SECURE:NVIDIA_H100_NVL}"
ok=0
for cc in ${COUNTRIES:-US CA DE NL SE}; do
  for o in $OFFERS; do
    cloud=${o%%:*}; g=${o#*:}; g=${g//_/ }
    if runpodctl pod create --name "iso-lux-$NAME" --image runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404 --gpu-id "$g" \
        --cloud-type $cloud --country-code $cc --public-ip --container-disk-in-gb 150 --volume-in-gb 40 --ports 22/tcp \
        --wait --wait-timeout 7m > $SP/$NAME.json 2> $SP/$NAME.err && python3 -I -c "import json;json.load(open('$SP/$NAME.json'))['ssh']" 2>/dev/null; then
      ok=1; break 2
    fi
    # a pod that was created but never answered is still billed: remove it (only this launch's, by its exact name)
    for pid in $(runpodctl pod list --all --name "iso-lux-$NAME" -o json 2>/dev/null | python3 -I -c "
import sys,json
d=json.load(sys.stdin); d=d if isinstance(d,list) else d.get('pods',[])
print(' '.join(p['id'] for p in d if p.get('name')=='iso-lux-$NAME'))"); do
      runpodctl pod delete "$pid" > /dev/null 2>&1 || true
    done
  done
done
[ $ok = 1 ] || { echo "NO GPU AVAILABLE"; exit 1; }
read id cost ip port <<< "$(python3 -I -c "
import json;d=json.load(open('$SP/$NAME.json'));s=d['ssh'];print(d['id'],d['costPerHr'],s['ip'],s['port'])")"
echo $id > $SP/$NAME.id; echo "$cost $(date +%s)" > $SP/$NAME.meta
if [ -f $SP/ssh_full ]; then
  sed -e "s/^Host .*/Host pod/" -e "s/HostName .*/HostName $ip/" -e "s/Port .*/Port $port/" $SP/ssh_full > $SP/$NAME.ssh
else
  # trust on first use, per pod: a new pod starts with a fresh known_hosts file, so the first connection records
  # its key and every later ssh/scp/rsync (all through this config, -F) is checked against it
  rm -f $SP/$NAME.known_hosts
  printf 'Host pod\n  HostName %s\n  Port %s\n  User root\n  IdentityFile ~/.ssh/id_ed25519\n  StrictHostKeyChecking accept-new\n  UserKnownHostsFile %s\n' \
    "$ip" "$port" "$SP/$NAME.known_hosts" > $SP/$NAME.ssh
fi
echo "pod $id \$$cost/h $ip:$port"
for f in "${FILES[@]}" "$SCRIPT"; do
  for i in 1 2 3 4; do rsync --partial --timeout=90 -e "ssh -F $SP/$NAME.ssh" "$f" pod:/workspace/ 2>/dev/null && break; sleep 5; done
done
DL=$(( $(date +%s) + $(python3 -I -c "print(int(float('$HOURS') * 3600))") ))
echo "$cost $(date +%s) $DL" > $SP/$NAME.meta
ssh -F $SP/$NAME.ssh pod "chmod +x /workspace/*.sh; setsid nohup /workspace/$(basename $SCRIPT) $DL ${ARGS[*]} > /workspace/guard.log 2>&1 < /dev/null &"
mkdir -p "$RES"
# results copier, detached: every 3 min until the pod is gone
nohup bash -c "while ssh -F $SP/$NAME.ssh -o ConnectTimeout=20 pod true 2>/dev/null; do
  rsync -a --timeout=120 -e 'ssh -F $SP/$NAME.ssh' 'pod:$RGLOB' '$RES/' 2>/dev/null
  scp -q -F $SP/$NAME.ssh pod:/workspace/train.log pod:/workspace/guard.log pod:/workspace/session.log '$RES/' 2>/dev/null
  sleep 180; done; echo pod gone \$(date) >> '$RES/pull.log'" > /dev/null 2>&1 &
echo "started $NAME; deadline $(date -r $DL)"
