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
    ctrl, _, _ = seams_of(lambda n: (tiles[n], ok), set(tiles), P, at=256)
    assert ctrl == 0


def road_scene(crossing="zebra", cls="secondary"):
    """A two-lane street running east through a tile's plan canvas, a footway crossing it: (renderer, canvas, the
    street's centre point)."""
    from shapely import STRtree
    from shapely.geometry import LineString

    from v2.layers.common import Tile
    from v2.layers.render import DU, Canvas, Renderer
    cv = Canvas(Tile(0, 0, apron=0), 0.0, 40.0)
    u, f = cv.u0 + 256 * DU, cv.f0 + 160 * DU
    c = np.array([cv.oe + (u - f) * R2, cv.on + (u + f) * R2])
    street = LineString([c + (-25, 0), c + (25, 0)])
    walk = LineString([c + (5, -6), c + (5, 6)])
    R = Renderer.__new__(Renderer)
    R.__dict__["edges"] = [
        {"mode": "road", "cls": cls, "width": 6.5, "lanes": 2, "oneway": False},
        {"mode": "path", "cls": "footway", "width": 2.0, "lanes": 0, "oneway": False, "crossing": crossing}]
    R.__dict__["surfaces"] = [(0, "road", street.buffer(3.25, cap_style="flat"), street, False),
                             (1, "path", walk.buffer(1.0, cap_style="flat"), walk, False)]
    R.__dict__["surface_tree"] = STRtree([s[2] for s in R.surfaces])
    return R, cv, c


def test_a_marked_crossing_is_striped_on_the_carriageway_only():
    from v2.layers.common import CLASS, pal
    white = np.round(pal("transport", "lane_dash")).astype(int)
    R, cv, c = road_scene()
    rgb, ids, _ = R._draw_transport(cv, bridge=False)
    is_white = (np.abs(rgb.astype(int) - white).max(-1) == 0)
    px = lambda p: tuple(int(v) for v in np.floor(cv.xy(p[0], p[1]))[::-1])        # noqa: E731
    along = [is_white[px(c + (5, d))] for d in np.arange(-2.9, 2.9, 0.125)]        # across the street, on the walk
    runs = np.flatnonzero(np.diff(np.r_[0, np.array(along, int), 0]) == 1)
    assert 5 <= len(runs) <= 7                                                    # bars of 0.5 m every metre
    assert 0.35 < np.mean(along) < 0.65
    assert is_white[(ids & 255) != CLASS["road"]].sum() == 0                      # nothing striped off the asphalt
    assert not any(is_white[px(c + (5, d))] for d in (-5.0, 5.0))                 # the footway beyond the kerbs
    assert not is_white[px(c + (-10, 1.5))]                                       # the street away from the crossing
    R2_, cv2, c2 = road_scene(crossing="")
    rgb2, _, _ = R2_._draw_transport(cv2, bridge=False)
    w2 = (np.abs(rgb2.astype(int) - white).max(-1) == 0)
    assert not any(w2[px(c2 + (5, d))] for d in np.arange(-2.9, 2.9, 0.125) if abs(d) > 0.3)   # unmarked: no stripes


def test_streets_have_a_kerb_and_driveways_do_not():
    from v2.layers.common import pal
    from v2.layers.render import KERB_M
    kerb = np.round(pal("transport", "kerb")).astype(int)
    px = lambda cv, p: tuple(int(v) for v in np.floor(cv.xy(p[0], p[1]))[::-1])   # noqa: E731
    for cls, want in (("secondary", True), ("residential", True), ("service", False), ("track", False)):
        R, cv, c = road_scene(crossing="", cls=cls)
        if cls != "secondary":
            R.surfaces[0] = (0, "road_minor") + R.surfaces[0][2:]
        rgb, _, _ = R._draw_transport(cv, bridge=False)
        at = rgb[px(cv, c + (-10, 3.25 + KERB_M / 2))].astype(int)
        assert (np.abs(at - kerb).max() == 0) == want, cls
        assert np.abs(rgb[px(cv, c + (-10, 2.5))].astype(int) - kerb).max() > 20    # the carriageway keeps its width


def test_asphalt_is_a_soft_wash_without_grain():
    from v2.layers import detail
    e, n = np.meshgrid(np.arange(0, 60, 0.125), np.arange(0, 60, 0.125))
    f = detail.asphalt(e, n)
    assert abs(f.mean() - 1) < 0.01 and 0.01 < f.std() < 0.04
    assert np.abs(np.diff(f, axis=1)).max() < 0.004 and np.abs(np.diff(f, axis=0)).max() < 0.004   # pixel to pixel


