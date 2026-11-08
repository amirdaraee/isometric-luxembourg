"""Remove painted vehicles from the day art and carry the repair into the painted versions (PLAN_NEXT item 4).

Never writes into data/work/city/<block>/canvas_*: every output goes to data/work/repair/<block>/, and the list of
canvases to replace is printed (and kept in data/work/repair/replace.json) for whoever swaps them in.

  repair_cars.py masks <block|all>         accepted spots (vehicles_<block>.json minus the rejects in
                                           decisions.json) -> mask_<block>.png at canvas scale, each box grown 1.5 m.
                                           Tight masks are also the ones for the painter: the first pilot closed car
                                           groups into one area (gpumasks) and the painter invented a lawn there.
  repair_cars.py gpumasks <block|all>      the same, grown 3 m and closed over 8 m (car groups as one area),
                                           for method (b) -> mask_<block>_gpu.png
  repair_cars.py free <block|all>          method (a), no GPU: fill each spot with a piece of nearby painted ground
                                           (Poisson-blended copy); spots with no clean piece near are left for
                                           method (b) and listed in left_<block>.json -> <block>/canvas_day_free.png.
                                           Pilot verdict (b00, b04): fine for a lone car on a road, not for car
                                           parks (most spots are left, and a partly boxed car leaves a smear).
  repair_cars.py crop <block> <x0,y0,w,h>  cut a pilot crop (map px) of the day canvas, its mask and the painter's
                                           inputs, for method (b) (gpu_repair.py)
  repair_cars.py carry <block> <version> <day_repaired.png>
                                           carry a repaired day canvas into a version: per spot, the repaired day
                                           pixels with their LAB mean and spread matched to the version on a ring
                                           1 to 3 m round the spot (lit pixels left out at night)
                                           -> <block>/canvas_<version>_repaired.png
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "data" / "work"
CITY = WORK / "city"
OUT = WORK / "repair"
Image.MAX_IMAGE_PIXELS = None
MAP_MPP = 0.25


def state():
    return json.loads((CITY / "blocks.json").read_text())


def block(bid):
    return next(b for b in state()["blocks"] if b["id"] == bid)


def blocks(arg):
    st = state()
    return [b["id"] for b in st["blocks"] if b["id"] in st["done"]] if arg == "all" else arg.split(",")


def accepted(bid):
    """Candidates kept after review: decisions.json maps candidate id -> "keep" (a vehicle: remove it) or
    "reject" (not a vehicle). Candidates without a decision count as vehicles only if marked by the review rule
    in vehicles_<block>.json ("auto": true)."""
    c = json.loads((OUT / f"vehicles_{bid}.json").read_text())
    dp = OUT / "decisions.json"
    dec = json.loads(dp.read_text()) if dp.exists() else {}
    return [d for d in c if dec.get(d["id"], "keep" if d.get("auto") else "reject") == "keep"]


def masks(bid, grow_m=1.5, close_m=0.0, name=None):
    b = block(bid)
    W = Image.open(state()["done"][bid]).size[0]
    k = W / b["w"]
    m = np.zeros((W, W), np.uint8)
    grow = grow_m / MAP_MPP * k
    spots = accepted(bid)
    for d in spots:
        x0, y0 = (d["x"] - b["x0"]) * k - grow, (d["y"] - b["y0"]) * k - grow
        x1, y1 = (d["x"] + d["w"] - b["x0"]) * k + grow, (d["y"] + d["h"] - b["y0"]) * k + grow
        cv2.rectangle(m, (int(x0), int(y0)), (int(np.ceil(x1)), int(np.ceil(y1))), 255, -1)
    if close_m:   # one area for a group of cars (the painter repaints a car park whole)
        c = int(close_m / MAP_MPP * k) | 1
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (c, c)))
    m[protect(b, k, W) > 0] = 0
    Image.fromarray(m).save(OUT / (name or f"mask_{bid}.png"))
    print(bid, len(spots), "spots,", int((m > 0).sum()), "px")
    return m


GROUP_M, GROUP_MAX = 6.0, 3   # spots within 6 m of each other form a group; groups of more than 3 are car parks
GROUP_MAX_M2 = 130.0          # ... or groups with more mask than about three grown car boxes


def lone(bid):
    """mask_<block>_lone.png: the tight mask without dense groups. Pilots on RunPod (8 Nov): the painter's repair
    removes lone cars and small groups well (b00, Place de la Constitution), but where spots merge into one area
    (the b04 hospital car parks) it redraws the whole car park as a blank wall or a road, with or without a start
    image from the free fill; such car parks keep their painted cars."""
    m = np.asarray(Image.open(OUT / f"mask_{bid}.png")) > 0
    b = block(bid)
    k = m.shape[1] / b["w"]
    c = int(GROUP_M / MAP_MPP * k) | 1
    grouped = cv2.dilate(m.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (c, c)))
    ng, glab = cv2.connectedComponents(grouped)
    ns, slab = cv2.connectedComponents(m.astype(np.uint8))
    # spots per group (a spot lies inside one group, since the groups are the spots grown)
    pairs = np.unique(np.stack([slab[m], glab[m]], 1), axis=0)
    count = np.bincount(pairs[:, 1], minlength=ng)
    # and by area: overlapping boxes of a row of cars merge into one spot
    area = np.bincount(glab[m], minlength=ng) / (k / MAP_MPP) ** 2      # m2 of mask per group
    count[area > GROUP_MAX_M2] = GROUP_MAX + 1
    keep_groups = np.nonzero((count >= 1) & (count <= GROUP_MAX))[0]
    out = m & np.isin(glab, keep_groups)
    Image.fromarray((out * 255).astype(np.uint8)).save(OUT / f"mask_{bid}_lone.png")
    print(bid, f"{ns - 1} spots; kept {int(sum(count[keep_groups]))} in {len(keep_groups)} small groups; "
          f"{int((count > GROUP_MAX).sum())} car parks left as painted")
    return out


PROTECT_M = 9.0  # radius kept out of every mask round a landmark's pin (statues and monuments stand in car parks)
PROTECT_SKIP = {"square", "park", "bridge", "viewpoint", "transport", "sport"}   # pins in the middle of open ground


def protect(b, k, W):
    """Discs round the landmarks' pins that no repair may touch. The pilot on Place de la Constitution showed why:
    with the parked cars closed into one area, the painter redrew the square and lost the Gëlle Fra monument."""
    m = np.zeros((W, W), np.uint8)
    r = int(PROTECT_M / MAP_MPP * k)
    for lm in json.loads((ROOT / "web/public/data/landmarks.json").read_text()):
        if lm["category"] in PROTECT_SKIP:
            continue
        x, y = (lm["x"] - b["x0"]) * k, (lm["y"] - b["y0"]) * k
        if -r <= x < W + r and -r <= y < W + r:
            cv2.circle(m, (int(x), int(y)), r, 255, -1)
    return m


def fill_ns(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fallback fill: Navier-Stokes inpainting with a little of the painted grain put back. Smooth, so only for
    spots where no clean piece of ground lies near."""
    m = (mask > 0).astype(np.uint8)
    out = cv2.inpaint(img, m * 255, 7, cv2.INPAINT_NS)
    hp = img.astype(np.float32) - cv2.GaussianBlur(img, (0, 0), 2).astype(np.float32)
    ring = cv2.dilate(m, np.ones((9, 9), np.uint8)) - m
    grain = cv2.blur(hp * ring[..., None], (9, 9)) / np.maximum(cv2.blur(ring.astype(np.float32), (9, 9)), 1e-3)[..., None]
    soft = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.0)[..., None]
    res = out.astype(np.float32) + grain * 0.5 * soft
    res = res * soft + img.astype(np.float32) * (1 - soft)
    return np.clip(res, 0, 255).astype(np.uint8)


