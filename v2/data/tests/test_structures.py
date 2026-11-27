"""Scene structures: what stands under the bridges without a model of their own (v2/data/structures/bridges.json)."""
import json

import numpy as np

from v2.data.scene import structures as S

RULE = S._values(json.loads(S.BRIDGES.read_text())["supports"])


def _valley(depth, half=30.0):
    """Ground at 300 m with a valley `depth` m deep across the line x = 50, `half` m to each side."""
    return lambda e, n: 300.0 - depth * np.clip(1 - np.abs(np.asarray(e, float) - 50) / half, 0, 1) + 0 * np.asarray(n, float)


def _deck(length=100.0, z=301.0):
    return S.resample(np.array([[0.0, 0.0], [length, 0.0]]), np.array([z, z]))


def test_a_bridge_over_a_valley_stands_on_arches_and_piers():
    ts, P, z = _deck()
    under, ground, arches, piers, walls, on_way = S.arcade(ts, P, z, 4.0, _valley(20.0), RULE)
    assert len(arches) >= 3 and len(piers) == len(arches) - 1 and on_way == 0
    spans = [a["t"][1] - a["t"][0] for a in arches]
    assert max(spans) - min(spans) < 0.05 and RULE["span_m"][0] <= spans[0] <= RULE["span_m"][1]
    for a, b in zip(arches, arches[1:]):                                # a pier fills the gap between two arches
        assert any(abs(p["t"][0] - a["t"][1]) < 0.02 and abs(p["t"][1] - b["t"][0]) < 0.02 for p in piers)
    for a in arches:                                                    # a round arch, or lower where the ground is near
        assert 0.5 <= a["rise_m"] <= (a["t"][1] - a["t"][0]) / 2 + 0.01
    for p in piers:                                                     # every pier stands on the ground under it
        assert p["foot_z"] <= float(np.interp(sum(p["t"]) / 2, ts, ground)) + 0.01
    clear = under - ground                                              # the arches span all that stands clear
    open_t = ts[clear > RULE["min_clear_m"]]
    assert abs(arches[0]["t"][0] - open_t[0]) < 0.6 and abs(arches[-1]["t"][1] - open_t[-1]) < 0.6


def test_a_low_deck_has_no_arch_and_its_sides_go_down_to_the_ground():
    ts, P, z = _deck(z=301.0)
    _, _, arches, piers, walls, _ = S.arcade(ts, P, z, 4.0, _valley(1.2), RULE)       # 1.2 m under a 1 m slab
    assert arches == [] and piers == [] and len(walls) == 1
    _, _, arches, piers, walls, _ = S.arcade(ts, P, z, 4.0, _valley(0.0), RULE)       # on the ground
    assert arches == [] and piers == [] and walls == []


def test_no_pier_stands_on_a_way_passing_under_where_a_layout_allows():
    ts, P, z = _deck()
    _, _, arches, piers, _, _ = S.arcade(ts, P, z, 4.0, _valley(20.0), RULE)
    road = sum(piers[len(piers) // 2]["t"]) / 2                         # a road right where a pier would stand
    _, _, arches2, piers2, _, on_way = S.arcade(ts, P, z, 4.0, _valley(20.0), RULE, ways=[(road, 3.5)])
    assert on_way == 0 and not any(p["t"][0] - 3.5 < road < p["t"][1] + 3.5 for p in piers2)
    assert len(arches2) != len(arches)


def test_ways_side_by_side_are_one_bridge_and_ways_end_to_end_one_line():
    a = np.array([[0.0, 0.0], [40.0, 0.0]])
    b = a + [0.0, 4.0]                                                  # a footway beside the road
    c = np.array([[20.0, -30.0], [20.0, 30.0]])                         # another bridge, crossing
    groups = sorted(sorted(g) for g in S.side_by_side([a, b, c], [6.0, 2.0, 3.0], RULE["parallel_gap_m"]))
    assert groups == [[0, 1], [2]]
    ts, P, z, w = S.deck_of([a, b], [np.full(2, 300.0)] * 2, [6.0, 2.0])
    assert abs(w - 8.0) < 0.01 and np.allclose(P[:, 1], 1.0)            # from -3 to +5: 8 m wide, centred on +1
    E = [{"a": 1, "b": 2, "en": [[0, 0], [10, 0]], "z": [300, 300]}, {"a": 3, "b": 2, "en": [[20, 0], [10, 0]], "z": [301, 300]}]
    ch = S.chains(E)
    assert len(ch) == 1
    en, zz = S.chain_line(E, ch[0])
    assert en.tolist() == [[0, 0], [10, 0], [20, 0]] and zz.tolist() == [300, 300, 301]


def test_the_red_bridge_stands_on_four_legs_that_lean_toward_the_middle():
    spec = json.loads(S.BRIDGES.read_text())["frames"][0]
    ways = [{"id": i, "en": [[0.0, off], [355.0, off]], "z": [340.0, 340.0], "width": 6.5} for i, off in enumerate((-4.0, 4.0))]
    f = S.frame(spec, ways, lambda e, n: 300.0 + 0 * np.asarray(e, float))
    v = S._values(spec)
    assert len(f["legs"]) == 4 and abs(f["feet_apart_m"] - v["feet_apart_m"]) < 0.5
    assert f["tops_apart_m"] < f["feet_apart_m"] - 10                   # the tops are nearer the middle than the feet
    for leg in f["legs"]:
        assert leg["foot"][2] == 300.0 and leg["top"][2] > 320.0
        assert abs(leg["top"][0] - 177.5) < abs(leg["foot"][0] - 177.5)
    top, bottom = np.array(f["girder"]["line"])[:, 2:].T
    assert np.allclose(top, 339.0) and (top - bottom).min() >= v["girder_depth_m"] - 0.01
    assert (top - bottom).max() > v["girder_depth_m"] + 0.9 * v["haunch_m"]          # deeper over the legs
