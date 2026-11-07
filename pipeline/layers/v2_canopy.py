"""Layered map v2, layer 3: the vegetation, from a 3D canopy of the surveyed trees.

Every tree of the LiDAR tree survey 2024 becomes a lumpy crown at its real place, height and crown width (never
enlarged), on a trunk, rendered in the map projection together with the terrain and the 3D buildings and bridges,
so the depth test decides per pixel what is in front: a crown hides a building only where it really stands in
front of it, and crowns behind a building or a ridge are trimmed. The crowns are shaded in green, lit from the upper
left, and then painted by the trained style in place (vegetation_paint), with the painted ground and buildings held
fixed around them as context.

  v2_canopy.py render [--k K]   -> b00_v2/canopy/canopy_k<K>.npz:
        vis     the tree drawn at each pixel (index + 1, 0 = none), after the depth test with buildings and terrain
        behind  what the pixel shows without the trees: 1 ground, 2 building or bridge (for the boundary checks and
                "keep landmarks clear")
        shade   the shaded crown colour for the painter (RGB)
        foot    for every tree pixel, the map row (layer px) of its trunk base, to sort trees and vehicles
        contact soft ground darkening under the crowns (0..1), drawn on the ground under buildings
        trees   the trees used (e, n, ground z, height, crown radius, kind)
"""
import argparse
import json
import math

import cv2
import moderngl
import numpy as np
from PIL import Image

from layers_common import MOSAIC, ORIGIN_E, ORIGIN_N, POC_IMG, WORK, block, en_to_map, ground_z, inputs_dir, preview
from terrain_pass import block_en
from v2_ground import v2_dir

PAINT = 5120
LIGHT = np.array((-0.62, 0.25, 0.74), np.float32)
LIGHT /= np.linalg.norm(LIGHT)

VS = """#version 410
in vec3 p;          // unit-sphere vertex (crowns) or world vertex (solids)
in vec4 ci;         // crown: centre e, n, z (local m), tree id
in vec4 cr;         // crown: radius xy, radius z, shape (0 round, 1 cone, 2 trunk), seed
uniform int mode;   // 0 solids (terrain, buildings), 1 crowns
uniform float solid_id;
uniform vec4 frame; uniform vec2 dr;
out vec3 wp; out vec3 nrm; flat out float tid; out float cz;
const float R = 0.70710678; const float SE = 0.5; const float CE = 0.8660254;
float h3(vec3 q){ return fract(sin(dot(q, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
void main(){
  vec3 w;
  if (mode == 0) { w = p; nrm = vec3(0., 0., 1.); tid = solid_id; cz = 0.; }
  else {
    vec3 u = p;
    float rr = cr.x, rz = cr.y;
    if (cr.z > 1.5) {            // trunk: a thin upright prism from the ground to the crown
      w = ci.xyz + vec3(u.x * rr, u.y * rr, (u.z * 0.5 + 0.5) * rz);
      nrm = normalize(vec3(u.xy, 0.));
      tid = -(ci.w + 10.); cz = 0.;
    } else {
      // lumpy crown: a few low-frequency bumps per tree, so neighbouring crowns read as clumps of leaves
      float s = cr.w;
      float bump = 0.10 * sin(dot(u, vec3(3.1, 1.7, 2.3)) + s * 6.3) + 0.08 * sin(dot(u, vec3(-2.2, 3.7, 1.1)) * 1.7 + s * 2.1)
                 + 0.05 * sin(dot(u, vec3(4.9, -3.3, 2.9)) * 1.3 + s * 9.7);
      vec3 q = u * (1. + bump);
      if (cr.z > 0.5) { float t = (q.z + 1.) * 0.5; q.xy *= mix(1.0, 0.18, pow(t, 1.15)); }
      else { q.z = q.z < 0. ? q.z * 0.8 : q.z; }       // flatter underside
      w = ci.xyz + vec3(q.x * rr, q.y * rr, q.z * rz);
      nrm = normalize(vec3(u.x / rr, u.y / rr, u.z / rz));
      tid = ci.w; cz = u.z;
    }
  }
  float sx = (w.x + w.y) * R; float f = (-w.x + w.y) * R;
  float sy = f * SE + w.z * CE; float d = f * CE - w.z * SE;
  gl_Position = vec4((sx-frame.x)/(frame.z-frame.x)*2.-1., (sy-frame.y)/(frame.w-frame.y)*2.-1., (d-dr.x)/(dr.y-dr.x)*2.-1., 1.);
  wp = w;
}"""
FS = """#version 410
in vec3 wp; in vec3 nrm; flat in float tid; in float cz;
layout(location = 0) out vec4 a;
layout(location = 1) out vec4 b;
void main(){
  vec3 fn = normalize(cross(dFdx(wp), dFdy(wp)));
  if (dot(fn, nrm) < 0.) fn = -fn;
  vec3 n = normalize(mix(nrm, fn, 0.35));
  a = vec4(tid, n);
  b = vec4(wp, cz);
}"""


