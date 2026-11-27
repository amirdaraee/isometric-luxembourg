"""Scene: bridges and the modelled viaducts (spec: v2/docs/specs/structures.md).

For each viaduct in v2/data/structures/viaducts.json that lies in the area:
  1. its axis is the long axis of its OSM bridge outline (man_made=bridge), its width the outline's short side;
  2. its deck height along the axis comes from the transport graph's rail edges on it (the LiDAR surface model of
     the deck, solved with the grade cap), binned every metre; stretches of the outline no rail edge covers take the
     nearest covered height (flagged "extended");
  3. arches: `count` equal spans, or spans of `span_m` (count = round((L + pier) / (span + pier))), separated by
     piers of the default thickness; a semicircular arch's crown is the deck height minus the deck thickness, its
     springing one radius lower (never below the ground at that point);
  4. piers stand between the arches, from the ground (LiDAR terrain, lowest point under the pier) to the springing;
     where the deck is less than a metre above that, there is no pier (abutment or embankment), and an arch whose
     crown is within 1.5 m of the ground is marked as abutment (solid).
Also lists every OSM bridge outline in the area (name, layer, structure) for the bridge layer in Phase 1.
Every other bridge of the graph gets supports (v2/data/structures/bridges.json): a bridge named there as a frame
(the Red Bridge) its girder and slanted legs; the rest one row of stone arches on piers per bridge, the span
following the height, no pier on a way passing under where a layout near the rule's span allows it.
structures.json: {"viaducts": [...], "bridge_outlines": [...], "supports": [...], "frames": [...]}
"""
from __future__ import annotations

import json

import numpy as np
import shapely

from v2.config import REPO
from v2.data.geo import area_polygon, osm_area_en
from v2.data.scene.grid import Grid
from v2.data.scene.transport import load

SPEC = REPO / "v2/data/structures/viaducts.json"
BRIDGES = REPO / "v2/data/structures/bridges.json"


def _values(spec):
    return {k: (v["value"] if isinstance(v, dict) and "value" in v else v) for k, v in spec.items()}


def _line(e):
    """A graph edge's plan line and heights; gaps in the heights are filled along the line."""
    en = np.array(e["en"], float)
    z = np.array([np.nan if q is None else q for q in e["z"]], float)
    ok = np.isfinite(z)
    if len(en) < 2 or not ok.any():
        return None
    return en, np.interp(np.arange(len(z)), np.flatnonzero(ok), z[ok])


def resample(en, z, step=0.5):
    """A line sampled evenly, every `step` m or a little less: distance along it, plan points, heights."""
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(en, axis=0), axis=1))]
    n = max(int(np.ceil(cum[-1] / step)), 2)
    ts = np.linspace(0, cum[-1], n + 1)
    return ts, np.column_stack([np.interp(ts, cum, en[:, 0]), np.interp(ts, cum, en[:, 1])]), np.interp(ts, cum, z)


