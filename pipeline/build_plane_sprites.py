"""Aircraft sprites for the sky over the city: low-poly Cargolux and Luxair aircraft, rendered with the map's camera.

The models are lofted fuselages (rings of flat facets), swept and tapered wing slabs, engines, fin and tailplane,
built here as triangle lists and drawn with the vehicle renderer of build_sprites.py (same camera, flat shading by
face normal, 1 px ink line), so they sit in the painted map's style. Liveries are simplified, with no logos or
lettering: Cargolux white with a blue fin and a red band across it; Luxair white with a light-blue fin, winglets
and engine lips.

Types (real sizes; drawn at 0.5 m per sprite px, half the map's resolution, since aircraft are seen from far out):
  b748    Boeing 747-8F, Cargolux (76.3 m long, 68.4 m span, four engines, the short upper-deck hump)
  b738    Boeing 737-800, Luxair (39.5 m, 35.8 m with winglets); the 737 MAX 8 looks the same from here
  e295    Embraer E195-E2, Luxair (41.5 m, 35.1 m)
  dh8d    De Havilland Dash 8-400, Luxair (32.8 m, 28.4 m, high wing, T-tail, two propellers)

Output, in web/public/sprites/: planes.json (the sprites.json format of src/components/sprites.ts) and one atlas per
type. Each type has three variants of 32 screen headings: "level" (cruise, descent), "climb" (nose up 8 degrees) and
"shadow" (a soft dark silhouette on the ground, cast along the map's sun from the model at height 0; draw it at the
plane's ground point moved along the sun by its height). The anchor is the model's centre (on the fuselage axis,
mid-length), so a plane at altitude h is drawn h * 3.46 map px above its ground point.
Per type, "lights" lists for each variant ("level", "climb") and heading the frame px of each light the camera
sees (depth-tested against the body): [kind, x, y] with kind
  "red" / "green"  navigation lights at the left and right wing tips;  "white" the tail light;
  "beacon"         the red anti-collision light on top of the fuselage (the one under it is hidden from above);
  "strobe"         white strobes at the wing tips;   "landing"  the landing lights at the wing roots.

Run: pipeline/.venv/bin/python pipeline/build_plane_sprites.py [--out DIR]
"""
import argparse
import json
import math
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image, ImageFilter

from build_sprites import CE, COLS, HEADINGS, INK, OUT, R, SE, SUN, Renderer, rotate, shade, to_ground, yaw_for

MPP = 0.5            # metres per sprite pixel
MAP_MPP = 0.25
PITCH_CLIMB = math.radians(8)
SHADOW_RGBA = (18, 20, 34, 70)

WHITE = (240, 240, 236)
BELLY = (206, 210, 216)
WING = (192, 197, 204)
METAL = (170, 175, 182)
WINDOW = (40, 48, 64)
ENGINE = (214, 216, 220)
INTAKE = (52, 56, 64)
PROP = (70, 72, 80)
CV_BLUE = (28, 62, 142)
CV_RED = (204, 34, 42)
LG_BLUE = (104, 184, 228)


