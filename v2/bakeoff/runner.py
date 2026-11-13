"""Running a paid job: ledger first, live price second, a hard time cap always (spec ledger.md; V1_RETRO P9).

    authorise(job)   Ledger.authorise(<the job's quote>): refused unless the owner approved that quote and it fits
                     the goal's cap. Then the provider's price now must not be above the quoted one (else re-quote).
    pod_spec(job)    the RunPod pod the job runs on: GPU, image, disk, and a start command whose first act is a
                     watchdog (pod/watchdog.sh) that TERMINATES the pod at the job's time cap whatever happens.
    run(job)         the whole life of one job: authorise, create the pod (or take over an open session's pod),
                     check a new pod in its first minute (pod/preflight.sh: the GPU, the image's torch, the disk,
                     Hugging Face) and terminate it at once if that fails, copy the job's bundle to it, start it, copy its results back while it runs, record the measured
                     spend in the ledger, terminate the pod. Without go=True it only prints the pod it would start.

A job that fails before it has made anything (a setup fault, a script that does not start) is not ended at once:
its pod is held for HOLD_S seconds, its own deadline pulled in to that, so the fault can be fixed and the same job
started again in place with `run <job> --go --on <session>`, on the same quote and within its own time cap (two
quotes were used up on 9 and 10 Nov 2026 by setup faults that a restart in place would have cured). Unless it is
started again the pod terminates itself when the hold ends, and `end` records the spend.

Sessions. A pod can serve several jobs one after the other (a "session"), so the 40 GB model is downloaded once:
`run(job, keep=True)` leaves the pod up after the job; `run(next, on=<session>)` first closes the job before it
(its spend is recorded: from its start to this moment, so the time spent checking its results is its own), then
authorises the next job and moves the pod's deadline to now + that job's cap. Each job is so held to its own
approved worst case: the pod terminates itself at the open job's deadline if the laptop never comes back.
`end(session)` terminates the pod and records the open job's spend.

Money. A job's spend = its seconds on the pod x (the pod's price per hour + its disk's), measured on the laptop's
clock from the create call (or the job before it closing) to the terminate call (or the next job starting); the
deadline is set so that this can never pass the quote's worst case. `reconcile()` compares the ledger with RunPod's
own billing (read-only).

Only this module's own pods are ever touched, each by the id RunPod returned when it was created here. The pod
"luxembourgish-asr-pilot" (another project) is never stopped or deleted, nor any pod not created here.
"""
from __future__ import annotations

import base64
import json
import subprocess
import time
import tomllib
import urllib.request
from pathlib import Path

from v2.bakeoff.jobs import BY_ID, JOBS, Job
from v2.config import v2_data
from v2.ledger.ledger import Ledger, LedgerRefusal

FOREIGN_PODS = {"luxembourgish-asr-pilot"}
IMAGE = "runpod/pytorch:1.0.3-cu1281-torch291-ubuntu2404"          # v1's (pipeline/gpu_train/launch.sh)
GPU_IDS = {"H100 SXM": "NVIDIA H100 80GB HBM3", "H100 PCIe": "NVIDIA H100 PCIe", "A100 SXM": "NVIDIA A100-SXM4-80GB",
           "H200 SXM": "NVIDIA H200", "L40S": "NVIDIA L40S", "H100 NVL": "NVIDIA H100 NVL"}
# The same chip in RunPod's other listing may be taken in place of the quoted one, the cheaper first, and only if its
# price is not above the quoted one (owner, 10 Nov 2026: "a cheaper same-chip listing (H100 NVL, or SXM) at or below
# the quoted hourly price is fine"). The time caps stay, so no quote's worst case can be passed.
SAME_CHIP = {"H100 SXM": ("H100 SXM", "H100 NVL")}
PRICE_FIELD = {"community": "communityPrice", "secure": "securePrice"}
HOLD_S = 420                              # how long a pod is held for a restart after a job failed with nothing made
DISK_GB = 150
DISK_USD_GB_H = 0.10 / 730                # RunPod: $0.10 per GB a month for a running pod's disk
POD = Path(__file__).resolve().parent / "pod"
COUNTRIES = ("US", "CA", None)            # v1: Hugging Face downloads stalled outside North America


