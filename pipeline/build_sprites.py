"""Vehicle sprites: small box models rendered with the map's own projection at 32 screen headings.

Each vehicle is a handful of boxes (body, glass band, roof, wheels, lights) in its own frame: x forward, y to the
left, z up, metres, origin at the ground centre. For every heading the model is turned to the world yaw that
appears on screen at that heading, drawn orthographically with exactly the camera of render.py (from the south-east,
30 degrees up), shaded flat by face normal, inked with a 1 px dark line and laid on a soft ground shadow cast from
the upper left of the screen, like the painted map.

Output, in web/public/sprites/:
  <type>.png     one atlas per vehicle type: for each colour variant 4 rows of 8 headings
  sprites.json   per type: frame size, anchor (sprite px of the ground centre), length in metres, the screen
                 heading and atlas cell of every frame, and the colour variants

Colour variants are rendered out in full (no tinting at run time), so outlines and shading stay right.

Run: pipeline/.venv/bin/python pipeline/build_sprites.py [--out DIR]
"""
import argparse
import json
import math
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image, ImageFilter

MPP = 0.125          # metres per sprite pixel: twice the map's resolution, so sprites stay sharp zoomed in
MAP_MPP = 0.25       # metres per map pixel
HEADINGS = 32
COLS = 8             # atlas columns; each variant takes HEADINGS / COLS rows
R = 0.70710678
SE, CE = 0.5, 0.8660254

# Sun from the upper left of the screen (world west, a little north), as in the painted map. Unit vector towards it.
SUN = np.array([-0.85, 0.3, 0.75])
SUN /= np.linalg.norm(SUN)
SHADOW_RGBA = (18, 20, 34, 105)
INK = (24, 22, 28)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "public" / "sprites"


# ---- geometry ---------------------------------------------------------------------------------------------------

def hexa(x0, x1, y0, y1, z0, z1, colour, front=0.0, back=0.0, side=0.0, part=None):
    """A box from x0..x1, y0..y1, z0..z1, its top face pulled in by `front` at +x, `back` at -x and `side` on both
    sides (windscreens, noses, rounded roofs). Returns (8 corners, colour, part id)."""
    b = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
    t = [(x0 + back, y0 + side, z1), (x1 - front, y0 + side, z1), (x1 - front, y1 - side, z1), (x0 + back, y1 - side, z1)]
    return np.array(b + t, float), colour, part


def box(cx, cy, cz0, lx, ly, lz, colour, **kw):
    """Box centred on (cx, cy) along the ground, from height cz0 up by lz."""
    return hexa(cx - lx / 2, cx + lx / 2, cy - ly / 2, cy + ly / 2, cz0, cz0 + lz, colour, **kw)


FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]  # bottom, top, sides


def triangles(parts):
    """Flat-shaded triangles: rows of x y z  r g b  nx ny nz  part."""
    rows = []
    for k, (v, col, part) in enumerate(parts):
        pid = float(k if part is None else part)
        c = np.array(col, float) / 255
        centre = v.mean(axis=0)
        for f in FACES:
            q = v[list(f)]
            n = np.cross(q[1] - q[0], q[2] - q[0])
            if np.linalg.norm(n) < 1e-9:
                n = np.cross(q[2] - q[0], q[3] - q[0])
            ln = np.linalg.norm(n)
            if ln < 1e-9:
                continue  # degenerate face (fully pulled-in top)
            n /= ln
            if np.dot(n, q.mean(axis=0) - centre) < 0:
                n = -n
            for tri in ((0, 1, 2), (0, 2, 3)):
                for i in tri:
                    rows.append([*q[i], *c, *n, pid])
    return np.array(rows, np.float32)


def wheels(xs, half_track, d=0.62, w=0.24, colour=(34, 34, 38)):
    return [box(x, s * half_track, 0.0, d, w, d, colour, part=900) for x in xs for s in (-1, 1)]


# ---- models -----------------------------------------------------------------------------------------------------

GLASS = (58, 74, 96)
GLASS_LIT = (84, 104, 128)
HEAD = (255, 244, 205)
TAIL = (205, 30, 34)
DARK = (44, 44, 50)


