"""Starting a paid job: ledger first, live price second, a hard time cap always (spec ledger.md; V1_RETRO P9).

    authorise(job)   Ledger.authorise(<the job's quote>): refused unless the owner approved that quote and it fits
                     the goal's cap. Then the provider's price now must not be above the quoted one (else re-quote).
    pod_spec(job)    the RunPod pod the job runs on: GPU, image, disk, and a start command whose first act is a
                     watchdog that stops the pod at cap_h whatever happens (so the cost is <= cap_h x price).
    launch(job)      authorise, then create the pod (the only call here that spends). --dry-run prints the spec.

Only read-only calls are made before authorise() passes. The pod "luxembourgish-asr-pilot" (another project) is
never listed, touched or stopped: every call names this job's own pod id.
"""
from __future__ import annotations

import json
import tomllib
import urllib.request
from pathlib import Path

from v2.bakeoff.jobs import BY_ID, GOAL, Job
from v2.ledger.ledger import Ledger, LedgerRefusal

FOREIGN_PODS = {"luxembourgish-asr-pilot"}
IMAGE = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
GPU_IDS = {"H100 SXM": "NVIDIA H100 80GB HBM3", "H100 PCIe": "NVIDIA H100 PCIe", "A100 SXM": "NVIDIA A100-SXM4-80GB",
           "H200 SXM": "NVIDIA H200", "L40S": "NVIDIA L40S"}


def quote_of(job: Job, ledger: Ledger | None = None) -> str | None:
    """The ledger quote id recorded for this job (the latest one), or None."""
    L = ledger or Ledger()
    qs = [e for e in L.events if e["type"] == "quote" and e["goal"] == GOAL and e["job"] == job.ledger_job()]
    return qs[-1]["id"] if qs else None


def record_quotes(ledger: Ledger | None = None) -> list:
    """Record every job's quote in the ledger, once (quote events only: approving is the owner's)."""
    L = ledger or Ledger()
    out = []
    for j in BY_ID.values():
        if quote_of(j, L) is None:
            out.append(L.quote(GOAL, j.provider, j.ledger_job(), j.worst_usd, j.ledger_note()))
    return out


def _runpod_key() -> str:
    cfg = tomllib.loads((Path.home() / ".runpod" / "config.toml").read_text())
    for k, v in cfg.items():
        if isinstance(v, dict) and "api_key" in v:
            return v["api_key"]
        if k in ("api_key", "apikey"):
            return v
    raise RuntimeError("no RunPod key in ~/.runpod/config.toml")


def _gql(query: str, variables=None) -> dict:
    req = urllib.request.Request("https://api.runpod.io/graphql", data=json.dumps({"query": query, "variables": variables or {}}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {_runpod_key()}",
                                          "User-Agent": "isolux-v2-bakeoff/1.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if d.get("errors"):
        raise RuntimeError(f"RunPod: {d['errors']}")
    return d["data"]


def live_price(job: Job) -> float:
    """The community on-demand price of the job's GPU now (read-only)."""
    d = _gql("query { gpuTypes { id communityPrice } }")
    gid = GPU_IDS[job.gpu]
    for g in d["gpuTypes"]:
        if g["id"] == gid:
            return float(g["communityPrice"])
    raise RuntimeError(f"no price for {gid}")


def authorise(job: Job, ledger: Ledger | None = None, price_now: float | None = None):
    L = ledger or Ledger()
    qid = quote_of(job, L)
    if qid is None:
        raise LedgerRefusal(f"{job.id}: no quote recorded (python -m v2.bakeoff quote --record)")
    for d in job.after:
        dq = quote_of(BY_ID[d], L)
        if dq is None or not any(e["type"] == "spend" and e["quote"] == dq for e in L.events):
            raise LedgerRefusal(f"{job.id}: needs {d} done first (its spend recorded and its result checked)")
    q = L.authorise(qid)
    p = live_price(job) if price_now is None else price_now
    if p > job.price_h + 1e-9:
        raise LedgerRefusal(f"{job.id}: {job.gpu} costs ${p}/h now, quoted ${job.price_h}/h: re-quote")
    return q


def pod_spec(job: Job, script: str) -> dict:
    """The pod: the watchdog stops it at cap_h (RunPod's own podStop via runpodctl, with the pod's id) before
    anything else starts; the job script runs after it."""
    cap_s = int(job.cap_h * 3600)
    start = (f"bash -lc '(sleep {cap_s} && runpodctl stop pod $RUNPOD_POD_ID) & "
             f"cd /workspace && {script}; runpodctl stop pod $RUNPOD_POD_ID'")
    return {"name": f"isolux-v2-{job.id.lower()}", "imageName": IMAGE, "gpuTypeId": GPU_IDS[job.gpu], "gpuCount": 1,
            "cloudType": "COMMUNITY", "containerDiskInGb": 60, "volumeInGb": 120, "volumeMountPath": "/workspace",
            "dockerArgs": start, "ports": "22/tcp", "env": [{"key": "ISOLUX_JOB", "value": job.id}]}


def launch(job_id: str, script: str, dry_run: bool = True):
    job = BY_ID[job_id]
    spec = pod_spec(job, script)
    assert spec["name"] not in FOREIGN_PODS
    if dry_run:
        return {"dry_run": True, "job": job.id, "pod": spec, "worst_usd": job.worst_usd}
    authorise(job)
    d = _gql("mutation($input: PodFindAndDeployOnDemandInput) { podFindAndDeployOnDemand(input: $input) { id name } }",
             {"input": spec})
    return {"job": job.id, "pod": d["podFindAndDeployOnDemand"], "worst_usd": job.worst_usd}
