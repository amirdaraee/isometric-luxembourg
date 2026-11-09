"""Fetch stages: the downloads v1 does not have, over the commune extent (shared by every area) or the area.

Sources, licences and dates: v2/docs/DATA.md.
"""
from __future__ import annotations

import json

import numpy as np

from v2.config import params
from v2.data.fetch import overpass
from v2.data.fetch.cog import read_window
from v2.data.fetch.gpkg_stream import stream_table
from v2.data.geo import area_bbox_en, area_bbox_lonlat

TREE_TYPES = ["deciduous_green", "deciduous_red", "conifer", "other"]


def extent_params(area: str) -> dict:
    f = params()["fetch"]
    return {"snapshot": f["snapshot"], "extent_area": f["extent_area"], "margin_m": f["extent_margin_m"]}


def _osm(ctx, template: str, name: str):
    p = ctx.params
    bbox = area_bbox_lonlat(p["extent_area"], p["margin_m"])
    q = template.format(bbox=overpass.bbox_str(bbox))
    ctx.log(f"overpass {name}, bbox {bbox}")
    d = overpass.run(q)
    d["query"] = q
    ctx.write_json(f"{name}.json", d)
    kinds = {}
    for el in d["elements"]:
        kinds[el["type"]] = kinds.get(el["type"], 0) + 1
    return {"elements": len(d["elements"]), "by_type": kinds, "osm_timestamp": d.get("osm3s", {}).get("timestamp_osm_base")}


def fetch_osm_transport(ctx):
    return _osm(ctx, overpass.TRANSPORT, "transport")


def fetch_osm_ground(ctx):
    return _osm(ctx, overpass.GROUND, "ground")


def lidar_params(area: str) -> dict:
    a = params()["areas"][area]
    f = params()["fetch"]
    return {"step_m": a["terrain_step_m"], "margin_m": a["margin_m"], "mnt": f["lidar_mnt"], "mns": f["lidar_mns"],
            "snapshot": f["snapshot"]}


def fetch_lidar(ctx):
    """LiDAR 2024 terrain (MNT) and surface (MNS) over the area's bounding box plus a margin."""
    p = ctx.params
    e0, n0, e1, n1 = area_bbox_en(ctx.area, p["margin_m"])
    s = p["step_m"]
    e0, n0 = np.floor(e0 / s) * s, np.floor(n0 / s) * s
    e1, n1 = np.ceil(e1 / s) * s, np.ceil(n1 / s) * s
    out = {}
    for name in ("mnt", "mns"):
        ctx.log(f"{name} {e1 - e0:.0f} x {n1 - n0:.0f} m at {s} m")
        z, grid = read_window(p[name], e0, n0, e1, n1, s, log=lambda m: None)
        out[name] = (z, grid)
        ctx.log(f"{name}: {z.shape}, {grid['bytes'] / 1e6:.0f} MB downloaded, no data {np.isnan(z).mean():.4f}")
    gm, gs = out["mnt"][1], out["mns"][1]
    assert (gm["e0"], gm["n0"], gm["step"]) == (gs["e0"], gs["n0"], gs["step"]) and out["mnt"][0].shape == out["mns"][0].shape
    np.savez_compressed(ctx.out / "lidar.npz", mnt=out["mnt"][0], mns=out["mns"][0], e0=gm["e0"], n0=gm["n0"],
                        step=gm["step"])
    return {"shape": list(out["mnt"][0].shape), "e0": gm["e0"], "n0": gm["n0"], "step": gm["step"],
            "downloaded_mb": round((gm["bytes"] + gs["bytes"]) / 1e6, 1),
            "nodata_share": {k: float(np.isnan(v[0]).mean()) for k, v in out.items()}}


def trees_params(area: str) -> dict:
    p = extent_params(area)
    p["url"] = params()["fetch"]["trees"]
    return p


def fetch_trees(ctx):
    """The national LiDAR 2024 tree survey (ACT, CC0), cut to the commune extent while it streams."""
    p = ctx.params
    e0, n0, e1, n1 = area_bbox_en(p["extent_area"], p["margin_m"])
    far = 1500.0

    def inside(r):
        try:
            x, y = float(r["luref_x"]), float(r["luref_y"])
        except (TypeError, ValueError):
            return False
        return e0 <= x <= e1 and n0 <= y <= n1

    def skip(a, b):
        try:
            xs = (float(a["luref_x"]), float(b["luref_x"])); ys = (float(a["luref_y"]), float(b["luref_y"]))
        except (TypeError, ValueError):
            return False
        return (max(xs) < e0 - far or min(xs) > e1 + far or max(ys) < n0 - far or min(ys) > n1 + far)

    cols = {k: [] for k in ("e", "n", "h", "cmax", "cmin", "cmean", "terrain", "type", "uuid")}
    for r in stream_table(p["url"], "tree", inside, log=ctx.log, skip_page=skip):
        cols["e"].append(float(r["luref_x"])); cols["n"].append(float(r["luref_y"]))
        cols["h"].append(float(r["tree_height"])); cols["terrain"].append(float(r["terrain"]))
        cols["cmax"].append(float(r["crown_max"])); cols["cmin"].append(float(r["crown_min"]))
        cols["cmean"].append(float(r["crown_mean"]))
        t = r["tree_type"]
        cols["type"].append(TREE_TYPES.index(t) if t in TREE_TYPES else 3)
        cols["uuid"].append(r["tree_uuid"])
    arr = {k: np.array(v, np.float64 if k in ("e", "n") else (np.int8 if k == "type" else np.float32))
           for k, v in cols.items() if k != "uuid"}
    np.savez_compressed(ctx.out / "trees.npz", **arr, uuid=np.array(cols["uuid"]), type_names=np.array(TREE_TYPES))
    return {"trees": len(cols["e"]), "by_type": {t: int((arr["type"] == i).sum()) for i, t in enumerate(TREE_TYPES)}}
