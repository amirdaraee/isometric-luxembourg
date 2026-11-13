"""Scene: the facade layout of every wall: floors and a window grid (spec: v2/docs/specs/facades.md).

Windows are known positions, straight by construction (PLAN_V2 section 6). For each LoD2 wall polygon:
  1. Wall frame: u along the wall's base (metres from its first base corner), v up (metres above the wall's lowest
     point), outward normal from the building's footprint. The wall's outline in (u, v) is its polygon.
  2. Walls that get no windows: shorter than min_wall_len_m, lower than min_wall_height_m, not vertical (> 10 deg
     off), or party walls (another building's wall within party_wall_tol_m, facing the other way, overlapping at
     least party_wall_min_overlap of the shorter one).
  3. Floors: the wall's eave height H (the lowest top of the outline along it) gives
     floors = max(1, min(max_floors, 1 + floor((H - ground_floor_m) / floor_m + 0.35))) when H >= ground_floor_m,
     else 1. Floor k's floor line is v = 0 for k = 0, ground_floor_m + (k - 1) floor_m after.
  4. Bays: n = floor((L - 2 edge_margin_m) / bay_m); n = 1 when the wall fits one window. Bays are centred on the
     wall: centre of bay i at u = L/2 + (i - (n - 1)/2) * (L - 2 edge_margin_m) / n.
  5. A window (window_w_m x window_h_m, sill_m above its floor line) is kept only when its rectangle, grown by
     inset_m, lies inside the wall outline (so gables and stepped walls lose the windows that don't fit).
  6. Places of worship (the owner's decisions of 13 Nov 2026; worship.py tells them from the data). The walls of a
     church, a cathedral or a chapel get the church rule in place of rule 4 and 5 (church.py). First each church
     wall's outward side is set by the building's footprint, and what a neighbour's wall covers is cut out of
     its outline. ACT gives many of a church's walls in pieces (triangles), which cannot hold a tall window, so the
     church's walls that lie in one plane and touch are then joined into one wall (a record of its own at the end
     of the list, "merged": the walls it is made of; walls that are not planar stay out). Each joined wall gets
     one row of windows sized to it (tall, with tracery where they are big enough; round on a low wall; none on a
     lower one), in its clear spans: the stretches along it where the wall is whole from under the sills to
     over the tops (between two buttresses, beside a porch). A tower wall also gets louvred belfry openings near
     its top. The church's one entrance front gets a portal and, where it fits, a rose window. Long rows get
     buttresses between their bays, and every wall high enough a string course under the sills. No shop fronts.
     Doors stay where the door rules put them, but for the one the portal replaces.
Output facades.json: per wall {building, wall id, base [e, n, z] x 2, normal [e, n], length, height, floors, bays,
party, windows: [[u0, v0, u1, v1], ...]}; a church's walls also "worship" (the head of its windows) and "house_rule"
(what the house rule had given the wall: see `build`), its joined walls "merged", windows with their kind
([u0, v0, u1, v1, "lancet" | "traceried" | "oculus" | "rose" | "belfry"]), "tower", "front", "buttresses" and
"courses"; and "worship": the places of worship, by building id, each with its entrance front and how it was told.
"""
from __future__ import annotations

import math

import numpy as np
from shapely import STRtree
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

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
    """Lowest top of the outline along the wall (a gable rises above it, so it is the eave)."""
    tops = []
    for f in np.linspace(0.02, 0.98, 25):
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


def clear_spans(poly, L, v0, v1, margin):
    """The stretches (u0, u1) along a wall where its outline is whole from v0 to v1, each kept `margin` away from
    where it is not (a buttress standing in front of it, a porch, a step in its top or bottom)."""
    band = box(0.0, v0, L, v1)
    gone = band.difference(poly.buffer(1e-6))
    blocked = sorted((g.bounds[0] - margin, g.bounds[2] + margin) for g in getattr(gone, "geoms", [gone])
                     if not g.is_empty and g.area > 1e-6)
    spans, at = [], 0.0
    for a, b in blocked:
        if a > at:
            spans.append((at, min(a, L)))
        at = max(at, b)
    if at < L:
        spans.append((at, L))
    return [(a, b) for a, b in spans if b - a > 1e-6]


