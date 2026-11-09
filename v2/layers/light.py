"""Layer 9, light: the shadow height map the viewer marches for cast shadows, and the Python reference of the
viewer's light (spec: v2/docs/specs/layer-09-light.md; constants: v2/config/light.json).

**Height map.** A plan grid (row 0 south, like the terrain) over the area and a margin, holding per cell the top of
everything that can cast a shadow, by source so a layer switched off in the viewer casts nothing:
  A (RGBA8): terrain (uint16 cm above zbase), building top above the terrain (/0.3 m), tree crown top (/0.25 m)
  B (RGBA8): tree crown bottom (/0.25 m), structure top, structure bottom (/0.25 m; bridge decks, viaducts, lift)
Bottoms let light pass under crowns, decks and through arches.

**Shadow test.** From a surface point, march towards the sun in steps that grow geometrically (t0, x growth, n
steps); the point is in shadow when a sample's ray height is inside any source's [bottom, top]. The viewer's shader
(v2/web/src/gl/shaders.ts) does exactly this; `shadow_ref` is the same in numpy for the checks.
"""
from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np

from v2.config import CONFIG
from v2.config.sun import position
from v2.layers import geometry as G
from v2.layers.raster import raster_tris

LIGHT = json.loads((CONFIG / "light.json").read_text())


class HeightMap:
    def __init__(self, e0, n0, step, shape, zbase):
        self.e0, self.n0, self.step, self.shape, self.zbase = float(e0), float(n0), float(step), shape, float(zbase)
        h, w = shape
        self.terrain = np.zeros(shape)
        self.b_top = np.zeros(shape)                 # building top above terrain (m), 0 = none
        self.t_top = np.zeros(shape)
        self.t_bot = np.zeros(shape)
        self.s_top = np.zeros(shape)
        self.s_bot = np.zeros(shape)
        self.b_id = np.full(shape, -1, np.int64)     # which building (for the shadow direction check)

    def grid_en(self):
        h, w = self.shape
        return (self.e0 + (np.arange(w) + 0.5) * self.step, self.n0 + (np.arange(h) + 0.5) * self.step)

    def encode(self):
        H = LIGHT["heightmap"]
        A = np.zeros(self.shape + (4,), np.uint8)
        B = np.zeros(self.shape + (4,), np.uint8)
        t = np.clip(np.round((self.terrain - self.zbase) * 100), 0, 65535).astype(np.uint16)
        A[..., 0] = t & 255
        A[..., 1] = t >> 8
        A[..., 2] = np.clip(np.ceil(self.b_top / H["building_unit_m"]), 0, 255)
        A[..., 3] = np.clip(np.ceil(self.t_top / H["tree_unit_m"]), 0, 255)
        B[..., 0] = np.clip(np.floor(self.t_bot / H["tree_unit_m"]), 0, 255)
        B[..., 1] = np.clip(np.ceil(self.s_top / H["structure_unit_m"]), 0, 255)
        B[..., 2] = np.clip(np.floor(self.s_bot / H["structure_unit_m"]), 0, 255)
        B[..., 0] = np.where(A[..., 3] > 0, B[..., 0], 0)
        B[..., 2] = np.where(B[..., 1] > 0, B[..., 2], 0)
        return A, B

    @classmethod
    def decode(cls, A, B, e0, n0, step, zbase):
        H = LIGHT["heightmap"]
        hm = cls(e0, n0, step, A.shape[:2], zbase)
        hm.terrain = zbase + (A[..., 0].astype(float) + A[..., 1].astype(float) * 256) / 100
        hm.b_top = A[..., 2] * H["building_unit_m"]
        hm.t_top = A[..., 3] * H["tree_unit_m"]
        hm.t_bot = B[..., 0] * H["tree_unit_m"]
        hm.s_top = B[..., 1] * H["structure_unit_m"]
        hm.s_bot = B[..., 2] * H["structure_unit_m"]
        return hm


def _plan_raster(hm, V, T, top=True):
    """Max (top) or min (bottom) z of a mesh per plan cell; returns (z, triangle index)."""
    h, w = hm.shape
    P = np.column_stack([(V[:, 0] - hm.e0) / hm.step, (V[:, 1] - hm.n0) / hm.step])
    D = -V[:, 2] if top else V[:, 2]
    zb = np.full((h, w), np.inf)
    tb = np.full((h, w), -1, np.int64)
    # walls are vertical: in plan they are lines, so draw every triangle grown by half a cell (no gaps between
    # a roof and its walls)
    raster_tris(P, D, T, w, h, zb, tb)
    z = np.where(np.isfinite(zb), -zb if top else zb, np.nan)
    return z, tb


