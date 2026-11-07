"""Layered map, step 0: fetch the extra OpenStreetMap data the code-drawn layers need for one block.

Writes data/work/layers/<block>/inputs/osm_extra.json: single trees and tree rows, pedestrian areas and squares,
retaining and city walls, cliffs and embankments, steps and paths with area tags, and land use areas not in
green.json (residential, churchyards, sports grounds, car parks are in parking.json already).
One Overpass request, with back-off; the tree points from the national LiDAR tree survey are cut separately
(see LAYERS_POC.md, step 0).

  fetch_inputs.py [b00]
"""
import json
import sys
import time
import urllib.parse
import urllib.request

from layers_common import block, block_lonlat, inputs_dir

UA = {"User-Agent": "isometric-map-research"}
EP = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]


def query(bbox):
    s, w, n, e = bbox
    return f"""[out:json][timeout:120][bbox:{s},{w},{n},{e}];
(node["natural"="tree"]; way["natural"="tree_row"];
 way["highway"="pedestrian"]["area"="yes"]; relation["highway"="pedestrian"]; way["area:highway"];
 way["place"="square"]; relation["place"="square"]; way["amenity"="marketplace"];
 way["barrier"~"retaining_wall|city_wall|wall"]; way["historic"~"citywalls|fort|castle"]; relation["historic"~"citywalls|fort"];
 way["natural"~"cliff|bare_rock|scree|water"]; way["man_made"~"embankment|bridge"]; way["embankment"="yes"];
 way["landuse"~"residential|churchyard|commercial|retail|railway|construction|religious|plant_nursery|flowerbed"];
 way["leisure"~"sports_centre|stadium|track|swimming_pool"]; way["amenity"~"parking|school|grave_yard"];
 way["highway"~"footway|path|steps|cycleway|track|bridleway"];);
out geom tags;"""


def main():
    bid = sys.argv[1] if len(sys.argv) > 1 else "b00"
    b = block(bid)
    w, s, e, n = block_lonlat(b, margin_m=150)
    q = query((round(s, 5), round(w, 5), round(n, 5), round(e, 5)))
    for attempt in range(6):
        try:
            req = urllib.request.Request(EP[attempt % 2], data=urllib.parse.urlencode({"data": q}).encode(), headers=UA)
            body = urllib.request.urlopen(req, timeout=180).read()
            els = json.loads(body)["elements"]
            break
        except Exception as ex:  # busy server: wait and retry
            print("overpass:", ex, "- retrying", flush=True)
            time.sleep(20 * (attempt + 1))
    else:
        sys.exit("overpass failed")
    out = inputs_dir(bid) / "osm_extra.json"
    out.write_text(json.dumps({"bbox_lonlat": [w, s, e, n], "elements": els}))
    print(out, len(els), "elements")


if __name__ == "__main__":
    main()
