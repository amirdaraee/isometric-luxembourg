"""Scene: the index of one built scene (spec: v2/docs/specs/scene.md).

scene.json names every part (its stage output folder and key), the area, the camera frame, the counts from each
part's manifest, and the area's extent in v2 map pixels. Later stages (layers, checks, the viewer export) read the
scene through this index only.
"""
from __future__ import annotations

import json

import numpy as np

from v2.config.camera import camera, en_to_px
from v2.data.geo import area_polygon

PARTS = ("scene_terrain", "scene_water", "scene_buildings", "scene_facades", "scene_trees", "scene_places",
         "scene_transport", "scene_structures", "scene_transit")


def build(ctx):
    poly = area_polygon(ctx.area)
    parts = {}
    for p in PARTS:
        m = json.loads((ctx.dep(p) / "manifest.json").read_text())
        parts[p.removeprefix("scene_")] = {"folder": str(ctx.dep(p)), "key": m["key"], "files": m["files"],
                                          "bytes": m["bytes"], "summary": m["summary"]}
    ring = np.array(poly.exterior.coords)
    px, py = en_to_px(ring[:, 0], ring[:, 1], np.full(len(ring), 300.0))
    idx = {"area": ctx.area, "area_km2": round(poly.area / 1e6, 3), "bounds_en": [round(b, 2) for b in poly.bounds],
           "camera": {k: camera()[k] for k in ("crs", "origin_en", "elevation_deg", "mpp", "frame", "v1_offset_px")},
           "extent_px_at_300m": [round(float(px.min())), round(float(py.min())), round(float(px.max())), round(float(py.max()))],
           "parts": parts}
    ctx.write_json("scene.json", idx, indent=1)
    return {"area_km2": idx["area_km2"], "parts": len(parts), "bytes": sum(p["bytes"] for p in parts.values()),
            "counts": {k: {kk: vv for kk, vv in v["summary"].items() if isinstance(vv, (int, float))} for k, v in parts.items()}}


def part(scene_folder, name):
    """The folder of a scene part, from a scene stage output."""
    from pathlib import Path
    idx = json.loads((Path(scene_folder) / "scene.json").read_text())
    return Path(idx["parts"][name]["folder"])
