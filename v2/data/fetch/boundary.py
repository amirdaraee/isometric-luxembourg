"""Writes the commune scope polygon and its 24 quarters into the repo config (run once; the result is committed).

The scope of v2 is a polygon in the repo (V1_RETRO P8): the City of Luxembourg's administrative boundary from
OpenStreetMap (relation 407489, admin_level 8, ref:lau2 0304) and its quarters (admin_level 9 inside it).

    python -m v2.data.fetch.boundary
writes v2/config/areas/commune.geojson and v2/config/areas/commune_quarters.geojson.
"""
from __future__ import annotations

import datetime
import json

from shapely.geometry import mapping

from v2.config import CONFIG
from v2.data.fetch import overpass
from v2.data.geo import relation_polygons, to_en_geom

COMMUNE_REL = 407489
QUERY = f"""[out:json][timeout:180];
rel({COMMUNE_REL});
out body geom;
map_to_area->.c;
rel(area.c)["boundary"="administrative"]["admin_level"="9"];
out body geom;"""


def rounded(g, nd=7):
    def r(c):
        if isinstance(c, (list, tuple)) and c and isinstance(c[0], (int, float)):
            return [round(c[0], nd), round(c[1], nd)]
        return [r(x) for x in c]
    m = mapping(g)
    return {"type": m["type"], "coordinates": r(m["coordinates"])}


def main():
    d = overpass.run(QUERY)
    stamp = d.get("osm3s", {}).get("timestamp_osm_base", "")
    rels = [e for e in d["elements"] if e["type"] == "relation"]
    commune = next(e for e in rels if e["id"] == COMMUNE_REL)
    cpoly = relation_polygons(commune)
    area_km2 = to_en_geom(cpoly).area / 1e6
    meta = {"source": "OpenStreetMap contributors, ODbL", "osm_timestamp": stamp,
            "fetched": datetime.date.today().isoformat(), "generator": "python -m v2.data.fetch.boundary"}
    (CONFIG / "areas" / "commune.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "name": "commune", **meta,
        "features": [{"type": "Feature", "properties": {"name": "Ville de Luxembourg", "osm": f"relation/{COMMUNE_REL}",
                                                        "ref:lau2": commune["tags"].get("ref:lau2"),
                                                        "area_km2": round(area_km2, 3)},
                      "geometry": rounded(cpoly)}]}, indent=1))
    quarters = []
    for q in rels:
        if q["id"] == COMMUNE_REL:
            continue
        p = relation_polygons(q)
        if p is None:
            continue
        # keep only quarters inside the commune (map_to_area also returns neighbours touching it)
        share = p.intersection(cpoly).area / p.area
        if share < 0.9:
            continue
        quarters.append({"type": "Feature", "properties": {"name": q["tags"].get("name"), "name:lb": q["tags"].get("name:lb"),
                                                           "osm": f"relation/{q['id']}",
                                                           "area_km2": round(to_en_geom(p).area / 1e6, 3)},
                         "geometry": rounded(p)})
    quarters.sort(key=lambda f: f["properties"]["name"])
    (CONFIG / "areas" / "commune_quarters.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "name": "commune_quarters", **meta, "features": quarters}, indent=1))
    print(f"commune {area_km2:.2f} km2, {len(quarters)} quarters:", ", ".join(f["properties"]["name"] for f in quarters))


if __name__ == "__main__":
    main()
