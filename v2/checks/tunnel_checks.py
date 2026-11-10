"""Gate checks of the tunnel view (x-ray), X1-X8 of v2/docs/specs/tunnel-view.md, on the built release of an area.

The viewer is run headless (v2/web/scripts/xray_checks.mjs) at views that together hold every tube at 1 screen pixel
per map pixel. Its debug frames (?debug=xid: class, depth step and tube index per pixel; ?debug=xdepth: the tubes'
depth buffer) are compared here with the transport graph itself, not with the tubes' file:

X1  the drawn centre line of every tunnel edge against the projection of its graph profile, every 0.5 m
X2  the depth buffer against the depth, at the same pixel, of the floor built on the graph's profile; the cover
    drawn (the tone's step) and stored against the graph's cover, and (reported) against the terrain
X3  vehicles: in still frames, every vehicle pixel of the tunnel pass lies on a vehicle that is in a tunnel past
    its portal; over a simulated day (scripts/xray_audit.ts) the viewer's choice equals the graph's rule, and every
    such vehicle lies inside its tube's footprint on screen (reported: its pixels behind a tunnel face)
X4  off is as it was (0 pixels); on, the city is the plain frame at the fixed opacity over the neutral colour
    (<= 1/255), and no step is added at the tile borders
X5  each ?off= layer leaves no pixel in tunnel view, and the tunnels and their vehicles are unchanged by it
X6  each tube ends at the portal layer 4 draws (the transport tiles' portal pixels)
X7  the casemates: drawn from their data (as X1, X2), 1 m of rock over every gallery's top, only in tunnel view
X8  turning the view on or off takes one frame; panning in tunnel view on this machine
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
import zlib

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint

from v2.checks.framework import Report
from v2.checks.g1_checks import WEB, _jumps, _lab, box_pixels, box_tris, viewer_server
from v2.checks.layer_checks import TileCache
from v2.layers import tunnels as T
from v2.layers.common import CLASS, COLOUR_LAYERS, TILE, Scene, project, project_local, unproject
from v2.layers.light import LIGHT
from v2.layers.raster import HeightField, raster_tris

VIEW_W, VIEW_H = 1600, 1200
DATE = "2026-06-21"
FLOOR_CLASSES = (1, 4)            # the debug frame's classes: 1 floor, 2 wall, 3 end, 4 centre line, 5 vehicle


# ------------------------------------------------------------------------------------------------ frames
class Frames:
    """The frames xray_checks.mjs wrote: RGB rows, top first; a view (cx, cy) shows map pixel x0 + column."""

    def __init__(self, folder, W=VIEW_W, H=VIEW_H):
        self.folder, self.W, self.H = folder, W, H
        self._ids = {}

    def rgb(self, name):
        return np.frombuffer(zlib.decompress((self.folder / f"{name}.rgb.z").read_bytes()), np.uint8).reshape(self.H, self.W, 3)

    def ids(self, name):
        """(class, depth step, tube index) per pixel of a debug=xid frame."""
        if name not in self._ids:
            if len(self._ids) >= 6:
                self._ids.pop(next(iter(self._ids)))
            a = self.rgb(name)
            self._ids[name] = (a[..., 0] & 15, a[..., 0] >> 4, a[..., 1].astype(np.int32) + 256 * a[..., 2].astype(np.int32))
        return self._ids[name]

    def depth(self, name, depth_cm):
        """View depth (m) per pixel of a debug=xdepth frame; inf where no tube is drawn."""
        a = self.rgb(name).astype(np.float64)
        code = a[..., 0] + 256 * a[..., 1] + 65536 * a[..., 2]
        d = (depth_cm[0] + code / 16777215.0 * (depth_cm[1] - depth_cm[0])) / 100.0
        return np.where(code >= 16777215, np.inf, d)

    def origin(self, view):
        return view[0] - self.W // 2, view[1] - self.H // 2


def cover_views(px, py, W=VIEW_W, H=VIEW_H, margin=24):
    """Views (centres, whole map pixels) that together hold every point at least `margin` px from a frame's edge."""
    sx, sy = W - 2 * margin, H - 2 * margin
    gx, gy = np.floor(px / sx).astype(int), np.floor(py / sy).astype(int)
    cells = sorted(set(zip(gx.tolist(), gy.tolist())))
    views = [(c[0] * sx + sx // 2, c[1] * sy + sy // 2) for c in cells]
    which = {c: i for i, c in enumerate(cells)}
    return views, np.array([which[c] for c in zip(gx.tolist(), gy.tolist())], np.int64)


def line_samples(en, z, step, end_skip=0.25):
    """Points every `step` m along a 3D polyline (not within end_skip of its ends): E, N, z."""
    en, z = np.asarray(en, float), np.asarray(z, float)
    s0 = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
    L = float(s0[-1])
    if L <= 2 * end_skip:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    s = np.arange(end_skip, L - end_skip + 1e-9, step)
    return np.interp(s, s0, en[:, 0]), np.interp(s, s0, en[:, 1]), np.interp(s, s0, z)


def centre_lines(sc, data, casemates):
    """Per tube of the release, its centre line from the source data (never from the tubes' file): the graph edge's
    polyline and profile, or the casemate gallery's: {tube index: (en, z, cover or None)}."""
    edges = sc.graph["edges"]
    gal = {f"casemate/{g['id']}": g for g in (casemates or {}).get("galleries", [])}
    out = {}
    for i, t in enumerate(data["tubes"]):
        if t["edge"] >= 0:
            e = edges[t["edge"]]
            en, z = np.array(e["en"], float), np.array(e["z"], float)
            cov = np.array(e["cover"], float) - z if e["structure"] == "tunnel" else T.depth_under_ground(e)
        else:
            g = gal[t["id"]]
            en = np.array(g["en"], float)
            z = np.array(g["z"] if isinstance(g["z"], list) else [g["z"]] * len(en), float)
            cov = None
        out[i] = (en, z, cov)
    return out


# ------------------------------------------------------------------------------------------------ X1, X2
def tube_samples(lines, step):
    """Samples of every tube's centre line: (tube index, E, N, z)."""
    S = {"tube": [], "E": [], "N": [], "z": []}
    for i, (en, z, _) in lines.items():
        e, n, zz = line_samples(en, z, step)
        S["tube"].append(np.full(len(e), i)); S["E"].append(e); S["N"].append(n); S["z"].append(zz)
    return (np.concatenate(S["tube"]).astype(int),) + tuple(np.concatenate(S[k]) for k in ("E", "N", "z"))


def source_floors(sc, data, casemates, lines, share):
    """Per tube, the floor built on its source's centre line (the graph edge's polyline, profile, width and ends; the
    casemate gallery's), projected: (pixels (v, 2), depth (v,), triangles)."""
    oe, on = data["origin_en"]
    edges = sc.graph["edges"]
    codes = T.end_codes(sc.graph, {i for i, e in enumerate(edges) if len(e["en"]) >= 2 and T.is_tube(e, share)})
    gal = {f"casemate/{g['id']}": g for g in (casemates or {}).get("galleries", [])}
    out = {}
    for i, t in enumerate(data["tubes"]):
        en, z, _ = lines[i]
        if t["edge"] >= 0:
            e = edges[t["edge"]]
            rec = {"w": float(e["width"]), "h": float(e.get("clearance_m", 2.5)), "ends": list(codes[t["edge"]])}
        else:
            g = gal[t["id"]]
            rec = {"w": float(g["width_m"]), "h": float(g["height_m"]),
                   "ends": [{"open": T.OPEN, "closed": T.CLOSED}[v] for v in g.get("ends", ["closed", "closed"])]}
        rec.update(p=np.column_stack([en[:, 0] - oe, en[:, 1] - on]).ravel(), z=z, c=np.zeros(len(z)))
        V, tri, kind = T.tube_mesh(rec, data["portal_face_m"])
        tri = tri[kind == T.FLOOR]
        px, py, d = project_local(V[:, 0], V[:, 1], V[:, 2])
        out[i] = (np.column_stack([px, py]), d, tri)
    return out


def measure_tubes(F, views, which, samples, lines, floors, data, P, step_m, casemate):
    """X1 and X2 on the geometry frames (a casemate's sample on the frames with the casemates, a tunnel's on those
    without them): per sample of a tube's centre line (in view which[i]), whether it is seen (the 3 x 3 pixels round
    it are this tube's drawn floor: not behind a nearer tube, not where two floors meet at a junction), whether this
    tube's drawn centre line is within `xray_line_px` of it, and where seen the drawn floor's depth against the
    profile's at that pixel (cm) and the drawn depth step.

    The profile's depth at a pixel: the floor built on the source's own centre line (`floors`: the graph's polyline
    and profile, level across at every sample), drawn here at full precision for the same pixel centres."""
    tube, E, N, Z = samples
    px, py, _ = project(E, N, Z)
    seen = np.zeros(len(E), bool)
    on = np.zeros(len(E), bool)
    err_cm = np.full(len(E), np.nan)
    band_bad = np.zeros(len(E), bool)
    geom = {i: (LineString(en), np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))], z, cov)
            for i, (en, z, cov) in lines.items()}
    for v, name, fam in [(v, n, c) for v in range(len(views)) for n, c in (("geo", False), ("geoc", True))]:
        m = np.flatnonzero((which == v) & (casemate[tube] == fam))
        if not len(m):
            continue
        x0, y0 = F.origin(views[v])
        cls, band, tid = F.ids(f"{name}_{v}_id")
        D = F.depth(f"{name}_{v}_depth", data["depth_cm"])
        sx, sy = px[m] - x0, py[m] - y0
        ix, iy = np.floor(sx).astype(int), np.floor(sy).astype(int)
        mine = np.isin(cls, FLOOR_CLASSES)
        s_ = np.ones(len(m), bool)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                s_ &= mine[iy + dy, ix + dx] & (tid[iy + dy, ix + dx] == tube[m])
        seen[m] = s_
        # the drawn centre line of this tube nearest the sample (pixel centres)
        best = np.full(len(m), np.inf)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                jx, jy = ix + dx, iy + dy
                ok = (cls[jy, jx] == 4) & (tid[jy, jx] == tube[m])
                best = np.where(ok, np.minimum(best, np.hypot(jx + 0.5 - sx, jy + 0.5 - sy)), best)
        on[m] = s_ & (best <= P["xray_line_px"])
        # the drawn floor at the sample's pixel against the profile's floor at that pixel
        k = m[s_]
        if len(k):
            e_, n_, _ = unproject(x0 + ix[s_] + 0.5, y0 + iy[s_] + 0.5, D[iy[s_], ix[s_]])
            for t in np.unique(tube[k]):
                line, s0, _, cov = geom[int(t)]
                j = tube[k] == t
                Pf, Df, Tf = floors[int(t)]
                jx, jy = ix[s_][j], iy[s_][j]
                wx, wy = int(jx.min()), int(jy.min())                         # a window round this tube's samples
                ww, wh = int(jx.max()) - wx + 1, int(jy.max()) - wy + 1
                ref = np.full((wh, ww), np.inf)
                raster_tris(Pf - [x0 + wx, y0 + wy], Df, Tf, ww, wh, ref, np.full((wh, ww), -1, np.int64))
                err_cm[k[j]] = np.abs(D[jy, jx] - ref[jy - wy, jx - wx]) * 100
                s_at = shapely.line_locate_point(line, shapely.points(e_[j], n_[j]))
                if cov is not None:
                    c_at = np.interp(s_at, s0, cov)
                    want = np.minimum(np.floor(np.maximum(c_at, 0) / step_m[0]), step_m[1])
                    edge = np.abs(c_at / step_m[0] - np.round(c_at / step_m[0])) * step_m[0] < 0.05
                    band_bad[k[j]] = (band[iy[s_], ix[s_]][j] != want) & ~edge
    return {"tube": tube, "E": E, "N": N, "seen": seen, "on": on, "err_cm": err_cm, "band_bad": band_bad}


