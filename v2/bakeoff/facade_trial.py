"""Job C4, the facade front-on trial (PLAN_V2 section 7, "Straight windows in C"): paint a wall seen exactly
front-on, then put the painting back on its 3D wall, so its lines are straight by construction.

    pick(scene)             ten buildings spread over the test area, and their walls that face the camera and carry
                            windows (walls turned away are never seen, so they are not painted)
    make_inputs(scene, d)   each wall as a 1024 px front-on drawing: the wall's outline in its plain colour, the
                            facade layout's windows, doors and shop fronts, ink outlines; and its layout map
    Projector               layer 5 as method A draws it, with each trial wall's pixels (the wall and its openings)
                            read from its painting at the pixel's place on the wall (metres along and up); the
                            mesh's ink outlines on top
    evaluate(...)           on the trial buildings, method A against C4's projected facades (each seed): the line
                            score (L5.2's measure), the flat-light check (no baked shadow: dataset.flat_light) and
                            the car detector on the paintings; and a preview sheet
    build_view(...)         a small C4 build for the bake-off viewer: method A's release with layer 5 drawn again
                            from the mesh for the tiles the trial buildings touch (every other tile and layer is
                            A's own, linked)

Nothing is warped: a painting is sampled at the wall's own coordinates. A trial result, not a build stage (owner,
10 Nov 2026: C4 runs on its own, with v1's style model): the result says whether painting facades front-on keeps
lines straight, and whether it looks richer than A.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from v2.layers.common import TILE, VIEW, Tile, pal, project

WIN = 1024
MARGIN = 48
MAX_PX_M = 64.0


def _rect(r):
    return [float(x) for x in r[:4]]


def pick(scene, n=10):
    """[(building index, [wall index, ...])]: buildings with two camera-facing walls of 5-30 m carrying at least
    four windows each (one such wall where too few have two), spread over the area by a fixed order."""
    from v2.layers.geometry import h01
    bidx = {b["id"]: i for i, b in enumerate(scene.buildings)}
    by = {}
    for wi, w in enumerate(scene.facades["walls"]):
        bi = bidx.get(w["building"])
        if bi is None or w.get("party") or len(w["windows"]) < 4:
            continue
        if not (5 <= w["length"] <= 30 and 6 <= w["height"] <= 22):
            continue
        if float(np.dot(w["normal"], VIEW[:2])) > -0.25:          # turned away from the camera, or seen edge-on
            continue
        by.setdefault(bi, []).append(wi)
    two = sorted((b for b, ws in by.items() if len(ws) >= 2), key=lambda b: h01(scene.buildings[b]["id"] + "c4"))
    one = sorted((b for b, ws in by.items() if len(ws) == 1), key=lambda b: h01(scene.buildings[b]["id"] + "c4"))
    chosen = (two + one)[:n]
    return [(b, by[b][:3]) for b in chosen]


def wall_frame(w):
    """Front-on drawing frame of a wall: scale (px per m), the x of u = 0 and of u = length (mirrored so the wall
    is seen from outside), the y of the wall's foot."""
    L, H = float(w["length"]), float(w["height"])
    s = min((WIN - 2 * MARGIN) / L, (WIN - 2 * MARGIN) / H, MAX_PX_M)
    (e0, n0, _), (e1, n1, _) = w["base"]
    ux, uy = (e1 - e0) / L, (n1 - n0) / L
    nx, ny = w["normal"]
    right = (-ny, nx)                                             # to the right of someone facing the wall
    flip = (ux * right[0] + uy * right[1]) < 0
    x0 = (WIN - L * s) / 2
    yb = WIN - MARGIN - max(0.0, (WIN - 2 * MARGIN - H * s) / 2)
    return {"s": s, "x0": x0, "yb": yb, "flip": bool(flip), "L": L, "H": H}


def uv_to_xy(f, u, v):
    u = np.asarray(u, float)
    x = f["x0"] + (f["L"] - u if f["flip"] else u) * f["s"]
    return x, f["yb"] - np.asarray(v, float) * f["s"]


