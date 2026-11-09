"""Scene: the transport graph with a height profile per segment (spec: v2/docs/specs/transport-graph.md).

Roads, paths, rail, tram and funicular ways from OpenStreetMap, in LUREF metres, unwarped (the data is the truth):
  1. Ways are cut where they leave the terrain grid and split into edges at every node shared with another way
     (a junction) and at their ends. Edges joined at a node share that node's height.
  2. Each edge is tagged with its mode (road, path, steps, rail, tram, funicular, elevator), width, lanes, oneway,
     OSM layer and structure: ground, bridge (bridge=* other than no), tunnel (tunnel=yes/culvert/...), passage
     (tunnel=building_passage, covered=yes: at ground level under a building) or indoor (corridors).
  3. Node heights: a node touching any ground-level edge takes the LiDAR ground (MNT) there, the median of five
     samples within 1 m; a node inside a bridge takes the LiDAR surface (MNS) of the deck; nodes inside tunnels have
     no observation and are interpolated along the tunnel graph from its portal nodes (harmonic, by length).
  4. Each edge is resampled every <= sample_m and its profile solved (v2.data.scene.profile) between its two node
     heights with the grade capped by mode: ground edges follow the MNT (median across the carriageway), bridge
     decks follow the MNS (median across the deck, kept at least deck_min_above_ground_m over the ground), tunnels
     run as straight as the grade allows, softly held below the terrain by the vehicle clearance plus 1 m of
     cover beyond the portal zone. Elevators run straight between their landings.
  5. Portals: where a tunnel's profile first lies a vehicle's clearance below the terrain, walking in from each
     portal node.
graph.json: {"nodes": [{id, e, n, z, kind, deg, boundary}], "edges": [{id, way, a, b, mode, cls, name, width,
lanes, oneway, layer, structure, bridge_name, tunnel_name, en, s, z, ground, deck_obs?, solved}], "portals": [...]}
"""
from __future__ import annotations

import heapq
import json
import math
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import box

from v2.config import params
from v2.data.geo import area_polygon, lonlat_to_en
from v2.data.scene.grid import Grid
from v2.data.scene.profile import normals, resample, solve

DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
            "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "service", "busway",
            "road", "raceway", "construction"}
PATHS = {"footway", "path", "cycleway", "track", "bridleway", "pedestrian", "corridor", "via_ferrata"}
RAIL = {"rail": "rail", "light_rail": "rail", "subway": "rail", "narrow_gauge": "rail", "preserved": "rail",
        "disused": "rail", "tram": "tram", "funicular": "funicular"}


def classify(tg, skip):
    """(mode, class) of a way, or None when it is not part of the graph."""
    if tg.get("area") == "yes":
        return None
    hw = tg.get("highway")
    if hw:
        if hw in skip:
            return None
        if hw == "elevator":
            return "elevator", hw
        if hw == "steps":
            return "steps", hw
        if hw in DRIVABLE:
            return "road", hw
        if hw in PATHS:
            return "path", hw
        return None
    rw = tg.get("railway")
    if rw in RAIL:
        return RAIL[rw], rw
    return None


def structure(tg, p):
    if tg.get("highway") in p["indoor_tags"]["highway"] or tg.get("indoor") == "yes":
        return "indoor"
    t = tg.get("tunnel", "no")
    if t == "building_passage" or tg.get("covered") == "yes":
        return "passage"
    if t in p["underground_tags"]["tunnel"]:
        return "tunnel"
    if tg.get("bridge", "no") not in ("no", "") or tg.get("man_made") == "bridge":
        return "bridge"
    return "ground"


def num(v):
    if v is None:
        return None
    try:
        return float(str(v).split(";")[0].replace(",", ".").replace("m", "").strip())
    except ValueError:
        return None


def grade_key(mode):
    return {"road": "road", "path": "path", "steps": "steps", "rail": "rail", "tram": "tram",
            "funicular": "funicular"}.get(mode, "other")


def deck_key(mode):
    return {"road": "road", "path": "path", "steps": "path", "rail": "rail", "tram": "tram"}.get(mode, "other")


def clearance(mode, p):
    return p["clearance_m"].get({"steps": "path"}.get(mode, mode), p["clearance_m"]["other"])