# ------------------------------------------------------------------------------------------------ X6
def portal_ends(sc, data):
    """Every portal end of a tube of the graph: where its tube should end (the face layer 4 draws: the end node,
    `portal_face_m` out; base: the middle of the face's foot), whether layer 4 draws a portal there
    (geometry.portal_mesh's rule), and whether another tunnel edge joins at that node (then the tunnel goes on
    there: it has a side way out, not an end)."""
    from v2.layers.common import VIEW
    face = data["portal_face_m"]
    edges = sc.graph["edges"]
    tunnels_at = {}
    for i, e in enumerate(edges):
        if e["structure"] == "tunnel":
            for end in ("a", "b"):
                tunnels_at.setdefault(int(e[end]), set()).add(i)
    out = []
    for i, t in enumerate(data["tubes"]):
        if t["edge"] < 0:
            continue
        e = edges[t["edge"]]
        en, z = np.array(e["en"], float), np.array(e["z"], float)
        for end in (0, 1):
            if t["ends"][end] != T.PORTAL:
                continue
            p, q = (en[0], en[1]) if end == 0 else (en[-1], en[-2])
            u = (p - q) / np.linalg.norm(p - q)
            drawn = (e["structure"] == "tunnel" and not (e["mode"] in ("path", "steps") and float(e["width"]) < 1.5)
                     and u[0] * VIEW[0] + u[1] * VIEW[1] <= 0)
            out.append({"tube": i, "edge": t["edge"], "id": t["id"], "base": (p + u * face).tolist(), "z": float(z[0] if end == 0 else z[-1]),
                        "out": u.tolist(), "w": t["w"], "h": t["h"], "drawn": bool(drawn),
                        "joined": len(tunnels_at.get(int(e["a" if end == 0 else "b"]), set()) - {t["edge"]}) > 0})
    return out


