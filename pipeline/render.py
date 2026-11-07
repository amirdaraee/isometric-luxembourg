"""Orthographic 3D captures: textured buildings on orthophoto-draped terrain, cut into frames."""
import argparse
import io
import json
import math
import time
import zipfile
from collections import OrderedDict
import moderngl
import numpy as np
from PIL import Image
from common import (BATI_ZIP, RAW, WORK, PILOT_LONLAT, METRES_PER_PIXEL, ORIGIN_E, ORIGIN_N,
                    TILE, ELEV, R, lonlat_to_en, en_to_lonlat)

FRAME = 2048
BG = (16, 24, 40)
ORTHO_Z = 18
MAX_TEX = 1024

VS = """#version 410
in vec3 p; in vec2 uv;
uniform vec4 frame;  // sx0, sy0, sx1, sy1
uniform vec2 dr;     // depth range
out vec2 vuv;
const float R = 0.70710678; const float SE = 0.5; const float CE = 0.8660254;
void main(){
  float sx = (p.x + p.y) * R;
  float f = (-p.x + p.y) * R;
  float sy = f * SE + p.z * CE;
  float d = f * CE - p.z * SE;
  gl_Position = vec4((sx-frame.x)/(frame.z-frame.x)*2.-1., (sy-frame.y)/(frame.w-frame.y)*2.-1., (d-dr.x)/(dr.y-dr.x)*2.-1., 1.);
  vuv = uv;
}"""
FS = """#version 410
in vec2 vuv; uniform sampler2D t; out vec4 c;
void main(){ c = texture(t, vuv); }"""


# Line-guide pass: same projection; writes surface normal (x, y), view depth and a procedural window mask, in
# float. Edges come from normal and depth jumps (CPU); windows sit on a regular grid in each wall's own plane.
VS_G = """#version 410
in vec3 p; in vec2 uv;
uniform vec4 frame; uniform vec2 dr;
out vec3 wp; out float vd;
const float R = 0.70710678; const float SE = 0.5; const float CE = 0.8660254;
void main(){
  float sx = (p.x + p.y) * R; float f = (-p.x + p.y) * R;
  float sy = f * SE + p.z * CE; float d = f * CE - p.z * SE;
  gl_Position = vec4((sx-frame.x)/(frame.z-frame.x)*2.-1., (sy-frame.y)/(frame.w-frame.y)*2.-1., (d-dr.x)/(dr.y-dr.x)*2.-1., 1.);
  wp = p; vd = d;
}"""
FS_G = """#version 410
in vec3 wp; in float vd; uniform int is_wall; out vec4 c;
void main(){
  vec3 n = normalize(cross(dFdx(wp), dFdy(wp)));
  if (n.z < 0.) n = -n;
  float win = 0.;
  if (is_wall == 1 && n.z < 0.35) {
    vec2 h = normalize(vec2(-n.y, n.x));            // along the wall
    float a = dot(wp.xy, h); float z = wp.z;
    float fa = fract(a / 2.6); float fz = fract((z - 0.9) / 3.2);
    win = (fa > 0.28 && fa < 0.72 && fz > 0.12 && fz < 0.62) ? 1. : 0.;
  }
  c = vec4(n.x, n.y, vd, win + (is_wall == 1 ? 2. : 0.));
}"""

# Height pass: the visible surface's height above sea level, in float (same projection as the line pass).
FS_H = """#version 410
in vec3 wp; in float vd; out vec4 c;
void main(){ c = vec4(wp.z, 0., 0., 1.); }"""


