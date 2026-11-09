"""The v2 build graph: stages with declared inputs, content-addressed outputs, manifests and check gates.

A stage is a function that writes files into an output folder. Its **key** is a hash of everything that can change
its output: the stage's code (the source of its module and of the helper modules it declares), its parameters, the
keys of the stages it depends on, and the fingerprints of the raw files it reads. Outputs live in

    <data>/v2/<area>/<stage>/<key[:12]>/        (or <data>/v2/_shared/<stage>/... for shared fetches)
        manifest.json                           stage, area, key, code hash, params, deps, raw inputs, status, summary
        ...                                     the stage's files

so every output is versioned and never overwritten: a changed input makes a new key and a new folder, and an old
version stays until it is cleaned. A stage whose folder already holds a manifest with status "ok" is skipped, so
an interrupted build resumes where it stopped. Work happens in a temporary folder that is renamed when complete.

Check stages return {"passed": bool, ...}. A failed check is recorded (status "failed") and makes the build exit
with a non-zero status after the stages that do not depend on it have run; nothing downstream of a failed check
runs.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib
import inspect
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from v2.config import REPO, v2_data

SHARED = "_shared"


@dataclass
class Stage:
    name: str
    fn: Callable
    deps: tuple = ()
    params: Callable | dict = field(default_factory=dict)   # dict, or fn(area) -> dict
    raw: Callable | None = None                            # fn(area) -> list[Path] of raw inputs
    code: tuple = ()                                       # extra modules (dotted names) whose source is hashed
    kind: str = "data"                                     # "fetch", "data", "check", "report"
    shared: bool = False                                   # one output for every area (fetches over the commune)
    doc: str = ""

    def params_for(self, area: str) -> dict:
        return self.params(area) if callable(self.params) else dict(self.params)


class CheckFailed(Exception):
    pass


@dataclass
class Ctx:
    """What a stage function gets: its area, its output folder, its params and its dependencies' folders."""
    area: str
    out: Path
    params: dict
    deps: dict
    workers: int

    def dep(self, name: str) -> Path:
        return self.deps[name]

    def log(self, *a):
        print("   ", *a, flush=True)

    def write_json(self, name: str, obj, **kw) -> Path:
        p = self.out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, separators=(",", ":"), **kw))
        return p


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def module_source_hash(mods) -> str:
    h = hashlib.sha256()
    for m in sorted(set(mods)):
        mod = importlib.import_module(m)
        h.update(m.encode())
        h.update(Path(inspect.getsourcefile(mod)).read_bytes())
    return h.hexdigest()


def _where(p: Path) -> str:
    """A raw input's path for its fingerprint: relative to the repository when it is in it, so two checkouts (a
    worktree, CI) of the same files share their stage keys."""
    try:
        return "repo:" + str(Path(p).resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(p)


def fingerprint(p: Path) -> dict:
    """Small files by content; big files (over 64 MB) by size and modification time."""
    p = Path(p)
    if not p.exists():
        raise FileNotFoundError(f"raw input missing: {p}")
    if p.is_dir():
        files = sorted(q for q in p.rglob("*") if q.is_file())
        h = hashlib.sha256()
        for q in files:
            st = q.stat()
            h.update(f"{q.relative_to(p)}:{st.st_size}:{int(st.st_mtime)}".encode())
        return {"path": _where(p), "dir_files": len(files), "hash": h.hexdigest()}
    st = p.stat()
    if st.st_size > 64 << 20:
        return {"path": _where(p), "size": st.st_size, "mtime": int(st.st_mtime)}
    return {"path": _where(p), "size": st.st_size, "sha256": _sha(p.read_bytes())}


def git_version() -> str:
    try:
        rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", "v2"], capture_output=True,
                               text=True).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except Exception:  # noqa: BLE001 - outside a checkout
        return "unknown"