def draw_wall(w, f):
    """(unlit, layout) of one wall, front-on, in the plain art's colours (flat, no light)."""
    paper = tuple(int(x) for x in pal("ink", "paper"))
    wall = tuple(int(x) for x in pal("buildings", "facade_cream"))
    glass = tuple(int(x) for x in pal("buildings", "window"))
    door = tuple(int(x) for x in (pal("buildings", "window") * 0.4 + pal("trees", "trunk") * 0.6))
    shop = tuple(int(x) for x in (pal("buildings", "window") * 0.75 + pal("ink", "paper") * 0.25))
    ink = tuple(int(x) for x in pal("ink", "line_soft"))
    im = Image.new("RGB", (WIN, WIN), paper)
    lay = Image.new("RGB", (WIN, WIN), (255, 255, 255))
    d, dl = ImageDraw.Draw(im), ImageDraw.Draw(lay)
    out = w.get("outline") or [[0, 0], [f["L"], 0], [f["L"], f["H"]], [0, f["H"]], [0, 0]]
    X, Y = uv_to_xy(f, [p[0] for p in out], [p[1] for p in out])
    poly = list(zip(X.tolist(), Y.tolist()))
    d.polygon(poly, fill=wall)
    d.line(poly + [poly[0]], fill=ink, width=3)
    dl.line(poly + [poly[0]], fill=(0, 0, 0), width=3)
    for rects, col in ((w["windows"], glass), (w["doors"], door), (w["shopfronts"], shop)):
        for r in rects:
            u0, v0, u1, v1 = _rect(r)
            xs, ys = uv_to_xy(f, [u0, u1], [v0, v1])
            box = (min(xs), min(ys), max(xs), max(ys))
            d.rectangle(box, fill=col, outline=ink, width=2)
            dl.rectangle(box, fill=(90, 90, 90), outline=(0, 0, 0), width=2)
    return im, lay


def make_inputs(scene, folder: Path, n=10):
    folder.mkdir(parents=True, exist_ok=True)
    for p in folder.glob("*"):
        p.unlink()
    walls = scene.facades["walls"]
    meta = {"buildings": [], "facades": {}}
    for bi, ws in pick(scene, n):
        meta["buildings"].append({"index": bi, "id": scene.buildings[bi]["id"], "walls": ws})
        for wi in ws:
            f = wall_frame(walls[wi])
            im, lay = draw_wall(walls[wi], f)
            name = f"f{wi}"
            im.save(folder / f"{name}.unlit.png")
            lay.save(folder / f"{name}.layout.png")
            meta["facades"][name] = {"wall": wi, "building": bi, **f}
    (folder / "facades.json").write_text(json.dumps(meta, indent=1))
    return meta


# ------------------------------------------------------------------------------------------------ projection
class Projector:
    """Layer 5 as method A draws it, with the trial walls' painted facades put back on the walls."""

    def __init__(self, R_a, inputs: Path, painted: Path, seed_k=0, texel_m=0.0625):
        self.R = R_a
        self.meta = json.loads((inputs / "facades.json").read_text())
        self.walls = R_a.scene.facades["walls"]
        self.trial_b = {b["index"] for b in self.meta["buildings"]}
        self.tex = {}
        for name, f in self.meta["facades"].items():
            p = painted / f"{name}_{seed_k}.png"
            if not p.exists():
                continue
            # read at texel_m per texel (twice the map's resolution), area-filtered, so a map pixel does not alias
            k = min(1.0, (1 / texel_m) / f["s"])
            n = max(int(round(WIN * k)), 8)
            img = np.asarray(Image.open(p).convert("RGB").resize((n, n), Image.BOX), np.float64)
            self.tex[f["wall"]] = (img, f, n / WIN, int(f["building"]))
        self._took, self.painted = [], None

    def shader(self, mi, ti, P, nrm, base, px, py, cls, obj):
        rgb, pcls = self.R._shade_buildings_a(mi, ti, P, nrm, base, px, py, cls, obj)
        b = self.R.building_meshes[0]
        upright = mi == 1                                         # an opening (window, door, shop front, shutter)
        on_b = mi == 0
        upright[on_b] = b["kind"][ti[on_b]] == 2                  # a wall face
        for wi, (img, f, k, bi) in self.tex.items():
            m = upright & (obj == bi)
            if not m.any():
                continue
            w = self.walls[wi]
            (e0, n0, z0), (e1, n1, _) = w["base"]
            ux, uy = (e1 - e0) / f["L"], (n1 - n0) / f["L"]
            nx, ny = w["normal"]
            dx, dy = P[m, 0] - e0, P[m, 1] - n0
            u = dx * ux + dy * uy
            v = P[m, 2] - z0
            # on this wall: in its plane (openings sit 0.05 m in front of it), within its length and height
            on = (np.abs(dx * nx + dy * ny) < 0.15) & (u >= 0) & (u <= f["L"]) & (v >= -0.02) & (v <= f["H"] + 0.02)
            if not on.any():
                continue
            x, y = uv_to_xy(f, u[on], v[on])
            xi = np.clip((x * k).astype(int), 0, img.shape[1] - 1)
            yi = np.clip((y * k).astype(int), 0, img.shape[0] - 1)
            sel = np.flatnonzero(m)[on]
            rgb[sel] = img[yi, xi]
            self._took.append((px[sel], py[sel]))
        return rgb, pcls

    def layer(self, tile):
        """The layer tile; `self.painted` is then the tile's mask of pixels that took a painting."""
        self._took = []
        L = self.R._mesh_layer(tile, self.R.building_meshes, shader=self.shader)
        self.painted = np.zeros((tile.size, tile.size), bool)
        for x, y in self._took:
            self.painted[np.floor(y).astype(int) - tile.py0, np.floor(x).astype(int) - tile.px0] = True
        return L


