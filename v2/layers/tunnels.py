"""Tunnel view (x-ray): the tubes the viewer draws under the faded city. Spec: v2/docs/specs/tunnel-view.md.

Everything here comes from the transport graph (rule 1): each tunnel edge is a box of the edge's width and clearance
on its height profile, from end to end. The Bock casemates are the same kind of record, from a hand model kept as
data (v2/data/structures/casemates.json).

tunnels.json   {"origin_en", "portal_face_m", "junction", "depth_cm": [lo, hi], "tubes": [...]}; one record per tube:
    id, edge   the graph edge (its id and its index in graph.json, the index vehicles.json uses); edge -1: a casemate
    kind       tunnel | indoor | passage | casemate;  mode, name, chain as in the graph
    w, h       width and clearance (m)
    p          the centre line of the floor: E, N relative to the camera origin, flat [e0, n0, e1, n1, ...] (m)
    z          floor height per point (m);  s: distance along the edge (m)
    c          depth of the floor under the surface per point (m): the graph's cover minus the profile
    d          distance into the tunnel from its nearest portal per point (m); portal_m: where a vehicle is first a
               full clearance under its cover (the graph's portal of the chain): past it, a vehicle is "in the tunnel"
    ends       per end: 0 joins another tube, 1 a portal (the tube runs on to the face layer 4 draws there), 2 closed
    nodes      the graph node at each end (-1: none): tubes with the same node join there

The mesh (the same rule here and in the viewer, v2/web/src/tunnels.ts): per segment the floor (two strips, either
side of the centre line, so the floor's height along it is the profile's whatever the corners do), and each wall and
closed end whose inside faces the camera. Nothing nearer is drawn, so what is in a tube is seen in it, and the tube's
drawn faces are also its depth: a vehicle in another tunnel behind it is hidden by them. Where tubes join at a node, a
wall is left out as far as it runs inside another of them (wall_trims): a junction is open, not walled across.
"""
from __future__ import annotations

import json
import math

import numpy as np

from v2.config import REPO
from v2.layers.common import VIEW, Scene, project_local

CASEMATES = REPO / "v2" / "data" / "structures" / "casemates.json"
FLOOR, WALL, CAP = 0, 1, 2
OPEN, PORTAL, CLOSED = 0, 1, 2


def cam_origin():
    from v2.config.camera import camera
    return tuple(camera()["origin_en"])


def r2(a):
    return [round(float(v), 2) for v in a]


# ------------------------------------------------------------------------------------------------ which edges
def depth_under_ground(e) -> np.ndarray:
    """Per sample, how far the floor of a non-tunnel edge lies under the ground (m)."""
    g = np.array([np.nan if v is None else v for v in e.get("ground") or []], float)
    z = np.array(e["z"], float)
    return g - z if len(g) == len(z) else np.full(len(z), np.nan)


def is_tube(e, share) -> bool:
    """A tunnel; or an indoor or passage edge that runs underground: on at least `share` of its samples the whole
    clearance is under the ground (most of them are at street level, under a building: those are not tunnels)."""
    if e["structure"] == "tunnel":
        return True
    if e["structure"] not in ("indoor", "passage") or len(e["en"]) < 2:
        return False
    d = depth_under_ground(e)
    return bool(np.isfinite(d).all() and (d >= float(e.get("clearance_m", 2.5))).mean() >= share)


def end_codes(graph, tubes: set) -> dict:
    """For each tube edge index: (code at its first node, code at its last node)."""
    by_node = {}
    for i, e in enumerate(graph["edges"]):
        for end in ("a", "b"):
            by_node.setdefault(int(e[end]), []).append(i)
    out = {}
    for i in tubes:
        e = graph["edges"][i]
        codes = []
        for end in ("a", "b"):
            others = [j for j in by_node[int(e[end])] if j != i]
            codes.append(CLOSED if not others else OPEN if all(j in tubes for j in others) else PORTAL)
        out[i] = tuple(codes)
    return out


