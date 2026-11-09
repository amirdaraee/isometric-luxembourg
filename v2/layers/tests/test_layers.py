"""Phase 1 unit tests: the rendering primitives, the tile codings, the shadow march and the checks' detectors, on
small synthetic inputs (no downloads, under a few seconds)."""
import math

import numpy as np

from v2.layers.common import (C30, R2, S30, depth_decode, depth_encode, depth_ref, oct_decode, oct_encode, pack_bin,
                              project, unpack_bin, unproject)
from v2.layers.light import HeightMap, shadow_ref
from v2.layers.raster import HeightField, raster_ellipsoids, raster_tris, terrain_scan


class SmallTile:
    """A tile-like window of n x n pixels at zoom-0 pixel (px0, py0)."""

    def __init__(self, px0, py0, n=48):
        self.px0, self.py0, self.size, self.apron = px0, py0, n, 0
        self.centres = (px0 + np.arange(n) + 0.5, py0 + np.arange(n) + 0.5)


def test_codings_round_trip():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 255, (16, 16, 4), dtype=np.uint8)
    assert np.array_equal(unpack_bin(pack_bin(a), a.shape, np.uint8), a)
    b = rng.integers(0, 2**32 - 1, (16, 16), dtype=np.uint32)
    assert np.array_equal(unpack_bin(pack_bin(b), b.shape, np.uint32), b)
    n = rng.normal(size=(500, 3))
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    assert np.degrees(np.arccos(np.clip((oct_decode(oct_encode(n)) * n).sum(1), -1, 1))).max() < 1.0
    ref = depth_ref("120_64", 3, 512)
    d = ref[:, None] - 2 * 300 + rng.uniform(-150, 150, (512, 512))     # any height, any zoom
    d[5, 5] = np.inf
    code, dmin = depth_encode(d, ref)
    back = depth_decode(code, dmin, ref)
    ok = np.isfinite(d)
    assert np.abs(back[ok] - d[ok]).max() <= 0.005 + 1e-9 and np.isinf(back[5, 5])


def test_project_unproject():
    e, n, z = 77500.0, 75000.0, 290.0
    px, py, d = project(e, n, z)
    assert np.allclose(unproject(px, py, d), (e, n, z))


def _hill(e0=77400.0, n0=74900.0, step=0.5, size=400):
    ee = e0 + (np.arange(size) + 0.5) * step
    nn = n0 + (np.arange(size) + 0.5) * step
    E, N = np.meshgrid(ee, nn)
    z = 280 + 25 * np.exp(-((E - ee.mean()) ** 2 + (N - nn.mean()) ** 2) / (2 * 25 ** 2))
    z += 6 * (np.abs(E - ee.mean() + 30) < 0.6)                  # a thin wall-like ridge, half a metre wide
    return HeightField(z, e0, n0, step), ee.mean(), nn.mean()


def test_terrain_scan_is_the_first_hit_of_each_view_ray():
    hf, ce, cn = _hill()
    px, py, _ = project(ce - 30, cn, 300)
    tile = SmallTile(int(px) - 24, int(py) - 24)
    r = terrain_scan(hf, tile, 270, 320)
    assert r["hit"].mean() > 0.9
    rng = np.random.default_rng(1)
    for i, j in np.argwhere(r["hit"])[rng.choice(int(r["hit"].sum()), 60, replace=False)]:
        cx, cy = tile.centres[0][j], tile.centres[1][i]
        ds = np.arange(r["depth"][i, j] - 120, r["depth"][i, j] + 2, 0.005)
        e, n, z = unproject(np.full(len(ds), cx), np.full(len(ds), cy), ds)
        k = int(np.argmax(z - hf.sample(e, n) <= 0))
        assert abs(ds[k] - r["depth"][i, j]) < 0.15, (i, j, ds[k], r["depth"][i, j])


def test_triangles_depth_buffer_keeps_the_nearest():
    P = np.array([[2, 2], [30, 2], [2, 30], [5, 5], [40, 5], [5, 40]], float)
    D = np.array([10, 10, 10, 5, 5, 5], float)
    zb = np.full((48, 48), np.inf)
    tb = np.full((48, 48), -1, np.int64)
    raster_tris(P, D, np.array([[0, 1, 2], [3, 4, 5]]), 48, 48, zb, tb)
    assert tb[6, 6] == 1 and zb[6, 6] == 5 and tb[3, 3] == 0
    assert abs((tb == 0).sum() + (tb == 1).sum() - np.isfinite(zb).sum()) == 0
    assert abs((tb >= 0).sum() - (0.5 * 28 * 28 + 0.5 * 35 * 35 - 0.5 * 25 * 25 * 0)) < 400


def test_ellipsoid_front_is_nearer_by_its_radius():
    C = np.array([[77500.0, 75000.0, 300.0]])
    px, py, d = project(*C[0])
    tile = SmallTile(int(px) - 24, int(py) - 24)
    zb = np.full((48, 48), np.inf)
    ib = np.full((48, 48), -1, np.int64)
    nb = np.zeros((48, 48, 3))
    raster_ellipsoids(C, np.array([2.0]), np.array([2.0]), tile, zb, ib, nb)
    r, c = int(py) - tile.py0, int(px) - tile.px0
    assert abs(zb[r, c] - (d - 2.0)) < 0.05
    assert np.allclose(np.linalg.norm(nb[ib >= 0], axis=1), 1)


def test_shadow_of_a_tower_points_away_from_the_sun():
    hm = HeightMap(0, 0, 0.5, (200, 200), 200)
    hm.terrain[:] = 250
    hm.b_top[90:110, 90:110] = 20                      # a 10 x 10 m tower, 20 m tall, centre (50, 50)
    pts = {"north": (50, 70), "south": (50, 30), "east": (70, 50), "west": (30, 50)}
    for az, shaded in ((180, "north"), (90, "west"), (270, "east"), (0, "south")):
        for k, (e, n) in pts.items():
            s = shadow_ref(hm, np.array([e]), np.array([n]), np.array([250.0]), az, 40)[0]
            assert s == (1.0 if k == shaded else 0.0), (az, k, s)
    assert shadow_ref(hm, np.array([5.0]), np.array([5.0]), np.array([250.0]), 180, -3)[0] == 1.0   # night


def test_look_grade_is_a_projection():
    from v2.checks.g1_checks import look_grade
    c = np.random.default_rng(2).uniform(0, 1, (5000, 3))
    once = look_grade(c)
    assert np.abs(look_grade(once) - once).max() < 1e-9


def test_seam_check_finds_a_seam_and_nothing_else():
    from v2.checks.g1_checks import seams_of
    P = {"seam_de_max": 3.0, "seam_run": 3}
    rng = np.random.default_rng(3)
    base = (rng.normal(150, 4, (512, 512, 3))).clip(0, 255)
    tiles = {"0_0": base, "1_0": base.copy()}
    ok = np.ones((512, 512), bool)
    bad, _, _ = seams_of(lambda n: (tiles[n], ok), set(tiles), P)
    assert bad == 0
    tiles["1_0"] = (base + 12).clip(0, 255)
    bad, _, _ = seams_of(lambda n: (tiles[n], ok), set(tiles), P)
    assert bad >= 3