def test_the_shadow_height_map_is_read_between_its_cells():
    from v2.layers.light import hm_at
    hm = HeightMap(0.0, 0.0, 0.5, (40, 40), 240.0)
    hm.terrain[:] = 250.0
    hm.terrain[:, 20:] = 252.0
    for i in range(40):                                   # a building whose edge runs askew to the grid
        hm.b_top[i, : 8 + i // 3] = 9.0
    T, bt, *_ = hm_at(hm, np.array([9.75, 10.0, 10.25]), np.array([5.25, 5.25, 5.25]))
    assert np.allclose(T, [250.0, 251.0, 252.0])          # the ground between two cells, not a step
    # along a row, the building's edge moves evenly with the row and not in steps of a cell
    n = np.linspace(2.0, 18.0, 65)
    e = np.linspace(0.0, 12.0, 961)
    edge = np.array([e[np.flatnonzero(hm_at(hm, e, np.full(len(e), v))[1] > 0)[-1]] for v in n])
    assert (np.diff(edge) >= -1e-9).all() and np.diff(edge).max() < 0.26
    assert np.unique(np.round(edge, 2)).size > 20


def test_a_wall_is_not_shadowed_by_its_own_cells():
    hm = HeightMap(0.0, 0.0, 0.5, (60, 60), 240.0)
    hm.terrain[:] = 250.0
    hm.b_top[20:40, 20:40] = 10.0                          # a block from 10 to 20 m east and north
    hm.b_id[20:40, 20:40] = 0
    n = np.linspace(11.0, 19.0, 33)
    wall = np.column_stack([np.full(33, 20.0), n])         # its east wall, lit by a sun in the south-east
    out = np.tile([1.0, 0.0, 0.0], (33, 1))
    for z in (252.0, 256.0, 259.0):
        s = shadow_ref(hm, wall[:, 0], wall[:, 1], np.full(33, z), 120, 35, normal=out)
        assert s.sum() == 0


def test_a_polygon_is_filled_the_same_wherever_the_canvas_begins():
    """A tile and its neighbour must draw the same border (S-ground): the fill is the exact test of each pixel's
    centre, whatever lies off the canvas and whatever whole-pixel shift the canvas has."""
    import shapely
    from PIL import Image
    from shapely.geometry import Polygon
    from v2.layers.render import fill_geom
    rng = np.random.default_rng(1)
    X, Y = np.meshgrid(np.arange(64) + 0.5, np.arange(64) + 0.5)
    n = 0
    for it in range(300):
        pts = rng.uniform(-300, 400, (int(rng.integers(3, 9)), 2)) if it % 2 else rng.uniform(-20, 90, (5, 2))
        c = pts.mean(0)
        pts = pts[np.argsort(np.arctan2(*(pts - c).T[::-1]))]
        P = Polygon(pts, [Polygon((pts - c) * 0.4 + c).exterior.coords]) if it % 3 == 0 else Polygon(pts)
        if not P.is_valid:
            continue
        sx, sy = int(rng.integers(0, 200)), int(rng.integers(0, 200))
        A = Image.new("L", (64, 64), 0)
        fill_geom(A, P, 1)
        B = Image.new("L", (104 + sx, 104 + sy), 0)
        fill_geom(B, shapely.transform(P, lambda a: a + [sx, sy]), 1)
        assert (np.asarray(A) == np.asarray(B)[sy:sy + 64, sx:sx + 64]).all()
        assert (shapely.contains_xy(P, X, Y) == (np.asarray(A) > 0)).all()
        n += 1
    assert n > 250


def test_walls_are_continued_down_where_the_ground_lies_under_the_base():
    from v2.layers.geometry import tri_normals, wall_skirts
    p = {"min_gap_m": 0.1, "sample_m": 0.5, "outside_m": 0.5, "below_m": 0.5}
    sq = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    yard = [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]]
    blds = [{"ground_z": 100.0, "footprint": [[sq, yard]]},                    # on a slope falling to the east
            {"ground_z": 100.0, "footprint": [[[[x + 50, y] for x, y in sq]]]}]  # on flat ground at its base
    ground = lambda e, n: np.where(np.asarray(e) < 40, 100.0 - 0.3 * np.asarray(e), 100.0)   # noqa: E731
    V, T, tb, gaps = wall_skirts(blds, ground, p)
    assert np.allclose(gaps, [3.15, 0.0])                                      # 10.5 m east of the top: 0.5 m outside
    assert set(tb) == {0}                                                      # the flat one gets no face
    assert np.allclose(V[:, 2].max(), 100.0)                                   # every face hangs from the base
    # the east wall reaches under its lowest ground; the west wall, on ground at the base, has no face
    east = np.isclose(V[:, 0], 10).reshape(-1, 4).all(1)
    assert east.sum() == 1 and np.isclose(V.reshape(-1, 4, 3)[east][0][:, 2].min(), 100 - 3.15 - 0.5)
    assert not np.isclose(V[:, 0], 0).reshape(-1, 4).all(1).any()
    # the faces look out: away from the middle of the building, and into the yard on the yard's ring
    n, _ = tri_normals(V, T)
    cen = V[T].mean(1)
    yard_face = (np.abs(cen[:, 0] - 5) <= 1.01) & (np.abs(cen[:, 1] - 5) <= 1.01)
    out = ((cen[:, :2] - 5.0) * n[:, :2]).sum(1)
    assert yard_face.any() and (out[~yard_face] > 0).all() and (out[yard_face] < 0).all()
    assert np.allclose(n[:, 2], 0)