class DictCache:
    def __init__(self):
        self.c = {}

    def get(self, tx, ty):
        return self.c.get((tx, ty))


def trial_tiles(sc, meta, ring=0):
    """The zoom-0 tiles the trial buildings' model lines fall in (and `ring` tiles round them)."""
    from v2.checks import line_checks as lc
    from v2.layers import geometry as G
    trial = np.array(sorted(b["index"] for b in meta["buildings"]))
    A, B, O = lc.feature_edges(G.buildings_mesh(sc))
    Ps, Ds, Os = lc.samples(A, B, O)
    m = np.isin(Os, trial)
    px, py, _ = project(Ps[m, 0], Ps[m, 1], Ps[m, 2])
    tiles = {(int(a), int(b)) for a, b in zip(np.floor(px / TILE), np.floor(py / TILE))}
    return sorted({(tx + dx, ty + dy) for tx, ty in tiles for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)})


def _mosaic(cache, tiles, key, fill):
    """One array over the box of `tiles` from a DictCache's tiles."""
    xs, ys = [t[0] for t in tiles], [t[1] for t in tiles]
    x0, y0 = min(xs), min(ys)
    first = next(iter(cache.c.values()))[key]
    out = np.full(((max(ys) - y0 + 1) * TILE, (max(xs) - x0 + 1) * TILE) + first.shape[2:], fill, first.dtype)
    for (tx, ty) in tiles:
        t = cache.c.get((tx, ty))
        if t is not None:
            out[(ty - y0) * TILE:(ty - y0 + 1) * TILE, (tx - x0) * TILE:(tx - x0 + 1) * TILE] = t[key]
    return out, x0 * TILE, y0 * TILE


