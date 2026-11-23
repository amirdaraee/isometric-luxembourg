"""A well-known building's openings as they are, in place of what the church rule gives (spec:
v2/docs/specs/facades.md, "Landmarks as they are"; the owner's decision of 23 Nov 2026).

The church rule (church.py) is a layout, not a survey: one row of windows per wall, sized to the wall. On the
cathedral that gives windows where there are none and leaves out the ones there are. A building entered in
`v2/data/structures/landmark_facades.json` has its walls described one by one, from the sources named there; this
module puts each description on the joined wall it names.

  the wall      a description names its wall by a point on its foot (`at`, the wall's left end as seen from
                outside) and the bearing its outside looks to (`facing`), never by a number in the list: the joined
                wall of that building in that plane (its normal within landmark_facing_deg of `facing`, either way
                round; `at` within landmark_reach_m of its base line). Where two walls stand in one plane, the one
                that holds more of the openings, then the one whose left end is nearer `at`
  the frame     openings are given from left to right as seen from outside. A joined wall whose normal points the
                other way (church.py tells the outside by the footprint, which does not tell for a tower's wall
                over the roofs) is turned round first: `facing` is what a source shows
  the openings  [kind, x0, x1, z0, z1, head]: metres from `at` to the right, metres above the building's datum. They
                replace the rule's windows on that wall; the rule's string courses and drawn buttresses go with
                them (a description gives its own courses). A wall that is not named keeps the rule
  what is kept  an opening is kept only where it lies inside the wall's outline and overlaps no other; what is not
                kept is listed, and the data check F28 fails on it
"""
from __future__ import annotations

import json
import math

import numpy as np
from shapely.geometry import Polygon, box

KINDS = ("lancet", "traceried", "belfry", "oculus", "rose")
ROUND = ("oculus", "rose")
HEADS = ("pointed", "round", "flat")
MEASURED = ("capture", "photo", "mirror")
FACING_DEG = 20.0              # a wall's normal against the description's bearing
REACH_M = 0.75                 # the description's point against the wall's base line


def load() -> dict:
    from v2.config import V2
    return json.loads((V2 / "data" / "structures" / "landmark_facades.json").read_text())


def frame_of(facing_deg: float):
    """The outward normal of a wall that looks to bearing `facing_deg`, and the direction along it from left to
    right as seen from outside: (n, r), each (east, north)."""
    a = math.radians(facing_deg)
    n = np.array([math.sin(a), math.cos(a)])
    return n, np.array([-n[1], n[0]])


def turn(rec: dict) -> None:
    """Turn a joined wall's frame round, in place: its base runs the other way, its normal points the other way,
    its outline and its doors are mirrored. Its windows, courses and buttresses are the caller's to set."""
    L = rec["length"]
    rec["base"] = [rec["base"][1], rec["base"][0]]
    rec["normal"] = [round(-float(x), 4) for x in rec["normal"]]
    rec["outline"] = [[round(L - u, 3), v] for u, v in rec["outline"]]
    rec["doors"] = [[round(L - d[2], 3), d[1], round(L - d[0], 3), d[3], *d[4:]] for d in rec["doors"]]
    rec["windows"] = [[round(L - x[2], 3), x[1], round(L - x[0], 3), x[3], *x[4:]] for x in rec["windows"]]
    rec["buttresses"] = [[round(L - b[2], 3), b[1], round(L - b[0], 3), b[3]] for b in rec.get("buttresses") or []]


def _outline(rec):
    if len(rec.get("outline", [])) < 4:
        return None
    poly = Polygon(rec["outline"])
    return poly if poly.is_valid else poly.buffer(0)


def _place(desc, rec, datum):
    """A description's openings in a wall record's frame as it would be once turned to `facing`: (rows, turned,
    how far `at` is from the wall's left end)."""
    n, r = frame_of(desc["facing"])
    b0, b1 = np.array(rec["base"][0][:2], float), np.array(rec["base"][1][:2], float)
    turned = float((b1 - b0) @ r) < 0
    left = b1 if turned else b0
    ua = float((np.array(desc["at"], float) - left) @ r)
    dz = datum - rec["base"][0][2]
    rows = [[round(ua + o[1], 3), round(o[3] + dz, 3), round(ua + o[2], 3), round(o[4] + dz, 3), o[0], *o[5:6]]
            for o in desc["openings"]]
    return rows, turned, ua


