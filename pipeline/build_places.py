"""Landmarks, streets and addresses, placed on the map's pixels, for pins and search. Run after build_landmarks.py."""
import json
import math
import re
from collections import defaultdict
import numpy as np
from common import ROOT, RAW, WORK, PILOT_LONLAT, ORIGIN_E, ORIGIN_N, ELEV, R, lonlat_to_en, landmark_slug, readme_sections

OUT = ROOT / "web" / "public" / "data"

# (OSM name, label, category, one-line description). Names are matched exactly against OSM.
FEATURED = [
    ("Cathédrale Notre-Dame de Luxembourg", "Notre-Dame Cathedral", "landmark", "The city's cathedral, begun by the Jesuits in the early 1600s."),
    ("Palais Grand Ducal", "Grand Ducal Palace", "landmark", "The Grand Duke's official town residence, in the old town."),
    ("Monument du souvenir", "Gëlle Fra", "landmark", "The golden-figure war memorial on Place de la Constitution."),
    ("Pont Adolphe", "Pont Adolphe", "bridge", "The great stone arch over the Pétrusse valley, opened in 1903."),
    ("Casemates du Bock", "Bock Casemates", "history", "Tunnels cut into the Bock rock, part of the UNESCO World Heritage fortress."),
    ("Pétrusse Casemates", "Pétrusse Casemates", "history", "Fortress galleries under Place de la Constitution."),
    ("Centre culturel de rencontre Abbaye de Neumünster", "Neumünster Abbey", "culture", "A former abbey beside the Alzette, now a cultural centre."),
    ("Philharmonie Luxembourg", "Philharmonie", "culture", "The concert hall on Place de l'Europe, with its forest of white columns."),
    ("MUDAM", "Mudam", "culture", "The modern art museum by I. M. Pei, built on Fort Thüngen."),
    ("Musée Dräi Eechelen", "Dräi Eechelen", "history", "Fort Thüngen's three acorn towers, now a fortress museum."),
    ("Pont Grande-Duchesse Charlotte", "Red Bridge", "bridge", "The red steel bridge joining the city centre to Kirchberg."),
    ("Panorama-Aufzug Pfaffenthal", "Pfaffenthal Lift", "viewpoint", "A glass lift between the Ville Haute and the Pfaffenthal valley."),
    ("Gare Centrale", "Luxembourg Station", "transport", "The central railway station and tram stop."),
    ("Pfaffenthal-Kirchberg", "Pfaffenthal-Kirchberg Station", "transport", "The rail station linked to the Red Bridge by funicular."),
    ("Centre National Sportif et Culturel d'Coque", "d'Coque", "culture", "The national sports and culture centre, under its shell-shaped roof."),
    ("Cour de Justice Tower Rocca", "EU Court of Justice", "landmark", "The golden towers of the Court of Justice of the European Union."),
    ("Parlement européen - bâtiment Konrad Adenauer (KAD)", "European Parliament", "landmark", "The Parliament's Luxembourg offices, in the Konrad Adenauer building."),
    ("Kiosque de la Place d'Armes", "Place d'Armes", "square", "The old town's café square, with its bandstand."),
    ("Guillaume II", "Place Guillaume II", "square", "The Knuedler, the market square with its equestrian statue."),
    ("Cercle municipal", "Cercle Cité", "culture", "The city's grand reception and exhibition hall on Place d'Armes."),
    ("Hôtel de Ville", "Hôtel de Ville", "landmark", "The city hall, on Place Guillaume II."),
    ("Chambre des Députés", "Chamber of Deputies", "landmark", "The national parliament, beside the palace."),
    ("Musée national d'histoire et d'art Luxembourg", "MNHA", "culture", "The National Museum of History and Art, on the Fëschmaart."),
    ("Musée national d'histoire naturelle", "Natur Musée", "culture", "The natural history museum, in the Grund."),
    ("Villa Vauban", "Villa Vauban", "culture", "The city's art museum, in the municipal park."),
    ("Parc municipal Edouard André", "Municipal Park", "park", "The park laid out where the fortress walls once stood."),
    ("Saint-Jean-Baptiste", "Saint-Jean du Grund", "landmark", "The parish church beside Neumünster Abbey."),
    ("Église de Saint-Michel", "Saint-Michel Church", "landmark", "The oldest religious site in the city."),
    ("Clausener Viaduc", "Clausen Viaduct", "bridge", "The railway viaduct over the Clausen valley."),
    ("Pont Viaduc", "Passerelle", "bridge", "The old viaduct over the Pétrusse, joining the centre to the Gare quarter."),
    ("BCEE Clock Tower", "Spuerkeess Tower", "landmark", "The clock tower of the state savings bank, by the Pont Adolphe."),
    ("Casino Luxembourg - Forum d'art contemporain", "Casino Luxembourg", "culture", "A contemporary art centre in a former casino."),
    ("Vallée de la Pétrusse", "Pétrusse Valley", "park", "The green valley that splits the centre from the Gare quarter."),
    ("Arboretum Kirchberg Parc Central", "Parc Central", "park", "Part of the Kirchberg arboretum."),
    ("Université du Luxembourg - Campus Kirchberg", "University, Kirchberg", "landmark", "The University of Luxembourg's Kirchberg campus."),
    ("Kirchberg Shopping Center", "Kirchberg Shopping Center", "landmark", "Shops and cinemas at the eastern end of Kirchberg."),
]
QUARTERS = ["Kirchberg", "Limpertsberg", "Gare", "Grund", "Pfaffenthal", "Clausen"]
POI_TAGS = {
    "tourism": {"museum", "attraction", "viewpoint", "gallery", "artwork"},
    "historic": None,
    "amenity": {"place_of_worship", "theatre", "arts_centre", "library", "university", "townhall", "hospital", "marketplace", "courthouse", "cinema"},
    "leisure": {"park", "stadium", "garden", "sports_centre", "water_park"},
    "railway": {"station", "halt", "tram_stop"},
    "man_made": {"bridge"},
    "government": None,
}


