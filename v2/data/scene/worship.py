"""Places of worship: which scene buildings are a church, a cathedral or a chapel, and which of their walls
(spec: v2/docs/specs/facades.md, "Places of worship"; the owner's decision of 13 Nov 2026).

A building is told from the data, never from a place in the picture:
  1. OSM: a way or relation tagged building=church|cathedral|chapel, or amenity=place_of_worship, with its outline
     (stage `fetch_osm_worship`). A scene building belongs to it when the outline covers at least `worship_min_share` of
     the building's footprint, or the building holds at least `worship_min_share_of_outline` of the outline (ACT
     often models a church and the convent or hospital it is part of as one building). The outline is kept: only
     the walls standing in it are the church's.
  2. The landmark list: a landmark card of category "church" (v1's cards, `scene_places`). The scene building that
     holds its point, or the nearest within `worship_landmark_max_m`. The whole building.
  3. `v2/data/structures/landmark_styles.json`: a building entered there with "kind": "place_of_worship". The whole
     building.
A point alone (an OSM node amenity=place_of_worship) does not make a building a church: prayer rooms and community
centres in ordinary houses are mapped that way.
"""
from __future__ import annotations

import json

import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

BUILDING_TAGS = ("church", "cathedral", "chapel")

def _ring(geom):
    from v2.data.geo import lonlat_to_en
    e, n = lonlat_to_en(np.array([g["lon"] for g in geom]), np.array([g["lat"] for g in geom]))
    return np.column_stack([e, n])


def outlines(worship_json) -> list:
    """The mapped places of worship as (outline in LUREF metres, name, "way/123", building tag)."""
    out = []
    for el in worship_json["elements"]:
        tg = el.get("tags", {})
        if tg.get("building") not in BUILDING_TAGS and tg.get("amenity") != "place_of_worship":
            continue
        poly = None
        if el["type"] == "way" and len(el.get("geometry", [])) >= 4:
            poly = Polygon(_ring(el["geometry"]))
        elif el["type"] == "relation" and tg.get("type") == "multipolygon":      # a site relation is not an outline
            lines = [LineString(_ring(m["geometry"])) for m in el.get("members", [])
                     if m.get("type") == "way" and m.get("role") in ("outer", "") and len(m.get("geometry", [])) >= 2]
            parts = list(polygonize(unary_union(lines))) if lines else []
            poly = unary_union(parts) if parts else None
        if poly is None or poly.is_empty:
            continue
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.area > 1.0:
            out.append((poly, tg.get("name"), f"{el['type']}/{el['id']}", tg.get("building", "yes")))
    return out


def find(blds, fps, worship_json, places, styles, p) -> dict:
    """{building index: {"source", "name", "area", "share"}}: the scene's places of worship. "area" is the mapped
    outline (a shapely geometry) when OSM gives one, else None: the whole building. "share": how much of the
    building's footprint the church is."""
    found = {}
    tree = STRtree(fps) if fps else None
    for poly, name, oid, tag in outlines(worship_json):
        for j in (tree.query(poly) if tree is not None else []):
            f = fps[j]
            if f.is_empty or not f.intersects(poly):
                continue
            a = f.intersection(poly).area
            if a >= p["worship_min_share"] * f.area or a >= p["worship_min_share_of_outline"] * poly.area:
                prev = found.get(int(j))
                area = poly if prev is None else unary_union([prev["area"], poly])
                found[int(j)] = {"source": f"osm:{oid}" if prev is None else prev["source"], "name": name if prev is None else prev["name"],
                                 "area": area, "osm_building": tag if prev is None else prev["osm_building"],
                                 "share": round(min(1.0, f.intersection(area).area / f.area), 3)}
    by_id = {b["id"]: i for i, b in enumerate(blds)}
    for pl in places:
        if pl.get("source") != "landmark" or pl.get("category") != "church":
            continue
        pt = Point(pl["e"], pl["n"])
        best = None
        for j in (tree.query(pt.buffer(p["worship_landmark_max_m"])) if tree is not None else []):
            d = fps[j].distance(pt)
            if d <= p["worship_landmark_max_m"] and (best is None or d < best[0]):
                best = (d, int(j))
        if best and best[1] not in found:
            found[best[1]] = {"source": f"landmark:{pl['slug']}", "name": pl.get("name"), "area": None, "osm_building": None,
                              "share": 1.0}
    for bid, st in styles.items():
        j = by_id.get(bid)
        if st.get("kind") == "place_of_worship" and j is not None and j not in found:
            found[j] = {"source": "landmark_styles", "name": st.get("name"), "area": None, "osm_building": None, "share": 1.0}
    return found


def wall_in(area, seg: LineString, tol: float) -> bool:
    """Is a wall (its base line) the church's? Its middle stands in the mapped outline, grown by `tol`."""
    return area is None or area.buffer(tol).contains(seg.interpolate(0.5, normalized=True))


def load_styles() -> dict:
    from v2.config import V2
    return json.loads((V2 / "data" / "structures" / "landmark_styles.json").read_text())
