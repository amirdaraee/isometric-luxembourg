"""Halo-free event patches: composite a drawing service output (the square with an event added) over the CURRENT
painted art, keeping only the event's objects.

Shared by xmas_v2.py (Christmas) and event_patch.py (other events). The rules, so no edge can show:
  - the patch is made at map scale (1 patch px = 1 map px), so it is drawn 1:1 with the tiles;
  - the object mask comes from where the drawing differs from what was sent, refined at the edges with a guided
    filter on the drawing; bright rims the drawing service tends to draw round what it changed are left out;
  - the objects are blended into the current art IN THE FILE (2 px grow, 3 px feather), and the patch has no alpha
    at all: it is the box round everything that changed, opaque, holding the map tiles' own pixels outside the
    objects, so its straight edge matches the screen to the pixel. (The viewer's WebGL drawer, OpenSeadragon 5.0.1,
    blends straight-alpha images as if premultiplied, which turns any soft or even resampled hard alpha edge into a
    light rim, so a patch must not rely on alpha);
  - colour is matched locally (64 px tiles, smoothed) on a 6 to 20 px ring just outside the objects;
  - at night the market's warm light on the ground is baked in as light only (a warm tint fading to nothing),
    never as redrawn map pixels;
  - day and night of one site share one opaque region, so the night patch fading in over the day patch (alpha 1)
    gives exactly the night art, at every moment of dusk;
  - saved as lossless WebP. Rerun the composite whenever the tiles of its versions are rebuilt.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from common import WORK  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
BLOCK = 6000


def canvas_for(x: float, y: float, version: str) -> tuple[Path, dict]:
    """The newest painted canvas of `version` ("day" or a version name) for the block that holds map px (x, y),
    read from the city_blocks.py state, preferring the block whose centre is nearest."""
    st = json.loads((WORK / "city" / "blocks.json").read_text())
    done = st["done"] if version == "day" else st.get("done_v", {}).get(version, {})
    best = None
    for b in st["blocks"]:
        if b["id"] not in done or not (b["x0"] <= x < b["x0"] + b["w"] and b["y0"] <= y < b["y0"] + b["h"]):
            continue
        d = np.hypot(x - b["x0"] - b["w"] / 2, y - b["y0"] - b["h"] / 2)
        if best is None or d < best[0]:
            best = (d, b)
    if best is None:
        raise SystemExit(f"no painted {version} block holds {x:.0f},{y:.0f}")
    return Path(done[best[1]["id"]]), best[1]


_canvases: dict[str, Image.Image] = {}


def tiles_crop(version: str, x0: int, y0: int, w: int, h: int) -> np.ndarray | None:
    """The full-resolution map tiles of a version ("day" or a version name) for map px (x0, y0, w, h): exactly the
    pixels the viewer shows when zoomed in. None if they are not built."""
    tiles = ROOT / "web/public/tiles"
    if not (tiles / "meta.json").exists():
        return None
    meta = json.loads((tiles / "meta.json").read_text())
    folder = tiles / ("map_files" if version == "day" else meta.get("variants", {}).get(version, "-"))
    if not folder.is_dir():
        return None
    level = max(int(d.name) for d in folder.iterdir() if d.is_dir() and d.name.isdigit())
    t = meta["tileSize"]
    out = np.zeros((h, w, 3), np.uint8)
    for ty in range(y0 // t, (y0 + h - 1) // t + 1):
        for tx in range(x0 // t, (x0 + w - 1) // t + 1):
            f = folder / str(level) / f"{tx}_{ty}.webp"
            if not f.exists():
                return None
            im = np.asarray(Image.open(f).convert("RGB"))
            sx0, sy0 = max(x0, tx * t), max(y0, ty * t)
            sx1, sy1 = min(x0 + w, tx * t + im.shape[1]), min(y0 + h, ty * t + im.shape[0])
            out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = im[sy0 - ty * t:sy1 - ty * t, sx0 - tx * t:sx1 - tx * t]
    return out


def base_crop(x0: int, y0: int, w: int, h: int, version: str, source: str = "tiles") -> np.ndarray:
    """The current art of `version` for map px (x0, y0, w, h), at map scale, as uint8 RGB. From the built map
    tiles when they exist (so the patch edge matches the screen to the pixel; rerun the composite after every tile
    rebuild), else from the newest painted canvas of the block (city_blocks.py state)."""
    if source == "tiles":
        t = tiles_crop(version, x0, y0, w, h)
        if t is not None:
            return t
    path, b = canvas_for(x0 + w / 2, y0 + h / 2, version)
    if str(path) not in _canvases:
        _canvases[str(path)] = Image.open(path).convert("RGB")
    im = _canvases[str(path)]
    k = im.width / b["w"]
    box = tuple(int(round(v)) for v in ((x0 - b["x0"]) * k, (y0 - b["y0"]) * k, (x0 + w - b["x0"]) * k, (y0 + h - b["y0"]) * k))
    return np.asarray(im.crop(box).resize((w, h), Image.LANCZOS))


def guided(I: np.ndarray, p: np.ndarray, r: int = 4, eps: float = 1e-3) -> np.ndarray:
    """Grey guided filter (He et al.): smooths p while following the edges of I. Both float in 0..1."""
    f = lambda a: cv2.boxFilter(a, -1, (2 * r + 1, 2 * r + 1))  # noqa: E731
    mi, mp = f(I), f(p)
    a = (f(I * p) - mi * mp) / (f(I * I) - mi * mi + eps)
    b = mp - a * mi
    return f(a) * I + f(b)


def object_mask(raw: np.ndarray, sent: np.ndarray, centre_r: float, min_area: int, thr: int = 70) -> np.ndarray:
    """Where the drawing added things: large changed blobs near the centre, holes filled, edges refined. 0/1 uint8."""
    n_ = raw.shape[0]
    yy, xx = np.mgrid[0:n_, 0:n_]
    rad = np.hypot(xx - n_ / 2, yy - n_ / 2)
    diff = np.abs(cv2.GaussianBlur(raw, (0, 0), 2).astype(int) - cv2.GaussianBlur(sent, (0, 0), 2).astype(int)).sum(2)
    changed = ((diff > thr) & (rad < n_ * 0.46)).astype(np.uint8)
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    changed = cv2.morphologyEx(changed, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(changed)
    keep = np.zeros_like(changed)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] > min_area and np.hypot(cen[i][0] - n_ / 2, cen[i][1] - n_ / 2) < centre_r:
            keep[lab == i] = 1
    # fill holes enclosed by the kept objects (snow between chalets the drawing left alike)
    flood = keep.copy() * 255
    ff = np.zeros((n_ + 2, n_ + 2), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 128)
    keep[flood == 0] = 1
    # refine the edge on the drawing itself
    g = cv2.cvtColor(raw, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    soft = guided(g, keep.astype(np.float32), r=4, eps=2e-3)
    return (soft > 0.5).astype(np.uint8)


def local_match(raw: np.ndarray, base: np.ndarray, mask: np.ndarray, tile: int = 64, night: bool = False) -> np.ndarray:
    """Shift the drawing's LAB colour so that, on a 6 to 20 px ring just outside the objects, it matches the
    current art. Offsets are measured per tile (median), filled outward and smoothed, then applied to the objects."""
    o = cv2.cvtColor(raw, cv2.COLOR_RGB2LAB).astype(np.float32)
    b = cv2.cvtColor(base, cv2.COLOR_RGB2LAB).astype(np.float32)
    d_in = cv2.distanceTransform((1 - mask).astype(np.uint8), cv2.DIST_L2, 5)
    ring = (d_in >= 6) & (d_in <= 20)
    if night:  # the market's own glow spills onto the ring: leave lit pixels out
        ring &= (o[..., 0] - b[..., 0]) < 20
    H, W = mask.shape
    gy, gx = (H + tile - 1) // tile, (W + tile - 1) // tile
    off = np.full((gy, gx, 3), np.nan, np.float32)
    for j in range(gy):
        for i in range(gx):
            sl = (slice(j * tile, (j + 1) * tile), slice(i * tile, (i + 1) * tile))
            r = ring[sl]
            if r.sum() > 60:
                off[j, i] = np.median((b[sl] - o[sl])[r], axis=0)
    have = ~np.isnan(off[..., 0])
    if not have.any():
        return raw
    glob = np.median(off[have], axis=0)
    # fill empty tiles outward from the measured ones (mean of measured neighbours, ring by ring)
    filled, known = off.copy(), have.copy()
    while not known.all():
        nxt = known.copy()
        for j, i in np.argwhere(~known):
            nb = [filled[y, x] for y in range(max(j - 1, 0), min(j + 2, gy)) for x in range(max(i - 1, 0), min(i + 2, gx)) if known[y, x]]
            if nb:
                filled[j, i] = np.mean(nb, axis=0)
                nxt[j, i] = True
        known = nxt
    filled = 0.7 * filled + 0.3 * glob
    full = cv2.resize(filled, (W, H), interpolation=cv2.INTER_CUBIC)
    full = cv2.GaussianBlur(full, (0, 0), tile * 0.75)
    full = np.clip(full, -25, 25)
    o += full
    return cv2.cvtColor(np.clip(o, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


WARM = np.array((255, 196, 120), np.float32)


def glow_alpha(raw: np.ndarray, base: np.ndarray, mask: np.ndarray, reach: int = 32) -> np.ndarray:
    """Night only: how much warm light the drawing put on the ground around the objects, as the strength of a warm
    tint (raw ~ base * (1 - a) + WARM * a). Only warm brightening counts (a redraw that is merely lighter or
    bluer does not), smoothed, and fading to 0 by `reach` px from the objects."""
    r, b = raw.astype(np.float32), base.astype(np.float32)
    d = r - b
    warm = (d[..., 0] - d[..., 2] > 18) & (d[..., 1] > 8)
    a = np.clip(d[..., 1] / np.maximum(WARM[1] - b[..., 1], 30), 0, 1) * warm
    a = cv2.GaussianBlur(a.astype(np.float32), (0, 0), 4)
    a = np.clip((a - 0.05) / 0.95, 0, 0.6)
    dist = cv2.distanceTransform((1 - mask).astype(np.uint8), cv2.DIST_L2, 5)
    return a * np.clip(1 - dist / reach, 0, 1) ** 1.5


def drop_rims(raw: np.ndarray, base: np.ndarray, mask: np.ndarray, width: int = 4) -> np.ndarray:
    """Leave out the light, greyish rims the drawing service draws along the edge of what it changed (a white
    line round a redrawn square reads as a highlight on the edge)."""
    band = (mask > 0) & (cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5) <= width)
    lab_r = cv2.cvtColor(raw, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_b = cv2.cvtColor(base, cv2.COLOR_RGB2LAB).astype(np.float32)
    chroma = np.hypot(lab_r[..., 1] - 128, lab_r[..., 2] - 128)
    rim = band & (lab_r[..., 0] - lab_b[..., 0] > 25) & (chroma < 18)
    out = mask.copy()
    out[rim] = 0
    return cv2.morphologyEx(out, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def prepare(raw_img: Image.Image, sent_img: Image.Image, base: np.ndarray, night: bool,
            centre_r: float | None = None, min_area: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """The drawing at map scale, colour-matched locally to the current art, and its object mask (0/1)."""
    H, W = base.shape[:2]
    raw = np.asarray(raw_img.convert("RGB").resize((W, H), Image.LANCZOS))
    sent = np.asarray(sent_img.convert("RGB").resize((W, H), Image.LANCZOS))
    mask = object_mask(raw, sent, centre_r if centre_r is not None else W * 0.32,
                       min_area if min_area is not None else int(1500 * (W / 1024) ** 2))
    mask = drop_rims(raw, base, mask)
    return local_match(raw, base, mask, night=night), mask


def blend(raw: np.ndarray, base: np.ndarray, mask: np.ndarray, night: bool) -> tuple[np.ndarray, np.ndarray]:
    """The art with the objects (and at night their light) blended in, and where it differs from the art."""
    grown = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))       # grow by 2 px
    soft = np.clip(cv2.GaussianBlur(grown.astype(np.float32), (0, 0), 1.2) * 1.15, 0, 1)[..., None]  # ~3 px feather
    rgb = raw.astype(np.float32) * soft + base.astype(np.float32) * (1 - soft)
    support = soft[..., 0] > 0.004
    if night:
        g = (glow_alpha(raw, base, grown) * (1 - soft[..., 0]))[..., None]
        rgb = rgb * (1 - g) + WARM * g
        support |= g[..., 0] > 0.004
    return rgb, support


def finish(rgb: np.ndarray, region: np.ndarray, pad: int = 4) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """The patch: fully opaque, cut to the box round `region` (plus `pad` px). Outside the region it holds the
    current art's own pixels (from the tiles), so its straight edge matches the map to the pixel. Returns the image
    and its box (x, y, w, h) in patch px."""
    ys, xs = np.nonzero(region)
    H, W = region.shape
    x0, y0 = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
    x1, y1 = min(int(xs.max()) + 1 + pad, W), min(int(ys.max()) + 1 + pad, H)
    out = np.clip(rgb[y0:y1, x0:x1] + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB"), (x0, y0, x1 - x0, y1 - y0)


def region_of(*supports: np.ndarray) -> np.ndarray:
    """The opaque region: everything that differs from the art, plus a 3 px margin of the art's own pixels."""
    s = np.zeros_like(supports[0], np.uint8)
    for x in supports:
        s |= x.astype(np.uint8)
    return cv2.dilate(s, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))