def main():
    m = json.loads((WORK / "mosaic.json").read_text())
    t = np.load(WORK / "terrain.npz")
    tz, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])
    W0, S0, E0, N0 = PILOT_LONLAT

    def place(lon, lat):
        e, n = lonlat_to_en(lon, lat)
        iy, ix = int((n - tn0) / ts), int((e - te0) / ts)
        if not (0 <= iy < tz.shape[0] and 0 <= ix < tz.shape[1]):
            return None
        z = float(tz[iy, ix])
        le, ln = e - ORIGIN_E, n - ORIGIN_N
        sx = (le + ln) * R
        sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
        return round((sx - m["sx0"]) / m["mpp"]), round((m["sy1"] - sy) / m["mpp"])

    def inside(lon, lat):
        return W0 <= lon <= E0 and S0 <= lat <= N0

    els = json.loads((RAW / "osm" / "places.json").read_text())["elements"]
    by_name = defaultdict(list)
    for el in els:
        c = el.get("center") or el
        if "lat" not in c or "name" not in el["tags"]:
            continue
        by_name[el["tags"]["name"]].append((el["tags"], c["lon"], c["lat"]))

    places, used = [], set()
    missing = []
    for osm, label, cat, desc in FEATURED:
        hits = [h for h in by_name.get(osm, []) if inside(h[1], h[2])]
        if not hits:
            missing.append(osm)
            continue
        p = place(hits[0][1], hits[0][2])
        places.append({"n": label, "c": cat, "d": desc, "x": p[0], "y": p[1], "f": 1, "a": osm})
        used.add(osm)
        used.add(label)
    # Landmark cards with a 'Pin' row in research/01-landmarks ("label · rank", rank 1 most important) become featured
    # pins too, at the card's own position and carrying its slug, so the pin always opens that card. They come after
    # FEATURED, best rank first: Pins.tsx keeps labels in this order and drops those that collide.
    lm_path = OUT / "landmarks.json"
    cards = {c["slug"]: c for c in json.loads(lm_path.read_text())} if lm_path.exists() else {}
    pins = []
    for title, rows, _ in readme_sections((ROOT / "research/01-landmarks/README.md").read_text()):
        c = cards.get(landmark_slug(title.split("(")[0]))
        if "Pin" in rows and c:
            label, _, rank = rows["Pin"].partition(" · ")
            pins.append((int(rank or 3), label.strip(), c, rows.get("OSM name", "").strip("`")))
    for rank, label, c, osm in sorted(pins, key=lambda p: p[0]):
        if label in used:
            continue
        places.append({"n": label, "c": c["category"], "x": c["x"], "y": c["y"], "f": 1, "s": c["slug"], **({"a": osm} if osm else {})})
        used.update({label, osm, c["name"]})
    for name in QUARTERS:
        hits = [h for h in by_name.get(name, []) if "place" in h[0] and inside(h[1], h[2])]
        if hits:
            p = place(hits[0][1], hits[0][2])
            places.append({"n": name, "c": "quarter", "x": p[0], "y": p[1], "q": 1})
            used.add(name)
        else:
            missing.append(name)
    if missing:
        print("not found in OSM or outside the pilot:", missing)

    poi = 0
    for name, hits in by_name.items():
        if name in used:
            continue
        for tags, lon, lat in hits:
            if not inside(lon, lat):
                continue
            hit = any(k in tags and (v is None or tags[k] in v) for k, v in POI_TAGS.items())
            if hit and "highway" not in tags:
                p = place(lon, lat)
                cat = "culture" if tags.get("tourism") in ("museum", "gallery", "artwork") else "park" if "leisure" in tags else "transport" if "railway" in tags else "history" if "historic" in tags else "landmark"
                places.append({"n": name, "c": cat, "x": p[0], "y": p[1]})
                poi += 1
                break

    streets = defaultdict(list)
    addr = []
    for el in els:
        tags = el["tags"]
        c = el.get("center") or el
        if "lat" not in c or not inside(c["lon"], c["lat"]):
            continue
        if "highway" in tags and "name" in tags:
            streets[tags["name"]].append((c["lon"], c["lat"]))
        if "addr:housenumber" in tags and "addr:street" in tags:
            addr.append((tags["addr:street"], tags["addr:housenumber"], tags.get("addr:postcode", ""), c["lon"], c["lat"]))
    seen_st = 0
    for name, pts in streets.items():
        if name in used or re.fullmatch(r"[A-Z]?\d+", name):
            continue
        a = np.array(pts)
        mid = a[np.argmin(((a - a.mean(0)) ** 2).sum(1))]
        p = place(float(mid[0]), float(mid[1]))
        places.append({"n": name, "c": "street", "x": p[0], "y": p[1]})
        seen_st += 1

    addresses = []
    seen_addr = set()
    for st, num, pc, lon, lat in sorted(set(addr)):
        if (st, num) in seen_addr:  # the same address can be mapped twice in OSM
            continue
        seen_addr.add((st, num))
        p = place(lon, lat)
        addresses.append([f"{num} {st}", pc, p[0], p[1]])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "places.json").write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")))
    (OUT / "addresses.json").write_text(json.dumps(addresses, ensure_ascii=False, separators=(",", ":")))
    print("featured", sum(1 for p in places if p.get("f")), "quarters", sum(1 for p in places if p.get("q")), "pois", poi, "streets", seen_st, "addresses", len(addresses))


if __name__ == "__main__":
    main()