def width_lanes(tg, cls, mode, p):
    lanes = num(tg.get("lanes"))
    w = num(tg.get("width")) or num(tg.get("est_width"))
    if mode in ("rail", "tram") and tg.get("tracks"):
        lanes = num(tg["tracks"])
    if lanes is None:
        lanes = p["default_lanes"].get(cls, 1 if mode in ("rail", "tram", "funicular") else 0)
    if w is None:
        if mode == "road" and tg.get("lanes"):
            w = lanes * p["lane_width_m"]
        else:
            w = p["default_width_m"].get(cls, 3.0)
    return float(w), int(lanes)


def ways_to_edges(elements, grid: Grid, select, p):
    """Split the graph ways into edges at junctions; cut where they leave the grid."""
    x0, y0, x1, y1 = grid.bounds()
    inner = (x0 + 3, y0 + 3, x1 - 3, y1 - 3)
    pieces = []
    for el in elements:
        if el["type"] != "way" or "geometry" not in el or "nodes" not in el:
            continue
        tg = el.get("tags", {})
        c = classify(tg, set(p["skip_highway"]))
        if c is None:
            continue
        g = el["geometry"]
        if len(g) != len(el["nodes"]) or len(g) < 2:
            continue
        e, n = lonlat_to_en(np.array([q["lon"] for q in g]), np.array([q["lat"] for q in g]))
        ok = (e > inner[0]) & (e < inner[2]) & (n > inner[1]) & (n < inner[3])
        # contiguous runs inside the grid
        run = []
        for k in range(len(g)):
            if ok[k]:
                run.append(k)
            if (not ok[k] or k == len(g) - 1) and len(run) >= 2:
                pieces.append((el, c, run[:], run[0] > 0, run[-1] < len(g) - 1, e, n))
            if not ok[k]:
                run = []
    use = defaultdict(int)
    for el, _, run, *_ in pieces:
        for k in run:
            use[el["nodes"][k]] += 1
        use[el["nodes"][run[0]]] += 1
        use[el["nodes"][run[-1]]] += 1
    edges, boundary = [], set()
    for el, (mode, cls), run, cut0, cut1, e, n in pieces:
        nodes = el["nodes"]
        if cut0:
            boundary.add(nodes[run[0]])
        if cut1:
            boundary.add(nodes[run[-1]])
        start = 0
        for j in range(1, len(run)):
            nid = nodes[run[j]]
            if j == len(run) - 1 or use[nid] > 1:
                ks = run[start:j + 1]
                en = np.column_stack((e[ks], n[ks]))
                if np.hypot(*np.diff(en, axis=0).T).sum() > 0.05:
                    edges.append({"el": el, "mode": mode, "cls": cls, "a": nodes[ks[0]], "b": nodes[ks[-1]],
                                  "en": en, "k": len(edges)})
                start = j
    sel = [ed for ed in edges if shapely.intersects(select, shapely.linestrings(ed["en"]))]
    return sel, boundary


