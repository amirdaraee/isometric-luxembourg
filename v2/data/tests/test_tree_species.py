"""The species rules (v2/data/scene/tree_species.py): what a tree is drawn as, and in which order the rules decide."""
import numpy as np
from shapely.geometry import LineString, Polygon

from v2.data.scene import tree_species as ts

S = ts.config()
NAMES = list(S["list"])
TYPES = ["deciduous_green", "deciduous_red", "conifer", "other"]
EMPTY = {"woods": [], "squares": {}, "lines": [], "line_names": [], "osm_trees": []}


def _assign(e, n, typ=None, h=None, ctx=None, **kw):
    e, n = np.asarray(e, float), np.asarray(n, float)
    typ = np.zeros(len(e), int) if typ is None else np.asarray(typ)
    h = np.full(len(e), 12.0) if h is None else np.asarray(h, float)
    sp, rule, names = ts.assign(e, n, typ, h, TYPES, S, {**EMPTY, **(ctx or {})}, **kw)
    return [names[i] for i in sp], [ts.RULES[i] for i in rule]


def test_every_species_is_complete_and_the_mixes_name_real_species():
    assert set(S["by_type"].values()) <= set(NAMES)
    A = S["assign"]
    for pool in A["pools"].values():
        assert set(pool) <= set(NAMES)
    assert set(A["genus"].values()) | set(A["named"].values()) | {c["as"] for c in A["cultivars"]} <= set(NAMES)
    assert set(A["conifers"]) | set(A["red"]) <= set(NAMES)
    for k, row in S["list"].items():
        assert row["form"] in S["forms"] and len(row["width"]) == 3 and 0 < row["share"] < 1, k


def test_a_known_tree_is_drawn_as_the_nearest_species():
    A = S["assign"]
    assert ts.drawn_as("Tilia cordata", "'Greenspire'", A) == "lime"
    assert ts.drawn_as("Acer platanoides", "'Columnare'", A) == "maple_column"
    assert ts.drawn_as("Quercus robur", "'Fastigiata'", A) == "oak_column"
    assert ts.drawn_as("Carpinus betulus", "'Fastigiata'", A) == "hornbeam_column"
    assert ts.drawn_as("Fagus sylvatica", "'Purpurea'", A) == "copper_beech"
    assert ts.drawn_as("Prunus cerasifera", "'Nigra'", A) == "cherry_plum_red"
    assert ts.drawn_as("Populus nigra", "'Italica'", A) == "poplar" and ts.drawn_as("Populus alba", "", A) == "ash"
    assert ts.drawn_as("Salix x sepulcralis", "'Chrysocoma'", A) == "willow"
    assert ts.drawn_as("Pinus nigra", "", A) == "pine" and ts.drawn_as("Baumgruppe-gemischt", "", A) is None
    assert ts.drawn_as("", "", A) is None


def test_the_register_decides_first_and_only_for_the_nearest_tree():
    e, n = [0.0, 2.0, 50.0], [0.0, 0.0, 0.0]
    reg = {"e": np.array([0.5, 1.6, 80.0]), "n": np.array([0.0, 0.0, 0.0]), "key": ["plane", "pine", "birch"]}
    sp, rule = _assign(e, n, register=reg)
    assert sp[:2] == ["plane", "pine"] and rule[:2] == ["register", "register"] and rule[2] != "register"
    # two register trees by one surveyed tree: the nearer one names it
    reg = {"e": np.array([0.5, 1.0]), "n": np.array([0.0, 0.0]), "key": ["plane", "lime"]}
    sp, rule = _assign([0.0, 50.0], [0.0, 0.0], register=reg)
    assert sp[0] == "plane" and rule == ["register", rule[1]] and rule[1] != "register"


def test_the_survey_s_type_narrows_the_species_and_height_rules_out_small_species():
    k = 400
    rng = np.random.default_rng(3)
    e, n = rng.uniform(0, 500, k), rng.uniform(0, 500, k)
    typ = rng.integers(0, 4, k)
    h = rng.uniform(3, 30, k)
    sp, rule = _assign(e, n, typ, h)
    A = S["assign"]
    for s, t, hh in zip(sp, typ, h):
        assert (s in A["conifers"]) == (t == 2) and (s in A["red"]) == (t == 1)
        lo, hi = {**S["defaults"], **S["list"][s]}["h"]
        assert lo <= hh <= hi
    assert _assign(e, n, typ, h) == (sp, rule)                              # the same trees, the same species
    assert len(set(sp)) > 8                                                # and a mix, not one species


def test_a_named_street_has_its_known_species_and_another_street_one_species_of_its_own():
    line = LineString([(0, 0), (200, 0)])
    e, n = np.arange(5, 200, 10.0), np.full(20, 4.0)
    sp, rule = _assign(e, n, ctx={"lines": [line], "line_names": ["Montée du Grund"]})
    assert set(sp) == {"lime"} and set(rule) == {"named"}
    sp, rule = _assign(e, n, ctx={"lines": [line], "line_names": ["Rue de Nulle Part"]})
    assert set(rule) == {"street"}
    most = max(set(sp), key=sp.count)
    assert sp.count(most) >= 0.6 * len(sp) and most in S["assign"]["pools"]["street"]
    # a square whose trees are known
    sq = Polygon([(0, 100), (40, 100), (40, 140), (0, 140)])
    sp, rule = _assign([10.0, 30.0], [110.0, 130.0], ctx={"squares": {"Place d'Armes": [sq]}})
    assert sp == ["plane", "plane"] and rule == ["named", "named"]


def test_trees_in_a_wood_take_the_wood_mix_and_those_by_the_water_the_riverside_mix():
    rng = np.random.default_rng(4)
    k = 600
    e, n = rng.uniform(0, 300, k), rng.uniform(0, 300, k)
    wood = Polygon([(-10, -10), (310, -10), (310, 310), (-10, 310)])
    sp, rule = _assign(e, n, ctx={"woods": [wood]})
    assert set(rule) == {"wood"} and set(sp) <= set(S["assign"]["pools"]["wood"])
    water = [Polygon([(-10, -30), (310, -30), (310, -20), (-10, -20)])]
    sp, rule = _assign([10.0, 20.0, 30.0], [-15.0, -14.0, 200.0], water=water)
    assert rule[:2] == ["water", "water"] and rule[2] != "water" and set(sp[:2]) <= set(S["assign"]["pools"]["water"])