def composite(raw_img: Image.Image, sent_img: Image.Image, base: np.ndarray, night: bool) -> tuple[Image.Image, tuple]:
    """One patch on its own (an event shown in one light only), and its box in patch px."""
    raw, mask = prepare(raw_img, sent_img, base, night)
    rgb, sup = blend(raw, base, mask, night)
    return finish(rgb, region_of(sup))


def composite_pair(day: tuple, night: tuple, share: bool = False) -> tuple[Image.Image, Image.Image, dict]:
    """Day and night patches of one site, each (raw_img, sent_img, base), sharing one opaque region. share: the
    night drawing was made from an input that already held the day market (relit), so its objects are the day
    drawing's objects plus whatever else it changed."""
    rd, md = prepare(*day, night=False)
    rn, mn = prepare(*night, night=True)
    if share:
        mn = np.maximum(mn, md)
    cd, sd = blend(rd, day[2], md, False)
    cn, sn = blend(rn, night[2], mn, True)
    region = region_of(sd, sn)
    (pd, bx), (pn, _) = finish(cd, region), finish(cn, region)
    info = {"day_objects_pct": round(float(md.mean() * 100), 1), "night_objects_pct": round(float(mn.mean() * 100), 1),
            "region_pct": round(float(region.mean() * 100), 1), "box": bx}
    return pd, pn, info


def save_patch(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", lossless=True, quality=100, method=6)


def over(patch: Image.Image, base: np.ndarray, at: tuple[int, int] = (0, 0)) -> np.ndarray:
    """The patch laid on a base crop at patch px `at` (uint8 RGB)."""
    out = base.copy()
    p = np.asarray(patch.convert("RGB"))
    out[at[1]:at[1] + p.shape[0], at[0]:at[0] + p.shape[1]] = p
    return out
