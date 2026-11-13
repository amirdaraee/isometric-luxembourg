"""The outside of a place of worship, by rule from its geometry (spec: v2/docs/specs/facades.md, "Places of
worship, round two"; the owner's decision of 13 Nov 2026, "One more round").

worship.py says which buildings and which walls; facades.py joins a church's walls plane by plane. This module
lays out each joined wall and the church as a whole. Nothing here is placed by hand: every opening follows from
the walls' outlines, their heights and the church's footprint.

  free walls     a church wall is free where no other building's wall stands against it: what a neighbour's wall
                 covers is cut out of its outline, the rest takes part (a nave wall that rises over a lower
                 neighbour keeps its upper part)
  outward        the outward side of a church wall is the side that is outside the building's footprint; where
                 both sides are inside it (a nave wall over its aisle) it points away from the centre of the church
                 part, not of the whole building
  towers         a wall whose top stands church_tower_rise_m over the church's main eave (the median top of its
                 walls, by length), no longer than church_tower_max_len_m, and tall for its length or standing on
                 the roofs
  the row        one row of windows per wall, sized to the wall: the sill at church_sill_share of the free height
                 (church_sill_min_m to church_sill_m), the top church_top_m under the eave, the width
                 church_window_w_share of the window's height. A window wide and tall enough has tracery (a
                 mullion, two lights, a top light), else it is a lancet. A wall too low for a window but
                 church_oculus_min_wall_m high has round windows; a lower wall has none
  belfry         louvred openings near the top of a tower wall, above the main eave; one, or a pair on a wide wall
  entrance front one per church: (1) the wall with an OSM door tagged entrance=main; else (2) the end of the long
                 axis where the tower stands; else (3) the end opposite the apse (the end where the footprint
                 narrows); else (4) the end with a wall onto a street; else (5) the wall with a door. At an end,
                 the outermost wall that can hold the portal
  portal, rose   an arched doorway on the entrance front, standing on the ground; above it a rose window where a
                 circle of church_rose_min_d_m fits the wall
  buttresses     between the bays of a row of three windows or more on a wall that is not a tower, from the wall's
                 bottom to three quarters up the windows, where the strip lies in the outline
  courses        a string course under the sills of every wall high enough
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

TALL = ("lancet", "traceried")
ROUND = ("oculus", "rose")
KINDS = TALL + ROUND + ("belfry",)


# ---------------------------------------------------------------------------------------------- walls
def mirror(poly, L):
    """A wall outline seen in the frame that runs the other way along the wall."""
    if poly.is_empty:
        return poly
    def one(g):
        return Polygon([(L - x, y) for x, y in g.exterior.coords])
    return unary_union([one(g) for g in getattr(poly, "geoms", [poly])])


def points_out(seg: LineString, n, fp, centre) -> bool:
    """Does normal n of a wall (base line seg) point out of the building? The side outside the footprint is the
    outside; where that does not tell (both sides in it, or neither), away from `centre`."""
    votes = 0
    for f in (0.25, 0.5, 0.75):
        m = seg.interpolate(f, normalized=True)
        a = fp.contains(Point(m.x + n[0] * 0.4, m.y + n[1] * 0.4))
        b = fp.contains(Point(m.x - n[0] * 0.4, m.y - n[1] * 0.4))
        if a != b:
            votes += -1 if a else 1
    if votes:
        return votes > 0
    m = seg.interpolate(0.5, normalized=True)
    return float((m.x - centre[0]) * n[0] + (m.y - centre[1]) * n[1]) >= 0


def flip(wall, rec):
    """Turn a wall's frame round (its normal pointed into the building): the wall dict of facades.build and its
    record. What the house rule had given it stays in its own frame, with the outline it was laid out in."""
    L = wall["L"]
    rec["house_rule"]["outline"] = rec["outline"]
    wall["o"] = wall["o"] + wall["u"] * L
    wall["u"], wall["n"] = -wall["u"], -wall["n"]
    wall["poly"] = mirror(wall["poly"], L)
    wall["base"] = [wall["base"][1], wall["base"][0]]
    rec["base"] = [rec["base"][1], rec["base"][0]]
    rec["normal"] = [round(float(x), 4) for x in wall["n"]]
    rec["outline"] = [[round(L - x, 3), y] for x, y in rec["outline"]]
    rec["doors"] = [[round(L - d[2], 3), d[1], round(L - d[0], 3), d[3]] + list(d[4:]) for d in rec["doors"]]


def covered(i, walls, segs, tree, tol):
    """What other buildings' walls cover of wall i, in its (u, v): the outlines of the walls on its line."""
    w = walls[i]
    polys = []
    for j in tree.query(segs[i].buffer(tol)):
        v = walls[j]
        if v["b"] == w["b"] or v["poly"].geom_type != "Polygon" or v["poly"].is_empty or v["L"] < 0.5:
            continue
        if abs(float(np.dot(v["n"], w["n"]))) < 0.9:
            continue
        if segs[j].buffer(tol, cap_style=2).intersection(segs[i]).length < 0.5:
            continue
        c = np.array(v["poly"].exterior.coords)
        xy = v["o"][None, :] + c[:, :1] * v["u"][None, :]
        q = Polygon(np.column_stack([(xy - w["o"]) @ w["u"], v["z0"] + c[:, 1] - w["z0"]]))
        polys.append(q if q.is_valid else q.buffer(0))
    return unary_union(polys) if polys else None


