"""Scene: water (spec: v2/docs/specs/scene.md, "Water"): OSM water areas and waterway lines in LUREF metres.

  water.json  {"areas": [{"osm", "kind", "name", "rings": [[[e, n], ...], ...]}], "lines": [{"osm", "kind", "name",
               "tunnel", "en"}]}
Areas: natural=water, waterway=riverbank, landuse=reservoir/basin, leisure=swimming_pool (outdoor). Lines:
waterway=river/stream/canal/ditch/drain; culverted stretches (tunnel=culvert) are kept and flagged.
"""
from __future__ import annotations

import json

from shapely.geometry import box, mapping

from v2.data.geo import area_bbox_en, osm_area_en, way_en

LINE_KINDS = {"river", "stream", "canal", "ditch", "drain"}


def is_water_area(tg):
    return (tg.get("natural") == "water" or tg.get("waterway") == "riverbank" or tg.get("landuse") in ("reservoir", "basin")
            or (tg.get("leisure") == "swimming_pool" and tg.get("location") not in ("indoor", "underground")
                and tg.get("indoor") != "yes"))


def rings_of(g):
    out = []
    for p in getattr(g, "geoms", [g]):
        if p.geom_type != "Polygon":
            continue
        m = mapping(p)["coordinates"]
        out.append([[[round(x, 2), round(y, 2)] for x, y in ring] for ring in m])
    return out


def load_polygons(path):
    """water.json areas as shapely polygons (for other stages and checks)."""
    from shapely.geometry import Polygon
    d = json.loads(path.read_text())
    out = []
    for a in d["areas"]:
        for rings in a["rings"]:
            p = Polygon(rings[0], rings[1:])
            out.append(p if p.is_valid else p.buffer(0))
    return out


def build(ctx):
    ground = json.loads((ctx.dep("fetch_osm_ground") / "ground.json").read_text())
    clip = box(*area_bbox_en(ctx.area, 300))
    areas, lines = [], []
    for el in ground["elements"]:
        tg = el.get("tags", {})
        if el["type"] in ("way", "relation") and is_water_area(tg):
            g = osm_area_en(el)
            if g is None or not g.intersects(clip):
                continue
            g = g.intersection(clip)
            r = rings_of(g)
            if r:
                areas.append({"osm": f"{el['type']}/{el['id']}", "kind": tg.get("water") or tg.get("natural") or tg.get("waterway")
                              or tg.get("landuse") or tg.get("leisure"), "name": tg.get("name", ""), "rings": r,
                              "area_m2": round(g.area, 1)})
        elif el["type"] == "way" and tg.get("waterway") in LINE_KINDS and "geometry" in el:
            en = way_en(el)
            from shapely.geometry import LineString
            if not LineString(en).intersects(clip):
                continue
            lines.append({"osm": f"way/{el['id']}", "kind": tg["waterway"], "name": tg.get("name", ""),
                          "tunnel": tg.get("tunnel", "no") != "no", "en": [[round(x, 2), round(y, 2)] for x, y in en]})
    ctx.write_json("water.json", {"areas": areas, "lines": lines})
    return {"areas": len(areas), "area_m2": round(sum(a["area_m2"] for a in areas)), "lines": len(lines),
            "rivers": sorted({l["name"] for l in lines if l["kind"] == "river" and l["name"]})}
