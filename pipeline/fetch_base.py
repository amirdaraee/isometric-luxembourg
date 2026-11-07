"""Fetch ground imagery (CC0 orthophoto 2023), elevation tiles and OSM places, all cached on disk."""
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from common import PILOT_LONLAT, RAW

UA = {"User-Agent": "isometric-luxembourg-builder/1.0"}
ORTHO = "https://wmts1.geoportail.lu/opendata/wmts/ortho_2023/GLOBAL_WEBMERCATOR_4_V3/{z}/{x}/{y}.jpeg"
TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
OVERPASS = "https://overpass-api.de/api/interpreter"
MARGIN = 0.006  # degrees around the area, so frames never reach the data's edge


def tile_range(bbox, z):
    w, s, e, n = bbox
    t = 2 ** z
    fx = lambda lon: int((lon + 180) / 360 * t)
    fy = lambda lat: int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * t)
    return fx(w), fy(n), fx(e), fy(s)


def get(url, dest, retries=4):
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                data = r.read()
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.rename(dest)
            return True
        except Exception as e:
            err = e
            time.sleep(2 * (attempt + 1))
    print("failed", url, err)
    return False


def fetch_tiles(template, sub, ext, bbox, z, workers):
    x0, y0, x1, y1 = tile_range(bbox, z)
    jobs = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    print(sub, "z", z, "tiles", len(jobs), flush=True)
    def one(job):
        x, y = job
        return get(template.format(z=z, x=x, y=y), RAW / sub / str(z) / f"{x}_{y}.{ext}")
    with ThreadPoolExecutor(workers) as ex:
        ok = sum(ex.map(one, jobs))
    print(sub, "ok", ok, "of", len(jobs), flush=True)
    return (x0, y0, x1, y1)


def fetch_osm(bbox):
    dest = RAW / "osm" / "places.json"
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    w, s, e, n = bbox
    q = f"""[out:json][timeout:120][bbox:{s},{w},{n},{e}];
(
 nwr["name"]["tourism"];
 nwr["name"]["historic"];
 nwr["name"]["amenity"~"place_of_worship|theatre|arts_centre|library|university|college|townhall|hospital|marketplace|courthouse|cinema"];
 nwr["name"]["leisure"~"park|stadium|garden|sports_centre|water_park"];
 nwr["name"]["railway"~"station|halt|tram_stop"];
 nwr["name"]["man_made"~"bridge|tower"];
 nwr["name"]["bridge"];
 nwr["name"]["place"];
 nwr["name"]["office"~"government|diplomatic"];
 nwr["name"]["government"];
 nwr["name"]["building"~"cathedral|church|palace|castle|government|museum|civic|university|train_station|stadium"];
 way["name"]["highway"];
 nwr["addr:housenumber"]["addr:street"];
);
out center tags;"""
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(OVERPASS, data=data, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=200) as r:
        body = r.read()
    dest.write_bytes(body)
    print("osm", len(json.loads(body)["elements"]), "elements", flush=True)


def main():
    w, s, e, n = PILOT_LONLAT
    bbox = (w - MARGIN, s - MARGIN, e + MARGIN, n + MARGIN)
    fetch_osm(bbox)
    fetch_tiles(TERRARIUM, "terrarium", "png", bbox, 14, 4)
    fetch_tiles(ORTHO, "ortho2023", "jpg", bbox, 18, 4)


if __name__ == "__main__":
    main()
