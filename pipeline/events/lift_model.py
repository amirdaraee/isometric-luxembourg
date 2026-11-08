"""The Pfaffenthal Panoramic Lift (PLAN_NEXT item 6): a clean box model of the tower, the empty glass shaft, the
footbridge and the glass end platform, in the map's own camera, used for three things:

  lift_model.py inputs     the painter's inputs for a repaint of the lift's surroundings (block b00):
                           data/work/lift/src.png (the 3D render with the model drawn in and the old, draped
                           footbridge taken out), layout.png, known.png (the day canvas), keep.png (white = keep),
                           and a preview sheet. The repaint itself runs with pipeline/repair/gpu_repair.py
                           --src-override (Modal, capped).
  lift_model.py sprites    the live cabin, by day and lit at night, the parts of the shaft frame in front of it
                           (drawn over the cabin so it reads as inside the shaft), and the whole structure (drawn
                           live while the base art lacks it, "structure" in lift.json): web/public/events/lift.png and
                           web/public/events/lift.json (sprite cells, the cabin's ground anchor and travel in map px,
                           timing and opening hours).

Facts (research/01-landmarks/README.md, Pfaffenthal lift): opened 22 July 2016; one cabin, 2.3 m wide and 3.7 m
deep, glass on its face, sides, floor and roof; a 2.6 m square concrete core holding the counterweight; 60 m rise
in about 30 s (2.5 m/s at most); the roof of the tower 74.77 m up; an enclosed steel through-truss footbridge
72 m long, 3 m wide and 3 m tall, from the Pescatore park to the tower and 9 m beyond it, ending in a glass-walled
viewing platform with a small glass floor. Open daily 05:45 to 01:00.
Positions: OpenStreetMap way 347619032 (the footbridge: park end, the tower node, the platform end) and the
bottom door (way 433292708).
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from common import ELEV, ORIGIN_E, ORIGIN_N, R, WORK, lonlat_to_en  # noqa: E402
import build_sprites as bs  # noqa: E402
from build_sprites import MPP, Renderer, frame_image, triangles  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from build_event_sprites import LAMP, beam, bounds, cube, glow, soften_ink  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
OUT = WORK / "lift"
WEB = ROOT / "web/public/events"
BLOCK = "b00"
# footbridge, from OSM way 347619032
PARK = (49.615349, 6.129745)
TOWER = (49.615564, 6.130541)
END = (49.615592, 6.130647)
DOOR = (49.615537, 6.130560)     # the bottom door, on the south side of the core
RISE = 60.0                      # metres, bottom door to the footbridge
ROOF = 74.77                     # tower roof above the bottom
CROP = (8560, 4720, 1200, 1200)  # map px: the repaint crop round the lift (x0, y0, w, h)

CONCRETE = (206, 200, 188)
STEEL = (92, 100, 112)           # the truss and the shaft frame: dark grey steel
LIGHT_STEEL = (196, 202, 210)
GLASS = (168, 190, 204)          # glass as a light blue-grey tint
DECK = (120, 116, 110)
CABIN_GLASS = (58, 96, 124)       # darker than the shaft glass, so the cabin reads inside it
CABIN_FRAME = (226, 228, 230)


def mosaic():
    m = json.loads((WORK / "mosaic.json").read_text())
    t = np.load(WORK / "terrain.npz")
    return m, t


M, T = mosaic()


def ground(e, n):
    tz, te0, tn0, ts = T["z"], float(T["e0"]), float(T["n0"]), float(T["step"])
    iy = min(max(int((n - tn0) / ts), 0), tz.shape[0] - 1)
    ix = min(max(int((e - te0) / ts), 0), tz.shape[1] - 1)
    return float(tz[iy, ix])


def to_px(e, n, z):
    """World metres to map px (as project_lines.py)."""
    le, ln = e - ORIGIN_E, n - ORIGIN_N
    sx = (le + ln) * R
    sy = (-le + ln) * R * math.sin(ELEV) + z * math.cos(ELEV)
    return (sx - M["sx0"]) / M["mpp"], (M["sy1"] - sy) / M["mpp"]


def en(p):
    return np.array(lonlat_to_en(p[1], p[0]))


def frame():
    """Local frame: origin at the tower's centre at the bottom door's level; u along the footbridge (park to
    platform), v across it (to its left)."""
    park, tower, end, door = en(PARK), en(TOWER), en(END), en(DOOR)
    deck = ground(*park) + 0.4                         # the footbridge leaves the park at ground level
    z0 = deck - RISE
    u = (end - park) / np.linalg.norm(end - park)
    v = np.array([-u[1], u[0]])
    return dict(park=park, tower=tower, end=end, door=door, deck=deck, z0=z0, u=u, v=v)


F = frame()


def P(a, b, z):
    """A point a metres along the footbridge and b across it from the tower centre, z above the bottom, as world
    (E, N, z) relative to the tower centre at the bottom."""
    q = F["u"] * a + F["v"] * b
    return (float(q[0]), float(q[1]), float(z))


def model(shaft_front=False):
    """Parts of the lift. shaft_front: only the shaft frame parts that stand in front of the cabin (seen from the
    camera, south-east), for the overlay over the live cabin."""
    parts = []
    dl = F["deck"] - F["z0"]                 # deck height above the bottom (60 m)
    # the shaft sits on the side of the core towards the bottom door
    sd = F["door"] - F["tower"]
    sd = sd / np.linalg.norm(sd)
    sw, sdp = 3.0, 4.3                        # shaft outside, across and deep
    sc = sd * (1.3 + sdp / 2)                 # shaft centre (from the core's centre)
    sa = np.array([-sd[1], sd[0]])            # across the shaft
    corners = [sc + sa * s * sw / 2 + sd * t * sdp / 2 for s in (-1, 1) for t in (-1, 1)]
    front = lambda c: (c[0] - c[1]) > (sc[0] - sc[1]) - 0.01   # nearer the camera (south-east): x - y larger  # noqa: E731
    top = dl + 4.0
    if not shaft_front:
        # concrete core, from below the bottom (the slope) to the roof
        parts.append(cube((0.0, 0.0, -6.0), 2.6, 2.6, ROOF + 6.0, CONCRETE, part=1))
        parts.append(cube((0.0, 0.0, ROOF - 0.6), 3.2, 3.2, 0.6, LIGHT_STEEL, part=2))     # roof cap
        # machine room / head of the shaft over the footbridge
        parts.append(cube((sc[0], sc[1], top), sw + 0.4, sdp + 0.4, 3.0, LIGHT_STEEL, part=3))
        # footbridge: deck, two side trusses (top and bottom chords, posts, diagonals), roof, glass walls
        a0 = -float(np.dot(F["tower"] - F["park"], F["u"]))      # park end (negative: behind the tower)
        a1 = float(np.dot(F["end"] - F["tower"], F["u"])) + 1.0  # platform end, 9 m past the tower
        z = dl
        parts.append(beam(P(a0, 0, z - 0.4), P(a1, 0, z - 0.4), 3.2, 0.6, DECK, up=(0, 0, 1), part=10))
        for side in (-1.5, 1.5):
            parts.append(beam(P(a0, side, z), P(a1, side, z), 0.3, 0.3, STEEL, part=11))
            parts.append(beam(P(a0, side, z + 3.0), P(a1, side, z + 3.0), 0.3, 0.3, STEEL, part=11))
            n = int((a1 - a0) / 3.6)
            for i in range(n + 1):
                a = a0 + (a1 - a0) * i / n
                parts.append(beam(P(a, side, z), P(a, side, z + 3.0), 0.22, 0.22, STEEL, part=12))
                if i < n:
                    b = a0 + (a1 - a0) * (i + 1) / n
                    p0, p1 = (P(a, side, z), P(b, side, z + 3.0)) if i % 2 == 0 else (P(a, side, z + 3.0), P(b, side, z))
                    parts.append(beam(p0, p1, 0.16, 0.16, STEEL, part=13))
        parts.append(beam(P(a0, 0, z + 3.1), P(a1 - 9.0, 0, z + 3.1), 3.1, 0.15, LIGHT_STEEL, up=(0, 0, 1), part=14))
        # glass walls of the footbridge (thin panes just inside the trusses) and the glass end platform
        for side in (-1.35, 1.35):
            parts.append(beam(P(a0, side, z + 1.5), P(a1, side, z + 1.5), 2.8, 0.05, GLASS, up=(0, 0, 1), part=15))
        parts.append(beam(P(a1 - 9.0, 0, z + 3.1), P(a1, 0, z + 3.1), 3.1, 0.15, GLASS, up=(0, 0, 1), part=16))
        parts.append(beam(P(a1 - 0.05, -1.5, z + 1.5), P(a1 - 0.05, 1.5, z + 1.5), 2.9, 0.08, GLASS, up=(0, 0, 1), part=16))
    # shaft frame: four corner posts, a ring every 4 m, and slim glass mullions; only the front ones for the overlay
    for c in corners:
        if shaft_front and not front(c):
            continue
        parts.append(beam((c[0], c[1], -1.0), (c[0], c[1], top), 0.35, 0.35, STEEL, part=20))
    for zz in np.arange(0.0, top + 0.1, 4.0):
        for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
            c0, c1 = corners[i], corners[j]
            if shaft_front and not (front(c0) and front(c1)):
                continue
            parts.append(beam((c0[0], c0[1], zz), (c1[0], c1[1], zz), 0.2, 0.2, STEEL, part=21))
    if not shaft_front:
        # back panes of the shaft: glass behind the cabin
        for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
            c0, c1 = corners[i], corners[j]
            if front(c0) and front(c1):
                continue
            mid0 = (c0 + c1) / 2
            parts.append(beam((mid0[0], mid0[1], -1.0), (mid0[0], mid0[1], top), 0.06, float(np.linalg.norm(c1 - c0)),
                              GLASS, up=(float((c1 - c0)[0]), float((c1 - c0)[1]), 0.0), part=22))
    return parts, dict(shaft_centre=sc, across=sa, depth_dir=sd, top=top)


def cabin(lit=False):
    """The cabin, at the bottom of its travel, in the shaft frame (origin at the shaft centre, bottom)."""
    _, info = model()
    sa, sd = info["across"], info["depth_dir"]
    parts = []
    w, d, h = 2.3, 3.7, 2.9
    glass = (255, 222, 160) if lit else CABIN_GLASS
    part_glass = LAMP if lit else 30
    # floor and roof plates, four slim corner posts, and glass all round
    c = np.zeros(2)
    corners = [c + sa * s * w / 2 + sd * t * d / 2 for s in (-1, 1) for t in (-1, 1)]
    parts.append(beam((0, 0, 0), (0, 0, 0.3), w, d, CABIN_FRAME, up=(float(sa[0]), float(sa[1]), 0.0), part=31))
    parts.append(beam((0, 0, h - 0.3), (0, 0, h), w, d, CABIN_FRAME, up=(float(sa[0]), float(sa[1]), 0.0), part=31))
    parts.append(beam((0, 0, 0.3), (0, 0, h - 0.3), w - 0.1, d - 0.1, glass, up=(float(sa[0]), float(sa[1]), 0.0), part=part_glass))
    for q in corners:
        parts.append(beam((q[0], q[1], 0.0), (q[0], q[1], h), 0.18, 0.18, CABIN_FRAME, part=32))
    return parts


class WideRenderer(Renderer):
    """The rides' renderer with a deeper depth range (the lift is 75 m tall and the footbridge 72 m long)."""

    def raster(self, tris, w, h, ax, ay):
        self.prog["dr"].value = (-200.0, 200.0)
        fbo = self._fbo(w, h)
        fbo.use()
        fbo.clear(0, 0, 0, -1, depth=1.0)
        self.ctx.enable(bs.moderngl.DEPTH_TEST)
        self.prog["frame"].value = (-ax * MPP, -(h - ay) * MPP, (w - ax) * MPP, ay * MPP)
        buf = self.ctx.buffer(tris.tobytes())
        vao = self.ctx.vertex_array(self.prog, [(buf, "3f 3f 3f 1f", "p", "col", "nrm", "part")])
        vao.render(bs.moderngl.TRIANGLES)
        vao.release(); buf.release()
        a = np.frombuffer(self.t0.read(), np.float32).reshape(h, w, 4)[::-1]
        b = np.frombuffer(self.t1.read(), np.float32).reshape(h, w, 4)[::-1]
        return a, b


