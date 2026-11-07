"""Event sprites: the moving parts of event rides, drawn as small box models with the map's own camera and ink
(the build_sprites.py renderer), by day and lit at night.

Rides (Christmas first; the same code serves the Schueberfouer later):
  wheel     Ferris wheel of about 32 m: two rims, 24 spokes a side and 24 gondolas that stay upright. It looks the
            same after one gondola step (15 degrees), so 12 frames make the whole loop.
  carousel  8 outer and 8 inner horses on gold poles, rising and falling, under the painted canopy. It repeats
            every 45 degrees: 12 frames.
  pyramid   the 6 fan blades on top of a Christmas pyramid, turning in the warm air: 8 frames over 60 degrees.
The fixed parts (the wheel's A-frame, the carousel's platform and roof, the pyramid's tiers) stay in the painted
event patch; the canopy roof is also cut from the patch as a "front" overlay drawn over the horses (see
cut_fronts in this file), so the horses read as being under it.

Output, in web/public/events/:
  rides.png      one atlas: per ride, a row of day frames and a row of night frames
  sprites.json   per ride: frame size, anchor (sprite px of the ground centre), metres per sprite px, frames, the
                 atlas cell of every day and night frame
  xmas/rides.json  per ride placed on the map: site, kind, ground anchor (map px), frame rate, and the front overlay

Run: pipeline/.venv/bin/python pipeline/events/build_event_sprites.py
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from build_sprites import INK, MPP, MAP_MPP, Renderer, frame_image, triangles  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import patchlib  # noqa: E402

OUT = ROOT / "web/public/events"
R = 0.70710678
LAMP = 901            # part id the renderer leaves unshaded and un-inked
WARM = (255, 214, 140)


# ---- geometry ---------------------------------------------------------------------------------------------------

def beam(p0, p1, w, d, colour, up=(0.0, 0.0, 1.0), part=None):
    """A box from p0 to p1 (world metres), w wide across and d deep; `up` sets which way "across" turns."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    e = p1 - p0
    e /= np.linalg.norm(e)
    v = np.cross(e, up)
    if np.linalg.norm(v) < 1e-6:
        v = np.cross(e, (1.0, 0.0, 0.0))
    v /= np.linalg.norm(v)
    u = np.cross(v, e)
    corners = [p0 + (s * u * w / 2 + t * v * d / 2) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    corners += [p1 + (s * u * w / 2 + t * v * d / 2) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    return np.array(corners, float), colour, part


def cube(c, lx, ly, lz, colour, part=None):
    """Axis-aligned box centred on c (x, y) with its bottom at c[2]."""
    x, y, z = c
    b = [(x - lx / 2, y - ly / 2, z), (x + lx / 2, y - ly / 2, z), (x + lx / 2, y + ly / 2, z), (x - lx / 2, y + ly / 2, z)]
    t = [(p[0], p[1], z + lz) for p in b]
    return np.array(b + t, float), colour, part


# ---- rides ------------------------------------------------------------------------------------------------------

WHITE = (240, 240, 236)
STEEL = (214, 218, 224)
GONDOLA = (206, 38, 40)   # one colour for all: the loop of 12 frames moves each gondola onto the next one


def wheel(theta, hub=26.5, radius=23.0, n=24, g=2.6, axle_yaw=-math.pi / 4):
    """The turning part of a Ferris wheel. Its axle points along `axle_yaw` (world, from east): the default faces
    the wheel to the camera (from the south-east), like the A-frame painted on Place de la Constitution. Sizes
    follow that painting (its hub is about 26 m up), not the real 32 m wheel. g: gondola size, metres."""
    a = np.array([math.cos(axle_yaw), math.sin(axle_yaw), 0.0])       # axle
    h = np.array([-a[1], a[0], 0.0])                                 # in the wheel plane, level
    zc = np.array([0.0, 0.0, 1.0])
    centre = zc * hub
    pt = lambda ang, off=0.0: centre + h * radius * math.cos(ang) + zc * radius * math.sin(ang) + a * off  # noqa: E731
    parts = []
    half = g * 0.75
    for side in (-half, half):
        for i in range(2 * n):
            a0, a1 = theta + 2 * math.pi * i / (2 * n), theta + 2 * math.pi * (i + 1) / (2 * n)
            parts.append(beam(pt(a0, side), pt(a1, side), 0.55, 0.4, WHITE, up=a, part=10))
            m = pt((a0 + a1) / 2, side * 1.2)
            parts.append(cube((m[0], m[1], m[2] - 0.2), 0.4, 0.4, 0.4, WARM, part=LAMP))
        for i in range(n):
            ang = theta + 2 * math.pi * (i + 0.5) / n
            parts.append(beam(centre + a * side * 0.5, pt(ang, side), 0.2, 0.2, STEEL, up=a, part=11))
            for f in (0.3, 0.5, 0.7, 0.88):
                q = centre + (pt(ang, side * 1.15) - centre) * f
                parts.append(cube((q[0], q[1], q[2] - 0.15), 0.3, 0.3, 0.3, WARM, part=LAMP))
    parts.append(beam(centre - a * (half + 0.8), centre + a * (half + 0.8), 2.0, 2.0, STEEL, up=zc, part=12))
    for i in range(n):
        ang = theta + 2 * math.pi * i / n
        p = pt(ang)
        parts.append(beam(p - a * half, p + a * half, 0.25, 0.25, STEEL, up=zc, part=13))    # cross bar
        col = GONDOLA
        top = p - zc * 0.4
        parts.append(cube((top[0], top[1], top[2] - g * 1.25), g, g, g * 1.05, col, part=20 + i))
        parts.append(cube((top[0], top[1], top[2] - g * 0.25), g * 1.12, g * 1.12, g * 0.2, WHITE, part=20 + i))
        parts.append(cube((top[0], top[1], top[2] - g * 0.85), g * 1.03, g * 1.03, g * 0.35, (70, 84, 110), part=60 + i))  # windows
    return parts


HORSE = [(246, 244, 236), (176, 116, 70)]   # outer ring, inner ring
GOLD = (222, 180, 70)


def carousel(theta, radius=10.0, roof=8.0, s=2.4):
    """Horses on poles of a carousel whose platform top is the ground (z = 0) and whose canopy starts `roof` metres
    up, at the size of the painting on the Knuedler (about 20 m across). s: horse scale."""
    parts = [beam((0, 0, 0), (0, 0, roof), 0.9, 0.9, GOLD, part=99)]       # central column
    for ring, r, k in ((0, radius * 0.8, 8), (1, radius * 0.5, 8)):
        for i in range(k):
            ang = theta + 2 * math.pi * (i + 0.5 * ring) / k
            bob = 0.25 * s * math.sin(8 * ang + ring * 1.7)
            c = np.array([r * math.cos(ang), r * math.sin(ang), 0])
            tang = np.array([-math.sin(ang), math.cos(ang), 0])
            parts.append(beam(c, c + [0, 0, roof], 0.12 * s, 0.12 * s, GOLD, part=100 + ring * 10 + i))
            parts.append(cube((c[0], c[1], roof - 0.45), 0.4, 0.4, 0.4, WARM, part=LAMP))       # bulb under the canopy
            body = c + [0, 0, 0.95 * s + bob]
            col = HORSE[ring]   # one colour per ring: the loop moves each horse onto the next one
            pid = 200 + ring * 10 + i
            parts.append(beam(body - tang * 0.6 * s, body + tang * 0.6 * s, 0.38 * s, 0.42 * s, col, part=pid))
            head = body + tang * 0.62 * s + [0, 0, 0.3 * s]
            parts.append(beam(head - [0, 0, 0.25 * s], head + [0, 0, 0.2 * s], 0.26 * s, 0.3 * s, col, up=tuple(tang), part=pid))
            for d in (-0.42, 0.42):
                leg = body + tang * d * s
                parts.append(beam(leg, leg - [0, 0, 0.45 * s], 0.11 * s, 0.13 * s, col, part=pid))
            parts.append(cube((body[0], body[1], body[2] + 0.2 * s), 0.32 * s, 0.32 * s, 0.07 * s, (196, 40, 44), part=pid + 50))
    return parts


WOOD = (150, 98, 52)


def pyramid(theta, radius=4.2, blades=6):
    """The fan on top of a Christmas pyramid: z = 0 is the top of the painted spire."""
    parts = [beam((0, 0, -0.3), (0, 0, 1.0), 0.3, 0.3, WOOD, part=300)]
    for i in range(blades):
        ang = theta + 2 * math.pi * i / blades
        d = np.array([math.cos(ang), math.sin(ang), 0])
        t = np.array([-math.sin(ang), math.cos(ang), 0])
        p0 = np.array([0, 0, 0.9]) + d * 0.3
        p1 = np.array([0, 0, 0.9]) + d * radius
        # pitched blade: a thin wide board
        parts.append(beam(p0, p1, 1.1, 0.08, (232, 196, 120), up=tuple(t * 0.6 + np.array([0, 0, 0.8])), part=310 + i))
    parts.append(cube((0, 0, 0.95), 0.7, 0.7, 0.35, GOLD, part=320))
    return parts


RIDES = {
    # name: (model, frames, step per frame in radians)
    "wheel": (wheel, 12, (2 * math.pi / 24) / 12),
    "carousel": (carousel, 12, (math.pi / 4) / 12),
    "pyramid": (pyramid, 8, (math.pi / 3) / 8),
}


# ---- drawing ----------------------------------------------------------------------------------------------------

def bounds(models):
    from build_sprites import project
    p = np.concatenate([project(np.concatenate([q[0] for q in m])) for m in models])
    pad = 4
    x0, y0 = np.floor(p.min(0)) - pad
    x1, y1 = np.ceil(p.max(0)) + pad
    return int(x1 - x0), int(y1 - y0), int(-x0), int(-y0)


def night_parts(parts):
    """Night colours: bodies dark and blue, lamps bright."""
    out = []
    for v, col, part in parts:
        if part == LAMP or (part is not None and 60 <= part < 100):   # bulbs, and lit gondola windows
            out.append((v, (255, 226, 160) if part == LAMP else (236, 178, 96), LAMP))
        else:
            c = np.array(col, float)
            l = c.mean()
            out.append((v, tuple(int(x) for x in (l * 0.24 + c[0] * 0.08 + 6, l * 0.26 + c[1] * 0.06 + 9, l * 0.36 + c[2] * 0.06 + 22)), part))
    return out


def soften_ink(img: Image.Image, k: float = 0.5) -> Image.Image:
    """The renderer's 1 px ink, made a dark shade of the colour beside it: thin steel stays light and fine instead
    of turning into a black line (the painted map inks light things in a darker tone of themselves too)."""
    a = np.asarray(img).copy()
    ink = (a[..., 3] == 255) & (np.abs(a[..., :3].astype(int) - INK).sum(2) == 0)
    fill = (a[..., 3] == 255) & ~ink
    c = a[..., :3].astype(np.float32) * fill[..., None]
    s = cv2.boxFilter(c, -1, (3, 3), normalize=False)
    n = cv2.boxFilter(fill.astype(np.float32), -1, (3, 3), normalize=False)
    mean = s / np.maximum(n, 1)[..., None]
    a[..., :3][ink] = np.clip(mean[ink] * k, 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def glow(img: Image.Image, warm=(255, 200, 120)) -> Image.Image:
    """Night: a soft warm glow round the lamp pixels, under the frame."""
    a = np.asarray(img).astype(np.float32)
    lamp = ((a[..., 0] > 230) & (a[..., 1] > 200) & (a[..., 3] > 0)).astype(np.float32)
    g = cv2.GaussianBlur(lamp, (0, 0), 3.0) * 1.6
    halo = np.zeros_like(a)
    halo[..., :3] = warm
    halo[..., 3] = np.clip(g, 0, 0.55) * 255
    base = Image.fromarray(halo.astype(np.uint8), "RGBA")
    base.alpha_composite(img)
    return base


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    r = Renderer()
    rows, meta = [], {"mpp": MPP, "map_mpp": MAP_MPP, "note": "per ride, a row of day frames and a row of night frames", "rides": {}}
    for name, (fn, n, step) in RIDES.items():
        models = [fn(i * step) for i in range(n)]
        w, h, ax, ay = bounds(models)
        day, night = [], []
        for parts in models:
            day.append(soften_ink(frame_image(r, triangles(parts), w, h, ax, ay), 0.72))
            night.append(glow(soften_ink(frame_image(r, triangles(night_parts(parts)), w, h, ax, ay), 0.6)))
        rows.append((name, w, h, ax, ay, day, night))
    W = max(w * len(d) for _, w, _, _, _, d, _ in rows)
    H = sum(2 * h for _, _, h, _, _, _, _ in rows)
    atlas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = 0
    for name, w, h, ax, ay, day, night in rows:
        cells, ncells = [], []
        for i, (d, nt) in enumerate(zip(day, night)):
            atlas.paste(d, (i * w, y)); cells.append([i * w, y])
            atlas.paste(nt, (i * w, y + h)); ncells.append([i * w, y + h])
        meta["rides"][name] = {"frame": [w, h], "anchor": [ax, ay], "frames": len(day), "day": cells, "night": ncells}
        print(f"{name}: frame {w}x{h}, anchor ({ax}, {ay}), {len(day)} frames")
        y += 2 * h
    path = OUT / "rides.png"
    atlas.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)
    meta["image"] = "rides.png"
    (OUT / "sprites.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f"atlas {atlas.size}, {path.stat().st_size // 1024} KB")


# ---- placing the rides on the Christmas patches -----------------------------------------------------------------

# Ground anchors placed by eye on the Christmas patches (map px; the contact sheet from xmas_v2.py composite and
# the shots b-rides-* show them). wheel: the foot of the painted A-frame, under its hub; carousel: the centre of the
# platform's top; pyramid: the tip of the painted spire.
XMAS = OUT / "xmas"
PLACED = [
    {"site": "constitution", "kind": "wheel", "at": (6918, 6146), "fps": 1.0},     # 12 frames per 15 degrees: 1.25 rpm, cross-faded between frames
    {"site": "knuedler", "kind": "carousel", "at": (7961, 6171), "fps": 6.0,       # 12 frames per 45 degrees: 3.75 rpm
     "front": {"apex": (7961, 6102), "rim": (7961, 6134, 50, 11)}},
    {"site": "constitution", "kind": "pyramid", "at": (7159.5, 6138), "fps": 6.0},  # 8 frames per 60 degrees: 7.5 rpm
]


def cut_front(e: dict, spec: dict) -> dict:
    """The painted canopy roof, cut from the day and night patches of site entry `e`, drawn over the horses."""
    cx, cy, rx, ry = spec["rim"]
    ax, ay = spec["apex"]
    t = np.linspace(0, 2 * np.pi, 72)
    pts = np.stack([cx + rx * np.cos(t), cy + ry * np.sin(t)], 1).tolist() + [[ax, ay]]
    pts = (np.array(pts, np.float64) - [e["x0"], e["y0"]]).astype(np.float32)
    hull = cv2.convexHull(pts).astype(np.int32)
    bx0, by0 = int(cx - rx - 3 - e["x0"]), int(ay - 6 - e["y0"])
    bx1, by1 = int(cx + rx + 3 - e["x0"]), int(cy + ry + 3 - e["y0"])
    out = {"x0": e["x0"] + bx0, "y0": e["y0"] + by0, "w": bx1 - bx0, "h": by1 - by0}
    for when in ("day", "night"):
        p = np.asarray(Image.open(XMAS / f"{e['site']}_{when}.webp").convert("RGBA")).copy()
        m = np.zeros(p.shape[:2], np.uint8)
        cv2.fillPoly(m, [hull], 255)
        m = cv2.GaussianBlur(m, (0, 0), 0.6)
        p[..., 3] = (p[..., 3].astype(np.float32) * m / 255).astype(np.uint8)
        name = f"{e['site']}_front_{when}.webp"
        Image.fromarray(p[by0:by1, bx0:bx1], "RGBA").save(XMAS / name, lossless=True)
        out[when] = name
    return out


def find_lights(e: dict, max_pts: int = 160) -> list:
    """Warm points of light the market added in a night patch: small bright warm peaks (bulbs, lamps) where the
    patch differs from the map, in map px with a size."""
    rgb = np.asarray(Image.open(XMAS / f"{e['site']}_night.webp").convert("RGB")).astype(np.float32)
    base = patchlib.tiles_crop("winter_night", e["x0"], e["y0"], e["w"], e["h"])
    changed = np.ones(rgb.shape[:2], bool) if base is None else np.abs(rgb - base).mean(2) > 6
    lum = rgb @ np.array([0.3, 0.55, 0.15], np.float32)
    warm = (rgb[..., 0] - rgb[..., 2] > 60) & changed
    peak = (lum >= cv2.dilate(lum, np.ones((7, 7), np.uint8))) & (lum > 200) & warm
    bg = cv2.blur(lum, (9, 9))
    peak &= (lum - bg) > 22          # a bulb, not a lit wall
    ys, xs = np.nonzero(peak)
    order = np.argsort(-(lum - bg)[ys, xs])[:max_pts]
    return [[int(e["x0"] + xs[i]), int(e["y0"] + ys[i]), round(float(1.0 + (lum - bg)[ys[i], xs[i]] / 60), 1)] for i in order]


def place():
    sites = {e["site"]: e for e in json.loads((XMAS / "xmas.json").read_text())}
    rides = []
    for r in PLACED:
        e = {"site": r["site"], "kind": r["kind"], "x": r["at"][0], "y": r["at"][1], "fps": r["fps"]}
        if "front" in r:
            e["front"] = cut_front(sites[r["site"]], r["front"])
        rides.append(e)
    (XMAS / "rides.json").write_text(json.dumps(rides, indent=1))
    lights = []
    for site, s in sites.items():
        pts = find_lights(s)
        lights.append({"site": site, "pts": pts})
        print(site, len(pts), "lights")
    (XMAS / "lights.json").write_text(json.dumps(lights, separators=(",", ":")))
    print("placed", len(rides), "rides")


if __name__ == "__main__":
    build()
    place()
