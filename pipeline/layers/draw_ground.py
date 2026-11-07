"""Layered map, step 1: the code-drawn ground layers of one block, in style A (inked rendering in code).

  L1_ground.png   land cover on the terrain: grass, woods floor, meadows, pitches, gardens, paving, squares,
                  car parks, railway ground; hill shading; paper texture; ink lines between areas (RGB, opaque)
  L2_relief.png   steep slopes and cliffs: rock colour, hatching, ink at the cliff tops (RGBA)
  L2_walls.png    retaining walls, fortification walls and garden walls as upright faces (RGBA, drawn above
                  the roads, since a wall face hides what is behind it)
  L3_water.png    rivers and ponds, flat, with an inked bank (RGBA); water_mask.png is its exact mask
  L4_roads.png    roads, streets, paths, steps, rail and tram tracks from web/public/data/lines.json, the same
                  lines the viewer's vehicles drive on, at their measured widths (RGBA)
  stack_A.png     L1 + L2 + L3 + L4 + walls, for comparison with today's painting

Land cover comes from OpenStreetMap areas draped on the terrain (drawn on a 1 m map grid and looked up through the
terrain pass), and where OSM says nothing, from the orthophoto's colour (green or paved). Colours are sampled
from today's painting, so the palette matches it.

  draw_ground.py [b00] [--k 0.5] [--crop x0,y0,w,h]   (k: scale of the 6000 px block; crop in layer px)
"""
import argparse
import json
import math

import cv2
import numpy as np
from PIL import Image

from layers_common import (ORIGIN_E, ORIGIN_N, POC_IMG, RAW, ROOT, block, cut, en_to_map, ground_z, inputs_dir,
                           kinds, lonlat_to_en, out_dir, preview, today)
from terrain_pass import block_en, ground_pass, sample, slope_normals

INK = np.array((52, 44, 40), np.float32)
RES = 1.0  # m per px of the land cover grid

# land cover classes (later ones win where OSM areas overlap)
PAVED, GRASS, WOOD, SCRUB, MEADOW, PITCH, GARDEN, CEMETERY, SQUARE, PARKING, RAILGROUND, BUILDSITE, WATER = range(13)
NAMES = ["paved", "grass", "wood", "scrub", "meadow", "pitch", "garden", "cemetery", "square", "parking", "railground",
         "buildsite", "water"]
FALLBACK = {PAVED: (206, 194, 168), GRASS: (128, 150, 74), WOOD: (78, 104, 52), SCRUB: (112, 128, 62),
            MEADOW: (168, 170, 96), PITCH: (104, 160, 72), GARDEN: (140, 150, 84), CEMETERY: (122, 140, 80),
            SQUARE: (214, 200, 174), PARKING: (170, 168, 162), RAILGROUND: (150, 136, 118), BUILDSITE: (196, 170, 130),
            WATER: (52, 112, 120)}


def osm_class(tg):
    lu, le, na, am = tg.get("landuse"), tg.get("leisure"), tg.get("natural"), tg.get("amenity")
    if na == "water" or lu in ("basin", "reservoir"):
        return WATER
    if le in ("pitch", "track", "stadium") or lu == "recreation_ground" and le:
        return PITCH
    if lu in ("forest",) or na == "wood":
        return WOOD
    if na in ("scrub", "heath"):
        return SCRUB
    if lu in ("meadow", "farmland") or na == "grassland":
        return MEADOW
    if lu in ("allotments", "orchard", "vineyard", "plant_nursery", "flowerbed") or le == "garden":
        return GARDEN
    if lu == "cemetery" or am == "grave_yard" or lu == "religious" and tg.get("religion"):
        return CEMETERY
    if lu in ("grass", "village_green", "recreation_ground") or le in ("park", "playground", "dog_park"):
        return GRASS
    if tg.get("highway") == "pedestrian" or tg.get("area:highway") or tg.get("place") == "square" or am == "marketplace":
        return SQUARE
    if am == "parking":
        return PARKING
    if lu == "railway":
        return RAILGROUND
    if lu == "construction":
        return BUILDSITE
    return None


PRIORITY = [RAILGROUND, MEADOW, CEMETERY, GRASS, SCRUB, WOOD, GARDEN, PITCH, PARKING, SQUARE, BUILDSITE, WATER]


