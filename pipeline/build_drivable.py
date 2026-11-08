"""Drivable surface map: where on the painted map a road vehicle may really be drawn, and how wide each street is.

One cell = CELL map px (0.5 m across), over the whole map, filled only near the streets that carry traffic. Each cell
is one of
    0  nothing (not near a street, or visible ground that is not road: pavement, grass, a square)
    1  road surface
    2  bridge deck (the 3D render's deck surface, visible from above)
    3  water
    4  inside a building: the ground point lies in a building's footprint (a vehicle there would be in the facade),
       or the painter drew a building there although the 3D model has open ground
    5  hidden: the ground is behind a building or wall nearer the camera (the occlusion cut hides vehicles there)
    6  unpainted: no art here (the empty map edge)
from these sources:
  - a corridor along every lines.json street that carries traffic, as wide as its estimated carriageway (the OSM
    width tag, else lanes x 3.2 m, else a default by kind) plus a margin for the painter's drift;
  - the kinds pass of the 3D render (data/work/frames_kind: ground, deck, wall, roof);
  - building footprints: the roofs of the 3D buildings (data/work/buildings.npz) laid on their ground height;
  - water: the painted water mask (web/public/data/water_mask.png, from build_water_mask.py) and the OSM water
    polygons in lines.json (where the art is not road-coloured);
  - road colour in the painted art (the summer day tiles, web/public/tiles/map_files/15): a colour model learnt from
    the art itself, road centrelines against the ground beside the streets, so the map follows the road the
    painter actually drew.

Output:
  web/public/data/drivable/index.json   {"cell": map px per cell, "tile": cells per tile side, "cols", "rows",
                                         "tiles": ["tx_ty", ...] (tiles not listed are all 0), "values": {...}}
  web/public/data/drivable/<tx>_<ty>.png  8-bit grey tiles of cell values; tile (tx, ty) starts at map px
                                         (tx * tile * cell, ty * tile * cell)
  web/public/data/lines.json            every street that carries traffic gets "w", its carriageway width in metres,
                                         measured across the drivable map every 10 m (median, within half and one and
                                         a half times the OSM estimate), and "c" where the painted road's centre is
                                         off the line (m to the right of the drawn direction). project_lines.py does
                                         the same when it runs and this map exists.
Usage: build_drivable.py [--debug out.jpg x0 y0 x1 y1] [--no-widths]
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import binary_closing, label

from common import ELEV, RAW, ROOT, WORK, R
from flowfield import Field as FlowField

Image.MAX_IMAGE_PIXELS = None
CELL = 2                 # map px per cell
TILE = 512               # cells per output tile side
MPP = 0.25               # metres per map px
LANE_W = 3.2
VALUES = {"none": 0, "road": 1, "deck": 2, "water": 3, "building": 4, "hidden": 5, "unpainted": 6}
BACKGROUND = np.array([16, 24, 40])   # the empty map edge in the art (RGB)
# Streets the traffic simulation uses (web/src/sim/traffic.ts: DRIVE and EXTRA).
DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
         "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "pedestrian", "service",
         "busway"}
# Carriageway width (m) by kind when OSM gives neither width nor lanes; one-way ways take 70% of it.
DEFAULT_W = {"motorway": 7.5, "trunk": 7.5, "primary": 7.0, "secondary": 6.5, "tertiary": 6.0, "unclassified": 5.0,
             "residential": 5.5, "living_street": 4.5, "service": 3.5, "pedestrian": 5.0, "busway": 6.5}
LINK_W = 4.5
WIDTH_STEP_M = 10.0      # width samples along a street
WALK_STEP_M = 0.25       # step of the walk across it
GAP_M = 0.75             # a gap in the road colour this wide (markings, a manhole) does not end the road


def default_width(way, tags):
    """The carriageway width OSM suggests: the width tag, else lanes x 3.2 m, else a default by kind."""
    t = tags.get(way["id"], {})
    try:
        w = float(str(t.get("width", "")).replace("m", "").strip())
        if 2 <= w <= 40:
            return w
    except ValueError:
        pass
    try:
        n = int(str(way.get("l") or "").split(";")[0])
        if 1 <= n <= 8:
            return n * LANE_W
    except ValueError:
        pass
    k = way.get("k", "")
    w = LINK_W if k.endswith("_link") else DEFAULT_W.get(k, 5.0)
    return w * 0.7 if way.get("o") else w


def lateral(dx, dy):
    """Map px per metre across a stretch of street drawn along (dx, dy) map px (the map is a 2:1 view: a metre is 4
    map px left-right and 2 up-down), and ground metres per map px along it."""
    fx, fy = dx, 2 * dy
    n = math.hypot(fx, fy) or 1.0
    return (-fy / n * 4, fx / n / 2 * 4), (n / 4) / (math.hypot(dx, dy) or 1.0)


def line_pts(w):
    """A way's points where the painting has it: lines.json "p" moved through the road layer of the render ->
    painting field (flow_field.py), when MOVE is set (main(), unless --no-field)."""
    p = np.array(w["p"], float).reshape(-1, 2)
    return MOVE.move(p) if MOVE is not None else p


MOVE = None


def corridor(lines, shape, half_m, shift_m=lambda w: 0.0):
    """Union of bands along the streets, half_m(way) metres either side of a line shift_m(way) metres to the right
    of the drawn one, at cell resolution."""
    H, W = shape
    m = np.zeros((H, W), np.uint8)
    for w in lines:
        p = line_pts(w)
        hm, sh = half_m(w), shift_m(w)
        for (ax, ay), (bx, by) in zip(p[:-1], p[1:]):
            (lx, ly), _ = lateral(bx - ax, by - ay)
            ox, oy = lx * hm, ly * hm
            cx, cy = lx * sh, ly * sh
            quad = np.array([[ax + cx + ox, ay + cy + oy], [bx + cx + ox, by + cy + oy], [bx + cx - ox, by + cy - oy],
                             [ax + cx - ox, ay + cy - oy]])
            cv2.fillPoly(m, [np.round(quad / CELL * 4).astype(np.int32)], 1, shift=2)
        if not sh:
            r = max(1, int(round(hm * 3 / CELL)))      # round joins (about the mean of the 4 and 2 px per metre)
            for x, y in p:
                cv2.circle(m, (int(round(x / CELL * 4)), int(round(y / CELL * 4))), r * 4, 1, -1, shift=2)
    return m.astype(bool)


def lane_band(lines, shape):
    """The carriageways as the traffic simulation lays its lanes: each street that carries traffic, w metres wide
    (lines.json "w"), centred on the painted road ("c"). Streets without a measured width are left out."""
    roads = [w for w in lines["roads"] if w.get("k") in DRIVE and not w.get("t") and w.get("w") and len(w["p"]) >= 4]
    return corridor(roads, shape, lambda w: w["w"] / 2, lambda w: w.get("c", 0.0))


def kinds(shape):
    """Per cell: ground visible, deck visible (half or more of its map px), from the kinds pass."""
    H, W = shape
    mos = json.loads((WORK / "mosaic.json").read_text())
    F = mos["frame"]
    ground = np.zeros((H, W), bool)
    deck = np.zeros((H, W), bool)
    for r in range(mos["rows"]):
        for c in range(mos["cols"]):
            k = np.asarray(Image.open(WORK / "frames_kind" / f"{c}_{r}.png").convert("L"))
            n = F // CELL
            k = k.reshape(n, CELL, n, CELL)
            g = (k > 200).mean(axis=(1, 3)) >= 0.5
            d = ((k > 100) & (k <= 200)).mean(axis=(1, 3)) >= 0.5
            ys, xs = r * n, c * n
            hh, ww = min(n, H - ys), min(n, W - xs)
            if hh > 0 and ww > 0:
                ground[ys:ys + hh, xs:xs + ww] = g[:hh, :ww]
                deck[ys:ys + hh, xs:xs + ww] = d[:hh, :ww]
    return ground, deck


def painted_water(shape, data):
    """The painted water mask (build_water_mask.py), at least half a metre inside the bank, at cell resolution."""
    H, W = shape
    info = json.loads((data / "water_mask.json").read_text())
    atlas = np.asarray(Image.open(data / "water_mask.png").convert("RGB"))[..., 0]
    S, C, cols = info["scale"], info["chunk"], info["cols"]
    k = CELL / S
    assert k == 1, "the water mask and the drivable map share one grid (2 map px)"
    ox, oy = info["x0"] // CELL, info["y0"] // CELL
    out = np.zeros((H, W), bool)
    ch = info["chunks"]
    for n in range(len(ch) // 2):
        i, j = ch[2 * n], ch[2 * n + 1]
        c, r = n % cols, n // cols
        blk = atlas[r * (C + 2) + 1:r * (C + 2) + 1 + C, c * (C + 2) + 1:c * (C + 2) + 1 + C]
        y0, x0 = oy + j * C, ox + i * C
        hh, ww = min(C, H - y0), min(C, W - x0)
        if hh > 0 and ww > 0:
            out[y0:y0 + hh, x0:x0 + ww] = blk[:hh, :ww] >= 8
    return out


def osm_water(lines, shape):
    m = np.zeros(shape, np.uint8)
    for w in lines["water"]:
        p = np.array(w["p"], float).reshape(-1, 2)
        if len(p) >= 3:
            cv2.fillPoly(m, [np.round(p / CELL * 4).astype(np.int32)], 1, shift=2)
    return m.astype(bool)


def art(shape, tiles):
    """The summer day art (deepest tile level), averaged to cells: (H, W, 3) uint8."""
    H, W = shape
    out = np.zeros((H, W, 3), np.uint8)
    lvl = max(int(p.name) for p in tiles.iterdir() if p.name.isdigit())
    T = 512
    for f in (tiles / str(lvl)).glob("*.webp"):
        c, r = map(int, f.stem.split("_"))
        a = np.asarray(Image.open(f).convert("RGB"), np.float32)
        h, w = a.shape[0] // CELL * CELL, a.shape[1] // CELL * CELL
        a = a[:h, :w].reshape(h // CELL, CELL, w // CELL, CELL, 3).mean(axis=(1, 3))
        ys, xs = r * T // CELL, c * T // CELL
        hh, ww = min(a.shape[0], H - ys), min(a.shape[1], W - xs)
        out[ys:ys + hh, xs:xs + ww] = (a[:hh, :ww] + 0.5).astype(np.uint8)
    return out


def footprints(shape):
    """Building footprints at cell resolution: every roof triangle of the 3D buildings, laid on the building's
    ground height and projected like the map."""
    H, W = shape
    mos = json.loads((WORK / "mosaic.json").read_text())
    d = np.load(WORK / "buildings.npz")
    roof = d["tri_kind"] == 1
    t = d["tris"][roof][..., :2].astype(np.float64)               # local E, N
    z = d["bld_ground"][d["tri_bld"][roof], 2].astype(np.float64)[:, None]
    sx = (t[..., 0] + t[..., 1]) * R
    sy = (-t[..., 0] + t[..., 1]) * R * math.sin(ELEV) + z * math.cos(ELEV)
    X = (sx - mos["sx0"]) / mos["mpp"] / CELL
    Y = (mos["sy1"] - sy) / mos["mpp"] / CELL
    pts = np.round(np.stack([X, Y], -1) * 4).astype(np.int32)
    m = np.zeros((H, W), np.uint8)
    for i in range(0, len(pts), 200000):
        cv2.fillPoly(m, list(pts[i:i + 200000]), 1, shift=2)
    return m.astype(bool)


def colour_index(rgb):
    q = rgb >> 4
    return (q[..., 0].astype(np.int32) << 8) | (q[..., 1].astype(np.int32) << 4) | q[..., 2]


def colour_model(rgb, pos, neg, bld):
    """Colour classes learnt from the art itself, on 4096 colour bins: road (road centrelines), beside (the ground
    beside the streets: pavements, verges, squares) and building (walls and roofs near the streets, where the 3D
    model has them). Returns, per cell, (road-coloured, painted as a building): road-coloured where the colour is
    clearly likelier on a road than beside one; painted as a building where it is clearly likelier on a building than
    on either (the painter put a facade where the 3D model has open ground)."""
    ci = colour_index(rgb)
    hist = [np.bincount(ci[m], minlength=4096).astype(np.float64) for m in (pos, neg, bld)]
    # densities with a little smoothing towards "no evidence" (an empty bin is equally likely in every class)
    p = [(h + 5 * h.sum() / 4096) / (h.sum() * 2) for h in hist]
    road_bins = (p[0] / p[1] > 1.3) & (hist[0] >= 10)
    bld_bins = (p[2] / np.maximum(p[0], p[1]) > 2.0) & (hist[2] >= 50)
    road = road_bins[ci]
    # specks out, small gaps (markings) in
    road = cv2.morphologyEx(road.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    road = cv2.morphologyEx(road, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    bld = cv2.morphologyEx(bld_bins[ci].astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    print(f"colour model: {pos.sum()} centreline cells, {neg.sum()} beside, {bld.sum()} building; "
          f"{road_bins.sum()} of 4096 colours count as road, {bld_bins.sum()} as building", flush=True)
    return road, bld


def measure_widths(roads, grid, tags):
    """Carriageway width (m) of every street that carries traffic, and where the painted road's centre lies across
    the drawn line (m to the right of its direction; the painter did not always put the road exactly on the OSM line).
    Every 10 m, across the drivable map: the run of road or deck cells through the line, or the nearest one beside
    it (short gaps bridged). Runs that end against a hidden cell (behind a building) are not measured. Medians, the
    width within half and one and a half times the OSM estimate, the shift at most half the width and 3 m.
    Returns {way id: (w, c)}."""
    H, W = grid.shape
    surface = (grid == VALUES["road"]) | (grid == VALUES["deck"])
    blocked = (grid == VALUES["hidden"]) | (grid == VALUES["building"]) | (grid == VALUES["unpainted"])
    out = {}
    gap = int(round(GAP_M / WALK_STEP_M))
    for w in roads:
        if w.get("k") not in DRIVE or w.get("t"):
            continue
        w0 = default_width(w, tags)
        p = line_pts(w)
        lo, hi = 0.5 * w0, 1.5 * w0
        reach = min(max(w0 * 0.75 + 1.5, 3.0), 14.0)
        n = int(math.ceil(reach / WALK_STEP_M))
        k = np.arange(-n, n + 1) * WALK_STEP_M
        widths, centres = [], []
        carry = WIDTH_STEP_M / 2
        for (ax, ay), (bx, by) in zip(p[:-1], p[1:]):
            (lx, ly), m_per_px = lateral(bx - ax, by - ay)
            L = math.hypot(bx - ax, by - ay) * m_per_px
            s_ = carry
            while s_ < L:
                f = s_ / L
                cx, cy = ax + (bx - ax) * f, ay + (by - ay) * f
                xs = ((cx + lx * k) / CELL).astype(int)
                ys = ((cy + ly * k) / CELL).astype(int)
                ok = (xs >= 0) & (ys >= 0) & (xs < W) & (ys < H)
                on = np.zeros(len(k), bool)
                bl = np.ones(len(k), bool)
                on[ok] = surface[ys[ok], xs[ok]]
                bl[ok] = blocked[ys[ok], xs[ok]]
                s_ += WIDTH_STEP_M
                if not on.any():
                    continue
                closed = binary_closing(np.r_[False, on, False], np.ones(gap + 1, bool))[1:-1] | on
                lab, nr = label(closed)
                # the run through the line, else the nearest one
                if closed[n]:
                    r = lab[n]
                else:
                    idx = np.flatnonzero(closed)
                    r = lab[idx[np.argmin(np.abs(idx - n))]]
                ii = np.flatnonzero(lab == r)
                i0, i1 = ii[0], ii[-1]
                if (i0 > 0 and bl[i0 - 1]) or (i1 < len(k) - 1 and bl[i1 + 1]) or i0 == 0 or i1 == len(k) - 1:
                    continue                                   # cut short by a building, or wider than we look
                widths.append((i1 - i0 + 1) * WALK_STEP_M)
                centres.append((k[i0] + k[i1]) / 2)
            carry = s_ - L
        if len(widths) >= 3:
            wm = min(max(float(np.median(widths)), lo), hi)
            cm = float(np.median(centres))
            lim = min(3.0, wm / 2)
            cm = min(max(cm, -lim), lim)
        else:
            wm, cm = w0, 0.0
        out[w["id"]] = (round(wm, 1), round(cm, 1))
    return out


def osm_tags():
    els = json.loads((RAW / "osm" / "lines.json").read_text())["elements"]
    return {e["id"]: e.get("tags", {}) for e in els if e.get("type") == "way"}


def add_widths(lines, grid, tags):
    """Writes "w" (width, m) and, where the painted road is off the line by 0.2 m or more, "c" (its centre, m to the
    right of the drawn direction) into every street of lines (a lines.json dict) that carries traffic."""
    ws = measure_widths(lines["roads"], grid, tags)
    for w in lines["roads"]:
        w.pop("c", None)
        if w["id"] in ws:
            w["w"], c = ws[w["id"]]
            if abs(c) >= 0.2:
                w["c"] = c
    return ws


def load_grid(data=ROOT / "web/public/data"):
    """The whole drivable map from its tiles: (grid uint8, index)."""
    d = data / "drivable"
    idx = json.loads((d / "index.json").read_text())
    T = idx["tile"]
    grid = np.zeros((idx["rows"] * T, idx["cols"] * T), np.uint8)
    for name in idx["tiles"]:
        tx, ty = map(int, name.split("_"))
        a = np.asarray(Image.open(d / f"{name}.png"))
        grid[ty * T:ty * T + a.shape[0], tx * T:tx * T + a.shape[1]] = a
    return grid[:idx["h"], :idx["w"]], idx


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "web/public/data")
    ap.add_argument("--tiles", type=Path, default=ROOT / "web/public/tiles/map_files")
    ap.add_argument("--debug", nargs=5, metavar=("OUT", "X0", "Y0", "X1", "Y1"),
                    help="write the map over the art for a map px box")
    ap.add_argument("--no-widths", action="store_true", help="leave lines.json alone")
    ap.add_argument("--widths-only", action="store_true", help="only measure the widths again, on the map as built")
    ap.add_argument("--no-field", action="store_true", help="leave the render's parts where the render has them")
    a = ap.parse_args()
    global MOVE
    MOVE = None if a.no_field else FlowField.load("road")
    FB = None if a.no_field else FlowField.load("built")
    FG = None if a.no_field else FlowField.load("ground")

    mos = json.loads((WORK / "mosaic.json").read_text())
    MW, MH = mos["cols"] * mos["frame"], mos["rows"] * mos["frame"]
    shape = (MH // CELL, MW // CELL)
    lines = json.loads((a.data / "lines.json").read_text())
    tags = osm_tags()
    roads = [w for w in lines["roads"] if w.get("k") in DRIVE and not w.get("t") and len(w["p"]) >= 4]
    w0 = {w["id"]: default_width(w, tags) for w in roads}
    if a.widths_only:
        widths(a, lines, load_grid(a.data)[0], tags, w0)
        return

    near = corridor(roads, shape, lambda w: min(max(w0[w["id"]] * 0.75 + 1.5, 3.0), 14.0))
    core = corridor(roads, shape, lambda w: 1.2)
    centre = corridor([w for w in roads if w.get("k") in ("primary", "secondary", "tertiary", "residential",
                                                            "unclassified") and not w.get("b")], shape, lambda w: 1.0)
    ring = corridor(roads, shape, lambda w: min(max(w0[w["id"]] * 0.75 + 1.5, 3.0), 14.0) + 6.0) & ~near
    print("corridors", f"{near.mean():.1%} of the map", flush=True)
    ground, deck = kinds(shape)
    if FB is not None:
        # the render's parts to where the painting has them: what the kinds pass shows as ground ends at building
        # outlines (the built layer moves those), bridge decks and OSM water are on the ground layer
        ground = FB.warp(ground.astype(np.uint8), CELL).astype(bool)
        deck = FG.warp(deck.astype(np.uint8), CELL).astype(bool)
        print("kinds moved through the field (flow_field.py)", flush=True)
    print("kinds", flush=True)
    water = painted_water(shape, a.data)
    wosm = osm_water(lines, shape)
    if FG is not None:
        wosm = FG.warp(wosm.astype(np.uint8), CELL).astype(bool)
    rgb = art(shape, a.tiles)
    unpainted = (np.abs(rgb.astype(np.int16) - BACKGROUND).max(axis=2) <= 8)
    foot = footprints(shape)
    if FB is not None:
        foot = FB.warp(foot.astype(np.uint8), CELL).astype(bool)
    print("art and footprints", flush=True)
    roadc, painted_bld = colour_model(rgb, centre & ground & ~water & ~deck, ring & ground & ~water & ~wosm,
                                      near & ~ground & ~deck & ~unpainted)
    del rgb

    grid = np.zeros(shape, np.uint8)
    road = ground & (roadc | (core & ~painted_bld))
    grid[near & road] = VALUES["road"]
    grid[near & ground & ~road & (water | wosm)] = VALUES["water"]
    grid[near & water & ~road & ~deck] = VALUES["water"]
    grid[near & ~ground & ~deck] = VALUES["hidden"]
    grid[near & ~ground & ~deck & foot] = VALUES["building"]
    grid[near & ground & ~deck & painted_bld & ~roadc] = VALUES["building"]   # a facade painted on open ground
    grid[near & deck] = VALUES["deck"]
    grid[near & unpainted] = VALUES["unpainted"]
    for k, v in VALUES.items():
        print(f"  {k}: {(grid[near] == v).mean():.1%} of the corridors")

    out = a.data / "drivable"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    rows, cols = -(-shape[0] // TILE), -(-shape[1] // TILE)
    names, total = [], 0
    for ty in range(rows):
        for tx in range(cols):
            t = grid[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE]
            if not t.any():
                continue
            name = f"{tx}_{ty}"
            Image.fromarray(t).save(out / f"{name}.png", optimize=True, compress_level=9)
            total += (out / f"{name}.png").stat().st_size
            names.append(name)
    (out / "index.json").write_text(json.dumps({"cell": CELL, "tile": TILE, "cols": cols, "rows": rows,
                                                "w": shape[1], "h": shape[0], "tiles": names, "values": VALUES},
                                               separators=(",", ":")))
    print(f"{len(names)} tiles, {total / 1e6:.2f} MB in {out}", flush=True)

    if not a.no_widths:
        widths(a, lines, grid, tags, w0)

    if a.debug:
        dest, x0, y0, x1, y1 = a.debug[0], *map(int, a.debug[1:])
        debug_image(Path(dest), (x0, y0, x1, y1), grid, a.tiles)


def widths(a, lines, grid, tags, w0):
    ws = add_widths(lines, grid, tags)
    (a.data / "lines.json").write_text(json.dumps(lines, separators=(",", ":")))
    r = np.array([ws[i][0] / w0[i] for i in ws if i in w0])
    cs = np.array([abs(v[1]) for v in ws.values()])
    print(f"widths for {len(ws)} streets; measured / estimated: median {np.median(r):.2f}, "
          f"at the lower clamp {(r <= 0.501).mean():.0%}, at the upper {(r >= 1.499).mean():.0%}; painted road off "
          f"the line by 0.5 m or more on {(cs >= 0.5).mean():.0%}, 1.5 m or more on {(cs >= 1.5).mean():.0%}", flush=True)


def debug_image(dest, box, grid, tiles):
    """The map over the art: road green, deck cyan, water blue, inside a building red, hidden orange."""
    x0, y0, x1, y1 = box
    lvl = max(int(p.name) for p in tiles.iterdir() if p.name.isdigit())
    img = Image.new("RGB", (x1 - x0, y1 - y0))
    for ty in range(y0 // 512, (y1 - 1) // 512 + 1):
        for tx in range(x0 // 512, (x1 - 1) // 512 + 1):
            f = tiles / str(lvl) / f"{tx}_{ty}.webp"
            if f.exists():
                img.paste(Image.open(f).convert("RGB"), (tx * 512 - x0, ty * 512 - y0))
    a = np.asarray(img).astype(np.float32)
    g = grid[y0 // CELL:y1 // CELL, x0 // CELL:x1 // CELL]
    g = np.repeat(np.repeat(g, CELL, 0), CELL, 1)[:a.shape[0], :a.shape[1]]
    cols = {1: (0, 220, 0), 2: (0, 220, 220), 3: (0, 60, 255), 4: (255, 0, 0), 5: (255, 170, 0)}
    for v, c in cols.items():
        m = g == v
        a[m] = a[m] * 0.55 + np.array(c) * 0.45
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(dest, quality=88)
    print("debug", dest)


if __name__ == "__main__":
    main()
