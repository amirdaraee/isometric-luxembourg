"""Water mask and river flow for the viewer's water effect, found in the painted art itself.

A pixel is water when it is:
  1. near real water: within ~12 m of the OpenStreetMap water polygons (and river lines drawn at a plausible width),
     because the painted river is often several metres off the OSM outline;
  2. painted water-coloured: teal or blue, not green, yellow, grey or slate (OpenCV LAB: a < 121 and b < 125, see
     A_MAX, B_MAX), and not the dark empty background outside the painted area. Trees over the banks are green, so
     they are left out here;
  3. at the water level in the height pass (data/work/frames_height): no more than 1.5 m above the lowest water
     pixel within ~10 m, which drops bridge decks and boats. The tolerance is loose because the painting and the
     render do not line up to the pixel.
The result is cleaned (close, open, pieces under ~12 m2 or not touching the OSM water dropped, small holes filled)
and eroded by ~0.5 m so that effects never touch the bank.

Every painted area in data/work/tiles/painted.json is used, in order (a later area wins where areas overlap, as in
build_tiles.py). Re-run after painting more of the city.

Flow: every water pixel also gets the river's surface current, so the viewer can draw ripples that run along the
river and drift downstream:
  - direction: that of the nearest OSM waterway centreline (lines.json "waterways"). OSM draws waterways in the
    direction of flow (checked: the Alzette runs north through Grund to Clausen and Pfaffenthal, the Petrusse east
    into it). The field is blurred over ~6 m so that it turns smoothly between segments and at the confluence;
  - strength, the vector's length (0..1): 1 mid-stream, falling to 0.3 at the banks (by the bank distance over the
    local half width, which is the largest bank distance within ~12 m), and fading out more than ~25 m from any
    centreline (ponds, basins);
  - bank distance: the mask's distance transform, in metres.

Output (half map resolution, 1 mask px = 2 map px = 0.5 m across):
  web/public/data/water_mask.png   8-bit RGB atlas of the mask's non-empty 128 x 128 blocks, each stored as
                                   130 x 130 with a 1 px apron, `cols` blocks per row:
                                     R     distance to the bank in steps of 1/16 m (0 = dry, capped at 255, ~16 m).
                                           The soft water mask is min(1, R / 16): a ~1 m soft inner edge;
                                     G, B  flow vector x, y (map px axes: x right, y down) as 128 + 127 * v, v in
                                           -1..1; its length is the relative current speed described above
  web/public/data/water_mask.json  {"x0", "y0"}: map px of the mask's top-left corner; "scale": map px per mask px;
                                   "w", "h": mask size; "chunk": block size; "cols"; "chunks": flat list i0, j0, i1, j1,
                                   ...: block k (atlas cell k % cols, k // cols) is mask block (i, j), which starts at
                                   map px (x0 + i * chunk * scale, y0 + j * chunk * scale); "bank_per_unit": metres
                                   per R step; "channels": the channel layout in words
Usage: build_water_mask.py [--work DIR] [--out DIR] [--lines lines.json] [--debug out.jpg]
  (defaults: data/work, web/public/data, <out>/lines.json; --debug writes the mask over the art, half resolution,
  with flow arrows whose length is the current speed)
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from common import ROOT, WORK

Image.MAX_IMAGE_PIXELS = None
S = 2                 # map px per mask px
MPP = 0.25            # metres per map px
PX_M = 1 / (MPP * S)  # mask px per metre
BACKGROUND = np.array([16, 24, 40])  # empty map edge (RGB)
LEVEL_TOL = 150       # cm above the local water level still counted as water
NEAR_M = 12           # how far (m) the painted water may stray from the OSM outline
A_MAX, B_MAX = 121, 125  # water colour: OpenCV LAB a and b (128 = neutral) below these
CHUNK = 128           # atlas block size in mask px
BANK_UNIT = 1 / 16    # metres per step of the bank distance channel
FLOW_BLUR_M = 6       # how far (m) the flow direction is smoothed
HALF_WIDTH_M = 12     # search radius (m) for the river's local half width
FLOW_FAR_M = 25       # beyond this distance (m) from a centreline the current fades out


def disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def osm_water(lines, x0, y0, w, h):
    """OSM water in mask px for the map rectangle x0, y0, w, h (map px)."""
    m = Image.new("L", (w // S, h // S), 0)
    d = ImageDraw.Draw(m)
    tr = lambda p: [((p[i] - x0) / S, (p[i + 1] - y0) / S) for i in range(0, len(p), 2)]
    for wtr in lines["water"]:
        q = tr(wtr["p"])
        if len(q) >= 3:
            d.polygon(q, fill=255)
    for wtr in lines["waterways"]:
        if wtr.get("t"):
            continue  # culverts and tunnels
        width_m = {"river": 16, "canal": 8}.get(wtr.get("k"), 5)
        d.line(tr(wtr["p"]), fill=255, width=max(2, int(width_m * PX_M)))
    return np.asarray(m) > 0


def heights(mosaic, work, x0, y0, w, h):
    """Height pass (cm above sea level, 0 = empty) for the map rectangle, at mask resolution, as float32."""
    F = mosaic["frame"]
    out = np.zeros((h, w), np.uint16)
    for r in range(max(0, y0 // F), min(mosaic["rows"], (y0 + h - 1) // F + 1)):
        for c in range(max(0, x0 // F), min(mosaic["cols"], (x0 + w - 1) // F + 1)):
            f = work / "frames_height" / f"{c}_{r}.png"
            if not f.exists():
                continue
            a = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
            fx0, fy0 = c * F, r * F
            ix0, iy0 = max(x0, fx0), max(y0, fy0)
            ix1, iy1 = min(x0 + w, fx0 + F), min(y0 + h, fy0 + F)
            out[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0] = a[iy0 - fy0:iy1 - fy0, ix0 - fx0:ix1 - fx0]
    # Nearest sampling: averaging would blend a bridge deck with the water under it.
    return out[::S, ::S].astype(np.float32)


def flat(hgt, cand, tol=LEVEL_TOL):
    """At the water level: within `tol` cm of the lowest candidate water pixel in the ~10 m around it. This drops
    bridge decks, boats and roofs, which are metres above the river. (The water surface is the lowest thing around.
    The tolerance is looser than the 0.4 m a pure height test could use, and there is no slope test, because the
    painting and the render it was painted from do not line up to the pixel: painted water often lies over the
    render's bank, and a slope test cut thin rivers like the Petrusse into pieces.)"""
    ok = cand & (hgt > 0)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(10 * PX_M) | 1,) * 2)
    level = cv2.erode(np.where(ok, hgt, 1e6).astype(np.float32), k)
    # The lowest pixel could be a stray: take the median of the minima over 5 x 5 instead.
    level = cv2.medianBlur(np.minimum(level, 65535).astype(np.uint16), 5).astype(np.float32)
    return ok & (hgt < level + tol)


