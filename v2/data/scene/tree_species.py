"""Scene: which species each surveyed tree is drawn as (spec: v2/docs/specs/scene.md, "Tree species").

The survey gives a place, a height, a crown and one of four types for every tree, never a species. So the species
is set by rule, in this order (v2/config/tree_species.json, assign); the first that applies decides:
  0. register: a tree of the city's register (Ville de Luxembourg, Service Parcs) within register_m of the tree:
     its species (the nearest drawn species), and its type with it;
  1. osm: an OpenStreetMap tree with a species or genus within osm_m of the tree: that species (mapped to the
     nearest drawn species by its genus);
  2. named: a street or square whose trees are known (assign.named): that species;
  3. the survey's type narrows what is left: a conifer is a pine, a spruce or a yew; a red-leaved tree a copper
     beech or a purple cherry plum; the others broadleaves;
  4. water: within water_m of a river or a pond: the riverside mix;
  5. street: within street_m of a street: the street's own species (one per named street, drawn from the street
     mix), but for a share of trees that differ;
  6. wood: in an OSM wood or forest, or in a dense stand: the wood mix, in patches;
  7. park: the rest (parks, gardens, yards): the park mix, in small groups.
Mixes are weighted by the species' share of the city's tree register unless they give their own weights; a species
is only given to a tree whose measured height is within the species' range. Every draw is a hash of the tree's
place, so a rebuild, and the commune, give the same species to the same tree.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import LineString
from shapely.ops import unary_union

from v2.data.geo import osm_area_en, way_en

RULES = ("register", "osm", "named", "type", "water", "street", "wood", "park")
CONFIG = Path(__file__).resolve().parents[2] / "config" / "tree_species.json"


@lru_cache(maxsize=None)
def config() -> dict:
    """The city's tree species (v2/config/tree_species.json): how each is drawn, and the rules of this module."""
    return json.loads(CONFIG.read_text())