def join_walls(members, tol_cos=0.9994, tol_m=0.15):
    """The walls of one building that lie in one plane and touch, as joined walls. `members`: wall frames (dicts with
    o, u, n, poly, L, z0 and "i", their index). Returns [{o, u, n, poly, L, z0, members: [i, ...]}], each a wall
    frame like wall_frame's: u along the wall from its left end seen from outside, v up from its lowest point."""
    groups = []
    for w in sorted(members, key=lambda w: -w["L"]):
        for g in groups:
            if float(np.dot(w["n"], g["n"])) > tol_cos and abs(float(np.dot(w["o"] - g["o"], g["n"]))) < tol_m:
                g["walls"].append(w)
                break
        else:
            groups.append({"o": w["o"], "u": w["u"], "n": w["n"], "walls": [w]})
    out = []
    for g in groups:
        polys = []
        for w in g["walls"]:
            c = np.array(w["poly"].exterior.coords)
            xy = w["o"][None, :] + c[:, :1] * w["u"][None, :]
            q = Polygon(np.column_stack([(xy - g["o"]) @ g["u"], w["z0"] + c[:, 1]]))
            polys.append(q if q.is_valid else q.buffer(0))
        whole = unary_union([q.buffer(0.03, join_style=2) for q in polys]).buffer(-0.03, join_style=2)
        for part in getattr(whole, "geoms", [whole]):
            if part.geom_type != "Polygon" or part.area < 1.0:
                continue
            s0, z0, s1, _ = part.bounds
            ring = np.array(part.exterior.coords) - [s0, z0]
            near = part.buffer(0.05)
            out.append({"o": g["o"] + g["u"] * s0, "u": g["u"], "n": g["n"], "poly": Polygon(ring), "L": float(s1 - s0),
                        "z0": float(z0), "members": [w["i"] for w, q in zip(g["walls"], polys) if near.contains(q.representative_point())]})
    return out


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
                    "floors": floors, "bays": bays, "party": bool(party[i]), "no_windows": reason, "windows": wins,
                    "b": w["b"]})
    # doors and shop fronts (entrances.py): OSM entrances and shops, else the street-door and commercial-street rules
    from v2.data.scene import entrances
    import json as _json
    graph = _json.loads((ctx.dep("scene_transport") / "graph.json").read_text())
    pois = _json.loads((ctx.dep("fetch_osm_pois") / "pois.json").read_text())
    ds, unplaced, commercial = entrances.place(out, blds, fps, graph, pois, p)
    # places of worship (rule 6): the church rule on their walls, in place of what the house rule gave
    from v2.data.scene import church, worship
    styles = worship.load_styles()
    places = _json.loads((ctx.dep("scene_places") / "places.json").read_text())
    skip = {x["osm"] for x in worship.load_exceptions()}
    found = worship.find(blds, fps, _json.loads((ctx.dep("fetch_osm_worship") / "worship.json").read_text()),
                         places["places"] if isinstance(places, dict) else places, styles["buildings"], p, skip)
    kind = styles.get("kinds", {}).get("place_of_worship", {})
    main_ids = {f"{el['type']}/{el['id']}" for el in pois["elements"] if el.get("tags", {}).get("entrance") == "main"}
    n_church = {"walls": 0, "windows": 0, "house_windows": 0, "shopfronts": 0, "joined": 0, "turned": 0, "freed": 0}
    by_church, parts = {}, {}
    for i, w in enumerate(out):
        f = found.get(w["b"])
        if f is None or not worship.wall_in(f["area"], segs[i], p["worship_wall_tol_m"]):
            continue
        # what the house rule gave this wall is kept as a count: a window's glass tone (art_a.py) and a night
        # window's seed (the viewer) go by the opening's place in the order of all openings, so every other
        # building keeps exactly the windows it had
        w["house_rule"] = {"windows": w["windows"], "doors": len(w["doors"]), "shopfronts": len(w["shopfronts"])}
        w["worship"] = styles["buildings"].get(w["building"], {}).get("windows") or kind.get("windows", "round")
        n_church["house_windows"] += len(w["windows"])
        n_church["shopfronts"] += len(w["shopfronts"])
        w["shopfronts"], w["windows"], w["bays"] = [], [], 0
        n_church["walls"] += 1
        m = walls[i]
        if m["flat"] > 0.5 or m["poly"].geom_type != "Polygon" or m["poly"].area <= 1e-4:
            continue
        # the church part of the building: its footprint in the mapped outline
        if w["b"] not in parts:
            part = fps[w["b"]] if f["area"] is None else fps[w["b"]].intersection(f["area"].buffer(p["worship_wall_tol_m"]))
            parts[w["b"]] = fps[w["b"]] if part.is_empty else part
        # free where no other building's wall stands against it (the outlines of the walls on its line cut out)
        free = church.free_parts(m["poly"], church.covered(i, walls, segs, tree, p["party_wall_tol_m"]), p["church_free_min_area_m2"])
        if party[i] and free:
            w["party_free"] = round(sum(g.area for g in free) / m["poly"].area, 3)
            n_church["freed"] += 1
        # its outward side: the side outside the footprint, else away from the church part's centre
        if not church.points_out(segs[i], m["n"], fps[w["b"]], parts[w["b"]].centroid.coords[0]):
            L = m["L"]
            church.flip(m, w)
            free = [church.mirror(g, L) for g in free]
            n_church["turned"] += 1
        for g in free:
            by_church.setdefault(w["b"], []).append(dict(m, poly=g, i=i))
    # the church's walls joined plane by plane, each joined wall a record of its own after every other wall (so the
    # other walls keep their place in the list), laid out by the church rule (church.py)
    fronts = {}
    for b, members in by_church.items():
        gs = join_walls(members)
        fronts[b] = church.plan(gs, walls, out, parts[b], main_ids, p)
        for g in gs:
            H = g["H"]
            first = out[g["members"][0]]
            floors = max(1, min(p["max_floors"], 1 + int(math.floor((H - p["ground_floor_m"]) / p["floor_m"] + 0.35)))) \
                if H >= p["ground_floor_m"] else 1
            base = [[*map(float, g["o"]), g["z0"]], [*map(float, g["o"] + g["u"] * g["L"]), g["z0"]]]
            out.append({"building": first["building"], "wall": first["wall"] + f"+{len(g['members']) - 1}",
                        "base": [[round(x, 3) for x in q] for q in base], "normal": [round(float(x), 4) for x in g["n"]],
                        "length": round(g["L"], 3), "height": round(H, 3),
                        "outline": [[round(x, 3), round(y, 3)] for x, y in g["poly"].exterior.coords],
                        "floors": floors, "bays": g["bays"], "party": False, "no_windows": g["reason"], "windows": g["windows"],
                        "b": b, "doors": [g["portal"] + [g["portal_src"] or "rule:church portal", "portal"]] if g["portal"] else [],
                        "shopfronts": [], "street": g["street"], "worship": first["worship"],
                        "house_rule": {"windows": [], "doors": 0, "shopfronts": 0},
                        "merged": [out[i]["wall"] for i in g["members"]], "tower": g["tower"], "front": g["portal"] is not None,
                        "buttresses": g["buttresses"], "courses": g["courses"]})
            n_church["joined"] += 1
            n_church["windows"] += len(g["windows"])
    worship_out = {}
    for j, f in sorted(found.items()):
        ws = [w for w in out if w["building"] == blds[j]["id"] and w.get("worship")]
        kinds = {}
        for w in ws:
            for x in w["windows"]:
                kinds[x[4]] = kinds.get(x[4], 0) + 1
        worship_out[blds[j]["id"]] = {"source": f["source"], "name": f["name"], "osm_building": f["osm_building"],
                                      "whole_building": f["area"] is None, "share": f["share"], "walls": len(ws),
                                      "windows": kinds, "towers": sum(1 for w in ws if w.get("tower")),
                                      "buttresses": sum(len(w.get("buttresses", [])) for w in ws),
                                      **fronts.get(j, {"main_eave": None, "front": {"how": "no wall to lay out", "portal": False, "rose": False}})}
    for w in out:
        w.pop("b", None)
    ctx.write_json("facades.json", {"rule": p, "walls": out, "unplaced_entrances": unplaced,
                                    "commercial_streets": commercial, "worship": worship_out,
                                    "worship_exceptions": worship.load_exceptions()})
    return {"walls": len(out), "with_windows": sum(1 for w in out if w["windows"]), "party_walls": int(party.sum()),
            "windows": sum(len(w["windows"]) for w in out), "windows_before_doors": n_win,
            "floors_max": max((w["floors"] for w in out), default=0), **ds,
            "places_of_worship": len(found), "church_walls": n_church["walls"], "church_walls_joined": n_church["joined"],
            "church_windows": n_church["windows"], "church_walls_turned": n_church["turned"],
            "church_party_walls_freed": n_church["freed"],
            "church_portals": sum(1 for v in worship_out.values() if v["front"]["portal"]),
            "house_windows_replaced": n_church["house_windows"], "shopfronts_removed_from_churches": n_church["shopfronts"]}


def window_world(w, win):
    """A window rectangle (u0, v0, u1, v1) of wall record w as 4 world corners (E, N, z)."""
    (e0, n0, z0), (e1, n1, _) = w["base"]
    L = w["length"] or 1.0
    ux, uy = (e1 - e0) / L, (n1 - n0) / L
    u0, v0, u1, v1 = win
    return [(e0 + ux * u, n0 + uy * u, z0 + v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
