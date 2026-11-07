"""Layered map, step 5: shadows on the ground (L6) from the 3D buildings, the terrain and the tree crowns, for a
real sun position.

A shadow map is rendered from the sun (orthographic, depth only) with the buildings, bridge solids, terrain and one
small sphere per surveyed tree crown. Every ground pixel of the layer (from the terrain pass) is then tested
against it. The result is a soft alpha mask; the viewer draws it in a cool shadow colour over the ground, under
the buildings and trees.

  shadows.py [b00] --when "2026-07-15 13:30" [--k K] [--name midday]   (local time, Luxembourg summer time UTC+2)
"""
import argparse
import datetime as dt
import json
import math

import cv2
import moderngl
import numpy as np
from PIL import Image

from layers_common import ORIGIN_E, ORIGIN_N, WORK, block, inputs_dir, out_dir, preview, POC_IMG
from terrain_pass import block_en, ground_pass

LAT, LON = 49.611, 6.131


def sun(when, utc_offset=2):
    """Sun azimuth (deg from north, clockwise) and elevation (deg) at Luxembourg City."""
    t = dt.datetime.strptime(when, "%Y-%m-%d %H:%M") - dt.timedelta(hours=utc_offset)
    doy = t.timetuple().tm_yday
    g = 2 * math.pi / 365 * (doy - 1 + (t.hour - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                    - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = t.hour * 60 + t.minute + eqt + 4 * LON
    ha = math.radians(tst / 4 - 180)
    lat = math.radians(LAT)
    cz = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    el = math.degrees(math.asin(cz))
    az = math.degrees(math.atan2(math.sin(ha), math.cos(ha) * math.sin(lat) - math.tan(decl) * math.cos(lat))) + 180
    return az % 360, el


VS = """#version 410
in vec3 p;
uniform mat3 rot; uniform vec4 box; uniform vec2 dr;
void main(){
  vec3 q = rot * p;
  gl_Position = vec4((q.x-box.x)/(box.z-box.x)*2.-1., (q.y-box.y)/(box.w-box.y)*2.-1., (q.z-dr.x)/(dr.y-dr.x)*2.-1., 1.);
}"""
FS = """#version 410
out vec4 c; void main(){ c = vec4(1.); }"""


def sun_frame(az, el):
    """Rotation into sun space: x, y across the sun's rays, z along them (smaller = nearer the sun)."""
    a, e = math.radians(az), math.radians(el)
    d = np.array((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))  # towards the sun
    z = -d
    x = np.cross((0, 0, 1), z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.array((x, y, z), np.float32)


def icosphere():
    t = (1 + 5 ** 0.5) / 2
    v = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
                  (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    f = np.array([(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
                  (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
                  (6, 2, 10), (8, 6, 7), (9, 8, 1)])
    return v[f]  # (20, 3, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bid", nargs="?", default="b00")
    ap.add_argument("--when", default="2026-07-15 13:30")
    ap.add_argument("--name", default="midday")
    ap.add_argument("--k", type=float, default=5120 / 6000)
    ap.add_argument("--res", type=float, default=0.4, help="shadow map m per texel")
    args = ap.parse_args()
    b = block(args.bid)
    az, el = sun(args.when)
    print(f"sun {args.when}: azimuth {az:.0f}, elevation {el:.0f}")
    e0, e1, n0, n1 = block_en(b, 300)
    le0, le1, ln0, ln1 = e0 - ORIGIN_E, e1 - ORIGIN_E, n0 - ORIGIN_N, n1 - ORIGIN_N
    geo = []
    # buildings
    B = np.load(WORK / "buildings.npz")
    tris, g = B["tris"][..., :3].astype(np.float32), B["bld_ground"]
    inside = (g[:, 0] >= le0) & (g[:, 0] <= le1) & (g[:, 1] >= ln0) & (g[:, 1] <= ln1)
    geo.append(tris[inside[B["tri_bld"]]].reshape(-1, 3))
    br = np.load(WORK / "bridges.npz")
    for key in ("solid", "deck", "deck_red"):
        if key in br.files and len(br[key]):
            geo.append(br[key][:, :3].astype(np.float32))
    # terrain (it shades itself at low sun)
    t = np.load(WORK / "terrain.npz")
    z, te0, tn0, ts = t["z"], float(t["e0"]), float(t["n0"]), float(t["step"])
    ix0, ix1 = max(int((e0 - te0) / ts), 0), min(int((e1 - te0) / ts) + 1, z.shape[1])
    iy0, iy1 = max(int((n0 - tn0) / ts), 0), min(int((n1 - tn0) / ts) + 1, z.shape[0])
    zz = z[iy0:iy1, ix0:ix1][::2, ::2]
    h, w = zz.shape
    E, N = np.meshgrid(te0 + (ix0 + np.arange(w) * 2) * ts - ORIGIN_E, tn0 + (iy0 + np.arange(h) * 2) * ts - ORIGIN_N)
    v = np.dstack((E, N, zz - 0.8)).astype(np.float32)  # a little below the surface: no self-shadow acne
    a_, b_, c_, d_ = v[:-1, :-1], v[:-1, 1:], v[1:, :-1], v[1:, 1:]
    geo.append(np.stack((a_, b_, c_, b_, d_, c_), 2).reshape(-1, 3))
    # tree crowns: one sphere each, centred a crown-radius below the top
    trees = json.loads((inputs_dir(args.bid) / "trees_lidar2024.json").read_text())
    ico = icosphere()
    from layers_common import ground_z
    te = np.array([tr["e"] for tr in trees]); tn = np.array([tr["n"] for tr in trees])
    zg = ground_z(te, tn)
    for tr, zg_ in zip(trees, zg):
        r = max(1.0, tr["cmean"]) * 0.95
        c = np.array((tr["e"] - ORIGIN_E, tr["n"] - ORIGIN_N, zg_ + max(tr["h"] - r, r * 0.8)), np.float32)
        sph = ico * np.array((r, r, r * 0.9), np.float32) + c
        geo.append(sph.reshape(-1, 3))
        # trunk: a thin upright prism
        tw = 0.25
        for dx, dy in ((tw, 0), (0, tw)):
            p0 = c - (dx, dy, 0); p1 = c + (dx, dy, 0)
            g0 = p0.copy(); g0[2] = zg_; g1 = p1.copy(); g1[2] = zg_
            geo.append(np.array((g0, g1, p1, g0, p1, p0), np.float32))
    V = np.concatenate(geo).astype("f4")
    rot = sun_frame(az, el)
    q = V @ rot.T
    # sun-space box from the block's ground area
    corners = np.array([(le0, ln0, 250), (le1, ln0, 250), (le0, ln1, 250), (le1, ln1, 250),
                        (le0, ln0, 400), (le1, ln1, 400), (le1, ln0, 400), (le0, ln1, 400)], np.float32) @ rot.T
    bx0, by0 = corners[:, 0].min(), corners[:, 1].min()
    bx1, by1 = corners[:, 0].max(), corners[:, 1].max()
    TW = min(16384, int((bx1 - bx0) / args.res)); TH = min(16384, int((by1 - by0) / args.res))
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
    prog["rot"].write(rot.T.astype("f4").tobytes())  # GLSL is column-major
    prog["box"].value = (float(bx0), float(by0), float(bx1), float(by1))
    dr = (float(q[:, 2].min()) - 10, float(q[:, 2].max()) + 10)
    prog["dr"].value = dr
    vbo = ctx.buffer(V.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, "3f", "p")])
    dtex = ctx.depth_texture((TW, TH))
    fbo = ctx.framebuffer(depth_attachment=dtex)
    fbo.use(); fbo.clear(depth=1.0)
    vao.render()
    depth = np.frombuffer(dtex.read(), np.float32).reshape(TH, TW)
    ctx.release()
    print("shadow map", TW, TH, "tris", len(V) // 3)
    # test every ground pixel of the layer
    G = ground_pass(b, args.k)
    ok = ~np.isnan(G[..., 0])
    P = np.nan_to_num(G).reshape(-1, 3) @ rot.T
    u = (P[:, 0] - bx0) / (bx1 - bx0) * TW
    vv = (P[:, 1] - by0) / (by1 - by0) * TH
    dz = (P[:, 2] - dr[0]) / (dr[1] - dr[0])
    ui = np.clip(u.astype(int), 0, TW - 1); vi = np.clip(vv.astype(int), 0, TH - 1)
    occ = depth[vi, ui]
    # slope-scaled bias: at a low sun one shadow-map texel covers a long stretch of ground
    bias = (0.5 + 1.5 * args.res / math.tan(math.radians(max(el, 3)))) / (dr[1] - dr[0])
    sh = (dz > occ + bias).reshape(G.shape[:2]) & ok
    # night or sun below the horizon: no shadows
    if el <= 1:
        sh[:] = False
    a = cv2.GaussianBlur(sh.astype(np.float32), (0, 0), 0.9)
    d = out_dir(args.bid) / "shadows"
    d.mkdir(exist_ok=True)
    Image.fromarray((a * 255).astype(np.uint8)).save(d / f"L6_shadow_{args.name}.png")
    (d / f"sun_{args.name}.json").write_text(json.dumps({"when": args.when, "azimuth": az, "elevation": el}))
    print(d / f"L6_shadow_{args.name}.png", f"{sh.mean():.0%} in shadow")


if __name__ == "__main__":
    main()