def free_parts(poly, cover, min_area):
    """The parts of a wall outline that no neighbour's wall covers."""
    if cover is None:
        return [poly]
    free = poly.difference(cover.buffer(0.3, join_style=2))
    return [g for g in getattr(free, "geoms", [free]) if g.geom_type == "Polygon" and g.area >= min_area]


# ---------------------------------------------------------------------------------------------- one wall
def _top_at(poly, u0, u1):
    """The lowest top of the outline between u0 and u1."""
    vals = []
    for u in np.linspace(u0, u1, 7):
        x = poly.intersection(LineString([(u, -1e3), (u, 1e4)]))
        if not x.is_empty:
            vals.append(x.bounds[3])
    return min(vals) if vals else None


def window_width(h, L, p):
    """The width of a tall window h high on a wall L long."""
    return round(float(np.clip(p["church_window_w_share"] * h, p["church_window_min_w_m"],
                               max(p["church_window_min_w_m"], min(p["church_window_max_w_m"], p["church_window_wall_share"] * L)))), 2)


def row(poly, L, H, p, top=None):
    """The one row of windows of a wall: (bays, [[u0, v0, u1, v1, kind], ...], the row's bottom). `top`: nothing
    of the row reaches above it (a tower's belfry)."""
    from v2.data.scene.entrances import bottom_at
    from v2.data.scene.facades import clear_spans
    inset, edge = p["inset_m"], p["edge_margin_m"]
    steps = np.arange(0.25, max(L - 0.25, 0.26), 0.5)
    under = [bottom_at(poly, u - 0.2, u + 0.2) for u in steps]
    bases = sorted({round(b, 1) for b in under if b is not None}) or [0.0]
    lim = H - p["church_top_m"] if top is None else min(top, H - p["church_top_m"])
    best = (0, [], bases[0])
    for base in bases:
        Hf = lim + p["church_top_m"] - base                    # the free height: to the eave, or to what is above
        if Hf <= 0:
            continue
        sill = base + min(p["church_sill_m"], max(p["church_sill_min_m"], p["church_sill_share"] * Hf))
        t = min(lim, sill + p["church_window_max_h_m"])
        if t - sill >= p["church_window_min_h_m"]:
            w = window_width(t - sill, L, p)
            kind = "traceried" if w >= p["church_tracery_min_w_m"] and t - sill >= p["church_tracery_min_h_m"] else "lancet"
            v0, v1 = sill, t
        elif Hf >= p["church_oculus_min_wall_m"]:
            w, kind = p["church_oculus_d_m"], "oculus"
            v0 = base + p["church_oculus_at"] * Hf - w / 2
            v1 = v0 + w
            if v1 > lim + p["church_top_m"] - 0.5:
                continue
        else:
            continue
        bay = max(p["church_bay_m"], w + p["church_pier_m"])
        wins, bays = [], 0
        for a, b in clear_spans(poly, L, v0 - inset, v1 + inset, inset):
            a2, b2 = max(a, edge), min(b, L - edge)             # the edge margin is for the wall's corners
            if b2 - a2 < w:
                continue
            n = max(1, int((b2 - a2) // bay))
            pitch = (b2 - a2) / n
            bays += n
            for k in range(n):
                cu = a2 + (k + 0.5) * pitch
                wins.append([round(cu - w / 2, 3), round(v0, 3), round(cu + w / 2, 3), round(v1, 3), kind])
        if len(wins) > len(best[1]):
            best = (bays, wins, base)
    return best


def belfry(poly, L, H, floor_v, p):
    """A tower wall's louvred openings near its top, none of them below floor_v: [[u0, v0, u1, v1, "belfry"], ...]."""
    t = H - p["church_belfry_top_m"]
    s = max(t - float(np.clip(p["church_belfry_h_share"] * L, p["church_belfry_min_h_m"], p["church_belfry_max_h_m"])), floor_v)
    if t - s < p["church_belfry_min_h_m"] - 1e-9:
        return []
    w = round(float(np.clip(p["church_belfry_w_share"] * L, p["church_belfry_min_w_m"], p["church_belfry_max_w_m"])), 2)
    cs = [L / 2 - w / 2 - p["church_belfry_gap_m"] / 2, L / 2 + w / 2 + p["church_belfry_gap_m"] / 2] \
        if L >= p["church_belfry_pair_len_m"] else [L / 2]
    shrink = poly.buffer(-p["inset_m"], join_style=2)
    out = [[round(c - w / 2, 3), round(s, 3), round(c + w / 2, 3), round(t, 3), "belfry"] for c in cs]
    return out if all(shrink.contains(box(*r[:4])) for r in out) else []


def portal_at(poly, L, H, uc, z0, ground, p):
    """The portal of a wall centred at uc, standing on the ground: [u0, v0, u1, v1], or None where it does not fit."""
    from v2.data.scene.entrances import bottom_at, fits
    w = float(np.clip(p["church_portal_w_share"] * L, p["church_portal_min_w_m"], p["church_portal_max_w_m"]))
    w = min(w, L - 2 * p["edge_margin_m"], p["church_portal_wall_share"] * H / p["church_portal_h_share"])
    if w < p["church_portal_min_w_m"] - 1e-9:
        return None
    uc = min(max(uc, w / 2 + p["edge_margin_m"]), L - w / 2 - p["edge_margin_m"])
    a, b = uc - w / 2, uc + w / 2
    v0 = bottom_at(poly, a, b)
    if v0 is None or z0 + v0 > ground + p["church_portal_max_step_m"]:
        return None
    top = _top_at(poly, a, b)
    h = min(p["church_portal_h_share"] * w, (top if top is not None else H) - v0 - p["church_top_m"])
    if h < p["church_portal_min_h_m"]:
        return None
    r = [round(a, 3), round(v0, 3), round(b, 3), round(v0 + h, 3)]
    return r if fits(poly, r, 0.25) else None


def rose_over(poly, L, portal, p):
    """The rose window over a portal: the largest circle (to church_rose_max_d_m) that fits the wall above it,
    as its square [u0, v0, u1, v1, "rose"], or None where none of church_rose_min_d_m fits."""
    uc = (portal[0] + portal[2]) / 2
    lo = portal[3] + p["church_rose_over_portal_m"]
    shrink = poly.buffer(-p["inset_m"], join_style=2)
    hi = poly.bounds[3]
    d = min(p["church_rose_max_d_m"], p["church_rose_wall_share"] * L)
    while d >= p["church_rose_min_d_m"] - 1e-9:
        ok = [v for v in np.arange(lo, hi - d, 0.25) if shrink.contains(box(uc - d / 2, v, uc + d / 2, v + d + p["church_rose_under_top_m"]))]
        if ok:
            v = ok[len(ok) // 2]                                # the middle of where it fits
            return [round(uc - d / 2, 3), round(float(v), 3), round(uc + d / 2, 3), round(float(v) + d, 3), "rose"]
        d -= 0.2
    return None


def buttresses(poly, wins, base, H, p):
    """The buttresses of a row: strips [u0, v0, u1, v1] between its bays and outside its end windows."""
    tall = sorted((w for w in wins if w[4] in TALL), key=lambda w: w[0])
    if len(tall) < p["church_buttress_min_bays"] or H - base < p["church_buttress_min_wall_m"]:
        return []
    bw = p["church_buttress_w_m"]
    v1 = tall[0][1] + p["church_buttress_h_share"] * (tall[0][3] - tall[0][1])
    cs = [(a[0] + a[2]) / 2 for a in tall]
    pitch = float(np.median(np.diff(cs)))
    at = [(cs[i] + cs[i + 1]) / 2 for i in range(len(cs) - 1) if cs[i + 1] - cs[i] < 1.5 * pitch]
    at = [cs[0] - pitch / 2] + at + [cs[-1] + pitch / 2]
    near = poly.buffer(0.02)
    out = []
    for c in at:
        r = [round(c - bw / 2, 3), round(base, 3), round(c + bw / 2, 3), round(v1, 3)]
        clear = all(r[2] + p["church_buttress_gap_m"] <= w[0] or r[0] - p["church_buttress_gap_m"] >= w[2] for w in wins)
        if clear and near.contains(box(r[0], r[1] + 0.05, r[2], r[3])):
            out.append(r)
    return out


# ---------------------------------------------------------------------------------------------- the church
def wmedian(values, weights):
    o = np.argsort(values)
    v, w = np.asarray(values, float)[o], np.asarray(weights, float)[o]
    return float(v[np.searchsorted(np.cumsum(w), w.sum() / 2)])


def towers(gs, p):
    """Marks the tower walls of a church's joined walls (g["tower"]); returns the main eave's height (m, absolute)."""
    ok = [g for g in gs if not g["reason"]]
    if not ok:
        for g in gs:
            g["tower"] = False
        return None
    main = wmedian([g["z0"] + g["H"] for g in ok], [g["L"] for g in ok])
    for g in gs:
        up = g["z0"] + g["H"] - main
        g["tower"] = bool(not g["reason"] and up >= p["church_tower_rise_m"] and g["L"] <= p["church_tower_max_len_m"]
                          and (g["H"] >= p["church_tower_slender"] * g["L"]
                               or (g["z0"] >= main - p["church_tower_stage_under_m"] and g["H"] >= g["L"])))
    return main


def axis_of(part):
    """The long axis of a footprint: (centre, unit direction, half length, half width)."""
    r = np.array(part.minimum_rotated_rectangle.exterior.coords)[:4]
    e0, e1 = r[1] - r[0], r[2] - r[1]
    a, b = (e0, e1) if np.linalg.norm(e0) >= np.linalg.norm(e1) else (e1, e0)
    return r.mean(axis=0), a / max(np.linalg.norm(a), 1e-9), float(np.linalg.norm(a)) / 2, float(np.linalg.norm(b)) / 2


def taper(part, c, a, hl, hw, s):
    """How much the footprint narrows at the end s (+1 or -1) of its axis: 1 - its width there over its widest."""
    nrm = np.array([-a[1], a[0]])

    def width(t):
        m = c + a * (t * hl)
        x = part.intersection(LineString([m - nrm * (hw + 1), m + nrm * (hw + 1)]))
        return x.length
    widest = max(width(t) for t in np.linspace(-0.6, 0.6, 13))
    return 1 - float(np.mean([width(s * t) for t in (0.9, 0.94, 0.98)])) / max(widest, 1e-9)


def entrance_front(gs, walls, part, ground, main_walls, door_walls, p):
    """The church's entrance front: (joined wall, its portal [u0, v0, u1, v1], how it was decided), or
    (None, None, why not). main_walls: {piece index: door's centre along the piece (m)} of the OSM main
    entrances; door_walls: the same of every door."""
    def centre_in(g, i, u, walls):
        m = walls[i]
        return float((m["o"] + m["u"] * u - g["o"]) @ g["u"])

    def with_door(doors, walls):
        for g in sorted(gs, key=lambda g: -g["L"] * g["H"]):
            if g["reason"]:
                continue
            for i in g["members"]:
                if i in doors:
                    for uc in (centre_in(g, i, doors[i], walls), g["L"] / 2):
                        r = portal_at(g["poly"], g["L"], g["H"], uc, g["z0"], ground, p)
                        if r:
                            return g, r
        return None, None

    g, r = with_door(main_walls, walls)
    if g is not None:
        return g, r, "the OSM main entrance"
    c, a, hl, hw = axis_of(part)
    mids = {id(g): (g["o"] + g["u"] * g["L"] / 2 - c) @ a / max(hl, 1e-9) for g in gs}

    def at_end(s):
        """The outermost wall of the end s that faces out along the axis and can hold the portal."""
        cand = [g for g in gs if not g["reason"] and s * float(np.dot(g["n"], a)) >= p["church_front_cos"]
                and s * mids[id(g)] >= p["church_front_end_share"]]
        for g in sorted(cand, key=lambda g: (-round(s * mids[id(g)], 2), -g["L"])):
            r = portal_at(g["poly"], g["L"], g["H"], g["L"] / 2, g["z0"], ground, p)
            if r:
                return g, r
        return None, None

    order = []
    tw = [s for s in (1, -1) if any(g["tower"] and s * mids[id(g)] >= p["church_front_end_share"] for g in gs)]
    if len(tw) == 1:
        order.append((tw[0], "the tower end"))
    t1, t2 = taper(part, c, a, hl, hw, 1), taper(part, c, a, hl, hw, -1)
    if abs(t1 - t2) >= p["church_apse_taper"]:
        order.append((-1 if t1 > t2 else 1, "opposite the apse"))
    st = [s for s in (1, -1) if any(g.get("street") and s * mids[id(g)] >= p["church_front_end_share"]
                                    and s * float(np.dot(g["n"], a)) >= p["church_front_cos"] for g in gs)]
    if len(st) == 1:
        order.append((st[0], "the end onto a street"))
    for s, how in order:
        g, r = at_end(s)
        if g is not None:
            return g, r, how
    g, r = with_door(door_walls, walls)
    if g is not None:
        return g, r, "the wall with a door"
    return None, None, "no wall can hold a portal"


def plan(gs, walls, recs, part, main_ids, p):
    """Lays out one church from its joined walls gs (facades.join_walls; each gets H, reason, tower, windows,
    buttresses, courses, portal). walls, recs: facades.build's wall dicts and records (the pieces, by index).
    Returns {"main_eave", "front": {...}}."""
    from v2.data.scene.facades import eave_height
    for g in gs:
        g["H"] = eave_height(g["poly"], g["L"])
        g["reason"] = "short" if g["L"] < p["min_wall_len_m"] else "low" if g["H"] < p["min_wall_height_m"] else None
        g["street"] = next((recs[i]["street"] for i in g["members"] if recs[i].get("street")), None)
        g["windows"], g["buttresses"], g["courses"], g["portal"], g["bays"], g["portal_src"] = [], [], [], None, 0, None
    main = towers(gs, p)
    ground = min(g["z0"] for g in gs) if gs else 0.0
    main_walls, door_walls = {}, {}
    for g in gs:
        for i in g["members"]:
            for d in recs[i]["doors"]:
                if len(d) > 5 and d[5] == "garage":
                    continue
                door_walls.setdefault(i, (d[0] + d[2]) / 2)
                if str(d[4]).removeprefix("osm:") in main_ids:
                    main_walls.setdefault(i, (d[0] + d[2]) / 2)
    front, portal, how = entrance_front(gs, walls, part, ground, main_walls, door_walls, p)
    gap = p["church_opening_gap_m"]
    for g in gs:
        if g["reason"]:
            continue
        poly, L, H = g["poly"], g["L"], g["H"]
        bell = belfry(poly, L, H, main - g["z0"] + p["church_belfry_over_eave_m"], p) if g["tower"] else []
        bays, wins, base = row(poly, L, H, p, top=bell[0][1] - p["church_belfry_under_m"] if bell else None)
        blocks = []
        if g is front:
            g["portal"] = portal
            rose = rose_over(poly, L, portal, p)
            blocks.append(box(portal[0] - gap, portal[1] - 1, portal[2] + gap, portal[3] + gap))
            if rose:
                blocks.append(box(rose[0] - gap, rose[1] - gap, rose[2] + gap, rose[3] + gap))
                bell = [x for x in bell if not blocks[-1].intersects(box(*x[:4]))]
        # the doors of the walls it is made of, in its own frame: its windows give way to them, and a door the
        # portal stands on is the portal
        for i in g["members"]:
            m = walls[i]
            keep = []
            for d in recs[i]["doors"]:
                a, c = sorted(float((m["o"] + m["u"] * d[k] - g["o"]) @ g["u"]) for k in (0, 2))
                dz = m["z0"] - g["z0"]
                b = box(a - p["door_window_gap_m"], d[1] + dz - 1, c + p["door_window_gap_m"], d[3] + dz + p["door_window_gap_m"])
                if g is front and blocks[0].intersects(b):
                    if str(d[4]).startswith("osm:") or g["portal_src"] is None:
                        g["portal_src"] = d[4]                 # the portal is that door: it keeps the door's source
                    continue
                keep.append(d)
                blocks.append(b)
            recs[i]["doors"] = keep
        wins = [x for x in wins if not any(k.intersects(box(*x[:4])) for k in blocks)]
        g["bays"] = bays
        g["buttresses"] = [] if g["tower"] else [r for r in buttresses(poly, wins, base, H, p)
                                                 if not any(k.intersects(box(*r)) for k in blocks)]
        tall = [x for x in wins if x[4] in TALL]
        if tall:
            g["courses"] = [round(tall[0][1] - p["church_course_under_sill_m"], 3)]
        elif H - base >= p["church_course_min_wall_m"]:
            g["courses"] = [round(base + min(p["church_sill_m"], max(p["church_sill_min_m"], p["church_sill_share"] * (H - base)))
                                  - p["church_course_under_sill_m"], 3)]
        g["windows"] = wins + ([rose] if g is front and rose else []) + bell
    return {"main_eave": None if main is None else round(main, 2),
            "front": {"how": how, "portal": portal is not None,
                      "rose": bool(front is not None and any(x[4] == "rose" for x in front["windows"]))}}