def measure_portals(F, views, which, ends, rel, P, mpp, depth_cm):
    """Per portal end (in view which[i]):
    end_px     how far past (+) or short of (-) the portal's face the drawn floor of its tube ends, along the way,
               in screen px. A floor pixel is put back in the world by its drawn depth; of those across the tube's
               width at its end, the one furthest along the way. None where the end is not to be seen: `hidden`
               (a nearer tube is drawn over the face's foot) or `joined`.
    portal_px  how far the portal pixels of layer 4 (its tiles' ids) reach outside the face's rectangle (the way's
               width + 1 m by its clearance, standing on the face's foot), in px: 0 when layer 4's portal is where
               the tube ends."""
    tr = TileCache(rel, "transport", maxn=64)
    other = {}
    for r in ends:
        if r["drawn"]:
            other.setdefault(r["edge"], []).append(r)
    for r, v in sorted(zip(ends, which.tolist()), key=lambda rv: rv[1]):
        b = np.array(r["base"])
        o = np.array(r["out"])
        lf = np.array([-o[1], o[0]])
        bx, by, _ = project(b[0], b[1], r["z"])
        ox, oy, _ = project(b[0] + o[0], b[1] + o[1], r["z"])
        lx, ly, _ = project(b[0] + lf[0], b[1] + lf[1], r["z"])
        ux, uy, _ = project(b[0], b[1], r["z"] + 1.0)
        so, sl, su = np.array([ox - bx, oy - by]), np.array([lx - bx, ly - by]), np.array([ux - bx, uy - by])   # px per metre
        x0, y0 = F.origin(views[v])
        cls, _, tid = F.ids(f"geo_{v}_id")
        D = F.depth(f"geo_{v}_depth", depth_cm)
        R = int(math.ceil((r["w"] / 2 + 1.0) / mpp))             # the floor's end, across the way and a metre along it
        ix, iy = int(bx - x0), int(by - y0)
        ax, ay = max(ix - R, 0), max(iy - R, 0)
        sub = (slice(ay, min(iy + R + 1, F.H)), slice(ax, min(ix + R + 1, F.W)))
        yy, xx = np.nonzero(np.isin(cls[sub], FLOOR_CLASSES) & (tid[sub] == r["tube"]))
        r["end_px"] = None
        r["hidden"] = bool(D[iy, ix] < project(b[0], b[1], r["z"])[2] - 0.3)
        if len(xx) and not r["hidden"] and not r["joined"]:
            # each floor pixel back in the world (its drawn depth), then along and across the way from the face's foot
            e_, n_, _ = unproject(xx + ax + 0.5 + x0, yy + ay + 0.5 + y0, D[sub][yy, xx])
            al, ac = (e_ - b[0]) * o[0] + (n_ - b[1]) * o[1], (e_ - b[0]) * lf[0] + (n_ - b[1]) * lf[1]
            mine = np.abs(ac) <= r["w"] / 2
            if mine.any():
                r["end_px"] = float(al[mine].max() * np.linalg.norm(so))
        r["portal_px"] = None
        if r["drawn"]:
            want = ((r["edge"] + 1) << 8) | CLASS["portal"]
            R = int(math.ceil((r["w"] + 8.0) / mpp))
            gx, gy = np.meshgrid(np.arange(int(bx) - R, int(bx) + R + 1), np.arange(int(by) - R, int(by) + R + 1))
            ids = np.array([0 if v is None else int(v) for v in tr.lookup(gx.ravel() + 0.5, gy.ravel() + 0.5, "ids")], np.int64)
            hit = ids == want
            for q in other[r["edge"]]:                  # the edge's other portal: its pixels are nearer its own foot
                if q is not r:
                    qx, qy, _ = project(q["base"][0], q["base"][1], q["z"])
                    hit &= np.hypot(gx.ravel() + 0.5 - bx, gy.ravel() + 0.5 - by) <= np.hypot(gx.ravel() + 0.5 - qx, gy.ravel() + 0.5 - qy)
            if hit.any():
                # in the face's plane: screen offset = across * sl + up * su (metres)
                au = np.linalg.solve(np.column_stack([sl, su]), np.vstack([gx.ravel()[hit] + 0.5 - bx, gy.ravel()[hit] + 0.5 - by]))
                over_a = np.maximum(np.abs(au[0]) - (r["w"] + 1.0) / 2, 0) * np.linalg.norm(sl)
                over_u = np.maximum(np.maximum(-au[1], au[1] - r["h"]), 0) * np.linalg.norm(su)
                r["portal_px"] = float(np.hypot(over_a, over_u).max())
                r["portal_pixels"] = int(hit.sum())
    return ends


