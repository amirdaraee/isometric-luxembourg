"""Checks on the build itself rather than its data (spec: v2/docs/specs/checks.md).

check_no_patching (brief item 1): no stage, module or stage function of the v2 build may be a fix applied to
finished art (warps, repaints, despeckles, colour fixes, "fit to art" steps): a defect is fixed in the layer that
made it. The gate greps stage names, module file names and stage function names for the words v1 used for such
steps (params.json checks.forbidden_stage_words).

check_ledger: the spend ledger parses, every spend has an owner-approved quote, and no goal is over its cap.
"""
from __future__ import annotations

import re

from v2.checks.framework import Report
from v2.config import V2


def check_no_patching(ctx):
    r = Report("no_patching")
    words = ctx.params["checks"]["forbidden_stage_words"]
    from v2.build.stages import graph
    g = graph()
    pat = re.compile("|".join(re.escape(w) for w in words), re.I)
    names = [s.name for s in g.stages.values()] + [s.fn.__name__ for s in g.stages.values()]
    bad_stages = [n for n in names if pat.search(n)]
    mods = [str(p.relative_to(V2)) for p in V2.rglob("*.py") if "tests" not in p.parts]
    bad_mods = [m for m in mods if pat.search(m.split("/")[-1])]
    r.at_most("N1", "stages or stage functions named like a fix on finished art", len(bad_stages), 0, bad_stages)
    r.at_most("N2", "v2 modules named like a fix on finished art", len(bad_mods), 0, bad_mods)
    r.info("N3", "stages in the build graph", len(g.stages))
    return r.result()


def check_ledger(ctx):
    from v2.ledger.ledger import Ledger
    r = Report("ledger")
    L = Ledger()
    errs = L.validate()
    r.at_most("L1", "ledger problems (bad events, spends without an approved quote, goals over cap)", len(errs), 0, errs)
    st = L.status()
    r.at_most("L2", "total spent + committed (USD)", round(st["spent_usd"] + st["committed_usd"], 2), L.budget["owner_cap_usd"])
    r.at_most("L3", "Phase 0 spend (USD)", L.spent("phase0_foundation"), 0.0)
    return r.result()