def fill(win: np.ndarray, sub: np.ndarray, busy: np.ndarray) -> tuple[np.ndarray, str]:
    """Fill one spot (sub, 0/1, in the window `win`) with a piece of painted ground copied from nearby: the offset
    whose ring (2 to 6 px round the spot) best matches the spot's own ring, among offsets whose source holds no
    other spot (busy) and lies inside the window; then blended in by Poisson cloning, so the painted texture, the
    ink of kerbs and the parking lines come with it and the light matches at the edge. Falls back to fill_ns."""
    H, W = sub.shape
    ys, xs = np.nonzero(sub)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    size = max(x1 - x0, y1 - y0)
    grown = cv2.dilate(sub, np.ones((5, 5), np.uint8))
    ring = (cv2.dilate(sub, np.ones((13, 13), np.uint8)) > 0) & ~(grown > 0)
    ry, rx = np.nonzero(ring)
    gy, gx = np.nonzero(grown)
    f = win.astype(np.float32)
    best = None
    for dist in (1.15, 1.5, 2.0, 2.6):
        for k in range(16):
            ang = k * np.pi / 8
            dx, dy = int(round(np.cos(ang) * dist * size)), int(round(np.sin(ang) * dist * size))
            if not (0 <= gx.min() + dx and gx.max() + dx < W and 0 <= gy.min() + dy and gy.max() + dy < H and
                    0 <= rx.min() + dx and rx.max() + dx < W and 0 <= ry.min() + dy and ry.max() + dy < H):
                continue
            if busy[gy + dy, gx + dx].any():
                continue
            cost = np.abs(f[ry + dy, rx + dx] - f[ry, rx]).mean() * (1 + 0.08 * dist)
            if best is None or cost < best[0]:
                best = (cost, dx, dy)
    if best is None or best[0] > 40:
        return fill_ns(win, sub), "ns"
    _, dx, dy = best
    src = np.roll(np.roll(win, -dy, 0), -dx, 1)
    m255 = (grown * 255).astype(np.uint8)
    cx, cy = (gx.min() + gx.max() + 1) // 2, (gy.min() + gy.max() + 1) // 2
    try:
        out = cv2.seamlessClone(src, win, m255, (int(cx), int(cy)), cv2.NORMAL_CLONE)
    except cv2.error:
        return fill_ns(win, sub), "ns"
    soft = cv2.GaussianBlur(grown.astype(np.float32), (0, 0), 0.8)[..., None]
    return np.clip(out * soft + win * (1 - soft), 0, 255).astype(np.uint8), "copy"


