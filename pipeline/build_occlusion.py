"""Foreground (occlusion) data for the moving vehicles, after Pixel Singapore's foreground layer.

Along a line of sight in this view, whatever is higher is nearer the camera. So a vehicle pixel is hidden when the
surface the height pass saw at that screen pixel is higher than the vehicle's body there. This script writes:

  web/public/data/occluders/<tx>_<ty>.png   RGB tiles of OCC_TILE x OCC_TILE px (fewer at the right and bottom
      edges), 1 px = SCALE map px; tile (tx, ty) starts OCC_TILE * (tx, ty) px into the box in occluders.json. Tiles
      that are all 0 are not written. The viewer loads only the tiles near the view (issue I13: the whole image used
      to be decoded at start, about 95 MB). The channels:
      R: ground layer. Height in decimetres (0..255, clipped at 25.5 m) of the visible surface above the ground
         that lies behind it along the line of sight (the terrain the ray reaches after passing the surface).
         0 = nothing in front of a road vehicle. Built things only (the 3D model); trees are in B.
      G: deck layer, only in a band above bridge and viaduct roads and rail: height in decimetres of the visible
         surface above the deck's own smoothed height (road_heights.json). Towers in front of a viaduct, or a
         higher deck crossing over it, show up here; the deck itself and anything behind it are 0.
      B: tree canopy in front of the lanes, soft: 0..255 is how much of a vehicle there is hidden (255 fully). Crowns
         are found in the painted art at full resolution (colour, and texture: crowns are busy, lawns smooth) on
         visible ground, kept where they cover a carriageway on screen (the road surface of the drivable map,
         build_drivable.py, or the lanes' strip from lines.json "w" and "c", which the crown hides in the art):
         such a tree stands nearer the camera than the lane. Then grown up the screen through the crown above
         (a vehicle's body rises there) and feathered over about 0.75 m, so that vehicles fade into a crown
         instead of being cut off. Crowns above a lane on screen that do not cover it stand behind it.
      (An RGB image, no alpha, so it decodes without premultiplied-alpha damage.)
     Both layers are only filled near roads, rail and tram lines (where vehicles can be); 0 elsewhere.
  web/public/data/occluders.json  {x0, y0, scale, w, h, unit, tile, tiles} placing the image on the map; tiles: the
      "tx_ty" names written.
  web/public/data/road_heights.json  per lines.json way id (bridges and viaducts that carry vehicles, roads and
      rail): samples about every 4 m along the polyline: x, y (the sample on the lines.json polyline, map px),
      s (distance along the lines.json polyline, map px), z (deck height above sea
      level, m), dz (z minus the height lines.json drew the line at; draw a vehicle dz*0.866/0.25 map px higher to
      sit it on the modelled deck), h (height above the terrain directly beneath, m).

Deck heights are a single lowest-cost path through candidate heights (0.5 m steps) per way, rising or falling no
faster than 1 in 8, and ways that meet are pulled to the same height at the shared point, so a vehicle's drawn
height never jumps between the deck, the valley below and a tree in front.

Every bridge or viaduct way that carries vehicles gets a profile: where its OSM geometry cannot be matched, the
deck runs straight between the terrain at its two ends, as lines.json drew it (dz 0).

Default box: the union of the painted areas in web/public/tiles/meta.json (traffic is only drawn there).
Needs web/public/data/drivable (run build_drivable.py first) and the painted tiles (web/public/tiles/map_files).
Usage: python build_occlusion.py [--work DIR] [--data DIR] [--scale 4] [--bbox x0 y0 x1 y1] [--debug out.jpg]
       python build_occlusion.py --split FILE.png   (tiles from a whole occluders.png of an earlier build, with the
                                                     x0, y0, scale and unit already in occluders.json)
"""
import argparse
import json
import math
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from common import ROOT, RAW, WORK, ORIGIN_E, ORIGIN_N, R, lonlat_to_en

Image.MAX_IMAGE_PIXELS = None
CE = 0.8660254                       # cos 30 degrees: screen metres per metre of height
MPP = 0.25
PX_PER_M_UP = CE / MPP               # map px a point moves up per metre of height (3.46)
CANOPY_CELL = 2                      # map px per cell of the canopy classification
CANOPY_FEATHER_M = 0.75              # soft edge of the canopy
BAND_UP_M = 6.0                      # vehicles reach at most this high (double-deck trains 4.6 m, plus slack)
DRIVE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street",
         "service", "busway", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
         "pedestrian"}                  # pedestrian: old-town streets with delivery and access traffic
