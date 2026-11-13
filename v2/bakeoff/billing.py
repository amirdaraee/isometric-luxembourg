"""Reconciling the ledger with RunPod's own billing (read-only API), spec ledger.md rule 4.

RunPod's billing endpoint (GET rest.runpod.io/v1/billing/pods, grouped by pod) gives the amount billed per pod and
hour. The pods created by the runner are known by their ids (<data>/v2/_shared/bakeoff/pods/*.json), so the billed
amount of exactly those pods is compared with the ledger's spend events of provider "runpod" for this goal.
"""
from __future__ import annotations

import datetime
import json
import urllib.request

from v2.bakeoff import runner
from v2.bakeoff.jobs import BY_ID
from v2.ledger.ledger import Ledger


def billed(pod_ids, start: str) -> dict:
    url = f"https://rest.runpod.io/v1/billing/pods?bucketSize=hour&grouping=podId&startTime={start}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {runner._runpod_key()}",
                                               "User-Agent": "isolux-v2-bakeoff/1.0"})
    rows = json.loads(urllib.request.urlopen(req, timeout=60).read())
    out = {p: 0.0 for p in pod_ids}
    for r in rows:
        if r.get("podId") in out:
            out[r["podId"]] += float(r["amount"])
    return out


def reconcile(record=False) -> int:
    L = Ledger()
    sessions = [json.loads(p.read_text()) for p in sorted(runner.state_dir().glob("*.json"))]
    if not sessions:
        print("no pods were created")
        return 0
    first = min(s["created"] for s in sessions)
    start = datetime.datetime.fromtimestamp(first - 3600, datetime.timezone.utc).strftime("%Y-%m-%dT%H:00:00Z")
    b = billed([s["pod_id"] for s in sessions], start)
    total = 0.0
    for s in sessions:
        led = sum(h["usd"] for h in s.get("history", []))
        total += b[s["pod_id"]]
        print(f"pod {s['pod_id']} ({s['name']}): billed ${b[s['pod_id']]:.4f}, ledger ${led:.4f}  jobs "
              + ", ".join(f"{h['id']} ${h['usd']:.2f}" for h in s.get("history", [])))
    goals = sorted({j.goal for j in BY_ID.values()})           # every budget line the runner's jobs are paid from
    ledger_usd = round(sum(e["usd"] for e in L.events if e["type"] == "spend" and e["provider"] == "runpod" and e["goal"] in goals), 4)
    print(f"RunPod billed ${total:.4f} for these pods; the ledger has ${ledger_usd:.4f} for {', '.join(goals)}")
    how = "billing lines per pod"
    # RunPod publishes a pod's billing lines over some hours after it ends (9 Nov 2026: 1,685 of a pod's 2,145
    # seconds were listed an hour after it was terminated, while the balance already held the whole charge). Its
    # balance is complete at once: what the account had before the first pod created here, less what it has now.
    # While the lines add up to less than that drop (and no pod of ours is running), the balance is the figure.
    before = [s.get("balance_before") for s in sessions if s.get("balance_before") is not None]
    if before and not runner.my_pods():
        now = runner.balance_now()
        drop = max(before) - now
        print(f"account balance: ${max(before):.4f} before the first pod, ${now:.4f} now: ${drop:.4f}")
        if total < drop - 0.01:
            how = (f"account balance, ${max(before):.4f} before the first pod and ${now:.4f} now; the billing lines "
                   f"list ${total:.4f} so far and are still being published; any other charge on the account in "
                   f"between is in this figure")
            total = drop
            print(f"the billing lines are not complete yet: reconciling by the balance, ${total:.4f}")
    elif any(b[s["pod_id"]] == 0 for s in sessions):
        print("the billing lines are not published yet and no balance was kept: reconcile again later")
        return 1
    if record:
        ev = L.reconcile("runpod", f"{start}..{datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} "
                         f"(pods {', '.join(s['pod_id'] for s in sessions)}; by {how})", total)
        print("recorded:", ev)
        return 0 if ev["ok"] else 1
    return 0
