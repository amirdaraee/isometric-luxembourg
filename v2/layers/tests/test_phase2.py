"""Phase 2: bridge ends (layer 4 rule 1, L4.6), method A's materials, the line score's model lines."""
import numpy as np

from v2.layers import geometry as G
from v2.layers.art_a import FACADES, Style, band, ihash
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
    pals = [pal("buildings", k) for k in FACADES + ["wall_stone"]]
    assert any((a.wall == p).all() for p in pals)
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