def icosphere(sub=2):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7),
         (9, 8, 1)]
    for _ in range(sub):
        cache = {}

        def mid(i, j):
            key = (min(i, j), max(i, j))
            if key not in cache:
                m = v[i] + v[j]
                v.append(m / np.linalg.norm(m))
                cache[key] = len(v) - 1
            return cache[key]
        nf = []
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(v, np.float32), np.array(f, np.uint32)


def prism(n=6):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    v = []
    for a0, a1 in zip(ang, np.roll(ang, -1)):
        p0, p1 = (math.cos(a0), math.sin(a0)), (math.cos(a1), math.sin(a1))
        v += [(*p0, -1), (*p1, -1), (*p1, 1), (*p0, -1), (*p1, 1), (*p0, 1)]
    return np.array(v, np.float32)


def crown_params(tr):
    """Crown radius (m, from the survey's mean crown radius, never enlarged), crown half-depth, centre height above
    the ground, and shape."""
    h, r = tr["h"], max(0.8, tr["cmean"])
    con = tr["type"] == "conifer"
    if con:
        depth = min(0.85 * h, 4.5 * r)
    else:
        depth = min(0.68 * h, 3.0 * r)
    rz = depth / 2
    return r, rz, h - rz, 1.0 if con else 0.0


def load_trees(b):
    e0, e1, n0, n1 = block_en(b, 40)
    out = []
    for tr in json.loads((inputs_dir("b00") / "trees_lidar2024.json").read_text()):
        if e0 < tr["e"] < e1 and n0 < tr["n"] < n1 and tr["h"] >= 2.5:
            out.append(tr)
    return out