# ------------------------------------------------------------------------------------------------ X3
def graph_rule(sc, rows, portal_default_m, tube_edges):
    """For the audit's samples: by the graph alone, is the vehicle in a tunnel past its portal? Returns (in, margin):
    margin is how far its nearer end is past the portal line (m)."""
    from v2.config.camera import camera
    oe, on = camera()["origin_en"]
    edges = sc.graph["edges"]
    portal = {}
    for p in sc.graph["portals"]:
        if p.get("found"):
            portal[str(p["chain"])] = max(portal.get(str(p["chain"]), 0.0), float(p["dist_m"]))
    E, N, L, EDGE = rows[:, 0] + oe, rows[:, 1] + on, rows[:, 4], rows[:, 7].astype(int)
    margin = np.full(len(rows), -np.inf)
    for i in np.unique(EDGE):
        if i < 0 or i not in tube_edges:
            continue
        e = edges[int(i)]
        m = EDGE == i
        s0 = np.array(e["s"], float)
        d = np.array(e["tunnel_d"], float) if e["structure"] == "tunnel" else np.minimum(s0, s0[-1] - s0)
        s = shapely.line_locate_point(LineString(e["en"]), shapely.points(E[m], N[m]))
        margin[m] = np.interp(s, s0, d) - L[m] / 2 - portal.get(str(e.get("chain")), portal_default_m)
    return margin >= 0, margin


class TubeFaces:
    """Every tube's drawn faces and boxes projected to the map, for the vehicles' tests."""

    def __init__(self, data):
        face = data["portal_face_m"]
        trims = T.wall_trims(data["tubes"], face, data["junction"])
        self.mesh, self.world, hulls, owner = [], [], [], []
        for i, t in enumerate(data["tubes"]):
            V, tri, _ = T.tube_mesh(t, face, trims[i])
            self.world.append((V, tri))
            px, py, d = project_local(V[:, 0], V[:, 1], V[:, 2]) if len(V) else (np.zeros(0),) * 3
            self.mesh.append((np.column_stack([px, py]), d, tri))
            for box in T.tube_prisms(t, face):
                bx, by, _ = project_local(box[:, 0], box[:, 1], box[:, 2])
                hulls.append(MultiPoint(np.column_stack([bx, by])).convex_hull)
                owner.append(i)
        self.hulls, self.owner = np.array(hulls, object), np.array(owner)
        self.tree = shapely.STRtree(self.hulls)

    def near(self, poly):
        return self.tree.query(poly, predicate="intersects")


def measure_day(sc, data, TF, rows, deep_ref, eps, own_tubes):
    """X3 over the simulated day, for the samples in a tunnel past its portal: pixels of the vehicle's box outside
    the tubes' footprint on screen, and pixels behind a drawn tunnel face (the floor of its own tube, or a face of
    another tube)."""
    from v2.config.camera import camera
    oe, on = camera()["origin_en"]
    res = {"samples": 0, "pixels": 0, "out_px": 0, "out_samples": 0, "out_ex": [], "hidden_own_px": 0, "hidden_other_px": 0,
           "hidden_own_samples": 0, "unseen_samples": 0, "hidden_ex": [], "out_by_kind": {}}
    for k in np.flatnonzero(deep_ref):
        X, Y, Z, Hd, L, W, Hh, EDGE, KIND, SEC = rows[k, :10]
        V, tri = box_tris(X + oe, Y + on, Z, Hd, L, W, Hh)
        bx, by, bd = box_pixels(V, tri)
        if not len(bx):
            continue
        res["samples"] += 1
        res["pixels"] += len(bx)
        hx, hy, _ = project(V[:, 0], V[:, 1], V[:, 2])
        hull = MultiPoint(np.column_stack([hx, hy])).convex_hull
        near = TF.near(hull)
        union = shapely.union_all(TF.hulls[near]) if len(near) else None
        if union is None or not union.contains(hull):
            outside = np.ones(len(bx), bool) if union is None else ~shapely.contains_xy(union, bx + 0.5, by + 0.5)
            n = int(outside.sum())
            if n:
                res["out_px"] += n
                res["out_samples"] += 1
                res["out_by_kind"][int(KIND)] = res["out_by_kind"].get(int(KIND), 0) + 1
                if len(res["out_ex"]) < 8:
                    res["out_ex"].append({"edge": sc.graph["edges"][int(EDGE)]["id"], "kind": int(KIND), "sec": int(SEC),
                                          "e": round(float(X + oe), 1), "n": round(float(Y + on), 1), "pixels": n, "of": len(bx)})
        # the depth test against the tubes' drawn faces (as the viewer: the box eps nearer, drawn where <= the face)
        x0, y0 = int(bx.min()), int(by.min())
        w, h = int(bx.max()) - x0 + 1, int(by.max()) - y0 + 1
        zb = np.full((h, w), np.inf)
        own = np.zeros((h, w), bool)
        me = own_tubes.get(int(EDGE))
        for ti in np.unique(TF.owner[near]):
            Pm, Dm, Tm = TF.mesh[int(ti)]
            if not len(Tm):
                continue
            z1 = np.full((h, w), np.inf)
            raster_tris(Pm - [x0, y0], Dm, Tm, w, h, z1, np.full((h, w), -1, np.int64))
            nearer = z1 < zb
            zb[nearer] = z1[nearer]
            own[nearer] = int(ti) == me
        hid = zb[by - y0, bx - x0] < bd - eps - 1e-6
        if hid.any():
            o = own[by - y0, bx - x0][hid]
            res["hidden_own_px"] += int(o.sum())
            res["hidden_other_px"] += int((~o).sum())
            res["hidden_own_samples"] += int(o.any())
            res["unseen_samples"] += int(hid.all())
            if o.any() and len(res["hidden_ex"]) < 8:
                res["hidden_ex"].append({"edge": sc.graph["edges"][int(EDGE)]["id"], "kind": int(KIND), "sec": int(SEC),
                                         "e": round(float(X + oe), 1), "n": round(float(Y + on), 1), "pixels": int(o.sum()), "of": len(bx)})
    return res