def free(bid, mask_name=None, dest_name="canvas_day_free.png", base=None, copy_only=True):
    """Method (a), no GPU: every spot of the mask filled by fill(), spot by spot, in a window round it.
    copy_only (the default, from the b00 and b04 pilots): a spot that no clean piece of nearby ground can fill is
    left as it is, for the painter's repair (method b): the smooth fallback leaves smudges that look worse than a
    painted car. The spots left are listed in left_<block>.json."""
    src = np.asarray(Image.open(base or state()["done"][bid]).convert("RGB"))
    m = np.asarray(Image.open(OUT / (mask_name or f"mask_{bid}.png"))) > 0
    out = src.copy()
    busy_all = cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8))
    how = {"copy": 0, "ns": 0}
    left = []
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        pad = int(3 * max(w, h)) + 12
        x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + w + pad, src.shape[1]), min(y + h + pad, src.shape[0])
        sub = (lab[y0:y1, x0:x1] == i).astype(np.uint8)
        res, kind = fill(out[y0:y1, x0:x1], sub, busy_all[y0:y1, x0:x1])
        how[kind] += 1
        if kind == "ns" and copy_only:
            left.append([int(x), int(y), int(w), int(h)])
            continue
        out[y0:y1, x0:x1] = res
    d = OUT / bid
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(d / dest_name)
    (OUT / f"left_{bid}.json").write_text(json.dumps(left))
    print(bid, "free repair:", n - 1, "spots", how, ("(smooth fills not used)" if copy_only else ""), "->", d / dest_name)