def test_supports_mesh_draws_arches_piers_and_the_red_bridges_legs():
    """The supports of scene structures as surfaces: each arch its two faces and its barrel, each pier a box down
    to its foot, a low deck's sides to the ground; a frame its girder and four legs from foot to girder."""
    from v2.layers import geometry as G
    from v2.layers.common import CLASS
    line = [[float(x), 0.0, 300.0, 300.0 - 10.0 * (10 < x < 40)] for x in np.arange(0, 50.5, 0.5)]
    st = {"supports": [{"edges": [7], "spine": 7, "length_m": 50.0, "width_m": 4.0, "crown_m": 0.3, "line": line,
                        "arches": [{"t": [10.0, 24.0], "rise_m": 7.0}, {"t": [26.0, 40.0], "rise_m": 7.0}],
                        "piers": [{"t": [24.0, 26.0], "foot_z": 290.0}], "walls": [[0, 4]]}],
          "frames": [{"edges": [8], "axis": [1.0, 0.0], "colour": "structures.red_bridge",
                      "girder": {"width_m": 10.0, "line": [[0.0, 20.0, 339.0, 335.0], [100.0, 20.0, 339.0, 335.0]]},
                      "legs": [{"top": [40.0, 20.0, 335.0], "foot": [20.0, 20.0, 300.0], "top_m": [6.0, 4.0], "foot_m": [3.0, 3.0]}],
                      "footings": [{"e": 20.0, "n": 20.0, "ground_z": 300.0, "size_m": [6.0, 4.0, 2.5]}]}]}
    by_id = {7: (0, {"id": 7}), 8: (1, {"id": 8})}
    M = G.Mesh()
    G.supports_mesh(M, st, by_id)
    m = M.done()
    V, T, cls, obj = m["V"], m["T"], m["cls"], m["obj"]
    arch = V[T[(cls == CLASS["arch"]) & (obj == 0)]]
    assert len(arch) == 2 * 3 * 32 * 2                                   # two arches: two faces and a barrel, 32 quads each
    assert abs(arch[:, :, 2].max() - 300.0) < 1e-6 and abs(arch[:, :, 2].min() - (300.0 - 0.3 - 7.0)) < 1e-6
    pier = V[T[(cls == CLASS["pier"]) & (obj == 0)]]
    assert abs(pier[:, :, 2].min() - 289.6) < 1e-6 and abs(pier[:, :, 2].max() - 300.0) < 1e-6
    assert pier[:, :, 0].min() == 24.0 and pier[:, :, 0].max() == 26.0
    leg = V[T[(cls == CLASS["pier"]) & (obj == 1)]]
    assert leg[:, :, 2].min() <= 299.5 and abs(leg[:, :, 2].max() - 335.5) < 1e-6
    red = {k for k in m["col_keys"] if k.startswith("structures.red_bridge")}
    assert red and "structures.stone" in m["col_keys"]
    M2 = G.Mesh()
    G.supports_mesh(M2, st, by_id, edge_ok=lambda e: e["id"] != 7)       # a way that is not drawn has no arches
    assert not (M2.done()["obj"] == 0).any()


def _flat_art(name="roof_flat_gravel", size=(20.0, 10.0), step=None):
    """Method A's roof painter on one building with a level roof `size` m at 310 m (and, with `step`, a second level
    part beside it, `step` m higher)."""
    from types import SimpleNamespace
    from v2.layers.art_a import ArtA
    w, d = size
    V = [[0, 0, 310], [w, 0, 310], [w, d, 310], [0, d, 310]]
    T = [[0, 1, 2], [0, 2, 3]]
    if step:
        V += [[w, 0, 310 + step], [w + 6, 0, 310 + step], [w + 6, d, 310 + step], [w, d, 310 + step]]
        T += [[4, 5, 6], [4, 6, 7]]
    A = object.__new__(ArtA)
    A.bmesh = {"V": np.array(V, float), "T": np.array(T), "obj": np.zeros(len(T), int), "kind": np.ones(len(T), int)}
    A._levels = {}
    A.styles = [SimpleNamespace(roof_name=name)]
    return A


