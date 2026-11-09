"""3D geometry the code layers draw, built once per scene from the scene's data (never from pixels).

Meshes are (V, 3) vertices in world metres (E, N, z) plus (T, 3) triangles and per-triangle attributes:
  group   a surface id (outlines are drawn where it changes)
  cls     object class (common.CLASS)
  obj     object id (building index, graph edge index, viaduct index, ...)
  colour  palette key "group.name", or a blend "a.b|c.d|t"

buildings_mesh      ACT LoD2 surfaces (roofs, walls, installations), surfaces grouped by plane for the outlines
openings_mesh       windows, doors and shop fronts of the facade layout as quads 5 cm in front of their walls
deck_mesh           the top of every bridge deck of the transport graph (layer 4 draws it)
structures_mesh     deck sides, undersides and parapets of every bridge; the modelled viaducts' slab, arches and
                    piers; the Pfaffenthal lift (layer 6)
portal_mesh         the dark mouth of every tunnel portal (layer 4)
wall_mesh           OSM retaining and city walls as vertical faces between their measured foot and top (layer 2)
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from v2.layers.common import CLASS


class Mesh:
    def __init__(self):
        self.V, self.T, self.group, self.cls, self.obj, self.col = [], [], [], [], [], []
        self.nv = 0
        self.ngroup = 0

    def new_group(self):
        self.ngroup += 1
        return self.ngroup - 1

    def add(self, verts, tris, cls, obj, col, group=None):
        verts = np.asarray(verts, float).reshape(-1, 3)
        tris = np.asarray(tris, np.int64).reshape(-1, 3)
        if group is None:
            group = self.new_group()
        self.V.append(verts)
        self.T.append(tris + self.nv)
        n = len(tris)
        self.group.append(np.full(n, group, np.int64))
        self.cls.append(np.full(n, cls, np.int16))
        self.obj.append(np.full(n, obj, np.int64))
        self.col.extend([col] * n)
        self.nv += len(verts)
        return group

    def quad(self, a, b, c, d, cls, obj, col, group=None):
        return self.add([a, b, c, d], [[0, 1, 2], [0, 2, 3]], cls, obj, col, group)

    def done(self):
        if not self.V:
            return {"V": np.zeros((0, 3)), "T": np.zeros((0, 3), np.int64), "group": np.zeros(0, np.int64),
                    "cls": np.zeros(0, np.int16), "obj": np.zeros(0, np.int64), "col": np.zeros(0, np.int64),
                    "col_keys": []}
        keys = sorted(set(self.col))
        ki = {k: i for i, k in enumerate(keys)}
        return {"V": np.concatenate(self.V), "T": np.concatenate(self.T), "group": np.concatenate(self.group),
                "cls": np.concatenate(self.cls), "obj": np.concatenate(self.obj),
                "col": np.array([ki[c] for c in self.col], np.int64), "col_keys": keys}


def tri_normals(V, T):
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.cross(b - a, c - a)
    L = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(L, 1e-12), L[:, 0] / 2


def h01(s: str) -> float:
    return int(hashlib.blake2s(s.encode(), digest_size=4).hexdigest(), 16) / 0xFFFFFFFF


# ------------------------------------------------------------------------------------------------ buildings
def plane_groups(V, T, tbld, ang_deg=2.0):
    """Surface ids: triangles of one building that share an edge and a plane (normals within ang_deg)."""
    n, _ = tri_normals(V, T)
    parent = np.arange(len(T))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    # edges keyed by rounded vertex positions (surfaces are triangulated separately, so vertices are not shared)
    q = np.round(V * 100).astype(np.int64)
    key = {}
    cos = math.cos(math.radians(ang_deg))
    for t in range(len(T)):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            pa, pb = tuple(q[T[t, a]]), tuple(q[T[t, b]])
            k = (pa, pb) if pa < pb else (pb, pa)
            o = key.get(k)
            if o is None:
                key[k] = t
            elif tbld[o] == tbld[t] and abs(float(n[o] @ n[t])) >= cos:
                ra, rb = find(o), find(t)
                if ra != rb:
                    parent[rb] = ra
    roots = np.array([find(t) for t in range(len(T))])
    _, g = np.unique(roots, return_inverse=True)
    return g


def buildings_mesh(scene):
    m = scene.mesh
    oe, on = (float(x) for x in m["origin_en"])
    V = m["verts"].astype(float) + np.array([oe, on, 0.0])
    keep = m["tri_kind"] != 0                                     # ground surfaces are never seen
    T = m["tris"][keep].astype(np.int64)
    kind = m["tri_kind"][keep]
    bld = m["tri_bld"][keep].astype(np.int64)
    groups = plane_groups(V, T, bld)
    B = scene.buildings
    cols = []
    for k, b in zip(kind, bld):
        info = B[b]
        bid = info["id"]
        if k == 2:
            cols.append("buildings.wall_stone" if h01(bid + "w") < 0.3 else "buildings.wall_render")
        else:
            shape = info.get("roof_shape", "")
            if shape == "flat" or k == 3 and shape == "flat":
                cols.append("buildings.roof_slate|ink.paper|0.55")
            elif h01(bid + "r") < 0.2:
                cols.append("buildings.roof_tile")
            else:
                cols.append("buildings.roof_slate")
    keys = sorted(set(cols))
    ki = {c: i for i, c in enumerate(keys)}
    cls = np.where(kind == 2, CLASS["building"], CLASS["building"]).astype(np.int16)
    return {"V": V, "T": T, "group": groups, "cls": cls, "obj": bld, "col": np.array([ki[c] for c in cols]),
            "col_keys": keys, "kind": kind}


def openings_mesh(scene, offset=0.05):
    """Windows, doors and shop fronts as quads just in front of their walls (straight by construction)."""
    from v2.data.scene.facades import window_world
    bidx = {b["id"]: i for i, b in enumerate(scene.buildings)}
    M = Mesh()
    for w in scene.facades["walls"]:
        bi = bidx.get(w["building"])
        if bi is None:
            continue
        nx, ny = w["normal"]
        off = np.array([nx * offset, ny * offset, 0.0])
        for kind, rects, col in (("window", w["windows"], "buildings.window"),
                                 ("door", w["doors"], "buildings.window|trees.trunk|0.6"),
                                 ("shopfront", w["shopfronts"], "buildings.window|ink.paper|0.25")):
            for r in rects:
                c = np.array(window_world(w, [float(x) for x in r[:4]])) + off
                M.quad(c[0], c[1], c[2], c[3], CLASS[kind], bi, col)
    return M.done()


# ------------------------------------------------------------------------------------------------ transport
def edge_frame(en):
    """Unit tangents and left normals at every sample of a polyline (averaged at the joins)."""
    d = np.diff(en, axis=0)
    L = np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    d = d / L
    t = np.vstack([d[:1], (d[:-1] + d[1:]) / 2, d[-1:]])
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    left = np.column_stack([-t[:, 1], t[:, 0]])
    return t, left


def ribbon(en, z, w):
    """Left and right edges of a ribbon of width w along a 3D polyline."""
    _, left = edge_frame(en)
    L = np.column_stack([en + left * w / 2, z])
    R = np.column_stack([en - left * w / 2, z])
    return L, R


def strip(M, A, B, cls, obj, col, group=None):
    """Quads between two polylines of equal length."""
    n = len(A)
    V = np.vstack([A, B])
    tris = []
    for i in range(n - 1):
        tris += [[i, i + 1, n + i + 1], [i, n + i + 1, n + i]]
    return M.add(V, tris, cls, obj, col, group)


def vehicle_mode(e):
    return e["mode"] in ("road", "rail", "tram", "funicular")


def on_deck(e) -> bool:
    """Drawn as a deck at its profile (layer 4 rule 1), not on the terrain: bridges, and approaches the profile
    holds on a structure above the ground (median more than 1 m over the terrain: the surface model sees a deck past
    the OSM bridge tag, transport-graph.md rule 0)."""
    if e["structure"] == "bridge":
        return True
    if e["structure"] != "ground" or not e.get("ground"):
        return False
    z, g = np.array(e["z"], float), np.array(e["ground"], float)
    ok = np.isfinite(g)
    return bool(ok.any() and np.median(z[ok] - g[ok]) > 1.0)


def deck_mesh(scene, edge_ok=lambda e: True):
    """The top of every bridge deck (the road, path or track surface on it)."""
    M = Mesh()
    for i, e in enumerate(scene.graph["edges"]):
        if not on_deck(e) or not edge_ok(e):
            continue
        en = np.array(e["en"], float)
        z = np.array(e["z"], float)
        if len(en) < 2:
            continue
        w = float(e["width"])
        L, R = ribbon(en, z, w)
        strip(M, L, R, CLASS["deck"], i, "transport.road")
    return M.done()


def portal_mesh(scene, edge_ok=lambda e: True):
    """A dark arch face where each tunnel leaves the open: at the tunnel's end node, across the way, facing out."""
    g = scene.graph
    nodes = {n["id"]: n for n in g["nodes"]}
    by_node = {}
    for i, e in enumerate(g["edges"]):
        for end in ("a", "b"):
            by_node.setdefault(int(e[end]), []).append((i, end))
    M = Mesh()
    for i, e in enumerate(g["edges"]):
        if e["structure"] != "tunnel" or not edge_ok(e) or e["mode"] in ("path", "steps") and float(e["width"]) < 1.5:
            continue
        en = np.array(e["en"], float)
        z = np.array(e["z"], float)
        for end in ("a", "b"):
            nid = int(e[end])
            others = [g["edges"][j] for j, _ in by_node.get(nid, []) if j != i]
            if not others or all(o["structure"] == "tunnel" for o in others):
                continue
            if end == "a":
                p, q, zz = en[0], en[min(1, len(en) - 1)], z[0]
            else:
                p, q, zz = en[-1], en[max(len(en) - 2, 0)], z[-1]
            d = p - q
            Ld = np.linalg.norm(d)
            if Ld < 1e-6:
                continue
            out = d / Ld                                  # pointing out of the tunnel
            left = np.array([-out[1], out[0]])
            w = float(e["width"]) + 1.0
            h = float(e.get("clearance_m", 4.5))
            ring = 24
            # an arch: a rectangle w x (h - w/2) topped by a half disc, as a fan from the base centre
            pts = [(-w / 2, 0.0)]
            sh = max(h - w / 2, 0.5)
            pts.append((-w / 2, sh))
            for k in range(ring + 1):
                a = math.pi - math.pi * k / ring
                pts.append((w / 2 * math.cos(a), sh + w / 2 * math.sin(a)))
            pts.append((w / 2, 0.0))
            base = np.array([p[0], p[1], zz]) + np.array([out[0], out[1], 0]) * 0.3
            V = [base + np.array([left[0] * s, left[1] * s, t]) for s, t in pts]
            c = np.array([p[0], p[1], zz + sh / 2]) + np.array([out[0], out[1], 0]) * 0.3
            V = [c] + V
            tris = [[0, k, k + 1] for k in range(1, len(V) - 1)]
            M.add(V, tris, CLASS["portal"], i, "ink.line")
    return M.done()