def tube_records(graph, polygon, P, portal_default_m, origin=None) -> list:
    """One record per tube edge of the graph that touches the area."""
    import shapely
    oe, on = origin if origin is not None else cam_origin()
    edges = graph["edges"]
    tubes = {i for i, e in enumerate(edges) if len(e["en"]) >= 2 and is_tube(e, P["underground_share"])}
    codes = end_codes(graph, tubes)
    portal = {}
    for p in graph.get("portals", []):
        if p.get("found"):
            portal[str(p["chain"])] = max(portal.get(str(p["chain"]), 0.0), float(p["dist_m"]))
    out = []
    for i in sorted(tubes):
        e = edges[i]
        en = np.array(e["en"], float)
        if polygon is not None and not shapely.contains_xy(polygon, en[:, 0], en[:, 1]).any():
            continue
        z = np.array(e["z"], float)
        s = np.array(e["s"], float)
        if e["structure"] == "tunnel":
            cover = np.array(e["cover"], float) - z
            d = np.array(e["tunnel_d"], float)
        else:
            cover = depth_under_ground(e)
            d = np.minimum(s, s[-1] - s)
        out.append({"id": e["id"], "edge": i, "kind": e["structure"], "mode": e["mode"], "name": e.get("tunnel_name") or e.get("name") or "",
                    "chain": str(e.get("chain", "")), "w": float(e["width"]), "h": float(e.get("clearance_m", 2.5)),
                    "portal_m": portal.get(str(e.get("chain")), float(portal_default_m)),
                    "p": r2(np.column_stack([en[:, 0] - oe, en[:, 1] - on]).ravel()), "z": r2(z), "s": r2(s), "c": r2(cover),
                    "d": r2(d), "ends": list(codes[i]), "nodes": [int(e["a"]), int(e["b"])]})
    return out


# ------------------------------------------------------------------------------------------------ casemates
def resample(en, z, step):
    """A polyline and its heights with a point every `step` m at most on each of its segments (its own points kept)."""
    en, z = np.asarray(en, float), np.asarray(z, float)
    E, Z = [en[0]], [z[0]]
    for a, b, za, zb in zip(en[:-1], en[1:], z[:-1], z[1:]):
        n = max(int(math.ceil(float(np.linalg.norm(b - a)) / step - 1e-9)), 1)
        for k in range(1, n + 1):
            E.append(a + (b - a) * k / n)
            Z.append(za + (zb - za) * k / n)
    return np.array(E), np.array(Z)


def casemate_records(doc, terrain, sample_m, polygon=None, origin=None) -> list:
    """The galleries of casemates.json as tube records. `terrain(e, n)` is the scene's terrain height."""
    import shapely
    oe, on = origin if origin is not None else cam_origin()
    code = {"open": OPEN, "closed": CLOSED}
    out = []
    for g in doc.get("galleries", []):
        z0 = g["z"] if isinstance(g["z"], list) else [g["z"]] * len(g["en"])
        en, z = resample(g["en"], z0, sample_m)
        if polygon is not None and not shapely.contains_xy(polygon, en[:, 0], en[:, 1]).all():
            continue
        s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
        cover = np.asarray(terrain(en[:, 0], en[:, 1]), float) - z
        out.append({"id": f"casemate/{g['id']}", "edge": -1, "kind": "casemate", "mode": "path", "name": g.get("name", ""),
                    "chain": doc.get("id", "casemates"), "w": float(g["width_m"]), "h": float(g["height_m"]), "portal_m": 0.0,
                    "p": r2(np.column_stack([en[:, 0] - oe, en[:, 1] - on]).ravel()), "z": r2(z), "s": r2(s), "c": r2(cover),
                    "d": r2(np.minimum(s, s[-1] - s)), "ends": [code[v] for v in g.get("ends", ["closed", "closed"])],
                    "nodes": [-1, -1]})
    return out


def rock_over(g, terrain, step=0.25, across=5) -> float:
    """The least rock over a gallery's top (m): the terrain minus the top, every `step` m along it and at `across`
    points over its width (check X7)."""
    en = np.asarray(g["en"], float)
    z0 = g["z"] if isinstance(g["z"], list) else [g["z"]] * len(en)
    c, z = resample(en, z0, step)
    seg = np.diff(c, axis=0)
    t = np.vstack([seg, seg[-1:]])
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    left = np.column_stack([-t[:, 1], t[:, 0]])
    w, h = float(g["width_m"]), float(g["height_m"])
    least = np.inf
    for o in np.linspace(-w / 2, w / 2, across):
        q = c + left * o
        least = min(least, float((np.asarray(terrain(q[:, 0], q[:, 1]), float) - (z + h)).min()))
    return least


