"""Geographic helpers shared by the fetch and scene stages: LUREF <-> WGS84, areas as polygons, OSM geometry.

All scene geometry is in LUREF (EPSG:2169) metres, E and N, with z in metres above sea level (the national LiDAR
heights). Map pixels are only made by ``v2.config.camera``.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon, Polygon, shape
from shapely.ops import linemerge, polygonize, unary_union

from v2.config import area_geojson


@lru_cache(maxsize=None)
def _tf(a: int, b: int) -> Transformer:
    return Transformer.from_crs(a, b, always_xy=True)


def lonlat_to_en(lon, lat):
    return _tf(4326, 2169).transform(lon, lat)


def en_to_lonlat(e, n):
    return _tf(2169, 4326).transform(e, n)


def to_en_geom(g):
    """A shapely geometry in lon/lat to LUREF metres."""
    return shapely.transform(g, lambda xy: np.column_stack(lonlat_to_en(xy[:, 0], xy[:, 1])))


def to_ll_geom(g):
    return shapely.transform(g, lambda xy: np.column_stack(en_to_lonlat(xy[:, 0], xy[:, 1])))


@lru_cache(maxsize=None)
def area_polygon(name: str):
    """The area polygon (scope) in LUREF metres, from v2/config/areas/<name>.geojson."""
    gj = area_geojson(name)
    geoms = [shape(f["geometry"]) for f in gj["features"]] if gj.get("type") == "FeatureCollection" else [shape(gj)]
    return to_en_geom(unary_union(geoms))


def area_bbox_en(name: str, margin: float = 0.0):
    x0, y0, x1, y1 = area_polygon(name).bounds
    return x0 - margin, y0 - margin, x1 + margin, y1 + margin


def area_bbox_lonlat(name: str, margin: float = 0.0):
    x0, y0, x1, y1 = area_bbox_en(name, margin)
    lo, la = en_to_lonlat(np.array([x0, x1, x0, x1]), np.array([y0, y0, y1, y1]))
    return float(min(lo)), float(min(la)), float(max(lo)), float(max(la))


def way_en(el) -> np.ndarray:
    """An Overpass way (out geom) as an (n, 2) array of LUREF metres."""
    g = el["geometry"]
    e, n = lonlat_to_en(np.array([p["lon"] for p in g]), np.array([p["lat"] for p in g]))
    return np.column_stack((e, n))


def relation_polygons(rel, roles=("outer",)) -> MultiPolygon | Polygon | None:
    """Rings of an Overpass relation (out geom), joined from its member ways, holes from 'inner' members (lon/lat)."""
    def rings(role_set):
        lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]]) for m in rel.get("members", [])
                 if m.get("type") == "way" and m.get("role", "") in role_set and len(m.get("geometry", [])) >= 2]
        if not lines:
            return []
        return list(polygonize(linemerge(lines)))
    outer = rings(set(roles))
    if not outer:
        return None
    inner = rings({"inner"})
    g = unary_union(outer)
    if inner:
        g = g.difference(unary_union(inner))
    return g


def way_polygon_ll(el) -> Polygon | None:
    g = el.get("geometry") or []
    if len(g) < 4 or (g[0]["lon"], g[0]["lat"]) != (g[-1]["lon"], g[-1]["lat"]):
        return None
    p = Polygon([(q["lon"], q["lat"]) for q in g])
    return p if p.is_valid else p.buffer(0)


def osm_area_en(el):
    """An Overpass way or multipolygon relation as a polygon in LUREF metres (None for open ways)."""
    if el["type"] == "way":
        p = way_polygon_ll(el)
    else:
        p = relation_polygons(el)
    return None if p is None or p.is_empty else to_en_geom(p)