def node_heights(edges, mnt: Grid, mns: Grid, p):
    inc = defaultdict(list)
    pos = {}
    for ed in edges:
        for end, idx in (("a", 0), ("b", -1)):
            inc[ed[end]].append(ed)
            pos[ed[end]] = ed["en"][idx]
    z, kind = {}, {}
    off = np.array([[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]], float)
    for nid, eds in inc.items():
        st = {ed["structure"] for ed in eds}
        x, y = pos[nid]
        if st <= {"ground", "passage", "indoor", "elevator"}:
            kind[nid] = "ground"
            z[nid] = float(np.nanmedian(mnt.sample(x + off[:, 0], y + off[:, 1])))
        elif st & {"ground", "passage", "indoor"}:
            # an abutment or a portal: the road's level is the ground a few metres back along the open approach
            # (the ground model under the first metres of a span already dips into the valley, and above a portal
            # it is the cliff)
            kind[nid] = "abutment"
            vals = []
            for ed in eds:
                if ed["structure"] not in ("ground", "passage", "indoor"):
                    continue
                en = ed["en"] if ed["a"] == nid else ed["en"][::-1]
                pts, s = resample(en, 1.0)
                k = (s >= 2.0) & (s <= 6.0)
                if k.any():
                    vals += list(mnt.sample(pts[k, 0], pts[k, 1]))
            if not vals:
                vals = list(mnt.sample(x + off[:, 0], y + off[:, 1]))
            z[nid] = float(np.nanmedian(vals))
        elif "bridge" in st and "tunnel" not in st:
            kind[nid] = "deck"
            r = p["node_search_m"] / 3
            z[nid] = float(np.nanmedian(mns.sample(x + off[:, 0] * r, y + off[:, 1] * r)))
        else:
            kind[nid] = "tunnel" if st == {"tunnel"} else "mixed"
            z[nid] = math.nan
    # interpolate the unobserved nodes along the edges (harmonic, weights 1 / length)
    unknown = [nid for nid in z if not np.isfinite(z[nid])]
    nb = defaultdict(list)
    for ed in edges:
        L = float(np.hypot(*np.diff(ed["en"], axis=0).T).sum()) or 1.0
        nb[ed["a"]].append((ed["b"], 1 / L)); nb[ed["b"]].append((ed["a"], 1 / L))
    known = {nid for nid in z if np.isfinite(z[nid])}
    est = {nid: (z[nid] if nid in known else math.nan) for nid in z}
    for nid in unknown:  # start from the terrain minus a clearance, then relax
        x, y = pos[nid]
        est[nid] = float(mnt.sample(np.array([x]), np.array([y]))[0]) - 10.0
    for _ in range(400):
        delta = 0.0
        for nid in unknown:
            s = sum(w for _, w in nb[nid])
            if not s:
                continue
            v = sum(est[m] * w for m, w in nb[nid]) / s
            delta = max(delta, abs(v - est[nid])); est[nid] = v
        if delta < 1e-3:
            break
    return est, kind, pos, inc


def tunnel_distances(edges, inc, kind):
    """Shortest distance along tunnel edges from each node to a portal node (a tunnel node touching the open)."""
    portal_nodes = {nid for nid, eds in inc.items()
                    if any(ed["structure"] == "tunnel" for ed in eds) and any(ed["structure"] != "tunnel" for ed in eds)}
    adj = defaultdict(list)
    for ed in edges:
        if ed["structure"] == "tunnel":
            adj[ed["a"]].append((ed["b"], ed["L"])); adj[ed["b"]].append((ed["a"], ed["L"]))
    dist = {nid: 0.0 for nid in portal_nodes}
    h = [(0.0, nid) for nid in portal_nodes]
    while h:
        d, u = heapq.heappop(h)
        if d > dist.get(u, math.inf):
            continue
        for v, L in adj[u]:
            if d + L < dist.get(v, math.inf):
                dist[v] = d + L
                heapq.heappush(h, (d + L, v))
    return dist, portal_nodes


