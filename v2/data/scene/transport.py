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
            "road", "raceway"}
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


def edge_clearance(mode, cls, tags, structure_, p):
    """The headroom a tunnel edge must give: its OSM maxheight when tagged (the signed clearance), else a car park's
    for service roads underground (garage ramps and aisles), else the mode's (road 4.5 m, rail 5.5 m, tram 4.5 m)."""
    mh = num(tags.get("maxheight")) if tags.get("maxheight") not in (None, "default", "none", "below_default") else None
    if mh is not None and 1.5 <= mh <= 7.0:
        return mh
    if structure_ == "tunnel" and mode == "road" and cls == "service":
        return p["clearance_m"]["service_tunnel"]
    return clearance(mode, p)


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
    keep = [shapely.intersects(select, shapely.linestrings(ed["en"])) for ed in edges]
    sel = [ed for ed, k in zip(edges, keep) if k]
    dropped_ends = {x for ed, k in zip(edges, keep) if not k for x in (ed["a"], ed["b"])}
    kept_ends = {x for ed in sel for x in (ed["a"], ed["b"])}
    boundary |= dropped_ends & kept_ends            # the network goes on outside the selection here
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
        # each incident edge's own estimate of this end: its profile solved with free ends (robust to a wall or
        # a kerb next to the node, where point samples of the ground model jump)
        def ends(structs):
            # vehicle ways set the level of a node they share with paths (a path leaving a bridge end down a ramp
            # or a stair must not pull the road down with it)
            use = [ed for ed in eds if ed["structure"] in structs and ed.get("free") is not None]
            veh = [ed for ed in use if ed["mode"] in ("road", "rail", "tram", "funicular")]
            v = [ed["free"][0 if ed["a"] == nid else 1] for ed in (veh or use)]
            return [x for x in v if np.isfinite(x)]
        if st <= {"ground", "passage", "indoor", "elevator"}:
            kind[nid] = "ground"
            v = ends(("ground", "passage", "indoor"))
            z[nid] = float(np.median(v)) if v else float(np.nanmedian(mnt.sample(x + off[:, 0], y + off[:, 1])))
        elif st & {"ground", "passage", "indoor"}:
            # an abutment or a portal: the level of the open approach (the ground model under the first metres of a
            # span already dips into the valley, and above a portal it is the cliff)
            kind[nid] = "abutment"
            v = ends(("ground", "passage", "indoor"))
            approach = float(np.median(v)) if v else float(np.nanmedian(mnt.sample(x + off[:, 0], y + off[:, 1])))
            d = ends(("bridge",))
            deck = float(np.median(d)) if d else math.nan
            # at a bridge end the deck's own surface is the road level; the ground model there is cut out. Keep the
            # approach's level only when the deck reading is far off (a tree over the deck end)
            # (an approach too short to say anything leaves only the raw ground model, which the deck beats)
            z[nid] = deck if np.isfinite(deck) and (not v or abs(deck - approach) <= p["abutment_agree_m"]) else approach
        elif "bridge" in st and "tunnel" not in st:
            kind[nid] = "deck"
            v = ends(("bridge",))
            r = p["node_search_m"] / 3
            z[nid] = float(np.median(v)) if v else float(np.nanmedian(mns.sample(x + off[:, 0] * r, y + off[:, 1] * r)))
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
    caps = defaultdict(list)
    for ed in edges:
        if ed["mode"] not in ("road", "rail", "tram", "funicular"):
            continue                 # paths and steps may be steep (stairs): they do not constrain the nodes
        g = p["deck_max_grade"][deck_key(ed["mode"])] if ed["structure"] == "bridge" else p["max_grade"][grade_key(ed["mode"])]
        cap = 0.9 * g * float(np.hypot(*np.diff(ed["en"], axis=0).T).sum())   # 10% headroom for the profile
        caps[ed["a"]].append((ed["b"], cap)); caps[ed["b"]].append((ed["a"], cap))
    # project the node heights into the band their vehicle edges' grade caps allow: the unobserved ones (tunnels)
    # freely, the observed ones only where two estimates disagree by a little more than the cap allows (short edges)
    for _ in range(60):
        moved = 0.0
        for nid in est:
            lo = max((est[m] - c for m, c in caps[nid] if np.isfinite(est[m])), default=-np.inf)
            hi = min((est[m] + c for m, c in caps[nid] if np.isfinite(est[m])), default=np.inf)
            v = min(max(est[nid], lo), hi) if lo <= hi else (lo + hi) / 2
            moved = max(moved, abs(v - est[nid])); est[nid] = v
        if moved < 1e-3:
            break
    return est, kind, pos, inc