# ------------------------------------------------------------------------------------------------ structures
def box(M, c, ax, w, l, z0, z1, cls, obj, col):
    """A box centred on plan point c, its length l along unit ax and width w across, from z0 to z1."""
    ax = np.asarray(ax, float) / np.linalg.norm(ax)
    lf = np.array([-ax[1], ax[0]])
    pts = [c + ax * l / 2 + lf * w / 2, c - ax * l / 2 + lf * w / 2, c - ax * l / 2 - lf * w / 2, c + ax * l / 2 - lf * w / 2]
    lo = [np.r_[p, z0] for p in pts]
    hi = [np.r_[p, z1] for p in pts]
    g = M.new_group()
    M.quad(hi[0], hi[1], hi[2], hi[3], cls, obj, col, g)
    for k in range(4):
        M.quad(lo[k], lo[(k + 1) % 4], hi[(k + 1) % 4], hi[k], cls, obj, col)


def structures_mesh(scene, edge_ok=lambda e: True, thickness=1.0, parapet=1.0):
    import shapely
    st = scene.structures
    M = Mesh()
    poly = scene.polygon
    via_edges = {e for v in st["viaducts"] for e in v.get("deck_edges", [])}
    g = scene.graph
    for i, e in enumerate(g["edges"]):
        if e["structure"] != "bridge" or not edge_ok(e) or e["id"] in via_edges:
            continue
        en = np.array(e["en"], float)
        z = np.array(e["z"], float)
        if len(en) < 2 or not shapely.contains_xy(poly, *en[len(en) // 2]):
            continue
        w = float(e["width"])
        red = "Grande-Duchesse Charlotte" in (e.get("bridge_name") or "") or "Pont Rouge" in (e.get("bridge_name") or "")
        col = "structures.red_bridge" if red else "structures.stone"
        L, R = ribbon(en, z, w)
        Lb, Rb = L.copy(), R.copy()
        Lb[:, 2] -= thickness
        Rb[:, 2] -= thickness
        strip(M, L, Lb, CLASS["structure"], i, col)
        strip(M, R, Rb, CLASS["structure"], i, col)
        strip(M, Lb, Rb, CLASS["structure"], i, col)
        Lp, Rp = L.copy(), R.copy()
        Lp[:, 2] += parapet
        Rp[:, 2] += parapet
        rail = "structures.railing" if vehicle_mode(e) or red else "structures.stone"
        strip(M, L, Lp, CLASS["parapet"], i, rail)
        strip(M, R, Rp, CLASS["parapet"], i, rail)
    for vi, v in enumerate(st["viaducts"]):
        if v.get("status") != "ok" or not v.get("deck"):
            continue
        deck = np.array(v["deck"], float)
        en, zt = deck[:, :2], deck[:, 2] - 0.15             # slab top just under the tracks (layer 4 draws them)
        w = float(v["width_m"])
        th = float(v.get("deck_thickness_m", 1.6))
        pa = float(v.get("parapet_m", 1.1))
        L, R = ribbon(en, zt, w)
        Lb, Rb = L.copy(), R.copy()
        Lb[:, 2] -= th
        Rb[:, 2] -= th
        strip(M, L, R, CLASS["structure"], vi, "structures.stone|transport.sleeper|0.3")
        strip(M, L, Lb, CLASS["structure"], vi, "structures.stone")
        strip(M, R, Rb, CLASS["structure"], vi, "structures.stone")
        Lp, Rp = L.copy(), R.copy()
        Lp[:, 2] += pa
        Rp[:, 2] += pa
        strip(M, L, Lp, CLASS["parapet"], vi, "structures.stone")
        strip(M, R, Rp, CLASS["parapet"], vi, "structures.stone")
        # arches: on both faces, the spandrel between the slab's underside and the arch's curve, and the barrel
        cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
        _, left = edge_frame(en)
        for a in v.get("arches", []):
            t0, t1 = a["t"]
            if t1 - t0 < 1:
                continue
            ts = np.linspace(t0, t1, 33)
            P = np.column_stack([np.interp(ts, cum, en[:, 0]), np.interp(ts, cum, en[:, 1])])
            lf = np.column_stack([np.interp(ts, cum, left[:, 0]), np.interp(ts, cum, left[:, 1])])
            lf /= np.linalg.norm(lf, axis=1, keepdims=True)
            top = np.interp(ts, cum, zt) - th
            mid, rad = (t0 + t1) / 2, (t1 - t0) / 2
            curve = a["spring_z"] + np.sqrt(np.maximum(rad ** 2 - (ts - mid) ** 2, 0))
            curve = np.minimum(curve, top - 0.3)
            for s in (1, -1):
                side = P + lf * (w / 2) * s
                A = np.column_stack([side, top])
                B = np.column_stack([side, curve])
                strip(M, A, B, CLASS["arch"], vi, "structures.stone")
            A = np.column_stack([P + lf * w / 2, curve])
            B = np.column_stack([P - lf * w / 2, curve])
            strip(M, A, B, CLASS["arch"], vi, "structures.stone|ink.line|0.25")
        for p in v.get("piers", []):
            c = np.array([p["e"], p["n"]])
            k = int(np.argmin(np.linalg.norm(en - c, axis=1)))
            ax = en[min(k + 1, len(en) - 1)] - en[max(k - 1, 0)]
            box(M, c, ax, w, float(p.get("thickness_m", 3.0)), float(p["foot_z"]), float(p["deck_z"]) - th,
                CLASS["pier"], vi, "structures.stone")
    for i, e in enumerate(g["edges"]):
        if e["mode"] != "elevator" or not edge_ok(e):
            continue
        en = np.array(e["en"], float)
        z = np.array(e["z"], float)
        c = en.mean(0)
        ax = en[-1] - en[0] if np.linalg.norm(en[-1] - en[0]) > 0.5 else np.array([1.0, 0.0])
        box(M, c, ax, 4.0, 4.0, float(z.min()) - 0.5, float(z.max()) + 3.0, CLASS["lift"], i,
            "structures.railing|ink.line|0.35")
    return M.done()


def wall_tops(w, P, top, ground=None):
    """A wall's top along its line: the measured top (1.5 m either side), never under the terrain at the line."""
    if ground is None:
        return top
    g = ground(P[:, 0], P[:, 1])
    return np.where(np.isfinite(g), np.maximum(top, g), top)


def wall_mesh(scene, min_drop=1.5, top_width=0.4, poly=None, ground=None):
    """OSM walls (retaining, city walls, cliffs, embankments) with a measured drop: vertical faces foot to top,
    and a flat top band (the ink edge)."""
    import shapely
    M = Mesh()
    for wi, w in enumerate(scene.walls):
        en = np.array(w["en"], float)
        top = np.array([np.nan if v is None else v for v in w.get("top_m", [])], float)
        foot = np.array([np.nan if v is None else v for v in w.get("foot_m", [])], float)
        if len(en) < 2 or len(top) < 2 or len(top) != len(foot) or (w.get("drop_m") or 0) < min_drop:
            continue
        if not (np.isfinite(top) & np.isfinite(foot)).any():
            continue
        seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
        L = float(seg[-1])
        s = np.minimum(np.arange(len(top)) * 5.0 * L / max(int(L), 1), L)   # terrain.py samples every 5 m
        if s[-1] < L - 0.5:                                                    # and the end of the wall
            s = np.r_[s, L]; top = np.r_[top, top[-1]]; foot = np.r_[foot, foot[-1]]
        sd = np.r_[np.arange(0, L, 0.5), L]                 # every half metre, as drawn
        top = np.interp(sd, s, np.where(np.isfinite(top), top, np.nanmedian(top)))
        foot = np.interp(sd, s, np.where(np.isfinite(foot), foot, np.nanmedian(foot)))
        s = sd
        P = np.column_stack([np.interp(s, seg, en[:, 0]), np.interp(s, seg, en[:, 1])])
        if poly is not None and not shapely.contains_xy(poly, P[:, 0], P[:, 1]).any():
            continue
        ok = np.isfinite(top) & np.isfinite(foot)
        if len(top) >= 3:                                   # smooth the measurements' noise over ~5 m
            from scipy.ndimage import median_filter, uniform_filter1d
            top = uniform_filter1d(median_filter(top, 11, mode="nearest"), 11, mode="nearest")
            foot = uniform_filter1d(median_filter(foot, 11, mode="nearest"), 11, mode="nearest")
            ok = np.ones(len(top), bool)
        top = np.where(ok, top, np.nanmedian(top))
        foot = np.where(ok, foot, np.nanmedian(foot))
        foot = np.minimum(foot, top - 0.2)
        top = wall_tops(w, P, top, ground)
        inside = shapely.contains_xy(poly, P[:, 0], P[:, 1]) if poly is not None else np.ones(len(P), bool)
        # the stretches inside the area only
        k = 0
        while k < len(P):
            if not inside[k]:
                k += 1
                continue
            j = k
            while j + 1 < len(P) and inside[j + 1]:
                j += 1
            if j > k:
                sl = slice(k, j + 1)
                A = np.column_stack([P[sl], top[sl] + 0.05])
                B = np.column_stack([P[sl], foot[sl] - 0.3])
                strip(M, A, B, CLASS["wall"], wi, "structures.stone|relief.rock|0.5")
                L, R = ribbon(P[sl], top[sl] + 0.06, top_width)
                strip(M, L, R, CLASS["wall"], wi, "ink.line")
            k = j + 1
    return M.done()