def evaluate(R_a, c_dir: Path, out_dir: Path, seeds=(0, 1), detector=True):
    """The trial buildings in method A and with C4's projected facades (each seed): the line score, the flat-light
    check per building, the car detector on the paintings; a preview sheet. Returns the result (also written to
    out_dir/c4_trial.json)."""
    from v2.bakeoff.dataset import flat_light
    from v2.checks import line_checks as lc
    from v2.config import params
    from v2.layers import geometry as G
    P = params()["g1"]
    sc = R_a.scene
    inputs, painted = c_dir / "facade_inputs", c_dir / "facades"
    meta = json.loads((inputs / "facades.json").read_text())
    trial = np.array(sorted(b["index"] for b in meta["buildings"]))
    lines = {}
    for name, (A, B, O) in (("edges", lc.feature_edges(G.buildings_mesh(sc))), ("windows", lc.window_rows(sc))):
        Ps, Ds, Os = lc.samples(A, B, O)
        m = np.isin(Os, trial)
        lines[name] = (Ps[m], Ds[m], Os[m])
    near = trial_tiles(sc, meta, ring=1)
    projs = {}
    for k in seeds:
        pr = Projector(R_a, inputs, painted, seed_k=k)
        if pr.tex:
            projs[f"C4 seed {k}"] = pr
    variants = {"A": DictCache(), **{n: DictCache() for n in projs}}
    for tx, ty in near:
        t = Tile(tx, ty, apron=0)
        for name in variants:
            L = R_a.buildings(t) if name == "A" else projs[name].layer(t)
            variants[name].c[(tx, ty)] = {"rgb": L.rgb, "depth": L.depth, "ids": L.ids, "normal": L.normal,
                                          "painted": projs[name].painted if name != "A" else np.zeros(L.depth.shape, bool)}
    res = {"buildings": [{"index": int(b["index"]), "id": b["id"], "walls": len(b["walls"])} for b in meta["buildings"]],
           "facades": len(meta["facades"]), "painted": {n: len(p.tex) for n, p in projs.items()},
           "thresholds": {"line_score_share": P["line_score_share"], "line_score_px": P["line_score_px"], "flat_light": 0.05},
           "scores": {}}
    for vname, cache in variants.items():
        row = {}
        for name, (Ps, Ds, Os) in lines.items():
            seen, on = lc.score(cache, Ps, Ds, P["line_score_px"], P["line_min_step"], obj=Os)
            row[name] = {"seen": int(seen.sum()), "share": round(float(on.sum() / max(seen.sum(), 1)), 4)}
            per = {}
            for bi in trial:
                mb = Os == bi
                if seen[mb].sum():
                    per[int(bi)] = round(float(on[mb].sum() / seen[mb].sum()), 4)
            row[name]["by_building"] = per
        row["lines_pass"] = bool(all(row[k]["share"] >= P["line_score_share"] for k in ("edges", "windows")))
        # flat light, one building at a time: its walls turned different ways must be as light as each other
        rgb, _, _ = _mosaic(cache, near, "rgb", 0)
        ids, _, _ = _mosaic(cache, near, "ids", 0)
        nrm, _, _ = _mosaic(cache, near, "normal", 0.0)
        flat = {}
        for bi in trial:
            worst, bad = flat_light(rgb, np.where((ids >> 8) == bi, ids, 0), nrm)
            flat[int(bi)] = round(float(worst), 4)
        row["flat_light"] = {"by_building": flat, "worst": max(flat.values()), "over_5_percent": sum(v > 0.05 for v in flat.values())}
        row["flat_pass"] = row["flat_light"]["over_5_percent"] == 0
        if vname != "A":
            # the same, between the painted walls only (a building's unpainted walls keep A's own colour, which
            # the trial's drawings did not use: that difference is the trial's, not a shadow)
            took, _, _ = _mosaic(cache, near, "painted", False)
            fp = {}
            for bi in trial:
                worst, bad = flat_light(rgb, np.where(((ids >> 8) == bi) & took, ids, 0), nrm)
                fp[int(bi)] = round(float(worst), 4)
            row["flat_light_painted_walls"] = {"by_building": fp, "worst": max(fp.values()),
                                               "over_5_percent": sum(v > 0.05 for v in fp.values())}
        res["scores"][vname] = row
    c4 = {n: r for n, r in res["scores"].items() if n != "A"}
    if c4:
        res["best_seed"] = int(max(c4, key=lambda n: (c4[n]["windows"]["share"], c4[n]["edges"]["share"])).split()[-1])
    files = sorted(painted.glob("f*_[0-9].png"))
    # light across each painting itself: the wall's left and right halves, and its top and bottom halves (a
    # shadow under the eaves, a gradient from one side), by median luminance, within 5%
    from v2.layers.common import lum
    within = {}
    for p in files:
        f = meta["facades"].get(p.stem.rsplit("_", 1)[0])
        if f is None:
            continue
        x0, x1 = int(f["x0"]) + 6, int(f["x0"] + f["L"] * f["s"]) - 6
        y1, y0 = int(f["yb"]) - 6, int(f["yb"] - f["H"] * f["s"]) + 6
        Lm = lum(np.asarray(Image.open(p).convert("RGB"), float)[y0:y1, x0:x1])
        if Lm.size < 400:
            continue
        h, w = Lm.shape
        rel = lambda a, b: float(abs(np.median(a) - np.median(b)) / max(np.median(a), np.median(b), 1e-6))  # noqa: E731
        within[p.name] = {"left_right": round(rel(Lm[:, : w // 2], Lm[:, w // 2:]), 4),
                          "top_bottom": round(rel(Lm[: h // 2], Lm[h // 2:]), 4)}
    if within:
        res["light_within_paintings"] = {
            "paintings": len(within), "worst_left_right": max(v["left_right"] for v in within.values()),
            "worst_top_bottom": max(v["top_bottom"] for v in within.values()),
            "over_5_percent": sum(max(v.values()) > 0.05 for v in within.values()), "by_file": within}
    if detector and files:
        from v2.bakeoff import paintcheck as PC
        det = PC.owl(files, out_dir / "owl", mpp=1 / float(np.median([f["s"] for f in meta["facades"].values()])))
        res["cars"] = {"paintings": len(files), "detections": sum(len(v) for v in det["by_file"].values()),
                       "max_score": det["max_score"]}
    out_dir.mkdir(parents=True, exist_ok=True)
    # preview: each trial building at 2x, method A beside the projected facades
    cols = list(variants)
    rows = []
    for b in meta["buildings"]:
        bi = b["index"]
        Ps = lines["edges"][0][lines["edges"][2] == bi]
        if not len(Ps):
            continue
        qx, qy, _ = project(Ps[:, 0], Ps[:, 1], Ps[:, 2])
        cx, cy = int(np.median(qx)), int(np.median(qy))
        x0, y0 = cx - 150, cy - 150
        strip = []
        for v in cols:
            im = np.full((300, 300, 3), 235, np.uint8)
            for (tx, ty), t in variants[v].c.items():
                a0, b0 = tx * TILE - x0, ty * TILE - y0
                xs0, ys0, xs1, ys1 = max(a0, 0), max(b0, 0), min(a0 + TILE, 300), min(b0 + TILE, 300)
                if xs1 <= xs0 or ys1 <= ys0:
                    continue
                sub = t["rgb"][ys0 - b0:ys1 - b0, xs0 - a0:xs1 - a0]
                dm = np.isfinite(t["depth"][ys0 - b0:ys1 - b0, xs0 - a0:xs1 - a0])
                tgt = im[ys0:ys1, xs0:xs1]
                tgt[dm] = sub[dm]
            strip.append(np.asarray(Image.fromarray(im).resize((600, 600), Image.NEAREST)))
        rows.append(np.concatenate(strip, 1))
    if rows:
        half = (len(rows) + 1) // 2
        blank = np.full_like(rows[0], 235)
        left = np.concatenate(rows[:half], 0)
        right = np.concatenate(rows[half:] + [blank] * (half - (len(rows) - half)), 0)
        sheet = Image.fromarray(np.concatenate([left, right], 1))
        d = ImageDraw.Draw(sheet)
        for side in (0, 1):
            for i, v in enumerate(cols):
                x = side * left.shape[1] + i * 600
                d.rectangle((x + 6, 6, x + 120, 26), fill=(255, 255, 255))
                d.text((x + 12, 10), v, fill=(0, 0, 0))
        sheet.save(out_dir / "c4_trial.png")
    (out_dir / "c4_trial.json").write_text(json.dumps(res, indent=1))
    return res


def build_view(R_a, release_a: Path, c_dir: Path, out: Path, seed_k=0):
    """The small C4 build: method A's release, with layer 5 drawn again from the mesh (Projector) for the tiles the
    trial buildings touch. Every other tile, level 0, and every other layer is A's own file, linked. The far-zoom
    set stays A's (the trial is looked at close up)."""
    import os
    import shutil
    from v2.layers.common import write_tile
    from v2.layers.tiles import pyramid, write_index
    release_a = Path(release_a)
    meta = json.loads((c_dir / "facade_inputs" / "facades.json").read_text())
    pr = Projector(R_a, c_dir / "facade_inputs", c_dir / "facades", seed_k=seed_k)
    if not pr.tex:
        raise SystemExit(f"C4: no painted facade of seed {seed_k} in {c_dir / 'facades'}")
    idx_a = json.loads((release_a / "index.json").read_text())
    lay = idx_a["layers"]["buildings"]
    if out.exists():
        shutil.rmtree(out)
    z0 = out / "buildings" / "0"
    z0.mkdir(parents=True)
    touched = {f"{tx}_{ty}" for tx, ty in trial_tiles(R_a.scene, meta)}
    idx0 = {}
    src0 = (release_a / "buildings" / "0").resolve()
    for name, dmin in lay["tiles"]["0"].items():
        if name in touched:
            t = Tile(*(int(v) for v in name.split("_")))
            L = pr.layer(t)
            c = t.crop
            idx0[name] = write_tile(z0, name, rgb=c(L.rgb), depth=c(L.depth), normal=c(L.normal), k=c(L.k), ids=c(L.ids), q=101)
        else:
            for ext in ("c.webp", "g.bin", "k.bin", "i.bin"):
                if (src0 / f"{name}.{ext}").exists():
                    os.symlink(src0 / f"{name}.{ext}", z0 / f"{name}.{ext}")
            idx0[name] = dmin
    idx = pyramid(out / "buildings", idx0, lay["levels"], lossless=True, has_ids=True)
    d = write_index(out / "buildings", "buildings", idx, ["k.bin", "i.bin"])
    for p in release_a.iterdir():
        if p.name not in ("buildings", "index.json", "manifest.json"):
            os.symlink(p.resolve(), out / p.name)
    idx_a["layers"]["buildings"] = {**lay, "levels": d["levels"], "tiles": d["tiles"], "files": d["files"]}
    (out / "index.json").write_text(json.dumps(idx_a))
    (out / "trial.json").write_text(json.dumps({"what": "C4 facade front-on trial: method A's release with layer 5 drawn again "
                                                        "for the trial buildings' tiles", "from_release": str(release_a),
                                                "seed": seed_k, "tiles_drawn": sorted(touched & set(idx0)),
                                                "facades_painted": len(pr.tex), "buildings": len(meta["buildings"])}, indent=1))
    return {"folder": str(out), "tiles_drawn": len(touched & set(idx0)), "facades": len(pr.tex)}
