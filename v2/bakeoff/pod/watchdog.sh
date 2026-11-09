#!/bin/bash
# The pod's start command (v2/bakeoff/runner.py pod_spec): before anything else, a watchdog that TERMINATES this pod
# at its deadline whatever happens (a stopped pod would keep billing its disk). The deadline is the pod's start plus
# ISOLUX_CAP_S (the job's approved time cap); the laptop moves it only by writing a new epoch to /workspace/DEADLINE
# when the next approved job of the session starts. Then the image's own start (sshd) runs.
mkdir -p /workspace
BOOT=$(date +%s)
echo $((BOOT + ISOLUX_CAP_S)) > /workspace/DEADLINE
(
  while true; do
    D=$(cat /workspace/DEADLINE 2>/dev/null); D=${D:-$((BOOT + ISOLUX_CAP_S))}
    [ "$(date +%s)" -ge "$D" ] && break
    sleep 10
  done
  echo "WATCHDOG $(date -u +%H:%M:%S) deadline reached: terminating"
  for i in 1 2 3 4 5 6 7 8; do
    curl -s -m 30 -H "Content-Type: application/json" -H "Authorization: Bearer $RUNPOD_API_KEY" \
      -d "{\"query\":\"mutation { podTerminate(input:{podId:\\\"$RUNPOD_POD_ID\\\"}) }\"}" https://api.runpod.io/graphql && break
    sleep 15
  done
) > /watchdog.log 2>&1 &
if [ -x /start.sh ]; then exec /start.sh; fi
mkdir -p ~/.ssh && echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
service ssh start || /usr/sbin/sshd
sleep infinity
