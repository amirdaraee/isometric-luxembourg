"""Gate G1's brief checks (PLAN_V2 section 8) on the built release of an area.

check_independence  brief 4  every colour layer re-rendered with each other layer's own inputs removed is identical,
                             and the built tiles are the renderer's output (C1, L*.3)
check_shadows       brief 5  no baked shadows: the shadow detector on the colour layers (L5.1, L9.2, L1.2 is in
                             check_layers); cast shadows follow the sun (L9.1); the relief ignores the sun (L2.3)
check_seams                  no tone or edge step at tile borders (v1's seam check, as a gate; L*.4, T3), depth too
check_vehicles      briefs 7, 8  vehicles on drawn road >= 99.5% over a simulated day (L4.2, L12.4); none drawn in a
                             tunnel past its portal (L12.1); per-pixel depth test at every portal and bridge (C4,
                             L6.2); smooth heights, no jump > 0.5 m between frames (L12.2); no fade guard needed (L12.3)
check_no_cars       brief 9  the vehicle detector (v1's OWLv2) finds no car in any colour layer (L1.5 ...)
check_viewer                 the viewer itself: layers off leave no trace, shadows move with ?hour and match the
                             reference, no light by day, seasons touch only their masks, labels never overlap, speed
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import shapely
from scipy import ndimage

from v2.checks.framework import Report
from v2.checks.layer_checks import TileCache, load, release_tiles
from v2.config import REPO
from v2.layers.common import (CLASS, COLOUR_LAYERS, TILE, Scene, Tile, VIEW, lum, project, unproject)
from v2.layers.light import LIGHT, HeightMap, build_heightmap, shadow_ref, sun_vector
from v2.layers.render import Renderer

WEB = REPO / "v2" / "web"


def _renderer(ctx, omit=()):
    sc = Scene(ctx.dep("scene"))
    return Renderer(sc, ctx.dep("fetch_osm_ground") / "ground.json", ctx.dep("fetch_osm_transport") / "transport.json",
                    frozenset(omit))


def sample_tiles(rel, n):
    """Tiles holding the most layers, spread over the area (deterministic)."""
    names = sorted(release_tiles(rel, "buffers"))
    score = []
    for name in names:
        b = load(rel, "buffers", name)
        score.append((len(np.unique(b["k"][b["k"] > 0])), int(np.isfinite(b["depth"]).sum()), name))
    score.sort(reverse=True)
    rich = [s[2] for s in score[: max(n * 3, n)]]
    return [rich[int(i)] for i in np.linspace(0, len(rich) - 1, n)]


# ------------------------------------------------------------------------------------------------ brief 4
def check_independence(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    rep = Report("independence")
    tiles = [Tile(*(int(v) for v in n.split("_"))) for n in sample_tiles(rel, P["independence_tiles"])]
    full = _renderer(ctx)
    ref = {(L, t): full.layer(L, t) for L in COLOUR_LAYERS for t in tiles}
    bad, compared, ex = 0, 0, []
    for X in COLOUR_LAYERS:
        R = _renderer(ctx, omit=(X,))
        for L in COLOUR_LAYERS:
            if L == X:
                continue
            for t in tiles:
                a, b = ref[(L, t)], R.layer(L, t)
                compared += 1
                same = (np.array_equal(a.rgb, b.rgb) and np.array_equal(a.depth, b.depth)
                        and np.array_equal(a.normal, b.normal) and np.array_equal(a.k, b.k) and np.array_equal(a.ids, b.ids))
                if not same:
                    bad += 1
                    if len(ex) < 8:
                        ex.append({"layer": L, "without": X, "tile": t.name,
                                   "pixels": int((np.abs(a.rgb.astype(int) - b.rgb).sum(-1) > 0).sum())})
    rep.at_most("C1a", f"layer tiles that change when another layer's inputs are removed ({compared} renders, "
                f"{len(tiles)} tiles x 7 layers x 6 others)", bad, 0, ex)
    # the built tiles are exactly the renderer's output (depth and normals exactly, colour within the lossy coding)
    gbad, cmax, ex2 = 0, 0.0, []
    for L in COLOUR_LAYERS:
        for t in tiles:
            built = load(rel, L, t.name)
            r = ref[(L, t)]
            crop = Tile(t.tx, t.ty).crop
            d = crop(r.depth)
            if built is None:
                if np.isfinite(d).any():
                    gbad += 1
                continue
            ok = np.isfinite(d)
            if not np.array_equal(ok, np.isfinite(built["depth"])) or np.abs(built["depth"][ok] - d[ok]).max(initial=0) > 0.0051:
                gbad += 1
                if len(ex2) < 8:
                    ex2.append({"layer": L, "tile": t.name})
            if ok.any():
                cmax = max(cmax, float(np.abs(built["rgb"][ok].astype(float) - crop(r.rgb)[ok]).mean()))
    rep.at_most("C1b", "built tiles whose geometry differs from the renderer's", gbad, 0, ex2)
    rep.at_most("C1c", "mean colour difference of a built tile from the renderer (lossy WebP q90 coding)", round(cmax, 2), 3.0)
    rep.info("C1d", "layer off in the viewer: no pixel of it, no shadow of it (check_viewer V1, V2)", "see check_viewer")
    return rep.result()


# ------------------------------------------------------------------------------------------------ brief 5
def _when(s):
    return dt.datetime.fromisoformat(s)


def check_shadows(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    rep = Report("shadows")
    R = _renderer(ctx)
    hm = build_heightmap(R)
    # the viewer's shadow height map is this one
    A, B = hm.encode()
    from v2.layers.common import unpack_bin
    li = json.loads((rel / "light.json").read_text())
    A2 = unpack_bin((rel / "shadow_a.bin").read_bytes(), (li["height"], li["width"], 4), np.uint8)
    B2 = unpack_bin((rel / "shadow_b.bin").read_bytes(), (li["height"], li["width"], 4), np.uint8)
    rep.add("L9.0", "the released shadow height map is the scene's", np.array_equal(A, A2) and np.array_equal(B, B2))
    # ------------------------------------------------------------ the shadow detector (photo sun), layers 1 and 3-7
    az, el, sv = sun_vector(_when(P["shadow_photo_sun"]))
    names = sorted(release_tiles(rel, "buffers"))[::3]
    stats = {}
    for name in names:
        tx, ty = (int(v) for v in name.split("_"))
        px = tx * TILE + np.arange(TILE) + 0.5
        py = ty * TILE + np.arange(TILE) + 0.5
        PX, PY = np.meshgrid(px, py)
        for L in ("ground", "water", "transport", "buildings", "structures", "trees"):
            t = load(rel, L, name)
            if t is None:
                continue
            ok = np.isfinite(t["depth"])
            if ok.sum() < 100:
                continue
            e, n, z = unproject(PX[ok], PY[ok], t["depth"][ok])
            cast = shadow_ref(hm, e, n, z, az, el)
            nrm = t["normal"][ok]
            away = (nrm @ sv) < 0
            sh = np.zeros(ok.shape, bool)
            sh[ok] = (cast > 0) | away
            near = ndimage.binary_dilation(sh, iterations=24) & ~sh & ok
            Lm = lum(t["rgb"])
            # surface edges carry the drawing's ink lines (and the coding's ringing): only the inside of a surface is
            # its material's colour, so pixels within 2 px of a change of object, class, surface or depth are left out
            idk = t["ids"].astype(np.int64) if "ids" in t else t["k"].astype(np.int64)
            dd = np.where(ok, t["depth"], 1e9)
            nz = np.round(t["normal"] * 20)
            edge = np.zeros(ok.shape, bool)
            for a_, b_ in (((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                           ((slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
                ch = (idk[a_] != idk[b_]) | (np.abs(dd[a_] - dd[b_]) > 0.5) | (nz[a_] != nz[b_]).any(-1) | (ok[a_] != ok[b_])
                edge[a_] |= ch
                edge[b_] |= ch
            inner = ok & ~ndimage.binary_dilation(edge, iterations=2)
            # a material: the ground class; or one object and its class (a building's walls, roofs, windows apart)
            if L == "ground":
                key = t["k"].astype(np.int64)
            elif L == "water":
                key = np.zeros(ok.shape, np.int64)
            else:
                ids = t["ids"].astype(np.int64)
                key = (ids >> 8) * 512 + (ids & 255) * 2
                if L == "buildings":
                    key += (np.abs(t["normal"][..., 2]) > 0.5).astype(np.int64)
            for which, m in (("sh", sh & inner), ("lit", near & inner)):
                kk = key[m]
                vv = Lm[m]
                if not len(kk):
                    continue
                o = np.argsort(kk, kind="stable")
                kk, vv = kk[o], vv[o]
                cut = np.flatnonzero(np.diff(kk)) + 1
                for k, part in zip(kk[np.r_[0, cut]], np.split(vv, cut)):
                    d = stats.setdefault((L, int(k)), {"sh": [], "lit": []})
                    d[which].append(part)
    worst, bad, ex, by_layer = 0.0, 0, [], {}
    for (L, k), d in stats.items():
        a = np.concatenate(d["sh"]) if d["sh"] else np.zeros(0)
        b = np.concatenate(d["lit"]) if d["lit"] else np.zeros(0)
        if len(a) < 50 or len(b) < 50:
            continue
        # the median: the material's own colour (its ink lines, markings and grain are a minority of its pixels)
        r = float(np.median(a)) / max(float(np.median(b)), 1e-9)
        dev = abs(r - 1)
        bl = by_layer.setdefault(L, [0, 0.0])
        bl[0] += 1; bl[1] = max(bl[1], dev)
        worst = max(worst, dev)
        if dev > P["shadow_lum_tol"]:
            bad += 1
            if len(ex) < 8:
                ex.append({"layer": L, "material": k, "shadow_over_lit": round(r, 4), "pixels": [len(a), len(b)]})
    rep.at_most("L5.1/L9.2", f"materials darker or lighter in the 3D shadow of the photo's sun ({P['shadow_photo_sun']}) "
                f"than lit next to it by > {P['shadow_lum_tol']:.0%} (median luminance inside surfaces; of {sum(v[0] for v in by_layer.values())} compared)",
                bad, 0, ex)
    rep.info("L5.1b", "worst relative difference by layer", {k: round(v[1], 4) for k, v in by_layer.items()})
    # ------------------------------------------------------------ L9.1: cast shadows point away from the sun
    sc = R.scene
    B_ = sc.buildings
    cen = np.array([b["centre"] for b in B_], float)
    hb = np.array([float(b["height"]) for b in B_], float)
    step = 1.0
    x0, y0, x1, y1 = sc.polygon.bounds
    E, N = np.meshgrid(np.arange(x0, x1, step) + step / 2, np.arange(y0, y1, step) + step / 2)
    E, N = E.ravel(), N.ravel()
    ins = shapely.contains_xy(sc.polygon, E, N)
    E, N = E[ins], N[ins]
    ci = np.clip(((N - hm.n0) / hm.step).astype(int), 0, hm.shape[0] - 1)
    cj = np.clip(((E - hm.e0) / hm.step).astype(int), 0, hm.shape[1] - 1)
    own = hm.b_id[ci, cj]                                   # the building under the cell (-1: none)
    Z = hm.terrain[ci, cj] + hm.b_top[ci, cj] + 0.01        # the top surface: the ground, or a roof
    ok = np.isfinite(Z)
    E, N, Z, own = E[ok], N[ok], Z[ok], own[ok]
    day = dt.date.fromisoformat(P["shadow_dir_date"])
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Luxembourg")
    for hour in P["shadow_dir_hours"]:
        t = dt.datetime(day.year, day.month, day.day, hour, tzinfo=tz)
        az, el, _ = sun_vector(t)
        sh, who = shadow_ref(hm, E, N, Z, az, el, sources=("buildings",), who=True)
        errs = []
        m = (who >= 0) & (who != own)                       # the shadow a building casts, not on itself
        if m.any():
            u, inv = np.unique(who[m], return_inverse=True)
            cnt = np.bincount(inv)
            se = np.bincount(inv, weights=E[m]); sn = np.bincount(inv, weights=N[m])
            for b, c_, a_, b_ in zip(u, cnt, se, sn):
                if c_ < P["shadow_dir_min_cells"]:
                    continue
                dx, dy = a_ / c_ - cen[b, 0], b_ / c_ - cen[b, 1]
                if math.hypot(dx, dy) < 1.0:
                    continue
                ang = math.degrees(math.atan2(dx, dy)) % 360
                want = (az + 180) % 360
                errs.append(abs((ang - want + 180) % 360 - 180))
        med = float(np.median(errs)) if errs else 999.0
        rep.at_most(f"L9.1-{hour:02d}", f"shadow direction vs the sun at {hour:02d}:00 on {day} (az {az:.1f}, el {el:.1f}): "
                    f"median angle error over {len(errs)} buildings (deg; 90th pct {np.percentile(errs, 90) if errs else 0:.1f})",
                    round(med, 2), P["shadow_dir_deg"])
        del sh
    # ------------------------------------------------------------ L2.3: the relief is not light
    import v2.config.sun as sunmod
    keep = sunmod.position
    tiles = [Tile(*(int(v) for v in n.split("_"))) for n in sample_tiles(rel, 3)]
    outs = []
    for fake in ((100.0, 8.0), (280.0, 6.0)):
        sunmod.position = lambda t, *a, _f=fake: _f
        R2 = _renderer(ctx)
        outs.append([R2.layer("relief", t).rgb for t in tiles])
    sunmod.position = keep
    rep.add("L2.3", "the relief layer is identical for a morning and an evening sun", all(np.array_equal(a, b) for a, b in zip(*outs)))
    return rep.result()


# ------------------------------------------------------------------------------------------------ seams
def _lab(rgb):
    c = np.asarray(rgb, float) / 255
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _jumps(lab, valid, pos, axis, CH=64, NEAR=0, FAR=4):
    """Per 64-px chunk, the LAB difference of the strips either side of a line (v1's seam_check)."""
    out = []
    n = lab.shape[0] if axis == 1 else lab.shape[1]
    for a in range(0, n - CH + 1, CH):
        if axis == 1:
            A, B = lab[a:a + CH, pos - FAR:pos - NEAR], lab[a:a + CH, pos + NEAR:pos + FAR]
            va, vb = valid[a:a + CH, pos - FAR:pos - NEAR], valid[a:a + CH, pos + NEAR:pos + FAR]
        else:
            A, B = lab[pos - FAR:pos - NEAR, a:a + CH], lab[pos + NEAR:pos + FAR, a:a + CH]
            va, vb = valid[pos - FAR:pos - NEAR, a:a + CH], valid[pos + NEAR:pos + FAR, a:a + CH]
        if va.mean() < 0.9 or vb.mean() < 0.9:
            out.append((a, 0.0, True, np.zeros(3)))
            continue
        vec = A[va].mean(0) - B[vb].mean(0)
        out.append((a, float(np.linalg.norm(vec)), False, vec))
    return out


def seams_of(get, names, P, at=TILE):
    """v1's rule: a border chunk is a seam when its jump is clearly larger than the jumps on parallel lines inside
    the tiles (or simply large), over a run of >= 3 chunks whose colour shift points the same way. v1 compared
    56 px strips 80 and 160 px away, for painted cells blended over 24 px; code tiles have no blend, so the strips
    here are the 4 px either side of a line and the parallel lines 8 and 16 px inside each tile (the same rule at
    the tiles' own scale: a content edge crossing the border changes the lines next to it as much)."""
    bad, total, ex = 0, 0, []
    have = set(names)
    for name in sorted(names):
        tx, ty = (int(v) for v in name.split("_"))
        for dx, dy, axis in ((1, 0, 1), (0, 1, 0)):
            other = f"{tx + dx}_{ty + dy}"
            if other not in have:
                continue
            a, b = get(name), get(other)
            if a is None or b is None:
                continue
            rgb = np.concatenate([a[0], b[0]], axis=1 if axis == 1 else 0)
            val = np.concatenate([a[1], b[1]], axis=1 if axis == 1 else 0)
            lab = _lab(rgb)
            line = _jumps(lab, val, at, axis)
            side = [_jumps(lab, val, at + o, axis) for o in (-16, -8, 8, 16)]
            hit = []
            for k, (pos, d, skip, vec) in enumerate(line):
                local = float(np.median([s[k][1] for s in side]))
                hit.append(not skip and d > max(P["seam_de_max"], 1.5 * local))
                # (v1 also flagged any jump over its global threshold; with 4 px strips that is every content edge)
                total += 0 if skip else 1
            k = 0
            while k < len(line):
                if not hit[k]:
                    k += 1
                    continue
                j = k
                while j + 1 < len(line) and hit[j + 1]:
                    v0, v1 = line[j][3], line[j + 1][3]
                    if float(v0 @ v1) / (np.linalg.norm(v0) * np.linalg.norm(v1) + 1e-6) < 0.6:
                        break
                    j += 1
                if j - k + 1 >= P["seam_run"]:
                    bad += j - k + 1
                    if len(ex) < 8:
                        ex.append({"tiles": [name, other], "chunk": line[k][0], "dE": round(line[k][1], 2)})
                k = j + 1
    return bad, total, ex


def check_seams(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    rep = Report("seams")
    for L in COLOUR_LAYERS:
        names = release_tiles(rel, L)

        def get(n, L=L):
            t = load(rel, L, n)
            return None if t is None else (t["rgb"], np.isfinite(t["depth"]))
        bad, total, ex = seams_of(get, names, P)
        # the control (v1's seam_check run on cell centres): the same rule on lines through the tiles' middles,
        # where no seam can be: a building corner or a class edge running along a line for 192 px is content
        c1, t1, _ = seams_of(get, names, P, at=TILE // 2)
        c2, t2, _ = seams_of(get, names, P, at=TILE + TILE // 2)
        ctrl = (c1 + c2) / 2
        rep.add(f"S-{L}", f"{L}: seam chunks at tile borders vs the same rule through the tiles' middles ({bad} of "
                f"{total} chunks of 64 px at borders, {ctrl:.1f} at the middles; a seam adds to the borders)",
                bad <= 1.5 * ctrl + P["seam_run"], {"borders": bad, "middles": ctrl},
                f"<= 1.5 x middles + {P['seam_run']}", ex)
    # depth continuity across tile borders where the same surface goes on (L8.4)
    names = release_tiles(rel, "buffers")
    jumps, n, ctrl_j, ctrl_n = 0, 0, 0, 0
    for name in names:
        tx, ty = (int(v) for v in name.split("_"))
        a = load(rel, "buffers", name)
        for dx, dy in ((1, 0), (0, 1)):
            o = f"{tx + dx}_{ty + dy}"
            if o not in names:
                continue
            b = load(rel, "buffers", o)
            if dx:
                da, db, ia, ib_ = a["depth"][:, -1], b["depth"][:, 0], a["ids"][:, -1], b["ids"][:, 0]
                da2 = a["depth"][:, -2]
            else:
                da, db, ia, ib_ = a["depth"][-1, :], b["depth"][0, :], a["ids"][-1, :], b["ids"][0, :]
                da2 = a["depth"][-2, :]
            same = (ia == ib_) & np.isfinite(da) & np.isfinite(db) & np.isfinite(da2)
            # the step across the border against the step one pixel before it
            step = np.abs(db - da)[same]
            prev = np.abs(da - da2)[same]
            n += int(same.sum())
            jumps += int((step > 3 * prev + 0.05).sum())
            # the same measure across the tile's middle line (no border there): the natural rate of such steps
            d = a["depth"]
            if dx:
                ca, cb, c2, ia2, ib2 = d[:, 255], d[:, 256], d[:, 254], a["ids"][:, 255], a["ids"][:, 256]
            else:
                ca, cb, c2, ia2, ib2 = d[255, :], d[256, :], d[254, :], a["ids"][255, :], a["ids"][256, :]
            s2 = (ia2 == ib2) & np.isfinite(ca) & np.isfinite(cb) & np.isfinite(c2)
            ctrl_n += int(s2.sum())
            ctrl_j += int((np.abs(cb - ca)[s2] > 3 * np.abs(ca - c2)[s2] + 0.05).sum())
    rate, ctrl = jumps / max(n, 1), ctrl_j / max(ctrl_n, 1)
    rep.at_most("L8.4", f"depth: share of border pixels with a step on one surface, over the share across the tiles' "
                f"middle lines ({jumps} of {n} vs {ctrl_j} of {ctrl_n}; a seam would make it larger)",
                round(rate / max(ctrl, 1e-9), 3) if ctrl > 0 else (0.0 if jumps == 0 else 99.0), 1.5)
    return rep.result()


# ------------------------------------------------------------------------------------------------ briefs 7 and 8
KIND_CAR = (0, 1, 2, 3, 4, 5)


def _run_audit(rel: Path, out: Path, sample_s) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["node", "--experimental-strip-types", "--no-warnings", str(WEB / "scripts" / "audit.ts"), str(rel), str(out), str(sample_s)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=WEB)
    if r.returncode:
        raise RuntimeError("audit failed: " + r.stderr[-2000:])
    return json.loads((out / "jumps.json").read_text())


def box_tris(x, y, z, h, L, W, H):
    """A vehicle box (ground centre x, y, z; heading h from east) as 12 triangles of world points."""
    c, s = math.cos(h), math.sin(h)
    pts = []
    for dz in (0, H):
        for a, b in ((L / 2, W / 2), (-L / 2, W / 2), (-L / 2, -W / 2), (L / 2, -W / 2)):
            pts.append((x + a * c - b * s, y + a * s + b * c, z + dz))
    V = np.array(pts)
    T = np.array([[4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
                  [0, 2, 1], [0, 3, 2]])
    return V, T


def box_pixels(V, T):
    """Zoom-0 pixels covered by a box and the box's depth there: (px ints, py ints, depth)."""
    from v2.layers.raster import raster_tris
    px, py, d = project(V[:, 0], V[:, 1], V[:, 2])
    x0, y0 = int(math.floor(px.min())) - 1, int(math.floor(py.min())) - 1
    W, H = int(math.ceil(px.max())) - x0 + 2, int(math.ceil(py.max())) - y0 + 2
    zb = np.full((H, W), np.inf)
    tb = np.full((H, W), -1, np.int64)
    raster_tris(np.column_stack([px - x0, py - y0]), d, T, W, H, zb, tb)
    r, c = np.nonzero(np.isfinite(zb))
    return c + x0, r + y0, zb[r, c]


def check_vehicles(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    rep = Report("vehicles")
    sc = Scene(ctx.dep("scene"))
    R = Renderer(sc)
    eps = float(LIGHT["vehicles"]["depth_eps_m"])
    t0 = time.time()
    J = _run_audit(rel, ctx.out / "audit", P["sim_day_sample_s"])
    rows = np.frombuffer((ctx.out / "audit" / "samples.bin").read_bytes(), np.float32).reshape(-1, 10).astype(float)
    shutil.rmtree(ctx.out / "audit", ignore_errors=True) if False else None
    from v2.config.camera import camera
    oe, on = camera()["origin_en"]
    X, Y, Z, Hd, L, W, Hh, EDGE, KIND, SEC = rows.T
    E, N = X + oe, Y + on
    EDGE = EDGE.astype(int)
    edges = sc.graph["edges"]
    st = np.array([edges[i]["structure"] for i in EDGE])
    tunnel = st == "tunnel"
    deck = st == "bridge"
    inarea = shapely.contains_xy(sc.polygon, E, N)
    car = np.isin(KIND, KIND_CAR)
    rep.info("V0", "audit: samples over a simulated day", {"car_samples": int(car.sum()), "transit_samples": int((~car).sum()),
                                                            "every_s": P["sim_day_sample_s"], "audit_s": round(J["seconds"], 1)})
    # ------------------------------------------------------------ L4.2, L12.4 on drawn road / track
    tr = TileCache(rel, "transport", maxn=400)
    from v2.layers.geometry import on_deck
    deck = np.array([on_deck(edges[i]) for i in EDGE])
    zdraw = np.where(deck, Z, R.hf.sample(E, N))                  # ground ways are drawn on the terrain
    px, py, dd = project(E, N, zdraw)
    # a way behind a hill is not in view: its vehicles are hidden there, not off the road (as L4.1)
    seen = np.ones(len(E), bool)
    txs, tys = (px // TILE).astype(int), (py // TILE).astype(int)
    for key in set(zip(txs[inarea].tolist(), tys[inarea].tolist())):
        m = inarea & (txs == key[0]) & (tys == key[1])
        T = R.terrain(Tile(key[0], key[1], apron=0))
        td = T["depth"][(py[m] - key[1] * TILE).astype(int), (px[m] - key[0] * TILE).astype(int)]
        seen[m] = deck[m] | ~(td < dd[m] - 0.5)
    rep.info("V0b", "vehicle samples in the area behind the terrain (not in view)", int((inarea & ~tunnel & ~seen).sum()))
    sel = inarea & ~tunnel & seen
    # under a deck (another way's surface is nearer there): hidden, as in a tunnel (C4 tests that per pixel)
    tdep = np.array([np.inf if v is None else v for v in tr.lookup(px[sel], py[sel], "depth")])
    under = tdep < dd[sel] - 0.5
    rep.info("V0c", "vehicle samples under another way's deck (not in view)", int(under.sum()))
    sel[np.flatnonzero(sel)[under]] = False
    ids = np.array([0 if v is None else int(v) for v in tr.lookup(px[sel], py[sel], "ids")], np.int64)
    cls = ids & 255
    road_cls = [CLASS["road"], CLASS["deck"], CLASS["tram"], CLASS["path"]]
    track_cls = [CLASS["rail"], CLASS["tram"], CLASS["deck"]]
    c_on = np.isin(cls, road_cls)
    t_on = np.isin(cls, track_cls)
    cs = car[sel]
    car_share = float(c_on[cs].mean()) if cs.any() else 1.0
    tr_share = float(t_on[~cs].mean()) if (~cs).any() else 1.0
    off_ex = [{"e": round(float(e), 1), "n": round(float(n), 1), "edge": edges[i]["id"]} for e, n, i in
              zip(E[sel][cs & ~c_on][:8], N[sel][cs & ~c_on][:8], EDGE[sel][cs & ~c_on][:8])]
    rep.at_least("L4.2", f"car samples on drawn road (of {int(cs.sum())} in the area, out of tunnels)", round(car_share, 5),
                 P["vehicles_on_road_share"], off_ex)
    rep.at_least("L12.4", f"tram and train samples on drawn track (of {int((~cs).sum())})", round(tr_share, 5),
                 P["transit_on_track_share"],
                 [{"e": round(float(e), 1), "n": round(float(n), 1)} for e, n in zip(E[sel][~cs & ~t_on][:8], N[sel][~cs & ~t_on][:8])])
    rep.at_most("L12.3", "share of car samples the v1 fade guard would act on (off the drawn road)", round(1 - car_share, 5),
                P["fade_guard_share"])
    # ------------------------------------------------------------ L12.1 none drawn inside a tunnel past its portal
    buf = TileCache(rel, "buffers", maxn=400)
    portal_d = {}
    for p in sc.graph["portals"]:
        if p.get("found"):
            portal_d[str(p["chain"])] = max(portal_d.get(str(p["chain"]), 0.0), float(p["dist_m"]))
    inside_px, n_in, ex = 0, 0, []
    for k in np.flatnonzero(tunnel & inarea):
        e = edges[EDGE[k]]
        td = e.get("tunnel_d")
        if not td:
            continue
        en = np.array(e["en"], float)
        # how far into the tunnel the vehicle's nearer end is
        j = int(np.argmin(np.hypot(en[:, 0] - E[k], en[:, 1] - N[k])))
        if float(td[j]) - L[k] / 2 < portal_d.get(str(e.get("chain")), 40.0):
            continue
        n_in += 1
        V, T = box_tris(E[k], N[k], Z[k], Hd[k], L[k], W[k], Hh[k])
        bx, by, bd = box_pixels(V, T)
        dep = np.array([np.inf if v is None else v for v in buf.lookup(bx + 0.5, by + 0.5, "depth")])
        shown = int((bd - eps <= dep).sum())
        if shown:
            inside_px += shown
            if len(ex) < 8:
                ex.append({"edge": e["id"], "e": round(float(E[k]), 1), "n": round(float(N[k]), 1), "pixels": shown})
    rep.at_most("L12.1a", f"vehicle pixels drawn inside tunnels past their portals ({n_in} samples in tunnels)", inside_px, 0, ex)
    # ------------------------------------------------------------ C4 / L6.2: probes at every portal and bridge
    _probes(rep, ctx, sc, rel, P, eps)
    # ------------------------------------------------------------ L12.2 smooth heights
    rep.at_most("L12.2a", f"largest height change of a car between two frames (m; {J['cars']['frames']} car-frames)",
                round(J["cars"]["max_m"], 3), P["vehicle_jump_m"], [J["cars"]["worst"]])
    rep.at_most("L12.2b", f"largest height change of a tram or train section between frames (m; {J['transit']['frames']})",
                round(J["transit"]["max_m"], 3), P["vehicle_jump_m"], [J["transit"]["worst"]])
    rep.info("V9", "seconds", round(time.time() - t0, 1))
    return rep.result()


def _probes(rep, ctx, sc, rel, P, eps):
    """Probe vehicles along every tunnel near its portals, on every bridge deck and on every way passing under a
    deck, in the area. Each probe pixel is drawn or hidden by the viewer's rule against layer 8's tiles; that must be
    exactly what the scene's geometry says, rendered at full precision for the same pixel (no tiles, no 16-bit
    depth). Pixels on a silhouette (a depth step within 1 px) are counted apart, as the rounding of an edge."""
    edges = sc.graph["edges"]
    step = P["probe_step_m"]
    probes = []   # (kind, edge, e, n, z, heading, L, W, H)
    size = {"road": (4.4, 1.8, 1.45), "rail": (26.8, 2.9, 4.6), "tram": (9.5, 2.65, 3.6), "funicular": (14.0, 2.6, 3.4)}
    nodes = {n["id"]: n for n in sc.graph["nodes"]}
    tunnels = [i for i, e in enumerate(edges) if e["structure"] == "tunnel" and e["mode"] in size]
    bridges = [i for i, e in enumerate(edges) if e["structure"] == "bridge" and e["mode"] in size]
    portal_nodes = {int(p["node"]) for p in sc.graph["portals"]}
    from shapely.geometry import LineString
    deck_polys = [(i, LineString(np.array(edges[i]["en"], float)).buffer(float(edges[i]["width"]) / 2)) for i in bridges]

    def along(i, s_from, s_to, kind):
        e = edges[i]
        en, s0, z0 = np.array(e["en"], float), np.array(e["s"], float), np.array(e["z"], float)
        for s in np.arange(max(s_from, 0), min(s_to, s0[-1]), step):
            x, y = np.interp(s, s0, en[:, 0]), np.interp(s, s0, en[:, 1])
            if not shapely.contains_xy(sc.polygon, x, y):
                continue
            a = np.interp(min(s + 1, s0[-1]), s0, en[:, 0]) - np.interp(max(s - 1, 0), s0, en[:, 0])
            b = np.interp(min(s + 1, s0[-1]), s0, en[:, 1]) - np.interp(max(s - 1, 0), s0, en[:, 1])
            probes.append((kind, i, x, y, float(np.interp(s, s0, z0)), math.atan2(b, a)) + size[e["mode"]])
    n_portals = 0
    for i in tunnels:
        e = edges[i]
        L = float(e["s"][-1])
        for end, s0 in (("a", 0.0), ("b", L)):
            if int(e[end]) in portal_nodes:
                n_portals += 1
                along(i, s0 - 60 if end == "b" else 0, 60 if end == "a" else L, "portal")
    for i in bridges:
        along(i, 0, 1e9, "deck")
    n_under = 0
    for i, e in enumerate(edges):
        if e["structure"] != "ground" or e["mode"] not in size:
            continue
        line = LineString(np.array(e["en"], float))
        for j, dp in deck_polys:
            if j == i or not line.intersects(dp):
                continue
            inter = line.intersection(dp)
            s_mid = line.project(inter.centroid)
            zdeck = float(np.median(edges[j]["z"]))
            zme = float(np.interp(s_mid, np.array(e["s"], float), np.array(e["z"], float)))
            if zdeck < zme + 2.0:
                continue
            n_under += 1
            along(i, s_mid - 20, s_mid + 20, "under")
    rep.info("C4a", "probed: tunnel portals, bridge edges, ways under a deck; probe vehicles",
             {"portals": n_portals, "bridges": len(bridges), "under_crossings": n_under, "probes": len(probes)})
    # exact geometry at the probes' tiles
    R = _renderer(ctx)
    buf = TileCache(rel, "buffers", maxn=400)
    exact = {}

    def exact_depth(tx, ty):
        if (tx, ty) not in exact:
            t = Tile(tx, ty, apron=0)
            d = np.full((TILE, TILE), np.inf)
            for L in COLOUR_LAYERS:
                lt = R.layer(L, t)
                dd = lt.depth if L != "relief" else np.where(lt.k == 3, lt.depth, np.inf)
                d = np.minimum(d, dd)
            exact.clear() if len(exact) > 64 else None
            exact[(tx, ty)] = d
        return exact[(tx, ty)]
    mism, sil, total, hidden_deck, hidden_tunnel, ex = 0, 0, 0, 0, 0, []
    for kind, i, x, y, z, h, L, W, H in probes:
        V, T = box_tris(x, y, z, h, L, W, H)
        bx, by, bd = box_pixels(V, T)
        dep = np.array([np.inf if v is None else v for v in buf.lookup(bx + 0.5, by + 0.5, "depth")])
        drawn = bd - eps <= dep
        ex_d = np.empty(len(bx))
        tx, ty = bx // TILE, by // TILE
        for k in set(zip(tx.tolist(), ty.tolist())):
            m = (tx == k[0]) & (ty == k[1])
            D = exact_depth(*k)
            ex_d[m] = D[by[m] - k[1] * TILE, bx[m] - k[0] * TILE]
        truth = bd - eps <= ex_d
        total += len(bx)
        diff = drawn != truth
        if diff.any():
            # silhouette: the exact depth jumps by > 1 m within 1 px there
            for q in np.flatnonzero(diff):
                k = (int(tx[q]), int(ty[q]))
                D = exact_depth(*k)
                r_, c_ = by[q] - k[1] * TILE, bx[q] - k[0] * TILE
                win = D[max(r_ - 1, 0):r_ + 2, max(c_ - 1, 0):c_ + 2]
                fin = win[np.isfinite(win)]
                on_edge = (not np.isfinite(win).all()) or (fin.max() - fin.min() > 1.0) or abs(bd[q] - eps - ex_d[q]) < 0.02
                if on_edge:
                    sil += 1
                else:
                    mism += 1
                    if len(ex) < 8:
                        ex.append({"kind": kind, "edge": edges[i]["id"], "e": round(x, 1), "n": round(y, 1)})
        if kind in ("under", "deck"):
            hidden_deck += int((~truth).sum())
        if kind == "portal":
            hidden_tunnel += int((~truth).sum())
    rep.at_most("C4", f"probe pixels where the viewer's depth test disagrees with the exact geometry (of {total}; "
                f"{sil} more on silhouettes, within 1 px of an edge)", mism, 0, ex)
    rep.at_most("C4b", "share of probe pixels on silhouettes (edge rounding)", round(sil / max(total, 1), 5), 0.01)
    rep.info("C4c", "probe pixels hidden (under decks or past portals)", {"deck_and_under": hidden_deck, "portals": hidden_tunnel})


# ------------------------------------------------------------------------------------------------ brief 9
def check_no_cars(ctx):
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    rep = Report("no_cars")
    jobs = []
    for L in COLOUR_LAYERS:
        for name in sorted(release_tiles(rel, L)):
            jobs.append({"layer": L, "path": str(rel / L / "0" / f"{name}.c.webp"), "tile": name})
    spec = {"jobs": jobs, "queries": P["detector_queries"], "queries_water": P["detector_queries_water"],
            "threshold": P["detector_score"], "box_m": P["detector_box_m"], "mpp": 0.125, "out": str(ctx.out / "owl.json")}
    (ctx.out / "owl_jobs.json").write_text(json.dumps(spec))
    script = REPO / "v2" / "checks" / "owl_detect.py"
    cmd = ["uv", "run", "--offline", "--no-project", "--with", "torch", "--with", "transformers", "--with", "pillow",
           "--with", "numpy", "python", "-I", str(script), str(ctx.out / "owl_jobs.json")]
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode:
        raise RuntimeError("detector failed: " + r.stderr[-3000:])
    res = json.loads((ctx.out / "owl.json").read_text())
    rep.info("D0", "detector", {"model": res["model"], "device": res["device"], "images": res["images"],
                                "seconds": round(res["seconds"], 1), "queries": P["detector_queries"]})
    for L in COLOUR_LAYERS:
        hits = [d for d in res["detections"] if d["layer"] == L]
        rep.at_most(f"D-{L}", f"{L}: detections >= {P['detector_score']} of a vehicle {P['detector_box_m'][0]}-"
                    f"{P['detector_box_m'][1]} m long", len(hits), 0, sorted(hits, key=lambda d: -d["score"]))
    rep.info("D9", "highest score of any query on any tile (below the threshold)", res["max_score"])
    return rep.result()


# ------------------------------------------------------------------------------------------------ the viewer
def look_grade(c):
    """Layer 14's grade, as the viewer's shader (LOOK_FS grade): a projection, so applying it twice changes nothing."""
    k = LIGHT["look"]
    c = np.clip(np.asarray(c, float), k["lum_min"], k["lum_max"])
    mx, mn = c.max(-1, keepdims=True), c.min(-1, keepdims=True)
    s = (mx - mn) / np.maximum(mx, 1e-6)
    over = s > k["sat_max"] + 1e-4
    return np.where(over, mx - (mx - c) * (k["sat_max"] / np.maximum(s, 1e-6)), c)


def check_viewer(ctx):
    """Runs the viewer headless (v2/web/scripts/viewer_checks.mjs) against this release, then compares its shadow
    masks with the Python reference at the same pixels."""
    P = ctx.params["g1"]
    rel = ctx.dep("release")
    rep = Report("viewer")
    out = ctx.out
    with viewer_server(rel) as base:
        r = subprocess.run(["node", str(WEB / "scripts" / "viewer_checks.mjs"), base, str(out)],
                           cwd=WEB, capture_output=True, text=True, timeout=1800)
    if r.returncode:
        raise RuntimeError("viewer checks failed to run: " + (r.stderr or r.stdout)[-3000:])
    V = json.loads((out / "viewer.json").read_text())
    rep.info("V0", "browser and GPU", V["gpu"])
    rep.at_most("V0b", "page errors", len(V["errors"]), 0, V["errors"])
    for x, n in V["layer_off"].items():
        rep.at_most(f"V1-{x}", f"?off={x}: pixels still showing layer {x}", n, 0)
    # shadows: the viewer's masks against the Python reference at the same pixels (layer 8's depth)
    R = _renderer(ctx)
    hm = build_heightmap(R)
    from zoneinfo import ZoneInfo
    masks = {}
    for name in ("10", "16", "13", "16_nobuildings"):
        meta = json.loads((out / f"shadow_{name}.json").read_text())
        m = np.frombuffer((out / f"shadow_{name}.bin").read_bytes(), np.uint8).reshape(meta["H"], meta["W"])
        masks[name] = m
        hour = int(name.split("_")[0])
        y, mo, d = (int(v) for v in meta["date"].split("-"))
        az, el, _ = sun_vector(dt.datetime(y, mo, d, hour, tzinfo=ZoneInfo("Europe/Luxembourg")))
        px = meta["x0"] + np.arange(meta["W"]) + 0.5
        py = meta["y0"] + np.arange(meta["H"]) + 0.5
        PX, PY = np.meshgrid(px, py)
        bt = TileCache(rel, "buffers", maxn=64)
        dep = np.array([np.inf if v is None else v for v in bt.lookup(PX.ravel(), PY.ravel(), "depth")]).reshape(PX.shape)
        okd = np.isfinite(dep)
        e, n, z = unproject(PX[okd], PY[okd], dep[okd])
        src = ("terrain", "trees", "structures") if "nobuildings" in name else ("terrain", "buildings", "trees", "structures")
        ref = np.zeros(PX.shape, bool)
        ref[okd] = shadow_ref(hm, e, n, z, az, el, sources=src) > 0
        got = m < 128
        match = float((got[okd] == ref[okd]).mean())
        if name == "16_nobuildings":
            rep.at_least("V2", "?off=buildings: the viewer's shadows equal the reference without buildings (share of pixels)",
                         round(match, 4), 0.97)
        else:
            rep.at_least(f"V3-{name}", f"shadows at {name}:00 on {meta['date']} match the Python reference (share of pixels; "
                         f"{float(ref[okd].mean()):.1%} in shadow)", round(match, 4), 0.97)
    moved = float(((masks["10"] < 128) != (masks["16"] < 128)).mean())
    rep.at_least("V3b", "share of pixels whose shadow changes between 10:00 and 16:00 (shadows move with ?hour)", round(moved, 4), 0.02)
    rep.at_most("V4", "pixels changed by the night layer at 13:00 (no light by day, L10.2)", V["night_by_day"], 0)
    rep.at_most("V5", "pixels changed by the season outside the tree and green-ground masks (L11.1)", V["season_outside"], 0)
    rep.at_most("V6", "overlapping labels at the reference views (L15.2)", V["label_overlaps"], 0)
    day = np.frombuffer((out / "day_13.bin").read_bytes(), np.uint8).reshape(-1, 4)[:, :3].astype(float) / 255
    once = look_grade(day)
    rep.at_most("V7", "the look pass applied again to the viewer's output: largest channel change (L14.1, in 1/255)",
                int(round(float(np.abs(once - day).max()) * 255)), 1)
    S = V["speed"]
    rep.info("C2", "speed (desktop, this machine's GPU)", S)
    rep.at_most("C2a", "first view, warm (s)", round(S["first_view_warm_s"], 3), P["speed_first_view_s"])
    rep.at_least("C2b", "panning, desktop (frames per second, all layers on, vehicles moving)", round(S["pan_fps"], 1),
                 P["speed_pan_fps_desktop"])
    rep.info("C2c", "mid phone: not measured on a device (see the report); 4x CPU throttle", S.get("throttled", {}))
    return rep.result()


class viewer_server:
    """A dev server of the viewer for a release, on a free port, stopped on exit: `with viewer_server(rel) as url:`."""

    def __init__(self, rel: Path):
        self.rel = rel

    def __enter__(self):
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        env = dict(os.environ, V2_RELEASE=str(self.rel), PORT=str(port))
        self.p = subprocess.Popen(["node", str(WEB / "node_modules" / "vite" / "bin" / "vite.js"), "--port", str(port),
                                   "--strictPort"], cwd=WEB, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        t_end = time.time() + 60
        while time.time() < t_end:
            line = self.p.stdout.readline()
            if "Local:" in line or "ready in" in line:
                break
            if self.p.poll() is not None:
                raise RuntimeError("the viewer's dev server did not start")
        time.sleep(0.5)
        return f"http://localhost:{port}/"

    def __exit__(self, *a):
        self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
