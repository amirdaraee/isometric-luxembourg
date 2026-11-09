"""Checks of the code layers' tiles (specs layer-01..04, 08, palette.md), on the built release.

L1.1  every pixel of the area has a ground class            L1.2  no shading: a class is as bright on north and
L2.1  flat ground untouched by the relief                          south slopes (within 2%)
L2.2  every OSM wall with a drop >= 1.5 m drawn (>= 90%)      L3.1  water exactly where OSM has it (+- 1 px)
L4.1  100% of road, rail and tram centre lines inside the      L4.3  no drawn pixel of a tunnel
      drawn surface (brief 7)
L8.1  every colour layer's depth equals layer 8's where it is the nearest (<= 1 cm)
L8.2  normals unit length and facing the camera                L8.3  every id exists in the scene
P-1   no colour literal in the layer code: every colour from the palette
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import shapely

from v2.checks.framework import Report
from v2.config import V2
from v2.layers.common import (CLASS, COLOUR_LAYERS, TILE, Scene, Tile, VIEW, lum, project, read_tile, unproject)
from v2.layers.render import GROUND_CLASSES, Renderer


def release_tiles(rel: Path, layer: str, z: int = 0):
    idx = json.loads((rel / "index.json").read_text())
    return idx["layers"][layer]["tiles"].get(str(z), {})


def load(rel: Path, layer: str, name: str, z: int = 0):
    d = release_tiles(rel, layer, z)
    if name not in d:
        return None
    return read_tile(rel / layer / str(z), name, d[name], z=z)


def pixel_of(px, py):
    """Zoom-0 map pixel -> (tile name, row, col)."""
    tx, ty = np.floor(px / TILE).astype(int), np.floor(py / TILE).astype(int)
    return tx, ty, (np.floor(py) - ty * TILE).astype(int), (np.floor(px) - tx * TILE).astype(int)


class TileCache:
    def __init__(self, rel, layer, maxn=48):
        self.rel, self.layer, self.c, self.maxn = rel, layer, {}, maxn

    def get(self, tx, ty):
        k = (tx, ty)
        if k not in self.c:
            if len(self.c) >= self.maxn:
                self.c.pop(next(iter(self.c)))
            self.c[k] = load(self.rel, self.layer, f"{tx}_{ty}")
        return self.c[k]

    def lookup(self, px, py, what):
        """Values of `what` at zoom-0 pixels (arrays); None where the layer has no tile."""
        tx, ty, r, c = pixel_of(np.asarray(px, float), np.asarray(py, float))
        out = [None] * len(tx)
        for k in set(zip(tx.tolist(), ty.tolist())):
            t = self.get(*k)
            m = np.flatnonzero((tx == k[0]) & (ty == k[1]))
            for i in m:
                out[i] = None if t is None or what not in t else t[what][r[i], c[i]]
        return out


def check_layers(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    sc = Scene(ctx.dep("scene"))
    R = Renderer(sc, ctx.dep("fetch_osm_ground") / "ground.json", ctx.dep("fetch_osm_transport") / "transport.json")
    rep = Report("layers")
    names = sorted(release_tiles(rel, "buffers"))
    # ------------------------------------------------------------------ L1.1, L1.2, L2.1, L8.1, L8.2, L8.3
    missing_cls, area_px = 0, 0
    miss_ex = []
    slope_lum = {}
    flat_bad, flat_n, flat_ex = 0, 0, []
    align_bad, align_n, align_ex = 0, 0, []
    nrm_bad, nrm_n = 0, 0
    id_bad, id_ex = 0, []
    nb, ne, nt = len(sc.buildings), len(sc.graph["edges"]), len(sc.trees["e"])
    seen_b = set()
    cosmin = math.sin(math.radians(P["ground_slope_min_deg"]))
    for name in names:
        tx, ty = (int(v) for v in name.split("_"))
        tile = Tile(tx, ty, apron=0)
        t = R.terrain(tile)
        g = load(rel, "ground", name)
        if g is not None:
            m = t["inarea"]
            area_px += int(m.sum())
            bad = m & ((g["k"] == 0) | ~np.isfinite(g["depth"]))
            missing_cls += int(bad.sum())
            if bad.any() and len(miss_ex) < 8:
                miss_ex.append({"tile": name, "pixels": int(bad.sum())})
            ok = np.isfinite(g["depth"]) & (g["k"] > 0)
            kk = g["k"]
            border = np.zeros(kk.shape, bool)
            border[:, :-1] |= kk[:, :-1] != kk[:, 1:]; border[:, 1:] |= kk[:, :-1] != kk[:, 1:]
            border[:-1, :] |= kk[:-1, :] != kk[1:, :]; border[1:, :] |= kk[:-1, :] != kk[1:, :]
            from scipy.ndimage import binary_dilation
            ok &= ~binary_dilation(border, iterations=2)       # the ink line and the coding's blur round it
            n = g["normal"]
            horiz = np.hypot(n[..., 0], n[..., 1])
            steep = ok & (horiz >= cosmin)
            north = steep & (n[..., 1] > 0.5 * horiz)
            south = steep & (n[..., 1] < -0.5 * horiz)
            L = lum(g["rgb"])
            for k in np.unique(g["k"][steep]):
                s = slope_lum.setdefault(int(k), [0.0, 0, 0.0, 0])
                mn, ms = north & (g["k"] == k), south & (g["k"] == k)
                s[0] += float(L[mn].sum()); s[1] += int(mn.sum()); s[2] += float(L[ms].sum()); s[3] += int(ms.sum())
        r = load(rel, "relief", name)
        if r is not None:
            n = r["normal"]
            flat = np.isfinite(r["depth"]) & (r["k"] == 1) & (n[..., 2] > math.cos(math.radians(P["relief_flat_deg"])))
            f = r["rgb"].astype(float) / 255
            badf = flat & (np.abs(f - 1).max(-1) > P["relief_flat_tol"] + 0.5 / 255)
            flat_n += int(flat.sum()); flat_bad += int(badf.sum())
            if badf.any() and len(flat_ex) < 8:
                flat_ex.append({"tile": name, "pixels": int(badf.sum()), "min_factor": round(float(f[badf].min()), 3)})
        b = load(rel, "buffers", name)
        if b is None:
            continue
        which = b["k"]
        for li, L in enumerate(COLOUR_LAYERS):
            lt = load(rel, L, name)
            if lt is None:
                continue
            m = (which == li + 1) & np.isfinite(lt["depth"])
            if L == "relief":
                m &= lt["k"] == 3
            dd = np.abs(lt["depth"][m] - b["depth"][m])
            align_n += int(m.sum())
            nbad = int((dd > P["align_cm"] / 100 + 1e-6).sum())
            align_bad += nbad
            if nbad and len(align_ex) < 8:
                align_ex.append({"tile": name, "layer": L, "pixels": nbad, "max_cm": round(float(dd.max()) * 100, 2)})
        okb = np.isfinite(b["depth"])
        nn = b["normal"][okb]
        nrm_n += int(okb.sum())
        facing = nn @ (-VIEW)
        nrm_bad += int(((np.abs(np.linalg.norm(nn, axis=1) - 1) > P["normal_unit_tol"]) | (facing < -0.02)).sum())
        ids = b["ids"][okb]
        cls, obj = ids & 255, ids >> 8
        bad_ids = ((np.isin(cls, [CLASS["building"], CLASS["window"], CLASS["door"], CLASS["shopfront"]]) & (obj >= nb)) |
                   (np.isin(cls, [CLASS["road"], CLASS["rail"], CLASS["tram"], CLASS["path"], CLASS["steps"], CLASS["deck"],
                                  CLASS["portal"]]) & ((obj < 1) | (obj > ne))) |
                   ((cls == CLASS["tree"]) & (obj >= nt)))
        id_bad += int(bad_ids.sum())
        if bad_ids.any() and len(id_ex) < 8:
            id_ex.append({"tile": name, "ids": [int(x) for x in ids[bad_ids][:3]]})
        seen_b.update(obj[np.isin(cls, [CLASS["building"], CLASS["window"], CLASS["door"], CLASS["shopfront"]])].tolist())
    rep.at_most("L1.1", "ground pixels of the area without a class (of %d)" % area_px, missing_cls, 0, miss_ex)
    worst, wex = 0.0, []
    for k, (sn, nn_, ss, ns) in sorted(slope_lum.items()):
        if nn_ < 2000 or ns < 2000:
            continue
        d = abs(sn / nn_ - ss / ns) / max(ss / ns, 1e-9)
        wex.append({"class": GROUND_CLASSES[k], "north": round(sn / nn_, 2), "south": round(ss / ns, 2), "diff": round(d, 4)})
        worst = max(worst, d)
    rep.at_most("L1.2", "no shading: worst relative luminance difference of a ground class, north vs south slopes",
                round(worst, 4), P["ground_slope_lum_max"], sorted(wex, key=lambda e: -e["diff"]))
    rep.at_most("L2.1", f"flat ground changed by the relief (of {flat_n} flat pixels)", flat_bad, 0, flat_ex)
    rep.at_most("L8.1", f"pixels where a layer's depth differs from layer 8's by > {P['align_cm']} cm (of {align_n})", align_bad, 0, align_ex)
    rep.at_most("L8.2", f"normals not unit or facing away from the camera (of {nrm_n})", nrm_bad, 0)
    rep.at_most("L8.3", "ids not in the scene", id_bad, 0, id_ex)
    rep.info("L8.3b", "buildings with at least one pixel in layer 8", f"{len(seen_b)} of {nb}")
    # ------------------------------------------------------------------ L2.2 walls
    _l22(rep, R, rel, P)
    # ------------------------------------------------------------------ L3.1 water
    _l31(rep, R, rel, P)
    # ------------------------------------------------------------------ L4.1, L4.3
    _l41(rep, R, rel, P)
    # ------------------------------------------------------------------ P-1 palette
    _palette(rep)
    return rep.result()


def _l22(rep, R, rel, P):
    relief = TileCache(rel, "relief")
    sc = R.scene
    bad, total, ex = 0, 0, []
    for wi, w in enumerate(sc.walls):
        if (w.get("drop_m") or 0) < P["wall_min_drop_m"]:
            continue
        en = np.array(w["en"], float)
        seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
        if seg[-1] < 1:
            continue
        s = np.arange(0.25, seg[-1], 0.5)
        e, n = np.interp(s, seg, en[:, 0]), np.interp(s, seg, en[:, 1])
        inside = shapely.contains_xy(sc.polygon, e, n)
        if inside.sum() < 4:
            continue
        e, n = e[inside], n[inside]
        top = np.array([np.nan if v is None else v for v in w["top_m"]], float)
        L = seg[-1]
        st = np.minimum(np.arange(len(top)) * 5.0 * L / max(int(L), 1), L)
        ok = np.isfinite(top)
        if ok.sum() < 2:
            continue
        from scipy.ndimage import median_filter, uniform_filter1d
        sd = np.r_[np.arange(0, L, 0.5), L]
        td = np.interp(sd, st, np.where(ok, top, np.nanmedian(top)))
        if len(top) >= 3:
            td = uniform_filter1d(median_filter(td, 11, mode="nearest"), 11, mode="nearest")
        z = np.interp(s[inside], sd, td)
        g = R.hf.sample(e, n)
        z = np.where(np.isfinite(g), np.maximum(z, g), z)            # as drawn: never under the terrain at the line
        px, py, d = project(e, n, z)
        drawn = np.zeros(len(e), bool)
        seen = np.zeros(len(e), bool)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                ks = relief.lookup(px + dx, py + dy, "k")
                ds = relief.lookup(px + dx, py + dy, "depth")
                for i in range(len(e)):
                    if ks[i] is None:
                        continue
                    if ks[i] == 3:
                        drawn[i] = True
                    if dx == 0 and dy == 0 and ds[i] is not None and ds[i] > d[i] - 1.0:
                        seen[i] = True          # its own pixel shows nothing nearer than the wall's top
        vis = seen | drawn
        if vis.sum() < 4:
            continue
        share = float((drawn & vis).sum() / vis.sum())
        total += 1
        if share < P["wall_drawn_share"]:
            bad += 1
            if len(ex) < 8:
                ex.append({"wall": w["osm"], "kind": w["kind"], "drawn_share": round(share, 3), "visible_samples": int(vis.sum())})
    rep.at_most(f"L2.2", f"walls (drop >= {P['wall_min_drop_m']} m, in the area, in view) drawn along < "
                f"{P['wall_drawn_share']:.0%} of their visible length (of {total})", bad, 0, ex)


def _l31(rep, R, rel, P):
    water = release_tiles(rel, "water")
    tol = P["water_px_tol"] * 0.125 * 2.5          # 1 px of screen is up to ~0.3 m of plan on the ground
    polys = R.water_polys
    if not polys:
        rep.info("L3.1", "water areas", 0)
        return
    from shapely.ops import unary_union
    W = unary_union(polys).intersection(R.scene.polygon)
    inner, outer = W.buffer(-tol), W.buffer(tol)
    bad_in, bad_out, n = 0, 0, 0
    names = set(water) | {nm for nm in release_tiles(rel, "buffers")}
    for name in sorted(names):
        tx, ty = (int(v) for v in name.split("_"))
        t = R.terrain(Tile(tx, ty, apron=0))
        m = t["inarea"]
        if not m.any():
            continue
        e, nn = t["e"][m], t["n"][m]
        must = shapely.contains_xy(inner, e, nn)
        may = shapely.contains_xy(outer, e, nn)
        if not may.any():
            continue
        wt = load(rel, "water", name)
        isw = np.zeros(m.shape, bool) if wt is None else (wt["k"] > 0) & np.isfinite(wt["depth"])
        isw = isw[m]
        bad_in += int((must & ~isw).sum())
        bad_out += int((isw & ~may).sum())
        n += int(must.sum())
    rep.at_most("L3.1", f"OSM water pixels not drawn as water, and water pixels outside OSM water (+- {P['water_px_tol']} px; "
                f"{n} water pixels)", bad_in + bad_out, 0, [{"missing": bad_in, "outside": bad_out}])


def _l41(rep, R, rel, P):
    sc = R.scene
    tr = TileCache(rel, "transport")
    gr = TileCache(rel, "ground")
    step = P["centreline_step_m"]
    n_in, n_hidden, bad, ex, n_edge = 0, 0, 0, [], 0
    tunnel_px = 0
    for i, e in enumerate(sc.graph["edges"]):
        if e["mode"] not in ("road", "rail", "tram") or e["structure"] in ("tunnel", "indoor"):
            continue
        en = np.array(e["en"], float)
        s0 = np.array(e["s"], float)
        z0 = np.array(e["z"], float)
        if len(en) < 2 or s0[-1] < step:
            continue
        s = np.arange(step / 2, s0[-1], step)
        ee, nn = np.interp(s, s0, en[:, 0]), np.interp(s, s0, en[:, 1])
        ok = shapely.contains_xy(sc.polygon.buffer(-0.5), ee, nn)
        if not ok.any():
            continue
        ee, nn, s = ee[ok], nn[ok], s[ok]
        # ground ways are drawn on the terrain, decks at their profile
        from v2.layers.geometry import on_deck
        deck = on_deck(e)
        z = np.interp(s, s0, z0) if deck else R.hf.sample(ee, nn)
        px, py, d = project(ee, nn, z)
        tdep = tr.lookup(px, py, "depth")
        near = [tr.lookup(px + dx, py + dy, "depth") for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        tx_, ty_ = (px // TILE).astype(int), (py // TILE).astype(int)
        gdep = np.full(len(px), np.inf)
        for key in set(zip(tx_.tolist(), ty_.tolist())):
            mm = (tx_ == key[0]) & (ty_ == key[1])
            T = R.terrain(Tile(key[0], key[1], apron=0))          # the terrain seen (also outside the area)
            gdep[mm] = T["depth"][(py[mm] - key[1] * TILE).astype(int), (px[mm] - key[0] * TILE).astype(int)]
        for k in range(len(ee)):
            drawn = tdep[k] is not None and np.isfinite(tdep[k])
            if not drawn and any(v[k] is not None and np.isfinite(v[k]) and abs(v[k] - d[k]) < 2.0 for v in near):
                n_edge += 1                       # on the surface's edge: the pixel next to it is drawn
                drawn = True
            if not drawn:
                # a drape is drawn where its terrain is seen: behind a hill it is not in view at all
                g = gdep[k]
                if not deck and np.isfinite(g) and g < d[k] - 0.5:
                    n_hidden += 1
                    continue
                if deck and tdep[k] is not None and np.isfinite(tdep[k]) and tdep[k] < d[k] - 0.5:
                    n_hidden += 1
                    continue
            n_in += 1
            if not drawn:
                bad += 1
                if len(ex) < 8:
                    ex.append({"edge": e["id"], "mode": e["mode"], "e": round(float(ee[k]), 2), "n": round(float(nn[k]), 2)})
    rep.at_least("L4.1", f"road, rail and tram centre-line samples (every {step} m) inside the drawn surface "
                 f"(of {n_in}; {n_hidden} behind the terrain; {n_edge} within 1 px of the surface's edge)", round(1 - bad / max(n_in, 1), 6), P["centreline_share"], ex)
    tun = {i for i, e in enumerate(sc.graph["edges"]) if e["structure"] == "tunnel"}
    for name in release_tiles(rel, "transport"):
        t = load(rel, "transport", name)
        ids = t["ids"]
        cls = ids & 255
        obj = (ids >> 8).astype(np.int64) - 1
        m = (cls != CLASS["portal"]) & (obj >= 0)
        if m.any():
            tunnel_px += int(np.isin(obj[m], list(tun)).sum())
    rep.at_most("L4.3", "drawn pixels of tunnel ways (portals are drawn, tunnels are not)", tunnel_px, 0)


RGB_LITERAL = re.compile(r"\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)")


def _palette(rep):
    bad = []
    for p in sorted((V2 / "layers").glob("*.py")):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            code = line.split("#")[0]
            for m in RGB_LITERAL.finditer(code):
                v = [int(x) for x in m.groups()]
                if max(v) > 1:
                    bad.append(f"{p.name}:{i}: {m.group(0)}")
    rep.at_most("P-1", "colour literals in the layer code (every colour comes from palette.json)", len(bad), 0, bad)