def area_mask(entry, tiles_dir, lines, mosaic, work):
    x0, y0, w, h = entry["x0"], entry["y0"], entry["w"], entry["h"]
    im = cv2.imread(str(tiles_dir / entry["file"]), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"cannot read {tiles_dir / entry['file']}")
    im = cv2.resize(im, (w // S, h // S), interpolation=cv2.INTER_AREA)
    rgb = im[..., ::-1].astype(int)

    osm = osm_water(lines, x0, y0, w, h).astype(np.uint8)
    near = cv2.dilate(osm, disk(NEAR_M * PX_M)) > 0

    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(int)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    # The painted rivers sit at a ~109-120, b ~109-121; slate roofs and grey roads, the nearest look-alikes, at
    # a >= 122 (measured on the old town).
    # Dark water in the shade of the gorges is valid too; the empty background is excluded below.
    colour = (a < A_MAX) & (b < B_MAX) & (L > 12) & (L < 175)
    # The empty background outside the painting: dark navy, like water in deep shade, so only large areas of it
    # count (an opening with a ~16 m disk keeps the background and drops shaded rivers), plus a 3 m margin.
    bg = (np.abs(rgb - BACKGROUND).sum(axis=2) < 36).astype(np.uint8)
    bg = cv2.morphologyEx(bg, cv2.MORPH_OPEN, disk(8 * PX_M))
    bg = cv2.dilate(bg, disk(3 * PX_M)) > 0
    cand = near & colour & ~bg

    hgt = heights(mosaic, work, x0, y0, w, h)
    if (hgt > 0).mean() > 0.05:
        cand = flat(hgt, cand)
    m = cand.astype(np.uint8)

    # Clean: close tiny gaps (ripples painted lighter), drop thin bits and specks, fill small holes.
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, disk(1.5))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, disk(1))
    # Keep pieces of at least ~12 m2 that touch the OSM water itself (not only its grown margin), so a teal roof or
    # pool near the river is left out.
    n, lab_, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    touch = np.zeros(n, bool)
    touch[np.unique(lab_[(cv2.dilate(osm, disk(1 * PX_M)) > 0) & (m > 0)])] = True
    keep = touch & (st[:, cv2.CC_STAT_AREA] >= 12 * PX_M ** 2)
    keep[0] = False
    m = keep[lab_].astype(np.uint8)
    inv = 1 - m
    n, lab_, st, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    hole = np.zeros(n, bool)
    hole[1:] = st[1:, cv2.CC_STAT_AREA] < 3 * PX_M ** 2  # holes under ~3 m2 (painted glints) are water
    m[hole[lab_]] = 1
    m = m & (~bg).astype(np.uint8)
    # Keep clear of the bank: ~0.5 m hard margin (the soft edge over the next ~1 m comes from the bank distance).
    return cv2.erode(m, disk(1))


