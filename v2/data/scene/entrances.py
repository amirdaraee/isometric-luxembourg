"""Doors and shop fronts on the facade layout (spec: v2/docs/specs/facades.md, "Doors and shop fronts").

Decided at the G0 review (research/v2/DECISIONS.md, 9 Nov): doors and shop fronts before the bake-off, from OSM where
it is mapped, by rule where it is not; ground-floor windows give way to them; dormers later.

  1. Street-facing walls: a wall (not a party wall, at least min_wall_len_m long and min_wall_height_m high, and able
     to take a door somewhere along its bottom) whose middle is within street_max_m of a street a person can walk
     from (any road but motorways and trunks, pedestrian streets, footways, living streets, steps) and whose outward
     normal points at it (cosine >= street_facing_cos).
  2. OSM doors: every entrance=* node within entrance_max_m of a building's outline becomes a door on that building's
     nearest wall (if that is a party wall, the next nearest), at the node's position along it. entrance=garage is a
     garage door; entrance=main is wider.
  3. OSM shops: a shop=*, craft=* or commercial amenity POI inside a building or within poi_max_m of it makes a shop
     front on that building's street-facing wall nearest the POI: the ground-floor bays within shop_reach_m of the
     POI along the wall (all bays of a wall of two bays or fewer), merged.
  4. Commercial streets: a named street (roads and pedestrian streets, not footways, steps or driveways), at least
     commercial_min_length_m long, with at least commercial_min_pois POIs within commercial_reach_m and at least
     commercial_min_per_km per km of its length. Every street-facing wall onto it at least shopfront_min_wall_m
     long gets a shop front across its ground-floor bays.
  5. Rule doors: a building with a street-facing wall but no door on one gets a door on its longest street-facing
     wall, in the bay nearest the wall's middle. A building without a street-facing wall gets one on its longest
     outside wall, recorded as such.
  6. Doors stand on the bottom of the wall outline at their position (the ground, as LoD2 walls follow it), shop fronts
     span from it to at most shopfront_h_m above it, below the first floor line. Both must fit inside the outline
     (shrunk by inset_m at the sides and top); a door inside a shop front is the shop's door.
  7. Ground-floor windows that a door or a shop front overlaps (with door_window_gap_m) are removed.
"""
from __future__ import annotations

import json

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import LineString, Point, box

COMMERCIAL_AMENITY = {"restaurant", "cafe", "bar", "pub", "fast_food", "bank", "pharmacy", "ice_cream", "bureau_de_change",
                      "biergarten", "food_court", "post_office", "cinema", "theatre", "nightclub", "veterinary", "dentist",
                      "doctors", "clinic", "car_rental", "bicycle_rental"}
COMMERCIAL_STREET_CLASSES = {"primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "pedestrian",
                             "primary_link", "secondary_link", "tertiary_link", "road"}
WALKABLE = {"primary", "secondary", "tertiary", "unclassified", "residential", "living_street", "service", "pedestrian",
            "footway", "path", "steps", "cycleway", "primary_link", "secondary_link", "tertiary_link", "busway", "road",
            "track", "corridor"}

QUERY = """[out:json][timeout:300][bbox:{bbox}];
(node["entrance"]; node["door"];
 node["shop"]; way["shop"]; node["craft"]; way["craft"];
 node["amenity"]; way["amenity"];);
out center tags;"""


def fetch_osm_pois(ctx):
    """OSM entrances, shops, crafts and amenities with their position (Overpass, ODbL), over the commune."""
    from v2.data.fetch import overpass
    from v2.data.geo import area_bbox_lonlat
    p = ctx.params
    bbox = area_bbox_lonlat(p["extent_area"], p["margin_m"])
    q = QUERY.format(bbox=overpass.bbox_str(bbox))
    d = overpass.run(q)
    d["query"] = q
    ctx.write_json("pois.json", d)
    n = {"entrance": 0, "shop": 0, "amenity": 0, "craft": 0}
    for el in d["elements"]:
        for k in n:
            if k in el.get("tags", {}):
                n[k] += 1
    return {"elements": len(d["elements"]), "by_key": n, "osm_timestamp": d.get("osm3s", {}).get("timestamp_osm_base")}