def left_of(P):
    """Unit left normals along a plan line."""
    d = np.diff(P, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    t = np.vstack([d[:1], (d[:-1] + d[1:]) / 2, d[-1:]])
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return np.column_stack([-t[:, 1], t[:, 0]])


def chains(E):
    """Bridge edges joined end to end where a node joins exactly two of them (OSM cuts a bridge's way where it
    likes): lists of (index into E, reversed)."""
    at = {}
    for k, e in enumerate(E):
        at.setdefault(e["a"], []).append(k)
        at.setdefault(e["b"], []).append(k)
    used, out = set(), []
    for k in range(len(E)):
        if k in used:
            continue
        used.add(k)
        chain = [(k, False)]
        for forward in (True, False):
            node = E[k]["b"] if forward else E[k]["a"]
            while len(at[node]) == 2:
                nxt = [j for j in at[node] if j not in used]
                if len(nxt) != 1:
                    break
                j = nxt[0]
                used.add(j)
                enters_at_a = E[j]["a"] == node
                rev = not enters_at_a if forward else enters_at_a
                chain.append((j, rev)) if forward else chain.insert(0, (j, rev))
                node = (E[j]["b"] if enters_at_a else E[j]["a"])
        out.append(chain)
    return out


def chain_line(E, chain):
    ens, zs = [], []
    for k, rev in chain:
        en, z = _line(E[k])
        if rev:
            en, z = en[::-1], z[::-1]
        ens.append(en if not ens else en[1:])
        zs.append(z if not zs else z[1:])
    return np.vstack(ens), np.concatenate(zs)


def side_by_side(lines, widths, gap):
    """Lines grouped where one runs beside another (within their half widths and `gap`, over 80% of the shorter,
    which is at least half the longer): the ways of one bridge."""
    n = len(lines)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    ls = [shapely.LineString(l) for l in lines]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = (i, j) if ls[i].length <= ls[j].length else (j, i)
            if ls[a].length < 0.5 * ls[b].length:
                continue
            pts = shapely.line_interpolate_point(ls[a], np.linspace(0, ls[a].length, max(int(ls[a].length / 2), 3)))
            if (shapely.distance(pts, ls[b]) <= (widths[a] + widths[b]) / 2 + gap).mean() >= 0.8:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def deck_of(lines, heights, widths):
    """One deck for the ways of a bridge: the longest way's line moved to the middle of them all, its heights, and
    the width that covers them all (the median along the line)."""
    k = int(np.argmax([shapely.LineString(l).length for l in lines]))
    ts, P, z = resample(lines[k], heights[k])
    left = left_of(P)
    lo, hi = np.full(len(P), -widths[k] / 2), np.full(len(P), widths[k] / 2)
    pts = shapely.points(P)
    for j, l in enumerate(lines):
        if j == k:
            continue
        ln = shapely.LineString(l)
        q = shapely.get_coordinates(shapely.line_interpolate_point(ln, shapely.line_locate_point(ln, pts)))
        off = ((q - P) * left).sum(1)
        near = np.linalg.norm(q - P, axis=1) <= np.abs(off) + 1.0          # beside this sample, not past the way's end
        lo = np.where(near, np.minimum(lo, off - widths[j] / 2), lo)
        hi = np.where(near, np.maximum(hi, off + widths[j] / 2), hi)
    mid = (np.median(lo) + np.median(hi)) / 2
    return ts, P + left * mid, z, float(np.median(hi) - np.median(lo))


def arcade(ts, P, z, w, ground_at, rule, ways=()):
    """Arches and piers under a deck (bridges.json "supports"). `ground_at(e, n)` is the terrain; `ways` are
    (distance along the deck, half width) of the roads, tracks and paths passing under it: of the layouts near
    the rule's span, the first whose piers stand on none of them is taken (else the one with the fewest).
    Returns the deck's underside and the ground under it per sample, the arches (t0, t1, rise), the piers
    (t0, t1, foot_z), the low stretches whose sides go down to the ground (first, last sample) and the piers
    that stand on a way."""
    left = left_of(P)
    under = z - rule["deck_thickness_m"]
    sides = [P + left * w / 2, P - left * w / 2]
    ground = np.minimum.reduce([ground_at(Q[:, 0], Q[:, 1]) for Q in [P] + sides])
    clear = under - ground
    op = clear > rule["min_clear_m"]
    edges = np.flatnonzero(np.diff(np.r_[False, op, False].astype(int)))
    arches, piers, walls, on_way = [], [], [], 0
    low = ~op & (clear > 0.15)
    for i0, i1 in zip(edges[::2], edges[1::2] - 1):
        Ls = ts[i1] - ts[i0]
        if Ls < rule["min_open_m"]:
            low[i0:i1 + 1] = True
            continue
        H = float(clear[i0:i1 + 1].max())
        span = float(np.clip(rule["span_per_height"] * H, *rule["span_m"]))
        pt = float(np.clip(rule["pier_per_span"] * span, *rule["pier_m"]))
        n0 = max(1, int(round((Ls + pt) / (span + pt))))
        best = None
        for n in (n0, n0 + 1, n0 - 1, n0 + 2):
            sp = (Ls - (n - 1) * pt) / n if n >= 1 else 0
            if sp < 3.0 and n != 1:
                continue
            pr = [(ts[i0] + k * (sp + pt) + sp, ts[i0] + (k + 1) * (sp + pt)) for k in range(n - 1)]
            hit = sum(any(a - hw < t < b + hw for t, hw in ways) for a, b in pr)
            if best is None or hit < best[0]:
                best = (hit, n, sp, pr)
            if hit == 0:
                break
        hit, n, sp, pr = best
        on_way += hit
        for k in range(n):
            a0 = ts[i0] + k * (sp + pt)
            a1 = a0 + sp
            tt = np.linspace(a0, a1, 17)
            room = float((np.interp(tt, ts, under) - rule["crown_m"] - np.interp(tt, ts, ground)).max())
            rise = min(sp / 2, max(rule["rise_share"] * room, 0.5))
            arches.append({"t": [round(float(a0), 2), round(float(a1), 2)], "rise_m": round(float(rise), 2)})
        for a, b in pr:
            foot = float(np.interp(np.linspace(a, b, 5), ts, ground).min())
            piers.append({"t": [round(float(a), 2), round(float(b), 2)], "foot_z": round(foot, 2)})
    le = np.flatnonzero(np.diff(np.r_[False, low, False].astype(int)))
    walls = [[int(a), int(b)] for a, b in zip(le[::2], le[1::2] - 1) if b > a]
    return under, ground, arches, piers, walls, on_way


def frame(spec, edges, ground_at):
    """A bridge on slanted legs (bridges.json "frames": the Red Bridge). Its axis is the line through its ways,
    its deck their heights; the feet stand on the terrain `feet_apart_m` apart (in proportion, if the bridge's
    length in the data is not the documented one), the legs lean toward the middle as they rise to the girder."""
    v = _values(spec)
    lines = [_line(e) for e in edges]
    pts = np.vstack([l[0] for l in lines])
    zz = np.concatenate([l[1] for l in lines])
    ctr = pts.mean(0)
    u = np.linalg.svd(pts - ctr, full_matrices=False)[2][0]
    side = np.array([-u[1], u[0]])
    t, lat = (pts - ctr) @ u, (pts - ctr) @ side
    W = float(lat.max() - lat.min() + np.mean([e["width"] for e in edges]))
    c_lat = float(lat.max() + lat.min()) / 2
    zfit = np.polyfit(t, zz, 2 if len(np.unique(np.round(t))) > 4 else 1)     # the deck's long profile (it sags or crowns a little)
    t0, t1 = float(t.min()), float(t.max())
    L, mid = t1 - t0, (t0 + t1) / 2
    at = lambda tt, l=0.0: ctr + np.outer(np.atleast_1d(tt), u) + side * (c_lat + l)      # noqa: E731
    under = lambda tt: np.polyval(zfit, tt) - 1.0                                           # noqa: E731
    half = v["feet_apart_m"] / 2 * L / v["length_m"]
    deep = v["girder_depth_m"] + v["haunch_m"]
    tops, legs, footings = {}, [], []
    for s in (-1, 1):
        tf = mid + s * half
        gz = float(ground_at(*at(tf)[0]))
        rise = max(float(under(tf)) - deep - gz, 5.0)
        tops[s] = mid + s * (half - v["leg_run_per_height"] * rise)
    ts = np.arange(t0, t1 + 1e-6, 2.0)
    depth = v["girder_depth_m"] + sum(v["haunch_m"] * np.exp(-(((ts - tops[s]) / v["haunch_length_m"]) ** 2)) for s in (-1, 1))
    for s in (-1, 1):
        tf, tt = mid + s * half, tops[s]
        ztop = float(under(tt)) - float(np.interp(tt, ts, depth))
        for l in (-v["leg_offset_share"] * W, v["leg_offset_share"] * W):
            pf, ptop = at(tf, l)[0], at(tt, l)[0]
            gz = float(ground_at(*pf))
            legs.append({"side": s, "top": [round(float(ptop[0]), 2), round(float(ptop[1]), 2), round(ztop, 2)],
                         "foot": [round(float(pf[0]), 2), round(float(pf[1]), 2), round(gz, 2)],
                         "top_m": v["leg_top_m"], "foot_m": v["leg_foot_m"]})
            footings.append({"e": round(float(pf[0]), 2), "n": round(float(pf[1]), 2), "ground_z": round(gz, 2),
                             "size_m": v["footing_m"]})
    G = at(ts)
    return {"id": spec["id"], "name": spec["name"], "structure": spec["structure"], "colour": spec["colour"],
            "edges": [e["id"] for e in edges], "axis": [round(float(u[0]), 5), round(float(u[1]), 5)],
            "length_model_m": round(L, 1), "length_documented_m": v["length_m"], "width_m": round(W, 2),
            "height_model_m": round(float(under(mid)) + 1.0 - float(ground_at(*at(mid)[0])), 1),
            "height_documented_m": v["height_m"], "feet_apart_m": round(2 * half, 1),
            "tops_apart_m": round(float(tops[1] - tops[-1]), 1),
            "girder": {"width_m": round(v["girder_width_share"] * W, 2),
                       "line": [[round(float(x), 2), round(float(y), 2), round(float(a), 2), round(float(a - d), 2)]
                                for (x, y), a, d in zip(G, under(ts), depth)]},
            "legs": legs, "footings": footings}


def bridges(g, ground_at, area, viaduct_edges):
    """Supports for every bridge of the graph that is not a modelled viaduct: the frames of bridges.json, and for
    the rest one row of arches per bridge (its ways side by side share it)."""
    spec = json.loads(BRIDGES.read_text())
    rule = _values(spec["supports"])
    E = [e for e in g["edges"] if e["structure"] == "bridge" and e["id"] not in viaduct_edges and e["mode"] != "elevator"
         and _line(e) is not None and shapely.contains_xy(area, *np.array(e["en"], float)[len(e["en"]) // 2])]
    frames, named = [], set()
    for f in spec["frames"]:
        mine = [e for e in E if any(n in ((e.get("bridge_name") or "") + " " + (e.get("name") or "")) for n in f["names"])]
        if mine:
            frames.append(frame(f, mine, ground_at))
            named |= {e["id"] for e in mine}
    E = [e for e in E if e["id"] not in named]
    ch = chains(E)
    lines = [chain_line(E, c) for c in ch]
    widths = [max(float(E[k]["width"]) for k, _ in c) for c in ch]
    under_ways = [(shapely.LineString(e["en"]), float(e["width"])) for e in g["edges"]
                  if e["structure"] == "ground" and e["mode"] in ("road", "rail", "tram", "path") and len(e["en"]) > 1]
    tree = shapely.STRtree([l for l, _ in under_ways])
    out = []
    for grp in side_by_side([l[0] for l in lines], widths, rule["parallel_gap_m"]):
        ts, P, z, w = deck_of([lines[i][0] for i in grp], [lines[i][1] for i in grp], [widths[i] for i in grp])
        centre = shapely.LineString(P)
        ways = []
        for j in tree.query(centre, predicate="intersects"):
            x = centre.intersection(under_ways[j][0])
            for q in shapely.get_coordinates(x):
                ways.append((float(centre.project(shapely.Point(q))), under_ways[j][1] / 2 + rule["way_margin_m"]))
        under, ground, arches, piers, walls, on_way = arcade(ts, P, z, w, ground_at, rule, ways)
        ids = [E[k]["id"] for i in grp for k, _ in ch[i]]
        longest = max((E[k] for i in grp for k, _ in ch[i]), key=lambda e: e["length"])
        out.append({"edges": ids, "spine": longest["id"], "name": longest.get("bridge_name") or longest.get("name") or "",
                    "length_m": round(float(ts[-1]), 2), "width_m": round(w, 2),
                    "height_m": round(float((under - ground).max()) + rule["deck_thickness_m"], 1),
                    "crown_m": rule["crown_m"],
                    "line": [[round(float(x), 2), round(float(y), 2), round(float(a), 2), round(float(b), 2)]
                             for (x, y), a, b in zip(P, under, ground)],
                    "arches": arches, "piers": piers, "walls": walls, "piers_on_a_way": on_way})
    return out, frames


def axis_of(outline):
    r = outline.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    sides = [(np.linalg.norm(c[(i + 1) % 4] - c[i]), i) for i in range(4)]
    L, i = max(sides)
    u = (c[(i + 1) % 4] - c[i]) / L
    W = min(s for s, _ in sides)
    ctr = np.array(r.centroid.coords[0])
    # the axis spans the outline itself (not its rectangle): project the outline's points
    pts = np.array(outline.exterior.coords)
    t = (pts - ctr) @ u
    return ctr, u, float(t.min()), float(t.max()), float(W)


def build(ctx):
    spec = json.loads(SPEC.read_text())
    dflt = {k: v["value"] for k, v in spec["defaults"].items()}
    g = load(ctx.dep("scene_transport"))
    T = np.load(ctx.dep("scene_terrain") / "terrain.npz")
    mnt = Grid(T["mnt"], T["e0"], T["n0"], T["step"])
    area = area_polygon(ctx.area)
    els = json.loads((ctx.dep("fetch_osm_transport") / "transport.json").read_text())["elements"]
    by_id = {f"{el['type']}/{el['id']}": el for el in els}
    outlines = []
    for key, el in by_id.items():
        if el.get("tags", {}).get("man_made") == "bridge":
            p = osm_area_en(el)
            if p is not None and p.intersects(area):
                tg = el["tags"]
                outlines.append({"osm": key, "name": tg.get("name", ""), "layer": tg.get("layer"),
                                 "structure": tg.get("bridge:structure"), "area_m2": round(p.area, 1),
                                 "rings": [[[round(x, 2), round(y, 2)] for x, y in p.exterior.coords]] if p.geom_type == "Polygon" else []})
    out = []
    for v in spec["viaducts"]:
        el = by_id.get(v["osm_outline"])
        outline = osm_area_en(el) if el else None
        if outline is None or not outline.intersects(area):
            out.append({"id": v["id"], "status": "outside area" if outline is not None else "outline missing"})
            continue
        ctr, u, t0, t1, W = axis_of(outline)
        L = t1 - t0
        # the deck: every rail or tram bridge edge of the graph over this outline (the listed OSM ways, and any
        # other way the outline covers: OSM splits the line where it likes)
        inside = outline.buffer(2.0)
        eds, tt, zz = [], [], []
        for e in g["edges"]:
            if e["mode"] not in ("rail", "tram") or e["structure"] != "bridge":
                continue
            en = np.array(e["en"]); z = np.array([np.nan if q is None else q for q in e["z"]], float)
            k = shapely.contains_xy(inside, en[:, 0], en[:, 1]) & np.isfinite(z)
            if not k.any():
                continue
            eds.append(e)
            t = (en - ctr) @ u
            tt += list(t[k]); zz += list(z[k])
        if not tt:
            out.append({"id": v["id"], "status": "no deck edges in the graph"})
            continue
        tt, zz = np.array(tt), np.array(zz)
        ts = np.arange(t0, t1 + 0.5, 1.0)
        zs = np.full(len(ts), np.nan)
        for i, t in enumerate(ts):
            k = np.abs(tt - t) <= 1.0
            if k.any():
                zs[i] = np.median(zz[k])
        covered = np.isfinite(zs)
        if not covered.any():
            out.append({"id": v["id"], "status": "deck edges off the outline"})
            continue
        zs = np.interp(ts, ts[covered], zs[covered])        # extended flat beyond the covered stretch
        en = ctr + np.outer(ts, u)
        ground = mnt.sample(en[:, 0], en[:, 1])
        pier = dflt["pier_thickness_m"]
        sp = v["spans"]
        n = int(sp["count"]) if "count" in sp else max(1, int(round((L + pier) / (sp["span_m"] + pier))))
        span = (L - (n - 1) * pier) / n
        arches, piers = [], []
        r = span / 2
        for i in range(n):
            a = t0 + i * (span + pier)
            b = a + span
            mid = (a + b) / 2
            zdeck = float(np.interp(mid, ts, zs))
            crown = zdeck - dflt["deck_thickness_m"]
            gmid = float(np.nanmin(np.interp([a, mid, b], ts, ground)))
            spring = min(crown, max(crown - r, gmid)) if v["structure"] == "arch" else crown
            pa, pb = ctr + u * a, ctr + u * b
            arches.append({"i": i, "t": [round(a - t0, 2), round(b - t0, 2)], "from": [round(pa[0], 2), round(pa[1], 2)],
                           "to": [round(pb[0], 2), round(pb[1], 2)], "span_m": round(span, 2), "crown_z": round(crown, 2),
                           "spring_z": round(spring, 2), "radius_m": round(r, 2), "ground_min_z": round(gmid, 2),
                           "clipped_by_ground": bool(crown - r < gmid)})
            if crown - gmid < 1.5:
                arches[-1]["abutment"] = True          # the deck is (nearly) on the ground here: solid, no arch
            if i < n - 1:
                pc = ctr + u * (b + pier / 2)
                ks = np.abs(ts - (b + pier / 2)) <= pier / 2 + 0.5
                foot = float(np.nanmin(ground[ks]))
                top = min(spring, float(np.interp(b + pier / 2, ts, zs)) - dflt["deck_thickness_m"])
                if top - foot < 1.0:
                    continue                            # no room for a pier: abutment or embankment
                piers.append({"i": i, "e": round(pc[0], 2), "n": round(pc[1], 2), "foot_z": round(foot, 2),
                              "top_z": round(top, 2), "deck_z": round(float(np.interp(b + pier / 2, ts, zs)), 2),
                              "thickness_m": pier, "width_m": round(W, 2), "height_m": round(top - foot, 2)})
        out.append({"id": v["id"], "name": v["name"], "status": "ok", "structure": v["structure"], "osm_outline": v["osm_outline"],
                    "length_model_m": round(L, 1), "length_documented_m": v["length_m"], "height_documented_m": v["height_m"],
                    "height_model_m": round(float(np.nanmax(zs - ground)), 1), "width_m": round(W, 2),
                    "deck_edges": [e["id"] for e in eds], "deck_covered_share": round(float(covered.mean()), 3),
                    "deck": [[round(float(x), 2), round(float(y), 2), round(float(z), 2)] for (x, y), z in zip(en, zs)],
                    "deck_thickness_m": dflt["deck_thickness_m"], "parapet_m": dflt["parapet_m"],
                    "arches": arches, "piers": piers, "spans_rule": sp})
    via_edges = {i for v in out for i in v.get("deck_edges", [])}
    supports, frames = bridges(g, mnt.sample, area, via_edges)
    ctx.write_json("structures.json", {"viaducts": out, "bridge_outlines": outlines, "supports": supports, "frames": frames})
    return {"viaducts": {v["id"]: v["status"] for v in out}, "bridge_outlines": len(outlines),
            "arches": {v["id"]: len(v.get("arches", [])) for v in out},
            "bridges_with_supports": len(supports), "bridge_arches": sum(len(b["arches"]) for b in supports),
            "bridge_piers": sum(len(b["piers"]) for b in supports),
            "piers_on_a_way": sum(b["piers_on_a_way"] for b in supports), "frames": [f["id"] for f in frames]}