class PlaneRenderer(Renderer):
    """The vehicle renderer at the aircraft scale: 0.5 m per px and a deeper depth range (a 747 spans 76 m)."""

    def raster(self, tris, w, h, ax, ay):
        fbo = self._fbo(w, h)
        fbo.use()
        fbo.clear(0, 0, 0, -1, depth=1.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.prog["frame"].value = (-ax * MPP, -(h - ay) * MPP, (w - ax) * MPP, ay * MPP)
        self.prog["dr"].value = (-90.0, 90.0)
        buf = self.ctx.buffer(tris.tobytes())
        vao = self.ctx.vertex_array(self.prog, [(buf, "3f 3f 3f 1f", "p", "col", "nrm", "part")])
        vao.render(moderngl.TRIANGLES)
        vao.release(); buf.release()
        a = np.frombuffer(self.t0.read(), np.float32).reshape(h, w, 4)[::-1]
        b = np.frombuffer(self.t1.read(), np.float32).reshape(h, w, 4)[::-1]
        return a, b


def frame_image(r, tris, w, h, ax, ay):
    """As build_sprites.frame_image, with the line tests scaled to this resolution: a level surface steps 0.87 m
    in depth per pixel here (0.22 m for the vehicles), and the rings of a fuselage turn by 26 to 30 degrees from
    facet to facet, which should read as one rounded body, not as stripes."""
    a, b = r.raster(tris, w, h, ax, ay)
    filled = a[..., 3] >= 0
    rgb = shade(a[..., :3], b[..., :3])
    depth = np.where(filled, b[..., 3], 1e3)
    part = np.where(filled, a[..., 3], -1)
    n = b[..., :3]
    inner = np.zeros((h, w), bool)
    for ax_ in (0, 1):
        dn = np.abs(np.diff(n, axis=ax_)).sum(-1)
        dd = np.abs(np.diff(depth, axis=ax_))
        dp = np.diff(part, axis=ax_) != 0
        both = np.logical_and(np.delete(filled, 0, axis=ax_), np.delete(filled, -1, axis=ax_))
        j = both & ((dn > 0.95) | (dd > 3.0) | dp)
        first_near = np.delete(depth, -1, axis=ax_) <= np.delete(depth, 0, axis=ax_)
        if ax_ == 0:
            inner[:-1] |= j & first_near; inner[1:] |= j & ~first_near
        else:
            inner[:, :-1] |= j & first_near; inner[:, 1:] |= j & ~first_near
    rgb[inner] *= 0.5
    grow = filled.copy()
    grow[1:] |= filled[:-1]; grow[:-1] |= filled[1:]; grow[:, 1:] |= filled[:, :-1]; grow[:, :-1] |= filled[:, 1:]
    outline = grow & ~filled
    out = np.zeros((h, w, 4), np.uint8)
    out[filled, :3] = (rgb[filled] * 255 + 0.5).astype(np.uint8)
    out[filled, 3] = 255
    out[outline, :3] = INK
    out[outline, 3] = 255
    return Image.fromarray(out, "RGBA")


def project(p):
    """World points (n, 3) to sprite px offsets (X right, Y down) from the model's centre, and their depth."""
    sx = (p[:, 0] + p[:, 1]) * R
    f = (-p[:, 0] + p[:, 1]) * R
    sy = f * SE + p[:, 2] * CE
    return np.stack([sx / MPP, -sy / MPP], axis=1), f * CE - p[:, 2] * SE


# ---- geometry ---------------------------------------------------------------------------------------------------

class Mesh:
    """Flat-shaded triangles, rows of x y z  r g b  nx ny nz  part, normals turned away from each piece's centre."""

    def __init__(self):
        self.rows = []
        self.part = 0

    def new_part(self):
        self.part += 1
        return self.part

    def quad(self, q, colour, centre, part):
        q = [np.asarray(v, float) for v in q]
        n = np.cross(q[1] - q[0], q[2] - q[0])
        if np.linalg.norm(n) < 1e-9 and len(q) > 3:
            n = np.cross(q[2] - q[0], q[3] - q[0])
        ln = np.linalg.norm(n)
        if ln < 1e-9:
            return
        n /= ln
        if np.dot(n, np.mean(q, axis=0) - centre) < 0:
            n = -n
        c = np.array(colour, float) / 255
        tris = ((0, 1, 2), (0, 2, 3)) if len(q) == 4 else ((0, 1, 2),)
        for tri in tris:
            for i in tri:
                self.rows.append([*q[i], *c, *n, float(part)])

    def solid(self, bottom, top, colour):
        """Eight corners: bottom and top rings of four, in the same order round."""
        v = [np.asarray(p, float) for p in list(bottom) + list(top)]
        centre = np.mean(v, axis=0)
        part = self.new_part()
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.quad([v[i] for i in f], colour, centre, part)

    def loft(self, sections, colour, sides=12, axis_y=0.0):
        """A body of revolution along x: sections (x, half width, top, bottom, centre z), nose first. colour is a
        function (x, angle) -> rgb, angle 0 to the left (+y), pi/2 up. Ends are closed with a fan."""
        part = self.new_part()
        rings = []
        for x, ry, rt, rb, zc in sections:
            ring = []
            for k in range(sides):
                a = 2 * math.pi * k / sides
                rz = rt if math.sin(a) >= 0 else rb
                ring.append((x, axis_y + ry * math.cos(a), zc + rz * math.sin(a)))
            rings.append(ring)
        for i in range(len(rings) - 1):
            r0, r1 = rings[i], rings[i + 1]
            xm = (sections[i][0] + sections[i + 1][0]) / 2
            centre = np.array([xm, axis_y, (sections[i][4] + sections[i + 1][4]) / 2])
            for k in range(sides):
                k1 = (k + 1) % sides
                a = 2 * math.pi * (k + 0.5) / sides
                self.quad([r0[k], r0[k1], r1[k1], r1[k]], colour(xm, a), centre, part)
        for ring, (x, _, _, _, zc), sgn in ((rings[0], sections[0], 1), (rings[-1], sections[-1], -1)):
            tip = np.array([x + 0.3 * sgn, axis_y, zc])
            centre = np.array([x - 2 * sgn, axis_y, zc])
            for k in range(sides):
                self.quad([ring[k], ring[(k + 1) % sides], tip], colour(x, 2 * math.pi * (k + 0.5) / sides), centre, part)

    def wing(self, x_le, y0, z0, root, tip, span, sweep_deg, dihedral_deg, thick, colour, mirror=True, up=False):
        """A tapered, swept slab from the root (leading edge at x_le, y0, z0) out to `span` metres. up: a fin."""
        t = math.tan(math.radians(sweep_deg))
        d = math.tan(math.radians(dihedral_deg))
        for s in ((1, -1) if mirror else (1,)):
            if up:
                le0, te0 = (x_le, y0, z0), (x_le - root, y0, z0)
                le1 = (x_le - span * t, y0, z0 + span)
                te1 = (le1[0] - tip, y0, z0 + span)
                ring = [le0, le1, te1, te0]
                off = np.array([0, thick / 2, 0])
                self.solid([np.array(p) - off for p in ring], [np.array(p) + off for p in ring], colour)
            else:
                le0, te0 = (x_le, s * y0, z0), (x_le - root, s * y0, z0)
                le1 = (x_le - span * t, s * (y0 + span), z0 + span * d)
                te1 = (le1[0] - tip, s * (y0 + span), z0 + span * d)
                ring = [le0, le1, te1, te0]
                off = np.array([0, 0, thick / 2])
                self.solid([np.array(p) - off for p in ring], [np.array(p) + off for p in ring], colour)

    def box(self, x0, x1, y0, y1, z0, z1, colour):
        self.solid([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                   [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], colour)

    def engine(self, x, y, z, length, radius, body, lip):
        """A nacelle along x centred on (x, y, z): a coloured lip, the cowl and a dark intake face."""
        self.loft([(x + length / 2, radius * 0.92, radius * 0.92, radius * 0.92, z),
                   (x + length / 2 - 0.6, radius, radius, radius, z),
                   (x + length * 0.1, radius, radius, radius, z),
                   (x - length / 2, radius * 0.6, radius * 0.6, radius * 0.6, z)],
                  lambda xm, a: lip if xm > x + length / 2 - 0.7 else body, sides=10, axis_y=y)
        # the intake, a dark disc just in front of the lip
        part = self.new_part()
        c = np.array([x + length / 2 + 0.05, y, z])
        ring = [(c[0], y + radius * 0.8 * math.cos(2 * math.pi * k / 10), z + radius * 0.8 * math.sin(2 * math.pi * k / 10))
                for k in range(10)]
        for k in range(10):
            self.quad([ring[k], ring[(k + 1) % 10], c + [0.01, 0, 0]], INTAKE, c - [1, 0, 0], part)

    def tris(self):
        return np.array(self.rows, np.float32)


def fuselage_colour(L, belly, windows_to):
    """White on top, a paler grey belly below the side line, dark cockpit windows near the nose."""
    def f(x, a):
        if x > L / 2 - windows_to and 0.25 < a < 1.25:
            return WINDOW
        return WHITE if math.sin(a) > -0.35 else belly
    return f


def b748():
    """Boeing 747-8F in a simplified Cargolux livery."""
    m, L = Mesh(), 76.3
    h = L / 2
    sec = [(h, 0.25, 0.3, 0.25, -0.6), (h - 1.5, 1.7, 1.9, 1.7, -0.5), (h - 4, 2.7, 3.0, 2.9, -0.25),
           (h - 7, 3.15, 3.9, 3.4, 0), (h - 13, 3.25, 4.5, 3.6, 0), (h - 20, 3.25, 4.35, 3.6, 0),
           (h - 25, 3.25, 3.65, 3.6, 0), (h - 54, 3.25, 3.6, 3.6, 0), (h - 63, 2.8, 3.2, 2.5, 0.6),
           (h - 71, 1.7, 2.1, 1.3, 1.4), (-h, 0.4, 0.5, 0.3, 2.0)]
    m.loft(sec, fuselage_colour(L, BELLY, 3.2), sides=14)
    # wings: 37.5 degrees of sweep, root chord about 14 m at the leading edge 10 m ahead of the centre
    m.wing(8.5, 3.0, -1.6, 14.5, 3.8, 31.2, 37.5, 5, 0.9, WING)
    for s in (1, -1):
        for yy, xx in ((11.5, 3.0), (21.0, -4.2)):
            z = -1.6 + yy * math.tan(math.radians(5)) - 1.9
            m.engine(xx + 2.5, s * yy, z, 7.4, 1.65, ENGINE, METAL)
            m.box(xx - 1.5, xx + 3.5, s * yy - 0.3, s * yy + 0.3, z + 1.2, z + 2.2, WING)
    # tailplane and fin: blue with a red band
    m.wing(-28.5, 1.5, 1.6, 9.0, 2.6, 10.0, 37, 7, 0.6, WING)
    def band(h0, h1, colour, thick):
        chord = lambda hh: 12.0 - hh * (12.0 - 4.6) / 13.0
        m.wing(-25.0 - h0, 0.0, 3.4 + h0, chord(h0), chord(h1), h1 - h0, 45, 0, thick, colour, mirror=False, up=True)
    band(0, 7.2, CV_BLUE, 0.6)
    band(7.2, 9.6, CV_RED, 0.62)
    band(9.6, 13.0, CV_BLUE, 0.6)
    lights = lights_for(L, 34.2, 8.5 - 31.2 * math.tan(math.radians(37.5)), -1.6 + 31.2 * math.tan(math.radians(5)),
                        4.5, 3.6, 8.0, 3.2)
    return L, m.tris(), lights


def twin(L, span, sweep, d, root, tip, x_le, fin_colour, lip, winglet, eng_r, eng_len, eng_y, fin_h, fin_root):
    """A low-wing twin jet (737, E195-E2)."""
    m, h = Mesh(), L / 2
    r = d / 2
    sec = [(h, 0.2, 0.25, 0.2, -0.35), (h - 1.2, r * 0.6, r * 0.65, r * 0.6, -0.3), (h - 3.2, r * 0.92, r * 0.95, r * 0.92, -0.1),
           (h - 5.5, r, r, r, 0), (h - L * 0.72, r, r, r, 0), (h - L * 0.86, r * 0.75, r * 0.85, r * 0.6, r * 0.25),
           (-h, 0.25, 0.3, 0.2, r * 0.6)]
    m.loft(sec, fuselage_colour(L, BELLY, 2.4), sides=12)
    semi = span / 2 - r
    m.wing(x_le, r * 0.8, -r * 0.6, root, tip, semi, sweep, 6, 0.55, WING)
    # winglets, straight up at the tips
    t = math.tan(math.radians(sweep))
    for s in (1, -1):
        tx = x_le - semi * t
        ty, tz = s * (r * 0.8 + semi), -r * 0.6 + semi * math.tan(math.radians(6))
        m.solid([(tx, ty - 0.12, tz), (tx - tip, ty - 0.12, tz), (tx - tip, ty + 0.12, tz), (tx, ty + 0.12, tz)],
                [(tx - 1.6, ty - 0.1, tz + 2.2), (tx - tip, ty - 0.1, tz + 2.2), (tx - tip, ty + 0.1, tz + 2.2),
                 (tx - 1.6, ty + 0.1, tz + 2.2)], winglet)
        z = -r * 0.6 + eng_y * math.tan(math.radians(6)) - eng_r - 0.2
        m.engine(x_le - eng_y * t + eng_len * 0.45, s * eng_y, z, eng_len, eng_r, ENGINE, lip)
    m.wing(-h + 6.2, r * 0.4, r * 0.3, 4.2, 1.6, span * 0.2, 32, 6, 0.4, WING)
    m.wing(-h + 8.4, 0.0, r * 0.8, fin_root, 2.0, fin_h, 40, 0, 0.45, fin_colour, mirror=False, up=True)
    lights = lights_for(L, span, x_le - semi * t, -r * 0.6 + semi * math.tan(math.radians(6)), x_le - 1, r, r * 0.8, r)
    return L, m.tris(), lights


def b738():
    """Boeing 737-800 in a simplified Luxair livery."""
    return twin(39.5, 35.8, 25, 3.76, 7.0, 1.4, 4.0, LG_BLUE, LG_BLUE, LG_BLUE, 1.0, 4.6, 4.9, 7.4, 6.2)


def e295():
    """Embraer E195-E2 in a simplified Luxair livery."""
    return twin(41.5, 35.1, 23, 3.35, 6.4, 1.5, 4.6, LG_BLUE, LG_BLUE, LG_BLUE, 1.15, 4.8, 5.0, 7.0, 5.6)


def dh8d():
    """De Havilland Dash 8-400 in a simplified Luxair livery: high wing, T-tail, two turboprops."""
    m, L = Mesh(), 32.8
    h, r = L / 2, 1.35
    sec = [(h, 0.2, 0.2, 0.2, -0.3), (h - 1.2, r * 0.6, r * 0.6, r * 0.55, -0.25), (h - 3.2, r * 0.95, r * 0.98, r * 0.92, -0.05),
           (h - 5, r, r, r, 0), (h - 22.5, r, r, r, 0), (h - 28.5, r * 0.65, r * 0.75, r * 0.5, r * 0.35), (-h, 0.2, 0.25, 0.2, r * 0.7)]
    m.loft(sec, fuselage_colour(L, BELLY, 2.2), sides=12)
    semi = 28.4 / 2 - 0.4
    m.wing(1.8, 0.4, r + 0.15, 3.0, 1.5, semi, 2, 2, 0.5, WING)
    for s in (1, -1):
        y = 4.1
        m.engine(1.8 + 1.6, s * y, r - 0.35, 7.2, 0.62, ENGINE, LG_BLUE)
        # the propeller: six slim blades, standing still (a disc would read as a dark hole from above)
        cx, cz = 1.8 + 1.6 + 3.7, r - 0.35
        for k in range(6):
            ang = math.pi / 6 + k * math.pi / 3
            dy, dz = math.cos(ang), math.sin(ang)
            py, pz = -dz, dy                           # across the blade
            ring = [(0.25 * dy + 0.14 * py, 0.25 * dz + 0.14 * pz), (2.0 * dy + 0.09 * py, 2.0 * dz + 0.09 * pz),
                    (2.0 * dy - 0.09 * py, 2.0 * dz - 0.09 * pz), (0.25 * dy - 0.14 * py, 0.25 * dz - 0.14 * pz)]
            m.solid([(cx - 0.06, s * y + u, cz + v) for u, v in ring], [(cx + 0.06, s * y + u, cz + v) for u, v in ring], PROP)
        m.loft([(cx + 0.7, 0.05, 0.05, 0.05, cz), (cx + 0.1, 0.32, 0.32, 0.32, cz), (cx - 0.1, 0.34, 0.34, 0.34, cz)],
               lambda xm, a: METAL, sides=8, axis_y=s * y)
    # fin (light blue) with the tailplane on top
    m.wing(-h + 6.8, 0.0, r * 0.7, 5.2, 3.3, 5.6, 32, 0, 0.4, LG_BLUE, mirror=False, up=True)
    m.wing(-h + 6.8 - 5.6 * math.tan(math.radians(32)) + 0.3, 0.0, r * 0.7 + 5.5, 2.6, 1.4, 4.0, 10, 0, 0.35, WING)
    lights = lights_for(L, 28.4, 1.8 - semi * math.tan(math.radians(2)), r + 0.15 + semi * math.tan(math.radians(2)),
                        1.6, r, r + 0.3, r)
    return L, m.tris(), lights


def lights_for(L, span, tip_x, tip_z, land_x, beacon_z, top_z, bottom_z):
    """Light positions in the model frame: kind and point."""
    s = span / 2 + 0.15
    return [("red", (tip_x - 0.5, s, tip_z)), ("green", (tip_x - 0.5, -s, tip_z)),
            ("strobe", (tip_x - 1.2, s, tip_z)), ("strobe", (tip_x - 1.2, -s, tip_z)),
            ("white", (-L / 2 - 0.3, 0, beacon_z * 0.6)),
            ("beacon", (0.0, 0, top_z + 0.25)), ("beacon", (0.0, 0, -bottom_z - 0.25)),
            ("landing", (land_x, 2.6, -0.5)), ("landing", (land_x, -2.6, -0.5))]


TYPES = {"b748": b748, "b738": b738, "e295": e295, "dh8d": dh8d}
NOTES = {
    "b748": "Boeing 747-8F, Cargolux (simplified: white, blue fin with a red band)",
    "b738": "Boeing 737-800 / MAX 8, Luxair (simplified: white, light-blue fin, winglets and engine lips)",
    "e295": "Embraer E195-E2, Luxair (simplified like the 737)",
    "dh8d": "De Havilland Dash 8-400, Luxair (simplified: white, light-blue fin and nacelle lips)",
}


# ---- rendering --------------------------------------------------------------------------------------------------

def pitch(p, a):
    """Nose up by `a` radians (about the model's y axis)."""
    out = p.copy()
    c, s = math.cos(a), math.sin(a)
    out[:, 0] = p[:, 0] * c - p[:, 2] * s
    out[:, 2] = p[:, 0] * s + p[:, 2] * c
    return out


def posed(tris, yaw, nose):
    t = tris.copy()
    t[:, :3] = rotate(pitch(t[:, :3], nose), yaw)
    t[:, 6:9] = rotate(pitch(t[:, 6:9], nose), yaw)
    return t


def bounds(tris, yaws):
    pts = []
    for yaw in yaws:
        for nose in (0.0, PITCH_CLIMB):
            p = rotate(pitch(tris[:, :3], nose), yaw)
            pts.append(project(p)[0])
            pts.append(project(to_ground(p))[0])
    p = np.concatenate(pts)
    x0, y0 = np.floor(p.min(0)) - 3
    x1, y1 = np.ceil(p.max(0)) + 3
    return int(x1 - x0), int(y1 - y0), int(-x0), int(-y0)


def shadow(r, t, w, h, ax, ay):
    g = t.copy()
    g[:, :3] = to_ground(g[:, :3])
    a, _ = r.raster(g, w, h, ax, ay)
    m = Image.fromarray(((a[..., 3] >= 0) * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(2.2))
    sh = Image.new("RGBA", (w, h), SHADOW_RGBA[:3] + (0,))
    sh.putalpha(m.point(lambda v: v * SHADOW_RGBA[3] // 255))
    return sh


def visible_lights(r, t, lights, yaw, nose, w, h, ax, ay):
    """[kind, x, y] of each light the camera sees: in the frame and not behind the body."""
    _, b = r.raster(t, w, h, ax, ay)
    depth = b[..., 3]
    filled = np.frombuffer(r.t0.read(), np.float32).reshape(h, w, 4)[::-1][..., 3] >= 0
    pts = rotate(pitch(np.array([p for _, p in lights], float), nose), yaw)
    xy, d = project(pts)
    out = []
    for (kind, _), (x, y), dd in zip(lights, xy, d):
        px, py = x + ax, y + ay
        ix, iy = int(px), int(py)
        if not (0 <= ix < w and 0 <= iy < h):
            continue
        # seen when nothing of the body is nearer at that pixel (the light sits on the surface: 0.6 m of slack)
        y0, y1, x0, x1 = max(0, iy - 1), min(h, iy + 2), max(0, ix - 1), min(w, ix + 2)
        near = np.where(filled[y0:y1, x0:x1], depth[y0:y1, x0:x1], 1e3).max()
        if near < dd - 0.6:
            continue
        out.append([kind, round(float(px), 1), round(float(py), 1)])
    return out


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    r = PlaneRenderer()
    step = 2 * math.pi / HEADINGS
    heads = [i * step for i in range(HEADINGS)]
    yaws = [yaw_for(hh) for hh in heads]
    rows_per = HEADINGS // COLS
    meta = {"mpp": MPP, "map_mpp": MAP_MPP, "headings": HEADINGS,
            "heading_note": "screen heading in radians, atan2(dy, dx) with y down; index i is i * 2pi / headings",
            "anchor_note": "the model's centre on the fuselage axis; draw it h * 3.46 map px above the ground point",
            "types": {}}
    total = 0
    for name, make in TYPES.items():
        length, tris, lights = make()
        w, h, ax, ay = bounds(tris, yaws)
        variants = ["level", "climb", "shadow"]
        atlas = Image.new("RGBA", (w * COLS, h * rows_per * len(variants)), (0, 0, 0, 0))
        cells = [[], [], []]
        lit = {"level": [], "climb": []}
        for i, yaw in enumerate(yaws):
            for vi, nose in enumerate((0.0, PITCH_CLIMB)):
                t = posed(tris, yaw, nose)
                cx, cy = (i % COLS) * w, (vi * rows_per + i // COLS) * h
                atlas.paste(frame_image(r, t, w, h, ax, ay), (cx, cy))
                cells[vi].append([cx, cy])
                lit[variants[vi]].append(visible_lights(r, t, lights, yaw, nose, w, h, ax, ay))
            cx, cy = (i % COLS) * w, (2 * rows_per + i // COLS) * h
            atlas.paste(shadow(r, posed(tris, yaw, 0.0), w, h, ax, ay), (cx, cy))
            cells[2].append([cx, cy])
        path = out / f"plane_{name}.png"
        atlas.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)
        total += path.stat().st_size
        meta["types"][name] = {"image": path.name, "length_m": length, "frame": [w, h], "anchor": [ax, ay],
                               "variants": variants, "heading": [round(x, 6) for x in heads], "cells": cells,
                               "lights": lit, "note": NOTES[name]}
        print(f"{name}: frame {w}x{h}, anchor ({ax}, {ay}), {path.stat().st_size // 1024} KB")
    (out / "planes.json").write_text(json.dumps(meta, separators=(",", ":")))
    total += (out / "planes.json").stat().st_size
    print(f"total {total // 1024} KB")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=OUT)
    build(ap.parse_args().out)


if __name__ == "__main__":
    main()
