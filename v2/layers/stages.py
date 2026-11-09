"""Build stages of the layers (phase 1, code layers on the test area). Each colour layer is its own stage that reads
the scene only (never another layer's tiles), writes its tile set (zoom 0 and the pyramid) and index.json.

layer_ground .. layer_trees   layers 1-4 and the placeholders for 5-7 (plain code buildings, structures, trees)
layer_buffers                 layer 8: depth, normal, height above the terrain and ids of the nearest surface
layer_light                   layer 9: the shadow height map (the viewer lights from it)
layer_night                   layer 10: windows, doors, shop fronts and street lamps
layer_vehicles                layer 12: roads and profiles for the simulation, trams and trains on the graph
layer_labels                  layer 15: labels and pins
release                       the viewer's folder: every layer's tiles and data behind one index.json
"""
from __future__ import annotations

import json
import math
import os
import shutil
from pathlib import Path

import numpy as np

from v2.layers.common import COLOUR_LAYERS, Scene, TILE, pack_bin, write_tile
from v2.layers.tiles import layer_writer, levels_for, pyramid, run_tiles, write_index

LOSSLESS = {"relief", "water"}
OUT_OF_SCOPE_NOTE = {
    "buildings": "placeholder for layer 5 (bake-off): plain evenly lit code buildings",
    "structures": "placeholder for layer 6 (bake-off): plain code bridges, viaducts and the lift",
    "trees": "placeholder for layer 7 (bake-off): flat code crowns at the surveyed size",
}


def _osm(ctx):
    return ctx.dep("fetch_osm_ground") / "ground.json", ctx.dep("fetch_osm_transport") / "transport.json"


def colour_layer(name):
    def build(ctx):
        sc_folder = ctx.dep("scene")
        sc = Scene(sc_folder)
        g, t = _osm(ctx)
        tiles = sc.tiles
        folder = ctx.out / "tiles"
        idx0 = run_tiles(sc_folder, g, t, tiles, layer_writer(name, name in LOSSLESS), folder / "0",
                         workers=ctx.workers)
        lv = levels_for(tiles)
        idx = pyramid(folder, idx0, lv, lossless=name in LOSSLESS, has_ids=name in ("transport", "buildings", "structures", "trees"))
        write_index(folder, name, idx, ["k.bin"] + (["i.bin"] if name in ("transport", "buildings", "structures", "trees") else []))
        return {"layer": name, "tiles_z0": len(idx0), "levels": lv, "note": OUT_OF_SCOPE_NOTE.get(name, ""),
                "bytes_z0": sum(p.stat().st_size for p in (folder / "0").iterdir())}
    build.__name__ = f"layer_{name}"
    build.__qualname__ = build.__name__
    return build


# ------------------------------------------------------------------------------------------------ layer 8
class _BuffersJob:
    def __call__(self, R, tile):
        H = W = tile.size
        depth = np.full((H, W), np.inf)
        normal = np.zeros((H, W, 3))
        ids = np.zeros((H, W), np.uint32)
        which = np.zeros((H, W), np.uint8)
        for li, name in enumerate(COLOUR_LAYERS):
            L = R.layer(name, tile)
            d = L.depth
            if name == "relief":
                d = np.where(L.k == 3, d, np.inf)          # relief shading is not a surface; its walls are
            m = d <= depth                                  # ties go to the later layer
            depth[m] = d[m]
            normal[m] = L.normal[m]
            if L.ids is not None:
                ids[m] = L.ids[m]
            which[m] = li + 1
        if not np.isfinite(depth).any():
            return None
        from v2.layers.common import unproject
        px, py = tile.centres
        ok = np.isfinite(depth)
        e, n, z = unproject(np.broadcast_to(px[None, :], depth.shape)[ok], np.broadcast_to(py[:, None], depth.shape)[ok], depth[ok])
        hgt = np.zeros(depth.shape, np.uint16)
        hgt[ok] = np.clip(np.round((z - R.hf.sample(e, n)) * 100), 0, 65535)
        c = tile.crop
        depth, normal, ids, which, hgt = c(depth), c(normal), c(ids), c(which), c(hgt)

        def write(folder, tile, q):
            dm = write_tile(folder, tile.name, depth=depth, normal=normal, k=which, ids=ids)
            (folder / f"{tile.name}.h.bin").write_bytes(pack_bin(hgt))
            return dm
        return write


def layer_buffers(ctx):
    sc_folder = ctx.dep("scene")
    sc = Scene(sc_folder)
    g, t = _osm(ctx)
    tiles = sc.tiles
    folder = ctx.out / "tiles"
    idx0 = run_tiles(sc_folder, g, t, tiles, _BuffersJob(), folder / "0", workers=ctx.workers)
    lv = levels_for(tiles)
    idx = pyramid(folder, idx0, lv, has_ids=True, has_h=True)
    # the pyramid writes an (empty) colour tile per parent; layer 8 has no colour
    for p in folder.rglob("*.c.webp"):
        p.unlink()
    d = write_index(folder, "buffers", idx, ["k.bin", "i.bin", "h.bin"])
    d["files"] = ["g.bin", "k.bin", "i.bin", "h.bin"]
    d["k"] = "nearest layer: 1 + index in " + ",".join(COLOUR_LAYERS)
    (folder / "index.json").write_text(json.dumps(d, separators=(",", ":")))
    return {"tiles_z0": len(idx0), "levels": lv}


