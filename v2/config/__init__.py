"""v2 configuration: paths, areas, camera, palette, sun and build parameters.

Everything a build reads from the repo lives here. Data never lives in git: raw downloads and build outputs go under
the data root (``$ISOLUX_DATA``, default ``<repo>/data``), in ``raw/`` (v1's downloads, reused) and ``v2/`` (v2).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

CONFIG = Path(__file__).resolve().parent
V2 = CONFIG.parent
REPO = V2.parent


def data_root() -> Path:
    return Path(os.environ.get("ISOLUX_DATA", REPO / "data")).resolve()


def raw_dir() -> Path:
    """v1's raw downloads (ACT 3D buildings, GTFS, OSM extracts): read only."""
    return data_root() / "raw"


def v1_work() -> Path:
    """v1's parsed data (terrain, LiDAR 2 m, tree survey cut): read only."""
    return data_root() / "work"


def v2_data() -> Path:
    """v2 build outputs and v2 downloads (gitignored)."""
    return data_root() / "v2"


def load_json(name: str):
    return json.loads((CONFIG / name).read_text())


@lru_cache(maxsize=None)
def params() -> dict:
    """Build and check parameters (params.json): one place for every threshold."""
    return load_json("params.json")


@lru_cache(maxsize=None)
def palette() -> dict:
    return load_json("palette.json")


@lru_cache(maxsize=None)
def layers() -> list[dict]:
    return load_json("layers.json")["layers"]


def area_names() -> list[str]:
    return sorted(p.stem for p in (CONFIG / "areas").glob("*.geojson") if not p.stem.endswith("_quarters"))


@lru_cache(maxsize=None)
def area_geojson(name: str) -> dict:
    p = CONFIG / "areas" / f"{name}.geojson"
    if not p.exists():
        raise SystemExit(f"unknown area {name!r}; known: {', '.join(area_names())}")
    return json.loads(p.read_text())