def poi_points(pois_json):
    """(entrances, shops) as lists of (e, n, tags, osm id) in LUREF."""
    from v2.data.geo import lonlat_to_en
    ent, shop = [], []
    for el in pois_json["elements"]:
        tg = el.get("tags", {})
        lon, lat = (el.get("lon"), el.get("lat")) if el["type"] == "node" else (el.get("center", {}).get("lon"), el.get("center", {}).get("lat"))
        if lon is None:
            continue
        e, n = lonlat_to_en(lon, lat)
        oid = f"{el['type']}/{el['id']}"
        if el["type"] == "node" and ("entrance" in tg or tg.get("door") not in (None, "no")) and tg.get("entrance") != "no":
            ent.append((e, n, tg, oid))
        if "shop" in tg or "craft" in tg or tg.get("amenity") in COMMERCIAL_AMENITY:
            shop.append((e, n, tg, oid))
    return ent, shop


def streets(graph):
    """Walkable street edges: (LineString, name or id, cls)."""
    out = []
    for e in graph["edges"]:
        if e["cls"] in WALKABLE and e["structure"] in ("ground", "bridge", "passage"):
            out.append((LineString(e["en"]), e["name"] or e["id"], e["cls"]))
    return out


def bottom_at(poly, u0, u1):
    """The highest bottom of the outline between u0 and u1 (where something standing on the ground starts)."""
    vals = []
    for u in np.linspace(u0, u1, 5):
        x = poly.intersection(LineString([(u, -1e3), (u, 1e4)]))
        if not x.is_empty:
            vals.append(x.bounds[1])
    return max(vals) if vals else None


