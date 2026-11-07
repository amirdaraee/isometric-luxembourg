"""OSM roads, paths, railways and water with full geometry (for traffic, street labels and painting checks).
Overpass is often busy, so back off and retry."""
import json
import time
import urllib.parse
import urllib.request
from common import RAW

Q = """[out:json][timeout:90][bbox:49.591,6.109,49.643,6.181];
(way["highway"];
 way["railway"~"rail|tram|light_rail|funicular"];
 way["waterway"~"river|stream|canal"];
 way["natural"="water"]; relation["natural"="water"];
 way["water"]; way["landuse"="reservoir"];);
out geom tags;"""
EP = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
dest = RAW / "osm" / "lines.json"
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
