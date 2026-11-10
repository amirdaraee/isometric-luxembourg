"""Gate G3's results so far: gate G1's whole suite on the richer art, the tunnel view (X1-X8) and the landmark
cutaways (K0-K6, as far as they run before anything is painted), in one file for the owner's review:
v2/docs/results/g3_<area>.json. The owner's own checks (L14.4, K7) are not in it."""
from __future__ import annotations

import json

from v2.config import V2


def g3(ctx):
    g1 = json.loads((ctx.dep("g1") / "g1.json").read_text())
    checks = dict(g1["checks"])
    for name in ("check_tunnel_view", "check_cutaways"):
        s = json.loads((ctx.dep(name) / "manifest.json").read_text())["summary"] or {}
        checks[name] = {"passed": s.get("passed"), "entries": s.get("entries", [])}
    passed = all(bool(c["passed"]) for c in checks.values())
    res = {"area": ctx.area, "art": g1["art"], "gate": "G3 (checks so far)", "passed": passed, "checks": checks,
           "speed": g1.get("speed"), "release": g1.get("release")}
    (V2 / "docs" / "results" / f"g3_{ctx.area}.json").write_text(json.dumps(res, indent=1, default=str))
    ctx.write_json("g3.json", res, indent=1, default=str)
    return {"passed": passed, "checks": {k: v["passed"] for k, v in checks.items()}}