def _hash(a, b, salt=0):
    """A fixed pseudo-random number in [0, 1) per pair of integers."""
    h = (np.asarray(a, np.int64) * 374761393 + np.asarray(b, np.int64) * 668265263 + int(salt) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(1 << 24)


def _name_hash(s: str) -> int:
    h = 2166136261
    for ch in s.encode():
        h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return h


def drawn_as(latin: str, cultivar: str, A) -> str | None:
    """The drawn species of a tree known by its Latin name and cultivar (assign.cultivars, then assign.genus)."""
    words = (latin or "").split(" ")
    genus = words[0].capitalize() if words and words[0] else ""
    text = f"{latin} {cultivar}".lower()
    for c in A["cultivars"]:
        if genus in c["genus"] and any(h in text for h in c["has"]):
            return c["as"]
    return A["genus"].get(genus)


def load_register(path, S):
    """The city's register (fetch/city_trees.py) as (e, n, drawn species) of the trees whose species is drawn."""
    rows = json.loads(path.read_text())["trees"]
    keys = [drawn_as(r["latin"], r["cultivar"], S["assign"]) for r in rows]
    ok = [i for i, k in enumerate(keys) if k]
    return {"e": np.array([rows[i]["e"] for i in ok]), "n": np.array([rows[i]["n"] for i in ok]),
            "key": [keys[i] for i in ok], "trees": len(rows), "drawn": len(ok)}


def species_table(S):
    """names, and per species: register share, height range."""
    names = list(S["list"])
    rows = [{**S["defaults"], **S["list"][n]} for n in names]
    return names, np.array([r["share"] for r in rows], float), np.array([r["h"] for r in rows], float)


def pool_weights(pool, names, share):
    """A mix as a weight per species: a list takes the register's shares, a dict its own weights."""
    w = np.zeros(len(names))
    for k in pool:
        w[names.index(k)] = pool[k] if isinstance(pool, dict) else share[names.index(k)]
    return w


def draw(w, ok, u):
    """Per tree: a species from the mix w (a weight per species) among those allowed (ok: trees x species), by the
    uniform number u. A tree for which the mix allows no species draws from the whole mix."""
    w = np.broadcast_to(np.asarray(w, float), ok.shape)
    wk = w * ok
    wk = np.where(wk.sum(1, keepdims=True) > 0, wk, w)
    c = np.cumsum(wk, 1)
    return (u[:, None] >= c / c[:, -1:]).sum(1).clip(0, ok.shape[1] - 1)


def context(osm_ground, osm_transport, S):
    """What the rules read from OpenStreetMap: woods, named streets and squares, street lines, trees with a species."""
    A = S["assign"]
    woods, squares, trees = [], {}, []
    for el in json.loads(osm_ground.read_text())["elements"]:
        tg = el.get("tags", {})
        if el["type"] == "node":
            if tg.get("natural") == "tree":
                key = drawn_as(tg.get("species") or tg.get("taxon") or tg.get("genus") or "", "", A)
                if key:
                    trees.append((el["lon"], el["lat"], key))
            continue
        if tg.get("landuse") == "forest" or tg.get("natural") == "wood":
            g = osm_area_en(el)
            if g is not None:
                woods.append(g)
        elif tg.get("name") in A["named"] and (tg.get("place") == "square" or tg.get("highway") == "pedestrian"):
            g = osm_area_en(el)
            if g is not None:
                squares.setdefault(tg["name"], []).append(g)
    lines, line_names = [], []
    for el in json.loads(osm_transport.read_text())["elements"]:
        tg = el.get("tags", {})
        if el["type"] != "way" or tg.get("highway") not in A["street_classes"] or tg.get("tunnel") in ("yes", "building_passage"):
            continue
        en = way_en(el)
        if len(en) < 2:
            continue
        if tg.get("name") in A["named"] and tg.get("area") == "yes" and len(en) >= 4:
            squares.setdefault(tg["name"], []).append(shapely.Polygon(en).buffer(0))
        lines.append(LineString(en)); line_names.append(tg.get("name", ""))
    return {"woods": woods, "squares": squares, "lines": lines, "line_names": line_names, "osm_trees": trees}


def assign(e, n, typ, h, type_names, S, ctx, water=(), register=None):
    """Each tree's species (row of species_table) and the rule that set it (index into RULES)."""
    from scipy.spatial import cKDTree

    from v2.data.geo import lonlat_to_en
    A = S["assign"]
    names, share, hr = species_table(S)
    N = len(e)
    sp = np.full(N, -1)
    rule = np.full(N, -1)
    pts = shapely.points(e, n)
    ke, kn = np.round(np.asarray(e) * 10).astype(np.int64), np.round(np.asarray(n) * 10).astype(np.int64)
    h = np.asarray(h, float)
    fits = (h[:, None] >= hr[None, :, 0]) & (h[:, None] <= hr[None, :, 1])
    tn = [str(t) for t in type_names]
    conifer, red = np.asarray(typ) == tn.index("conifer"), np.asarray(typ) == tn.index("deciduous_red")
    kinds = {"conifer": np.isin(names, A["conifers"]), "red": np.isin(names, A["red"])}
    kinds["broad"] = ~kinds["conifer"] & ~kinds["red"]
    kind_ok = np.where(conifer[:, None], kinds["conifer"][None], np.where(red[:, None], kinds["red"][None], kinds["broad"][None]))

    def put(m, s, r):
        m = m & (sp < 0)
        sp[m] = np.broadcast_to(s, (N,))[m]; rule[m] = RULES.index(r)

    # 0. the city's register: each register tree to the surveyed tree nearest to it, each surveyed tree to the
    # register tree nearest to it
    if register is not None and len(register["e"]):
        d, j = cKDTree(np.column_stack([e, n])).query(np.column_stack([register["e"], register["n"]]))
        best = np.full(N, np.inf)
        np.minimum.at(best, j, d)
        win = (d <= A["register_m"]) & (d == best[j])
        s = np.full(N, -1)
        s[j[win]] = np.array([names.index(k) for k in register["key"]])[win]
        put(s >= 0, np.maximum(s, 0), "register")
    # 1. OpenStreetMap trees with a species
    if ctx["osm_trees"]:
        oe, on = lonlat_to_en(np.array([t[0] for t in ctx["osm_trees"]]), np.array([t[1] for t in ctx["osm_trees"]]))
        d, j = cKDTree(np.column_stack([oe, on])).query(np.column_stack([e, n]))
        s = np.array([names.index(t[2]) for t in ctx["osm_trees"]])[j]
        put((d <= A["osm_m"]) & kind_ok[np.arange(N), s], s, "osm")
    # 2. streets and squares whose trees are known
    tree_lines = STRtree(ctx["lines"]) if ctx["lines"] else None
    near_name = np.full(N, "", object)
    near_d = np.full(N, np.inf)
    if tree_lines is not None:
        ti, li = tree_lines.query_nearest(pts, max_distance=A["street_m"], all_matches=False)
        near_name[ti] = np.array(ctx["line_names"], object)[li]
        near_d[ti] = shapely.distance(pts[ti], np.array(ctx["lines"], object)[li])
    for name, key in A["named"].items():
        m = near_name == name
        for g in ctx["squares"].get(name, []):
            m = m | shapely.contains_xy(g.buffer(A["square_m"]), e, n)
        put(m & kind_ok[:, names.index(key)], names.index(key), "named")
    # 3. the survey's type
    for mask, pool in ((conifer, A["conifers"]), (red, A["red"])):
        s = draw(pool_weights(pool, names, share), fits, _hash(ke, kn, 11))
        put(mask, s, "type")
    # 4. by the water
    if len(water):
        wt = STRtree(list(water))
        ti, _ = wt.query_nearest(pts, max_distance=A["water_m"], all_matches=False)
        m = np.zeros(N, bool); m[ti] = True
        s = draw(pool_weights(A["pools"]["water"], names, share), fits, _hash(ke, kn, 12))
        put(m, s, "water")
    in_wood = np.zeros(N, bool)
    if ctx["woods"]:
        in_wood = np.asarray(shapely.contains_xy(unary_union(ctx["woods"]), e, n))
    if N > 1:
        k = min(A["stand_trees"] + 1, N)
        d, _ = cKDTree(np.column_stack([e, n])).query(np.column_stack([e, n]), k=k)
        in_wood |= d[:, -1] <= A["stand_m"]
    # 5. street trees: one species per named street, but for the share that differ
    w_street = pool_weights(A["pools"]["street"], names, share)
    street = np.isfinite(near_d) & ~in_wood
    sid = np.array([_name_hash(str(s)) for s in near_name], np.int64)
    unnamed = near_name == ""
    cell = lambda size, salt: _hash(np.floor(np.asarray(e) / size).astype(np.int64), np.floor(np.asarray(n) / size).astype(np.int64), salt)
    u_row = np.where(unnamed, cell(A["street_cell_m"], 13), _hash(sid, 0, 13))
    own = _hash(ke, kn, 14) < A["street_mixed_share"]
    s = draw(w_street, fits, np.where(own, _hash(ke, kn, 15), u_row))
    put(street, s, "street")
    # 6. woods and dense stands, in patches; 7. the rest, in small groups
    for mask, pool, size, share_own, r, salt in ((in_wood, "wood", A["wood_cell_m"], A["wood_mixed_share"], "wood", 20),
                                                 (np.ones(N, bool), "park", A["park_cell_m"], A["park_mixed_share"], "park", 30)):
        own = _hash(ke, kn, salt) < share_own
        s = draw(pool_weights(A["pools"][pool], names, share), fits, np.where(own, _hash(ke, kn, salt + 1), cell(size, salt + 2)))
        put(mask, s, r)
    return sp, rule, names