def geoms(el):
    if "geometry" in el:
        return [el["geometry"]]
    return [m["geometry"] for m in el.get("members", []) if m.get("role") == "outer" and "geometry" in m]


def landcover_grid(bid, box):
    """OSM land cover on a north-up grid of RES m over box (e0, e1, n0, n1); 255 = no OSM class."""
    e0, e1, n0, n1 = box
    W, H = int((e1 - e0) / RES) + 1, int((n1 - n0) / RES) + 1
    grid = np.full((H, W), 255, np.uint8)
    els = json.loads((RAW / "osm" / "green.json").read_text())["elements"]
    els += json.loads((inputs_dir(bid) / "osm_extra.json").read_text())["elements"]
    els += [e for e in json.loads((RAW / "osm" / "lines.json").read_text())["elements"]
            if e.get("tags", {}).get("natural") == "water" or e["type"] == "relation"]
    els += json.loads((RAW / "osm" / "parking.json").read_text())["elements"]
    byc = {c: [] for c in PRIORITY}
    for el in els:
        tg = el.get("tags", {})
        if el["type"] == "relation" and "waterway" in tg and tg.get("type") != "multipolygon":
            continue
        c = osm_class(tg)
        if c is None or tg.get("parking") == "underground" or tg.get("parking") in ("rooftop", "multi-storey"):
            continue
        for g in geoms(el):
            if len(g) < 3 or g[0] != g[-1] and el["type"] == "way" and c != WATER and "area" not in tg and len(g) < 4:
                continue
            en = np.array([lonlat_to_en(p["lon"], p["lat"]) for p in g])
            px = np.column_stack(((en[:, 0] - e0) / RES, (n1 - en[:, 1]) / RES))
            if px[:, 0].max() < 0 or px[:, 0].min() > W or px[:, 1].max() < 0 or px[:, 1].min() > H:
                continue
            byc[c].append(np.round(px * 4).astype(np.int32))
    for c in PRIORITY:
        if byc[c]:
            cv2.fillPoly(grid, byc[c], int(c), shift=2)
    # rivers and streams drawn as lines where OSM has no water area for them
    for el in json.loads((RAW / "osm" / "lines.json").read_text())["elements"]:
        tg = el.get("tags", {})
        if el["type"] == "way" and tg.get("waterway") in ("river", "stream", "canal") and tg.get("tunnel", "no") == "no":
            en = np.array([lonlat_to_en(p["lon"], p["lat"]) for p in el["geometry"]])
            px = np.column_stack(((en[:, 0] - e0) / RES, (n1 - en[:, 1]) / RES))
            wm = {"river": 14, "canal": 6, "stream": 2.5}[tg["waterway"]]
            sub = np.zeros_like(grid)
            cv2.polylines(sub, [np.round(px * 4).astype(np.int32)], False, 1, max(1, round(wm / RES)), cv2.LINE_8, shift=2)
            grid[(sub > 0) & (grid != WATER) & ((grid == 255) | (tg["waterway"] != "stream"))] = WATER
    return grid


def tree_canopy_grid(bid, box):
    """Where the LiDAR tree survey has crowns, on the same grid (0/1)."""
    e0, e1, n0, n1 = box
    W, H = int((e1 - e0) / RES) + 1, int((n1 - n0) / RES) + 1
    g = np.zeros((H, W), np.uint8)
    for t in json.loads((inputs_dir(bid) / "trees_lidar2024.json").read_text()):
        r = max(1.0, t["cmean"]) / RES
        cv2.circle(g, (int((t["e"] - e0) / RES), int((n1 - t["n"]) / RES)), int(round(r)), 1, -1)
    return g


def noise(shape, scale, seed):
    """Smooth value noise in [-1, 1] with features about `scale` px wide."""
    rng = np.random.default_rng(seed)
    h, w = shape
    sh, sw = max(2, int(h / scale) + 2), max(2, int(w / scale) + 2)
    n = rng.standard_normal((sh, sw)).astype(np.float32)
    n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    return np.clip(n / 1.5, -1, 1)