def car(body):
    roof = tuple(int(c * 0.95) for c in body)
    return [
        *wheels((-1.38, 1.38), 0.78),
        hexa(-2.2, 2.2, -0.9, 0.9, 0.28, 0.98, body, front=0.25, back=0.08),              # lower body, sloped bonnet
        hexa(-1.45, 0.85, -0.82, 0.82, 0.98, 1.42, GLASS, front=0.55, back=0.32, side=0.08),  # glass band
        hexa(-1.13, 0.3, -0.74, 0.74, 1.42, 1.5, roof),                                     # roof
        box(2.19, 0.6, 0.7, 0.04, 0.32, 0.13, HEAD, part=901), box(2.19, -0.6, 0.7, 0.04, 0.32, 0.13, HEAD, part=901),
        box(-2.19, 0.62, 0.74, 0.04, 0.3, 0.12, TAIL, part=902), box(-2.19, -0.62, 0.74, 0.04, 0.3, 0.12, TAIL, part=902),
    ]


def van(body):
    return [
        *wheels((-1.85, 1.75), 0.86, d=0.68),
        hexa(-2.75, 2.75, -1.0, 1.0, 0.32, 1.12, body, front=0.12),                       # lower body
        hexa(-2.75, 1.25, -1.0, 1.0, 1.12, 2.3, body, side=0.04),                          # load box
        hexa(1.25, 2.55, -0.97, 0.97, 1.12, 2.12, GLASS, front=0.7, side=0.06),            # cab glass
        hexa(1.25, 1.85, -0.92, 0.92, 2.12, 2.24, body),                                   # cab roof
        box(2.74, 0.68, 0.82, 0.04, 0.34, 0.16, HEAD, part=901), box(2.74, -0.68, 0.82, 0.04, 0.34, 0.16, HEAD, part=901),
        box(-2.74, 0.82, 0.8, 0.04, 0.22, 0.4, TAIL, part=902), box(-2.74, -0.82, 0.8, 0.04, 0.22, 0.4, TAIL, part=902),
    ]


WHITE = (238, 238, 232)


def bus(livery):
    p = [*wheels((-3.0, 3.6), 1.06, d=0.95, w=0.3),
         box(0, 0, 0.32, 12.0, 2.55, 0.78, livery),                                      # coloured lower body
         box(0, 0, 1.1, 12.0, 2.5, 1.5, GLASS),                                          # window band
         hexa(-6.0, 6.0, -1.275, 1.275, 2.6, 3.0, WHITE, side=0.08, front=0.05),         # white roof
         box(-1.0, 0, 3.0, 3.2, 1.7, 0.18, (196, 200, 204))]                             # roof air-conditioning
    for x in (-4.6, -2.3, 0.0, 2.3):                                                     # window pillars
        for s in (-1, 1):
            p.append(box(x, s * 1.255, 1.1, 0.16, 0.06, 1.5, WHITE, part=903))
    p.append(box(5.995, 0, 1.0, 0.04, 2.3, 0.12, livery, part=904))                     # band under windscreen
    p += [box(5.99, s * 0.95, 0.55, 0.04, 0.34, 0.14, HEAD, part=901) for s in (-1, 1)]
    p += [box(-5.99, s * 1.0, 0.55, 0.04, 0.3, 0.3, TAIL, part=902) for s in (-1, 1)]
    return p


TRAM_BODY = (232, 234, 236)
TRAM_SILVER = (214, 218, 224)
TURQ = (0, 166, 190)


