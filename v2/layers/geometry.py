"""3D geometry the code layers draw, built once per scene from the scene's data (never from pixels).

Meshes are (V, 3) vertices in world metres (E, N, z) plus (T, 3) triangles and per-triangle attributes:
  group   a surface id (outlines are drawn where it changes)
  cls     object class (common.CLASS)
  obj     object id (building index, graph edge index, viaduct index, ...)
  colour  palette key "group.name", or a blend "a.b|c.d|t"

buildings_mesh      ACT LoD2 surfaces (roofs, walls, installations), surfaces grouped by plane for the outlines
wall_skirts         a building's walls continued down to the ground where its base stands over the ground
openings_mesh       windows, doors and shop fronts of the facade layout as quads 5 cm in front of their walls
deck_mesh           the top of every bridge deck of the transport graph (layer 4 draws it)
supports_mesh       the arches and piers under the bridges without a model, the Red Bridge's girder and legs
structures_mesh     deck sides, undersides and parapets of every bridge; the modelled viaducts' slab, arches and
                    piers; the Pfaffenthal lift (layer 6)
portal_mesh         the dark mouth of every tunnel portal (layer 4)
wall_mesh           OSM retaining and city walls as vertical faces between their measured foot and top (layer 2)
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from v2.layers.common import CLASS, VIEW


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


def wall_skirts(buildings, ground, p):
    """Walls continued down to the ground (params buildings.skirt). ACT's walls end at the model's own ground
    surface, one height per building; where the LiDAR ground at the outline lies lower, the building would stand in
    the air. For every outline edge whose ground is more than min_gap_m under the building's base, one vertical
    face from the base down to below_m under the lowest ground along that edge, facing out. `ground(e, n)` gives
    the terrain's height. Returns (verts (n, 3), tris (m, 3), building index per triangle, gaps): gaps is, per
    building, how far its base stands over the lowest ground at its outline (m, 0 if it does not)."""
    from shapely.geometry import Polygon
    from shapely.geometry.polygon import orient
    V, T, TB = [], [], []
    gaps = np.zeros(len(buildings))
    nv = 0
    for bi, b in enumerate(buildings):
        top = float(b["ground_z"])
        for part in b["footprint"]:
            poly = orient(Polygon(part[0], part[1:]), 1.0)        # outside on the right of every ring's direction
            for ring in [poly.exterior, *poly.interiors]:
                c = np.asarray(ring.coords)[:, :2]
                for a, d in zip(c[:-1], c[1:]):
                    L = float(np.hypot(*(d - a)))
                    if L < 0.05:
                        continue
                    t = np.linspace(0, 1, max(2, int(math.ceil(L / p["sample_m"])) + 1))[:, None]
                    on = a + (d - a) * t
                    out = on + np.array([d[1] - a[1], a[0] - d[0]]) / L * p["outside_m"]
                    low = float(min(ground(on[:, 0], on[:, 1]).min(), ground(out[:, 0], out[:, 1]).min()))
                    gaps[bi] = max(gaps[bi], top - low)
                    if top - low <= p["min_gap_m"]:
                        continue
                    z = low - p["below_m"]
                    V += [[a[0], a[1], z], [d[0], d[1], z], [d[0], d[1], top], [a[0], a[1], top]]
                    T += [[nv, nv + 1, nv + 2], [nv, nv + 2, nv + 3]]
                    TB += [bi, bi]
                    nv += 4
    return (np.array(V, float).reshape(-1, 3), np.array(T, np.int64).reshape(-1, 3), np.array(TB, np.int64),
            np.maximum(gaps, 0.0))


def scene_skirts(scene):
    """wall_skirts for a scene, on its LiDAR terrain."""
    from v2.config import params
    from v2.layers.raster import HeightField
    t = scene.terrain
    hf = HeightField(t["mnt"], float(t["e0"]), float(t["n0"]), float(t["step"]))
    return wall_skirts(scene.buildings, hf.sample, params()["buildings"]["skirt"])


def buildings_mesh(scene):
    m = scene.mesh
    oe, on = (float(x) for x in m["origin_en"])
    V = m["verts"].astype(float) + np.array([oe, on, 0.0])
    keep = m["tri_kind"] != 0                                     # ground surfaces are never seen
    T = m["tris"][keep].astype(np.int64)
    kind = m["tri_kind"][keep]
    bld = m["tri_bld"][keep].astype(np.int64)
    sv, st, sb, _ = scene_skirts(scene)                           # walls continued down to the ground
    if len(st):
        T = np.vstack([T, st + len(V)])
        V = np.vstack([V, sv])
        kind = np.r_[kind, np.full(len(st), 2, kind.dtype)]
        bld = np.r_[bld, sb]
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
    # walls, roofs and parts (dormers, chimneys) are told apart in the ids: they are different materials
    cls = np.select([kind == 1, kind == 3], [CLASS["roof"], CLASS["part"]], CLASS["building"]).astype(np.int16)
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


DECK_CORE_M = 1.0      # a way whose profile stands this far over the terrain is on a structure (Phase 1's rule)
DECK_EDGE_M = 0.1      # ... and the structure runs on until the profile is back within this of the terrain


def deck_mask(e, terrain, abutment=(False, False)) -> np.ndarray:
    """Per sample of an edge: drawn at its profile as a deck (True) or on the terrain (False) (layer 4 rule 1).

    Bridges are decks all along. A ground way is a deck on every stretch where its profile stands more than
    DECK_CORE_M over the terrain, grown along the way while it stays more than DECK_EDGE_M over it: so an approach
    the terrain model has cut away (ACT cuts bridges out past OSM's bridge tag; transport-graph.md rule 0) is drawn
    at the road's level and meets the terrain where the road does, with no gap or step at the abutment.
    A ground way leaving a bridge (`abutment`: its first / last node is a bridge's end) also stays at its profile
    from that end while it is more than DECK_EDGE_M over the terrain, so the bridge's deck never ends in a step.
    `terrain(e, n)` is the drawn terrain's height (the renderer's height field)."""
    n = len(e["en"])
    if e["structure"] == "bridge":
        return np.ones(n, bool)
    if e["structure"] != "ground" or n < 2:
        return np.zeros(n, bool)
    en = np.array(e["en"], float)
    d = np.array(e["z"], float) - terrain(en[:, 0], en[:, 1])
    d = np.where(np.isfinite(d), d, 0.0)
    over = d > DECK_EDGE_M
    seed = d > DECK_CORE_M
    seed[0] |= bool(abutment[0])
    seed[-1] |= bool(abutment[1])
    seed &= over
    if not seed.any():
        return np.zeros(n, bool)
    from scipy import ndimage
    lab, k = ndimage.label(over)
    keep = np.unique(lab[seed])
    return np.isin(lab, keep[keep > 0])


def runs(mask):
    """(first, last) sample indices of each run of True."""
    m = np.r_[False, np.asarray(mask, bool), False].astype(np.int8)
    a = np.flatnonzero(np.diff(m) == 1)
    b = np.flatnonzero(np.diff(m) == -1) - 1
    return list(zip(a.tolist(), b.tolist()))


def pieces(mask):
    """The edge cut into (deck, i0, i1) pieces of samples i0..i1; neighbouring pieces share their end sample, so
    the drawn surfaces meet (the deck's end is within DECK_EDGE_M of the terrain there)."""
    n = len(mask)
    if n < 2:
        return []
    out, i = [], 0
    while i < n - 1:
        v = bool(mask[i]) or bool(mask[i + 1])
        j = i + 1
        while j < n - 1 and (bool(mask[j]) or bool(mask[j + 1])) == v:
            j += 1
        out.append((v, i, j))
        i = j
    return out


def densify(e, step=0.5):
    """The edge with its polyline, profile and distances resampled every `step` m (and at its own samples' ends), so
    deck and terrain pieces are cut within half a metre of where the profile leaves the terrain."""
    en = np.array(e["en"], float)
    if len(en) < 2:
        return e
    s0 = np.array(e["s"], float) if e.get("s") is not None and len(e["s"]) == len(en) else \
        np.r_[0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
    L = float(s0[-1])
    n = max(int(math.ceil(L / step)), 1)
    s = np.linspace(0, L, n + 1)
    out = dict(e)
    out["en"] = np.column_stack([np.interp(s, s0, en[:, 0]), np.interp(s, s0, en[:, 1])])
    out["z"] = np.interp(s, s0, np.array(e["z"], float))
    out["s"] = s
    return out


def deck_at(e, mask, s) -> np.ndarray:
    """Whether the points at distances s along the edge are drawn on its deck pieces (as pieces())."""
    s0 = np.asarray(e["s"], float)
    mask = np.asarray(mask, bool)
    if len(s0) < 2:
        return np.zeros(np.shape(s), bool)
    k = np.clip(np.searchsorted(s0, s, side="right") - 1, 0, len(s0) - 2)
    return mask[k] | mask[k + 1]


def on_deck(e) -> bool:
    """A bridge (decks of raised approaches are per stretch: deck_mask)."""
    return e["structure"] == "bridge"


def deck_mesh(scene, edge_ok=lambda e: True, masks=None, edges=None):
    """The top of every bridge deck and raised approach (the road, path or track surface on it). `edges` (the graph's,
    densified as the masks were) default to the graph's own."""
    M = Mesh()
    for i, e in enumerate(edges if edges is not None else scene.graph["edges"]):
        if not edge_ok(e) or len(e["en"]) < 2:
            continue
        mask = masks[i] if masks is not None else np.full(len(e["en"]), on_deck(e))
        en = np.array(e["en"], float)
        z = np.array(e["z"], float)
        w = float(e["width"])
        for deck, i0, i1 in pieces(mask):
            if not deck:
                continue
            L, R = ribbon(en[i0:i1 + 1], z[i0:i1 + 1], w)
            strip(M, L, R, CLASS["deck"], i, "transport.road")
    return M.done()


def portal_mesh(scene, edge_ok=lambda e: True, ceiling=None):
    """A dark arch face where each tunnel leaves the open: at the tunnel's end node, across the way, facing out.
    `ceiling(e, n, z, r)`, if given, is the lowest underside of a deck within r m above z: a portal under a bridge
    is cut to it (its arch never rises through the deck over it)."""
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
            if out[0] * VIEW[0] + out[1] * VIEW[1] > 0:
                continue                                  # a mouth facing away from the camera is never seen
            left = np.array([-out[1], out[0]])
            w = float(e["width"]) + 1.0
            h = float(e.get("clearance_m", 4.5))
            if ceiling is not None:
                h = min(h, max(float(ceiling(p[0], p[1], zz, w / 2 + 1.0)) - zz, 1.0))
            ring = 24
            # an arch: a rectangle w x (h - w/2) topped by a half ellipse (a half disc when there is room), as a fan
            # from the base centre
            pts = [(-w / 2, 0.0)]
            sh = max(h - w / 2, 0.5)
            ry = max(min(w / 2, h - sh), 0.2)
            pts.append((-w / 2, sh))
            for k in range(ring + 1):
                a = math.pi - math.pi * k / ring
                pts.append((w / 2 * math.cos(a), sh + ry * math.sin(a)))
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


PARAPET_M = 0.5           # thickness of a viaduct's stone parapet


def supports_mesh(M, st, by_id, edge_ok=lambda e: True):
    """What stands under the bridges without a model of their own (scene structures "supports" and "frames";
    v2/data/structures/bridges.json): rows of stone arches on piers, and the Red Bridge's girder and slanted legs."""
    for b in st.get("supports", []):
        if b["spine"] not in by_id or not all(edge_ok(by_id[i][1]) for i in b["edges"] if i in by_id):
            continue
        obj = by_id[b["spine"]][0]
        ln = np.array(b["line"], float)
        P, under, ground = ln[:, :2], ln[:, 2], ln[:, 3]
        ts = np.linspace(0, b["length_m"], len(P))
        _, left = edge_frame(P)
        w, col = b["width_m"], "structures.stone"
        at = lambda A, t: np.column_stack([np.interp(t, ts, A[:, k]) for k in range(A.shape[1])])      # noqa: E731
        for a in b["arches"]:
            t0, t1 = a["t"]
            tt = np.linspace(t0, t1, 33)
            Q, lf = at(P, tt), at(left, tt)
            lf /= np.linalg.norm(lf, axis=1, keepdims=True)
            top = np.interp(tt, ts, under)
            x = np.clip((tt - (t0 + t1) / 2) / ((t1 - t0) / 2), -1, 1)
            curve = top - b["crown_m"] - a["rise_m"] * (1 - np.sqrt(1 - x ** 2))
            for s in (1, -1):                                  # the spandrel on both faces, then the barrel
                side = Q + lf * (w / 2) * s
                strip(M, np.column_stack([side, top]), np.column_stack([side, curve]), CLASS["arch"], obj, col)
            strip(M, np.column_stack([Q + lf * w / 2, curve]), np.column_stack([Q - lf * w / 2, curve]), CLASS["arch"],
                  obj, col + "|ink.line|0.25")
        for p in b["piers"]:
            t0, t1 = p["t"]
            c = (t0 + t1) / 2
            ax = at(P, np.array([c + 0.5]))[0] - at(P, np.array([c - 0.5]))[0]
            box(M, at(P, np.array([c]))[0], ax, w, t1 - t0, p["foot_z"] - 0.4, float(np.interp(c, ts, under)),
                CLASS["pier"], obj, col)
        for i0, i1 in b["walls"]:                              # a low deck: its sides go down to the ground
            for s in (1, -1):
                side = P[i0:i1 + 1] + left[i0:i1 + 1] * (w / 2) * s
                A = np.column_stack([side, under[i0:i1 + 1]])
                B = np.column_stack([side, np.minimum(ground[i0:i1 + 1], under[i0:i1 + 1]) - 0.3])
                strip(M, A, B, CLASS["structure"], obj, col)
    for f in st.get("frames", []):
        ids = [i for i in f["edges"] if i in by_id]
        if not ids or not all(edge_ok(by_id[i][1]) for i in ids):
            continue
        obj, col = by_id[ids[0]][0], f["colour"]
        u = np.array(f["axis"], float)
        v = np.array([-u[1], u[0]])
        G_ = np.array(f["girder"]["line"], float)
        gw = f["girder"]["width_m"]
        A, B = G_[:, :2] + v * gw / 2, G_[:, :2] - v * gw / 2
        for S in (A, B):
            strip(M, np.column_stack([S, G_[:, 2]]), np.column_stack([S, G_[:, 3]]), CLASS["structure"], obj, col)
        strip(M, np.column_stack([A, G_[:, 3]]), np.column_stack([B, G_[:, 3]]), CLASS["structure"], obj, col + "|ink.line|0.3")
        for leg in f["legs"]:
            def ring(c, size, z):
                return [np.r_[np.array(c[:2]) + u * a * size[0] / 2 + v * b_ * size[1] / 2, z]
                        for a, b_ in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
            hi = ring(leg["top"], leg["top_m"], leg["top"][2] + 0.5)          # into the girder
            lo = ring(leg["foot"], leg["foot_m"], leg["foot"][2] - 0.5)       # into its footing
            for k in range(4):
                M.quad(lo[k], lo[(k + 1) % 4], hi[(k + 1) % 4], hi[k], CLASS["pier"], obj, col)
        for q in f["footings"]:
            la, lc, h = q["size_m"]
            box(M, np.array([q["e"], q["n"]]), u, lc, la, q["ground_z"] - 1.5, q["ground_z"] + h - 1.5, CLASS["pier"], obj,
                "structures.stone")


def structures_mesh(scene, edge_ok=lambda e: True, thickness=1.0, parapet=1.0, masks=None, terrain=None, dense=None,
                    on_face=None):
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
        # the Red Bridge: OSM names it on the way (name), not always on the bridge (bridge_name)
        names = (e.get("bridge_name") or "") + " " + (e.get("name") or "")
        red = "Grande-Duchesse Charlotte" in names or "Pont Rouge" in names
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
    # raised approaches (deck_mask on a ground way): the abutment's sides, from the deck's edges down into the terrain
    if masks is not None and terrain is not None:
        for i, e in enumerate(dense if dense is not None else g["edges"]):
            if e["structure"] != "ground" or not edge_ok(e) or not masks[i].any():
                continue
            en = np.array(e["en"], float)
            z = np.array(e["z"], float)
            w = float(e["width"])
            for deck, i0, i1 in pieces(masks[i]):
                if not deck or not shapely.contains_xy(poly, *en[(i0 + i1) // 2]):
                    continue
                L, R = ribbon(en[i0:i1 + 1], z[i0:i1 + 1], w)
                for A in (L, R):
                    B = A.copy()
                    B[:, 2] = np.minimum(terrain(A[:, 0], A[:, 1]), A[:, 2]) - 0.3
                    # not down a rock face (`on_face`): a way along a cliff's edge has the cliff under its side, and
                    # the cliff is drawn as rock, not as a sheet of masonry hanging from the way
                    keep = ~on_face(A[:, 0], A[:, 1]) if on_face is not None else np.ones(len(A), bool)
                    for ok, j0, j1 in pieces(keep):
                        if ok and j1 > j0:
                            strip(M, A[j0:j1 + 1], B[j0:j1 + 1], CLASS["structure"], i, "structures.stone")
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
        strip(M, L, R, CLASS["structure"], vi, "structures.ballast")         # the gravel bed the tracks lie in
        strip(M, L, Lb, CLASS["structure"], vi, "structures.stone")
        strip(M, R, Rb, CLASS["structure"], vi, "structures.stone")
        # parapets: solid stone, PARAPET_M thick, under a pale coping (the owner, 27 Nov 2026: "top surface of
        # bridges for train tracks seems wrong": the deck was one plain slab)
        for A, s in ((L, 1), (R, -1)):
            In, _ = ribbon(en, zt, s * (w - 2 * PARAPET_M))
            Ap, Ip = A.copy(), In.copy()
            Ap[:, 2] += pa
            Ip[:, 2] += pa
            strip(M, A, Ap, CLASS["parapet"], vi, "structures.stone")
            strip(M, In, Ip, CLASS["parapet"], vi, "structures.stone")
            strip(M, Ap, Ip, CLASS["parapet"], vi, "structures.coping")
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
    supports_mesh(M, st, {e["id"]: (i, e) for i, e in enumerate(g["edges"])}, edge_ok)
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


def wall_mesh(scene, min_drop=1.5, top_width=0.6, poly=None, ground=None, on_face=None):
    """OSM walls (retaining, city walls, cliffs, embankments) with a measured drop: vertical faces foot to top,
    and a flat top band (the ink edge). `on_face(e, n, step_m)` marks the samples along a wall that are part of a
    rock face: they are not built (layer-02-relief.md rule 2)."""
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
        if on_face is not None:
            inside &= ~on_face(P[:, 0], P[:, 1], 0.5)
        # the stretches inside the area only
        k = 0
        while k < len(P):
            if not inside[k]:
                k += 1
                continue
            j = k
            while j + 1 < len(P) and inside[j + 1]:
                j += 1
            if j > k or len(P) > 1:
                sl = slice(max(k - 1, 0), min(j + 2, len(P)))   # half a metre past the area's edge: no gap there
                A = np.column_stack([P[sl], top[sl] + 0.05])
                B = np.column_stack([P[sl], foot[sl] - 0.3])
                strip(M, A, B, CLASS["wall"], wi, "structures.stone|relief.rock|0.5")
                L, R = ribbon(P[sl], top[sl] + 0.06, top_width)
                strip(M, L, R, CLASS["wall"], wi, "ink.line")
            k = j + 1
    return M.done()
