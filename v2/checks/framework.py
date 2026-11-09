"""Checks: numbered pass/fail tests that gate the build (PLAN_V2 principle 6).

A check stage builds a Report, adds one entry per numbered test (with the measured value, the threshold and up to a
few examples of what failed), and returns report.result(). The stage fails, and the build exits non-zero, when any
entry with severity "gate" fails. Entries with severity "report" are measured and shown but never fail (used for
facts the owner should see, not for pass/fail rules).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Entry:
    id: str
    title: str
    passed: bool
    value: object = None
    threshold: object = None
    severity: str = "gate"
    examples: list = field(default_factory=list)


class Report:
    def __init__(self, name: str):
        self.name = name
        self.entries: list[Entry] = []

    def add(self, id, title, passed, value=None, threshold=None, examples=(), severity="gate"):
        self.entries.append(Entry(id, title, bool(passed), value, threshold, severity, list(examples)[:8]))
        return passed

    def at_most(self, id, title, value, limit, examples=(), severity="gate"):
        return self.add(id, title, value <= limit, value, f"<= {limit}", examples, severity)

    def at_least(self, id, title, value, limit, examples=(), severity="gate"):
        return self.add(id, title, value >= limit, value, f">= {limit}", examples, severity)

    def info(self, id, title, value):
        return self.add(id, title, True, value, None, (), "report")

    def result(self) -> dict:
        ok = all(e.passed for e in self.entries if e.severity == "gate")
        lines = []
        for e in self.entries:
            mark = "PASS" if e.passed else ("FAIL" if e.severity == "gate" else "note")
            if e.severity == "report":
                mark = "info"
            v = e.value if not isinstance(e.value, float) else round(e.value, 4)
            lines.append(f"{mark} {e.id} {e.title}: {v}" + (f" ({e.threshold})" if e.threshold else ""))
            if not e.passed and e.examples:
                lines.append("       e.g. " + json.dumps(e.examples[:3], default=str)[:300])
        return {"passed": ok, "check": self.name, "lines": lines,
                "entries": [e.__dict__ for e in self.entries]}