class Graph:
    def __init__(self, stages: list[Stage]):
        self.stages = {s.name: s for s in stages}
        for s in stages:
            for d in s.deps:
                if d not in self.stages:
                    raise ValueError(f"stage {s.name} depends on unknown stage {d}")
        self._keys: dict = {}

    # ------------------------------------------------------------------ ordering
    def order(self, targets) -> list[str]:
        seen, out = set(), []

        def visit(n, stack=()):
            if n in stack:
                raise ValueError("cycle: " + " -> ".join(stack + (n,)))
            if n in seen:
                return
            for d in self.stages[n].deps:
                visit(d, stack + (n,))
            seen.add(n)
            out.append(n)
        for t in targets:
            if t not in self.stages:
                raise SystemExit(f"unknown stage {t!r}")
            visit(t)
        return out

    # ------------------------------------------------------------------ keys and folders
    def scope(self, name: str, area: str) -> str:
        return SHARED if self.stages[name].shared else area

    def key(self, name: str, area: str) -> tuple[str, dict]:
        ck = (name, self.scope(name, area))
        if ck in self._keys:
            return self._keys[ck]
        s = self.stages[name]
        mods = (s.fn.__module__,) + tuple(s.code)
        raw = [fingerprint(p) for p in (s.raw(area) if s.raw else [])]
        spec = {"stage": name, "scope": self.scope(name, area), "params": s.params_for(area),
                "code": module_source_hash(mods), "deps": {d: self.key(d, area)[0] for d in s.deps}, "raw": raw}
        k = _sha(json.dumps(spec, sort_keys=True, default=str).encode())
        self._keys[ck] = (k, spec)
        return k, spec

    def folder(self, name: str, area: str) -> Path:
        k, _ = self.key(name, area)
        return v2_data() / self.scope(name, area) / name / k[:12]

    def status(self, name: str, area: str) -> str:
        m = self.folder(name, area) / "manifest.json"
        if not m.exists():
            return "missing"
        return json.loads(m.read_text()).get("status", "unknown")

    # ------------------------------------------------------------------ running
    def run_stage(self, name: str, area: str, workers: int, force: bool = False) -> dict:
        s = self.stages[name]
        dest = self.folder(name, area)
        man = dest / "manifest.json"
        if man.exists() and not force:
            m = json.loads(man.read_text())
            if m.get("status") == "ok":
                print(f"  = {name:<28} up to date  {dest.relative_to(v2_data())}")
                return m
        k, spec = self.key(name, area)
        tmp = dest.with_name(dest.name + f".tmp-{os.getpid()}")
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        ctx = Ctx(area=area, out=tmp, params=spec["params"], workers=workers,
                  deps={d: self.folder(d, area) for d in s.deps})
        print(f"  > {name:<28} [{s.kind}] {area}", flush=True)
        t0 = time.time()
        status, summary, err = "ok", None, None
        try:
            summary = s.fn(ctx) or {}
            if s.kind == "check" and not summary.get("passed", False):
                status = "failed"
        except Exception as ex:  # noqa: BLE001 - recorded in the manifest, then re-raised as a build failure
            status, err = "error", "".join(traceback.format_exception(ex))
        manifest = {"stage": name, "area": area, "scope": spec["scope"], "kind": s.kind, "key": k,
                    "status": status, "code_version": git_version(), "code_hash": spec["code"],
                    "params": spec["params"], "deps": {d: {"key": v, "folder": str(ctx.deps[d])} for d, v in spec["deps"].items()},
                    "raw": spec["raw"], "seconds": round(time.time() - t0, 1),
                    "finished": datetime.datetime.now().isoformat(timespec="seconds"),
                    "files": sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file()),
                    "bytes": sum(p.stat().st_size for p in tmp.rglob("*") if p.is_file()),
                    "summary": summary, "error": err}
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str))
        if dest.exists():
            shutil.rmtree(dest)
        tmp.rename(dest)
        (dest.parent / "current.json").write_text(json.dumps({"key": k, "folder": dest.name, "status": status}))
        mark = {"ok": "ok", "failed": "FAILED", "error": "ERROR"}[status]
        print(f"    {mark} in {manifest['seconds']}s, {manifest['bytes'] / 1e6:.2f} MB  {dest.relative_to(v2_data())}",
              flush=True)
        if err:
            print(err, file=sys.stderr)
        if s.kind == "check" and summary:
            for line in summary.get("lines", []):
                print("     ", line)
        return manifest

    def build(self, area: str, targets, workers: int = 2, force=()) -> int:
        order = self.order(targets)
        failed: set[str] = set()
        for n in order:
            blocked = [d for d in self.stages[n].deps if d in failed]
            if blocked:
                print(f"  x {n:<28} skipped: {', '.join(blocked)} failed")
                failed.add(n)
                continue
            m = self.run_stage(n, area, workers, force=n in force or "all" in force)
            if m["status"] != "ok":
                failed.add(n)
        bad = [n for n in order if n in failed]
        print(f"build {area}: {len(order) - len(bad)}/{len(order)} stages ok" + (f"; failed: {', '.join(bad)}" if bad else ""))
        return 1 if bad else 0
