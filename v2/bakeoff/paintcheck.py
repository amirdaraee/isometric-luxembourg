"""The checks every painting must pass before it is used (briefs 5, 6 and 9), on one 1024 px window, locally at $0.

    flat light   dataset.flat_light: on every building, the same material on faces turned different ways has the same
                 median luminance within 5% (no baked shadow)
    no cars      v1's OWLv2 detector (v2/checks/owl_detect.py, as gate check_no_cars): nothing at 0.1 or above
    line score   L5.2's measure (v2/checks/line_checks.score) on the window: building edges and window rows of the 3D
                 model within 1 px of a drawn line, 95% each

A painting is judged where layer 5 is what the window shows (geom.npz: which, ids, depth, normals); the thresholds are
the build's (params.json g1), unchanged.
"""
from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from v2.bakeoff.dataset import flat_light
from v2.config import REPO, params
from v2.layers.common import COLOUR_LAYERS, TILE, project

B_LAYER = COLOUR_LAYERS.index("buildings") + 1
S_LAYER = COLOUR_LAYERS.index("structures") + 1


def geom(folder: Path, name: str) -> dict:
    g = np.load(folder / f"{name}.geom.npz")
    return {"ids": g["ids"], "which": g["which"], "normal": g["normal"].astype(np.float64),
            "depth": g["depth"].astype(np.float64)}


class WindowCache:
    """One window as the tile cache line_checks.score reads: the painting's colour, and layer 5's depth and ids
    where layer 5 is what the window shows (nothing elsewhere)."""

    def __init__(self, x0, y0, rgb, g):
        self.x0, self.y0 = x0, y0
        seen = g["which"] == B_LAYER
        self.rgb = np.asarray(rgb, np.uint8)
        self.depth = np.where(seen, g["depth"], np.inf)
        self.ids = np.where(seen, g["ids"], 0)
        self.n = self.rgb.shape[0]
        self.c = {}

    def get(self, tx, ty):
        k = (tx, ty)
        if k in self.c:
            return self.c[k]
        a0, b0 = tx * TILE - self.x0, ty * TILE - self.y0          # the tile's corner in window pixels
        xs0, ys0, xs1, ys1 = max(a0, 0), max(b0, 0), min(a0 + TILE, self.n), min(b0 + TILE, self.n)
        if xs1 <= xs0 or ys1 <= ys0:
            self.c[k] = None
            return None
        t = {"rgb": np.zeros((TILE, TILE, 3), np.uint8), "depth": np.full((TILE, TILE), np.inf),
             "ids": np.zeros((TILE, TILE), np.uint32)}
        dst = (slice(ys0 - b0, ys1 - b0), slice(xs0 - a0, xs1 - a0))
        src = (slice(ys0, ys1), slice(xs0, xs1))
        t["rgb"][dst] = self.rgb[src]; t["depth"][dst] = self.depth[src]; t["ids"][dst] = self.ids[src]
        self.c[k] = t
        return t


@lru_cache(maxsize=2)
def model_lines(scene_folder: str):
    """The 3D model's line samples (as check_lines): {"edges": (P, D, O, px, py), "windows": ...}."""
    from v2.checks import line_checks as lc
    from v2.layers import geometry as G
    from v2.layers.common import Scene
    sc = Scene(Path(scene_folder))
    out = {}
    for name, (A, B, O) in (("edges", lc.feature_edges(G.buildings_mesh(sc))), ("windows", lc.window_rows(sc))):
        Ps, Ds, Os = lc.samples(A, B, O)
        px, py, _ = project(Ps[:, 0], Ps[:, 1], Ps[:, 2])
        out[name] = (Ps, Ds, Os, px, py)
    return out


def line_score(scene_folder, x0, y0, rgb, g, margin=4):
    """{"edges": (seen, on), "windows": (seen, on)} for the model's lines inside the window."""
    from v2.checks import line_checks as lc
    P = params()["g1"]
    cache = WindowCache(x0, y0, rgb, g)
    n = cache.n
    out = {}
    for name, (Ps, Ds, Os, px, py) in model_lines(str(scene_folder)).items():
        m = (px >= x0 + margin) & (px < x0 + n - margin) & (py >= y0 + margin) & (py < y0 + n - margin)
        if not m.any():
            out[name] = (0, 0)
            continue
        seen, on = lc.score(cache, Ps[m], Ds[m], P["line_score_px"], P["line_min_step"], obj=Os[m])
        out[name] = (int(seen.sum()), int(on.sum()))
    return out


def owl(paths: list, out_dir: Path, mpp=0.125) -> dict:
    """Detections per file (name -> list) with the build's detector, queries, threshold and box sizes."""
    P = params()["g1"]
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = {"jobs": [{"layer": "painting", "path": str(p), "tile": Path(p).name} for p in paths],
            "queries": P["detector_queries"], "queries_water": P["detector_queries_water"],
            "threshold": P["detector_score"], "box_m": P["detector_box_m"], "mpp": mpp, "out": str(out_dir / "owl.json")}
    (out_dir / "owl_jobs.json").write_text(json.dumps(spec))
    cmd = ["uv", "run", "--offline", "--no-project", "--with", "torch", "--with", "transformers", "--with", "pillow",
           "--with", "numpy", "python", "-I", str(REPO / "v2" / "checks" / "owl_detect.py"), str(out_dir / "owl_jobs.json")]
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"))
    if r.returncode:
        raise RuntimeError("detector failed: " + r.stderr[-2000:])
    res = json.loads((out_dir / "owl.json").read_text())
    by = {}
    for d in res["detections"]:
        by.setdefault(d["tile"], []).append(d)
    return {"by_file": by, "max_score": res["max_score"], "images": res["images"]}


def check_painting(scene_folder, png: Path, g: dict, x0: int, y0: int) -> dict:
    """Flat light and line score of one painting (the detector runs on all paintings at once: owl())."""
    P = params()["g1"]
    rgb = np.asarray(Image.open(png).convert("RGB"))
    seen = g["which"] == B_LAYER
    ids = np.where(seen, g["ids"], 0)
    worst, bad = flat_light(rgb, ids, g["normal"])
    ls = line_score(scene_folder, x0, y0, rgb, g)
    share = {k: (round(v[1] / v[0], 4) if v[0] else None) for k, v in ls.items()}
    lines_ok = all(s is None or s >= P["line_score_share"] for s in share.values())
    return {"file": png.name, "flat_worst": worst, "flat_failing_buildings": len(bad), "flat_ok": not bad,
            "line_edges": share["edges"], "line_windows": share["windows"], "line_seen": {k: v[0] for k, v in ls.items()},
            "lines_ok": lines_ok}


def check_set(scene_folder, inputs: Path, painted: Path, files: list, out_dir: Path) -> list:
    """Every painting of `files` ((window name, file name)): flat light, lines, detector. Returns one dict each with
    "keep" (all three pass)."""
    res = []
    for name, fn in files:
        x0, y0 = (int(v) for v in name.split("_")[:2])
        res.append({"window": name, **check_painting(scene_folder, painted / fn, geom(inputs, name), x0, y0)})
    det = owl([painted / fn for _, fn in files], out_dir)
    for r in res:
        hits = det["by_file"].get(r["file"], [])
        r["vehicles"] = len(hits)
        r["cars_ok"] = not hits
        r["keep"] = bool(r["flat_ok"] and r["lines_ok"] and r["cars_ok"])
    return res
