"""The art method of layers 5-7 (PLAN_V2 section 7, the bake-off)."""
from __future__ import annotations

import os

from v2.config import params

ART_METHODS = ("a", "b", "c", "plain")


def art_method() -> str:
    """params.json art.method, or V2_ART to build another bake-off option ("a" all code, "b" code + AI materials,
    "c" code + AI-painted buildings; "plain" Phase 1's placeholder)."""
    m = os.environ.get("V2_ART") or params()["art"]["method"]
    if m not in ART_METHODS:
        raise SystemExit(f"unknown art method {m!r}; known: {', '.join(ART_METHODS)}")
    return m
