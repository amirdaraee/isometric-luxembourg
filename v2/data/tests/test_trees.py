"""Layer 7 rule 1: the drawn crown follows the tree's shape by species and age; its height is never touched."""
import numpy as np

from v2.config import params
from v2.data.scene.trees import shape_radius

P = params()["trees"]
NAMES = P["types"]


def _r(h, r_survey, typ, e=None, n=None):
    h = np.asarray(h, float)
    e = np.arange(len(h)) * 100.0 if e is None else np.asarray(e, float)      # far apart: no neighbour cap
    n = np.zeros(len(h)) if n is None else np.asarray(n, float)
    return shape_radius(h, np.asarray(r_survey, float), np.asarray(typ), e, n, P, NAMES)[0]


def test_a_tall_broadleaf_with_a_narrow_survey_crown_is_no_longer_a_poplar():
    r = _r([20.0], [1.4], [0])                       # the survey: 2.8 m wide on a 20 m tree
    assert 2 * r[0] == 20.0 * P["crown_shape"]["by_type"]["deciduous_green"]["mature"]
    assert 20.0 / (2 * r[0]) < 2.5


def test_width_grows_with_age_and_conifers_stay_slimmer():
    young, mature = _r([6.0, 20.0], [0.5, 0.5], [0, 0])
    assert young / 6.0 < mature / 20.0               # the ratio grows with height (age)
    assert _r([20.0], [0.5], [2])[0] < mature        # a conifer of the same height is narrower


def test_never_narrower_than_surveyed_and_never_wider_than_the_cap():
    assert _r([10.0], [4.0], [0])[0] == 4.0          # the survey's own width is kept when it is wider
    c = P["crown_shape"]["by_type"]["deciduous_green"]
    assert _r([45.0], [1.0], [0])[0] == c["max_width_m"] / 2


def test_a_crown_has_no_more_room_than_its_neighbours_leave():
    r = _r([20.0, 20.0], [1.0, 1.0], [0, 0], e=[0.0, 3.0], n=[0.0, 0.0])      # two trees 3 m apart
    assert np.allclose(r, 3.0 * P["crown_shape"]["neighbour_factor"])