def state_dir() -> Path:
    d = v2_data() / "_shared" / "bakeoff" / "pods"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------------------------- ledger side
def quote_of(job: Job, ledger: Ledger | None = None) -> str | None:
    """The ledger quote id recorded for this job (the latest one), or None."""
    L = ledger or Ledger()
    qs = [e for e in L.events if e["type"] == "quote" and e["goal"] == job.goal and e["job"] == job.ledger_job()]
    return qs[-1]["id"] if qs else None


def record_quotes(ledger: Ledger | None = None) -> list:
    """Record every job's quote in the ledger, once (quote events only: approving is the owner's)."""
    L = ledger or Ledger()
    out = []
    for j in JOBS:
        if quote_of(j, L) is None:
            out.append(L.quote(j.goal, j.provider, j.ledger_job(), j.worst_usd, j.ledger_note()))
    return out


def requote(job: Job, ledger: Ledger | None = None):
    """A new quote for a job whose last quote is used up (spent, or released by the owner): the job as it is in
    jobs.py now. Refused while the last quote can still run. Approving it is the owner's."""
    L = ledger or Ledger()
    if job.cancelled:
        raise LedgerRefusal(f"{job.id}: {job.cancelled}")
    q = quote_of(job, L)
    if q is not None and q not in L.released() and not any(e["type"] == "spend" and e["quote"] == q for e in L.events):
        raise LedgerRefusal(f"{job.id}: its quote {q} is not used yet")
    return L.quote(job.goal, job.provider, job.ledger_job(), job.worst_usd, job.ledger_note())


def spent(job: Job, ledger: Ledger | None = None) -> bool:
    L = ledger or Ledger()
    q = quote_of(job, L)
    return q is not None and any(e["type"] == "spend" and e["quote"] == q for e in L.events)


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
    """The on-demand price of the job's GPU on the job's cloud now (read-only)."""
    d = _gql("query { gpuTypes { id communityPrice securePrice } }")
    gid = GPU_IDS[job.gpu]
    for g in d["gpuTypes"]:
        if g["id"] == gid:
            return float(g[PRICE_FIELD[job.cloud]])
    raise RuntimeError(f"no price for {gid}")


def authorise(job: Job, ledger: Ledger | None = None, price_now: float | None = None):
    L = ledger or Ledger()
    if job.cancelled:
        raise LedgerRefusal(f"{job.id}: {job.cancelled}")
    qid = quote_of(job, L)
    if qid is None:
        raise LedgerRefusal(f"{job.id}: no quote recorded (python -m v2.bakeoff quote --record)")
    for d in job.after:
        dq = quote_of(BY_ID[d], L)
        if dq is None or not any(e["type"] == "spend" and e["quote"] == dq for e in L.events):
            raise LedgerRefusal(f"{job.id}: needs {d} done first (its spend recorded and its result checked)")
        if stopped(d):
            raise LedgerRefusal(f"{job.id}: {d} did not pass its checks ({stop_file(d)}): this branch is stopped")
    q = L.authorise(qid)
    p = live_price(job) if price_now is None else price_now
    if p > job.price_h + 1e-9:
        raise LedgerRefusal(f"{job.id}: {job.gpu} costs ${p}/h now, quoted ${job.price_h}/h: re-quote")
    return q


def stop_file(job_id: str) -> Path:
    """Written by the checks of a job's results (python -m v2.bakeoff check <job>) when they fail: the jobs after
    it are then refused."""
    return v2_data() / "test" / "bakeoff" / "stopped" / f"{job_id}.json"


def stopped(job_id: str) -> bool:
    return stop_file(job_id).exists()


