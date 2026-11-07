"""Bare-earth terrain pass for one block: for every layer pixel, the ground point (LUREF e, n, z) it shows.

Same projection as render.py, but only the terrain (no buildings, no bridge decks), so the ground layers can be
draped: land cover is drawn on a flat map grid in metres and looked up per pixel, and slopes come from the
terrain's own normals. Pixels with no terrain get NaN.
"""
import math

import moderngl
import numpy as np

from layers_common import MOSAIC, ORIGIN_E, ORIGIN_N, TE0, TN0, TS, TZ, map_to_en

VS = """#version 410
in vec3 p;
uniform vec4 frame; uniform vec2 dr;
out vec3 wp;
const float R = 0.70710678; const float SE = 0.5; const float CE = 0.8660254;
void main(){
  float sx = (p.x + p.y) * R; float f = (-p.x + p.y) * R;
  float sy = f * SE + p.z * CE; float d = f * CE - p.z * SE;
  gl_Position = vec4((sx-frame.x)/(frame.z-frame.x)*2.-1., (sy-frame.y)/(frame.w-frame.y)*2.-1., (d-dr.x)/(dr.y-dr.x)*2.-1., 1.);
  wp = p;
}"""
FS = """#version 410
in vec3 wp; out vec4 c;
void main(){ c = vec4(wp, 1.); }"""


def block_en(b, margin_m=150.0):
    """LUREF box (e0, e1, n0, n1) of the ground a block can show."""
    es, ns = [], []
    for px in (b["x0"], b["x0"] + b["w"]):
        for py in (b["y0"], b["y0"] + b["h"]):
            for z in (200, 420):
                e, n = map_to_en(px, py, z)
                es.append(float(e)); ns.append(float(n))
    return min(es) - margin_m, max(es) + margin_m, min(ns) - margin_m, max(ns) + margin_m


def ground_pass(b, k=1.0, tile=2048):
    """(H, W, 3) float32: local e, n (relative to ORIGIN) and z of the visible terrain; NaN where none."""
    e0, e1, n0, n1 = block_en(b)
    ix0, ix1 = max(int((e0 - TE0) / TS), 0), min(int((e1 - TE0) / TS) + 2, TZ.shape[1])
    iy0, iy1 = max(int((n0 - TN0) / TS), 0), min(int((n1 - TN0) / TS) + 2, TZ.shape[0])
    z = TZ[iy0:iy1, ix0:ix1].astype(np.float32)
    h, w = z.shape
    E, N = np.meshgrid(TE0 + (ix0 + np.arange(w)) * TS - ORIGIN_E, TN0 + (iy0 + np.arange(h)) * TS - ORIGIN_N)
    v = np.dstack((E, N, z)).reshape(-1, 3).astype("f4")
    i = np.arange(h * w, dtype=np.uint32).reshape(h, w)
    a, bb, c, d = i[:-1, :-1].ravel(), i[:-1, 1:].ravel(), i[1:, :-1].ravel(), i[1:, 1:].ravel()
    idx = np.column_stack((a, bb, c, bb, d, c)).ravel().astype("u4")
    f = (-v[:, 0] + v[:, 1]) * (1 / math.sqrt(2))
    dep = f * math.cos(math.radians(30)) - v[:, 2] * 0.5
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)
    prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
    prog["dr"].value = (float(dep.min()) - 50, float(dep.max()) + 50)
    vbo = ctx.buffer(v.tobytes()); ibo = ctx.buffer(idx.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, "3f", "p")], index_buffer=ibo)
    W, H = round(b["w"] * k), round(b["h"] * k)
    out = np.full((H, W, 3), np.nan, np.float32)
    mpp = MOSAIC["mpp"] / k
    fbo = ctx.framebuffer(ctx.renderbuffer((tile, tile), 4, dtype="f4"), ctx.depth_renderbuffer((tile, tile)))
    fbo.use()
    for ty in range(0, H, tile):
        for tx in range(0, W, tile):
            # layer px -> screen metres; GL y runs up
            fx0 = MOSAIC["sx0"] + b["x0"] * MOSAIC["mpp"] + tx * mpp
            fy1 = MOSAIC["sy1"] - b["y0"] * MOSAIC["mpp"] - ty * mpp
            prog["frame"].value = (fx0, fy1 - tile * mpp, fx0 + tile * mpp, fy1)
            fbo.clear(0, 0, 0, 0)
            vao.render()
            g = np.frombuffer(fbo.read(components=4, dtype="f4"), np.float32).reshape(tile, tile, 4)[::-1]
            hh, ww = min(tile, H - ty), min(tile, W - tx)
            blk = g[:hh, :ww]
            o = out[ty:ty + hh, tx:tx + ww]
            hit = blk[..., 3] > 0.5
            o[hit] = blk[..., :3][hit]
    ctx.release()
    return out


def sample(grid, fx, fy, nearest=False):
    """Sample a 2D grid at float column fx, row fy (arrays of the layer's shape), bilinear (or nearest)."""
    import cv2
    out = np.empty(fx.shape, grid.dtype if nearest else np.float32)
    step = 4096  # cv2.remap wants maps under 32767 px a side; do it in bands
    for y in range(0, fx.shape[0], step):
        out[y:y + step] = cv2.remap(grid if nearest else grid.astype(np.float32), fx[y:y + step].astype(np.float32),
                                    fy[y:y + step].astype(np.float32),
                                    cv2.INTER_NEAREST if nearest else cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out


def slope_normals(G):
    """Unit terrain normals (H, W, 3) in (e, n, z) at the ground points of a ground pass, from the 2 m grid."""
    gy, gx = np.gradient(TZ.astype(np.float32), TS)
    e = G[..., 0] + ORIGIN_E; n = G[..., 1] + ORIGIN_N
    ok = ~np.isnan(e)
    dzx = sample(gx, (np.nan_to_num(e) - TE0) / TS, (np.nan_to_num(n) - TN0) / TS)
    dzy = sample(gy, (np.nan_to_num(e) - TE0) / TS, (np.nan_to_num(n) - TN0) / TS)
    nrm = np.dstack((-dzx, -dzy, np.ones_like(dzx)))
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    nrm[~ok] = (0, 0, 1)
    return nrm.astype(np.float32)