def edges(lab, width=1):
    """Pixels on a boundary between different labels."""
    e = np.zeros(lab.shape, bool)
    e[1:] |= lab[1:] != lab[:-1]; e[:-1] |= lab[1:] != lab[:-1]
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]; e[:, :-1] |= lab[:, 1:] != lab[:, :-1]
    if width > 1:
        e = cv2.dilate(e.astype(np.uint8), np.ones((width, width), np.uint8)) > 0
    return e


def hatch(shape, spacing, angle_deg, thick=1, seed=0, jitter=0.0):
    """Parallel hatching lines as a 0..1 mask."""
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle_deg)
    d = xx * math.cos(a) + yy * math.sin(a)
    if jitter:
        d = d + noise(shape, spacing * 6, seed) * spacing * jitter
    f = np.abs(((d / spacing) % 1.0) - 0.5) * spacing
    return np.clip(thick / 2 + 0.5 - f, 0, 1)


def sample_palette(cls, art, shade_ok):
    """Median colour of today's painting per class, over open ground (no trees, no buildings)."""
    pal = {}
    for c in range(len(NAMES)):
        m = (cls == c) & shade_ok
        if m.sum() > 400:
            pal[c] = np.median(art[m], axis=0)
        else:
            pal[c] = np.array(FALLBACK[c], np.float32)
        pal[c] = 0.6 * pal[c] + 0.4 * np.array(FALLBACK[c], np.float32)  # keep classes apart
    # open paving reads darker in the painting (shadows of houses): keep it light and warm, like its sunlit parts
    pal[PAVED] = 0.25 * pal[PAVED] + 0.75 * np.array(FALLBACK[PAVED], np.float32)
    return pal


# ---------------------------------------------------------------- roads (L4)
WIDTH_M = {"motorway": 7.5, "trunk": 7.5, "primary": 7.0, "secondary": 6.5, "tertiary": 6.0, "unclassified": 5.0,
           "residential": 5.0, "living_street": 4.5, "service": 3.5, "pedestrian": 5.0, "motorway_link": 5.0,
           "trunk_link": 5.0, "primary_link": 5.0, "secondary_link": 5.0, "tertiary_link": 5.0, "busway": 4.0,
           "footway": 2.0, "path": 1.6, "cycleway": 2.2, "steps": 2.2, "track": 3.0, "bridleway": 2.0,
           "corridor": 2.0, "platform": 3.0}
PATHS = {"footway", "path", "cycleway", "track", "bridleway", "corridor", "platform"}
ROAD_COL = {"road": (132, 130, 128), "ped": (206, 192, 164), "path": (200, 180, 140), "steps": (196, 184, 160)}