# ------------------------------------------------------------------------------------------------ layer 9
def layer_light(ctx):
    from v2.layers.light import LIGHT, build_heightmap
    from v2.layers.render import Renderer
    sc = Scene(ctx.dep("scene"))
    g, t = _osm(ctx)
    R = Renderer(sc, g, t)
    hm = build_heightmap(R)
    A, B = hm.encode()
    (ctx.out / "shadow_a.bin").write_bytes(pack_bin(A))
    (ctx.out / "shadow_b.bin").write_bytes(pack_bin(B))
    np.save(ctx.out / "building_id.npy", hm.b_id.astype(np.int32))
    meta = {"e0": hm.e0, "n0": hm.n0, "step": hm.step, "width": hm.shape[1], "height": hm.shape[0], "zbase": hm.zbase,
            "files": ["shadow_a.bin", "shadow_b.bin"], "encoding": LIGHT["heightmap"]}
    ctx.write_json("light.json", meta, indent=1)
    return {"shape": list(hm.shape), "bytes": (ctx.out / "shadow_a.bin").stat().st_size + (ctx.out / "shadow_b.bin").stat().st_size}


# ------------------------------------------------------------------------------------------------ layers 10, 12, 15
def layer_night(ctx):
    from v2.layers.data import night_data
    from v2.layers.render import Renderer
    sc = Scene(ctx.dep("scene"))
    g, t = _osm(ctx)
    win, lamps = night_data(Renderer(sc, g, t))
    (ctx.out / "windows.bin").write_bytes(win.tobytes())
    (ctx.out / "lamps.bin").write_bytes(lamps.tobytes())
    ctx.write_json("night.json", {"windows": len(win), "lamps": len(lamps), "window_floats": 8, "lamp_floats": 3})
    return {"windows": int(len(win)), "lamps": int(len(lamps))}


def layer_vehicles(ctx):
    from v2.layers.data import transit_data, vehicles_data
    sc = Scene(ctx.dep("scene"))
    v = vehicles_data(sc)
    ctx.write_json("vehicles.json", v)
    tr = transit_data(sc, ctx.params["transit"])
    ctx.write_json("transit.json", tr)
    return {"roads": len(v["roads"]), "edges": len(v["edges"]), "transit_paths": len(tr["shapes"]),
            "trips": len(tr["trips"]), "by_kind": {k: sum(1 for t in tr["trips"] if t["k"] == k) for k in ("tram", "train", "funicular")}}


def layer_labels(ctx):
    from v2.layers.data import labels_data
    from v2.layers.render import Renderer
    sc = Scene(ctx.dep("scene"))
    g, t = _osm(ctx)
    lab = labels_data(Renderer(sc, g, t))
    ctx.write_json("labels.json", lab)
    return {"labels": len(lab), "by_cat": {c: sum(1 for x in lab if x["cat"] == c) for c in sorted({x["cat"] for x in lab})}}


# ------------------------------------------------------------------------------------------------ release
RELEASE_LAYERS = COLOUR_LAYERS + ["buffers"]


def release(ctx):
    """The viewer's folder: links to every layer's tiles and data, and index.json describing them."""
    from v2.config.camera import camera
    sc = Scene(ctx.dep("scene"))
    idx = {"area": sc.area, "camera": {k: camera()[k] for k in ("origin_en", "elevation_deg", "mpp", "frame", "v1_offset_px")},
           "tile_px": TILE, "layers": {}, "depth_cm": [None, None]}
    from v2.layers.common import depth_ref
    lo, hi = 10 ** 12, -10 ** 12
    for name in RELEASE_LAYERS:
        src = ctx.dep(f"layer_{name}") / "tiles"
        os.symlink(src, ctx.out / name)
        li = json.loads((src / "index.json").read_text())
        idx["layers"][name] = {"levels": li["levels"], "tiles": li["tiles"], "files": li["files"]}
        for z, v in li["tiles"].items():
            for n, dm in v.items():
                r = depth_ref(n, int(z)) * 100
                lo, hi = min(lo, int(math.floor(dm + r.min()))), max(hi, int(math.ceil(dm + 65535 + r.max())))
    idx["depth_cm"] = [lo, hi]
    idx["levels"] = max(v["levels"] for v in idx["layers"].values())
    tx = [int(n.split("_")[0]) for n in idx["layers"]["buffers"]["tiles"]["0"]]
    ty = [int(n.split("_")[1]) for n in idx["layers"]["buffers"]["tiles"]["0"]]
    idx["extent_px"] = [min(tx) * TILE, min(ty) * TILE, (max(tx) + 1) * TILE, (max(ty) + 1) * TILE]
    for name, files in (("layer_light", ["light.json", "shadow_a.bin", "shadow_b.bin"]),
                        ("layer_night", ["night.json", "windows.bin", "lamps.bin"]),
                        ("layer_vehicles", ["vehicles.json", "transit.json"]),
                        ("layer_labels", ["labels.json"])):
        for f in files:
            os.symlink(ctx.dep(name) / f, ctx.out / f)
    idx["light"] = json.loads((ctx.dep("layer_light") / "light.json").read_text())
    idx["night"] = json.loads((ctx.dep("layer_night") / "night.json").read_text())
    from v2.config import CONFIG
    idx["config"] = json.loads((CONFIG / "light.json").read_text())
    idx["palette"] = json.loads((CONFIG / "palette.json").read_text())
    idx["polygon_en"] = [list(map(lambda v: round(v, 2), p)) for p in sc.polygon.exterior.coords]
    ctx.write_json("index.json", idx)
    return {"layers": list(idx["layers"]), "levels": idx["levels"], "extent_px": idx["extent_px"]}