def project_grades(est, edges, p, movable, iters=60):
    """Moves the `movable` node heights into the band their vehicle edges' grade caps allow (10% headroom)."""
    caps = defaultdict(list)
    for ed in edges:
        if ed["mode"] not in ("road", "rail", "tram", "funicular"):
            continue
        g = p["deck_max_grade"][deck_key(ed["mode"])] if ed["structure"] == "bridge" else p["max_grade"][grade_key(ed["mode"])]
        cap = 0.9 * g * float(np.hypot(*np.diff(ed["en"], axis=0).T).sum())
        caps[ed["a"]].append((ed["b"], cap)); caps[ed["b"]].append((ed["a"], cap))
    for _ in range(iters):
        moved = 0.0
        for nid in movable:
            lo = max((est[m] - c for m, c in caps[nid] if np.isfinite(est[m])), default=-np.inf)
            hi = min((est[m] + c for m, c in caps[nid] if np.isfinite(est[m])), default=np.inf)
            if lo > hi:
                continue                       # the caps cannot all be met here: leave it (check P4 will say)
            v = min(max(est[nid], lo), hi)
            moved = max(moved, abs(v - est[nid])); est[nid] = v
        if moved < 1e-3:
            break


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
            need = r0["clearance_m"]
            # walk into the tunnel network (every branch, nearest first) until the vehicle is a clearance under cover
            hit = None
            heap = [(0.0, 0, r0["id"], r0, node)]
            seen, tie = set(), 1
            while heap:
                walked, _, _, cur, at = heapq.heappop(heap)
                if cur["id"] in seen or walked > 500:
                    continue
                seen.add(cur["id"])
                fwd = cur["a"] == at
                zs, cs, ss = cur["z"], cur["cover"], cur["s"]
                order = range(len(zs)) if fwd else range(len(zs) - 1, -1, -1)
                for i in order:
                    if zs[i] is not None and cs[i] is not None and cs[i] - zs[i] >= need:
                        d = walked + (ss[i] if fwd else ss[-1] - ss[i])
                        if hit is None or d < hit[2]:
                            hit = (cur, i, d)
                        break
                nxt_at = cur["b"] if fwd else cur["a"]
                if nxt_at in portal_nodes:
                    continue
                for r in by_node[nxt_at]:
                    if r["id"] not in seen:
                        heapq.heappush(heap, (walked + cur["length"], tie, r["id"], r, nxt_at)); tie += 1
            rec = {"node": node, "edge": r0["id"], "mode": r0["mode"], "chain": r0["chain"],
                   "chain_length": r0["chain_length"], "found": hit is not None}
            if hit:
                c, i, d = hit
                rec.update(dist_m=round(d, 1), at_edge=c["id"], e=c["en"][i][0], n=c["en"][i][1], z=c["z"][i],
                           cover=c["cover"][i])
            out.append(rec)
    return out