# ------------------------------------------------------------------------------------------------ geometry
def tube_frame(rec, face_m):
    """The floor of a tube: its centre line (n, 2), heights, cover, and its left and right edges (n, 2). A portal
    end runs `face_m` on, to the portal's face. Corners are mitred, so the tube keeps its width round a bend."""
    P = np.array(rec["p"], float).reshape(-1, 2)
    z = np.array(rec["z"], float)
    c = np.array(rec["c"], float)
    keep = np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 1e-6]
    P, z, c = P[keep], z[keep], c[keep]
    if len(P) < 2:
        return None
    if rec["ends"][0] == PORTAL:
        u = (P[0] - P[1]) / np.linalg.norm(P[0] - P[1])
        P, z, c = np.vstack([P[0] + u * face_m, P]), np.r_[z[0], z], np.r_[c[0], c]
    if rec["ends"][1] == PORTAL:
        u = (P[-1] - P[-2]) / np.linalg.norm(P[-1] - P[-2])
        P, z, c = np.vstack([P, P[-1] + u * face_m]), np.r_[z, z[-1]], np.r_[c, c[-1]]
    d = np.diff(P, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    t = np.vstack([d[:1], d[:-1] + d[1:], d[-1:]])
    ln = np.linalg.norm(t, axis=1, keepdims=True)
    t = np.where(ln > 1e-6, t / np.maximum(ln, 1e-9), np.vstack([d[:1], d[1:], d[-1:]]))
    cos = np.r_[1.0, np.einsum("ij,ij->i", t[1:-1], d[1:]), 1.0]
    half = (float(rec["w"]) / 2) / np.maximum(cos, 0.5)
    left = np.column_stack([-t[:, 1], t[:, 0]]) * half[:, None]
    return {"P": P, "z": z, "c": c, "A": P + left, "B": P - left, "d": d}


def faces_camera(nx, ny) -> bool:
    """A vertical face whose inside normal is (nx, ny) shows its inside to the camera."""
    return nx * VIEW[0] + ny * VIEW[1] < 0


def _along(W):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(W, axis=0), axis=1))]