def build_heightmap(R, sources=("terrain", "buildings", "trees", "structures")) -> HeightMap:
    """The shadow height map of a scene, from the renderer's geometry (R: render.Renderer)."""
    sc = R.scene
    Hc = LIGHT["heightmap"]
    step = Hc["step_m"]
    x0, y0, x1, y1 = sc.polygon.buffer(Hc["margin_m"]).bounds
    x0, y0 = math.floor(x0 / step) * step, math.floor(y0 / step) * step
    w = int(math.ceil((x1 - x0) / step))
    h = int(math.ceil((y1 - y0) / step))
    zmin, _ = sc.z_range
    hm = HeightMap(x0, y0, step, (h, w), math.floor(zmin) - 5)
    ee, nn = hm.grid_en()
    E, N = np.meshgrid(ee, nn)
    hm.terrain = R.hf.sample(E, N)
    if "buildings" in sources and R.building_meshes:
        B = R.building_meshes[0]
        z, tb = _plan_raster(hm, B["V"], B["T"], top=True)
        ok = np.isfinite(z)
        hm.b_top = np.where(ok, np.maximum(z - hm.terrain, 0), 0)
        hm.b_id = np.where(ok, B["obj"][np.maximum(tb, 0)], -1)
    if "trees" in sources and R.tree_geo is not None:
        g = R.tree_geo
        C, r, b = g["C"], g["r"], g["b"]
        top = np.full(hm.shape, -np.inf)
        bot = np.full(hm.shape, np.inf)
        for i in range(len(C)):
            j0 = int((C[i, 0] - r[i] - hm.e0) / step); j1 = int((C[i, 0] + r[i] - hm.e0) / step) + 1
            i0 = int((C[i, 1] - r[i] - hm.n0) / step); i1 = int((C[i, 1] + r[i] - hm.n0) / step) + 1
            j0, i0 = max(j0, 0), max(i0, 0)
            j1, i1 = min(j1, w), min(i1, h)
            if j1 <= j0 or i1 <= i0:
                continue
            de = ee[j0:j1][None, :] - C[i, 0]
            dn = nn[i0:i1][:, None] - C[i, 1]
            q = 1 - (de ** 2 + dn ** 2) / r[i] ** 2
            m = q > 0
            dz = b[i] * np.sqrt(np.where(m, q, 0))
            tt = np.where(m, C[i, 2] + dz, -np.inf)
            bb = np.where(m, C[i, 2] - dz, np.inf)
            top[i0:i1, j0:j1] = np.maximum(top[i0:i1, j0:j1], tt)
            bot[i0:i1, j0:j1] = np.minimum(bot[i0:i1, j0:j1], bb)
        ok = np.isfinite(top)
        hm.t_top = np.where(ok, np.maximum(top - hm.terrain, 0.25), 0)
        hm.t_bot = np.where(ok, np.clip(bot - hm.terrain, 0, None), 0)
    if "structures" in sources:
        meshes = [m for m in (R.structure_meshes or []) + [R.decks] if len(m["T"])]
        if meshes:
            V = np.concatenate([m["V"] for m in meshes])
            off = np.cumsum([0] + [len(m["V"]) for m in meshes])[:-1]
            T = np.concatenate([m["T"] + o for m, o in zip(meshes, off)])
            zt, _ = _plan_raster(hm, V, T, top=True)
            zbm, _ = _plan_raster(hm, V, T, top=False)
            ok = np.isfinite(zt)
            hm.s_top = np.where(ok, np.maximum(zt - hm.terrain, 0.25), 0)
            hm.s_bot = np.where(ok, np.clip(zbm - hm.terrain, 0, None), 0)
    return hm


# ------------------------------------------------------------------------------------------------ reference march
def sun_vector(when: dt.datetime):
    az, el = position(when)
    a, e = math.radians(az), math.radians(el)
    return az, el, np.array([math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)])


def march_steps():
    M = LIGHT["march"]
    t, out = M["t0_m"], []
    for _ in range(M["steps"]):
        out.append(t)
        t *= M["growth"]
    return np.array(out)


def shadow_ref(hm: HeightMap, e, n, z, az_deg, el_deg, sources=("terrain", "buildings", "trees", "structures"),
               who=False):
    """1 where (e, n, z) is in a cast shadow for the sun at (az, el), else 0 (as the viewer's shader).
    With who=True also returns the building index that cast it (-1: something else or nothing)."""
    e, n, z = (np.asarray(a, float) for a in (e, n, z))
    if el_deg <= 0:
        return (np.ones(e.shape), np.full(e.shape, -1)) if who else np.ones(e.shape)
    a = math.radians(az_deg)
    dx, dy, tz = math.sin(a), math.cos(a), math.tan(math.radians(el_deg))
    bias = LIGHT["march"]["bias_m"]
    sh = np.zeros(e.shape, bool)
    by = np.full(e.shape, -1, np.int64)
    h, w = hm.shape
    for t in march_steps():
        ee, nn, zr = e + dx * t, n + dy * t, z + tz * t + bias
        j = np.floor((ee - hm.e0) / hm.step).astype(np.int64)
        i = np.floor((nn - hm.n0) / hm.step).astype(np.int64)
        inside = (i >= 0) & (i < h) & (j >= 0) & (j < w)
        ii, jj = np.clip(i, 0, h - 1), np.clip(j, 0, w - 1)
        T = hm.terrain[ii, jj]
        occ = np.zeros(e.shape, bool)
        if "terrain" in sources:
            occ |= T > zr
        if "buildings" in sources:
            bt = hm.b_top[ii, jj]
            hitb = (bt > 0) & (T + bt > zr)
            if who:
                by = np.where(hitb & ~sh & ~occ, hm.b_id[ii, jj], by)
            occ |= hitb
        if "trees" in sources:
            tt, tb = hm.t_top[ii, jj], hm.t_bot[ii, jj]
            occ |= (tt > 0) & (T + tb < zr) & (T + tt > zr)
        if "structures" in sources:
            st, sb = hm.s_top[ii, jj], hm.s_bot[ii, jj]
            occ |= (st > 0) & (T + sb < zr) & (T + st > zr)
        sh |= occ & inside
        if zr.min() > hm.terrain.max() + 80:
            break
    return (sh.astype(float), by) if who else sh.astype(float)


def lambert(normal, sunv):
    w = LIGHT["sun"]["wrap"]
    return np.clip((normal @ sunv + w) / (1 + w), 0, 1)
