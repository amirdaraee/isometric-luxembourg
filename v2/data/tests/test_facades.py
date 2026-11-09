import numpy as np
from shapely.geometry import Polygon, box

from v2.config import params
from v2.data.scene.facades import eave_height, layout, wall_frame, window_world

P = params()["facades"]


def wall(L, H, gable=0.0):
    """A wall ring along E from (0, 0), L long, H to the eave, with an optional gable rising `gable` m."""
    pts = [(0, 0, 0), (L, 0, 0), (L, 0, H)]
    if gable:
        pts.append((L / 2, 0, H + gable))
    pts += [(0, 0, H), (0, 0, 0)]
    return [[x + 1000, y + 2000, z + 300] for x, y, z in pts]


def test_frame_faces_away_from_the_building():
    fr = wall_frame(wall(10, 9), centre=np.array([1005.0, 2005.0]))   # building to the north
    o, u, n, poly, L, z0, flat = fr
    assert n[1] < -0.99 and abs(L - 10) < 1e-9 and abs(z0 - 300) < 1e-9 and flat < 1e-9


def test_floors_bays_and_straight_rows():
    poly = Polygon([(0, 0), (12, 0), (12, 9.6), (0, 9.6)])
    floors, bays, wins = layout(poly, 12.0, 9.6, P)
    assert floors == 3                                    # 3.6 + 3.0 + 3.0
    assert bays == int((12 - 2 * P["edge_margin_m"]) // P["bay_m"])
    assert len(wins) == floors * bays
    rows = sorted({w[1] for w in wins})
    assert rows == sorted({round(v + P["sill_m"], 3) for v in (0, 3.6, 6.6)})
    for w in wins:                                        # inside the wall, never overlapping
        assert poly.buffer(-P["inset_m"] + 1e-6).contains(box(*w))


def test_gable_gets_no_windows_above_the_eave():
    ring = np.array(wall(8, 6.6, gable=4))
    o, u, n, poly, L, z0, flat = wall_frame(ring, centre=np.array([1004.0, 2004.0]))
    H = eave_height(poly, L)
    assert abs(H - 6.6) < 0.5
    floors, bays, wins = layout(poly, L, H, P)
    assert all(w[3] <= 6.6 for w in wins)


def test_window_world_corners():
    rec = {"base": [[0, 0, 300], [10, 0, 300]], "length": 10}
    c = window_world(rec, [1, 1, 2, 3])
    assert c[0] == (1, 0, 301) and c[2] == (2, 0, 303)
