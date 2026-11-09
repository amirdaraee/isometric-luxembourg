"""Scene: the facade layout of every wall: floors and a window grid (spec: v2/docs/specs/facades.md).

Windows are known positions, straight by construction (PLAN_V2 section 6). For each LoD2 wall polygon:
  1. Wall frame: u along the wall's base (metres from its first base corner), v up (metres above the wall's lowest
     point), outward normal from the building's footprint. The wall's outline in (u, v) is its polygon.
  2. Walls that get no windows: shorter than min_wall_len_m, lower than min_wall_height_m, not vertical (> 10 deg
     off), or party walls (another building's wall within party_wall_tol_m, facing the other way, overlapping at
     least party_wall_min_overlap of the shorter one).
  3. Floors: the wall's eave height H (the lowest top of the outline over its middle half) gives
     floors = max(1, min(max_floors, 1 + floor((H - ground_floor_m) / floor_m + 0.35))) when H >= ground_floor_m,
     else 1. Floor k's floor line is v = 0 for k = 0, ground_floor_m + (k - 1) floor_m after.
  4. Bays: n = floor((L - 2 edge_margin_m) / bay_m); n = 1 when the wall fits one window. Bays are centred on the
     wall: centre of bay i at u = L/2 + (i - (n - 1)/2) * (L - 2 edge_margin_m) / n.
  5. A window (window_w_m x window_h_m, sill_m above its floor line) is kept only when its rectangle, grown by
     inset_m, lies inside the wall outline (so gables and stepped walls lose the windows that don't fit).
Output facades.json: per wall {building, wall id, base [e, n, z] x 2, normal [e, n], length, height, floors, bays,
party, windows: [[u0, v0, u1, v1], ...]}.
"""
from __future__ import annotations

import math

import numpy as np
from shapely import STRtree
from shapely.geometry import LineString, Polygon, box

from v2.data.scene.buildings import footprints, load


def wall_frame(ring, centre):
    """(origin, u axis, normal, (u, v) polygon, length, z0) of a 3D wall ring, normal pointing away from centre."""
    p = np.asarray(ring, float)
    if len(p) < 4:
        return None
    xy = p[:, :2]
    # the wall's horizontal direction: the longest horizontal extent of its points
    c = xy.mean(axis=0)
    _, _, vt = np.linalg.svd(xy - c, full_matrices=False)
    u = vt[0]
    if np.linalg.norm(u) < 1e-9:
        return None
    nrm = np.array([u[1], -u[0]])
    if np.dot(c - centre, nrm) < 0:
        nrm = -nrm
    # u runs so that the normal is to its right (u x n = +z): looking at the wall from outside, u goes left to right
    if u[0] * nrm[1] - u[1] * nrm[0] > 0:
        u = -u
    s = (xy - c) @ u
    o = c + u * s.min()
    us = (xy - o) @ u
    z0 = float(p[:, 2].min())
    vs = p[:, 2] - z0
    flat = float(np.abs((xy - o) @ nrm).max())          # how far the wall's points are from its plane
    return o, u, nrm, Polygon(np.column_stack((us, vs))), float(us.max()), z0, flat


def eave_height(poly: Polygon, L: float) -> float:
    """Lowest top of the outline over the middle half of the wall."""
    tops = []
    for f in np.linspace(0.25, 0.75, 9):
        line = LineString([(f * L, -1), (f * L, 1e4)])
        x = poly.intersection(line)
        if not x.is_empty:
            tops.append(x.bounds[3])
    return min(tops) if tops else 0.0


