"""OpenStreetMap through the Overpass API (ODbL). One request at a time, with back-off between the two mirrors.

Every query asks for ``out body geom``: tags, the node ids of each way (needed to join the transport graph at real
junctions) and the coordinates.
"""
from __future__ import annotations

import json

from .http import post_form

ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]


def run(query: str, tries: int = 6) -> dict:
    last = None
    for attempt in range(tries):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            body = post_form(url, {"data": query}, timeout=400)
            d = json.loads(body)
            if "remark" in d and "runtime error" in d["remark"]:
                raise RuntimeError(d["remark"])
            return d
        except Exception as ex:  # noqa: BLE001 - mirrors fail in many ways; try the other one
            last = ex
            print(f"  overpass {url}: {ex}", flush=True)
    raise RuntimeError(f"overpass failed: {last}")


def bbox_str(bbox_lonlat) -> str:
    w, s, e, n = bbox_lonlat
    return f"{s:.5f},{w:.5f},{n:.5f},{e:.5f}"


TRANSPORT = """[out:json][timeout:300][bbox:{bbox}];
(way["highway"];
 way["railway"~"^(rail|tram|light_rail|subway|funicular|narrow_gauge|preserved|construction|disused)$"];
 way["aerialway"];
 way["man_made"="bridge"]; relation["man_made"="bridge"];
 way["bridge:support"]; node["bridge:support"];
 way["tunnel"]["tunnel"!="no"];
 way["building"="bridge"];
);
out body geom;"""

GROUND = """[out:json][timeout:300][bbox:{bbox}];
(way["landuse"]; relation["landuse"];
 way["leisure"]; relation["leisure"];
 way["natural"]; relation["natural"]; node["natural"="tree"];
 way["amenity"~"^(parking|school|grave_yard|marketplace|university|hospital)$"]; relation["amenity"="parking"];
 way["waterway"]; way["water"]; relation["water"];
 way["barrier"~"^(retaining_wall|city_wall|wall)$"];
 way["historic"~"^(citywalls|fort|castle)$"]; relation["historic"~"^(citywalls|fort)$"];
 way["man_made"~"^(embankment|dyke|pier)$"]; way["embankment"="yes"];
 way["place"="square"]; relation["place"="square"];
 way["area:highway"];
 node["highway"="street_lamp"];
);
out body geom;"""

BOUNDARY = """[out:json][timeout:120];
area["ISO3166-1"="LU"][admin_level=2]->.lu;
(relation["boundary"="administrative"]["admin_level"="8"]["name"="Luxembourg"](area.lu););
out body geom;
rel(r:"subarea") ->.sub;
(relation["boundary"="administrative"]["admin_level"="10"](area.lu);) ->.q;
.q out body geom;"""