def tunnel_chains(edges):
    """Connected groups of tunnel edges: {edge k: chain id}, {chain id: total length}."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for ed in edges:
        if ed["structure"] == "tunnel":
            parent[find(ed["a"])] = find(ed["b"])
    chain_of, chain_len = {}, defaultdict(float)
    for ed in edges:
        if ed["structure"] == "tunnel":
            c = find(ed["a"])
            chain_of[ed["k"]] = str(c)
            chain_len[str(c)] += ed["L"]
    return chain_of, chain_len


def find_portals(recs, portal_nodes, p):
    """From each portal node, walk into the tunnel (through simple joins) to where the vehicle is first a full
    clearance under its cover: the portal."""
    by_node = defaultdict(list)
    for r in recs:
        if r["structure"] == "tunnel":
            by_node[r["a"]].append(r); by_node[r["b"]].append(r)
    out = []
    for node in sorted(portal_nodes):
        for r0 in by_node[node]:
            need = clearance(r0["mode"], p)
            walked, cur, at, hit, seen = 0.0, r0, node, None, set()
            while cur is not None and cur["id"] not in seen and walked < 500:
                seen.add(cur["id"])
                fwd = cur["a"] == at
                zs, cs, ss = cur["z"], cur["cover"], cur["s"]
                order = range(len(zs)) if fwd else range(len(zs) - 1, -1, -1)
                for i in order:
                    if zs[i] is not None and cs[i] is not None and cs[i] - zs[i] >= need:
                        hit = (cur, i, walked + (ss[i] if fwd else ss[-1] - ss[i]))
                        break
                if hit:
                    break
                walked += cur["length"]
                at = cur["b"] if fwd else cur["a"]
                nxt = [r for r in by_node[at] if r["id"] != cur["id"]]
                cur = nxt[0] if len(nxt) == 1 and at not in portal_nodes else None
            rec = {"node": node, "edge": r0["id"], "mode": r0["mode"], "chain": r0["chain"],
                   "chain_length": r0["chain_length"], "found": hit is not None}
            if hit:
                c, i, d = hit
                rec.update(dist_m=round(d, 1), at_edge=c["id"], e=c["en"][i][0], n=c["en"][i][1], z=c["z"][i],
                           cover=c["cover"][i])
            out.append(rec)
    return out


def build(ctx):
    p = ctx.params["transport"]
    chk = params()["checks"]
    area = area_polygon(ctx.area)
    margin = params()["areas"][ctx.area]["margin_m"]
    T = np.load(ctx.dep("scene_terrain") / "terrain.npz")
    mnt = Grid(T["mnt"], T["e0"], T["n0"], T["step"]); mns = Grid(T["mns"], T["e0"], T["n0"], T["step"])
    els = json.loads((ctx.dep("fetch_osm_transport") / "transport.json").read_text())["elements"]
    edges, boundary = ways_to_edges(els, mnt, area.buffer(margin / 2), p)
    ctx.log(f"{len(edges)} edges")
    for ed in edges:
        tg = ed["el"].get("tags", {})
        ed["structure"] = structure(tg, p)
        if ed["mode"] == "elevator":
            ed["structure"] = "elevator"
        ed["L"] = float(np.hypot(*np.diff(ed["en"], axis=0).T).sum())
    nz, nkind, npos, inc = node_heights(edges, mnt, mns, p)
    tdist, portal_nodes = tunnel_distances(edges, inc, nkind)
    chain_of, chain_len = tunnel_chains(edges)
    # what covers a tunnel: the earth (MNT), or a building or bridge deck built over it (then the surface, MNS)
    from v2.data.scene.buildings import footprints, load as load_buildings
    built = list(footprints(load_buildings(ctx.dep("scene_buildings"))))
    built += [shapely.linestrings(ed["en"]).buffer(4.0) for ed in edges if ed["structure"] == "bridge"]
    built = shapely.union_all(built) if built else None
    out_edges, portals, unsolved = [], [], 0
    for ed in edges:
        tg = ed["el"].get("tags", {})
        mode, st = ed["mode"], ed["structure"]
        width, lanes = width_lanes(tg, ed["cls"], mode, p)
        pts, s = resample(ed["en"], p["sample_m"])
        ds = float(s[1] - s[0]) if len(s) > 1 else 0.0
        nrm = normals(pts)
        lat = np.array(p["lateral_samples"]) * width
        ground = np.nanmedian(np.stack([mnt.sample(pts[:, 0] + nrm[:, 0] * o, pts[:, 1] + nrm[:, 1] * o) for o in lat]), axis=0)
        z0, z1 = nz[ed["a"]], nz[ed["b"]]
        rec_extra = {}
        if st == "tunnel":
            under = shapely.contains_xy(built, pts[:, 0], pts[:, 1]) if built is not None else np.zeros(len(s), bool)
            cover = np.where(under, np.fmax(mns.sample(pts[:, 0], pts[:, 1]), ground), ground)
            tun_d = np.minimum(tdist.get(ed["a"], 0.0) + s, tdist.get(ed["b"], 0.0) + (s[-1] - s))
            rec_extra.update(cover=cover, tunnel_d=tun_d, under_built=under)
        if st == "elevator":
            z = np.linspace(z0, z1, len(s))
            how = "linear"
        else:
            grade = p["max_grade"][grade_key(mode)]
            kw = dict(z0=z0, z1=z1, bin_m=p["profile_bin_m"], smooth_n=max(1, int(round(p["smooth_window_m"] / max(ds, 0.1)))) | 1)
            if st == "bridge":
                dl = np.array([-1, 0, 1]) * max(0.0, width / 2 - p["deck_lateral_m"])
                deck = np.nanmedian(np.stack([mns.sample(pts[:, 0] + nrm[:, 0] * o, pts[:, 1] + nrm[:, 1] * o) for o in dl]), axis=0)
                z = solve(deck, ds, p["deck_max_grade"][deck_key(mode)], lo_soft=ground + p["deck_min_above_ground_m"], **kw)
                rec_extra["deck_obs"] = deck
                how = "mns"
            elif st == "tunnel":
                need = clearance(mode, p) + chk["tunnel_min_cover_m"]
                ramp = np.clip(tun_d / chk["portal_max_from_end_m"], 0, 1)
                hi_soft = cover - need * ramp
                lin = np.linspace(z0, z1, len(s))
                z = solve(np.full(len(s), np.nan), ds, grade, prior=lin, prior_w=0.01, hi_soft=hi_soft, **kw)
                how = "tunnel"
            else:
                z = solve(ground, ds, grade, **kw)
                how = "mnt"
            relax = 1.0
            while z is None and relax < 16:
                # the pinned ends cannot be joined within the grade cap: relax the cap, and say so
                relax *= 2
                kw2 = dict(kw)
                if st == "bridge":
                    z = solve(deck, ds, p["deck_max_grade"][deck_key(mode)] * relax, lo_soft=ground + p["deck_min_above_ground_m"], **kw2)
                elif st == "tunnel":
                    z = solve(np.full(len(s), np.nan), ds, grade * relax, prior=lin, prior_w=0.01, hi_soft=hi_soft, **kw2)
                else:
                    z = solve(ground, ds, grade * relax, **kw2)
            if relax > 1:
                unsolved += 1
                how += f"+grade_x{relax:g}"
            if z is None:
                z = np.linspace(z0, z1, len(s))
                how += "+linear"
        r2 = lambda a: [round(float(v), 2) if np.isfinite(v) else None for v in a]  # noqa: E731
        rec = {"id": f"w{ed['el']['id']}_{ed['k']}", "way": ed["el"]["id"], "a": ed["a"], "b": ed["b"], "mode": mode,
               "cls": ed["cls"], "name": tg.get("name", ""), "ref": tg.get("ref", ""), "width": round(width, 2),
               "lanes": lanes, "oneway": tg.get("oneway") in ("yes", "1", "-1") or tg.get("junction") == "roundabout",
               "layer": int(num(tg.get("layer")) or 0), "structure": st, "bridge_name": tg.get("bridge:name", ""),
               "tunnel_name": tg.get("tunnel:name", ""), "length": round(ed["L"], 2), "solved": how,
               "en": [[round(float(x), 2), round(float(y), 2)] for x, y in pts], "s": r2(s), "z": r2(z),
               "ground": r2(ground)}
        if "deck_obs" in rec_extra:
            rec["deck_obs"] = r2(rec_extra["deck_obs"])
        if st == "tunnel":
            rec["cover"] = r2(rec_extra["cover"]); rec["tunnel_d"] = r2(rec_extra["tunnel_d"])
            rec["under_built_share"] = round(float(np.mean(rec_extra["under_built"])), 3)
            rec["chain"] = chain_of[ed["k"]]; rec["chain_length"] = round(chain_len[chain_of[ed["k"]]], 1)
        out_edges.append(rec)
    portals = find_portals(out_edges, portal_nodes, p)
    nodes = [{"id": nid, "e": round(float(npos[nid][0]), 2), "n": round(float(npos[nid][1]), 2), "z": round(float(nz[nid]), 2),
              "kind": nkind[nid], "deg": len(inc[nid]), "boundary": nid in boundary} for nid in npos]
    ctx.write_json("graph.json", {"nodes": nodes, "edges": out_edges, "portals": portals})
    by = defaultdict(float)
    for e in out_edges:
        by[f"{e['mode']}/{e['structure']}"] += e["length"]
    return {"nodes": len(nodes), "edges": len(out_edges), "portals": len(portals), "unsolved": unsolved,
            "km": {k: round(v / 1000, 2) for k, v in sorted(by.items())}}


def load(path):
    return json.loads((path / "graph.json").read_text())
