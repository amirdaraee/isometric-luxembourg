"""Shared helpers for the layered map (LAYERS_POC.md): the block, the map projection, reading the render passes.

Map px are mosaic px (0.25 m per px at full resolution), as in render.py, layout.py and project_lines.py.
Layers are written at a scale `k` of the block (1.0 = 6000 px for a 6000 px block; 0.5 for quick iterations).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ELEV, ORIGIN_E, ORIGIN_N, R, ROOT, RAW, WORK, en_to_lonlat, lonlat_to_en  # noqa: E402,F401

Image.MAX_IMAGE_PIXELS = None
LAYERS = WORK / "layers"
MOSAIC = json.loads((WORK / "mosaic.json").read_text())
F = MOSAIC["frame"]
BG = (16, 24, 40)

_t = np.load(WORK / "terrain.npz")
TZ, TE0, TN0, TS = _t["z"], float(_t["e0"]), float(_t["n0"]), float(_t["step"])


def block(bid="b00"):
    st = json.loads((WORK / "city" / "blocks.json").read_text())
    return next(b for b in st["blocks"] if b["id"] == bid)


def out_dir(bid="b00"):
    d = LAYERS / bid
    d.mkdir(parents=True, exist_ok=True)
    return d


def inputs_dir(bid="b00"):
    d = LAYERS / bid / "inputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ground_z(e, n):
    """Bare-earth height (m) at LUREF e, n (arrays allowed), bilinear."""
    fx = (np.asarray(e, float) - TE0) / TS
    fy = (np.asarray(n, float) - TN0) / TS
    x0 = np.clip(np.floor(fx).astype(int), 0, TZ.shape[1] - 2)
    y0 = np.clip(np.floor(fy).astype(int), 0, TZ.shape[0] - 2)
    ax, ay = np.clip(fx - x0, 0, 1), np.clip(fy - y0, 0, 1)
    z = (TZ[y0, x0] * (1 - ax) * (1 - ay) + TZ[y0, x0 + 1] * ax * (1 - ay) + TZ[y0 + 1, x0] * (1 - ax) * ay
         + TZ[y0 + 1, x0 + 1] * ax * ay)
    return z


def en_to_map(e, n, z):
    """LUREF e, n and height z (m) to mosaic px (float)."""
    le, ln = np.asarray(e, float) - ORIGIN_E, np.asarray(n, float) - ORIGIN_N
    sx = (le + ln) * R
    sy = (-le + ln) * R * math.sin(ELEV) + np.asarray(z, float) * math.cos(ELEV)
    return (sx - MOSAIC["sx0"]) / MOSAIC["mpp"], (MOSAIC["sy1"] - sy) / MOSAIC["mpp"]


def lonlat_to_map(lon, lat, z=None):
    e, n = lonlat_to_en(lon, lat)
    if z is None:
        z = ground_z(e, n)
    return en_to_map(e, n, z)


def map_to_en(px, py, z):
    """Inverse of en_to_map for a known height."""
    sx = MOSAIC["sx0"] + np.asarray(px, float) * MOSAIC["mpp"]
    sy = MOSAIC["sy1"] - np.asarray(py, float) * MOSAIC["mpp"]
    f = (sy - np.asarray(z, float) * math.cos(ELEV)) / math.sin(ELEV)
    return (sx - f) / (2 * R) + ORIGIN_E, (sx + f) / (2 * R) + ORIGIN_N


def block_lonlat(b, margin_m=0.0):
    """lon/lat box (w, s, e, n) of the ground a block can show (heights 200-420 m)."""
    es, ns = [], []
    for px in (b["x0"], b["x0"] + b["w"]):
        for py in (b["y0"], b["y0"] + b["h"]):
            for z in (200, 420):
                e, n = map_to_en(px, py, z)
                es.append(float(e)); ns.append(float(n))
    e0, e1, n0, n1 = min(es) - margin_m, max(es) + margin_m, min(ns) - margin_m, max(ns) + margin_m
    w, s = en_to_lonlat(e0, n0)
    e, n = en_to_lonlat(e1, n1)
    return w, s, e, n


def cut(folder, ext, mode, fill, b, k=1.0, resample=Image.NEAREST):
    """The block's crop of a render pass (frames, frames_kind, frames_line, frames_height), scaled by k."""
    x0, y0, W, H = b["x0"], b["y0"], b["w"], b["h"]
    im = Image.new(mode, (W, H), fill)
    for r in range(max(y0, 0) // F, (y0 + H) // F + 1):
        for c in range(max(x0, 0) // F, (x0 + W) // F + 1):
            p = WORK / folder / f"{c}_{r}.{ext}"
            if p.exists():
                im.paste(Image.open(p).convert(mode), (c * F - x0, r * F - y0))
    if k != 1.0:
        im = im.resize((round(W * k), round(H * k)), resample)
    return im


def heights(b, k=1.0):
    """Visible-surface height above sea level in m (0 = empty), float32, at scale k."""
    im = cut("frames_height", "png", "I;16", 0, b, k)
    return np.asarray(im, np.float32) / 100.0


def kinds(b, k=1.0):
    """frames_kind: ground 255, bridge decks 128, walls 64, roofs 0 (and empty map edge, also 0)."""
    return np.asarray(cut("frames_kind", "png", "L", 0, b, k))


def today(b, k=1.0, version="day_s8"):
    """Today's painted art for the block, resized to the layer grid."""
    im = Image.open(WORK / "city" / b["id"] / f"canvas_{version}.png").convert("RGB")
    return im.resize((round(b["w"] * k), round(b["h"] * k)), Image.LANCZOS)


def preview(im, path, size=1600, quality=82):
    """Small JPEG for the progress page."""
    im = im if isinstance(im, Image.Image) else Image.fromarray(im)
    im = im.convert("RGB")
    s = min(1.0, size / max(im.size))
    if s < 1:
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path, quality=quality)
    return path


# The local progress page's image folder (web/public/poc/img); POC_IMG overrides it (e.g. from a worktree).
import os  # noqa: E402
POC_IMG = Path(os.environ.get("POC_IMG", ROOT / "web" / "public" / "poc" / "img"))