def flow_field(water, lines, x0, y0):
    """Bank distance (m) and flow vector (vx, vy in map px axes, length = relative speed) for every pixel of the
    0/1 mask canvas `water`, whose top-left corner is at map px x0, y0."""
    H, W = water.shape
    bank = cv2.distanceTransform(water, cv2.DIST_L2, 5) / PX_M

    # Rasterise the centrelines with their segment directions; every pixel then takes the nearest centreline pixel's.
    seed = np.full((H, W), 255, np.uint8)
    dx = np.zeros((H, W), np.float32)
    dy = np.zeros((H, W), np.float32)
    for wtr in lines["waterways"]:
        p = wtr["p"]
        q = [((p[i] - x0) / S, (p[i + 1] - y0) / S) for i in range(0, len(p), 2)]
        for (ax, ay), (bx, by) in zip(q, q[1:]):
            n = np.hypot(bx - ax, by - ay)
            if n < 1e-6 or max(ax, bx) < -1 or min(ax, bx) > W or max(ay, by) < -1 or min(ay, by) > H:
                continue
            a, b = (int(round(ax)), int(round(ay))), (int(round(bx)), int(round(by)))
            cv2.line(seed, a, b, 0, 1)
            cv2.line(dx, a, b, float((bx - ax) / n), 1)
            cv2.line(dy, a, b, float((by - ay) / n), 1)
    if seed.all():
        raise SystemExit("no waterway centreline crosses the water mask")
    dcl, lab = cv2.distanceTransformWithLabels(seed, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    zero = seed == 0
    lut_x = np.zeros(lab.max() + 1, np.float32)
    lut_y = np.zeros(lab.max() + 1, np.float32)
    lut_x[lab[zero]], lut_y[lab[zero]] = dx[zero], dy[zero]
    vx, vy = lut_x[lab], lut_y[lab]
    del lab, lut_x, lut_y, dx, dy
    # Blend between neighbouring segments (and rivers, at the confluence), then back to unit length.
    vx = cv2.GaussianBlur(vx, (0, 0), FLOW_BLUR_M * PX_M)
    vy = cv2.GaussianBlur(vy, (0, 0), FLOW_BLUR_M * PX_M)
    n = np.maximum(np.hypot(vx, vy), 1e-6)
    vx, vy = vx / n, vy / n

    # Speed: a rounded profile across the river (bank distance over the local half width), none far from any
    # centreline. A small floor keeps the direction readable after rounding to 8 bits.
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (int(2 * HALF_WIDTH_M * PX_M) | 1,) * 2)
    half = cv2.GaussianBlur(cv2.dilate(bank.astype(np.float32), k), (0, 0), 2 * PX_M)
    across = np.clip(bank / np.maximum(half, 1.0), 0, 1)
    profile = 0.3 + 0.7 * (1 - (1 - across) ** 2)
    far = np.clip(1.5 - dcl / (FLOW_FAR_M * PX_M), 0, 1)
    # Smoothed so the field has no kinks (also halves its PNG size).
    speed = np.maximum(cv2.GaussianBlur((profile * far).astype(np.float32), (0, 0), 2 * PX_M), 0.08)
    return bank, vx * speed, vy * speed