class Blockers:
    """Where the LiDAR surface model does not see a road or deck: under a building, under a tree crown (survey
    crowns), or under a bridge of a higher OSM layer."""

    def __init__(self, footprints_=(), crowns=None, bridges=()):
        self.fp = shapely.union_all(list(footprints_)) if len(footprints_) else None
        if self.fp is not None:
            shapely.prepare(self.fp)
        self.crowns = None
        if crowns is not None and len(crowns[0]):
            from scipy.spatial import cKDTree
            self.crowns = (cKDTree(np.column_stack(crowns[:2])), np.asarray(crowns[2], float))
        self.by_layer = {}
        layers = sorted({lay for lay, _ in bridges})
        for lay in layers:
            above = [g for l2, g in bridges if l2 > lay]
            self.by_layer[lay] = shapely.union_all(above) if above else None
        self.top = max(layers) if layers else 0

    def mask(self, pts, layer=None):
        m = np.zeros(len(pts), bool)
        if self.fp is not None:
            m |= shapely.contains_xy(self.fp, pts[:, 0], pts[:, 1])
        if self.crowns is not None:
            tree, r = self.crowns
            d, i = tree.query(pts, k=8, distance_upper_bound=float(r.max()) if len(r) else 1.0)
            ok = np.isfinite(d)
            rr = np.where(ok, r[np.minimum(i, len(r) - 1)], 0.0)
            m |= (ok & (d < rr)).any(axis=1)
        if layer is not None:
            above = self.by_layer.get(layer)
            if above is not None and not above.is_empty:
                m |= shapely.contains_xy(above, pts[:, 0], pts[:, 1])
        return m