def draw_roads(L, b, k, shape):
    """Masks (float 0..1) for road casings and fills, plus lane dashes, steps and rails."""
    H, W = shape
    x0, y0 = b["x0"], b["y0"]
    S = 16  # subpixel shift 4

    def pts(p):
        a = (np.array(p, np.float64).reshape(-1, 2) - (x0, y0)) * k
        return np.round(a * S).astype(np.int32)

    def inside(p):
        a = np.array(p).reshape(-1, 2)
        return (a[:, 0].max() > x0 - 200 and a[:, 0].min() < x0 + b["w"] + 200 and a[:, 1].max() > y0 - 200
                and a[:, 1].min() < y0 + b["h"] + 200)

    m = {n: np.zeros(shape, np.uint8) for n in ("case", "road", "ped", "path", "steps", "dash", "rbed", "rcase",
                                                 "rail", "sleep", "tram")}
    ink = max(1, round(1.2 * 4 * k * 0.5))  # ink line width in px (0.6 m at full scale -> ~2 px)
    roads = [r for r in L["roads"] if not r.get("t") and not r.get("b") and r["k"] in WIDTH_M and inside(r["p"])]
    order = {"path": 0, "steps": 1, "ped": 2, "road": 3}

    def kind(r):
        return "steps" if r["k"] == "steps" else "path" if r["k"] in PATHS else "ped" if r["k"] in ("pedestrian", "living_street") else "road"
    roads.sort(key=lambda r: order[kind(r)])
    for r in roads:
        w = r.get("w") or WIDTH_M[r["k"]]
        if kind(r) in ("path", "steps"):
            w = WIDTH_M[r["k"]]
        wp = max(1, int(round(w * 4 * k)))
        q = pts(r["p"])
        cv2.polylines(m["case"], [q], False, 255, wp + 2 * ink, cv2.LINE_AA, shift=4)
    for r in roads:
        w = r.get("w") or WIDTH_M[r["k"]]
        if kind(r) in ("path", "steps"):
            w = WIDTH_M[r["k"]]
        wp = max(1, int(round(w * 4 * k)))
        q = pts(r["p"])
        kk = kind(r)
        # a road drawn later covers the fill of an earlier one at junctions
        for n in ("road", "ped", "path", "steps"):
            if n != kk:
                tmp = np.zeros(shape, np.uint8)
                cv2.polylines(tmp, [q], False, 255, wp, cv2.LINE_AA, shift=4)
                m[n] = np.minimum(m[n], 255 - tmp)
        cv2.polylines(m[kk], [q], False, 255, wp, cv2.LINE_AA, shift=4)
        if kk == "steps":  # treads across the flight, every 0.9 m
            a = np.array(r["p"], float).reshape(-1, 2)
            seg = np.hypot(*np.diff(a, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
            for s in np.arange(0, cum[-1], 0.9 * 4):
                i = min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
                d = (a[i + 1] - a[i]) / max(seg[i], 1e-6)
                c = a[i] + d * (s - cum[i])
                nrm = np.array((-d[1], d[0])) * w * 4 / 2
                p1, p2 = ((c - nrm - (x0, y0)) * k * S).round().astype(int), ((c + nrm - (x0, y0)) * k * S).round().astype(int)
                cv2.line(m["dash"], tuple(p1), tuple(p2), 255, 1, cv2.LINE_AA, shift=4)
        if kk == "road" and w >= 6 and not r.get("o"):  # centre dashes: 3 m dash, 6 m gap
            a = np.array(r["p"], float).reshape(-1, 2)
            seg = np.hypot(*np.diff(a, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
            for s in np.arange(0, cum[-1], 9 * 4):
                p1 = [np.interp(s, cum, a[:, i]) for i in (0, 1)]
                p2 = [np.interp(min(s + 3 * 4, cum[-1]), cum, a[:, i]) for i in (0, 1)]
                p1 = ((np.array(p1) - (x0, y0)) * k * S).round().astype(int)
                p2 = ((np.array(p2) - (x0, y0)) * k * S).round().astype(int)
                cv2.line(m["dash"], tuple(p1), tuple(p2), 255, max(1, round(0.15 * 4 * k * 2)), cv2.LINE_AA, shift=4)
    # rail: ballast bed with ink casing, sleepers, two rails; tram: two rails on the street
    for r in L["rail"]:
        if r.get("t") or r.get("b") or not inside(r["p"]):
            continue
        a = np.array(r["p"], float).reshape(-1, 2)
        if len(a) < 2:
            continue
        q = pts(r["p"])
        dd = np.diff(a, axis=0); dd /= (np.linalg.norm(dd, axis=1, keepdims=True) + 1e-6)
        nn = np.r_[dd[:1], (dd[1:] + dd[:-1]) / 2, dd[-1:]]; nn = np.stack([-nn[:, 1], nn[:, 0]], 1)
        nn /= np.linalg.norm(nn, axis=1, keepdims=True) + 1e-6
        gauge = 0.72 * 4
        if r["k"] in ("rail", "funicular"):
            bw = int(round(3.4 * 4 * k))
            cv2.polylines(m["rcase"], [q], False, 255, bw + 2 * ink, cv2.LINE_AA, shift=4)
            cv2.polylines(m["rbed"], [q], False, 255, bw, cv2.LINE_AA, shift=4)
            seg = np.hypot(*np.diff(a, axis=0).T); cum = np.r_[0, np.cumsum(seg)]
            for s in np.arange(0, cum[-1], 0.75 * 4):
                i = min(np.searchsorted(cum, s, side="right") - 1, len(seg) - 1)
                d = (a[i + 1] - a[i]) / max(seg[i], 1e-6)
                c = a[i] + d * (s - cum[i])
                nrm = np.array((-d[1], d[0])) * 1.25 * 4
                p1, p2 = ((c - nrm - (x0, y0)) * k * S).round().astype(int), ((c + nrm - (x0, y0)) * k * S).round().astype(int)
                cv2.line(m["sleep"], tuple(p1), tuple(p2), 255, max(1, round(0.25 * 4 * k)), cv2.LINE_AA, shift=4)
        tgt = "rail" if r["k"] != "tram" else "tram"
        for sgn in (-1, 1):
            qq = (((a + nn * sgn * gauge) - (x0, y0)) * k * S).round().astype(np.int32)
            cv2.polylines(m[tgt], [qq], False, 255, 1, cv2.LINE_AA, shift=4)
    return {n: v.astype(np.float32) / 255 for n, v in m.items()}


# ---------------------------------------------------------------- walls (L2)
def draw_walls(bid, b, k, shape, light):
    """Upright faces for walls, sorted far to near. Heights: retaining walls from the terrain step across the
    wall, fortification walls at least 6 m, garden walls 1.8 m."""
    H, W = shape
    rgba = np.zeros((H, W, 4), np.float32)
    els = json.loads((inputs_dir(bid) / "osm_extra.json").read_text())["elements"]
    faces = []
    for el in els:
        tg = el.get("tags", {})
        bar, hist = tg.get("barrier"), tg.get("historic")
        if not (bar in ("retaining_wall", "city_wall", "wall") or hist == "citywalls") or "geometry" not in el:
            continue
        en = np.array([lonlat_to_en(p["lon"], p["lat"]) for p in el["geometry"]])
        # densify to <= 3 m segments
        pts = [en[0]]
        for a, c in zip(en[:-1], en[1:]):
            n_ = max(1, int(np.hypot(*(c - a)) / 3))
            pts += [a + (c - a) * t for t in np.linspace(0, 1, n_ + 1)[1:]]
        en = np.array(pts)
        for a, c in zip(en[:-1], en[1:]):
            d = c - a
            L_ = np.hypot(*d)
            if L_ < 0.2:
                continue
            nrm = np.array((-d[1], d[0])) / L_
            mid = (a + c) / 2
            z1, z2 = float(ground_z(*(mid + nrm * 2.0))), float(ground_z(*(mid - nrm * 2.0)))
            zlo, zhi = min(z1, z2), max(z1, z2)
            if bar == "wall" and not hist:
                hgt = 1.8
            elif bar == "city_wall" or hist == "citywalls":
                hgt = max(6.0, zhi - zlo + 1.0)
            else:
                hgt = float(np.clip(zhi - zlo + 0.6, 1.5, 14))
            base = min(float(ground_z(*a)), float(ground_z(*c)), zlo + 0.5) if bar != "wall" else None
            za = float(ground_z(*a)) if base is None else base
            zc = float(ground_z(*c)) if base is None else base
            # outward normal: facing the lower ground (or the camera, for free-standing walls)
            out = nrm if z1 < z2 else -nrm
            if bar == "wall" and not hist:
                out = nrm if (nrm @ np.array((1, -1))) > 0 else -nrm
            faces.append((a, c, za, zc, hgt, out, bar or hist))
    # camera looks north-west: depth grows towards the north-west, so draw far (large f) first
    f = lambda a: (-(a[0] - ORIGIN_E) + (a[1] - ORIGIN_N))  # noqa: E731
    faces.sort(key=lambda fc: -f((fc[0] + fc[1]) / 2))
    stone = {"retaining_wall": (200, 174, 128), "city_wall": (210, 180, 128), "citywalls": (210, 180, 128),
             "wall": (204, 186, 150)}
    img = np.zeros((H, W, 3), np.uint8)
    alpha = np.zeros((H, W), np.uint8)
    inkimg = np.zeros((H, W), np.uint8)
    S = 16
    lw = max(1, round(2 * k))
    for a, c, za, zc, hgt, out, kind_ in faces:
        p = np.array([en_to_map(*a, za), en_to_map(*c, zc), en_to_map(*c, zc + hgt), en_to_map(*a, za + hgt)], float)
        p = (p - (b["x0"], b["y0"])) * k
        if (p[:, 0].max() < 0 or p[:, 0].min() > W or p[:, 1].max() < 0 or p[:, 1].min() > H):
            continue
        n3 = np.array((out[0], out[1], 0.0))
        lit = 0.72 + 0.4 * max(0.0, float(n3 @ light))
        facing = (n3[0] * (1 / math.sqrt(2)) - n3[1] * (1 / math.sqrt(2)))  # towards the camera (south-east)
        col = np.array(stone.get(kind_, (180, 166, 140))) * (lit if facing > -0.2 else lit * 0.85)
        q = np.round(p * S).astype(np.int32)
        cv2.fillPoly(img, [q], tuple(int(v) for v in col), cv2.LINE_AA, shift=4)
        cv2.fillPoly(alpha, [q], 255, cv2.LINE_AA, shift=4)
        cv2.polylines(inkimg, [q[2:4]], False, 255, lw, cv2.LINE_AA, shift=4)          # top edge
        cv2.polylines(inkimg, [q[[0, 3]]], False, 140, 1, cv2.LINE_AA, shift=4)       # faint joints
        # stone courses every 0.8 m on tall walls
        if hgt > 2.5:
            for zz in np.arange(0.8, hgt - 0.3, 0.8):
                l2 = np.array([en_to_map(*a, za + zz), en_to_map(*c, zc + zz)], float)
                l2 = np.round((l2 - (b["x0"], b["y0"])) * k * S).astype(np.int32)
                cv2.polylines(inkimg, [l2], False, 45, 1, cv2.LINE_AA, shift=4)
    rgba[..., :3] = img
    ink = inkimg.astype(np.float32)[..., None] / 255
    rgba[..., :3] = rgba[..., :3] * (1 - ink * 0.75) + INK * ink * 0.75
    rgba[..., 3] = alpha
    return rgba


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bid", nargs="?", default="b00")
    ap.add_argument("--k", type=float, default=0.5)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    b = block(args.bid)
    k = args.k
    od = out_dir(args.bid) / (f"k{int(k * 100)}" if k != 1 else "full")
    od.mkdir(parents=True, exist_ok=True)
    G = ground_pass(b, k)
    H, W = G.shape[:2]
    ok = ~np.isnan(G[..., 0])
    e = np.nan_to_num(G[..., 0]) + ORIGIN_E
    n = np.nan_to_num(G[..., 1]) + ORIGIN_N
    box = block_en(b)
    e0, e1, n0, n1 = box
    gx, gy = (e - e0) / RES, (n1 - n) / RES
    lc = sample(landcover_grid(args.bid, box), gx, gy, nearest=True)
    canopy = sample(tree_canopy_grid(args.bid, box), gx, gy, nearest=True) > 0
    nrm = slope_normals(G)
    slope = np.degrees(np.arccos(np.clip(nrm[..., 2], 0, 1)))
    # orthophoto: green or paved where OSM is silent
    photo = np.asarray(cut("frames", "jpg", "RGB", (16, 24, 40), b, k, Image.BILINEAR)).astype(np.float32)
    kd = kinds(b, k)
    vis_ground = kd > 200
    exg = 2 * photo[..., 1] - photo[..., 0] - photo[..., 2]
    green = cv2.GaussianBlur((exg > 14).astype(np.float32) * vis_ground, (0, 0), 3 * k * 4) > 0.45
    cls = np.where(lc == 255, np.where(green, GRASS, PAVED), lc).astype(np.uint8)
    cls[(cls == GRASS) & canopy & (lc == 255)] = WOOD  # under tree crowns: woods floor
    # clean small specks
    cls = cv2.medianBlur(cls, 5 if k >= 0.5 else 3)
    art = np.asarray(today(b, k)).astype(np.float32)
    pal = sample_palette(cls, art, vis_ground & ~canopy & (slope < 25))
    print("palette:", {NAMES[c]: tuple(int(v) for v in pal[c]) for c in pal})

    # --- L1: flat colours, mottling, hill shading, paper, ink between areas
    base = np.zeros((H, W, 3), np.float32)
    for c, col in pal.items():
        base[cls == c] = col
    mott = noise((H, W), 40 * k * 4 / 4, 1) * 0.5 + noise((H, W), 10 * k * 4 / 4, 2) * 0.35
    soft = np.isin(cls, (GRASS, WOOD, SCRUB, MEADOW, GARDEN, CEMETERY, PITCH))
    base *= (1 + mott[..., None] * np.where(soft, 0.10, 0.04)[..., None])
    # texture strokes: grass tufts / meadow mowing stripes / garden beds / cobbles on squares
    tuft = (noise((H, W), 2.2, 3) > 0.55) & np.isin(cls, (GRASS, MEADOW, SCRUB, WOOD, CEMETERY))
    base[tuft] *= 0.88
    stripes = hatch((H, W), max(3, 6 * k * 4 / 2), 33, 1, 4, 0.3) * (cls == MEADOW)
    base *= (1 - 0.08 * stripes[..., None])
    beds = hatch((H, W), max(3, 3 * k * 4), 63, max(1, k * 2), 5, 0.1) * (cls == GARDEN)
    base *= (1 - 0.12 * beds[..., None])
    cob = np.maximum(hatch((H, W), max(3, 1.2 * k * 4 * 2), 27, 1), hatch((H, W), max(3, 1.2 * k * 4 * 2), 153, 1))
    base *= (1 - 0.07 * (cob * np.isin(cls, (SQUARE,)))[..., None])
    # light from the south-south-west, high: lights the cliffs that face the viewer, like the painting
    az, el = math.radians(200), math.radians(42)
    light = np.array((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)), np.float32)
    shade = np.clip(nrm @ light, 0, 1)
    flat = float(light[2])
    base *= np.clip(1 + (shade - flat) * 0.9, 0.55, 1.25)[..., None]
    # ink between land-cover areas (not inside the noisy ortho classes at full strength)
    e_cls = edges(cls, max(1, round(2 * k)))
    osm_edge = edges(np.where(lc == 255, 254, lc).astype(np.uint8), max(1, round(2 * k)))
    inkm = np.where(osm_edge, 0.55, np.where(e_cls, 0.25, 0.0))
    base = base * (1 - inkm[..., None]) + INK * inkm[..., None]
    paper = 1 + noise((H, W), 1.2, 7) * 0.035 + noise((H, W), 120 * k, 8) * 0.03
    base *= paper[..., None]
    base[~ok] = (16, 24, 40)
    L1 = np.clip(base, 0, 255).astype(np.uint8)

    # --- L2 relief: steep slopes get rock, hatching down the fall line, ink at the top edge
    steep = np.clip((slope - 32) / 18, 0, 1) * ok
    steep = cv2.GaussianBlur(steep.astype(np.float32), (0, 0), max(0.6, k * 1.5))
    rock = np.array((198, 166, 112), np.float32)
    rockcol = rock * np.clip(0.72 + shade * 0.5, 0.6, 1.2)[..., None]
    rockcol *= (1 + noise((H, W), 6 * k * 4 / 4, 11)[..., None] * 0.14)
    crev = (noise((H, W), 3 * k * 4 / 2, 14) > 0.45)  # dark clefts in the rock
    rockcol[crev] *= 0.72
    # vertical strokes (cliffs read as upright rock in this view), broken by noise
    vs = hatch((H, W), max(3, 2.6 * k * 4 / 2 * 2), 90, 1, 12, 0.5) * (noise((H, W), 8, 13) > -0.2)
    rockcol = rockcol * (1 - 0.45 * vs[..., None]) + INK * 0.45 * vs[..., None]
    a2 = steep.copy()
    top = edges((steep > 0.5).astype(np.uint8), max(1, round(2 * k))) & (steep > 0.2)
    rockcol[top] = rockcol[top] * 0.4 + INK * 0.6
    L2 = np.dstack((rockcol, a2 * 255)).clip(0, 255).astype(np.uint8)
    # cliffs from OSM: an ink line along the top
    S = 16
    cl = np.zeros((H, W), np.uint8)
    for el in json.loads((inputs_dir(args.bid) / "osm_extra.json").read_text())["elements"]:
        if el.get("tags", {}).get("natural") == "cliff" and "geometry" in el:
            en = np.array([lonlat_to_en(p["lon"], p["lat"]) for p in el["geometry"]])
            q = np.array(en_to_map(en[:, 0], en[:, 1], ground_z(en[:, 0], en[:, 1]))).T
            q = np.round((q - (b["x0"], b["y0"])) * k * S).astype(np.int32)
            cv2.polylines(cl, [q], False, 255, max(1, round(2.5 * k)), cv2.LINE_AA, shift=4)
    c = cl > 0
    L2[c, :3] = (L2[c, :3] * 0.3 + INK * 0.7).astype(np.uint8)
    L2[c, 3] = np.maximum(L2[c, 3], cl[c])

    # --- L3 water: flat, a lighter band along the bank, inked bank
    wat = (cls == WATER) & ok
    wcol = np.array((44, 108, 118), np.float32)
    if "water" in NAMES:
        m_ = wat & vis_ground
        if m_.sum() > 1000:
            wcol = 0.5 * np.median(art[m_], axis=0) + 0.5 * wcol
    dist = cv2.distanceTransform(wat.astype(np.uint8), cv2.DIST_L2, 3)
    band = np.clip(1 - dist / max(2, 3 * k * 4 / 2), 0, 1)
    wimg = np.zeros((H, W, 3), np.float32) + wcol
    wimg *= (1 + noise((H, W), 30 * k, 21)[..., None] * 0.04)
    wimg = wimg * (1 - 0.25 * band[..., None]) + np.array((150, 190, 180)) * 0.25 * band[..., None]
    bank = edges(wat.astype(np.uint8), max(1, round(2 * k))) & wat
    wimg[bank] = wimg[bank] * 0.35 + INK * 0.65
    L3 = np.dstack((wimg, wat * 255.0)).clip(0, 255).astype(np.uint8)

    # --- L4 roads, paths, rails
    L = json.loads((ROOT / "web" / "public" / "data" / "lines.json").read_text())
    rm = draw_roads(L, b, k, (H, W))
    road_col = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    def put(mask, col, a=1.0):  # noqa: E301
        nonlocal road_col, alpha
        m = (mask * a)[..., None]
        road_col = road_col * (1 - m) + np.array(col, np.float32) * m
        alpha = np.maximum(alpha, mask * a)
    put(rm["rcase"], INK)
    put(rm["rbed"], (138, 124, 108))
    put(rm["sleep"], (96, 80, 66), 0.8)
    put(rm["case"], INK * 1.1)
    asphalt = np.array(pal[PARKING]) * 0.55 + np.array(ROAD_COL["road"]) * 0.45
    put(rm["path"], ROAD_COL["path"])
    put(rm["steps"], ROAD_COL["steps"])
    put(rm["ped"], np.array(pal[SQUARE]) * 0.5 + np.array(ROAD_COL["ped"]) * 0.5)
    put(rm["road"], asphalt)
    tex = 1 + noise((H, W), 2, 31) * 0.03
    road_col *= tex[..., None] * np.clip(1 + (shade - flat) * 0.4, 0.8, 1.1)[..., None]
    put(rm["dash"] * (rm["road"] + rm["steps"] > 0.5), (236, 232, 220), 0.9)
    put(rm["rail"], (58, 52, 50))
    put(rm["tram"] * (alpha > 0), (60, 56, 54), 0.8)
    L4 = np.dstack((road_col, alpha * 255)).clip(0, 255).astype(np.uint8)

    # --- walls (L2, drawn above the roads)
    LW = draw_walls(args.bid, b, k, (H, W), light).clip(0, 255).astype(np.uint8)

    def over(dst, src):
        a = src[..., 3:4].astype(np.float32) / 255
        return dst * (1 - a) + src[..., :3].astype(np.float32) * a
    stack = L1.astype(np.float32)
    for lay in (L2, L3, L4, LW):
        stack = over(stack, lay)
    stack = stack.clip(0, 255).astype(np.uint8)
    for name, arr in (("L1_ground", L1), ("L2_relief", L2), ("L2_walls", LW), ("L3_water", L3), ("L4_roads", L4),
                      ("stack_A", stack)):
        Image.fromarray(arr).save(od / f"{name}.png")
    Image.fromarray((wat * 255).astype(np.uint8)).save(od / "water_mask.png")
    np.save(od / "landcover.npy", cls)
    print("written to", od, (W, H))


if __name__ == "__main__":
    main()