def render(parts, pad=6):
    """Render parts (local metres, origin at the tower centre at the bottom) to an RGBA image at map scale, with
    the map px of its top-left corner."""
    w, h, ax, ay = bounds([parts])
    img = soften_ink(frame_image(WideRenderer(), triangles(parts), w, h, ax, ay), 0.6)
    # to map scale (sprites are drawn at twice the map's resolution)
    small = img.resize((w // 2, h // 2), Image.LANCZOS)
    t = F["tower"]
    ox, oy = to_px(t[0], t[1], F["z0"])
    return small, (ox - ax / 2, oy - ay / 2), img, (ax, ay)


def inputs():
    OUT.mkdir(parents=True, exist_ok=True)
    st = json.loads((WORK / "city/blocks.json").read_text())
    b = next(x for x in st["blocks"] if x["id"] == BLOCK)
    x0, y0, w, h = CROP
    rx0, ry0 = x0 - b["x0"], y0 - b["y0"]
    tiles = Path("/Users/amirdaraee/00/projects/isometric-luxembourg/pipeline/gpu_train/tiles")
    src_p = WORK / "city" / BLOCK / "src.png"
    if not src_p.exists():
        src_p, lay_p = tiles / "src_showcase_hint.png", tiles / "layout_showcase.png"
    else:
        lay_p = WORK / "city" / BLOCK / "layout.png"
    src = np.asarray(Image.open(src_p).convert("RGB").crop((rx0, ry0, rx0 + w, ry0 + h))).copy()
    lay = Image.open(lay_p).convert("RGB").crop((rx0, ry0, rx0 + w, ry0 + h))
    parts, _ = model()
    img, (mx, my), _, _ = render(parts)
    a = np.asarray(img).astype(np.float32) / 255
    px, py = int(round(mx - x0)), int(round(my - y0))
    hh, ww = a.shape[:2]
    sil = np.zeros((h, w), np.uint8)
    sil[py:py + hh, px:px + ww] = (a[..., 3] > 0.05).astype(np.uint8) * 255
    # the old footbridge, draped down the slope in the 3D render (it came from the orthophoto): a band along the
    # ground line from the park to below the platform, and the "glass wall" the painter made of it
    old = np.zeros((h, w), np.uint8)
    park, end = F["park"], F["end"]
    pts = []
    for s in np.linspace(0, 1, 40):
        e, n = park + (end - park) * s
        qx, qy = to_px(e, n, ground(e, n))
        pts.append((int(qx - x0), int(qy - y0)))
    cv2.polylines(old, [np.array(pts, np.int32)], False, 255, thickness=int(7 / 0.25))
    # the wall the painter drew under the platform's end, down to the valley floor
    ex, ey = to_px(end[0], end[1], F["deck"])
    bx, by = to_px(end[0], end[1], F["z0"])
    cv2.line(old, (int(ex - x0), int(ey - y0)), (int(bx - x0), int(by - y0)), 255, int(14 / 0.25))
    # empty the old footbridge in the render: fill it from the trees round it
    fillm = cv2.dilate(old, np.ones((5, 5), np.uint8))
    src_f = cv2.inpaint(src, fillm, 9, cv2.INPAINT_TELEA)
    noise = (np.random.default_rng(7).normal(0, 12, src.shape)).astype(np.float32)
    src_f = np.where(fillm[..., None] > 0, np.clip(src_f.astype(np.float32) + noise * 0.6, 0, 255), src_f).astype(np.uint8)
    # the model over it
    out = src_f.astype(np.float32)
    region = out[py:py + hh, px:px + ww]
    region[:] = region * (1 - a[..., 3:4]) + a[..., :3] * 255 * a[..., 3:4]
    Image.fromarray(out.astype(np.uint8)).save(OUT / "src.png")
    lay.save(OUT / "layout.png")
    canvas = Image.open(st["done"][BLOCK]).convert("RGB")
    k = canvas.width / b["w"]
    cbox = tuple(int(round(v * k)) for v in (rx0, ry0, rx0 + w, ry0 + h))
    known = canvas.crop(cbox)
    known.save(OUT / "known.png")
    rep = cv2.dilate(np.maximum(sil, old), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(2 * 6 / 0.25) | 1,) * 2))
    rep_c = cv2.resize(rep, known.size, interpolation=cv2.INTER_NEAREST)
    Image.fromarray(np.where(rep_c > 0, 0, 255).astype(np.uint8)).save(OUT / "keep.png")
    # the repaint mask at block canvas scale (white = repaint), for gpu_repair.py --mask
    full = np.zeros((canvas.height, canvas.width), np.uint8)
    full[cbox[1]:cbox[1] + rep_c.shape[0], cbox[0]:cbox[0] + rep_c.shape[1]] = rep_c
    Image.fromarray(full).save(OUT / "mask_b00.png")
    sheet = np.hstack([src, np.asarray(Image.open(OUT / "src.png")), np.asarray(known.resize((w, h)))])
    Image.fromarray(sheet).resize((sheet.shape[1] // 2, sheet.shape[0] // 2)).save(OUT / "inputs_sheet.jpg", quality=88)
    print("inputs ->", OUT, f"(repaint {(rep > 0).mean() * 100:.1f}% of the crop)")


# ---- live cabin -------------------------------------------------------------------------------------------------

def sprites():
    """The cabin by day and lit at night, and the shaft frame in front of it, at sprite scale (0.125 m/px)."""
    _, info = model()
    sc = info["shaft_centre"]
    cab_d = [(v + np.array([sc[0], sc[1], 0.0]), c, p) for v, c, p in cabin(False)]
    cab_n = [(v + np.array([sc[0], sc[1], 0.0]), c, p) for v, c, p in cabin(True)]
    front, _ = model(shaft_front=True)
    r = WideRenderer()
    # the cabin, anchored at its own bottom centre
    w, h, ax, ay = bounds([cab_d])
    shift = lambda parts: [(v - np.array([sc[0], sc[1], 0.0]), c, p) for v, c, p in parts]  # noqa: E731
    day = soften_ink(frame_image(r, triangles(shift(cab_d)), w, h, ax, ay), 0.72)
    night = glow(soften_ink(frame_image(r, triangles(shift(cab_n)), w, h, ax, ay), 0.6))
    # the front frame, anchored at the shaft centre at the bottom
    fw, fh, fax, fay = bounds([shift(front)])
    fr = soften_ink(frame_image(r, triangles(shift(front)), fw, fh, fax, fay), 0.6)
    frn = Image.fromarray(np.dstack([(np.asarray(fr)[..., :3] * np.array([0.3, 0.33, 0.45])).astype(np.uint8), np.asarray(fr)[..., 3]]), "RGBA")
    # the whole structure (tower, shaft, footbridge and platform), drawn live until the art is repainted with it
    tower, _ = model()
    tw, th, tax, tay = bounds([shift(tower)])
    tr = soften_ink(frame_image(r, triangles(shift(tower)), tw, th, tax, tay), 0.6)
    ta = np.asarray(tr).astype(np.float32)
    trn = ta.copy()
    trn[..., :3] = ta[..., :3] * np.array([0.26, 0.29, 0.42])
    glass = (np.abs(ta[..., :3] - np.array(GLASS)).sum(2) < 40) & (ta[..., 3] > 0)   # the footbridge glass glows warm at night
    trn[glass, :3] = trn[glass, :3] * 0.4 + np.array([255, 200, 120]) * 0.6
    trn = Image.fromarray(trn.clip(0, 255).astype(np.uint8), "RGBA")
    W = max(2 * w, 2 * fw, 2 * tw)
    atlas = Image.new("RGBA", (W, h + fh + th), (0, 0, 0, 0))
    atlas.paste(day, (0, 0)); atlas.paste(night, (w, 0))
    atlas.paste(fr, (0, h)); atlas.paste(frn, (fw, h))
    atlas.paste(tr, (0, h + fh)); atlas.paste(trn, (tw, h + fh))
    atlas.save(WEB / "lift.png", optimize=True)
    t = F["tower"]
    bx, by = to_px(t[0] + sc[0], t[1] + sc[1], F["z0"])
    rise_px = RISE * math.cos(ELEV) / M["mpp"]
    meta = {
        "note": "Pfaffenthal Panoramic Lift: one cabin running up and down its shaft (pipeline/events/lift_model.py)",
        "image": "lift.png", "mpp": MPP, "map_mpp": M["mpp"],
        "cabin": {"frame": [w, h], "anchor": [ax, ay], "day": [0, 0], "night": [w, 0]},
        "front": {"frame": [fw, fh], "anchor": [fax, fay], "day": [0, h], "night": [fw, h]},
        "tower": {"frame": [tw, th], "anchor": [tax, tay], "day": [0, h + fh], "night": [tw, h + fh]},
        # the base art has no tower yet (the painter made a wall of the old footbridge): draw the modelled
        # structure live until the repaint (PLAN_NEXT item 6, step 4) is in, then set this to false
        "structure": True,
        "bottom": [round(bx, 1), round(by, 1)],      # map px of the cabin's bottom centre at the lower stop
        "rise": round(rise_px, 1),                   # map px up to the upper stop (60 m)
        "ride": 30, "wait": [25, 35],                # seconds: the ride, and the stop at the bottom and at the top
        "hours": [5.75, 25.0],                       # 05:45 to 01:00 next day; outside them the cabin waits at the bottom
    }
    (WEB / "lift.json").write_text(json.dumps(meta, indent=1))
    print(f"cabin {w}x{h}, front {fw}x{fh}; bottom {meta['bottom']}, rise {meta['rise']} px; {(WEB / 'lift.png').stat().st_size // 1024} KB")


if __name__ == "__main__":
    {"inputs": inputs, "sprites": sprites}[sys.argv[1]]()