def prepare(ed, mnt, mns, p, special, blockers=None, abutments=frozenset(), deck_ends=None):
    """Samples, ground and deck observations of an edge, and its profile with free ends (pass 1).

    Next to an abutment or a portal (`special` nodes) the ground model is not the road: ACT cuts bridges out of it and
    the cut and the OSM node rarely agree within a few metres, and above a portal it is the cliff. Ground samples
    within abutment_ignore_m of such a node get no weight; the profile carries the approach's level to the node."""
    tg = ed["el"].get("tags", {})
    ed["width"], ed["lanes"] = width_lanes(tg, ed["cls"], ed["mode"], p)
    pts, s = resample(ed["en"], p["sample_m"])
    ed["pts"], ed["s"] = pts, s
    ed["ds"] = ds = float(s[1] - s[0]) if len(s) > 1 else 0.0
    nrm = normals(pts)
    lat = np.array(p["lateral_samples"]) * ed["width"]
    ed["ground"] = np.nanmedian(np.stack([mnt.sample(pts[:, 0] + nrm[:, 0] * o, pts[:, 1] + nrm[:, 1] * o) for o in lat]), axis=0)
    ed["free"] = None
    st, mode = ed["structure"], ed["mode"]
    w = np.ones(len(s))
    ed["on_structure_m"] = 0.0
    if st in ("ground", "passage", "indoor"):
        if ed["a"] in special:
            w[s < p["abutment_ignore_m"]] = 0.0
        if ed["b"] in special:
            w[s > s[-1] - p["abutment_ignore_m"]] = 0.0
        # ACT's cut-out of a bridge from the ground model often runs past OSM's bridge tag: the approach is still on
        # the structure (a ramp, a retained embankment cut out with the deck). From an abutment, while the surface
        # model stands clear above the ground model and nothing covers it, the road is the surface model.
        if mode in ("road", "rail", "tram") and (ed["a"] in abutments or ed["b"] in abutments):
            surf = np.nanmedian(np.stack([mns.sample(pts[:, 0] + nrm[:, 0] * o, pts[:, 1] + nrm[:, 1] * o) for o in lat]), axis=0)
            free = ~blockers.mask(pts) if blockers is not None else np.ones(len(s), bool)
            raised = (surf - ed["ground"] > p["approach_structure_min_m"]) & free & np.isfinite(surf)
            cap = p["max_grade"][grade_key(mode)] * max(ed["ds"], 0.1) + 0.3
            for end, order in (("a", range(len(s))), ("b", range(len(s) - 1, -1, -1))):
                if ed[end] not in abutments:
                    continue
                # it must start at the deck's own level at the abutment and run on smoothly (a wall, a parapet or a
                # hedge beside a street is not the street)
                lvl = (deck_ends or {}).get(ed[end], [])
                run = []
                for i in order:
                    if not raised[i]:
                        break
                    if not run:
                        if not lvl or min(abs(surf[i] - v) for v in lvl) > p["approach_deck_tol_m"]:
                            break
                    elif abs(surf[i] - surf[run[-1]]) > cap:
                        break
                    run.append(i)
                if run:
                    ed["ground"] = ed["ground"].copy()
                    ed["ground"][run] = surf[run]
                    w[run] = 1.0
                    ed["on_structure_m"] += float(abs(s[run[-1]] - s[run[0]]))
    ed["w"] = w
    # where samples have no weight, hold the nearest observed level (a weak prior, so the profile is defined there)
    ok = (w > 0) & np.isfinite(ed["ground"])
    ed["hold"] = np.interp(s, s[ok], ed["ground"][ok]) if ok.any() else None
    sm = max(1, int(round(p["smooth_window_m"] / max(ds, 0.1)))) | 1
    if st == "bridge":
        dl = np.array([-1, 0, 1]) * max(0.0, ed["width"] / 2 - p["deck_lateral_m"])
        # the surface model is the deck only where nothing stands over it (a building, a crown, a higher bridge):
        # each of the three samples across the deck is dropped where something does
        lay = int(num(tg.get("layer")) or 1)
        raw, kept = [], []
        for o in dl:
            q = np.column_stack((pts[:, 0] + nrm[:, 0] * o, pts[:, 1] + nrm[:, 1] * o))
            v = mns.sample(q[:, 0], q[:, 1])
            raw.append(v)
            m = blockers.mask(q, layer=lay) if blockers is not None else np.zeros(len(s), bool)
            kept.append(np.where(m, np.nan, v))
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ed["deck_raw"] = np.nanmedian(np.stack(raw), axis=0)
            deck = np.nanmedian(np.stack(kept), axis=0)
        blocked = ~np.isfinite(deck)
        ed["deck_blocked"] = blocked
        ed["deck"] = deck
        okd = np.isfinite(deck)
        ed["deck_hold"] = np.interp(s, s[okd], deck[okd]) if okd.any() else None
        z = solve(deck, ds, p["deck_max_grade"][deck_key(mode)], lo_soft=ed["ground"] + p["deck_min_above_ground_m"],
                  prior=ed["deck_hold"], prior_w=0.01, bin_m=p["profile_bin_m"], smooth_n=sm) if okd.any() else None
    elif st in ("ground", "passage", "indoor"):
        z = solve(ed["ground"], ds, p["max_grade"][grade_key(mode)], w=w, prior=ed["hold"], prior_w=0.01,
                  bin_m=p["profile_bin_m"], smooth_n=sm) if w.any() else None
    else:
        z = None
    if z is not None and len(z):
        ed["free"] = (float(z[0]), float(z[-1]))


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
    from v2.data.scene.buildings import footprints, load as load_buildings
    fps = list(footprints(load_buildings(ctx.dep("scene_buildings"))))
    t = np.load(ctx.dep("fetch_trees") / "trees.npz")       # every surveyed crown (not only the scene's thinned ones)
    keep = mnt.inside(t["e"], t["n"]) & (t["h"] >= 2.0)
    crowns = (t["e"][keep], t["n"][keep], t["cmax"][keep] / 2.0 + p["crown_block_margin_m"])  # the widest extent
    nodes, out_edges, portals, unsolved = solve_graph(edges, boundary, mnt, mns, p, chk, fps, crowns)
    ctx.write_json("graph.json", {"nodes": nodes, "edges": out_edges, "portals": portals})
    by = defaultdict(float)
    for e in out_edges:
        by[f"{e['mode']}/{e['structure']}"] += e["length"]
    return {"nodes": len(nodes), "edges": len(out_edges), "portals": len(portals), "grade_relaxed": unsolved,
            "approach_on_structure_m": round(sum(e.get("on_structure_m", 0) for e in out_edges), 1),
            "km": {k: round(v / 1000, 2) for k, v in sorted(by.items())}}