def match_ring(rep, ver, day, m, night):
    """Version pixels for the spot: the repaired day pixels, LAB-matched (mean and spread) to the version on a ring
    1 to 3 m round the spot. Both rings are measured in day and version, so the transfer maps day -> version."""
    k_ring = 4 * 3   # ~3 m at canvas scale (0.85 canvas px per map px, 4 map px per metre)
    ring = (cv2.dilate(m, np.ones((k_ring, k_ring), np.uint8)) > 0) & ~(cv2.dilate(m, np.ones((4, 4), np.uint8)) > 0)
    dl = cv2.cvtColor(day, cv2.COLOR_RGB2LAB).astype(np.float32)
    vl = cv2.cvtColor(ver, cv2.COLOR_RGB2LAB).astype(np.float32)
    rl = cv2.cvtColor(rep, cv2.COLOR_RGB2LAB).astype(np.float32)
    if night:   # street lamps and lit windows in the ring would brighten the spot
        ring &= vl[..., 0] < np.percentile(vl[..., 0][ring], 80) if ring.any() else ring
    if ring.sum() < 20:
        return ver
    out = vl.copy()
    for c in range(3):
        dm, ds = dl[..., c][ring].mean(), dl[..., c][ring].std() + 1e-3
        vm, vs = vl[..., c][ring].mean(), vl[..., c][ring].std() + 1e-3
        out[..., c] = (rl[..., c] - dm) * (vs / ds) + vm
    res = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    soft = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.0)[..., None]
    return (res * soft + ver * (1 - soft)).astype(np.uint8)


def carry(bid, version, rep_path):
    st = state()
    day = np.asarray(Image.open(st["done"][bid]).convert("RGB"))
    ver = np.asarray(Image.open(st["done_v"][version][bid]).convert("RGB"))
    rep = np.asarray(Image.open(rep_path).convert("RGB"))
    changed = (np.abs(rep.astype(int) - day.astype(int)).sum(2) > 0).astype(np.uint8)
    changed = cv2.dilate(changed, np.ones((3, 3), np.uint8))
    out = ver.copy()
    n, lab, stt, _ = cv2.connectedComponentsWithStats(changed)
    for i in range(1, n):
        x, y, w, h, _ = stt[i]
        pad = 16
        x0, y0, x1, y1 = max(x - pad, 0), max(y - pad, 0), min(x + w + pad, day.shape[1]), min(y + h + pad, day.shape[0])
        sub = (lab[y0:y1, x0:x1] == i).astype(np.uint8)
        out[y0:y1, x0:x1] = match_ring(rep[y0:y1, x0:x1], ver[y0:y1, x0:x1], day[y0:y1, x0:x1], sub, "night" in version)
    d = OUT / bid
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"canvas_{version}_repaired.png"
    Image.fromarray(out).save(dest)
    print(bid, version, n - 1, "spots carried ->", dest)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "carry":
        carry(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "lonemasks":   # the painter's mask for the full run: car parks (dense groups) left out
        for bid in blocks(sys.argv[2]):
            lone(bid)
    elif cmd == "freeall":   # every spot filled (copy, or the smooth fallback): the start image for gpu_repair.py --init-from
        for bid in blocks(sys.argv[2]):
            free(bid, dest_name="canvas_day_freeall.png", copy_only=False)
    elif cmd == "gpumasks":   # wider spots for the painter: grown 3 m, groups closed over 8 m
        for bid in blocks(sys.argv[2]):
            masks(bid, 3.0, 8.0, f"mask_{bid}_gpu.png")
    else:
        for bid in blocks(sys.argv[2]):
            {"masks": masks, "free": free}[cmd](bid)
