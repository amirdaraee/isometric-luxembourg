"""OSM green areas (parks, forest, lawns, pitches) for the layout map.
Overpass is often busy, so back off and retry."""
import json
import time
import urllib.parse
import urllib.request
from common import RAW

Q = """[out:json][timeout:90][bbox:49.591,6.109,49.643,6.181];
(way["landuse"~"grass|forest|meadow|recreation_ground|cemetery|allotments|vineyard|orchard|village_green"]; relation["landuse"~"forest|grass|meadow"];
 way["leisure"~"park|garden|pitch|playground"]; relation["leisure"="park"]; way["natural"~"wood|scrub|grassland"]; relation["natural"="wood"];);
out geom tags;"""
EP = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
dest = RAW / "osm" / "green.json"
wait = 30
for attempt in range(12):
    try:
        req = urllib.request.Request(EP[attempt % 2], data=urllib.parse.urlencode({"data": Q}).encode(),
                                     headers={"User-Agent": "isometric-luxembourg-builder/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=150) as r:
            body = r.read()
        n = len(json.loads(body)["elements"])
        dest.write_bytes(body)
        print("elements", n, "bytes", len(body))
        break
    except Exception as e:
        print("retry", attempt, type(e).__name__, e, flush=True)
        time.sleep(wait)
        wait = min(wait * 2, 240)
else:
    raise SystemExit("gave up")