def _dist_to_polyline(q, P):
    """Distance of each point q (k, 2) to the polyline P (m, 2)."""
    a, b = P[:-1][None], P[1:][None]
    ab = b - a
    t = np.clip(((q[:, None] - a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0, 1)
    return np.linalg.norm(q[:, None] - (a + ab * t[..., None]), axis=-1).min(1)


def wall_trims(tubes, face_m, J) -> list:
    """Per tube, how much of each wall is left out at each end: [[left, right] at its first end, [left, right] at its
    last], in metres along the wall. Where tubes join at a node, a wall is left out from the node as far as it runs
    inside another of them (within its half width less J.slack_m of its centre line): the first point clear of them,
    looked for every J.step_m, up to J.max_m."""
    frames = [tube_frame(t, face_m) for t in tubes]
    at = {}
    for i, t in enumerate(tubes):
        for end in (0, 1):
            if frames[i] is not None and t.get("nodes", [-1, -1])[end] >= 0:
                at.setdefault(t["nodes"][end], []).append((i, end))
    out = [[[0.0, 0.0], [0.0, 0.0]] for _ in tubes]
    K = int(J["segments"])
    for ends in at.values():
        if len(ends) < 2:
            continue
        for i, end in ends:
            others = []
            for j, e2 in ends:
                if j == i:
                    continue
                Pj = frames[j]["P"] if e2 == 0 else frames[j]["P"][::-1]
                others.append((Pj[:K + 1], float(tubes[j]["w"]) / 2 - J["slack_m"]))
            for side, key in enumerate(("A", "B")):
                Wl = frames[i][key] if end == 0 else frames[i][key][::-1]
                L = _along(Wl)
                ts = np.arange(0.0, min(L[-1], J["max_m"]) + 1e-9, J["step_m"])
                q = np.column_stack([np.interp(ts, L, Wl[:, 0]), np.interp(ts, L, Wl[:, 1])])
                inside = np.zeros(len(ts), bool)
                for Pj, r in others:
                    inside |= _dist_to_polyline(q, Pj) < r
                clear = np.flatnonzero(~inside)
                out[i][end][side] = float(ts[clear[0]]) if len(clear) else float(min(L[-1], J["max_m"]))
    return out


def tube_mesh(rec, face_m, trim=None):
    """The drawn faces of a tube: vertices (E, N local, z) and triangles with their face kind (FLOOR, WALL, CAP).
    `trim`: its entry of wall_trims (none: whole walls)."""
    f = tube_frame(rec, face_m)
    if f is None:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), np.zeros(0, np.int8)
    A, B, C, z, d, h = f["A"], f["B"], f["P"], f["z"], f["d"], float(rec["h"])
    trim = trim or [[0.0, 0.0], [0.0, 0.0]]
    V, T, K = [], [], []

    def quad(a, b, c, e, kind):
        n = len(V)
        V.extend([a, b, c, e])
        T.extend([[n, n + 1, n + 2], [n, n + 2, n + 3]])
        K.extend([kind, kind])

    def p3(q, zz):
        return (float(q[0]), float(q[1]), float(zz))
    along = (_along(A), _along(B))
    for i in range(len(A) - 1):
        quad(p3(A[i], z[i]), p3(A[i + 1], z[i + 1]), p3(C[i + 1], z[i + 1]), p3(C[i], z[i]), FLOOR)
        quad(p3(C[i], z[i]), p3(C[i + 1], z[i + 1]), p3(B[i + 1], z[i + 1]), p3(B[i], z[i]), FLOOR)
        lx, ly = -d[i][1], d[i][0]                      # the segment's left
        for k, (side, inx, iny) in enumerate(((A, -lx, -ly), (B, lx, ly))):
            if not faces_camera(inx, iny):
                continue
            L = along[k]                                # the wall between what is left out at its two ends
            lo, hi = max(L[i], trim[0][k]), min(L[i + 1], L[-1] - trim[1][k])
            if hi - lo < 1e-6:
                continue
            u0, u1 = (lo - L[i]) / (L[i + 1] - L[i]), (hi - L[i]) / (L[i + 1] - L[i])
            q0, q1 = side[i] + (side[i + 1] - side[i]) * u0, side[i] + (side[i + 1] - side[i]) * u1
            z0, z1 = z[i] + (z[i + 1] - z[i]) * u0, z[i] + (z[i + 1] - z[i]) * u1
            quad(p3(q0, z0), p3(q1, z1), p3(q1, z1 + h), p3(q0, z0 + h), WALL)
    for end, i, sign in ((0, 0, 1.0), (1, len(A) - 1, -1.0)):
        k = 0 if end == 0 else len(d) - 1
        if rec["ends"][end] == CLOSED and faces_camera(sign * d[k][0], sign * d[k][1]):
            quad(p3(A[i], z[i]), p3(B[i], z[i]), p3(B[i], z[i] + h), p3(A[i], z[i] + h), CAP)
    return np.array(V, float).reshape(-1, 3), np.array(T, np.int64).reshape(-1, 3), np.array(K, np.int8)


def tube_prisms(rec, face_m):
    """Each segment of a tube as the 8 corners of its box (floor then roof): (segments, 8, 3)."""
    f = tube_frame(rec, face_m)
    if f is None:
        return np.zeros([0, 8, 3])
    A, B, z, h = f["A"], f["B"], f["z"], float(rec["h"])
    out = []
    for i in range(len(A) - 1):
        fl = [(*A[i], z[i]), (*A[i + 1], z[i + 1]), (*B[i + 1], z[i + 1]), (*B[i], z[i])]
        out.append(fl + [(x, y, zz + h) for x, y, zz in fl])
    return np.array(out, float)


def depth_range_cm(records, face_m, margin_m=10.0):
    """The view depth every tube lies in (cm), with a margin: the depth range of the tunnel pass."""
    lo, hi = np.inf, -np.inf
    for r in records:
        pr = tube_prisms(r, face_m).reshape(-1, 3)
        if len(pr):
            d = project_local(pr[:, 0], pr[:, 1], pr[:, 2])[2]
            lo, hi = min(lo, float(d.min())), max(hi, float(d.max()))
    if not np.isfinite(lo):
        return [0, 1]
    return [int(math.floor((lo - margin_m) * 100)), int(math.ceil((hi + margin_m) * 100))]


# ------------------------------------------------------------------------------------------------ the stage
def tunnels_data(graph, polygon, terrain, casemates, P, portal_default_m, origin=None):
    origin = origin if origin is not None else cam_origin()
    tubes = tube_records(graph, polygon, P, portal_default_m, origin)
    if casemates:
        tubes += casemate_records(casemates, terrain, P["sample_m"], polygon, origin)
    return {"about": "Tunnel view (v2/docs/specs/tunnel-view.md): the tunnels of the transport graph, and the casemate galleries of "
                     "v2/data/structures/casemates.json, as tubes. Format: v2/layers/tunnels.py.",
            "origin_en": list(origin), "portal_face_m": P["portal_face_m"], "junction": P["junction"],
            "depth_cm": depth_range_cm(tubes, P["portal_face_m"]), "tubes": tubes}


def layer_tunnels(ctx):
    from v2.layers.raster import HeightField
    sc = Scene(ctx.dep("scene"))
    P = ctx.params["tunnels"]
    T = sc.terrain
    hf = HeightField(T["mnt"], T["e0"], T["n0"], T["step"])
    doc = json.loads(CASEMATES.read_text()) if CASEMATES.exists() else None
    data = tunnels_data(sc.graph, sc.polygon, hf.sample, doc, P, ctx.params["portal_max_from_end_m"])
    ctx.write_json("tunnels.json", data)
    tubes = data["tubes"]
    by = {}
    for t in tubes:
        by[t["kind"]] = by.get(t["kind"], 0) + 1
    meta = {"file": "tunnels.json", "tubes": len(tubes), "casemates": by.get("casemate", 0), "depth_cm": data["depth_cm"],
            "length_m": round(sum(t["s"][-1] for t in tubes), 1)}
    ctx.write_json("meta.json", meta)
    rock = [rock_over(g, hf.sample) for g in (doc or {}).get("galleries", [])]
    return {**meta, "by_kind": by, "deepest_m": round(max((max(t["c"]) for t in tubes), default=0.0), 1),
            "casemate_least_rock_m": round(min(rock), 2) if rock else None}
