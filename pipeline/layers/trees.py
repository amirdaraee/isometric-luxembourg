"""Layered map, step 4: a trial tree library, painted by the trained model and placed from the LiDAR tree survey.

  trees.py sheet [b00]           -> <block>/trees/sheet_src.png, sheet_layout.png, sheet_keep.png, sheet.json:
                                    simple 3D-looking "renders" of single trees and canopy masses in the map's
                                    projection and light, on the flat backdrop, for the painter (painted at map scale
                                    together with the buildings, so the ink weight matches)
  trees.py cut [b00] <painted_sheet.png> <season>
                                 -> <block>/trees/lib_<season>/<name>.png (RGBA sprites, trunk base at a known
                                    point) and lib_<season>.json
  trees.py place [b00] [--k K]   -> <block>/trees/placed.json: one entry per tree in the block (sprite, map position
                                    of the trunk base, scale, colour jitter), from the survey's height, crown width and
                                    type; dense woods get canopy-mass pieces
  trees.py render [b00] <season> [--k K] -> <block>/trees/L8_trees_<season>.png (RGBA) and the trees' depth rows
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from layers_common import POC_IMG, block, en_to_map, ground_z, inputs_dir, out_dir, preview, unshift

BACKDROP = (255, 0, 255)
TONE = 0.84  # placed trees a little darker than the painted sheet, like the painting's woods
PXM = 5120 / 6000 * 4          # painted px per metre (0.293 m per px)
CE = math.cos(math.radians(30))  # vertical screen scale of heights
SE = 0.5                          # vertical screen scale of ground depth

# species: crown shape and summer colours (light, mid, dark) for the render the painter starts from
SPECIES = {
    "lime": {"shape": "round", "col": ((150, 176, 70), (96, 132, 48), (46, 72, 30)), "ratio": 1.05},
    "plane": {"shape": "open", "col": ((168, 184, 92), (110, 140, 60), (58, 82, 38)), "ratio": 0.95},
    "chestnut": {"shape": "round", "col": ((120, 150, 56), (70, 104, 40), (34, 56, 26)), "ratio": 0.9},
    "beech_red": {"shape": "round", "col": ((150, 86, 80), (104, 52, 56), (56, 30, 36)), "ratio": 1.0},
    "conifer": {"shape": "cone", "col": ((84, 120, 80), (46, 80, 56), (22, 44, 34)), "ratio": 2.2},
}
SIZES = {"s": (7.0, 4.0), "l": (16.0, 10.0)}  # (height m, crown diameter m)
VARIANTS = 2
MASSES = 4


def blob_tree(rng, species, height, crown, scale=PXM):
    """RGBA render of one tree: trunk and a leafy crown of clumps, lit from the upper left. Returns the image and
    the trunk base (x, y) in it."""
    sp = SPECIES[species]
    cw = crown * scale
    ch = crown * scale * sp["ratio"] * CE
    trunk_h = max(1.5, height - crown * sp["ratio"]) * scale * CE
    W = int(cw * 1.5) + 12
    H = int(ch + trunk_h + cw * 0.3) + 12
    img = np.zeros((H, W, 4), np.float32)
    bx, by = W / 2, H - 6 - cw * 0.12
    # trunk
    tw = max(1.5, crown * scale * 0.07)
    cv2.rectangle(img, (int(bx - tw / 2), int(by - trunk_h - ch * 0.3)), (int(bx + tw / 2), int(by)), (92, 70, 52, 255), -1)
    cx, cy = bx, by - trunk_h - ch / 2
    light, mid, dark = (np.array(c, np.float32) for c in sp["col"])
    clumps = []
    n = int(10 + crown * 2.2)
    for _ in range(n):
        if sp["shape"] == "cone":
            t = rng.uniform(0, 1)          # 0 top .. 1 bottom
            yy = cy - ch / 2 + t * ch
            half = (0.08 + 0.42 * t) * cw
            xx = cx + rng.uniform(-half, half)
            r = (0.10 + 0.12 * t) * cw
        else:
            a = rng.uniform(0, 2 * math.pi); d = rng.uniform(0, 0.38) ** 0.8
            xx = cx + math.cos(a) * d * cw * 0.95
            yy = cy + math.sin(a) * d * ch * 0.95
            r = rng.uniform(0.16, 0.26 if sp["shape"] == "round" else 0.2) * cw
        clumps.append((xx, yy, r))
    clumps.sort(key=lambda c: c[1])  # far (upper) clumps first
    yy_, xx_ = np.mgrid[0:H, 0:W].astype(np.float32)
    for xx, yy, r in clumps:
        d2 = ((xx_ - xx) ** 2 + (yy_ - yy) ** 2) / (r * r)
        m = d2 < 1
        # light from the upper left; lower and right parts darker; leaf grain
        lx, ly = (xx_ - xx) / r, (yy_ - yy) / r
        lit = np.clip(0.55 - 0.55 * lx - 0.65 * ly + (cy - yy) / ch * 0.4, 0, 1)
        grain = rng.normal(0, 0.18, (H, W)).astype(np.float32)
        t = np.clip(lit + grain, 0, 1)[..., None]
        col = np.where(t > 0.5, mid + (light - mid) * (t - 0.5) * 2, dark + (mid - dark) * t * 2)
        img[m, :3] = col[m]
        img[m, 3] = 255
    # open crowns (plane): a few gaps showing branches
    if sp["shape"] == "open":
        for _ in range(3):
            gx, gy = cx + rng.uniform(-0.25, 0.25) * cw, cy + rng.uniform(-0.1, 0.3) * ch
            cv2.circle(img, (int(gx), int(gy)), max(1, int(cw * 0.05)), (70, 60, 48, 255), -1)
    return img, (bx, by)


def mass(rng, species_mix, width_m, scale=PXM):
    """A canopy mass: many overlapping crowns, as on the wooded valley slopes."""
    W = int(width_m * scale * 1.15) + 20
    H = int(width_m * scale * 0.85) + 30
    img = np.zeros((H, W, 4), np.float32)
    pts = []
    for _ in range(int(width_m * 0.9)):
        pts.append((rng.uniform(0.1, 0.9) * W, rng.uniform(0.35, 0.95) * H, rng.choice(species_mix),
                    rng.uniform(10, 22), rng.uniform(6, 11)))
    pts.sort(key=lambda p: p[1])
    for x, y, sp, h, c in pts:
        t, (bx, by) = blob_tree(rng, sp, h, c, scale)
        x0, y0 = int(x - bx), int(y - by)
        th, tw = t.shape[:2]
        sx0, sy0 = max(0, -x0), max(0, -y0)
        sx1, sy1 = min(tw, W - x0), min(th, H - y0)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        sub = t[sy0:sy1, sx0:sx1]
        a = sub[..., 3:] / 255
        dst = img[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
        dst[..., :3] = dst[..., :3] * (1 - a) + sub[..., :3] * a
        dst[..., 3:] = np.maximum(dst[..., 3:], sub[..., 3:])
    return img, (W / 2, H - 10)


def sheet(bid):
    d = out_dir(bid) / "trees"
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    items = []
    for sp in SPECIES:
        for sz, (h, c) in SIZES.items():
            for v in range(VARIANTS):
                img, base = blob_tree(rng, sp, h * rng.uniform(0.9, 1.1), c * rng.uniform(0.9, 1.1))
                items.append({"name": f"{sp}_{sz}{v}", "species": sp, "size": sz, "img": img, "base": base})
    mixes = [["lime", "chestnut", "plane"], ["chestnut", "lime", "conifer"], ["lime", "plane", "beech_red"],
             ["chestnut", "chestnut", "lime"]]
    for i in range(MASSES):
        img, base = mass(rng, mixes[i], 40 if i % 2 == 0 else 28)
        items.append({"name": f"mass_{i}", "species": "mass", "size": "m", "img": img, "base": base})
    # pack into a strip 5120 px wide: cells with 70 px gaps (the painter's free band is 64 px)
    GAP = 70
    x, y, rowh = GAP, GAP, 0
    W = 5120
    for it in items:
        h, w = it["img"].shape[:2]
        if x + w + GAP > W:
            x, y, rowh = GAP, y + rowh + GAP, 0
        it["xy"] = (x, y)
        x += w + GAP
        rowh = max(rowh, h)
    H = int(math.ceil((y + rowh + GAP) / 16) * 16)
    src = np.zeros((H, W, 3), np.float32) + BACKDROP
    lay = src.copy()
    keep = np.full((H, W), 255, np.uint8)
    meta = []
    for it in items:
        x, y = it["xy"]
        h, w = it["img"].shape[:2]
        a = it["img"][..., 3:] / 255
        src[y:y + h, x:x + w] = src[y:y + h, x:x + w] * (1 - a) + it["img"][..., :3] * a
        lay[y:y + h, x:x + w] = lay[y:y + h, x:x + w] * (1 - a) + np.array((110, 170, 90)) * a
        keep[y:y + h, x:x + w][a[..., 0] > 0] = 0
        meta.append({"name": it["name"], "species": it["species"], "size": it["size"], "box": [x, y, w, h],
                     "base": [it["base"][0], it["base"][1]]})
    Image.fromarray(src.clip(0, 255).astype(np.uint8)).save(d / "sheet_src.png")
    Image.fromarray(lay.clip(0, 255).astype(np.uint8)).save(d / "sheet_layout.png")
    Image.fromarray(keep).save(d / "sheet_keep.png")
    (d / "sheet.json").write_text(json.dumps({"size": [W, H], "items": meta}, indent=1))
    preview(Image.fromarray(src.clip(0, 255).astype(np.uint8)), POC_IMG / "s4_sheet_src.jpg")
    print(d / "sheet_src.png", (W, H), len(items), "items")


def cut(bid, painted, season, slack=None):
    d = out_dir(bid) / "trees"
    meta = json.loads((d / "sheet.json").read_text())
    P = np.asarray(Image.open(painted).convert("RGB")).astype(np.float32)
    src = np.asarray(Image.open(d / "sheet_src.png").convert("RGB")).astype(np.float32)
    if P.shape != src.shape:
        P = np.asarray(Image.open(painted).convert("RGB").resize((src.shape[1], src.shape[0]), Image.LANCZOS)).astype(np.float32)
    # the painter's shift, measured on the buildings painted in the same job (the sheet is too sparse to measure)
    sh = out_dir(bid) / "objects" / "shift.txt"
    if sh.exists():
        dx, dy = (float(v) for v in sh.read_text().split())
        P = unshift(P, dx, dy).astype(np.float32)
    lib = d / f"lib_{season}"
    lib.mkdir(exist_ok=True)
    slack = slack or (9 if season == "spring" else 5)  # the season pass paints fuller crowns than the summer shapes
    out = []
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * slack + 1, 2 * slack + 1))
    for it in meta["items"]:
        x, y, w, h = it["box"]
        pad = slack + 2
        x0, y0, x1, y1 = x - pad, y - pad, x + w + pad, y + h + pad
        crop = P[y0:y1, x0:x1]
        shape = (np.abs(src[y0:y1, x0:x1] - BACKDROP).sum(2) > 30).astype(np.uint8)
        rule1 = cv2.dilate(shape, ker) > 0
        dist = np.abs(crop - np.array(BACKDROP)).sum(2)
        a = np.clip((dist - 120) / 80, 0, 1) * rule1
        a = cv2.GaussianBlur(a.astype(np.float32), (3, 3), 0.6) * (a > 0) + 0 * a
        col = crop.copy()
        spill = np.clip((col[..., 0] + col[..., 2]) / 2 - col[..., 1] - 30, 0, None)
        # the painted glow round each tree: light, pinkish pixels (backdrop mixed with paper white) are dropped
        pink = (crop[..., 0] + crop[..., 2]) / 2 - crop[..., 1]
        lum = crop @ np.array((0.3, 0.59, 0.11), np.float32)
        # (white is blossom in spring, so only the pink glow goes there)
        if season != "spring":  # spring blossom is white and pink
            a = np.where((pink > 8) & (lum > 120) | (lum > 200), 0, a)
        else:  # the season pass paints a bright lawn round the trunk: drop grass green in the lower part
            hh = crop.shape[0]
            low = (np.arange(hh)[:, None] > hh * 0.62) & np.ones((1, crop.shape[1]), bool)
            grass = (crop[..., 1] > 150) & (crop[..., 2] < 120) & (crop[..., 1] - crop[..., 0] > 25)
            a = np.where(low & grass, 0, a)
        a = cv2.erode((a > 0).astype(np.uint8), np.ones((2, 2), np.uint8)).astype(np.float32) * a + 0 * a
        col[..., 0] -= spill * 0.7; col[..., 2] -= spill * 0.7
        if it["species"] == "beech_red" and season == "summer":
            # the painter turned the copper beech green: give the foliage its copper-purple back, keeping the shading
            g = col.mean(axis=2, keepdims=True)
            leaf = (col[..., 1] > col[..., 0]).astype(np.float32)[..., None]
            col = col * (1 - leaf) + (g * np.array((1.25, 0.62, 0.66), np.float32)) * leaf
        rgba = np.dstack((col.clip(0, 255), (a * 255).clip(0, 255))).astype(np.uint8)
        Image.fromarray(rgba).save(lib / f"{it['name']}.png")
        out.append({**it, "file": f"{it['name']}.png", "base": [it["base"][0] + pad, it["base"][1] + pad],
                    "w": x1 - x0, "h": y1 - y0})
    (d / f"lib_{season}.json").write_text(json.dumps(out, indent=1))
    contact(bid, season)
    print(lib, len(out), "sprites")


def season_inputs(bid):
    """Inputs for a season pass of the painted summer sheet (the light model): the sheet padded to the painter's
    1024 px minimum height with backdrop, the backdrop held."""
    d = out_dir(bid) / "trees"
    P = Image.open(d / "painted_sheet.png").convert("RGB")
    sh = out_dir(bid) / "objects" / "shift.txt"
    if sh.exists():  # start from the shift-corrected sheet, so the season pass's own shift is the only one left
        dx, dy = (float(v) for v in sh.read_text().split())
        P = Image.fromarray(unshift(np.asarray(P), dx, dy))
    keep = Image.open(d / "sheet_keep.png").convert("L")
    H = 1024
    src = Image.new("RGB", (P.width, H), BACKDROP); src.paste(P, (0, 0))
    kp = Image.new("L", (P.width, H), 255); kp.paste(keep, (0, 0))
    src.save(d / "season_src.png"); kp.save(d / "season_keep.png")
    print(d / "season_src.png", src.size)


def contact(bid, season):
    d = out_dir(bid) / "trees"
    items = json.loads((d / f"lib_{season}.json").read_text())
    S = 3  # shown 3x, so the painted detail is visible
    cell = 200
    cols = 8
    rows = math.ceil(len(items) / cols)
    sheet = Image.new("RGB", (cols * cell, rows * cell), (244, 240, 230))
    for i, it in enumerate(items):
        im = Image.open(d / f"lib_{season}" / it["file"])
        s = min(S, (cell - 10) / max(im.size))
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.NEAREST if s >= 2 else Image.LANCZOS)
        sheet.paste(im, ((i % cols) * cell + (cell - im.width) // 2, (i // cols) * cell + (cell - im.height) // 2), im)
    preview(sheet, POC_IMG / f"s4_library_{season}.jpg")


# ---------------------------------------------------------------- placement
def place(bid, k):
    """Choose a sprite, scale and colour jitter for every surveyed tree whose base falls in the block."""
    b = block(bid)
    trees = json.loads((inputs_dir(bid) / "trees_lidar2024.json").read_text())
    lib = json.loads((out_dir(bid) / "trees" / "lib_summer.json").read_text())
    by = {}
    for it in lib:
        by.setdefault((it["species"], it["size"]), []).append(it)
    masses = [it for it in lib if it["species"] == "mass"]
    e = np.array([t["e"] for t in trees]); n = np.array([t["n"] for t in trees])
    x, y = en_to_map(e, n, ground_z(e, n))
    lx, ly = (x - b["x0"]) * k, (y - b["y0"]) * k
    S = b["w"] * k
    ins = (lx > -60) & (lx < S + 60) & (ly > -20) & (ly < S + 120)
    # density: neighbours within 12 m, to find woods
    from scipy.spatial import cKDTree
    tree = cKDTree(np.column_stack((e, n)))
    dens = np.array([len(v) for v in tree.query_ball_point(np.column_stack((e, n)), 12.0)])
    rng = np.random.default_rng(11)
    placed = []
    used_mass = np.zeros(len(trees), bool)
    order = np.argsort(-dens)
    # canopy masses for the densest woods: one mass stands in for the trees around it
    for i in order:
        if not ins[i] or used_mass[i] or dens[i] < 14 or trees[i]["type"] == "conifer":
            continue
        m = masses[rng.integers(len(masses))]
        width_m = m["w"] / PXM / 1.15
        near = tree.query_ball_point((e[i], n[i]), width_m * 0.42)
        used_mass[near] = True
        placed.append({"s": m["file"], "x": float(lx[i]), "y": float(ly[i]), "sc": float(k * 6000 / 5120 * rng.uniform(0.9, 1.1)),
                       "j": float(rng.uniform(-0.06, 0.06)), "mass": 1})
    # no tree rooted in the river: the survey finds crowns hanging over the water, but the painting keeps the
    # rivers open, and a trunk in the water reads wrong
    wm = np.asarray(Image.open(out_dir(bid) / f"k{int(k * 100)}" / "water_mask.png")) > 0 if \
        (out_dir(bid) / f"k{int(k * 100)}" / "water_mask.png").exists() else None
    for i in np.flatnonzero(ins & ~used_mass):
        t = trees[i]
        if wm is not None:
            xi, yi = int(lx[i]), int(ly[i])
            if 0 <= xi < wm.shape[1] and 0 <= yi < wm.shape[0] and wm[max(0, yi - 3):yi + 4, max(0, xi - 3):xi + 4].any():
                continue
        sp = {"conifer": "conifer"}.get(t["type"])
        if t["type"] == "deciduous_red" and rng.random() < 0.3:  # the survey's "red" is often just shade
            sp = "beech_red"
        if sp is None:
            sp = ["lime", "chestnut", "plane"][int(rng.integers(3))] if dens[i] < 8 else ["chestnut", "lime"][int(rng.integers(2))]
        size = "l" if t["h"] > 11 else "s"
        cand = by.get((sp, size)) or by[("lime", size)]
        it = cand[int(rng.integers(len(cand)))]
        nominal = SIZES[size][1]
        sc = float(np.clip(0.9 * (2 * max(t["cmean"], 1.0)) / nominal, 0.45, 1.6))
        placed.append({"s": it["file"], "x": float(lx[i]), "y": float(ly[i]), "sc": sc * k * 6000 / 5120,
                       "j": float(rng.uniform(-0.06, 0.06)), "h": t["h"]})
    placed.sort(key=lambda p: p["y"])
    d = out_dir(bid) / "trees"
    (d / f"placed_k{int(k * 100)}.json").write_text(json.dumps({"k": k, "trees": placed}))
    print(len(placed), "placed,", int(sum(1 for p in placed if p.get("mass"))), "canopy masses")


def render(bid, season, k):
    """All placed trees into one RGBA layer (trunk bases sorted far to near) plus a row map for depth."""
    d = out_dir(bid) / "trees"
    pl = json.loads((d / f"placed_k{int(k * 100)}.json").read_text())["trees"]
    lib = {it["file"]: it for it in json.loads((d / f"lib_{season}.json").read_text())}
    S = round(6000 * k)
    # Spring: only some trees blossom (as in the city: cherries, magnolias, some fruit trees); the others get the
    # summer drawing tinted to fresh light green. Per-tree control is the point of a tree layer.
    rng = np.random.default_rng(5)
    fresh = np.array((1.08, 1.16, 0.78), np.float32)
    libs = {s_: {it["file"]: it for it in json.loads((d / f"lib_{s_}.json").read_text())}
            for s_ in {season, "summer"}}
    acc = np.zeros((S, S, 4), np.float32)
    row = np.zeros((S, S), np.uint16)   # trunk-base row of the tree drawn at each pixel (for depth against buildings)
    cache = {}
    for p in pl:
        it = lib[p["s"]]
        src_season = season
        if season == "spring" and (rng.random() > 0.3 or p["s"].startswith("conifer")):
            src_season = "summer"
        key = (p["s"], round(p["sc"], 2), src_season)
        if key not in cache:
            im = Image.open(d / f"lib_{src_season}" / p["s"])
            w, h = max(1, round(im.width * p["sc"])), max(1, round(im.height * p["sc"]))
            cache[key] = np.asarray(im.resize((w, h), Image.LANCZOS)).astype(np.float32)
            if season == "spring" and src_season == "summer" and not p["s"].startswith("conifer"):
                cache[key][..., :3] *= fresh
        spr = cache[key]
        if src_season != season:
            it = libs[src_season][p["s"]]
        h, w = spr.shape[:2]
        x0 = int(round(p["x"] - it["base"][0] * p["sc"])); y0 = int(round(p["y"] - it["base"][1] * p["sc"]))
        sx0, sy0 = max(0, -x0), max(0, -y0)
        sx1, sy1 = min(w, S - x0), min(h, S - y0)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        sub = spr[sy0:sy1, sx0:sx1]
        a = sub[..., 3:] / 255
        col = sub[..., :3] * (TONE + p["j"])
        dst = acc[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
        dst[..., :3] = dst[..., :3] * (1 - a) + col * a
        dst[..., 3:] = dst[..., 3:] * (1 - a) + 255 * a
        r = row[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
        r[a[..., 0] > 0.5] = int(min(65535, max(0, p["y"])))
    out = d / f"L8_trees_{season}_k{int(k * 100)}.png"
    Image.fromarray(acc.clip(0, 255).astype(np.uint8)).save(out)
    Image.fromarray(row).save(d / f"tree_rows_k{int(k * 100)}.png")
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--k", type=float, default=5120 / 6000)
    a = ap.parse_args()
    bid = a.args[0] if a.args and a.args[0].startswith("b") and len(a.args[0]) == 3 else "b00"
    rest = [x for x in a.args if x != bid]
    if a.cmd == "sheet":
        sheet(bid)
    elif a.cmd == "cut":
        cut(bid, rest[0], rest[1])
    elif a.cmd == "season_inputs":
        season_inputs(bid)
    elif a.cmd == "contact":
        contact(bid, rest[0])
    elif a.cmd == "place":
        place(bid, a.k)
    elif a.cmd == "render":
        render(bid, rest[0], a.k)