# ---------------------------------------------------------------------------------------------- the pod
def cap_seconds(job: Job, cost_h: float | None = None) -> int:
    """The job's time on the pod: its cap, shortened so that seconds x (price + disk) stays within the quote's
    worst case (cap_h x the quoted price)."""
    rate = (cost_h if cost_h is not None else job.price_h) + DISK_GB * DISK_USD_GB_H
    return int(min(job.cap_h * 3600, job.worst_usd / rate * 3600) - 20)   # 20 s for the terminate call itself


def pod_spec(job: Job, country: str | None = None, gpu: str | None = None) -> dict:
    """The pod: its start command is the watchdog (pod/watchdog.sh), which terminates the pod at the deadline before
    anything else runs; the image's own start (sshd) follows."""
    wd = base64.b64encode((POD / "watchdog.sh").read_bytes()).decode()
    pub = (Path.home() / ".ssh" / "id_ed25519.pub").read_text().strip()
    spec = {"name": f"isolux-v2-{job.id.lower()}", "imageName": IMAGE, "gpuTypeId": GPU_IDS[gpu or job.gpu], "gpuCount": 1,
            "cloudType": job.cloud.upper(), "containerDiskInGb": DISK_GB, "volumeInGb": 0, "volumeMountPath": "/workspace",
            "dockerArgs": f"bash -c 'echo {wd} | base64 -d > /watchdog.sh; exec bash /watchdog.sh'",
            "ports": "22/tcp", "supportPublicIp": True, "startSsh": True,
            "env": [{"key": "ISOLUX_JOB", "value": job.id}, {"key": "ISOLUX_CAP_S", "value": str(cap_seconds(job))},
                    {"key": "PUBLIC_KEY", "value": pub}]}
    if country:
        spec["countryCode"] = country
    return spec


def _pod(pod_id: str) -> dict | None:
    d = _gql("query($id: String!) { pod(input: {podId: $id}) { id name desiredStatus costPerHr "
             "runtime { uptimeInSeconds ports { ip isIpPublic privatePort publicPort type } } } }", {"id": pod_id})
    return d.get("pod")


def terminate(pod_id: str) -> None:
    """Terminate one of this module's own pods, by its id, and wait until RunPod no longer lists it."""
    for attempt in range(6):
        try:
            _gql("mutation($id: String!) { podTerminate(input: {podId: $id}) }", {"id": pod_id})
        except Exception as ex:                                     # already gone, or a network blip: look
            print(f"terminate {pod_id}: {str(ex)[:200]}", flush=True)
        try:
            if _pod(pod_id) is None:
                return
        except Exception:
            pass
        time.sleep(5)
    raise RuntimeError(f"pod {pod_id} is still listed after terminate: check RunPod now")


def balance_now() -> float:
    """The account's balance at RunPod (read-only)."""
    return float(_gql("query { myself { clientBalance } }")["myself"]["clientBalance"])


def my_pods() -> list:
    """Every pod of the account whose name is one of this module's (read-only)."""
    d = _gql("query { myself { pods { id name desiredStatus costPerHr } } }")
    return [p for p in d["myself"]["pods"] if p["name"].startswith("isolux-v2-") and p["name"] not in FOREIGN_PODS]


