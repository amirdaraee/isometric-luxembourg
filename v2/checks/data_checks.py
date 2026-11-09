"""G0 data checks on the scene and the transport graph (spec: v2/docs/specs/checks.md).

Each function is a check stage: it measures, adds numbered entries to a Report and returns the result; a failing
"gate" entry fails the build. Thresholds come from params.json "checks" (and the section of the part checked).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import Point, Polygon, box

from v2.checks.framework import Report
from v2.config import params
from v2.config.camera import camera
from v2.data.geo import area_polygon
from v2.data.scene.buildings import footprints, load as load_buildings
from v2.data.scene.grid import Grid
from v2.data.scene.scene import part
from v2.data.scene.transport import clearance, deck_key, grade_key, load as load_graph
from v2.data.scene.water import load_polygons

VEHICLE = {"road", "rail", "tram", "funicular"}


def _arr(a):
    return np.array([np.nan if v is None else v for v in a], float)


# ------------------------------------------------------------------------------------------------ scope
def check_scope(ctx):
    r = Report("scope")
    c = ctx.params["checks"]
    poly = area_polygon(ctx.area)
    margin = params()["areas"][ctx.area]["margin_m"]
    sc = ctx.dep("scene")
    blds = load_buildings(part(sc, "buildings"))
    pts = [Polygon(b["footprint"][0][0]).representative_point() for b in blds]
    out = [b["id"] for b, p in zip(blds, pts) if not poly.buffer(c["scene_outside_tol_m"]).contains(p)]
    r.at_most("S1", "buildings whose footprint lies outside the area", len(out), 0, out)
    t = np.load(part(sc, "trees") / "trees.npz")
    ins = shapely.contains_xy(poly.buffer(c["scene_outside_tol_m"]), t["e"], t["n"])
    r.at_most("S2", "trees outside the area", int((~ins).sum()), 0)
    pl = json.loads((part(sc, "places") / "places.json").read_text())["places"]
    bad = [p["name"] for p in pl if not poly.buffer(c["scene_outside_tol_m"]).contains(Point(p["e"], p["n"]))]
    r.at_most("S3", "places outside the area", len(bad), 0, bad)
    g = load_graph(part(sc, "transport"))
    reach = poly.buffer(margin)
    far = [e["id"] for e in g["edges"] if not shapely.intersects(reach, shapely.linestrings(e["en"]))]
    r.at_most("S4", f"transport edges not touching the area + {margin} m", len(far), 0, far)
    T = np.load(part(sc, "terrain") / "terrain.npz")
    gb = Grid(T["mnt"], T["e0"], T["n0"], T["step"]).bounds()
    covered = box(*gb).contains(poly.buffer(margin * 0.9))
    r.add("S5", "terrain grid covers the area and its margin", covered, gb)
    fr = camera()["frame"]
    from v2.config.camera import en_to_px
    ring = np.array(poly.buffer(margin).exterior.coords)
    px, py = en_to_px(ring[:, 0], ring[:, 1], np.full(len(ring), 450.0))
    px2, py2 = en_to_px(ring[:, 0], ring[:, 1], np.full(len(ring), 180.0))
    ok = min(px.min(), px2.min()) >= 0 and min(py.min(), py2.min()) >= 0 and max(px.max(), px2.max()) < fr["width_px"] \
        and max(py.max(), py2.max()) < fr["height_px"]
    r.add("S6", "the area (z 180-450 m) lies inside the v2 pixel frame", ok, [round(float(px.min())), round(float(py.min()))])
    r.info("S7", "area km2", round(poly.area / 1e6, 3))
    return r.result()


# ------------------------------------------------------------------------------------------------ terrain
def check_terrain(ctx):
    r = Report("terrain")
    T = np.load(ctx.dep("scene_terrain") / "terrain.npz")
    m = json.loads((ctx.dep("scene_terrain") / "manifest.json").read_text())["summary"]
    cells = T["mnt"].size
    r.at_most("TR1", "share of terrain cells that had no data (filled)", m["holes_filled"]["mnt"] / cells, 0.001)
    r.at_most("TR2", "non-finite terrain cells after filling", int((~np.isfinite(T["mnt"])).sum()), 0)
    below = float(np.mean(T["mns"] < T["mnt"] - 0.5))
    r.at_most("TR3", "share of cells where the surface is > 0.5 m below the ground", below, 0.001)
    blds = load_buildings(ctx.dep("scene_buildings"))
    d = np.array([b["ground_z"] - b["terrain_z"] for b in blds if b["terrain_z"] is not None])
    tol = params()["buildings"]["terrain_tolerance_m"]
    med = float(np.median(np.abs(d))) if len(d) else 0.0
    r.at_most("TR4", "median |building ground - LiDAR terrain| (m)", round(med, 3), tol)
    r.info("TR5", "90th percentile |building ground - terrain| (m)", round(float(np.percentile(np.abs(d), 90)), 2) if len(d) else 0)
    r.info("TR6", "steep / cliff area (m2)", [m["steep_m2"], m["cliff_m2"]])
    r.info("TR7", "OSM walls and cliffs measured", [m["walls"], m["walls_km"]])
    return r.result()


# ------------------------------------------------------------------------------------------------ buildings
def check_buildings(ctx):
    r = Report("buildings")
    c = ctx.params["checks"]
    blds = load_buildings(ctx.dep("scene_buildings"))
    fps = footprints(blds)
    closed = all(r_[0] == r_[-1] for b in blds for g in b["footprint"] for r_ in g)
    r.add("B1", "every footprint ring is closed", closed)
    invalid = [b["id"] for b, f in zip(blds, fps) if not f.is_valid or f.is_empty]
    r.at_most("B2", "invalid or empty footprints", len(invalid), 0, invalid)
    shell = [b["id"] for b in blds if not b["roofs"] or len(b["walls"]) < 3]
    r.at_most("B3", "share of buildings without a roof or with fewer than 3 walls", len(shell) / max(len(blds), 1), 0.01, shell)
    tree = STRtree(fps)
    over = []
    for i, f in enumerate(fps):
        for j in tree.query(f):
            if j <= i:
                continue
            a = f.intersection(fps[j]).area
            if a > c["building_max_overlap_m2"] and a > c["building_max_overlap_share"] * min(f.area, fps[j].area):
                over.append([blds[i]["id"], blds[j]["id"], round(a, 1)])
    r.at_most("B4", "pairs of buildings overlapping (> 1 m2 and > 2% of the smaller)", len(over), 0, over)
    bad_h = [b["id"] for b in blds if not (0 < b["height"] <= 150) or b["ridge_z"] < b["eave_z"] - 0.01
             or b["eave_z"] < b["ground_z"] - 0.5]
    r.at_most("B5", "buildings with impossible heights (0 < h <= 150, ground <= eave <= ridge)", len(bad_h), 0, bad_h)
    ids = [b["id"] for b in blds]
    r.add("B6", "building ids unique", len(ids) == len(set(ids)), len(ids))
    shapes = defaultdict(int)
    for b in blds:
        shapes[b["roof_shape"]] += 1
    r.info("B7", "roof shapes", dict(shapes))
    return r.result()


# ------------------------------------------------------------------------------------------------ facades
def check_facades(ctx):
    r = Report("facades")
    f = json.loads((ctx.dep("scene_facades") / "facades.json").read_text())
    p, walls = f["rule"], f["walls"]
    outside, overlap, misrow, party_win, bad_floors = [], [], [], [], []
    lines = lambda n: [0.0] + [p["ground_floor_m"] + (k - 1) * p["floor_m"] for k in range(1, n)]  # noqa: E731
    for w in walls:
        if not w["windows"]:
            continue
        if w["party"]:
            party_win.append(w["wall"])
        poly = Polygon(w["outline"]) if len(w["outline"]) >= 4 else None
        if poly is not None and not poly.is_valid:
            poly = poly.buffer(0)
        rects = [box(*x) for x in w["windows"]]
        if poly is None or any(not poly.contains(b) for b in rects):
            outside.append(w["wall"])
        ws = sorted(w["windows"], key=lambda x: (x[1], x[0]))
        for a, b in zip(ws, ws[1:]):
            if abs(a[1] - b[1]) < 1e-6 and b[0] - a[2] < ctx.params["checks"]["facade_window_min_gap_m"] - 1e-6:
                overlap.append(w["wall"]); break
        rows = {round(x[1] - p["sill_m"], 3) for x in w["windows"]}
        allowed = {round(v, 3) for v in lines(w["floors"])}
        if not rows <= allowed:
            misrow.append(w["wall"])
        # the floor count must fit the wall: the top floor's line is below the eave
        if w["floors"] < 1 or lines(w["floors"])[-1] > w["height"] + 1e-6:
            bad_floors.append(w["wall"])
    r.at_most("F1", "walls with a window outside the wall outline", len(outside), 0, outside)
    r.at_most("F2", "walls with windows closer than the minimum gap", len(overlap), 0, overlap)
    r.at_most("F3", "walls whose window rows are not on their floor lines (straight rows)", len(misrow), 0, misrow)
    r.at_most("F4", "party walls with windows", len(party_win), 0, party_win)
    r.at_most("F5", "walls with more floors than their eave height allows", len(bad_floors), 0, bad_floors)
    blds = load_buildings(ctx.dep("scene_buildings"))
    with_win = {w["building"] for w in walls if w["windows"]}
    tall = [b for b in blds if b["height"] >= 5 and b["footprint_m2"] >= 40]
    share = sum(1 for b in tall if b["id"] in with_win) / max(len(tall), 1)
    r.at_least("F6", "share of buildings >= 5 m tall and >= 40 m2 with at least one window", round(share, 4), 0.9)
    r.info("F7", "walls, with windows, party walls, windows",
           [len(walls), sum(1 for w in walls if w["windows"]), sum(1 for w in walls if w["party"]), sum(len(w["windows"]) for w in walls)])
    return r.result()


# ------------------------------------------------------------------------------------------------ trees
def check_trees(ctx):
    r = Report("trees")
    p = params()["trees"]
    t = np.load(ctx.dep("scene_trees") / "trees.npz")
    fps = footprints(load_buildings(ctx.dep("scene_buildings")))
    water = load_polygons(ctx.dep("scene_water") / "water.json")
    ub = shapely.union_all(fps) if fps else None
    uw = shapely.union_all(water) if water else None
    in_b = int(shapely.contains_xy(ub, t["e"], t["n"]).sum()) if ub is not None else 0
    in_w = int(shapely.contains_xy(uw, t["e"], t["n"]).sum()) if uw is not None else 0
    r.at_most("TE1", "trees standing inside a building", in_b, ctx.params["checks"]["trees_max_inside"])
    r.at_most("TE2", "trees standing in water", in_w, ctx.params["checks"]["trees_max_inside"])
    blk = shapely.union_all([g for g in (ub, uw) if g is not None]) if (ub is not None or uw is not None) else None
    worst, ex = 0.0, []
    if blk is not None:
        discs = shapely.buffer(shapely.points(t["e"], t["n"]), t["crown_r"].astype(float), quad_segs=8)
        share = shapely.area(shapely.intersection(discs, blk)) / np.maximum(shapely.area(discs), 1e-9)
        share = np.where(t["crown_r"] > 0, share, 0)
        worst = float(share.max()) if len(share) else 0.0
        ex = [str(u) for u in t["uuid"][share > p["max_overlap_share"] + 0.02][:5]]
    r.at_most("TE3", "largest share of a crown over buildings or water", round(worst, 3), p["max_overlap_share"] + 0.02, ex)
    h = t["height"]
    r.add("TE4", f"heights within {p['min_height_m']}-{p['max_height_m']} m",
          bool(((h >= p["min_height_m"]) & (h <= p["max_height_m"])).all()), [float(h.min()), float(h.max())] if len(h) else None)
    T = np.load(ctx.dep("scene_terrain") / "terrain.npz") if "scene_terrain" in ctx.deps else None
    r.info("TE5", "trees", int(len(h)))
    return r.result()


# ------------------------------------------------------------------------------------------------ transport
def check_transport_profiles(ctx):
    r = Report("transport_profiles")
    c = ctx.params["checks"]
    tp = params()["transport"]
    g = load_graph(ctx.dep("scene_transport"))
    poly = area_polygon(ctx.area)
    N = {n["id"]: n for n in g["nodes"]}
    nonfinite, discont, jumps, jumps_path, grades, below_ground, deck_off, deep, above, relaxed = ([] for _ in range(10))
    deck_med = []
    for e in g["edges"]:
        z, s = _arr(e["z"]), _arr(e["s"])
        if not np.isfinite(z).all():
            nonfinite.append(e["id"]); continue
        for end, zz in ((e["a"], z[0]), (e["b"], z[-1])):
            if abs(zz - N[end]["z"]) > c["node_height_tol_m"]:
                discont.append([e["id"], end, round(zz - N[end]["z"], 2)])
        if len(z) < 2:
            continue
        ds = np.diff(s); dz = np.abs(np.diff(z))
        veh = e["mode"] in VEHICLE
        if e["structure"] == "elevator":
            continue
        cap = tp["deck_max_grade"][deck_key(e["mode"])] if e["structure"] == "bridge" else tp["max_grade"][grade_key(e["mode"])]
        limit = np.maximum(c["profile_max_step_m"], cap * ds + c["profile_max_step_extra_m"])
        if (dz > limit).any():
            (jumps if veh else jumps_path).append([e["id"], e["mode"], round(float(dz.max()), 2)])
        if "+grade" in e["solved"] or "+linear" in e["solved"]:
            relaxed.append([e["id"], e["mode"], e["structure"], e["name"], e["solved"]])
        if e["structure"] == "bridge" and veh:
            gr = _arr(e["ground"])
            if (z < gr - 0.5).any():
                below_ground.append(e["id"])
            obs = _arr(e.get("deck_obs", []))
            k = np.isfinite(obs)
            if k.sum() >= 3 and e["length"] >= 10:
                med = float(np.median(np.abs(z[k] - obs[k])))
                deck_med.append(med)
                if med > 0.5:
                    deck_off.append([e["id"], e["name"], round(med, 2)])
        if e["structure"] == "tunnel" and veh:
            cov, d = _arr(e["cover"]), _arr(e["tunnel_d"])
            need = clearance(e["mode"], tp) + c["tunnel_min_cover_m"]
            en = np.array(e["en"])
            in_area = shapely.contains_xy(poly, en[:, 0], en[:, 1])   # the cover (buildings) is known inside the area
            interior = (d >= c["portal_max_from_end_m"]) & in_area
            z = np.where(in_area, z, np.nan); cov = np.where(in_area, cov, np.nan)
            if (interior & (cov - z < need)).any():
                deep.append([e["id"], e["name"] or e["tunnel_name"], round(float(np.nanmin((cov - z)[interior])), 2)])
            # past the portal mouth (where the ground model shows the portal's cutting, not the cover)
            mouth = d < tp["abutment_ignore_m"]
            if (np.nan_to_num(np.where(mouth, np.nan, z - cov), nan=-1e9) > 1.0).any():
                above.append([e["id"], e["name"] or e["tunnel_name"], round(float(np.nanmax(z - cov)), 2)])
    r.at_most("P1", "edges with a missing height", len(nonfinite), 0, nonfinite)
    r.at_most("P2", f"edge ends off their node height (> {c['node_height_tol_m']} m)", len(discont), 0, discont)
    r.at_most("P3", "vehicle edges with a height jump between samples (beyond the grade cap)", len(jumps), 0, jumps)
    r.at_most("P4", "vehicle edges whose grade cap had to be relaxed", len([x for x in relaxed if x[1] in VEHICLE]), 0,
              [x for x in relaxed if x[1] in VEHICLE])
    r.at_most("P5", "vehicle bridge edges with the deck below the ground", len(below_ground), 0, below_ground)
    r.at_most("P6", "vehicle bridge edges whose deck is off the LiDAR surface (median > 0.5 m)", len(deck_off), 0, deck_off)
    r.at_most("P7", "vehicle tunnels (inside the area) not a clearance + cover below their cover beyond the portal zone", len(deep), 0, deep)
    r.at_most("P8", "vehicle tunnels (inside the area, past the portal mouth) rising more than 1 m above their cover", len(above), 0, above)
    zone = c["portal_max_from_end_m"]
    miss = [p for p in g["portals"] if p["mode"] in VEHICLE and p["chain_length"] >= 2 * zone
            and (not p["found"] or p["dist_m"] > zone) and poly.contains(Point(N[p["node"]]["e"], N[p["node"]]["n"]))]
    r.at_most("P9", f"portals of vehicle tunnels (>= {2 * zone:g} m, ends inside the area) not found within {zone:g} m of the tunnel end",
              len(miss), 0, [[m["edge"], m.get("dist_m")] for m in miss])
    r.info("P10", "paths/steps with a jump or relaxed grade (not gated: stairs and lifts are often mapped as paths)",
           [len(jumps_path), len([x for x in relaxed if x[1] not in VEHICLE])])
    r.info("P11", "median |deck - LiDAR surface| over bridge edges (m)", round(float(np.median(deck_med)), 3) if deck_med else None)
    r.info("P12", "portals found / total", [sum(p["found"] for p in g["portals"]), len(g["portals"])])
    return r.result()


def check_transport_graph(ctx):
    r = Report("transport_graph")
    c = ctx.params["checks"]
    g = load_graph(ctx.dep("scene_transport"))
    N = {n["id"]: n for n in g["nodes"]}
    missing = [e["id"] for e in g["edges"] if e["a"] not in N or e["b"] not in N]
    r.at_most("G1", "edges whose end nodes are missing", len(missing), 0, missing)
    # near misses: two vehicle edge ends within 0.5 m that are different nodes (should have been one junction)
    ends = [(e["a"], e["en"][0], e["mode"]) for e in g["edges"]] + [(e["b"], e["en"][-1], e["mode"]) for e in g["edges"]]
    pts = shapely.points([q[1] for q in ends])
    tree = STRtree(pts)
    near = set()
    for i, (nid, xy, mode) in enumerate(ends):
        if mode not in VEHICLE or N[nid]["deg"] != 1 or N[nid]["boundary"]:
            continue
        for j in tree.query(pts[i].buffer(0.5)):
            if ends[j][0] != nid and ends[j][2] in VEHICLE:
                near.add(tuple(sorted((nid, ends[j][0]))))
    r.at_most("G2", "vehicle dead ends within 0.5 m of another edge end (unjoined junctions)", len(near), 0, sorted(near))
    for gid, modes, title in (("G3", {"road"}, "roads"), ("G4", {"rail", "tram"}, "rail and tram")):
        eds = [e for e in g["edges"] if e["mode"] in modes]
        parent = {}

        def find(x):
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for e in eds:
            parent[find(e["a"])] = find(e["b"])
        comp_len, comp_bound = defaultdict(float), defaultdict(bool)
        for e in eds:
            k = find(e["a"])
            comp_len[k] += e["length"]
            comp_bound[k] |= N[e["a"]]["boundary"] or N[e["b"]]["boundary"]
        tot = sum(comp_len.values()) or 1.0
        big = max(comp_len, key=comp_len.get) if comp_len else None
        ok_len = sum(v for k, v in comp_len.items() if k == big or comp_bound[k])
        r.at_least(gid, f"share of {title} length connected (to the main network or out of the area)",
                   round(ok_len / tot, 4), c["graph_min_component_share"],
                   [[k, round(v, 1)] for k, v in comp_len.items() if k != big and not comp_bound[k]][:8])
    # bridges and tunnels joined at both ends to the network
    dead = lambda e: any(N[x]["deg"] == 1 and not N[x]["boundary"] for x in (e["a"], e["b"]))  # noqa: E731
    dangling = [e["id"] for e in g["edges"] if e["mode"] in VEHICLE and e["structure"] in ("bridge", "tunnel")
                and e["cls"] != "service" and dead(e)]
    r.at_most("G5", "vehicle bridges or tunnels with a dead end (driveways into garages excepted)", len(dangling), 0, dangling)
    r.info("G5b", "service roads (garage driveways) ending in a tunnel or on a bridge",
           [e["id"] for e in g["edges"] if e["cls"] == "service" and e["structure"] in ("bridge", "tunnel") and dead(e)])
    km = defaultdict(float)
    for e in g["edges"]:
        km[e["mode"]] += e["length"] / 1000
    r.info("G6", "km by mode", {k: round(v, 2) for k, v in sorted(km.items())})
    return r.result()


# ------------------------------------------------------------------------------------------------ structures
def check_structures(ctx):
    r = Report("structures")
    s = json.loads((ctx.dep("scene_structures") / "structures.json").read_text())
    g = load_graph(ctx.dep("scene_transport"))
    T = np.load(ctx.dep("scene_terrain") / "terrain.npz")
    mnt = Grid(T["mnt"], T["e0"], T["n0"], T["step"])
    vs = [v for v in s["viaducts"] if v["status"] != "outside area"]
    notok = [[v["id"], v["status"]] for v in vs if v["status"] != "ok"]
    r.at_most("V1", "viaducts in the area not modelled", len(notok), 0, notok)
    off, feet, piers_bad, arch_bad, length_bad = [], [], [], [], []
    E = {e["id"]: e for e in g["edges"]}
    for v in vs:
        if v["status"] != "ok":
            continue
        deck = np.array(v["deck"])
        # deck vs graph: nearest graph sample of the deck edges
        pts = np.concatenate([np.array(E[i]["en"]) for i in v["deck_edges"]])
        zs = np.concatenate([_arr(E[i]["z"]) for i in v["deck_edges"]])
        d = np.hypot(pts[:, None, 0] - deck[None, :, 0], pts[:, None, 1] - deck[None, :, 1])
        j = d.argmin(axis=0); close = d.min(axis=0) < v["width_m"] / 2 + 1
        if close.any():
            err = float(np.median(np.abs(deck[close, 2] - zs[j[close]])))
            if err > 0.3:
                off.append([v["id"], round(err, 2)])
        for p in v["piers"]:
            gz = mnt.sample(np.array([p["e"]]), np.array([p["n"]]))[0]
            if p["foot_z"] > gz + 0.5:
                feet.append([v["id"], p["i"], round(p["foot_z"] - gz, 2)])
            if not (p["foot_z"] + 1.0 <= p["top_z"] < p["deck_z"]):
                piers_bad.append([v["id"], p["i"]])
        for a in v["arches"]:
            if a.get("abutment"):
                continue
            if not (a["spring_z"] <= a["crown_z"] < max(q[2] for q in v["deck"])):
                arch_bad.append([v["id"], a["i"]])
        rel = abs(v["length_model_m"] - v["length_documented_m"]) / v["length_documented_m"]
        if rel > 0.15:
            length_bad.append([v["id"], v["length_model_m"], v["length_documented_m"]])
    r.at_most("V2", "viaduct decks off the transport graph (median > 0.3 m)", len(off), 0, off)
    r.at_most("V3", "piers whose foot is above the ground (> 0.5 m)", len(feet), 0, feet)
    r.at_most("V4", "piers not between ground + 1 m and the deck", len(piers_bad), 0, piers_bad)
    r.at_most("V5", "arches with the crown above the deck or the springing above the crown", len(arch_bad), 0, arch_bad)
    r.at_most("V6", "viaducts whose modelled length is off the documented length by > 15%", len(length_bad), 0, length_bad)
    r.info("V7", "modelled vs documented height (m)", [[v["id"], v.get("height_model_m"), v.get("height_documented_m")] for v in vs])
    return r.result()


# ------------------------------------------------------------------------------------------------ transit
def check_transit(ctx):
    r = Report("transit")
    c = ctx.params["checks"]
    t = json.loads((ctx.dep("scene_transit") / "transit.json").read_text())
    sh = t["shapes"]
    n_in = sum(s["samples_in_area"] for s in sh); n_cov = sum(s["covered"] for s in sh)
    share = n_cov / n_in if n_in else 1.0
    r.at_least("TT1", "share of GTFS tram and train track in the area matched onto the rail graph", round(share, 4),
               c["transit_min_match_share"], [[s["shape"], s["lines"], s["share"]] for s in sh if (s["share"] or 0) < 0.99])
    near = sum(s["near_share"] * s["samples_in_area"] for s in sh if s["near_share"] is not None) / n_in if n_in else 1.0
    r.at_least("TT2", "share of GTFS samples within 17 m of their matched rail path", round(near, 4), 0.9)
    no_run = [s["shape"] for s in sh if not s["runs"]]
    r.at_most("TT3", "shapes in the area with no matched run", len(no_run), 0, no_run)
    r.info("TT4", "shapes by kind", {k: sum(1 for s in sh if s["kind"] == k) for k in ("tram", "train", "funicular")})
    return r.result()


# ------------------------------------------------------------------------------------------------ places
def check_places(ctx):
    r = Report("places")
    from v2.config.camera import to_screen
    pl = json.loads((ctx.dep("scene_places") / "places.json").read_text())["places"]
    v = camera()["v1"]
    errs, ex = [], []
    for p in pl:
        sx, sy = to_screen(p["e"], p["n"], p["z_v1"])
        x, y = (sx - v["sx0"]) / v["mpp"], (v["sy1"] - sy) / v["mpp"]
        d = math.hypot(x - p["v1_px"][0], y - p["v1_px"][1])
        errs.append(d)
        if d > 0.75:
            ex.append([p["name"], round(d, 2)])
    errs = np.array(errs) if errs else np.zeros(1)
    # v1 stored whole pixels: half a pixel of rounding can move a ray off a cliff edge cell, hence the max allowance
    r.at_most("PL1", "95th percentile round-trip error back to v1 pixels (px)", round(float(np.percentile(errs, 95)), 3), 0.75, ex)
    r.at_most("PL2a", "largest round-trip error back to v1 pixels (px; cliff edges)", round(float(errs.max()), 3), 4.0, ex)
    dz = [abs(p["z"] - p["z_v1"]) for p in pl if p["z"] is not None]
    r.info("PL2", "median |v2 terrain - v1 terrain| at the places (m)", round(float(np.median(dz)), 2) if dz else None)
    r.info("PL3", "places, landmarks", [len(pl), sum(1 for p in pl if p["source"] == "landmark")])
    return r.result()
