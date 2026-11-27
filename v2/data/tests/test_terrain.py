"""Scene terrain: small deep pits inside paved squares are filled to the square's level (terrain.square_pits)."""
import numpy as np
from shapely.geometry import box

from v2.data.scene.terrain import fill_pits

P = {"min_depth_m": 1.0, "edge_m": 0.3, "max_area_m2": 150.0, "level_window_m": 20.0}
STEP = 0.5


def _ground():
    n, e = np.mgrid[0:200, 0:200] * STEP + STEP / 2                   # 100 m x 100 m, falling gently to the east
    return (300.0 - 0.01 * e).astype(np.float32), e, n


def test_a_small_deep_pit_in_a_square_is_filled_to_the_squares_level():
    z, e, n = _ground()
    flat = z.copy()
    stair = (np.abs(e - 50) < 2) & (np.abs(n - 50) < 3)               # 4 m x 6 m, 3 m deep
    z[stair] -= 3.0
    out, pits, cells = fill_pits(z, 0.0, 0.0, STEP, [box(20, 20, 80, 80)], P)
    assert pits == 1 and cells == stair.sum()
    assert np.abs(out - flat).max() < 0.05                            # the level, slope and all
    assert fill_pits(out, 0.0, 0.0, STEP, [box(20, 20, 80, 80)], P)[1:] == (0, 0)


def test_what_is_not_a_small_deep_pit_of_a_square_is_left():
    z, e, n = _ground()
    shallow = (np.abs(e - 40) < 2) & (np.abs(n - 40) < 2)             # a kerb's worth: 0.5 m
    wide = (np.abs(e - 60) < 8) & (np.abs(n - 60) < 8)                # 256 m2: a sunken court, not a stair
    outside = (np.abs(e - 10) < 2) & (np.abs(n - 10) < 2)             # deep, but not in the square
    z[shallow] -= 0.5; z[wide] -= 3.0; z[outside] -= 3.0
    out, pits, cells = fill_pits(z, 0.0, 0.0, STEP, [box(20, 20, 80, 80)], P)
    assert (pits, cells) == (0, 0) and np.array_equal(out, z)
    assert fill_pits(z, 0.0, 0.0, STEP, [], P)[1:] == (0, 0)