# ---------------------------------------------------------------------------------------------- sessions
class Session:
    """One pod and the jobs run on it, kept in <data>/v2/_shared/bakeoff/pods/<name>.json."""

    def __init__(self, name: str):
        self.name = name
        self.path = state_dir() / f"{name}.json"
        self.d = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self):
        self.path.write_text(json.dumps(self.d, indent=1))

    @property
    def open(self) -> bool:
        return bool(self.d) and not self.d.get("closed")

    @property
    def rate(self) -> float:
        return self.d["cost_h"] + DISK_GB * DISK_USD_GB_H

    def ssh_cfg(self) -> Path:
        return state_dir() / f"{self.name}.ssh"

    def ssh(self, cmd: str, timeout=120, check=True) -> str:
        r = subprocess.run(["ssh", "-F", str(self.ssh_cfg()), "-o", "ConnectTimeout=20", "pod", cmd],
                           capture_output=True, text=True, timeout=timeout)
        if check and r.returncode:
            raise RuntimeError(f"ssh failed ({r.returncode}): {r.stderr[-400:]}")
        return r.stdout

    def rsync(self, src: str, dst: str, timeout=1800, extra=()) -> bool:
        for attempt in range(4):
            r = subprocess.run(["rsync", "-a", "--partial", "--timeout=120", *extra, "-e", f"ssh -F {self.ssh_cfg()}", src, dst],
                               capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                return True
            time.sleep(5)
        print(f"rsync {src} -> {dst} failed: {r.stderr[-300:]}", flush=True)
        return False

    # -- money
    def close_job(self, ledger: Ledger, now: float | None = None, note: str = "") -> dict | None:
        """Record the open job's spend: its seconds on the pod up to now x the pod's rate."""
        cur = self.d.get("job")
        if not cur:
            return None
        # the pod's own watchdog terminates it at the deadline (or at the end of a hold): no second after that is billed
        now = min(now or time.time(), min(cur["deadline"], cur.get("hold_until", cur["deadline"])) + 20)
        secs = now - cur["start"]
        usd = round(secs / 3600 * self.rate, 4)
        job = BY_ID[cur["id"]]
        ev = ledger.record_spend(quote_of(job, ledger), usd,
                                 measured_by=f"runpod pod {self.d['pod_id']} ({self.d['name']}): {secs:.0f} s x "
                                             f"(${self.d['cost_h']}/h + ${DISK_GB * DISK_USD_GB_H:.4f}/h disk), laptop clock"
                                             + (f"; {note}" if note else ""))
        self.d.setdefault("history", []).append({**cur, "end": now, "seconds": round(secs), "usd": usd, "note": note})
        self.d["job"] = None
        self.save()
        print(f"spend recorded: {job.id} ${usd} ({secs / 60:.1f} min; quote worst case ${job.worst_usd})", flush=True)
        return ev

    def end(self, ledger: Ledger | None = None, note: str = ""):
        """Terminate the pod, then record the open job's spend up to the terminate call."""
        if not self.open:
            return
        terminate(self.d["pod_id"])
        self.close_job(ledger or Ledger(), note=note)
        self.d["closed"] = time.time()
        try:                                     # RunPod's own figure after this pod, for the reconciliation
            self.d["balance_after"] = balance_now()
        except Exception:
            pass
        self.save()
        for f in (self.ssh_cfg(), state_dir() / f"{self.name}.known_hosts"):
            f.unlink(missing_ok=True)
        print(f"pod {self.d['pod_id']} terminated; session {self.name} closed", flush=True)


def _create(job: Job, name: str, wait_min: float = 0) -> Session:
    """Create the pod (the only call that starts spending) and wait until ssh answers. With wait_min, a creation
    refused for lack of machines is tried again every 45 s for that long (a refused creation costs nothing)."""
    last = None
    pod = None
    t_end = time.time() + wait_min * 60
    tries = 0
    balance = balance_now()                      # RunPod's own figure before this pod, for the reconciliation
    while pod is None:
        f = PRICE_FIELD[job.cloud]
        prices = {g["id"]: g[f] for g in _gql("query { gpuTypes { id communityPrice securePrice } }")["gpuTypes"]}
        for gpu in sorted(SAME_CHIP.get(job.gpu, (job.gpu,)), key=lambda g: float(prices.get(GPU_IDS[g]) or 1e9)):
            pr = prices.get(GPU_IDS[gpu])
            if pr is None or float(pr) > job.price_h + 1e-9:
                continue
            for cc in COUNTRIES:
                spec = pod_spec(job, cc, gpu)
                assert spec["name"] not in FOREIGN_PODS
                try:
                    pod = _gql("mutation($input: PodFindAndDeployOnDemandInput) { podFindAndDeployOnDemand(input: $input) "
                               "{ id name costPerHr desiredStatus } }", {"input": spec})["podFindAndDeployOnDemand"]
                except Exception as ex:
                    last = ex
                    pod = None
                if pod:
                    break
            if pod:
                break
        if pod or time.time() >= t_end:
            break
        tries += 1
        if tries % 8 == 1:
            print(f"{job.id}: no free machine yet ({time.strftime('%H:%M')}); trying again every 45 s", flush=True)
        time.sleep(45)
    if not pod:
        raise LedgerRefusal(f"{job.id}: no {job.gpu} on RunPod's {job.cloud} cloud right now ({str(last)[:300]}); nothing was started")
    t0 = time.time()
    s = Session(name)
    s.d = {"name": spec["name"], "pod_id": pod["id"], "cost_h": float(pod["costPerHr"]), "created": t0, "gpu": gpu,
           "country": cc, "balance_before": balance,
           "job": {"id": job.id, "start": t0, "deadline": t0 + cap_seconds(job)}, "history": []}
    s.save()
    print(f"pod {pod['id']} created for {job.id}: {gpu} ${pod['costPerHr']}/h ({cc or 'any country'})", flush=True)
    try:
        if float(pod["costPerHr"]) > job.price_h + 1e-9:
            raise LedgerRefusal(f"{job.id}: the pod costs ${pod['costPerHr']}/h, quoted ${job.price_h}/h")
        _wait_ssh(s)
    except BaseException:
        s.end(note="pod never became usable")
        raise
    return s


def _wait_ssh(s: Session, minutes=12):
    t_end = time.time() + minutes * 60
    while time.time() < t_end:
        p = _pod(s.d["pod_id"])
        if p is None:
            raise RuntimeError("the pod disappeared while starting")
        ports = ((p.get("runtime") or {}).get("ports")) or []
        pub = [x for x in ports if x.get("isIpPublic") and x.get("privatePort") == 22]
        if pub:
            ip, port = pub[0]["ip"], pub[0]["publicPort"]
            kh = state_dir() / f"{s.name}.known_hosts"
            if s.d.get("ip") != ip or s.d.get("port") != port:
                kh.unlink(missing_ok=True)                  # trust on first use, per pod (as v1's launch.sh)
                s.ssh_cfg().write_text(f"Host pod\n  HostName {ip}\n  Port {port}\n  User root\n  IdentityFile ~/.ssh/id_ed25519\n"
                                       f"  StrictHostKeyChecking accept-new\n  UserKnownHostsFile {kh}\n  ServerAliveInterval 30\n")
                s.d["ip"], s.d["port"] = ip, port
                s.save()
            try:
                if "ok" in s.ssh("echo ok", timeout=40):
                    print(f"ssh up after {time.time() - s.d['created']:.0f} s", flush=True)
                    return
            except Exception:
                pass
        time.sleep(10)
    raise RuntimeError(f"no ssh after {minutes} min")


def preflight(s: Session, job: Job, kind: str) -> tuple:
    """A new pod's first minute (pod/preflight.sh): (ok, what it printed). Nothing is installed or downloaded
    before this passes, so a host that cannot run the job costs its start-up only."""
    from v2.bakeoff import bundle as B
    try:
        s.ssh(f"mkdir -p /workspace/job/{job.id}")
        s.rsync(str(POD) + "/", f"pod:/workspace/job/{job.id}/pod/")
        out = s.ssh(f"bash /workspace/job/{job.id}/pod/preflight.sh {B.MODEL[kind]} 2>&1", timeout=120, check=False)
    except Exception as ex:
        out = f"PREFLIGHT FAILED: {type(ex).__name__}: {str(ex)[:200]}"
    return "PREFLIGHT OK" in out, out.strip()


def _alive(s: Session) -> bool:
    try:
        return s.open and _pod(s.d["pod_id"]) is not None and "ok" in s.ssh("echo ok", timeout=40)
    except Exception:
        return False


# ---------------------------------------------------------------------------------------------- one job
def run(job_id: str, go: bool = False, keep: bool = False, on: str | None = None, session: str | None = None,
        setup: str | None = None, wait_min: float = 0):
    """Run one job (see the module doc). Returns a summary dict."""
    from v2.bakeoff import bundle as B
    job = BY_ID[job_id]
    if not go:
        return {"dry_run": True, "job": job.id, "pod": pod_spec(job), "worst_usd": job.worst_usd,
                "cap_s": cap_seconds(job)}
    L = Ledger()
    name = session or on or job.id.lower()
    s = Session(on) if on else Session(name)
    resumed = False
    fresh = False
    if s.open and (s.d.get("job") or {}).get("id") == job.id:
        resumed = True                                       # the same job again within its own time (a retry)
        if not _alive(s):
            s.end(L, note="pod gone before the job finished")
            raise LedgerRefusal(f"{job.id}: its pod is gone and its spend is recorded: a rerun needs a new quote")
        if s.d["job"].pop("hold_until", None):               # a held pod: back to the job's own deadline
            s.save()
            s.ssh(f"echo {int(s.d['job']['deadline'])} > /workspace/DEADLINE")
    elif on and s.open and _alive(s):
        s.close_job(L)                                       # the job before: its time ends here
        try:
            authorise(job, L)
        except BaseException:
            s.end(L)
            raise
        now = time.time()
        s.d["job"] = {"id": job.id, "start": now, "deadline": now + cap_seconds(job, s.d["cost_h"])}
        s.save()
        s.ssh(f"echo {int(s.d['job']['deadline'])} > /workspace/DEADLINE && cat /workspace/DEADLINE")
    else:
        if on and s.open:
            s.end(L, note="pod gone between jobs")
        authorise(job, L)
        s = _create(job, name, wait_min)
        fresh = True
        dl = s.d["job"]["start"] + cap_seconds(job, s.d["cost_h"])
        s.d["job"]["deadline"] = dl
        s.save()
        s.ssh(f"mkdir -p /workspace && echo {int(dl)} > /workspace/DEADLINE")
    deadline = s.d["job"]["deadline"]
    ok = False
    try:
        kind = setup or B.SETUP[job.id]
        if fresh:
            good, out = preflight(s, job, kind)
            print(out, flush=True)
            if not good:
                secs = time.time() - s.d["job"]["start"]
                s.end(L, note="preflight failed: " + out.splitlines()[-1][:160] if out else "preflight failed")
                return {"job": job.id, "ok": False, "rc": None, "pod": s.d["pod_id"], "session": s.name,
                        "note": "preflight failed; the pod was terminated before any setup", "minutes": round(secs / 60, 1)}
        bdir = B.build(job.id)
        s.ssh(f"mkdir -p /workspace/job/{job.id} /workspace/lora /workspace/logs /workspace/state /workspace/out/{job.id}")
        s.rsync(str(POD) + "/", f"pod:/workspace/job/{job.id}/pod/")
        s.ssh(f"cd /workspace && (setsid nohup bash job/{job.id}/pod/setup.sh {kind} >> logs/setup.log 2>&1 < /dev/null &) ; true")
        for src, dst, extra in B.uploads(job.id, bdir):
            if not s.rsync(src, f"pod:{dst}", extra=extra):
                raise RuntimeError(f"upload failed: {src}")
        s.ssh(f"cd /workspace && rm -f state/{job.id}.rc && (setsid nohup bash job/{job.id}/pod/run.sh {job.id} "
              f">> logs/{job.id}.log 2>&1 < /dev/null &) ; true")
        print(f"{job.id} started on pod {s.d['pod_id']}; deadline in {(deadline - time.time()) / 60:.1f} min"
              + (" (retry)" if resumed else ""), flush=True)
        local = B.local_out(job.id)
        local.mkdir(parents=True, exist_ok=True)
        rc, last = None, ""
        while time.time() < deadline - 45:
            time.sleep(20)
            try:
                out = s.ssh(f"cat /workspace/state/{job.id}.rc 2>/dev/null || echo running; "
                            f"tail -n 1 /workspace/logs/{job.id}.log 2>/dev/null | cut -c1-160", timeout=60)
            except Exception as ex:
                print(f"poll: {str(ex)[:120]}", flush=True)
                if _pod(s.d["pod_id"]) is None:
                    break
                continue
            lines = out.strip().splitlines()
            if len(lines) > 1 and lines[-1] != last:
                last = lines[-1]
                print(f"  [{(time.time() - s.d['job']['start']) / 60:5.1f} min] {last}", flush=True)
            s.rsync(f"pod:/workspace/out/{job.id}/", str(local) + "/", extra=B.PULL_FILTER.get(job.id, ()))
            if lines and lines[0] != "running":
                rc = int(lines[0])
                break
        s.rsync(f"pod:/workspace/out/{job.id}/", str(local) + "/", extra=B.PULL_FILTER.get(job.id, ()))
        s.rsync(f"pod:/workspace/logs/", str(local / "logs") + "/")
        ok = rc == 0
        note = "finished" if ok else ("failed rc=%s" % rc if rc is not None else "stopped at its time cap")
        res = {"job": job.id, "ok": ok, "rc": rc, "pod": s.d["pod_id"], "session": s.name, "note": note,
               "minutes": round((time.time() - s.d["job"]["start"]) / 60, 1), "out": str(local)}
        if keep and ok:
            res["kept"] = True                               # the pod stays for the next job
            print(json.dumps(res), flush=True)
            return res
        made = [p for p in local.iterdir() if p.is_file() and p.suffix in (".png", ".jpg", ".safetensors")]
        if rc not in (None, 0) and not made and time.time() < deadline - HOLD_S - 60:
            hold = time.time() + HOLD_S                      # nothing made: held for a restart in place (module doc)
            s.d["job"]["hold_until"] = hold
            s.save()
            s.ssh(f"echo {int(hold)} > /workspace/DEADLINE")
            res.update(kept=True, held_s=HOLD_S, retry=f"python -m v2.bakeoff run {job.id} --go --on {s.name}",
                       note=note + f"; nothing was made: the pod is held {HOLD_S // 60} min for a restart in place "
                                   f"(then it terminates itself); or end it now: python -m v2.bakeoff end {s.name}")
            print(json.dumps(res), flush=True)
            return res
        s.end(L, note=note)
        return res
    except BaseException as ex:
        if s.open:
            try:
                s.end(L, note=f"runner error: {type(ex).__name__}")
            except Exception as ex2:
                print(f"COULD NOT END SESSION {s.name} (pod {s.d.get('pod_id')}): {ex2}", flush=True)
        raise


def end(session: str, note: str = "ended by hand"):
    s = Session(session)
    if not s.open:
        print(f"session {session}: nothing open")
        return
    s.end(Ledger(), note=note)


def end_all(note: str = "paused by the owner"):
    """Every open session: terminate its pod and record its spend (the owner's pause)."""
    for p in sorted(state_dir().glob("*.json")):
        s = Session(p.stem)
        if s.open:
            s.end(Ledger(), note=note)


def created_pod_ids() -> list:
    return [json.loads(p.read_text()).get("pod_id") for p in sorted(state_dir().glob("*.json"))]


def verify_none_left() -> dict:
    """Read-only: none of the pods created here is still listed by RunPod, and no pod carries one of our names."""
    d = _gql("query { myself { pods { id name desiredStatus } } }")["myself"]["pods"]
    mine = set(created_pod_ids())
    left = [p for p in d if p["id"] in mine or (p["name"].startswith("isolux-v2-") and p["name"] not in FOREIGN_PODS)]
    return {"created_here": sorted(x for x in mine if x), "still_listed": left,
            "others_untouched": [p["name"] for p in d if p["id"] not in mine and p not in left]}