def render(k):
    b = block("b00")
    d = v2_dir("canopy")
    trees = load_trees(b)
    e = np.array([t["e"] for t in trees]); n = np.array([t["n"] for t in trees])
    gz = ground_z(e, n)
    par = np.array([crown_params(t) for t in trees], np.float32)
    rng = np.random.default_rng(17)
    N = len(trees)
    ids = np.arange(1, N + 1, dtype=np.float32)
    ci = np.column_stack((e - ORIGIN_E, n - ORIGIN_N, gz + par[:, 2], ids)).astype("f4")
    cr = np.column_stack((par[:, 0], par[:, 1], par[:, 3], rng.uniform(0, 1, N))).astype("f4")
    # trunks: from the ground to just inside the crown, 0.2-0.4 m thick
    bottom = par[:, 2] - par[:, 1] * 0.6
    ti = np.column_stack((e - ORIGIN_E, n - ORIGIN_N, gz - 0.3, ids)).astype("f4")
    tr_ = np.column_stack((np.clip(par[:, 0] * 0.07, 0.18, 0.4), np.clip(bottom + 0.3, 0.5, None), np.full(N, 2.0),
                           np.zeros(N))).astype("f4")
    print(N, "trees", flush=True)

    # solids: terrain, buildings, bridges (for the depth test only)
    eb0, eb1, nb0, nb1 = block_en(b, 60)
    T = np.load(WORK / "terrain.npz")
    TZ, TE0, TN0, TS = T["z"], float(T["e0"]), float(T["n0"]), float(T["step"])
    ix0, ix1 = max(int((eb0 - TE0) / TS), 0), min(int((eb1 - TE0) / TS) + 2, TZ.shape[1])
    iy0, iy1 = max(int((nb0 - TN0) / TS), 0), min(int((nb1 - TN0) / TS) + 2, TZ.shape[0])
    z = TZ[iy0:iy1, ix0:ix1].astype(np.float32)
    hh, ww = z.shape
    E, Nn = np.meshgrid(TE0 + (ix0 + np.arange(ww)) * TS - ORIGIN_E, TN0 + (iy0 + np.arange(hh)) * TS - ORIGIN_N)
    tv = np.dstack((E, Nn, z)).reshape(-1, 3).astype("f4")
    i = np.arange(hh * ww, dtype=np.uint32).reshape(hh, ww)
    a_, b_, c_, d_ = i[:-1, :-1].ravel(), i[:-1, 1:].ravel(), i[1:, :-1].ravel(), i[1:, 1:].ravel()
    tidx = np.column_stack((a_, b_, c_, b_, d_, c_)).ravel().astype("u4")
    bz = np.load(WORK / "buildings.npz")
    tris, kind = bz["tris"][..., :3], bz["tri_kind"]
    m = (kind != 0) & ((tris[..., 0] + ORIGIN_E > eb0) & (tris[..., 0] + ORIGIN_E < eb1)
                       & (tris[..., 1] + ORIGIN_N > nb0) & (tris[..., 1] + ORIGIN_N < nb1)).any(1)
    btris = tris[m].reshape(-1, 3).astype("f4")
    br = np.load(WORK / "bridges.npz")
    brt = np.concatenate([br[kk] for kk in ("deck", "deck_red", "solid") if kk in br.files and len(br[kk])]).astype("f4")

    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
    f_all = (-tv[:, 0] + tv[:, 1]) * (1 / math.sqrt(2))
    dep = f_all * math.cos(math.radians(30)) - tv[:, 2] * 0.5
    prog["dr"].value = (float(dep.min()) - 300, float(dep.max()) + 300)
    zero_inst = ctx.buffer(np.zeros(8, "f4").tobytes())

    def solid_vao(verts, idx=None):
        vb = ctx.buffer(verts.tobytes())
        ib = ctx.buffer(idx.tobytes()) if idx is not None else None
        return ctx.vertex_array(prog, [(vb, "3f", "p"), (zero_inst, "4f 4f/i", "ci", "cr")], index_buffer=ib)
    v_ter = solid_vao(tv, tidx)
    v_bld = solid_vao(btris)
    v_br = solid_vao(brt)
    sv, sf = icosphere(2)
    sphere_vb = ctx.buffer(sv.tobytes()); sphere_ib = ctx.buffer(sf.ravel().tobytes())
    inst = ctx.buffer(np.column_stack((ci, cr)).astype("f4").tobytes())
    v_crown = ctx.vertex_array(prog, [(sphere_vb, "3f", "p"), (inst, "4f 4f/i", "ci", "cr")], index_buffer=sphere_ib)
    pv = ctx.buffer(prism().tobytes())
    tinst = ctx.buffer(np.column_stack((ti, tr_)).astype("f4").tobytes())
    v_trunk = ctx.vertex_array(prog, [(pv, "3f", "p"), (tinst, "4f 4f/i", "ci", "cr")])

    W = H = round(b["w"] * k)
    tile = 2048
    mpp = MOSAIC["mpp"] / k
    A = np.zeros((H, W, 4), np.float32); B = np.zeros((H, W, 4), np.float32)
    behind = np.zeros((H, W), np.uint8)
    fbo = ctx.framebuffer([ctx.renderbuffer((tile, tile), 4, dtype="f4"), ctx.renderbuffer((tile, tile), 4, dtype="f4")],
                          ctx.depth_renderbuffer((tile, tile)))
    fbo.use()
    for ty in range(0, H, tile):
        for tx in range(0, W, tile):
            fx0 = MOSAIC["sx0"] + b["x0"] * MOSAIC["mpp"] + tx * mpp
            fy1 = MOSAIC["sy1"] - b["y0"] * MOSAIC["mpp"] - ty * mpp
            prog["frame"].value = (fx0, fy1 - tile * mpp, fx0 + tile * mpp, fy1)
            hh_, ww_ = min(tile, H - ty), min(tile, W - tx)
            for with_trees in (False, True):
                fbo.clear(0, 0, 0, 0)
                prog["mode"].value = 0
                prog["solid_id"].value = -1.0; v_ter.render()
                prog["solid_id"].value = -2.0; v_bld.render(); v_br.render()
                if with_trees:
                    prog["mode"].value = 1
                    v_crown.render(instances=N)
                    v_trunk.render(instances=N)
                ga = np.frombuffer(fbo.read(components=4, dtype="f4", attachment=0), np.float32).reshape(tile, tile, 4)[::-1]
                if not with_trees:
                    behind[ty:ty + hh_, tx:tx + ww_] = np.where(ga[:hh_, :ww_, 0] < -1.5, 2, np.where(ga[:hh_, :ww_, 0] < -0.5, 1, 0))
                else:
                    gb = np.frombuffer(fbo.read(components=4, dtype="f4", attachment=1), np.float32).reshape(tile, tile, 4)[::-1]
                    A[ty:ty + hh_, tx:tx + ww_] = ga[:hh_, :ww_]
                    B[ty:ty + hh_, tx:tx + ww_] = gb[:hh_, :ww_]
    ctx.release()
    tid = A[..., 0]
    crown = tid > 0.5
    trunk = (tid < -2.5)
    vis = np.where(crown, tid, np.where(trunk, -tid - 10, 0)).round().astype(np.int32)
    # shading for the painter: lambert from the upper left, darker underside and inner gaps, leaf grain
    nrm = A[..., 1:4]
    lam = np.clip(nrm @ LIGHT, 0, 1)
    cz = B[..., 3]
    ao = np.clip(0.62 + 0.38 * (cz + 1) / 2, 0, 1)
    grain_rng = np.random.default_rng(4)
    gr = (cv2.GaussianBlur(grain_rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.8 * k * 4 / 3.4) * 0.10
          + cv2.GaussianBlur(grain_rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 2.5 * k * 4 / 3.4) * 0.12)
    t = np.clip(0.18 + 0.82 * lam * ao + gr, 0, 1.15)
    kinds = np.array([{"conifer": 1, "deciduous_red": 2}.get(tr["type"], 0) for tr in trees])
    red = np.zeros(N + 1, bool)
    red[1:] = (kinds == 2) & (rng.uniform(0, 1, N) < 0.3)
    con = np.zeros(N + 1, bool); con[1:] = kinds == 1
    hue = np.zeros((N + 1, 3), np.float32)
    hue[1:] = rng.uniform(-1, 1, (N, 1)) * np.array((10, 8, 4))      # a little colour variety per tree
    dark = np.array((28, 44, 24), np.float32); light = np.array((150, 178, 84), np.float32)
    col = dark + (light - dark) * t[..., None]
    vv = np.clip(vis, 0, N)
    col += hue[vv]
    cmask = con[vv] & crown
    col[cmask] = (np.array((20, 40, 30), np.float32) + (np.array((96, 132, 84), np.float32) - (20, 40, 30)) * t[cmask][:, None])
    rmask = red[vv] & crown
    col[rmask] = (np.array((48, 26, 30), np.float32) + (np.array((150, 88, 78), np.float32) - (48, 26, 30)) * t[rmask][:, None])
    col[trunk] = (84, 66, 50)
    col[vis == 0] = 0
    # trunk-base rows
    bx, by = en_to_map(e, n, gz)
    rows = np.zeros(N + 1, np.float32); rows[1:] = (by - b["y0"]) * k
    cols_ = np.zeros(N + 1, np.float32); cols_[1:] = (bx - b["x0"]) * k
    foot = np.where(vis > 0, rows[vv], 0).astype(np.float32)
    # contact darkening: each crown's footprint on the ground (ellipse, 2:1), soft
    contact = np.zeros((H, W), np.float32)
    rpx = par[:, 0] * 4 * k * 0.9
    for j in range(N):
        cx, cy, r = cols_[j + 1], rows[j + 1], rpx[j]
        if -50 < cx < W + 50 and -50 < cy < H + 50:
            cv2.ellipse(contact, (int(cx * 4), int(cy * 4)), (max(1, int(r * 4)), max(1, int(r * 2))), 0, 0, 360, 1.0, -1,
                        cv2.LINE_AA, shift=2)
    contact = cv2.GaussianBlur(contact, (0, 0), 1.5 * 4 * k)
    np.savez_compressed(d / f"canopy_k{round(k * 100)}.npz", vis=vis, behind=behind, shade=col.clip(0, 255).astype(np.uint8),
                        foot=foot, contact=contact.astype(np.float16), crown=crown, trunk=trunk,
                        trees=np.column_stack((e, n, gz, par)).astype(np.float32), k=k)
    print("canopy", f"{crown.mean():.1%} of the block in crowns,", f"{(crown & (behind == 2)).mean():.2%} in front of buildings",
          flush=True)
    sh = col.clip(0, 255).astype(np.uint8)
    preview(sh, POC_IMG / "v2_s3_canopy_render.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--k", type=float, default=PAINT / 6000)
    a = ap.parse_args()
    if a.cmd == "render":
        render(a.k)