def layout(poly, L, H, p):
    """The window rectangles (u0, v0, u1, v1) of one wall."""
    if H >= p["ground_floor_m"]:
        floors = 1 + int(math.floor((H - p["ground_floor_m"]) / p["floor_m"] + 0.35))
    else:
        floors = 1
    floors = max(1, min(p["max_floors"], floors))
    usable = L - 2 * p["edge_margin_m"]
    bays = int(usable // p["bay_m"]) if usable >= p["bay_m"] else (1 if L >= p["window_w_m"] + 2 * p["inset_m"] else 0)
    bays = max(bays, 0)
    wins = []
    if bays:
        pitch = usable / bays if usable > 0 else L
        lines = [0.0] + [p["ground_floor_m"] + (k - 1) * p["floor_m"] for k in range(1, floors)]
        shrink = poly.buffer(-p["inset_m"], join_style=2)
        for v in lines:
            for i in range(bays):
                cu = L / 2 + (i - (bays - 1) / 2) * pitch
                r = (cu - p["window_w_m"] / 2, v + p["sill_m"], cu + p["window_w_m"] / 2, v + p["sill_m"] + p["window_h_m"])
                if not shrink.is_empty and shrink.contains(box(*r)):
                    wins.append([round(x, 3) for x in r])
    return floors, bays, wins


def build(ctx):
    p = ctx.params["facades"]
    blds = load(ctx.dep("scene_buildings"))
    fps = footprints(blds)
    walls = []
    for bi, b in enumerate(blds):
        cen = np.array(fps[bi].centroid.coords[0])
        for w in b["walls"]:
            fr = wall_frame(w["ring"], cen)
            if fr is None:
                continue
            o, u, nrm, poly, L, z0, flat = fr
            if not poly.is_valid:
                poly = poly.buffer(0)
            base = [[*map(float, o), z0], [*map(float, o + u * L), z0]]
            walls.append({"b": bi, "building": b["id"], "wall": w["id"], "o": o, "u": u, "n": nrm, "poly": poly,
                          "L": L, "z0": z0, "flat": flat, "base": base})
    # party walls: another building's wall on the same line, facing the other way
    segs = [LineString([w["base"][0][:2], w["base"][1][:2]]) for w in walls]
    tree = STRtree(segs)
    party = np.zeros(len(walls), bool)
    for i, w in enumerate(walls):
        if w["L"] < 0.5:
            continue
        for j in tree.query(segs[i].buffer(p["party_wall_tol_m"])):
            v = walls[j]
            if v["b"] == w["b"] or np.dot(v["n"], w["n"]) > -0.9:
                continue
            ov = segs[j].buffer(p["party_wall_tol_m"], cap_style=2).intersection(segs[i]).length
            if ov >= p["party_wall_min_overlap"] * min(w["L"], v["L"]):
                party[i] = True
                break
    out = []
    n_win = 0
    for i, w in enumerate(walls):
        H = eave_height(w["poly"], w["L"])
        reason = None
        if party[i]:
            reason = "party wall"
        elif w["L"] < p["min_wall_len_m"]:
            reason = "short"
        elif H < p["min_wall_height_m"]:
            reason = "low"
        elif w["flat"] > 0.5:
            reason = "not planar"
        floors, bays, wins = (0, 0, []) if reason else layout(w["poly"], w["L"], H, p)
        n_win += len(wins)
        out.append({"building": w["building"], "wall": w["wall"], "base": [[round(x, 3) for x in q] for q in w["base"]],
                    "normal": [round(float(x), 4) for x in w["n"]], "length": round(w["L"], 3), "height": round(H, 3),
                    "outline": [[round(x, 3), round(y, 3)] for x, y in w["poly"].exterior.coords] if w["poly"].geom_type == "Polygon" else [],
                    "floors": floors, "bays": bays, "party": bool(party[i]), "no_windows": reason, "windows": wins})
    ctx.write_json("facades.json", {"rule": p, "walls": out})
    return {"walls": len(out), "with_windows": sum(1 for w in out if w["windows"]), "party_walls": int(party.sum()),
            "windows": n_win, "floors_max": max((w["floors"] for w in out), default=0)}


def window_world(w, win):
    """A window rectangle (u0, v0, u1, v1) of wall record w as 4 world corners (E, N, z)."""
    (e0, n0, z0), (e1, n1, _) = w["base"]
    L = w["length"] or 1.0
    ux, uy = (e1 - e0) / L, (n1 - n0) / L
    u0, v0, u1, v1 = win
    return [(e0 + ux * u, n0 + uy * u, z0 + v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