def measure_stills(F, views, V, oe, on):
    """X3 in the still frames: vehicle pixels of the tunnel pass that lie on no vehicle that is in a tunnel (its box,
    grown by one pixel for the rounding of its edges), and the vehicles in a tunnel that show at least a pixel."""
    out = {"vehicles_in_tunnels": 0, "shown": 0, "vehicle_px": 0, "other_px": 0}
    from scipy import ndimage
    for S in V:
        inst = np.array(S["inst"], float).reshape(-1, 4)
        size = np.array(S["size"], float).reshape(-1, 4)
        deep = np.array(S["deep"], bool)
        boxes = []
        for k in np.flatnonzero(deep):
            Vb, tri = box_tris(inst[k, 0] + oe, inst[k, 1] + on, inst[k, 2], inst[k, 3], size[k, 0], size[k, 1], size[k, 2])
            boxes.append(box_pixels(Vb, tri))
        out["vehicles_in_tunnels"] += len(boxes)
        shown = np.zeros(len(boxes), bool)
        for v in S["views"]:
            x0, y0 = F.origin(views[v])
            cls, _, _ = F.ids(f"veh_{S['hour']}_{v}_id")
            ref = np.zeros(cls.shape, bool)
            for j, (bx, by, _) in enumerate(boxes):
                cx, cy = bx - x0, by - y0
                ok = (cx >= 0) & (cx < F.W) & (cy >= 0) & (cy < F.H)
                ref[cy[ok], cx[ok]] = True
                shown[j] |= bool((cls[cy[ok], cx[ok]] == 5).any())
            veh = cls == 5
            out["vehicle_px"] += int(veh.sum())
            out["other_px"] += int((veh & ~ndimage.binary_dilation(ref, iterations=1)).sum())
        out["shown"] += int(shown.sum())
    return out


# ------------------------------------------------------------------------------------------------ X4
def faded(plain, ground, opacity):
    return ground[None, None, :] * (1 - opacity) + plain.astype(np.float64) * opacity


def fade_error(F, plain, xray, ids, ground, opacity):
    """Largest channel difference (in 1/255) between the tunnel view's city pixels and the plain frame faded offline;
    the city pixels are those the tunnel pass drew nothing on."""
    cls = F.ids(ids)[0]
    city = cls == 0
    ref = faded(F.rgb(plain), ground, opacity)
    d = np.abs(F.rgb(xray).astype(np.float64) - ref).max(-1)
    return float(d[city].max()) if city.any() else 0.0, int(city.sum()), ref, city


def border_steps(rgb, valid, x0, y0, W, H):
    """The colour step (LAB vector of the 4 px either side, per 64 px chunk) across every tile border in a frame."""
    lab = _lab(rgb)
    out = []
    for axis, o, size in ((1, x0, W), (0, y0, H)):
        first = (-o) % TILE
        for pos in range(first, size, TILE):
            if pos < 24 or pos > size - 24:
                continue
            out += [(axis, pos, a, vec) for a, _, skip, vec in _jumps(lab, valid, pos, axis) if not skip]
    return out