def solve_graph(edges, boundary, mnt, mns, p, chk, footprints_=(), crowns=None):
    """Heights for a list of edges (from ways_to_edges): node heights, then each edge's profile, then portals.
    crowns: (e, n, radius) of the tree survey, to know where the surface model sees a crown, not a deck."""
    for ed in edges:
        tg = ed["el"].get("tags", {})
        ed["structure"] = structure(tg, p)
        if ed["mode"] == "elevator":
            ed["structure"] = "elevator"
        ed["L"] = float(np.hypot(*np.diff(ed["en"], axis=0).T).sum())
    sts = defaultdict(set)
    for ed in edges:
        sts[ed["a"]].add(ed["structure"]); sts[ed["b"]].add(ed["structure"])
    special = {nid for nid, st in sts.items() if st & {"ground", "passage", "indoor"} and st & {"bridge", "tunnel"}}
    abutments = {nid for nid, st in sts.items() if st & {"ground", "passage", "indoor"} and "bridge" in st}
    bridges = [(int(num(ed["el"].get("tags", {}).get("layer")) or 1),
                shapely.linestrings(ed["en"]).buffer(width_lanes(ed["el"].get("tags", {}), ed["cls"], ed["mode"], p)[0] / 2 + 1.0))
               for ed in edges if ed["structure"] == "bridge"]
    blockers = Blockers(footprints_, crowns, bridges)
    for ed in edges:
        ed["clearance"] = edge_clearance(ed["mode"], ed["cls"], ed["el"].get("tags", {}), ed["structure"], p)
    # bridges first: their decks' levels at the abutments tell where an approach still stands on the structure
    deck_ends = defaultdict(list)
    for ed in edges:
        if ed["structure"] == "bridge":
            prepare(ed, mnt, mns, p, special, blockers, abutments)
            if ed["free"] is not None:
                deck_ends[ed["a"]].append(ed["free"][0]); deck_ends[ed["b"]].append(ed["free"][1])
    for ed in edges:
        if ed["structure"] != "bridge":
            prepare(ed, mnt, mns, p, special, blockers, abutments, deck_ends)
    nz, nkind, npos, inc = node_heights(edges, mnt, mns, p)
    tdist, portal_nodes = tunnel_distances(edges, inc, nkind)
    # tunnel nodes have no observation: hold them under their cover (the earth, or what is built over them) by the
    # clearance of their tunnels + the minimum cover, ramped in from the portals, then back within the grade caps
    built0 = list(footprints_) + [g for _, g in bridges]
    built0 = shapely.union_all(built0) if built0 else None
    moved = False
    for nid, kd in nkind.items():
        if kd not in ("tunnel", "mixed"):
            continue
        x, y = npos[nid]
        gz = float(mnt.sample(np.array([x]), np.array([y]))[0])
        cov = gz
        if built0 is not None and shapely.contains_xy(built0, x, y):
            cov = max(gz, float(mns.sample(np.array([x]), np.array([y]))[0]))
        tun = [ed for ed in inc[nid] if ed["structure"] == "tunnel"]
        if not tun or not np.isfinite(cov):
            continue
        need = min(ed["clearance"] for ed in tun) + chk["tunnel_min_cover_m"] + 0.5
        ramp = min(1.0, tdist.get(nid, 0.0) / chk["portal_max_from_end_m"])
        hi = cov - need * ramp
        if nz[nid] > hi:
            nz[nid] = hi
            moved = True
    if moved:
        project_grades(nz, edges, p, movable={nid for nid, kd in nkind.items() if kd in ("tunnel", "mixed")})
    chain_of, chain_len = tunnel_chains(edges)
    # what covers a tunnel: the earth (MNT), or a building or bridge deck built over it (then the surface, MNS)
    built = list(footprints_)
    built += [shapely.linestrings(ed["en"]).buffer(4.0) for ed in edges if ed["structure"] == "bridge"]
    built = shapely.union_all(built) if built else None
    out_edges, portals, unsolved = [], [], 0
    for ed in edges:
        tg = ed["el"].get("tags", {})
        mode, st = ed["mode"], ed["structure"]
        width, lanes, pts, s, ds, ground = ed["width"], ed["lanes"], ed["pts"], ed["s"], ed["ds"], ed["ground"]
        z0, z1 = nz[ed["a"]], nz[ed["b"]]
        rec_extra = {}
        ed["clearance"] = ed.get("clearance", clearance(mode, p))
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
                deck = ed["deck"]
                lin = np.linspace(z0, z1, len(s))
                prior = ed["deck_hold"] if ed.get("deck_hold") is not None else lin
                z = solve(deck, ds, p["deck_max_grade"][deck_key(mode)], lo_soft=ground + p["deck_min_above_ground_m"],
                          prior=prior, prior_w=0.01, **kw)
                rec_extra["deck_obs"] = deck
                how = "mns"
            elif st == "tunnel":
                need = ed["clearance"] + chk["tunnel_min_cover_m"]
                ramp = np.clip(tun_d / chk["portal_max_from_end_m"], 0, 1)
                hi_soft = cover - (need + 0.5) * ramp     # aim a little deeper than the check (smoothing)
                lin = np.linspace(z0, z1, len(s))
                z = solve(np.full(len(s), np.nan), ds, grade, prior=lin, prior_w=0.01, hi_soft=hi_soft, **kw)
                how = "tunnel"
            else:
                z = solve(ground, ds, grade, w=ed["w"], prior=ed["hold"], prior_w=0.01, **kw)
                how = "mnt"
            relax = 1.0
            while z is None and relax < 16:
                # the pinned ends cannot be joined within the grade cap: relax the cap, and say so
                relax *= 2
                kw2 = dict(kw)
                if st == "bridge":
                    z = solve(deck, ds, p["deck_max_grade"][deck_key(mode)] * relax, lo_soft=ground + p["deck_min_above_ground_m"],
                              prior=prior, prior_w=0.01, **kw2)
                elif st == "tunnel":
                    z = solve(np.full(len(s), np.nan), ds, grade * relax, prior=lin, prior_w=0.01, hi_soft=hi_soft, **kw2)
                else:
                    z = solve(ground, ds, grade * relax, w=ed["w"], prior=ed["hold"], prior_w=0.01, **kw2)
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
        rec["clearance_m"] = round(float(ed["clearance"]), 2)
        if ed.get("on_structure_m"):
            rec["on_structure_m"] = round(ed["on_structure_m"], 1)
        if "deck_obs" in rec_extra:
            rec["deck_obs"] = r2(rec_extra["deck_obs"])
            rec["deck_raw"] = r2(ed["deck_raw"])
            rec["deck_blocked_share"] = round(float(np.mean(ed["deck_blocked"])), 3)
        if st == "tunnel":
            rec["cover"] = r2(rec_extra["cover"]); rec["tunnel_d"] = r2(rec_extra["tunnel_d"])
            rec["under_built_share"] = round(float(np.mean(rec_extra["under_built"])), 3)
            rec["chain"] = chain_of[ed["k"]]; rec["chain_length"] = round(chain_len[chain_of[ed["k"]]], 1)
        out_edges.append(rec)
    portals = find_portals(out_edges, portal_nodes, p)
    nodes = [{"id": nid, "e": round(float(npos[nid][0]), 2), "n": round(float(npos[nid][1]), 2), "z": round(float(nz[nid]), 2),
              "kind": nkind[nid], "deg": len(inc[nid]), "boundary": nid in boundary} for nid in npos]
    return nodes, out_edges, portals, unsolved


def load(path):
    return json.loads((path / "graph.json").read_text())