def tram(end):
    """One 9 m section of a Luxtram CAF Urbos (five make a tram). `end`: a cab section, nose at +x."""
    L, W = 9.0, 2.65
    x0, x1 = -L / 2, L / 2
    nose = 1.3 if end else 0.0
    p = [box(0, 0, 0.12, L - 1.0, W - 0.5, 0.25, DARK, part=905),                       # skirted bogie
         hexa(x0, x1, -W / 2, W / 2, 0.36, 1.02, TRAM_BODY, front=0.25 if end else 0.0),  # lower body
         box(0, 0, 0.36, L, W + 0.02, 0.16, TURQ, part=906),                              # turquoise skirt line
         box(-nose / 2, 0, 1.02, L - nose, W, 1.58, TRAM_BODY),                           # white upper body
         hexa(x0, x1 - nose * 0.6, -W / 2, W / 2, 2.6, 3.2, TRAM_SILVER, side=0.12, front=0.35 if end else 0.0)]
    # windows between the doors, on both sides
    doors = (-L / 4, L / 4)
    spans = [(x0 + 0.25, doors[0] - 0.8), (doors[0] + 0.8, doors[1] - 0.8), (doors[1] + 0.8, x1 - nose - 0.25)]
    for a, b in spans:
        for s in (-1, 1):
            p.append(box((a + b) / 2, s * (W / 2 + 0.01), 1.18, b - a, 0.04, 1.22, GLASS, part=920))
    for x in doors:                                                                       # doors, turquoise glass
        for s in (-1, 1):
            p.append(box(x, s * (W / 2 + 0.015), 0.52, 1.3, 0.05, 1.95, TURQ, part=907))
    if end:
        # tapered nose: wrap-round windscreen, turquoise mask under it
        p.append(hexa(x1 - nose, x1 - 0.25, -W / 2 + 0.02, W / 2 - 0.02, 1.02, 2.6, GLASS, front=0.55, part=913))
        p.append(hexa(x1 - 0.6, x1 - 0.05, -W / 2 + 0.05, W / 2 - 0.05, 0.62, 1.05, TURQ, front=0.12, part=908))
        p += [box(x1 - 0.12, s * 0.9, 0.62, 0.06, 0.3, 0.12, HEAD, part=901) for s in (-1, 1)]
    else:
        p.append(box(0, 0, 3.2, 3.0, 1.4, 0.4, (150, 156, 164)))                         # roof equipment
    return p


CFL_RED = (206, 26, 38)
TRAIN_WHITE = (240, 240, 236)


def coach(cab):
    """One 26 m CFL double-deck coach. `cab`: the driving car, red nose at +x."""
    L, W = 26.0, 2.8
    x0, x1 = -L / 2, L / 2
    p = [box(-8.6, 0, 0.0, 2.6, W - 0.6, 0.85, DARK, part=905), box(8.6, 0, 0.0, 2.6, W - 0.6, 0.85, DARK, part=905),
         box(0, 0, 0.55, L, W, 0.5, CFL_RED),                                             # red lower band
         hexa(x0, x1, -W / 2, W / 2, 1.05, 4.25, TRAIN_WHITE, side=0.12),                 # white body
         hexa(x0 + 0.3, x1 - 0.3, -W / 2 + 0.02, W / 2 - 0.02, 4.25, 4.6, (196, 198, 200), side=0.35),  # roof
         box(0, 0, 1.45, L - 4.6, W + 0.04, 0.72, GLASS, part=909),                       # lower deck windows
         box(0, 0, 2.95, L - 2.2, W - 0.18, 0.8, GLASS, part=910)]                        # upper deck windows
    for x in (-10.4, 10.4):                                                               # red doors over the bogies
        for s in (-1, 1):
            p.append(box(x, s * (W / 2 + 0.02), 0.6, 1.4, 0.04, 2.2, CFL_RED, part=911))
    if cab:
        nose = 2.4
        p[3] = hexa(x0, x1 - nose, -W / 2, W / 2, 1.05, 4.25, TRAIN_WHITE, side=0.12)
        p[4] = hexa(x0 + 0.3, x1 - nose - 0.3, -W / 2 + 0.02, W / 2 - 0.02, 4.25, 4.6, (196, 198, 200), side=0.35)
        p[6] = box(-0.9, 0, 2.95, L - 2.2 - 1.8, W - 0.18, 0.8, GLASS, part=910)
        p.append(hexa(x1 - nose, x1, -W / 2, W / 2, 0.55, 3.0, CFL_RED, front=1.2, side=0.15, part=912))  # red nose
        p.append(hexa(x1 - nose, x1 - 1.2, -W / 2 + 0.15, W / 2 - 0.15, 3.0, 4.0, CFL_RED, front=0.6, side=0.15, part=912))
        p.append(hexa(x1 - 1.25, x1 - 0.6, -W / 2 + 0.3, W / 2 - 0.3, 1.9, 3.0, GLASS, front=0.5, part=913))  # windscreen
        p += [box(x1 - 0.05, s * 1.0, 0.9, 0.08, 0.3, 0.16, HEAD, part=901) for s in (-1, 1)]
    return p