# ------------------------------------------------------------------------------------------------ the check
def check_tunnel_view(ctx):
    P, TP = ctx.params["g3"], ctx.params["tunnels"]
    rel = ctx.dep("release")
    sc = Scene(ctx.dep("scene"))
    rep = Report("tunnel_view")
    out = ctx.out
    t_start = time.time()
    idx = json.loads((rel / "index.json").read_text())
    X = idx["config"]["xray"]
    data = json.loads((rel / "tunnels.json").read_text())
    casemates = json.loads(T.CASEMATES.read_text()) if T.CASEMATES.exists() else None
    tubes = data["tubes"]
    from v2.config.camera import camera
    oe, on = camera()["origin_en"]
    kinds = {}
    for t in tubes:
        kinds[t["kind"]] = kinds.get(t["kind"], 0) + 1
    rep.info("X0", "tubes in the release (by kind), their length (m), the deepest floor under the surface (m)",
             {"by_kind": kinds, "length_m": round(sum(t["s"][-1] for t in tubes), 1), "deepest_m": max(max(t["c"]) for t in tubes)})
    # rule 1: the tubes are the graph's: every tunnel edge of the area has its tube, with the edge's width and clearance
    edges = sc.graph["edges"]
    want = {i for i, e in enumerate(edges) if len(e["en"]) >= 2 and T.is_tube(e, TP["underground_share"])
            and shapely.contains_xy(sc.polygon, np.array(e["en"])[:, 0], np.array(e["en"])[:, 1]).any()}
    have = {t["edge"]: t for t in tubes if t["edge"] >= 0}
    wrong = [edges[i]["id"] for i in want ^ set(have)]
    wrong += [t["id"] for i, t in have.items() if i in want and (abs(t["w"] - float(edges[i]["width"])) > 1e-6
                                                                 or abs(t["h"] - float(edges[i].get("clearance_m", 2.5))) > 1e-6)]
    rep.at_most("X0a", f"tunnel edges of the graph without their tube, or tubes without their edge's width and clearance "
                f"(of {len(want)} edges)", len(wrong), 0, wrong)
    # ---------------------------------------------------------------- the views, then the viewer
    lines = centre_lines(sc, data, casemates)
    samples = tube_samples(lines, P["xray_line_step_m"])
    ends = portal_ends(sc, data)
    sp = project(samples[1], samples[2], samples[3])
    ep = project(np.array([r["base"][0] for r in ends]), np.array([r["base"][1] for r in ends]), np.array([r["z"] for r in ends]))
    # every sample of a centre line and every portal is in one view, at least 24 px from its edge
    views, which = cover_views(np.r_[sp[0], ep[0]], np.r_[sp[1], ep[1]])
    which_s, which_e = which[:len(sp[0])], which[len(sp[0]):]
    bock = next((t for t in tubes if t["kind"] == "casemate"), None)
    busy = max((t for t in tubes if t["mode"] == "road"), key=lambda t: t["s"][-1], default=tubes[0])

    def mid(t):
        k = len(t["z"]) // 2
        x, y, _ = project_local(t["p"][2 * k], t["p"][2 * k + 1], t["z"][k])
        return [int(round(float(x))), int(round(float(y)))]
    ext = idx["extent_px"]
    tile_view = [int(round(mid(busy)[0] / TILE)) * TILE, int(round(mid(busy)[1] / TILE)) * TILE]
    is_case = np.array([t["kind"] == "casemate" for t in tubes])
    jobs = {"size": [VIEW_W, VIEW_H], "date": DATE, "views": [list(v) for v in views], "vehicle_hours": [8.5, 17.5],
            "casemate_views": sorted(set(which_s[is_case[samples[0]]].tolist())),
            "layers": COLOUR_LAYERS, "whole": [(ext[0] + ext[2]) // 2, (ext[1] + ext[3]) // 2, 0.25],
            "bock": mid(bock) if bock else mid(busy), "busy": mid(busy),
            "casemate_from": min((i for i, t in enumerate(tubes) if t["kind"] == "casemate"), default=len(tubes)),
            "fade_views": [{"name": f"{n}_{h}", "x": x, "y": y, "hour": h} for n, (x, y) in
                           (("tunnel", tile_view), ("bock", mid(bock) if bock else tile_view)) for h in (13, 23)]}
    (out / "jobs.json").write_text(json.dumps(jobs))
    with viewer_server(rel) as base:
        r = subprocess.run(["node", str(WEB / "scripts" / "xray_checks.mjs"), base, str(out)], cwd=WEB, capture_output=True,
                           text=True, timeout=3600)
    if r.returncode:
        raise RuntimeError("the tunnel view's checks failed to run: " + (r.stderr or r.stdout)[-3000:])
    R = json.loads((out / "xray.json").read_text())
    F = Frames(out)
    rep.info("X0b", "browser and GPU; views at 1 px per map px", {**R["gpu"], "views": len(views), "size": [VIEW_W, VIEW_H]})
    rep.at_most("X0c", "page errors", len(R["errors"]), 0, R["errors"])
    # ---------------------------------------------------------------- X1, X2 (and X7's share of them)
    M = measure_tubes(F, views, which_s, samples, lines, source_floors(sc, data, casemates, lines, TP["underground_share"]), data, P,
                      (X["depth_step_m"], X["depth_steps"]), is_case)

    def line_score(sel, what, cid):
        bad, worst, unseen = [], 1.0, 0
        for i in np.unique(M["tube"][sel]):
            m = sel & (M["tube"] == i)
            n = int(M["seen"][m].sum())
            if not n:
                unseen += 1
                continue
            share = float(M["on"][m].sum() / n)
            worst = min(worst, share)
            if share < P["xray_line_share"]:
                bad.append({"tube": tubes[int(i)]["id"], "share": round(share, 4), "seen": n})
        n_all, n_seen = int(sel.sum()), int((sel & M["seen"]).sum())
        rep.at_most(cid, f"{what} whose drawn centre line is within {P['xray_line_px']} px of its profile's projection over less "
                    f"than {P['xray_line_share']:.0%} of its seen length ({len(np.unique(M['tube'][sel]))} of them; {n_seen} of "
                    f"{n_all} samples every {P['xray_line_step_m']} m seen, the rest behind a nearer tube; {unseen} never seen)",
                    len(bad), 0, bad)
        rep.info(cid + "-share", f"{what}: share of seen samples on their line; the worst one's",
                 {"all": round(float((sel & M["on"]).sum() / max(n_seen, 1)), 5), "worst": round(worst, 4)})

    def depth_score(sel, what, cid):
        e = M["err_cm"][sel & M["seen"]]
        k = np.flatnonzero(sel & M["seen"])
        w = k[np.argsort(-e)[:3]] if len(k) else []
        rep.at_most(cid, f"{what}: largest difference between the drawn floor's depth (the depth buffer) and the depth, at the same "
                    f"pixel, of the floor on the source's profile (cm; {len(e)} samples)", round(float(e.max()), 3) if len(e) else 0.0, P["xray_depth_cm"],
                    [{"tube": tubes[int(M['tube'][i])]["id"], "e": round(float(M["E"][i]), 1), "n": round(float(M["N"][i]), 1),
                      "cm": round(float(M["err_cm"][i]), 3)} for i in w])
    graph_s = ~is_case[M["tube"]]
    line_score(graph_s, "tunnel edges", "X1")
    depth_score(graph_s, "tunnel edges", "X2")
    cov_err, n_cov = 0.0, 0
    ter = {"terrain": 0, "built_over": 0, "neither": 0}
    Tn = sc.terrain
    mnt = HeightField(Tn["mnt"], Tn["e0"], Tn["n0"], Tn["step"])
    mns = HeightField(Tn["mns"], Tn["e0"], Tn["n0"], Tn["step"])
    for i, t in enumerate(tubes):
        en, z, cov = lines[i]
        if cov is None:
            continue
        cov_err = max(cov_err, float(np.abs(np.array(t["c"]) - cov).max()))
        n_cov += len(cov)
        a = mnt.sample(en[:, 0], en[:, 1]) - z
        b = np.maximum(mns.sample(en[:, 0], en[:, 1]), mnt.sample(en[:, 0], en[:, 1])) - z
        ok_a = np.abs(cov - a) <= P["xray_cover_m"]
        ok_b = ~ok_a & (np.abs(cov - b) <= P["xray_cover_m"])
        ter["terrain"] += int(ok_a.sum()); ter["built_over"] += int(ok_b.sum()); ter["neither"] += int((~ok_a & ~ok_b).sum())
    rep.at_most("X2b", f"largest difference between a tube's depth under the surface and the graph's cover minus its profile "
                f"(m; {n_cov} samples)", round(cov_err, 3), P["xray_cover_m"])
    rep.at_most("X2c", "seen samples whose drawn tone is not the step of the graph's cover there (one step per "
                f"{X['depth_step_m']} m; samples within 5 cm of a step's edge left out)", int((M["band_bad"] & graph_s).sum()), 0)
    rep.info("X2d", f"the graph's cover against the scene's terrain at the centre line (within {P['xray_cover_m']} m of the terrain; "
             "of what is built over the tunnel; of neither: the graph takes the median across the way, on a cliff that differs)", ter)
    # ---------------------------------------------------------------- X3
    st = measure_stills(F, views, R["vehicles"], oe, on)
    rep.at_most("X3a", f"still frames ({len(R['vehicles'])} hours, {st['vehicles_in_tunnels']} vehicles in tunnels, {st['shown']} of them "
                f"showing, {st['vehicle_px']} vehicle pixels at full opacity): pixels on no vehicle that is in a tunnel past its portal",
                st["other_px"], 0)
    audit = out / "audit"
    audit.mkdir(exist_ok=True)
    cmd = ["node", "--experimental-strip-types", "--no-warnings", str(WEB / "scripts" / "xray_audit.ts"), str(rel), str(audit),
           str(P["xray_sim_day_sample_s"])]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=WEB)
    if r.returncode:
        raise RuntimeError("the audit failed: " + r.stderr[-2000:])
    rows = np.frombuffer((audit / "samples.bin").read_bytes(), np.float32).reshape(-1, 11).astype(float)
    (audit / "samples.bin").unlink()
    TF = TubeFaces(data)
    vm = np.frombuffer((audit / "mesh.bin").read_bytes(), np.float32).reshape(-1, 3, 4).astype(float)      # triangles
    (audit / "mesh.bin").unlink()
    mine = np.vstack([np.column_stack([np.full(len(tri), i), V[tri].mean(1)]) for i, (V, tri) in enumerate(TF.world) if len(tri)])
    theirs = np.column_stack([vm[:, 0, 3], vm[:, :, :3].mean(1)])
    gap = float(np.abs(mine - theirs).max()) if len(mine) == len(theirs) else float("inf")     # both in the tubes' order
    rep.at_most("X0d", f"the viewer's tube mesh against the reference mesh of these checks (v2/layers/tunnels.py): largest distance "
                f"between two matching triangles' centres (m; {len(theirs)} and {len(mine)} triangles)", round(gap, 4), 0.01)
    deep_ref, margin = graph_rule(sc, rows, float(ctx.params["portal_max_from_end_m"]), set(have))
    deep_view = rows[:, 10] > 0.5
    line = np.abs(margin) < 0.05                          # on the portal line itself: the two could round apart
    lost = deep_ref & ~deep_view & ~line
    others = deep_view & ~deep_ref & ~line
    ex = lambda m: [{"edge": edges[int(rows[k, 7])]["id"], "sec": int(rows[k, 9]), "margin_m": round(float(margin[k]), 2)}  # noqa: E731
                    for k in np.flatnonzero(m)[:8]]
    rep.info("X3-day", "simulated day: vehicle samples, in a tunnel past its portal by the graph, by the viewer, on the portal line",
             {"samples": len(rows), "every_s": P["xray_sim_day_sample_s"], "graph": int(deep_ref.sum()), "viewer": int(deep_view.sum()),
              "on_the_line": int((line & (deep_ref | deep_view)).sum())})
    rep.at_most("X3b", "vehicles the viewer draws in a tunnel that are not on a tunnel edge past its portal (simulated day)",
                int(others.sum()), 0, ex(others))
    rep.at_most("X3c", "vehicles in a tunnel past its portal that the viewer does not draw there (lost; simulated day)",
                int(lost.sum()), 0, ex(lost))
    own = {t["edge"]: i for i, t in enumerate(tubes) if t["edge"] >= 0}
    day = measure_day(sc, data, TF, rows, deep_ref & deep_view, float(LIGHT["vehicles"]["depth_eps_m"]), own)
    rep.at_most("X3d", f"pixels of vehicles in tunnels outside the tubes' footprint on screen ({day['samples']} samples, "
                f"{day['pixels']} pixels; {day['out_samples']} samples stick out, by kind code {day['out_by_kind']})",
                day["out_px"], 0, day["out_ex"])
    rep.info("X3e", "vehicles in tunnels against the tubes' depth (rule 4), of the pixels above: behind the floor of their own tube "
             "(a vehicle is a level box: on a steep floor its uphill end is under it, as on the surface); behind a face of another "
             "tube; samples with no pixel left", {"own_floor_px": day["hidden_own_px"], "own_floor_samples": day["hidden_own_samples"],
                                                   "other_tube_px": day["hidden_other_px"], "wholly_hidden_samples": day["unseen_samples"],
                                                   "e.g.": day["hidden_ex"][:2]})
    # ---------------------------------------------------------------- X4
    ground = np.array(idx["palette"]["tunnel"]["ground"]["rgb"], float)
    rep.at_most("X4a", f"view off after it was on: pixels that differ from the frame before it was ever on ({len(R['fade'])} views: "
                + ", ".join(f["name"] for f in R["fade"]) + ")", sum(f["off_differs_px"] for f in R["fade"]), 0,
                [f for f in R["fade"] if f["off_differs_px"]])
    worst, npx, seam = 0.0, 0, 0.0
    nseam = 0
    for f in R["fade"]:
        n = f"fade_{f['name']}"
        e, c, ref, city = fade_error(F, n + "_plain", n + "_xray", n + "_id", ground, X["opacity"])
        worst, npx = max(worst, e), npx + c
        x0, y0 = F.origin((f["x"], f["y"]))
        a = border_steps(F.rgb(n + "_xray"), city, x0, y0, F.W, F.H)
        b = border_steps(np.clip(np.round(ref), 0, 255), city, x0, y0, F.W, F.H)
        for (_, _, _, va), (_, _, _, vb) in zip(a, b):
            seam = max(seam, float(np.linalg.norm(va - vb)))
            nseam += 1
    rep.at_most("X4b", f"view on: largest difference of a city pixel from the plain frame at opacity {X['opacity']} over the neutral "
                f"colour, computed offline (in 1/255 per channel; {npx} pixels, day and night)", round(worst, 3), P["xray_fade_tol"])
    rep.at_most("X4c", f"view on: largest colour step the fade adds at a tile border (LAB, the 4 px either side per 64 px, against the "
                f"offline faded frame; {nseam} border chunks)", round(seam, 3), P["xray_seam_de_max"])
    # ---------------------------------------------------------------- X5
    for L in COLOUR_LAYERS:
        rep.at_most(f"X5-{L}", f"tunnel view with ?off={L}: pixels still showing layer {L}; tunnel and vehicle pixels (class, index, "
                    "depth) changed by it", R["layer_off"][L] + R["tunnels_changed"][L], 0)
    worst5 = 0.0
    for L in COLOUR_LAYERS:
        e, _, _, _ = fade_error(F, f"off_{L}_plain", f"off_{L}_xray", f"off_{L}_id", ground, X["opacity"])
        worst5 = max(worst5, e)
    rep.at_most("X5b", "tunnel view with a layer off: largest difference of a city pixel from the plain frame without that layer, "
                "faded offline (in 1/255; the seven layers)", round(worst5, 3), P["xray_fade_tol"])
    # ---------------------------------------------------------------- X6
    ends = measure_portals(F, views, which_e, ends, rel, P, idx["camera"]["mpp"], data["depth_cm"])
    drawn = [r for r in ends if r["drawn"] and r["portal_px"] is not None]
    seen = [r for r in drawn if r["end_px"] is not None]
    val = [max(abs(r["end_px"]), r["portal_px"]) for r in seen]
    bad = [{"tube": r["id"], "tube_end_px": round(r["end_px"], 2), "portal_px": round(r["portal_px"], 2)}
           for r, v in zip(seen, val) if v > P["xray_portal_px"]]
    why = {"joined": sum(1 for r in drawn if r["joined"]), "hidden": sum(1 for r in drawn if r["hidden"] and not r["joined"])}
    rep.at_most("X6", f"portals: how far the drawn tube ends from the face of the portal layer 4 draws (px along the way), or how far "
                f"layer 4's portal pixels reach outside that face, whichever is larger; the worst of {len(seen)} portals "
                f"({len(ends)} portal ends; layer 4 draws {len(drawn)}: those facing the camera, in its tiles; of those {why['joined']} "
                f"are side ways out of a tunnel that goes on, {why['hidden']} lie behind a nearer tube)",
                round(max(val), 3) if val else 0.0, P["xray_portal_px"], bad)
    allv = [abs(r["end_px"]) for r in ends if r["end_px"] is not None]
    rep.info("X6b", "every portal end, drawn by layer 4 or not: the tube's end against the portal face's place (px): the worst, "
             "ends seen", {"worst": round(max(allv), 3) if allv else None, "seen": len(allv), "of": len(ends)})
    # ---------------------------------------------------------------- X7
    if casemates and is_case.any():
        case_s = is_case[M["tube"]]
        line_score(case_s, "casemate galleries", "X7a")
        depth_score(case_s, "casemate galleries", "X7b")
        ids = {t["id"] for t in tubes}
        missing = [g["id"] for g in casemates["galleries"] if f"casemate/{g['id']}" not in ids]
        rock = {g["id"]: T.rock_over(g, mnt.sample) for g in casemates["galleries"]}
        low = min(rock, key=rock.get)
        rep.at_most("X7c", f"casemate galleries of the data that are not in the release (of {len(casemates['galleries'])})",
                    len(missing), 0, missing)
        rep.at_least("X7d", f"least rock over a casemate gallery's top (m; over its whole width, every 0.25 m; the least is at {low})",
                     round(rock[low], 3), P["casemate_min_rock_m"])
        rep.at_most("X7e", f"casemate pixels drawn with the view off, or with ?off=casemates ({R['casemates']['on_px']} with the view on)",
                    R["casemates"]["view_off_px"] + R["casemates"]["switched_off_px"] + (0 if R["casemates"]["on_px"] else 1), 0)
    # ---------------------------------------------------------------- X8
    Sp = R["speed"]
    rep.info("X8", "speed (desktop, this machine's GPU, in tunnel view with vehicles moving)", Sp)
    rep.at_most("X8a", f"turning the view on or off: frames until it is drawn (the most of {len(Sp['toggle'])} turns; "
                f"{max(t['ms'] for t in Sp['toggle']):.1f} ms at most)", max(t["frames"] for t in Sp["toggle"]), P["xray_toggle_frames"])
    rep.at_least("X8b", "panning in tunnel view, desktop (frames per second, the whole area and 1:1)", round(Sp["pan_fps"], 1),
                 P["xray_pan_fps_desktop"])
    if not os.environ.get("V2_XRAY_KEEP"):                # the frames are large: only the fade's are kept (V2_XRAY_KEEP=1: all)
        for p in out.glob("*.rgb.z"):
            if not p.name.startswith("fade_"):
                p.unlink()
    rep.info("X9", "seconds", round(time.time() - t_start, 1))
    return rep.result()

