"""Phase 2: bridge ends (layer 4 rule 1, L4.6), method A's materials, the line score's model lines."""
import numpy as np

from v2.layers import geometry as G
from v2.layers.art_a import FACADES, ROOFS, Style, band, ihash
from v2.layers.common import pal


def edge(z, structure="ground", step=2.0):
    n = len(z)
    return {"en": [[i * step, 0.0] for i in range(n)], "z": list(z), "s": [i * step for i in range(n)],
            "structure": structure, "a": 1, "b": 2}


def flat(e, n):
    return np.zeros(len(np.atleast_1d(e)))


def test_an_approach_cut_out_of_the_terrain_is_a_deck_up_to_where_it_meets_the_ground():
    # the red bridge's east end: the road stays at 11 m over the terrain model for its first metres, then lands
    z = [11.0, 9.0, 6.0, 3.0, 0.5, 0.05, 0.0, 0.0]
    m = G.deck_mask(edge(z), flat)
    assert m.tolist() == [True, True, True, True, True, False, False, False]
    parts = G.pieces(m)
    assert parts[0][0] and not parts[-1][0]
    assert parts[0][2] == parts[1][1]                         # the pieces share their joint sample


def test_a_small_bump_alone_is_draped_but_not_at_a_bridge_end():
    z = [0.5, 0.4, 0.3, 0.0, 0.0]
    assert not G.deck_mask(edge(z), flat).any()               # under DECK_CORE_M: on the terrain
    assert G.deck_mask(edge(z), flat, abutment=(True, False)).tolist()[:3] == [True, True, True]
    assert G.deck_mask(edge([1, 1], "bridge"), flat).all()
    assert not G.deck_mask(edge([5, 5], "tunnel"), flat).any()


def test_densify_keeps_the_polyline_and_profile():
    e = edge([0.0, 2.0, 2.0], step=3.0)
    d = G.densify(e, 0.5)
    assert np.allclose(d["en"][0], [0, 0]) and np.allclose(d["en"][-1], [6, 0])
    assert np.allclose(np.diff(d["s"]), 0.5)
    assert np.isclose(np.interp(1.5, d["s"], d["z"]), 1.0)
    m = np.zeros(len(d["s"]), bool); m[:3] = True
    assert G.deck_at(d, m, np.array([0.2, 0.9, 5.0])).tolist() == [True, True, False]


def test_method_a_styles_are_deterministic_palette_colours():
    a, b = Style("ACT_x", "gable"), Style("ACT_x", "gable")
    assert (a.wall == b.wall).all() and a.facade == b.facade and a.facade in FACADES
    # the wall is a palette colour in the building's own tone (0.93 to 1.04 of it), never another colour
    pals = [pal("buildings", k) for k in FACADES + ["wall_stone"]]
    ratio = [a.wall / p for p in pals]
    assert any(np.ptp(r[p < 245]) < 1e-9 and 0.93 <= r[1] <= 1.04 + 1e-9 for r, p in zip(ratio, pals))
    assert a.roof_name in [r[0] for r in ROOFS] and abs(sum(r[2] for r in ROOFS) - 1) < 1e-9
    assert Style("ACT_y", "flat").courses is None
    assert band(np.array([0.0, 0.5, 3.0]), 3.0, 0.2).tolist() == [True, False, True]
    h = ihash(np.arange(1000), np.zeros(1000))
    assert 0 <= h.min() and h.max() <= 1 and h.std() > 0.2


def test_feature_edges_of_a_box_are_its_12_edges():
    from v2.checks.line_checks import feature_edges, samples
    M = G.Mesh()
    G.box(M, np.array([0.0, 0.0]), np.array([1.0, 0.0]), 2.0, 4.0, 0.0, 3.0, 11, 0, "buildings.wall_render")
    D = M.done()
    A, B, O = feature_edges(D)
    assert len(A) == 12 and (O == 0).all()
    P, Dir, Ob = samples(A, B, O, step=0.25)
    assert len(P) > 0 and np.allclose(np.linalg.norm(Dir, axis=1), 1)


def test_drawn_detail_is_even_and_knows_no_side():
    """Phase 3's patterns (detail.py): tones are symmetric about 1 and lines a minority, so a material's median stays
    its palette colour (what L5.1 measures); a pattern is a function of the place only (the same on every call)."""
    from v2.layers import detail
    rng = np.random.default_rng(3)
    e, n, z = rng.uniform(0, 400, 200_000), rng.uniform(0, 400, 200_000), rng.uniform(250, 300, 200_000)
    t, j = detail.slabs(e, n, 1.5, 0.75, 0.2, joint=0.07, tone=0.035, seed=1)
    assert abs(np.median(t) - 1) < 0.005 and (j > 0.5).mean() < 0.25
    r = detail.rock(e, n, z)
    assert np.array_equal(r, detail.rock(e, n, z)) and (r <= 1.2).all() and (r > 0.3).all()
    assert abs(np.median(detail.vnoise(e, n, 3.0, 5)) - 0.5) < 0.02
    # a line 0.06 m wide seen by samples 0.125 m apart covers about half of the samples it passes through
    c = detail.soft_band(np.arange(0, 100, 0.125) + 0.01, 1.0, 0.06, 0.125)
    assert abs(c.mean() - 0.06) < 0.005 and c.max() <= 0.5 + 1e-9
    # the ground's detail keeps each class's median within 3% of its colour (5% on rock, whose beds are drawn dark)
    names = ["none", "paved", "square", "grass", "garden", "rock", "wood"]
    px, py = rng.integers(0, 4000, 200_000), rng.integers(0, 4000, 200_000)
    for i, c in enumerate(names[1:], 1):
        rgb = np.full((len(e), 3), 180.0)
        out = detail.ground_detail(rgb, np.full(len(e), i), names, e, n, z, px, py)
        assert abs(np.median(out[:, 1]) / 180 - 1) < (0.05 if c == "rock" else 0.03), c


def test_crown_lobes_stay_inside_the_measured_crown():
    from v2.layers.render import crown_lobes
    rng = np.random.default_rng(5)
    k = 500
    C = np.column_stack([rng.uniform(0, 100, k), rng.uniform(0, 100, k), rng.uniform(260, 300, k)])
    r, b, typ = rng.uniform(0.6, 6.5, k), rng.uniform(1.0, 9.0, k), rng.integers(0, 4, k)
    C2, r2, b2, own = crown_lobes(C, r, b, typ)
    assert set(own.tolist()) == set(range(k))
    d = np.hypot(C2[:, 0] - C[own, 0], C2[:, 1] - C[own, 1])
    assert (d + r2 <= r[own] + 1e-9).all()                               # never wider than the measured crown
    assert (C2[:, 2] + b2 <= C[own, 2] + b[own] + 1e-9).all()             # never above the measured top
    assert (C2[:, 2] - b2 >= C[own, 2] - b[own] - 1e-9).all()             # never below the crown's foot
    top = np.full(k, -np.inf)
    np.maximum.at(top, own, C2[:, 2] + b2)
    assert np.allclose(top, C[:, 2] + b)                                  # and its top is the measured top
    again = crown_lobes(C, r, b, typ)
    assert all(np.array_equal(x, y) for x, y in zip((C2, r2, b2, own), again))