HALF_WIDTH_PX = {"motorway": 40, "trunk": 36, "primary": 30, "secondary": 26, "tertiary": 24}  # else 18
RAIL = {"rail", "tram", "light_rail", "subway", "narrow_gauge", "funicular"}
SAMPLE_M = 4.0                       # deck profile sample spacing
DZ_STEP = 0.5                        # candidate height step
DZ_LO, DZ_HI = -10.0, 60.0           # candidates relative to the straight-deck height lines.json used


# ---------------------------------------------------------------------------------------------------- inputs
class Mosaic:
    """A box of the height and kind passes at full map resolution, read from the 2048 px frames."""

    def __init__(self, work, x0, y0, x1, y1):
        m = json.loads((work / "mosaic.json").read_text())
        self.m, F = m, m["frame"]
        self.x0, self.y0 = x0, y0
        w, h = x1 - x0, y1 - y0
        self.z = np.zeros((h, w), np.uint16)
        self.k = np.zeros((h, w), np.uint8)
        for r in range(max(0, y0 // F), min(m["rows"], (y1 - 1) // F + 1)):
            for c in range(max(0, x0 // F), min(m["cols"], (x1 - 1) // F + 1)):
                fx, fy = c * F, r * F
                ax, ay, bx, by = max(x0, fx), max(y0, fy), min(x1, fx + F), min(y1, fy + F)
                zf = np.asarray(Image.open(work / "frames_height" / f"{c}_{r}.png"))
                kf = np.asarray(Image.open(work / "frames_kind" / f"{c}_{r}.png").convert("L"))
                self.z[ay - y0:by - y0, ax - x0:bx - x0] = zf[ay - fy:by - fy, ax - fx:bx - fx]
                self.k[ay - y0:by - y0, ax - x0:bx - x0] = kf[ay - fy:by - fy, ax - fx:bx - fx]

    def window(self, X, Y, r=1):
        """Heights (m) and kinds in a (2r+1)^2 window around integer map px (X, Y); arrays of shape (n, (2r+1)^2)."""
        h, w = self.z.shape
        dx, dy = np.meshgrid(np.arange(-r, r + 1), np.arange(-r, r + 1))
        xi = np.clip(np.round(X).astype(int)[:, None] - self.x0 + dx.ravel(), 0, w - 1)
        yi = np.clip(np.round(Y).astype(int)[:, None] - self.y0 + dy.ravel(), 0, h - 1)
        return self.z[yi, xi] / 100.0, self.k[yi, xi]


class Terrain:
    def __init__(self, work):
        t = np.load(work / "terrain.npz")
        self.z = t["z"].astype(np.float32)
        self.e0, self.n0, self.s = float(t["e0"]), float(t["n0"]), float(t["step"])

    def bilinear(self, E, N):
        h, w = self.z.shape
        fx = np.clip((E - self.e0) / self.s, 0, w - 1.001)
        fy = np.clip((N - self.n0) / self.s, 0, h - 1.001)
        ix, iy = fx.astype(np.int32), fy.astype(np.int32)
        ax, ay = (fx - ix).astype(np.float32), (fy - iy).astype(np.float32)
        z = self.z
        return ((z[iy, ix] * (1 - ax) + z[iy, ix + 1] * ax) * (1 - ay)
                + (z[iy + 1, ix] * (1 - ax) + z[iy + 1, ix + 1] * ax) * ay)

    def nearest(self, E, N):
        """The same cell lookup project_lines.py used, so heights match lines.json exactly."""
        iy = np.clip(((N - self.n0) / self.s).astype(int), 0, self.z.shape[0] - 1)
        ix = np.clip(((E - self.e0) / self.s).astype(int), 0, self.z.shape[1] - 1)
        return self.z[iy, ix].astype(np.float64)


class Camera:
    def __init__(self, m):
        self.sx0, self.sy1, self.mpp = m["sx0"], m["sy1"], m["mpp"]

    def to_px(self, E, N, z):
        le, ln = E - ORIGIN_E, N - ORIGIN_N
        sx = (le + ln) * R
        sy = (-le + ln) * R * 0.5 + z * CE
        return (sx - self.sx0) / self.mpp, (self.sy1 - sy) / self.mpp

    def ray(self, X, Y, z):
        """World E, N of the point at height z that shows at map px (X, Y)."""
        sx = self.sx0 + X * self.mpp
        sy = self.sy1 - Y * self.mpp
        f = (sy - z * CE) / 0.5
        return (sx - f) * R + ORIGIN_E, (sx + f) * R + ORIGIN_N


# ------------------------------------------------------------------------------------------- deck profiles
def deck_profiles(mos, ter, cam, lines, osm, box):
    """Lowest-cost-path deck heights for every bridge way (roads and rail) inside the box."""
    geo = {e["id"]: e["geometry"] for e in osm if e.get("type") == "way" and "geometry" in e}
    x0, y0, x1, y1 = box
    out = {}
    ends = []
    fallback = []                                                    # carrying bridges whose geometry won't match
    for group in ("roads", "rail"):
        for w in lines[group]:
            if not w.get("b") or w.get("t"):
                continue
            if w.get("k") not in (DRIVE if group == "roads" else RAIL):
                continue                                             # footbridges carry no vehicles
            if w["id"] not in geo:
                fallback.append(w)
                continue
            p = np.array(w["p"], float).reshape(-1, 2)
            if p[:, 0].max() < x0 or p[:, 0].min() > x1 or p[:, 1].max() < y0 or p[:, 1].min() > y1:
                continue
            en = np.array([lonlat_to_en(g["lon"], g["lat"]) for g in geo[w["id"]]], float)
            if len(en) != len(p) or len(en) < 2:
                fallback.append(w)
                continue
            seg = np.hypot(*np.diff(en, axis=0).T)
            d = np.r_[0, np.cumsum(seg)]
            L = d[-1]
            if L < 1:
                continue
            zg = ter.nearest(en[:, 0], en[:, 1])
            zl_v = np.interp(d, [0, L], [zg[0], zg[-1]])          # what lines.json drew (straight deck)
            # lines.json screen polyline and its cumulative length
            scum = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
            n = max(2, int(math.ceil(L / SAMPLE_M)) + 1)
            ds = np.linspace(0, L, n)
            i = np.clip(np.searchsorted(d, ds, side="right") - 1, 0, len(d) - 2)
            t = (ds - d[i]) / np.maximum(seg[i], 1e-9)
            E = en[i, 0] + (en[i + 1, 0] - en[i, 0]) * t
            N = en[i, 1] + (en[i + 1, 1] - en[i, 1]) * t
            zl = zl_v[i] + (zl_v[i + 1] - zl_v[i]) * t
            s = scum[i] + (scum[i + 1] - scum[i]) * t              # screen arc length is linear per segment too
            X, Y = cam.to_px(E, N, zl)
            dzs = np.arange(DZ_LO, DZ_HI + 1e-6, DZ_STEP)
            K = len(dzs)
            # data cost for every (sample, candidate): does the height pass see a deck at that height there?
            cost = np.empty((n, K))
            for k, dz in enumerate(dzs):
                zc = zl + dz
                hz, kk = mos.window(X, Y - dz * PX_PER_M_UP, r=1)
                diff = np.abs(hz - zc[:, None])
                best = diff.min(axis=1)
                c = np.minimum(best, 3.0)
                infront = (hz > zc[:, None] + 0.5).all(axis=1)       # something nearer covers it: no evidence
                c = np.where(infront & (best > 0.5), 1.2, c)
                isdeck = ((kk > 100) & (kk <= 200) & (diff < 1.0)).any(axis=1)
                c = c - 0.3 * isdeck
                c = c + 0.01 * abs(dz)
                cost[:, k] = c
            cost[0] += 0.15 * np.abs(dzs)                            # abutments sit near the ground
            cost[-1] += 0.15 * np.abs(dzs)
            # Viterbi with |step| <= 1 candidate (0.5 m per 4 m: 1 in 8), small cost for every step
            acc = cost[0].copy()
            back = np.zeros((n, K), np.int8)
            for j in range(1, n):
                maxstep = max(1, int(round((ds[j] - ds[j - 1]) / 8.0 / DZ_STEP + 0.49)))
                best = np.full(K, np.inf)
                arg = np.zeros(K, np.int8)
                for st in range(-maxstep, maxstep + 1):
                    sh = np.full(K, np.inf)
                    if st >= 0:
                        sh[st:] = acc[:K - st] if st else acc
                    else:
                        sh[:st] = acc[-st:]
                    sh = sh + 0.05 * abs(st)
                    better = sh < best
                    best[better] = sh[better]
                    arg[better] = st
                acc = best + cost[j]
                back[j] = arg
            k = int(np.argmin(acc))
            ks = np.empty(n, int)
            for j in range(n - 1, -1, -1):
                ks[j] = k
                k -= back[j, k]
            z = zl + dzs[ks]
            out[w["id"]] = dict(s=s, z=z, zl=zl, E=E, N=N, X=X, Y=Y)
            ends.append((w["id"], 0, E[0], N[0]))
            ends.append((w["id"], -1, E[-1], N[-1]))

    # ways that meet share one height there; the correction fades out over 40 m
    keyed = {}
    for wid, j, e, nn in ends:
        keyed.setdefault((round(e), round(nn)), []).append((wid, j))
    for grp in keyed.values():
        if len(grp) < 2:
            continue
        zt = float(np.mean([out[w]["z"][j] for w, j in grp]))
        for w, j in grp:
            o = out[w]
            dist = o["s"] if j == 0 else o["s"][-1] - o["s"]
            dist_m = dist * MPP / 0.7                               # rough map px -> metres along the deck
            fade = np.clip(1 - dist_m / 40.0, 0, 1)
            o["z"] = o["z"] + (zt - o["z"][j]) * fade
    for o in out.values():
        o["h"] = o["z"] - ter.bilinear(o["E"], o["N"])
        o["dz"] = o["z"] - o["zl"]
    # The rest: the deck straight between its ends, exactly where lines.json drew it (no lift, height unknown).
    for w in fallback:
        p = np.array(w["p"], float).reshape(-1, 2)
        s = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
        n = len(p)
        out[w["id"]] = dict(s=s, z=np.zeros(n), zl=np.zeros(n), E=np.zeros(n), N=np.zeros(n), X=p[:, 0], Y=p[:, 1],
                            h=np.zeros(n), dz=np.zeros(n))
    if fallback:
        print(f"deck profiles: {len(fallback)} bridge way(s) straight between their ends", flush=True)
    return out


# ------------------------------------------------------------------------------------------------ the layers
def road_band(lines, box, S, H, W):
    """Pixels (at output resolution) where a road vehicle's body can appear, and the roads themselves."""
    x0, y0 = box[0], box[1]
    m = np.zeros((H, W), np.uint8)
    for group in ("roads", "rail"):
        for w in lines[group]:
            if w.get("t"):
                continue
            k = w.get("k", "")
            if (group == "roads" and k not in DRIVE) or (group == "rail" and k not in RAIL):
                continue
            p = np.array(w["p"], float).reshape(-1, 2)
            pts = np.round((p - [x0, y0]) / S * 4).astype(np.int32)   # 2 bits of sub-pixel precision
            hw = HALF_WIDTH_PX.get(k.replace("_link", ""), 18)
            cv2.polylines(m, [pts], False, 1, thickness=max(1, int(round(2 * hw / S))), shift=2)
    up = int(math.ceil(BAND_UP_M * PX_PER_M_UP / S))
    band = m.copy()
    for i in range(1, up + 1):
        band[:-i] |= m[i:]                                           # a vehicle's body rises above its road
    return band.astype(bool), m.astype(bool)


def deck_band(profiles, box, S, H, W):
    """Per output pixel: the smoothed height of the highest deck whose vehicles can show there (nan elsewhere)."""
    x0, y0 = box[0], box[1]
    zd = np.full((H, W), -1e9, np.float32)
    up = int(math.ceil(BAND_UP_M * PX_PER_M_UP / S))
    segs = []
    for wid, o in profiles.items():
        Xd = o["X"]
        Yd = o["Y"] - o["dz"] * PX_PER_M_UP                           # the vehicle drawn on the modelled deck
        for j in range(len(Xd) - 1):
            segs.append((0.5 * (o["z"][j] + o["z"][j + 1]), Xd[j], Yd[j], Xd[j + 1], Yd[j + 1]))
        # also the straight line lines.json draws, in case the viewer does not apply dz
        for j in range(len(Xd) - 1):
            segs.append((0.5 * (o["z"][j] + o["z"][j + 1]), Xd[j], o["Y"][j], Xd[j + 1], o["Y"][j + 1]))
    segs.sort(key=lambda s: s[0])                                    # highest deck drawn last, so it wins
    th = max(1, int(round(2 * 30 / S)))
    for z, ax, ay, bx, by in segs:
        for u in range(0, up + 1):
            a = (int(round((ax - x0) / S * 4)), int(round((ay - y0) / S * 4 - u * 4)))
            b = (int(round((bx - x0) / S * 4)), int(round((by - y0) / S * 4 - u * 4)))
            cv2.line(zd, a, b, float(z), thickness=th, shift=2)
    return np.where(zd > -1e8, zd, np.nan)


def ground_hit(zs, X, Y, ter, cam):
    """Height of the terrain the line of sight reaches after passing a surface at height zs (m), per pixel."""
    z = zs.astype(np.float64).copy()
    zt = np.full_like(z, np.nan)
    act = np.arange(len(z))
    for _ in range(400):
        if not len(act):
            break
        E, N = cam.ray(X[act], Y[act], z[act])
        g = z[act] - ter.bilinear(E, N)
        done = g <= 0.05
        zt[act[done]] = z[act[done]]
        act, g = act[~done], g[~done]
        z[act] -= np.maximum(0.25, 0.5 * g)
    zt[np.isnan(zt)] = z[np.isnan(zt)]
    return zt


def art_tile(tiles, tx, ty):
    """One tile of the painted summer day art at full resolution (512 x 512 RGB), or None."""
    f = tiles / f"{tx}_{ty}.webp"
    return np.asarray(Image.open(f).convert("RGB")) if f.exists() else None


def crowns(tiles, shape):
    """Tree crowns in the painted art, per CANOPY_CELL cell: foliage colours (greens through yellow-greens, light and
    back-lit crowns included) that are busy at full resolution (lawns are smooth), with the dark shadows between
    leaves; specks out, gaps filled, crowns under about 3 m across dropped."""
    H, W = shape
    C = CANOPY_CELL
    out = np.zeros((H, W), bool)
    T = 512
    for f in tiles.glob("*.webp"):
        tx, ty = map(int, f.stem.split("_"))
        rgb = np.asarray(Image.open(f).convert("RGB"))
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV).astype(np.int16)
        hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
        v = val.astype(np.float32)
        mean = cv2.blur(v, (5, 5))
        busy = np.sqrt(np.maximum(cv2.blur(v * v, (5, 5)) - mean * mean, 0)) >= 14
        leaf = (hue >= 20) & (hue <= 95) & (sat >= 45) & (val <= 215) & (g >= r * 0.92) & (g >= b) & busy
        dark = (val < 70) & (cv2.dilate(leaf.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
        m = (leaf | dark).astype(np.float32)
        h, w = m.shape[0] // C * C, m.shape[1] // C * C
        m = m[:h, :w].reshape(h // C, C, w // C, C).mean(axis=(1, 3)) >= 0.5
        ys, xs = ty * T // C, tx * T // C
        hh, ww = min(m.shape[0], H - ys), min(m.shape[1], W - xs)
        if hh > 0 and ww > 0:
            out[ys:ys + hh, xs:xs + ww] = m[:hh, :ww]
    k1, k2 = max(1, round(4 / C)), max(1, round(8 / C))      # about 1 m and 2 m
    m = cv2.morphologyEx(out.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k1 + 1,) * 2))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k2 + 1,) * 2))
    _, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    keep = st[:, cv2.CC_STAT_AREA] >= int((12 / C) ** 2)
    keep[0] = False
    return keep[lab]


def canopy_layer(tiles, data, ground_px, lines, box, S, H, W):
    """The B layer: soft coverage (0..255) of tree crowns in front of the lanes, on the output grid."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_drivable
    from build_drivable import VALUES, lane_band, load_grid
    from flowfield import Field as FlowField
    # the crowns are found in the painting and the drivable map is in its positions: lay the lanes there too
    build_drivable.MOVE = FlowField.load("road")
    grid, idx = load_grid(data)
    assert idx["cell"] == CANOPY_CELL, "the canopy uses the drivable map's grid"
    C = CANOPY_CELL
    crown = crowns(tiles, grid.shape)
    # on visible ground only (the 3D model has no trees: a crown over a wall or roof is painted on the building)
    crown &= ground_px
    lanes = (grid == VALUES["road"]) | (grid == VALUES["deck"]) | lane_band(lines, grid.shape)
    hit = crown & lanes
    up = int(math.ceil(BAND_UP_M * PX_PER_M_UP / C))
    for _ in range(up):
        hit[:-1] |= hit[1:] & crown[:-1]                             # up the screen through the crown above
    soft = cv2.GaussianBlur(hit.astype(np.float32), (0, 0), CANOPY_FEATHER_M / MPP / C / 2)
    soft = np.maximum(soft * 2 - 0.5, 0).clip(0, 1) * hit.astype(np.float32) + soft * (1 - hit) * 0.6
    # onto the output grid (S map px per output px)
    x0, y0 = box[0] // C, box[1] // C
    k = S // C
    blk = soft[y0:y0 + H * k, x0:x0 + W * k]
    hh, ww = blk.shape[0] // k, blk.shape[1] // k
    out = np.zeros((H, W), np.float32)
    out[:hh, :ww] = blk[:hh * k, :ww * k].reshape(hh, k, ww, k).mean(axis=(1, 3))
    print(f"canopy: crowns {crown.mean():.1%} of the map, over the lanes {hit.mean():.2%}", flush=True)
    return np.round(out * 255).astype(np.uint8)


def kinds_ground(work, shape, C):
    """Visible ground (kinds pass) per C-map-px cell over the whole map."""
    H, W = shape
    mos = json.loads((work / "mosaic.json").read_text())
    F = mos["frame"]
    n = F // C
    out = np.zeros((H, W), bool)
    for r in range(mos["rows"]):
        for c in range(mos["cols"]):
            k = np.asarray(Image.open(work / "frames_kind" / f"{c}_{r}.png").convert("L"))
            g = (k > 200).reshape(n, C, n, C).mean(axis=(1, 3)) >= 0.5
            ys, xs = r * n, c * n
            hh, ww = min(n, H - ys), min(n, W - xs)
            if hh > 0 and ww > 0:
                out[ys:ys + hh, xs:xs + ww] = g[:hh, :ww]
    return out


OCC_TILE = 512


def write_tiles(rgb, out, meta):
    """The occluder image as tiles in out/occluders/ (all-zero tiles left out), and occluders.json."""
    d = out / "occluders"
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.png"):
        f.unlink()
    H, W = rgb.shape[:2]
    names, size = [], 0
    for ty in range((H + OCC_TILE - 1) // OCC_TILE):
        for tx in range((W + OCC_TILE - 1) // OCC_TILE):
            t = rgb[ty * OCC_TILE:(ty + 1) * OCC_TILE, tx * OCC_TILE:(tx + 1) * OCC_TILE]
            if not t.any():
                continue
            Image.fromarray(np.ascontiguousarray(t)).save(d / f"{tx}_{ty}.png", optimize=True, compress_level=9)
            size += (d / f"{tx}_{ty}.png").stat().st_size
            names.append(f"{tx}_{ty}")
    (out / "occluders.json").write_text(json.dumps({**meta, "w": W, "h": H, "tile": OCC_TILE, "tiles": names}))
    old = out / "occluders.png"
    if old.exists():
        old.unlink()
    print(f"occluders: {len(names)} tiles of {OCC_TILE} px, {size // 1024} KB", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", type=Path, default=WORK, help="data/work with mosaic.json, frames_height, ...")
    ap.add_argument("--data", type=Path, default=ROOT / "web/public", help="web/public with data/lines.json and "
                    "tiles/meta.json")
    ap.add_argument("--raw", type=Path, default=RAW, help="data/raw with osm/lines.json")
    ap.add_argument("--out", type=Path, default=ROOT / "web/public/data")
    ap.add_argument("--scale", type=int, default=4, help="map px per output px (even)")
    ap.add_argument("--bbox", type=int, nargs=4, help="map px box x0 y0 x1 y1 (default: the painted areas)")
    ap.add_argument("--tiles", type=Path, default=ROOT / "web/public/tiles/map_files/15",
                    help="the painted summer day art, deepest tile level (for the canopy)")
    ap.add_argument("--debug", type=Path, help="write debug overlays of the painted art, NAME.jpg, NAME_1.jpg, ...")
    ap.add_argument("--debug-box", type=int, nargs="+", default=[5600, 5000, 8400, 7100],
                    help="map px boxes for --debug, four numbers each")
    ap.add_argument("--split", type=Path, help="only cut this whole occluders.png into tiles (see above)")
    a = ap.parse_args()
    S = a.scale
    if a.split:
        m = json.loads((a.out / "occluders.json").read_text())
        write_tiles(np.asarray(Image.open(a.split).convert("RGB")), a.out,
                    {k: m[k] for k in ("x0", "y0", "scale", "unit")})
        return

    lines = json.loads((a.data / "data" / "lines.json").read_text())
    if a.bbox:
        box = list(a.bbox)
    else:
        meta = json.loads((a.data / "tiles" / "meta.json").read_text())
        ps = meta["painted"]
        box = [min(p["x0"] for p in ps), min(p["y0"] for p in ps),
               max(p["x0"] + p["w"] for p in ps), max(p["y0"] + p["h"] for p in ps)]
    mj = json.loads((a.work / "mosaic.json").read_text())   # never past the map's own edges
    box = [max(0, box[0]) // S * S, max(0, box[1]) // S * S, min(mj["cols"] * mj["frame"], box[2]),
           min(mj["rows"] * mj["frame"], box[3])]
    box[2] = box[0] + (box[2] - box[0]) // S * S
    box[3] = box[1] + (box[3] - box[1]) // S * S
    W, H = (box[2] - box[0]) // S, (box[3] - box[1]) // S
    print("box", box, "output", W, "x", H, flush=True)

    m = json.loads((a.work / "mosaic.json").read_text())
    cam = Camera(m)
    ter = Terrain(a.work)
    pad = 400                                     # deck candidates reach above the box
    mos = Mosaic(a.work, max(0, box[0] - pad), max(0, box[1] - pad),
                 min(m["cols"] * m["frame"], box[2] + pad), min(m["rows"] * m["frame"], box[3] + pad))
    print("mosaic loaded", flush=True)

    # 1. deck profiles
    osm = json.loads((a.raw / "osm" / "lines.json").read_text())["elements"]
    prof = deck_profiles(mos, ter, cam, lines, osm, box)
    print("deck profiles", len(prof), flush=True)
    rh = {}
    for wid, o in prof.items():
        rh[str(wid)] = {"x": [round(float(v)) for v in o["X"]], "y": [round(float(v)) for v in o["Y"]],
                        "s": [round(float(v), 1) for v in o["s"]], "z": [round(float(v), 1) for v in o["z"]],
                        "dz": [round(float(v), 1) for v in o["dz"]], "h": [round(float(v), 1) for v in o["h"]]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "road_heights.json").write_text(json.dumps(rh, separators=(",", ":")))

    # 2. surface height per output px: of each S x S block, the second highest sample (a block counts as the
    #    nearer surface once half of it is)
    bx0, by0 = box[0] - mos.x0, box[1] - mos.y0
    zb = mos.z[by0:by0 + H * S, bx0:bx0 + W * S].reshape(H, S, W, S).transpose(0, 2, 1, 3).reshape(H, W, S * S)
    kb = mos.k[by0:by0 + H * S, bx0:bx0 + W * S].reshape(H, S, W, S).transpose(0, 2, 1, 3).reshape(H, W, S * S)
    zs = np.sort(zb, axis=2)[..., -max(1, S * S // 2)].astype(np.float32) / 100.0
    ground = (kb > 200).mean(axis=2) > 0.5
    empty = (zb == 0).any(axis=2)
    del zb, kb

    band, road = road_band(lines, box, S, H, W)
    print("road band", f"{band.mean():.1%}", flush=True)

    # 3. ground layer: surface above the terrain behind it
    todo = band & ~ground & ~empty
    yy, xx = np.nonzero(todo)
    X = box[0] + (xx + 0.5) * S
    Y = box[1] + (yy + 0.5) * S
    zt = ground_hit(zs[yy, xx], X, Y, ter, cam)
    occ = np.zeros((H, W), np.float32)
    occ[yy, xx] = np.maximum(zs[yy, xx] - zt, 0)
    Rch = np.clip(np.round(occ * 10), 0, 255).astype(np.uint8)
    Rch[Rch < 3] = 0                                                  # under 0.3 m is the road itself
    print("ground layer done", flush=True)

    # 4. canopy from the painted art, soft, in its own channel. A crown counts only where it reaches down over the
    # lanes (a tree in front of the road, or one overhanging it): crowns that show above the road on screen but stop
    # short of it stand behind the road and must not hide vehicles passing in front of them.
    del mos
    gpx = kinds_ground(a.work, (m["rows"] * m["frame"] // CANOPY_CELL, m["cols"] * m["frame"] // CANOPY_CELL), CANOPY_CELL)
    Bch = canopy_layer(a.tiles, a.data / "data", gpx, lines, box, S, H, W)
    del gpx
    canopy = Bch > 127

    # 5. deck layer: surface above the smoothed deck height, near bridges
    zd = deck_band(prof, box, S, H, W)
    dz = zs - zd
    # Only built things (towers, walls, roofs, other decks) count. Visible ground in front of a deck vehicle only
    # happens where the modelled deck meets its street with a step, and must not cut vehicles off there.
    Gch = np.where(np.isfinite(dz) & ~empty & ~ground, np.clip(np.round(dz * 10), 0, 255), 0).astype(np.uint8)
    Gch[Gch < 3] = 0

    rgb = np.dstack((Rch, Gch, Bch))
    write_tiles(rgb, a.out, {"x0": box[0], "y0": box[1], "scale": S, "unit": 0.1})
    print("occluders", W, H, ";",
          "road_heights.json", (a.out / "road_heights.json").stat().st_size // 1024, "KB;",
          f"canopy {(Bch > 0).mean():.1%}, ground>1.6 m {(Rch > 16).mean():.1%}, deck>0 {(Gch > 0).mean():.2%}",
          flush=True)

    if a.debug:
        for i in range(0, len(a.debug_box) - 3, 4):
            dest = a.debug if i == 0 else a.debug.with_name(f"{a.debug.stem}_{i // 4}{a.debug.suffix}")
            debug_image(dest, a.debug_box[i:i + 4], box, S, Rch, Gch, canopy, a.tiles, prof)


def debug_image(dest, dbox, box, S, Rch, Gch, canopy, tiles, prof):
    """Painted art with the layers tinted: red = in front of even a 4.5 m train, orange = in front of a 1.6 m
    car only, magenta = canopy (more than half hidden), blue = deck layer over 2 m, cyan lines = smoothed deck
    lines."""
    img = Image.new("RGB", (dbox[2] - dbox[0], dbox[3] - dbox[1]))
    for ty in range(dbox[1] // 512, (dbox[3] - 1) // 512 + 1):
        for tx in range(dbox[0] // 512, (dbox[2] - 1) // 512 + 1):
            t = art_tile(tiles, tx, ty)
            if t is not None:
                img.paste(Image.fromarray(t), (tx * 512 - dbox[0], ty * 512 - dbox[1]))
    w, h = (dbox[2] - dbox[0]) // S, (dbox[3] - dbox[1]) // S
    up = max(1, 1400 // w)                               # small boxes are shown enlarged
    c = img.resize((w * up, h * up), Image.LANCZOS)
    a = np.asarray(c).astype(np.float32)
    ox, oy = (dbox[0] - box[0]) // S, (dbox[1] - box[1]) // S
    sl = (slice(oy, oy + h), slice(ox, ox + w))

    def big(m):
        return np.repeat(np.repeat(m[sl], up, axis=0), up, axis=1)
    r, g, cn = big(Rch), big(Gch), big(canopy)

    def tint(mask, col, al):
        a[mask] = a[mask] * (1 - al) + np.array(col, np.float32) * al
    tint((r > 45) & ~cn, (255, 0, 0), 0.5)           # in front of even a 4.5 m train
    tint((r > 16) & (r <= 45) & ~cn, (255, 150, 0), 0.5)   # in front of cars only
    tint(cn, (255, 0, 255), 0.4)
    tint(g > 20, (0, 80, 255), 0.6)
    out = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for o in prof.values():
        pts = [((x - dbox[0]) / S * up, (y - o["dz"][i] * PX_PER_M_UP - dbox[1]) / S * up)
               for i, (x, y) in enumerate(zip(o["X"], o["Y"]))]
        d.line(pts, fill=(0, 255, 255), width=2)
    out.save(dest, quality=88)
    print("debug", dest, out.size)


if __name__ == "__main__":
    main()