def find(desc: dict, recs: list, datum: float):
    """The joined wall a description names: (index into recs, or None; the reason when None)."""
    n, _ = frame_of(desc["facing"])
    at = np.array(desc["at"], float)
    cands = []
    for k, rec in enumerate(recs):
        L = rec["length"]
        if L <= 0 or abs(float(np.array(rec["normal"], float) @ n)) < math.cos(math.radians(FACING_DEG)):
            continue
        b0, b1 = np.array(rec["base"][0][:2], float), np.array(rec["base"][1][:2], float)
        u = (b1 - b0) / L
        rel = at - b0
        if abs(float(rel[0] * u[1] - rel[1] * u[0])) > REACH_M or not (-REACH_M <= float(rel @ u) <= L + REACH_M):
            continue
        rows, turned, ua = _place(desc, rec, datum)
        poly = _outline(rec)
        if turned and poly is not None:
            poly = Polygon([(L - x, y) for x, y in poly.exterior.coords])
        held = sum(1 for x in rows if poly is not None and poly.buffer(0.02).contains(box(*x[:4])))
        cands.append((held, -abs(ua), k))
    if not cands:
        return None, "no joined wall of the building in that plane at that point"
    cands.sort(reverse=True)
    if len(cands) > 1 and cands[0][:2] == cands[1][:2]:
        return None, "two walls fit the description alike"
    return cands[0][2], None


def bad_description(desc: dict) -> str | None:
    """What is wrong with a description as written, or None."""
    if not (isinstance(desc.get("at"), list) and len(desc["at"]) == 2 and isinstance(desc.get("facing"), (int, float))):
        return "no point or no bearing"
    if desc.get("measured") not in MEASURED:
        return f"measured is not one of {MEASURED}"
    for o in desc.get("openings", []):
        if len(o) not in (5, 6) or o[0] not in KINDS:
            return f"an opening that is not [kind, x0, x1, z0, z1, head]: {o}"
        if not (o[1] < o[2] and o[3] < o[4]):
            return f"an opening with no width or no height: {o}"
        if o[0] in ROUND:
            if len(o) == 6 and o[5] is not None:
                return f"a round window has no head: {o}"
        elif len(o) != 6 or o[5] not in HEADS:
            return f"an opening whose head is not one of {HEADS}: {o}"
    return None


def apply(out: list, data: dict | None = None) -> dict:
    """Put every described wall's openings on its joined wall in `out` (the facade records, in place). Returns the
    report: per building its name, the walls set, their openings by kind and by how they were measured, the walls
    turned round, and what did not fit (`unmatched`, `outside`, `overlapping`: each must be empty, check F28)."""
    data = load() if data is None else data
    report = {}
    for bid, b in data.get("buildings", {}).items():
        recs = [w for w in out if w.get("building") == bid and w.get("merged")]
        rep = {"name": b.get("name"), "described": len(b.get("walls", [])), "walls": 0, "openings": {}, "measured": {},
               "blank": 0, "turned": [], "unmatched": [], "outside": [], "overlapping": []}
        report[bid] = rep
        if not recs:
            rep["unmatched"] = [[d.get("name"), "the building has no joined church wall here"] for d in b.get("walls", [])]
            continue
        taken = {}
        for desc in b.get("walls", []):
            name = desc.get("name")
            why = bad_description(desc)
            k = None
            if why is None:
                k, why = find(desc, recs, b["datum"])
            if why is None and k in taken:
                why = f"the same wall as '{taken[k]}'"
            if why is not None:
                rep["unmatched"].append([name, why])
                continue
            taken[k] = name
            rec = recs[k]
            rows, turned, _ = _place(desc, rec, b["datum"])
            if turned:
                turn(rec)
                rep["turned"].append(name)
            poly = _outline(rec)
            keep = []
            for x in rows:
                if poly is None or not poly.buffer(0.02).contains(box(*x[:4])):
                    rep["outside"].append([name, x])
                elif any(box(*x[:4]).intersection(box(*y[:4])).area > 1e-6 for y in keep) or \
                        any(box(*x[:4]).intersection(box(*d[:4])).area > 1e-6 for d in rec["doors"]):
                    rep["overlapping"].append([name, x])
                else:
                    keep.append(x)
            dz = b["datum"] - rec["base"][0][2]
            rec["windows"] = keep
            rec["courses"] = [round(z + dz, 3) for z in desc.get("courses", []) if 0.3 < z + dz < rec["height"] - 0.3]
            rec["buttresses"] = []
            rec["no_windows"] = None if keep else "landmark: a wall without openings"
            rec["landmark"] = name
            rec["measured"] = desc["measured"]
            rep["walls"] += 1
            rep["blank"] += not keep
            rep["measured"][desc["measured"]] = rep["measured"].get(desc["measured"], 0) + 1
            for x in keep:
                rep["openings"][x[4]] = rep["openings"].get(x[4], 0) + 1
    return report
