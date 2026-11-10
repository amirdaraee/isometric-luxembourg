"""What the viewer must show with a cutaway on (v2/checks/cutaway_view_checks.py Window.expected), on one made-up
tile: a replaced building's pixels of layer 5 are gone, the cutaway's are in their place, ties go to the later."""
import numpy as np

from v2.checks.cutaway_view_checks import Window, probe_grid
from v2.layers.common import TILE, depth_ref, write_tile

NAME = "3_2"


def tile(folder, depth_m, k=None, ids=None, value=100):
    ref = depth_ref(NAME)[:, None]
    d = np.where(np.isfinite(depth_m), ref + depth_m, np.inf)
    rgb = np.full((TILE, TILE, 3), value, np.uint8)
    return write_tile(folder / "0", NAME, rgb=rgb, depth=d, normal=np.tile([0.0, 0.0, 1.0], (TILE, TILE, 1)),
                      k=k, ids=ids, q=101)


def test_expected_frame_with_and_without_the_cutaway(tmp_path):
    inf = np.full((TILE, TILE), np.inf)
    ground = np.full((TILE, TILE), 10.0)
    b = inf.copy(); bid = np.zeros((TILE, TILE), np.uint32)
    b[100:200, 100:200] = 5.0; bid[100:200, 100:200] = (3 << 8) | 11       # building 3: the landmark
    b[100:200, 300:400] = 6.0; bid[100:200, 300:400] = (4 << 8) | 23       # building 4: another
    c = inf.copy(); ck = np.zeros((TILE, TILE), np.uint8)
    c[100:200, 150:200] = 7.0; ck[100:200, 150:200] = 2                    # the kept half's section, further back
    c[100:200, 300:400] = 6.0; ck[100:200, 300:400] = 7                    # the other building, at layer 5's depth
    idx = {"layers": {L: {"tiles": {"0": {}}} for L in ("ground", "relief", "water", "transport", "buildings", "structures", "trees")},
           "cutaways": {"landmarks": {"x": {"replaces_index": [3], "tiles": {"0": {}}}}}}
    idx["layers"]["ground"]["tiles"]["0"][NAME] = tile(tmp_path / "ground", ground, k=np.full((TILE, TILE), 6, np.uint8))
    idx["layers"]["buildings"]["tiles"]["0"][NAME] = tile(tmp_path / "buildings", b, k=(np.isfinite(b)).astype(np.uint8), ids=bid, value=50)
    idx["cutaways"]["landmarks"]["x"]["tiles"]["0"][NAME] = tile(tmp_path / "cutaways" / "x", c, k=ck, ids=bid, value=200)
    w = Window(tmp_path, idx, 3 * TILE, 2 * TILE, TILE, TILE)
    off = w.expected([])
    assert (off["layer"][100:200, 100:200] == 5).all() and (off["k"][100:200, 100:200] == 1).all() and not off["from_cut"].any()
    assert (off["layer"][0:50] == 1).all() and (off["rgb"][150, 150] == 50).all()
    on = w.expected(["x"])
    assert (on["layer"][100:200, 100:150] == 1).all()                       # the slice: open to the ground behind
    assert (on["layer"][100:200, 150:200] == 5).all() and (on["k"][100:200, 150:200] == 2).all()
    assert np.allclose(on["depth"][150, 175] - depth_ref(NAME)[150], 7.0, atol=0.006) and (on["rgb"][150, 175] == 200).all()
    assert on["from_cut"][100:200, 300:400].all() and (on["k"][100:200, 300:400] == 7).all()   # a tie: the later one
    assert np.array_equal(on["depth"][:, 300:400], off["depth"][:, 300:400])


def test_probe_grid_covers_the_footprint_at_the_floor():
    lm = {"replaces_index": [0], "floor_z": 301.0}
    blds = [{"footprint": [[[[100.0, 200.0], [120.0, 200.0], [120.0, 230.0], [100.0, 230.0], [100.0, 200.0]]]]}]
    p = np.array(probe_grid(lm, blds, step=4.0, margin=6.0))
    assert p[:, 0].min() == 94.0 and p[:, 0].max() >= 122.0 and p[:, 1].max() >= 232.0 and (p[:, 2] == 301.0).all()
    assert len(p) == 8 * 11