def loco():
    """A 19 m CFL electric locomotive (pushes the double-deck set from the other end)."""
    L, W = 19.0, 2.95
    x0, x1 = -L / 2, L / 2
    p = [box(-5.6, 0, 0.0, 3.2, W - 0.6, 0.9, DARK, part=905), box(5.6, 0, 0.0, 3.2, W - 0.6, 0.9, DARK, part=905),
         hexa(x0, x1, -W / 2, W / 2, 0.75, 3.95, CFL_RED, front=0.35, back=0.35, side=0.12),  # red body
         box(0, 0, 1.6, L - 3.0, W + 0.04, 0.42, TRAIN_WHITE, part=914),                      # white side band
         hexa(x0 + 0.6, x1 - 0.6, -W / 2 + 0.25, W / 2 - 0.25, 3.95, 4.3, (110, 112, 118)),   # roof
         box(-3.5, 0, 4.3, 3.0, 1.2, 0.35, (150, 152, 158)), box(3.5, 0, 4.3, 3.0, 1.2, 0.35, (150, 152, 158))]
    # cab windscreens, lying on the sloped ends just proud of the body
    slope = 0.35 / 3.2
    xb, xt = x1 - slope * (2.6 - 0.75) + 0.02, x1 - slope * (3.45 - 0.75) + 0.02
    p.append(hexa(x1 - 0.6, xb, -W / 2 + 0.35, W / 2 - 0.35, 2.6, 3.45, GLASS, front=xb - xt, part=913))
    p.append(hexa(-xb, -(x1 - 0.6), -W / 2 + 0.35, W / 2 - 0.35, 2.6, 3.45, GLASS, back=xb - xt, part=913))
    for sgn in (-1, 1):
        p += [box(sgn * (L / 2 - 0.02), s * 1.0, 1.0, 0.06, 0.3, 0.16, HEAD, part=901) for s in (-1, 1)]
    return p


CAR_COLOURS = {  # warm, slightly muted: they sit on a painted map
    "red": (196, 52, 46), "blue": (46, 88, 158), "white": (234, 232, 226), "black": (52, 54, 60),
    "silver": (170, 174, 180), "yellow": (226, 178, 52), "green": (58, 120, 84), "teal": (48, 140, 150),
}
VAN_COLOURS = {"white": (236, 236, 230), "silver": (176, 180, 186), "blue": (52, 84, 140)}
BUS_LIVERIES = {"avl": (92, 172, 222), "rgtr": (64, 156, 92)}

TYPES = {
    "car": (4.4, {k: car(c) for k, c in CAR_COLOURS.items()}),
    "van": (5.5, {k: van(c) for k, c in VAN_COLOURS.items()}),
    "bus": (12.0, {k: bus(c) for k, c in BUS_LIVERIES.items()}),
    "tram_end": (9.0, {"luxtram": tram(True)}),
    "tram_mid": (9.0, {"luxtram": tram(False)}),
    "train_cab": (26.0, {"cfl": coach(True)}),
    "train_coach": (26.0, {"cfl": coach(False)}),
    "train_loco": (19.0, {"cfl": loco()}),
}

NOTES = {
    "tram_end": "cab section, nose at the front; a tram is end, 3 x mid, end (the rear end drawn at heading + pi)",
    "tram_mid": "middle section of a Luxtram",
    "train_cab": "double-deck driving car, red nose at the front",
    "train_coach": "double-deck middle coach",
    "train_loco": "electric locomotive; symmetric, cabs at both ends",
}


# ---- projection -------------------------------------------------------------------------------------------------

def screen_heading(yaw):
    """Screen direction (map px, y down) of travel along world yaw (from east, anticlockwise)."""
    c, s = math.cos(yaw), math.sin(yaw)
    return math.atan2(-(s - c) * R * SE, (c + s) * R)


def yaw_for(h):
    """World yaw whose travel shows on screen at heading h (inverse of screen_heading)."""
    u, v = math.cos(h), -2 * math.sin(h)
    return math.atan2(u + v, u - v)


def project(p):
    """World points (n, 3) to sprite px offsets (X right, Y down) from the ground origin."""
    sx = (p[:, 0] + p[:, 1]) * R
    sy = (-p[:, 0] + p[:, 1]) * R * SE + p[:, 2] * CE
    return np.stack([sx / MPP, -sy / MPP], axis=1)