def test_a_flat_roof_has_a_pale_rim_round_each_level_and_a_surface_inside():
    from v2.layers.art_a import B, FLAT_ROOF as F
    A = _flat_art(step=3.0)
    lines, ax, wide = A.roof_levels(0)
    assert wide and abs(lines.length - (2 * 30 + 2 * 16)) < 1e-6         # both levels' own outlines, the step twice
    assert abs(abs(ax[0]) - 1) < 1e-9
    x, y = np.meshgrid(np.arange(0.05, 20, 0.1), np.arange(0.05, 10, 0.1))
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 310.0)])
    base = np.tile(B("roof_flat_gravel"), (len(P), 1))
    rgb = base.copy()
    on_rim = A.flat_roofs(rgb, np.zeros(len(P), int), P, np.ones(len(P), bool))
    d = np.minimum.reduce([P[:, 0], 20 - P[:, 0], P[:, 1], 10 - P[:, 1]])
    rim, line, inside = d < F["rim_m"] - 0.01, (d > F["rim_m"] + 0.01) & (d < F["rim_m"] + F["line_m"] - 0.01), d > 1.0
    assert np.allclose(rgb[rim], B("roof_rim"))
    assert on_rim[rim].all() and not on_rim[d > F["rim_m"] + 0.01].any()    # the rim's pixels: a material of their own
    plain = base.copy()                                                  # a part's top: the surface, no rim
    assert not A.flat_roofs(plain, np.zeros(len(P), int), P, np.ones(len(P), bool), rim=False).any()
    assert not np.isclose(plain, B("roof_rim")).all(1).any()
    assert (rgb[line].sum(1) < 0.8 * base[line].sum(1)).all()
    tone = rgb[inside].sum(1) / base[inside].sum(1)                      # gravel: flecked about the roof's own colour
    assert abs(np.median(tone) - 1) < 0.03 and tone.std() > 0.02 and np.abs(tone - 1).max() <= F["gravel_tone"] / 2 + 1e-9
    out = base.copy()                                                    # pixels that are not level roof are left
    A.flat_roofs(out, np.zeros(len(P), int), P, np.zeros(len(P), bool))
    assert (out == base).all()


def test_a_narrow_flat_roof_has_no_rim_and_a_membrane_roof_has_seams():
    from v2.layers.art_a import B, FLAT_ROOF as F
    A = _flat_art(name="roof_flat", size=(12.0, 2.0))                    # 2 m wide: the rim would be most of it
    assert not A.roof_levels(0)[2]
    x, y = np.meshgrid(np.arange(0.05, 12, 0.1), np.arange(0.05, 2, 0.1))
    P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 310.0)])
    base = np.tile(B("roof_flat"), (len(P), 1))
    rgb = base.copy()
    A.flat_roofs(rgb, np.zeros(len(P), int), P, np.ones(len(P), bool))
    assert not np.isclose(rgb, B("roof_rim")).all(1).any()
    seam = np.isclose(rgb, base * F["seam"]).all(1)
    assert 0 < seam.mean() < 0.2 and (np.isclose(rgb, base).all(1) | seam).all()


def test_a_flat_roofs_own_colour_is_the_larger_part_of_every_patch_of_it():
    """Stones and tufts are dots on the roof's colour: the middle tone of a small roof, or of the part of one in a
    shadow, is the roof's own (L5.1; with whole cells toned a planted roof of 150 pixels read 16% apart)."""
    from v2.layers.art_a import B, FLAT_ROOF as F
    for name, cell in (("roof_flat_gravel", F["gravel_m"]), ("roof_flat_green", F["tuft_m"])):
        A = _flat_art(name=name, size=(12.0, 2.0))                       # narrow: the surface alone, no rim
        x, y = np.meshgrid(np.arange(0.03, 12, 0.06), np.arange(0.03, 2, 0.06))
        P = np.column_stack([x.ravel(), y.ravel(), np.full(x.size, 310.0)])
        base = np.tile(B(name), (len(P), 1))
        rgb = base.copy()
        A.flat_roofs(rgb, np.zeros(len(P), int), P, np.ones(len(P), bool))
        tone = (rgb.sum(1) / base.sum(1)).reshape(x.shape)
        on = ~np.isclose(tone, 1)
        assert abs(on.mean() - F["dot_share"]) < 0.06 and (tone < 1).any() and (tone > 1).any()
        w = int(round(3 * cell / 0.06))                                  # every patch three cells long, 2 m wide
        for j in range(0, x.shape[1] - w, 5):
            patch = tone[:, j:j + w]
            assert np.median(patch) == 1.0 and (~np.isclose(patch, 1)).mean() < 0.5