def write_atlas(img, x0, y0, out):
    """Save the H x W x 3 image (R = bank distance, 0 off the water) as an atlas of its non-empty CHUNK x CHUNK
    blocks, so the viewer loads and keeps on the GPU only the rivers, not the dry land between them. Each block is
    stored with a 1 px apron copied from its neighbours, so smooth sampling never bleeds in from the next block in
    the atlas."""
    H, W = img.shape[:2]
    mask = img[..., 0]
    nx, ny = -(-W // CHUNK), -(-H // CHUNK)
    pad = np.zeros((ny * CHUNK + 2, nx * CHUNK + 2, 3), np.uint8)
    pad[..., 1:] = 128
    pad[1:H + 1, 1:W + 1] = img
    chunks = [(i, j) for j in range(ny) for i in range(nx)
              if mask[j * CHUNK:(j + 1) * CHUNK, i * CHUNK:(i + 1) * CHUNK].any()]
    cols = 16 if len(chunks) <= 16 * 32 else 32
    cell = CHUNK + 2
    rows = -(-len(chunks) // cols)
    if rows * cell > 8192:
        raise SystemExit(f"{len(chunks)} water blocks do not fit one 4096 x 8192 atlas: raise CHUNK or split it")
    atlas = np.zeros((rows * cell, cols * cell, 3), np.uint8)
    atlas[..., 1:] = 128
    for k, (i, j) in enumerate(chunks):
        c, r = k % cols, k // cols
        atlas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = pad[j * CHUNK:j * CHUNK + cell, i * CHUNK:i * CHUNK + cell]
    out.mkdir(parents=True, exist_ok=True)
    png = out / "water_mask.png"
    Image.fromarray(atlas).save(png, optimize=True)
    info = {"x0": x0, "y0": y0, "scale": S, "w": W, "h": H, "chunk": CHUNK, "cols": cols,
            "channels": "R: bank distance in bank_per_unit m (0 dry; mask = min(1, R / 16)); "
                        "G, B: flow vector x, y as 128 + 127 * v, length = relative speed",
            "bank_per_unit": BANK_UNIT, "chunks": [c for ij in chunks for c in ij]}
    (out / "water_mask.json").write_text(json.dumps(info, separators=(",", ":")) + "\n")
    print(f"{png}: {len(chunks)} blocks of {CHUNK} px, atlas {atlas.shape[1]} x {atlas.shape[0]}, "
          f"{png.stat().st_size / 1024:.0f} KB; mask {W} x {H} mask px at map {x0}, {y0}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=WORK, help="data/work folder (painted.json, frames_height)")
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "public" / "data", help="where to write the mask")
    ap.add_argument("--lines", type=Path, default=None, help="lines.json (default: <out>/lines.json)")
    ap.add_argument("--debug", type=Path, help="also write a JPEG of the mask over the art (half resolution)")
    args = ap.parse_args()

    tiles_dir = args.work / "tiles"
    painted = json.loads((tiles_dir / "painted.json").read_text())
    mosaic = json.loads((args.work / "mosaic.json").read_text())
    lines = json.loads((args.lines or args.out / "lines.json").read_text())
    MW, MH = mosaic["cols"] * mosaic["frame"], mosaic["rows"] * mosaic["frame"]
    if not painted:
        raise SystemExit("painted.json is empty: nothing to do")

    # Everything is laid out on one half-resolution canvas over the painted areas' union (clipped to the map).
    gx0 = max(0, min(p["x0"] for p in painted)) // S * S
    gy0 = max(0, min(p["y0"] for p in painted)) // S * S
    gx1 = min(MW, max(p["x0"] + p["w"] for p in painted))
    gy1 = min(MH, max(p["y0"] + p["h"] for p in painted))
    G = np.zeros(((gy1 - gy0 + S - 1) // S, (gx1 - gx0 + S - 1) // S), np.uint8)
    art = np.zeros(G.shape + (3,), np.uint8) if args.debug else None

    for p in painted:
        # Snap to the mask grid so areas line up pixel for pixel.
        e = dict(p, x0=p["x0"] // S * S, y0=p["y0"] // S * S, w=p["w"] // S * S, h=p["h"] // S * S)
        m = area_mask(e, tiles_dir, lines, mosaic, args.work)
        # Paste the part that lies on the canvas; a later area replaces an earlier one where they overlap.
        ax, ay = (e["x0"] - gx0) // S, (e["y0"] - gy0) // S
        sx, sy = max(0, -ax), max(0, -ay)
        ex, ey = min(m.shape[1], G.shape[1] - ax), min(m.shape[0], G.shape[0] - ay)
        G[ay + sy:ay + ey, ax + sx:ax + ex] = m[sy:ey, sx:ex]
        if art is not None:
            im = cv2.imread(str(tiles_dir / p["file"]), cv2.IMREAD_COLOR)
            im = cv2.resize(im, (e["w"] // S, e["h"] // S), interpolation=cv2.INTER_AREA)
            art[ay + sy:ay + ey, ax + sx:ax + ex] = im[sy:ey, sx:ex]
        print(f"{p['file']}: {(m > 0).sum() / PX_M ** 2 / 1e4:.1f} ha of water")

    # Crop to the water, with a small margin.
    ys, xs = np.nonzero(G)
    if not len(xs):
        raise SystemExit("no water found")
    cx0, cy0 = max(0, xs.min() - 4), max(0, ys.min() - 4)
    cx1, cy1 = min(G.shape[1], xs.max() + 5), min(G.shape[0], ys.max() + 5)
    crop = np.ascontiguousarray(G[cy0:cy1, cx0:cx1])
    X0, Y0 = int(gx0 + cx0 * S), int(gy0 + cy0 * S)
    bank, vx, vy = flow_field(crop, lines, X0, Y0)
    enc = np.zeros(crop.shape + (3,), np.uint8)
    enc[..., 0] = np.where(crop > 0, np.clip(np.round(bank / BANK_UNIT), 1, 255), 0)
    enc[..., 1] = np.clip(np.round(128 + 127 * vx), 1, 255)
    enc[..., 2] = np.clip(np.round(128 + 127 * vy), 1, 255)
    # Off the water (beyond the 1 px that smooth sampling reaches) the flow is not needed: a flat 128 packs better.
    dry = cv2.dilate(crop, np.ones((3, 3), np.uint8)) == 0
    enc[dry, 1:] = 128
    write_atlas(enc, X0, Y0, args.out)

    if art is not None:
        a = art[cy0:cy1, cx0:cx1].astype(np.float32)
        k = np.minimum(1, enc[..., 0].astype(np.float32) / 16)[..., None]
        tint = np.array([60, 40, 255], np.float32)  # BGR: red-magenta over water
        out = a * (1 - 0.55 * k) + tint * 0.55 * k
        edge = cv2.morphologyEx((crop > 0).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        out[edge] = (255, 255, 0)
        # Flow arrows every ~10 m on the water; their length is the current speed.
        for y in range(10, crop.shape[0], 20):
            for x in range(10, crop.shape[1], 20):
                if crop[y, x]:
                    tip = (int(round(x + vx[y, x] * 12)), int(round(y + vy[y, x] * 12)))
                    cv2.arrowedLine(out, (x, y), tip, (255, 255, 255), 1, tipLength=0.4)
        cv2.imwrite(str(args.debug), out.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print("debug", args.debug)


if __name__ == "__main__":
    main()
