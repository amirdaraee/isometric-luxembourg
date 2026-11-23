"""Ground cover from the orthophoto (v2/data/scene/groundcover.py): the classing on a made-up photo."""
import numpy as np

from v2.config import params
from v2.data.scene import groundcover as GC
from v2.data.scene.grid import Grid

P = params()["groundcover"]
STEP = 0.5
GREY, LAWN, STRAW, SHADE = (150, 148, 146), (92, 128, 60), (170, 150, 110), (20, 24, 22)


def photo(n=240):
    rgb = np.tile(np.array(GREY, np.uint8), (n, n, 1))
    return rgb, np.ones((n, n), bool)


def test_a_lawn_is_vegetated_with_its_dry_patches_and_a_square_with_a_planter_is_not():
    rgb, readable = photo()
    rgb[20:120, 20:120] = LAWN                                           # a lawn of 50 m by 50 m
    rgb[60:70, 30:110] = STRAW                                           # a dry strip across it
    rgb[160:166, 160:166] = LAWN                                         # a planter of 3 m on the paving
    veg = GC.classify(rgb, readable, P, STEP)
    assert veg[30:110, 30:110].all()                                     # the lawn, its dry strip with it
    assert not veg[150:176, 150:176].any()                               # the planter does not make a lawn
    assert not veg[200:, :].any() and not veg[:, 200:].any()             # paving stays paving


def test_a_street_trees_crown_does_not_turn_its_pavement_into_lawn():
    """A crown is green over paving too. Under the surveyed crown the photo is not read, and the paving round it
    decides."""
    rgb, readable = photo()
    yy, xx = np.mgrid[0:240, 0:240]
    crown = (yy - 120) ** 2 + (xx - 120) ** 2 <= 10 ** 2                 # a crown of 5 m radius
    rgb[crown] = LAWN
    assert not GC.classify(rgb, readable & ~crown, P, STEP).any()
    # the same crown on a lawn: the lawn round it decides, and the ground under it is lawn
    rgb2, _ = photo(); rgb2[60:180, 60:180] = LAWN
    assert GC.classify(rgb2, readable & ~crown, P, STEP)[115:125, 115:125].all()


def test_shadow_is_not_read_and_takes_its_surroundings_answer():
    rgb, readable = photo()
    rgb[40:200, 40:200] = LAWN
    rgb[100:140, 100:140] = SHADE                                        # a building's shadow on the lawn
    assert GC.classify(rgb, readable, P, STEP)[105:135, 105:135].all()
    rgb2, _ = photo(); rgb2[100:140, 100:140] = SHADE                     # the same shadow on paving
    assert not GC.classify(rgb2, readable, P, STEP).any()


def test_the_ground_is_asked_by_place_and_is_not_vegetated_outside_the_grid():
    z = np.zeros((4, 6), np.float32); z[1, 2] = 1                        # row 0 south
    g = Grid(z, 1000.0, 2000.0, STEP)
    e = np.array([1000.0 + 2.5 * STEP, 1000.0 + 0.5 * STEP, 900.0, 1000.0 + 2.5 * STEP])
    n = np.array([2000.0 + 1.5 * STEP, 2000.0 + 1.5 * STEP, 2000.0, 2100.0])
    assert GC.vegetated(g, e, n).tolist() == [True, False, False, False]