def rotate(p, yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    out = p.copy()
    out[:, 0] = p[:, 0] * c - p[:, 1] * s
    out[:, 1] = p[:, 0] * s + p[:, 1] * c
    return out


def to_ground(p):
    """Cast along the sun onto z = 0."""
    out = p.copy()
    out[:, 0] -= p[:, 2] * SUN[0] / SUN[2]
    out[:, 1] -= p[:, 2] * SUN[1] / SUN[2]
    out[:, 2] = 0
    return out


VS = """#version 410
in vec3 p; in vec3 col; in vec3 nrm; in float part;
uniform vec4 frame; uniform vec2 dr;
out vec3 vcol; out vec3 vn; out float vd; out float vpart;
const float R = 0.70710678; const float SE = 0.5; const float CE = 0.8660254;
void main(){
  float sx = (p.x + p.y) * R; float f = (-p.x + p.y) * R;
  float sy = f * SE + p.z * CE; float d = f * CE - p.z * SE;
  gl_Position = vec4((sx-frame.x)/(frame.z-frame.x)*2.-1., (sy-frame.y)/(frame.w-frame.y)*2.-1., (d-dr.x)/(dr.y-dr.x)*2.-1., 1.);
  vcol = col; vn = nrm; vd = d; vpart = part;
}"""
FS = """#version 410
in vec3 vcol; in vec3 vn; in float vd; in float vpart;
layout(location = 0) out vec4 c0; layout(location = 1) out vec4 c1;
void main(){ c0 = vec4(vcol, vpart); c1 = vec4(vn, vd); }"""


class Renderer:
    def __init__(self):
        self.ctx = moderngl.create_standalone_context()
        self.prog = self.ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.size = None

    def _fbo(self, w, h):
        if self.size != (w, h):
            self.t0 = self.ctx.texture((w, h), 4, dtype="f4")
            self.t1 = self.ctx.texture((w, h), 4, dtype="f4")
            self.depth = self.ctx.depth_renderbuffer((w, h))
            self.fbo = self.ctx.framebuffer([self.t0, self.t1], self.depth)
            self.size = (w, h)
        return self.fbo

    def raster(self, tris, w, h, ax, ay):
        """Draw triangles (world coords) into a w x h frame whose ground origin sits at sprite px (ax, ay)."""
        fbo = self._fbo(w, h)
        fbo.use()
        fbo.clear(0, 0, 0, -1, depth=1.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        # sprite px X = sx / MPP + ax, Y = -sy / MPP + ay, pixel edges at integers
        self.prog["frame"].value = (-ax * MPP, -(h - ay) * MPP, (w - ax) * MPP, ay * MPP)
        self.prog["dr"].value = (-30.0, 30.0)
        buf = self.ctx.buffer(tris.tobytes())
        vao = self.ctx.vertex_array(self.prog, [(buf, "3f 3f 3f 1f", "p", "col", "nrm", "part")])
        vao.render(moderngl.TRIANGLES)
        vao.release(); buf.release()
        a = np.frombuffer(self.t0.read(), np.float32).reshape(h, w, 4)[::-1]
        b = np.frombuffer(self.t1.read(), np.float32).reshape(h, w, 4)[::-1]
        return a, b


def shade(rgb, n):
    s = np.clip(0.8 + 0.3 * (n @ SUN), 0.45, 1.06)
    return np.clip(rgb * s[..., None], 0, 1)


def frame_image(r, tris, w, h, ax, ay):
    a, b = r.raster(tris, w, h, ax, ay)
    filled = a[..., 3] >= 0
    rgb = shade(a[..., :3], b[..., :3])
    depth = np.where(filled, b[..., 3], 1e3)
    part = np.where(filled, a[..., 3], -1)
    n = b[..., :3]
    # inner lines: part, normal or depth jumps between neighbours, drawn on the nearer pixel of the pair
    inner = np.zeros((h, w), bool)
    for ax_ in (0, 1):
        dn = np.abs(np.diff(n, axis=ax_)).sum(-1)
        dd = np.abs(np.diff(depth, axis=ax_))
        dp = np.diff(part, axis=ax_) != 0
        both = np.logical_and(np.delete(filled, 0, axis=ax_), np.delete(filled, -1, axis=ax_))
        j = both & ((dn > 0.3) | (dd > 0.35) | dp)
        first_near = np.delete(depth, -1, axis=ax_) <= np.delete(depth, 0, axis=ax_)
        if ax_ == 0:
            inner[:-1] |= j & first_near; inner[1:] |= j & ~first_near
        else:
            inner[:, :-1] |= j & first_near; inner[:, 1:] |= j & ~first_near
    # lamps glow: no shading and no ink over them (they are only a pixel or two)
    lamp = (part == 901) | (part == 902)
    rgb[lamp] = a[..., :3][lamp]
    inner &= ~lamp
    rgb[inner] *= 0.42
    # outer line: 1 px around the silhouette (4-neighbours)
    grow = filled.copy()
    grow[1:] |= filled[:-1]; grow[:-1] |= filled[1:]; grow[:, 1:] |= filled[:, :-1]; grow[:, :-1] |= filled[:, 1:]
    outline = grow & ~filled
    out = np.zeros((h, w, 4), np.uint8)
    out[filled, :3] = (rgb[filled] * 255 + 0.5).astype(np.uint8)
    out[filled, 3] = 255
    out[outline, :3] = INK
    out[outline, 3] = 255
    return Image.fromarray(out, "RGBA")


def shadow_image(r, tris, w, h, ax, ay):
    g = tris.copy()
    g[:, :3] = to_ground(g[:, :3])
    a, _ = r.raster(g, w, h, ax, ay)
    m = Image.fromarray(((a[..., 3] >= 0) * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.3))
    sh = Image.new("RGBA", (w, h), SHADOW_RGBA[:3] + (0,))
    sh.putalpha(m.point(lambda v: v * SHADOW_RGBA[3] // 255))
    return sh


def frame_bounds(models, yaws):
    pts = []
    for parts in models:
        v = np.concatenate([p[0] for p in parts])
        for yaw in yaws:
            w = rotate(v, yaw)
            pts.append(project(w)); pts.append(project(to_ground(w)))
    p = np.concatenate(pts)
    pad = 3
    x0, y0 = np.floor(p.min(0)) - pad
    x1, y1 = np.ceil(p.max(0)) + pad
    return int(x1 - x0), int(y1 - y0), int(-x0), int(-y0)


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    r = Renderer()
    step = 2 * math.pi / HEADINGS
    heads = [i * step for i in range(HEADINGS)]
    yaws = [yaw_for(h) for h in heads]
    rows_per = HEADINGS // COLS
    meta = {"mpp": MPP, "map_mpp": MAP_MPP, "headings": HEADINGS,
            "heading_note": "screen heading in radians, atan2(dy, dx) with y down; index i is i * 2pi / headings",
            "types": {}}
    total = 0
    for name, (length, variants) in TYPES.items():
        models = list(variants.values())
        w, h, ax, ay = frame_bounds(models, yaws)
        atlas = Image.new("RGBA", (w * COLS, h * rows_per * len(models)), (0, 0, 0, 0))
        cells = []
        for vi, parts in enumerate(models):
            tris = triangles(parts)
            vc = []
            for i, yaw in enumerate(yaws):
                t = tris.copy()
                t[:, :3] = rotate(t[:, :3], yaw)
                t[:, 6:9] = rotate(t[:, 6:9], yaw)
                img = shadow_image(r, t, w, h, ax, ay)
                img.alpha_composite(frame_image(r, t, w, h, ax, ay))
                cx, cy = (i % COLS) * w, (vi * rows_per + i // COLS) * h
                atlas.paste(img, (cx, cy))
                vc.append([cx, cy])
            cells.append(vc)
        path = out / f"{name}.png"
        atlas.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)
        total += path.stat().st_size
        meta["types"][name] = {
            "image": f"{name}.png", "length_m": length, "frame": [w, h], "anchor": [ax, ay],
            "variants": list(variants.keys()), "heading": [round(x, 6) for x in heads], "cells": cells,
            **({"note": NOTES[name]} if name in NOTES else {}),
        }
        print(f"{name}: frame {w}x{h}, anchor ({ax}, {ay}), {len(models)} variant(s), {path.stat().st_size // 1024} KB")
    (out / "sprites.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f"total {total // 1024} KB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