def merc_px(lon, lat, z):
    t = 2 ** z * 256
    return (lon + 180) / 360 * t, (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * t


def load_ortho():
    d = RAW / "ortho2023" / str(ORTHO_Z)
    files = sorted(d.glob("*.jpg"))
    xs = [int(f.stem.split("_")[0]) for f in files]; ys = [int(f.stem.split("_")[1]) for f in files]
    x0, y0 = min(xs), min(ys)
    W, H = (max(xs) - x0 + 1) * 256, (max(ys) - y0 + 1) * 256
    im = Image.new("RGB", (W, H))
    for f, x, y in zip(files, xs, ys):
        im.paste(Image.open(f), ((x - x0) * 256, (y - y0) * 256))
    return im, x0 * 256, y0 * 256


def mirror_fill(img, mask):
    """Fill a thin masked strip with real ground texture: each hole pixel copies the pixel mirrored across
    the nearest edge of the hole (trees stay trees, grass stays grass), instead of smearing colours inward."""
    import cv2
    hole = mask > 0
    if not hole.any():
        return img
    # Nearest non-hole pixel for every pixel.
    _, lab = cv2.distanceTransformWithLabels(hole.astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(~hole)
    qy = np.zeros(lab.max() + 1, np.int32); qx = np.zeros(lab.max() + 1, np.int32)
    qy[lab[~hole]] = ys; qx[lab[~hole]] = xs
    py, px = np.nonzero(hole)
    ny, nx = qy[lab[py, px]], qx[lab[py, px]]
    sy = np.clip(2 * ny - py, 0, img.shape[0] - 1); sx = np.clip(2 * nx - px, 0, img.shape[1] - 1)
    bad = hole[sy, sx]  # mirror landed in another hole: fall back to the edge pixel
    sy[bad], sx[bad] = ny[bad], nx[bad]
    out = img.copy()
    out[py, px] = img[sy, sx]
    # Soften the mirror line a little so it doesn't read as a crease.
    blur = cv2.GaussianBlur(out, (5, 5), 0)
    out[py, px] = blur[py, px]
    return out


def erase_decks(ortho, deck, ox, oy, pad_m=4.0):
    """Paint bridge decks out of the ground photo, bridge by bridge, from the surrounding ground."""
    import cv2
    from PIL import ImageDraw
    lon, lat = en_to_lonlat(deck[:, 0].astype("f8") + ORIGIN_E, deck[:, 1].astype("f8") + ORIGIN_N)
    mx, my = merc_px(lon, lat, ORTHO_Z)
    px = np.column_stack((mx - ox, my - oy)).reshape(-1, 3, 2)
    mask = Image.new("L", ortho.size, 0)
    d = ImageDraw.Draw(mask)
    for tri in px:
        d.polygon([tuple(p) for p in tri], fill=255)
    m = np.asarray(mask)
    pad = int(round(pad_m / 0.38))  # z18 is about 0.38 m per pixel here
    m = cv2.dilate(m, np.ones((2 * pad + 1, 2 * pad + 1), np.uint8))
    img = np.asarray(ortho).copy()
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m)
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        x0, y0 = max(x - 40, 0), max(y - 40, 0)
        x1, y1 = min(x + w + 40, img.shape[1]), min(y + h + 40, img.shape[0])
        sub = np.ascontiguousarray(img[y0:y1, x0:x1])
        sm = np.ascontiguousarray(m[y0:y1, x0:x1])
        img[y0:y1, x0:x1] = mirror_fill(sub, sm)
    print("decks erased from ground:", n - 1, "areas,", int((m > 0).sum()), "px", flush=True)
    return Image.fromarray(img)


def terrain_mesh(ox, oy, W, H):
    t = np.load(WORK / "terrain.npz")
    z = t["z"]; e0 = float(t["e0"]); n0 = float(t["n0"]); s = float(t["step"])
    h, w = z.shape
    E, N = np.meshgrid(e0 + np.arange(w) * s, n0 + np.arange(h) * s)
    lon, lat = en_to_lonlat(E, N)
    mx, my = merc_px(lon, lat, ORTHO_Z)
    v = np.dstack((E - ORIGIN_E, N - ORIGIN_N, z, (mx - ox) / W, (my - oy) / H)).astype("f4")
    i = np.arange(h * w, dtype=np.uint32).reshape(h, w)
    a, b, c, d = i[:-1, :-1].ravel(), i[:-1, 1:].ravel(), i[1:, :-1].ravel(), i[1:, 1:].ravel()
    idx = np.column_stack((a, b, c, b, d, c)).ravel()
    return v.reshape(-1, 5)[idx]  # flat triangles


class Textures:
    def __init__(self, ctx, names):
        self.ctx, self.names = ctx, names
        self.zip = zipfile.ZipFile(BATI_ZIP)
        self.lru = OrderedDict()
        self.flat = {}

    def _upload(self, im):
        t = self.ctx.texture(im.size, 3, im.tobytes())
        t.build_mipmaps()
        t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        t.anisotropy = 8.0
        t.repeat_x = t.repeat_y = True
        return t

    def get(self, i):
        if i in self.lru:
            self.lru.move_to_end(i)
            return self.lru[i]
        im = Image.open(io.BytesIO(self.zip.read(str(self.names[i])))).convert("RGB")
        if max(im.size) > MAX_TEX:
            im.thumbnail((MAX_TEX, MAX_TEX), Image.BILINEAR)
        # CityGML v runs up from the bottom; the image's first row is its top.
        t = self._upload(im.transpose(Image.FLIP_TOP_BOTTOM))
        self.lru[i] = t
        if len(self.lru) > 4000:
            self.lru.popitem(last=False)[1].release()
        return t

    def colour(self, rgb):
        if rgb not in self.flat:
            self.flat[rgb] = self._upload(Image.new("RGB", (2, 2), rgb))
        return self.flat[rgb]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="lon,lat: render one frame centred here, to data/work/test.jpg")
    ap.add_argument("--lines", action="store_true", help="also write frames_line/: straight-line guide (building edges "
                    "and a window grid) for the painter")
    ap.add_argument("--kinds", action="store_true", help="also write frames_kind/: white ground (255), grey bridges (128), "
                    "walls (64), roofs (0), so 2D map data (roads, rivers) is only drawn where the ground is really visible")
    ap.add_argument("--heights", action="store_true", help="also write frames_height/: 16-bit PNG, height of the "
                    "visible surface above sea level in cm (0 = empty), for car hiding, tree crowns and patch repair")
    args = ap.parse_args()
    t0 = time.time()
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)

    w, s, e, n = PILOT_LONLAT
    cs = [lonlat_to_en(a, b) for a in (w, e) for b in (s, n)]
    le0, le1 = min(c[0] for c in cs) - ORIGIN_E, max(c[0] for c in cs) - ORIGIN_E
    ln0, ln1 = min(c[1] for c in cs) - ORIGIN_N, max(c[1] for c in cs) - ORIGIN_N

    ortho, ox, oy = load_ortho()
    print("ortho", ortho.size, f"{time.time() - t0:.0f}s", flush=True)

    def upload(im):
        t = ctx.texture(im.size, 3, im.tobytes())
        t.build_mipmaps(); t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR); t.anisotropy = 8.0
        return t

    # Decks keep the real photo; the ground under them gets the deck painted out,
    # otherwise a ghost of the road appears on the valley floor beneath every bridge.
    deck_tex = None
    bridges_path = WORK / "bridges.npz"
    if bridges_path.exists() and len(np.load(bridges_path)["deck"]):
        deck_tex = upload(ortho)
        _b = np.load(bridges_path)
        _all = np.concatenate([_b["deck"]] + ([_b["deck_red"]] if "deck_red" in _b.files and len(_b["deck_red"]) else []))
        ground = erase_decks(ortho, _all, ox, oy)
        otex = upload(ground)
        del ground
    else:
        otex = upload(ortho)
    ter = terrain_mesh(ox, oy, *ortho.size)
    del ortho
    tmask = ((ter[:, 0] >= le0) & (ter[:, 0] <= le1) & (ter[:, 1] >= ln0) & (ter[:, 1] <= ln1)).reshape(-1, 3).all(axis=1)
    ter = ter.reshape(-1, 3, 5)[tmask].reshape(-1, 5)
    tbuf = ctx.buffer(ter.tobytes())
    tvao = ctx.vertex_array(prog, [(tbuf, "3f 2f", "p", "uv")])

    # Bridges: bare-earth terrain has none, so decks and piers are rebuilt from OSM centrelines.
    deck_vao = None
    red_vao = None
    solids = []
    extra_bufs = []  # bridge decks and piers, also drawn in the height pass
    bridges_path = WORK / "bridges.npz"
    if bridges_path.exists():
        br = np.load(bridges_path)
        dp = br["deck"]
        if len(dp):
            dlon, dlat = en_to_lonlat(dp[:, 0].astype("f8") + ORIGIN_E, dp[:, 1].astype("f8") + ORIGIN_N)
            dmx, dmy = merc_px(dlon, dlat, ORTHO_Z)
            dv = np.column_stack((dp, (dmx - ox) / deck_tex.width, (dmy - oy) / deck_tex.height)).astype("f4")
            deck_buf = ctx.buffer(dv.tobytes())
            deck_vao = ctx.vertex_array(prog, [(deck_buf, "3f 2f", "p", "uv")])
            extra_bufs.append(deck_buf)
        red_vao = None
        if "deck_red" in br.files and len(br["deck_red"]):
            rv = np.column_stack((br["deck_red"], np.zeros((len(br["deck_red"]), 2)))).astype("f4")
            rbuf = ctx.buffer(rv.tobytes())
            red_vao = ctx.vertex_array(prog, [(rbuf, "3f 2f", "p", "uv")])
            extra_bufs.append(rbuf)
        sp, sc = br["solid"], br["solid_col"]
        for col in np.unique(sc, axis=0):
            pts = sp[(sc == col).all(axis=1)]
            sv = np.column_stack((pts, np.zeros((len(pts), 2)))).astype("f4")
            sbuf = ctx.buffer(sv.tobytes())
            solids.append((tuple(int(c) for c in col), ctx.vertex_array(prog, [(sbuf, "3f 2f", "p", "uv")])))
            extra_bufs.append(sbuf)
        print("bridges: deck verts", len(dp), "solid verts", len(sp), flush=True)

    d = np.load(WORK / "buildings.npz")
    tris, tex, kind, bld = d["tris"], d["tri_tex"], d["tri_kind"], d["tri_bld"]
    names = d["textures"]; g = d["bld_ground"]
    inside = (g[:, 0] >= le0) & (g[:, 0] <= le1) & (g[:, 1] >= ln0) & (g[:, 1] <= ln1)
    m = inside[bld] & (kind != 0)
    tris, tex, kind = tris[m], tex[m], kind[m]
    print("buildings", int(inside.sum()), "tris", len(tris), f"{time.time() - t0:.0f}s", flush=True)
    order = np.lexsort((kind, tex))
    tris, tex, kind = tris[order], tex[order], kind[order]
    tsx = (tris[..., 0] + tris[..., 1]) * R
    tf = (-tris[..., 0] + tris[..., 1]) * R
    tsy = tf * 0.5 + tris[..., 2] * math.cos(ELEV)
    bx0, bx1, by0, by1 = tsx.min(1), tsx.max(1), tsy.min(1), tsy.max(1)

    sxs = np.concatenate((tsx.ravel(), (ter[:, 0] + ter[:, 1]) * R))
    tersy = (-ter[:, 0] + ter[:, 1]) * R * 0.5 + ter[:, 2] * math.cos(ELEV)
    sys_ = np.concatenate((tsy.ravel(), tersy))
    mpp = METRES_PER_PIXEL
    pad = 60.0
    sx0, sx1, sy0, sy1 = sxs.min() - pad, sxs.max() + pad, sys_.min() - pad, sys_.max() + pad
    cols = math.ceil((sx1 - sx0) / mpp / FRAME); rows = math.ceil((sy1 - sy0) / mpp / FRAME)
    all_f = (-tris[..., 0] + tris[..., 1]) * R * math.cos(ELEV) - tris[..., 2] * 0.5
    dr = (float(all_f.min()) - 2000, float(all_f.max()) + 2000)
    prog["dr"].value = dr
    print("mosaic", cols * FRAME, rows * FRAME, "px;", cols, "x", rows, "frames", flush=True)

    fbo_ms = ctx.framebuffer(ctx.renderbuffer((FRAME, FRAME), 4, samples=4), ctx.depth_renderbuffer((FRAME, FRAME), samples=4))
    fbo = ctx.framebuffer(ctx.renderbuffer((FRAME, FRAME), 4))
    texs = Textures(ctx, names)
    span = FRAME * mpp
    if args.lines:
        gprog = ctx.program(vertex_shader=VS_G, fragment_shader=FS_G)
        gprog["dr"].value = dr
        g_fbo = ctx.framebuffer(ctx.renderbuffer((FRAME, FRAME), 4, dtype="f4"), ctx.depth_renderbuffer((FRAME, FRAME)))
        g_ter = ctx.vertex_array(gprog, [(tbuf, "3f 2x4", "p")])
    if args.heights:
        hprog = ctx.program(vertex_shader=VS_G, fragment_shader=FS_H)
        hprog["dr"].value = dr
        h_fbo = ctx.framebuffer(ctx.renderbuffer((FRAME, FRAME), 4, dtype="f4"), ctx.depth_renderbuffer((FRAME, FRAME)))
        h_static = [ctx.vertex_array(hprog, [(b, "3f 2x4", "p")]) for b in [tbuf] + extra_bufs]

    def draw_heights(fx0, fy0):
        """Height pass for one frame: cm above sea level of the visible surface, 0 where nothing is drawn."""
        fx1, fy1 = fx0 + span, fy0 + span
        hprog["frame"].value = (fx0, fy0, fx1, fy1)
        h_fbo.use()
        h_fbo.clear(0, 0, 0, 0)
        for vao_h in h_static:
            vao_h.render()
        hit = np.where((bx1 >= fx0) & (bx0 <= fx1) & (by1 >= fy0) & (by0 <= fy1))[0]
        if len(hit):
            buf = ctx.buffer(tris[hit].tobytes())
            vao = ctx.vertex_array(hprog, [(buf, "3f 2x4", "p")])
            vao.render()
            vao.release(); buf.release()
        z = np.frombuffer(h_fbo.read(components=4, dtype="f4"), np.float32).reshape(FRAME, FRAME, 4)[::-1, :, 0]
        cm = np.clip(np.round(z * 100), 0, 65535).astype(np.uint16)
        return Image.fromarray(cm)  # 16-bit greyscale PNG

    def draw_lines(fx0, fy0):
        """Straight-line guide for one frame: white paper, black edges, grey windows."""
        fx1, fy1 = fx0 + span, fy0 + span
        gprog["frame"].value = (fx0, fy0, fx1, fy1)
        g_fbo.use()
        g_fbo.clear(0, 0, 1e9, 0)
        gprog["is_wall"].value = 0
        g_ter.render()
        hit = np.where((bx1 >= fx0) & (bx0 <= fx1) & (by1 >= fy0) & (by0 <= fy1))[0]
        if len(hit):
            buf = ctx.buffer(tris[hit].tobytes())
            vao = ctx.vertex_array(gprog, [(buf, "3f 2x4", "p")])
            hk = kind[hit]
            cut = np.flatnonzero(hk[1:] != hk[:-1]) + 1
            for a, b in zip(np.r_[0, cut], np.r_[cut, len(hit)]):
                gprog["is_wall"].value = int(hk[a] == 2)
                vao.render(moderngl.TRIANGLES, vertices=int(b - a) * 3, first=int(a) * 3)
            vao.release(); buf.release()
        g = np.frombuffer(g_fbo.read(components=4, dtype="f4"), np.float32).reshape(FRAME, FRAME, 4)[::-1]
        nx, ny, dep, w = g[..., 0], g[..., 1], g[..., 2], g[..., 3]
        empty = dep > 1e8
        wall = w >= 2
        win = (w - 2 * wall) > 0.5
        # edges: normal or depth jumps between neighbours
        e = np.zeros((FRAME, FRAME), bool)
        for ax in (0, 1):
            dn = np.abs(np.diff(nx, axis=ax)) + np.abs(np.diff(ny, axis=ax))
            dd = np.abs(np.diff(np.where(empty, 0, dep), axis=ax))
            j = (dn > 0.35) | (dd > 1.2)
            if ax == 0:
                e[1:] |= j; e[:-1] |= j
            else:
                e[:, 1:] |= j; e[:, :-1] |= j
        out = np.full((FRAME, FRAME), 255, np.uint8)
        out[wall] = 235
        out[win & wall] = 120
        out[e] = 0
        out[empty] = 255
        return Image.fromarray(out)

    def draw(fx0, fy0, kinds=False):
        fx1, fy1 = fx0 + span, fy0 + span
        prog["frame"].value = (fx0, fy0, fx1, fy1)
        fbo_ms.use()
        ctx.clear(BG[0] / 255, BG[1] / 255, BG[2] / 255, 1)
        (texs.colour((255, 255, 255)) if kinds else otex).use(0)
        tvao.render()
        if deck_vao is not None:
            (texs.colour((128, 128, 128)) if kinds else deck_tex).use(0)
            deck_vao.render()
        if red_vao is not None:
            texs.colour((128, 128, 128) if kinds else (112, 114, 118)).use(0)  # plain asphalt
            red_vao.render()
        for col, vao_s in solids:
            texs.colour((128, 128, 128) if kinds else col).use(0)
            vao_s.render()
        hit = np.where((bx1 >= fx0) & (bx0 <= fx1) & (by1 >= fy0) & (by0 <= fy1))[0]
        if not len(hit):
            return
        buf = ctx.buffer(tris[hit].tobytes())
        vao = ctx.vertex_array(prog, [(buf, "3f 2f", "p", "uv")])
        ht, hk = tex[hit], kind[hit]
        # Split on texture; also on kind where it matters (flat colours, and the kinds pass: walls and roofs of a
        # building often share one texture atlas).
        cut = np.flatnonzero((ht[1:] != ht[:-1]) | (((ht[1:] < 0) | kinds) & (hk[1:] != hk[:-1]))) + 1
        for a, b in zip(np.r_[0, cut], np.r_[cut, len(hit)]):
            ti = int(ht[a])
            if kinds:
                t = texs.colour((64, 64, 64) if hk[a] == 2 else (0, 0, 0))  # walls 64, roofs 0
            else:
                t = texs.get(ti) if ti >= 0 else texs.colour((150, 92, 74) if hk[a] == 1 else (205, 198, 186))
            t.use(0)
            vao.render(moderngl.TRIANGLES, vertices=int(b - a) * 3, first=int(a) * 3)
        vao.release(); buf.release()

    def read():
        ctx.copy_framebuffer(fbo, fbo_ms)
        return Image.frombytes("RGBA", (FRAME, FRAME), fbo.read(components=4)).convert("RGB").transpose(Image.FLIP_TOP_BOTTOM)

    if args.only:
        lon, lat = map(float, args.only.split(","))
        ee, nn = lonlat_to_en(lon, lat)
        ee -= ORIGIN_E; nn -= ORIGIN_N
        t = np.load(WORK / "terrain.npz")
        zz = float(t["z"][int((nn + ORIGIN_N - float(t["n0"])) / float(t["step"])), int((ee + ORIGIN_E - float(t["e0"])) / float(t["step"]))])
        cx, cy = (ee + nn) * R, (-ee + nn) * R * 0.5 + zz * math.cos(ELEV)
        draw(cx - span / 2, cy - span / 2)
        read().save(WORK / "test.jpg", quality=92)
        if args.lines:
            draw_lines(cx - span / 2, cy - span / 2).save(WORK / "test_lines.png")
        if args.heights:
            draw_heights(cx - span / 2, cy - span / 2).save(WORK / "test_height.png")
        print("test frame", f"{time.time() - t0:.0f}s")
        return

    out = WORK / "frames"
    out.mkdir(exist_ok=True)
    lout = WORK / "frames_line"
    if args.lines:
        lout.mkdir(exist_ok=True)
    kout = WORK / "frames_kind"
    if args.kinds:
        kout.mkdir(exist_ok=True)
    hout = WORK / "frames_height"
    if args.heights:
        hout.mkdir(exist_ok=True)
    only_height = args.heights and (out / "0_0.jpg").exists() and not (args.kinds or args.lines)
    for r in range(rows):
        for c in range(cols):
            if args.heights:
                draw_heights(sx0 + c * span, sy1 - (r + 1) * span).save(hout / f"{c}_{r}.png")
                if only_height:  # colour frames already exist: just add the height pass
                    continue
            draw(sx0 + c * span, sy1 - (r + 1) * span)
            read().save(out / f"{c}_{r}.jpg", quality=95, subsampling=0)
            if args.kinds:
                draw(sx0 + c * span, sy1 - (r + 1) * span, kinds=True)
                read().convert("L").save(kout / f"{c}_{r}.png")
            if args.lines:
                draw_lines(sx0 + c * span, sy1 - (r + 1) * span).save(lout / f"{c}_{r}.png")
        print(f"row {r + 1}/{rows} {time.time() - t0:.0f}s", flush=True)
    (WORK / "mosaic.json").write_text(json.dumps({"cols": cols, "rows": rows, "frame": FRAME, "mpp": mpp, "sx0": float(sx0), "sy1": float(sy1)}))
    print("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
