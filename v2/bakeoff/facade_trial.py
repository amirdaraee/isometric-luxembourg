"""Job C4, the facade front-on trial (PLAN_V2 section 7, "Straight windows in C"): paint a wall seen exactly
front-on, then put the painting back on its 3D wall, so its lines are straight by construction.

    pick(scene)             ten buildings spread over the test area, and their walls that face the camera and carry
                            windows (walls turned away are never seen, so they are not painted)
    make_inputs(scene, d)   each wall as a 1024 px front-on drawing: the wall's outline in its plain colour, the
                            facade layout's windows, doors and shop fronts, ink outlines; and its layout map
    shader(...)             layer 5 with each trial wall's pixels read from its painting at the pixel's place on the
                            wall (metres along and up), everything else plain; the mesh's ink outlines on top
    evaluate(...)           the line score (L5.2's measure) of the trial buildings, three ways: method A, C as
                            painted in the map view (C3), and C4's projected facades; and a preview

Nothing is warped: a painting is sampled at the wall's own coordinates. A trial result, not a build stage: C's
release keeps C3's paintings whatever the outcome here, and the result decides how the city would be painted.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from v2.layers.common import CLASS, TILE, VIEW, Tile, pal, project

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
    """Layer 5 of the trial buildings with their painted facades put back on the walls."""

    def __init__(self, R_plain, R_a, inputs: Path, painted: Path, seed_k=0, texel_m=0.0625):
        self.R = R_plain
        self.meta = json.loads((inputs / "facades.json").read_text())
        self.walls = R_plain.scene.facades["walls"]
        self.trial_b = {b["index"] for b in self.meta["buildings"]}
        self.tri_wall = R_a.art_a.tri_wall                      # wall of every wall triangle of the buildings mesh
        # the wall of every opening triangle (geometry.openings_mesh: two triangles per rectangle, in this order)
        bidx = {b["id"]: i for i, b in enumerate(R_plain.scene.buildings)}
        ow = []
        for wi, w in enumerate(self.walls):
            if bidx.get(w["building"]) is None:
                continue
            ow += [wi] * (2 * (len(w["windows"]) + len(w["doors"]) + len(w["shopfronts"])))
        self.open_wall = np.array(ow, np.int64)
        self.tex = {}
        for name, f in self.meta["facades"].items():
            p = painted / f"{name}_{seed_k}.png"
            if not p.exists():
                continue
            # read at texel_m per texel (twice the map's resolution), area-filtered, so a map pixel does not alias
            k = min(1.0, (1 / texel_m) / f["s"])
            n = max(int(round(WIN * k)), 8)
            img = np.asarray(Image.open(p).convert("RGB").resize((n, n), Image.BOX), np.float64)
            self.tex[f["wall"]] = (img, f, n / WIN)

    def shader(self, mi, ti, P, nrm, base, px, py, cls, obj):
        rgb = base.copy()
        b, o = self.R.building_meshes
        wall = np.full(len(mi), -1, np.int64)
        on_b = mi == 0
        wall[on_b] = np.where(b["kind"][ti[on_b]] == 2, self.tri_wall[ti[on_b]], -1)
        on_o = mi == 1
        wall[on_o] = self.open_wall[ti[on_o]]
        for wi, (img, f, k) in self.tex.items():
            m = wall == wi
            if not m.any():
                continue
            w = self.walls[wi]
            (e0, n0, z0), (e1, n1, _) = w["base"]
            ux, uy = (e1 - e0) / f["L"], (n1 - n0) / f["L"]
            u = (P[m, 0] - e0) * ux + (P[m, 1] - n0) * uy
            v = P[m, 2] - z0
            x, y = uv_to_xy(f, u, v)
            xi = np.clip((x * k).astype(int), 0, img.shape[1] - 1)
            yi = np.clip((y * k).astype(int), 0, img.shape[0] - 1)
            rgb[m] = img[yi, xi]
        return rgb

    def layer(self, tile):
        return self.R._mesh_layer(tile, self.R.building_meshes, shader=self.shader)


class DictCache:
    def __init__(self):
        self.c = {}

    def get(self, tx, ty):
        return self.c.get((tx, ty))


def evaluate(R_plain, R_a, release_a: Path, c_dir: Path, out_dir: Path):
    """Line score of the trial buildings for A, C3 (painted in the map view) and C4 (projected facades, each
    seed), and a preview of three of them."""
    from v2.bakeoff import compose
    from v2.checks import line_checks as lc
    from v2.checks.layer_checks import load
    from v2.config import params
    from v2.layers import geometry as G
    P = params()["g1"]
    sc = R_plain.scene
    meta = json.loads((c_dir / "facade_inputs" / "facades.json").read_text())
    trial = np.array(sorted(b["index"] for b in meta["buildings"]))
    lines = {}
    for name, (A, B, O) in (("edges", lc.feature_edges(G.buildings_mesh(sc))), ("windows", lc.window_rows(sc))):
        Ps, Ds, Os = lc.samples(A, B, O)
        m = np.isin(Os, trial)
        lines[name] = (Ps[m], Ds[m], Os[m])
    px, py, _ = project(lines["edges"][0][:, 0], lines["edges"][0][:, 1], lines["edges"][0][:, 2])
    tiles = sorted({(int(a), int(b)) for a, b in zip(np.floor(px / TILE), np.floor(py / TILE))})
    near = sorted({(tx + dx, ty + dy) for tx, ty in tiles for dx in (-1, 0, 1) for dy in (-1, 0, 1)})
    variants = {"A": DictCache(), "C3": DictCache()}
    projs = {}
    for k in (0, 1):
        pr = Projector(R_plain, R_a, c_dir / "facade_inputs", c_dir / "facades", seed_k=k)
        if pr.tex:
            projs[f"C4 seed {k}"] = pr
            variants[f"C4 seed {k}"] = DictCache()
    for tx, ty in near:
        t = Tile(tx, ty, apron=0)
        a = load(release_a, "buildings", t.name)
        if a is not None:
            variants["A"].c[(tx, ty)] = a
        if (c_dir / "painted").exists():
            L = compose.layer(R_plain, "c", "buildings", t, c_dir)
            variants["C3"].c[(tx, ty)] = {"rgb": L.rgb, "depth": L.depth, "ids": L.ids}
        for name, pr in projs.items():
            L = pr.layer(t)
            variants[name].c[(tx, ty)] = {"rgb": L.rgb, "depth": L.depth, "ids": L.ids}
    res = {"buildings": len(trial), "facades": len(meta["facades"]), "painted": {n: len(p.tex) for n, p in projs.items()}, "scores": {}}
    for vname, cache in variants.items():
        if not cache.c:
            continue
        row = {}
        for name, (Ps, Ds, Os) in lines.items():
            seen, on = lc.score(cache, Ps, Ds, P["line_score_px"], P["line_min_step"], obj=Os)
            row[name] = {"seen": int(seen.sum()), "share": round(float(on.sum() / max(seen.sum(), 1)), 4)}
        row["pass"] = bool(all(v["share"] >= P["line_score_share"] for v in row.values() if isinstance(v, dict)))
        res["scores"][vname] = row
    out_dir.mkdir(parents=True, exist_ok=True)
    # preview: the three trial buildings with the most seen window samples, each variant side by side
    cols = [v for v in variants if variants[v].c]
    rows = []
    for b in meta["buildings"][:4]:
        bi = b["index"]
        Ps = lines["edges"][0][lines["edges"][2] == bi]
        if not len(Ps):
            continue
        qx, qy, _ = project(Ps[:, 0], Ps[:, 1], Ps[:, 2])
        cx, cy = int(np.median(qx)), int(np.median(qy))
        x0, y0 = cx - 160, cy - 160
        strip = []
        for v in cols:
            im = np.full((320, 320, 3), 235, np.uint8)
            for (tx, ty), t in variants[v].c.items():
                a0, b0 = tx * TILE - x0, ty * TILE - y0
                xs0, ys0, xs1, ys1 = max(a0, 0), max(b0, 0), min(a0 + TILE, 320), min(b0 + TILE, 320)
                if xs1 <= xs0 or ys1 <= ys0:
                    continue
                sub = t["rgb"][ys0 - b0:ys1 - b0, xs0 - a0:xs1 - a0]
                dm = np.isfinite(t["depth"][ys0 - b0:ys1 - b0, xs0 - a0:xs1 - a0])
                tgt = im[ys0:ys1, xs0:xs1]
                tgt[dm] = sub[dm]
            strip.append(np.asarray(Image.fromarray(im).resize((640, 640), Image.NEAREST)))
        rows.append(np.concatenate(strip, 1))
    if rows:
        sheet = Image.fromarray(np.concatenate(rows, 0))
        d = ImageDraw.Draw(sheet)
        for i, v in enumerate(cols):
            d.rectangle((i * 640 + 6, 6, i * 640 + 150, 30), fill=(255, 255, 255))
            d.text((i * 640 + 12, 10), v, fill=(0, 0, 0))
        sheet.save(out_dir / "c4_trial.jpg", quality=82)
    (out_dir / "c4_trial.json").write_text(json.dumps(res, indent=1))
    return res
