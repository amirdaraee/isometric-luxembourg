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
structures.json: {"viaducts": [...], "bridge_outlines": [...]}
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
            spring = max(crown - r, gmid) if v["structure"] == "arch" else crown
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
    ctx.write_json("structures.json", {"viaducts": out, "bridge_outlines": outlines})
    return {"viaducts": {v["id"]: v["status"] for v in out}, "bridge_outlines": len(outlines),
            "arches": {v["id"]: len(v.get("arches", [])) for v in out}}