def bay_centres(L, p):
    usable = L - 2 * p["edge_margin_m"]
    n = int(usable // p["bay_m"]) if usable >= p["bay_m"] else 1
    pitch = usable / n if usable > 0 else L
    return np.array([L / 2 + (i - (n - 1) / 2) * pitch for i in range(n)]), pitch


def fits(poly, rect, inset):
    """The rectangle lies in the outline shrunk by `inset` at the sides and top (its bottom may touch the outline)."""
    u0, v0, u1, v1 = rect
    shrunk = box(u0 - inset, v0 + 0.01, u1 + inset, v1 + inset)
    return poly.buffer(0.02).contains(shrunk)


def place(walls, blds, fps, graph, pois_json, p):
    """Adds "doors" and "shopfronts" to the wall records (facades.json) and removes the ground-floor windows they
    replace. Returns a summary and the list of OSM entrances that could not be placed, with the reason."""
    ent, shops = poi_points(pois_json)
    st = streets(graph)
    st_geoms = [g for g, _, _ in st]
    st_tree = STRtree(st_geoms) if st_geoms else None
    fp_tree = STRtree(fps)
    # walls per building, with their frame
    by_b = {}
    for i, w in enumerate(walls):
        by_b.setdefault(w["b"], []).append(i)
        w["doors"], w["shopfronts"] = [], []
        (e0, n0, z0), (e1, n1, _) = w["base"]
        w["_seg"] = LineString([(e0, n0), (e1, n1)])
        w["street"] = None
    from shapely.geometry import Polygon
    for w in walls:
        w["_poly"] = Polygon(w["outline"]) if len(w["outline"]) >= 4 else Polygon()
        if not w["_poly"].is_valid:
            w["_poly"] = w["_poly"].buffer(0)

    def door_fits_somewhere(w):
        centres, _ = bay_centres(w["length"], p)
        for c in centres:
            a, b = c - p["door_w_m"] / 2, c + p["door_w_m"] / 2
            if a < 0.2 or b > w["length"] - 0.2:
                continue
            v0 = bottom_at(w["_poly"], a, b)
            if v0 is not None and fits(w["_poly"], [a, v0, b, v0 + p["door_h_m"]], 0.15):
                return True
        return False

    # 1. street-facing walls (that can take a door: a sliver of a wall or a gable end cannot)
    for w in walls:
        if w["party"] or w["length"] < p["min_wall_len_m"] or w["height"] < p["min_wall_height_m"] or st_tree is None:
            continue
        mid = w["_seg"].interpolate(0.5, normalized=True)
        cand = st_tree.query(mid.buffer(p["street_max_m"]))
        best = None
        for j in cand:
            q = st_geoms[j].interpolate(st_geoms[j].project(mid))
            d = mid.distance(q)
            if d > p["street_max_m"] or d < 1e-6:
                continue
            v = np.array([q.x - mid.x, q.y - mid.y]) / d
            if float(v @ np.array(w["normal"])) >= p["street_facing_cos"] and (best is None or d < best[0]):
                best = (d, j)
        if best and door_fits_somewhere(w):
            w["street"] = st[best[1]][1]
    # commercial streets: POIs within reach of each named street
    shop_pts = shapely.points([(e, n) for e, n, _, _ in shops]) if shops else np.array([])
    shop_tree = STRtree(shop_pts) if len(shop_pts) else None
    street_len, street_pois = {}, {}
    for g, name, cls in st:
        if cls not in COMMERCIAL_STREET_CLASSES:
            continue                      # footways, steps and driveways are not shopping streets
        street_len[name] = street_len.get(name, 0.0) + g.length
        if shop_tree is not None:
            for j in shop_tree.query(g.buffer(p["commercial_reach_m"])):
                street_pois.setdefault(name, set()).add(int(j))
    commercial = {n for n, s in street_pois.items()
                  if not n.startswith("w") or " " in n                       # a named street, not an edge id
                  if street_len[n] >= p["commercial_min_length_m"] and len(s) >= p["commercial_min_pois"]
                  and len(s) / max(street_len[n] / 1000, 1e-3) >= p["commercial_min_per_km"]}

    def add_shopfront(w, u_lo, u_hi, src):
        poly = w["_poly"]
        centres, pitch = bay_centres(w["length"], p)
        sel = [c for c in centres if u_lo <= c <= u_hi] or [min(centres, key=lambda c: abs(c - (u_lo + u_hi) / 2))]
        a, b = min(sel) - pitch / 2 + 0.25, max(sel) + pitch / 2 - 0.25
        a, b = max(a, p["edge_margin_m"] * 0.5), min(b, w["length"] - p["edge_margin_m"] * 0.5)
        if b - a < 1.5:
            return False
        v0 = bottom_at(poly, a, b)
        if v0 is None:
            return False
        v1 = v0 + min(p["shopfront_h_m"], p["ground_floor_m"] - 0.4)
        r = [round(a, 3), round(v0, 3), round(b, 3), round(v1, 3)]
        if not fits(poly, r, p["inset_m"] * 0.5):
            return False
        w["shopfronts"].append(r + [src])
        return True

    def add_door(w, u, width, src, kind="door"):
        poly = w["_poly"]
        u = min(max(u, width / 2 + 0.2), w["length"] - width / 2 - 0.2)
        a, b = u - width / 2, u + width / 2
        v0 = bottom_at(poly, a, b)
        if v0 is None:
            return False
        h = p["garage_door_h_m"] if kind == "garage" else p["door_h_m"]
        r = [round(a, 3), round(v0, 3), round(b, 3), round(v0 + h, 3)]
        if not fits(poly, r, 0.15):
            return False
        w["doors"].append(r + [src, kind])
        return True

    # 2. OSM doors
    unplaced = []
    placed = 0
    for e, n, tg, oid in ent:
        pt = Point(e, n)
        near = [j for j in fp_tree.query(pt.buffer(p["entrance_max_m"])) if fps[j].exterior.distance(pt) <= p["entrance_max_m"]
                or fps[j].contains(pt)] if fps else []
        if not near:
            continue                               # not a building door (a gate, a park entrance) or outside the area
        bi = min(near, key=lambda j: fps[j].exterior.distance(pt))
        cands = sorted((walls[i]["_seg"].distance(pt), i) for i in by_b.get(bi, []))
        cands = [(d, i) for d, i in cands if d <= p["entrance_max_m"] + 1.0]
        ok = False
        reason = "no wall within reach"
        for d, i in cands:
            w = walls[i]
            if w["party"]:
                reason = "nearest walls are party walls"
                continue
            kind = "garage" if tg.get("entrance") == "garage" or tg.get("door") == "overhead" else "door"
            width = p["garage_door_w_m"] if kind == "garage" else (p["main_door_w_m"] if tg.get("entrance") == "main" else p["door_w_m"])
            if add_door(w, w["_seg"].project(pt), width, f"osm:{oid}", kind):
                ok = True
                break
            reason = "does not fit the wall outline"
        if ok:
            placed += 1
        else:
            unplaced.append({"osm": oid, "building": blds[bi]["id"], "reason": reason})

    # 3. OSM shops
    shop_bld = 0
    for e, n, tg, oid in shops:
        pt = Point(e, n)
        near = [j for j in fp_tree.query(pt.buffer(p["poi_max_m"])) if fps[j].distance(pt) <= p["poi_max_m"]] if fps else []
        if not near:
            continue
        bi = min(near, key=lambda j: fps[j].distance(pt))
        ws = [walls[i] for i in by_b.get(bi, []) if walls[i]["street"]]
        if not ws:
            continue
        w = min(ws, key=lambda w: w["_seg"].distance(pt))
        u = w["_seg"].project(pt)
        if add_shopfront(w, u - p["shop_reach_m"], u + p["shop_reach_m"], f"osm:{oid}"):
            shop_bld += 1

    # 4. commercial streets
    for w in walls:
        if w["street"] in commercial and not w["shopfronts"] and w["length"] >= p["shopfront_min_wall_m"]:
            add_shopfront(w, 0.0, w["length"], f"rule:commercial street {w['street']}")

    # 5. rule doors
    rule_doors, no_street = 0, []
    for bi, idx in by_b.items():
        ws = [walls[i] for i in idx]
        street_ws = [w for w in ws if w["street"]]
        if any(w["doors"] for w in street_ws):
            continue
        if blds[bi]["height"] < p["min_wall_height_m"] or blds[bi]["footprint_m2"] < p["door_min_footprint_m2"]:
            continue
        pool = street_ws or [w for w in ws if not w["party"] and w["length"] >= p["min_wall_len_m"]
                             and w["height"] >= p["min_wall_height_m"]]
        done = False
        for w in sorted(pool, key=lambda w: -w["length"]):
            centres, _ = bay_centres(w["length"], p)
            for c in sorted(centres, key=lambda c: abs(c - w["length"] / 2)):
                if add_door(w, c, p["door_w_m"], "rule:street door" if street_ws else "rule:no street-facing wall"):
                    done = True
                    break
            if done:
                break
        if done:
            rule_doors += 1
            if not street_ws:
                no_street.append(blds[bi]["id"])

    # 7. ground-floor windows give way
    removed = 0
    for w in walls:
        blocks = [box(r[0] - p["door_window_gap_m"], r[1] - 1, r[2] + p["door_window_gap_m"], r[3] + p["door_window_gap_m"])
                  for r in w["doors"] + w["shopfronts"]]
        if blocks and w["windows"]:
            keep = [x for x in w["windows"] if not any(b.intersects(box(*x)) for b in blocks)]
            removed += len(w["windows"]) - len(keep)
            w["windows"] = keep
    for w in walls:
        for k in ("_seg", "_poly"):
            w.pop(k, None)
    summary = {"street_facing_walls": sum(1 for w in walls if w["street"]), "commercial_streets": len(commercial),
               "osm_entrances_near_buildings": placed + len(unplaced), "osm_doors_placed": placed,
               "osm_doors_unplaced": len(unplaced), "shopfronts_from_osm": shop_bld,
               "shopfronts": sum(len(w["shopfronts"]) for w in walls), "rule_doors": rule_doors,
               "doors": sum(len(w["doors"]) for w in walls), "windows_removed": removed,
               "doors_without_street_wall": len(no_street)}
    return summary, unplaced, sorted(commercial)
