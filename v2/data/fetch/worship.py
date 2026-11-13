"""Fetch: OSM places of worship with their outlines, over the commune (used by v2/data/scene/worship.py; spec:
v2/docs/specs/facades.md, "Places of worship"). Kept apart from the other fetches so that it is a stage of its own.
"""
from __future__ import annotations

QUERY = """[out:json][timeout:300][bbox:{bbox}];
(way["building"~"^(church|cathedral|chapel)$"]; relation["building"~"^(church|cathedral|chapel)$"];
 way["amenity"="place_of_worship"]; relation["amenity"="place_of_worship"];
);
out body geom;"""


def fetch_osm_worship(ctx):
    """OSM places of worship with their outlines (Overpass, ODbL), over the commune."""
    from v2.data.fetch import overpass
    from v2.data.geo import area_bbox_lonlat
    p = ctx.params
    bbox = area_bbox_lonlat(p["extent_area"], p["margin_m"])
    q = QUERY.format(bbox=overpass.bbox_str(bbox))
    d = overpass.run(q)
    d["query"] = q
    ctx.write_json("worship.json", d)
    n = {}
    for el in d["elements"]:
        k = el.get("tags", {}).get("building", "-")
        n[k] = n.get(k, 0) + 1
    return {"elements": len(d["elements"]), "by_building_tag": n, "osm_timestamp": d.get("osm3s", {}).get("timestamp_osm_base")}
