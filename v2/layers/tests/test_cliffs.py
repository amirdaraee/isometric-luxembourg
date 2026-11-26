"""Cliffs and walls (v2/layers/cliffs.py): the rock's drawing is one pale face with a few big clefts and a function
of the place only; where a rock face is; a low face; a face's smooth border."""
import numpy as np

from v2.layers import cliffs
from v2.layers.common import R2, pal

INK = np.array(pal("ink", "outline"), float)
CLEFT = np.array(pal("relief", "rock_cleft"), float)


def face(n_across=4000, n_up=160, step=0.125):
    """An upright face 500 m across and 20 m tall, sampled as the map does: (e, n, z) grids (up, across)."""
    a = np.arange(n_across) * step
    z = 260 + np.arange(n_up) * step
    A, Z = np.meshgrid(a, z)
    return 1000 + A * R2, 2000 + A * R2, Z                      # across the screen: e + n grows


def test_rock_is_a_function_of_the_place_only():
    e, n, z = (v.ravel() for v in face(800, 80))
    whole = cliffs.rock(e, n, z)
    assert np.array_equal(whole, cliffs.rock(e, n, z))
    h = len(e) // 3
    parts = np.vstack([cliffs.rock(e[:h], n[:h], z[:h]), cliffs.rock(e[h:], n[h:], z[h:])])
    assert np.array_equal(whole, parts)                        # a tile and its neighbour draw the same rock
    assert whole.shape == (len(e), 3) and (whole >= 0).all() and (whole <= 255).all()


def test_rock_is_one_pale_face_with_a_few_big_clefts():
    """The owner turned down a rock of stacked blocks ("no noo, what is this? find a real photo of this cliff and
    compare"). The photo shows one massive pale face, a few big clefts, no blocks, nothing black."""
    e, n, z = face()
    c = cliffs.rock(e.ravel(), n.ravel(), z.ravel()).reshape(e.shape + (3,))
    cleft = (c == CLEFT).all(-1)
    assert not (c == INK).all(-1).any()                        # no ink in the rock: a cleft is dark brown
    assert 0.02 < cleft.mean() < 0.09                          # the clefts are a small part: the face is stone
    stone = c[~cleft]
    T = np.array([pal("relief", k) for k in ("rock_1", "rock_2", "rock_3")], float)
    plain = (stone[:, None, :] == T[None]).all(-1).any(1)
    assert plain.mean() > 0.6                                  # most of the face is one of three near tones, flat
    assert stone[:, 0].min() > 110                             # nothing in the stone is dark (the darkest tone, in a
                                                               # flank, under a stroke and a stain, is 116)
    assert np.median(stone, axis=0)[0] > 200                   # pale gold
    # along a level line, the clefts are few and far apart: about one in 11 m, never a pillar every few metres
    gaps = []
    for row in cleft[::20]:
        starts = np.flatnonzero(row[1:] & ~row[:-1])
        assert len(starts) < 500 / 11.0 + 5
        gaps += list(np.diff(starts) * 0.125)
    gaps = np.array(gaps)
    assert np.median(gaps) > 8.0 and gaps.std() / gaps.mean() > 0.25      # ... and not evenly spaced
    # a cleft opens and closes up the face: no level line has all of them, and each is open on some
    assert (cleft.any(0) & ~cleft.all(0)).sum() > 0.5 * cleft.any(0).sum()
    widths = [len(r) for row in cleft[::20] for r in np.split(np.flatnonzero(row), np.flatnonzero(np.diff(np.flatnonzero(row)) > 1) + 1) if len(r)]
    assert max(widths) * 0.125 <= 1.5 + 0.126                  # the widest cleft is a metre and a half


def test_rock_does_not_change_with_the_light_or_the_side_it_faces():
    """The same face seen at another place has about the same share of clefts and the same median tone: nothing
    in the drawing knows a direction but across the screen and up."""
    e, n, z = face()
    a = cliffs.rock(e.ravel(), n.ravel(), z.ravel())
    b = cliffs.rock((e + 700).ravel(), (n - 300).ravel(), (z + 31).ravel())
    ia, ib = (a == CLEFT).all(-1), (b == CLEFT).all(-1)
    assert abs(ia.mean() - ib.mean()) < 0.03
    assert abs(np.median(a[~ia, 1]) / np.median(b[~ib, 1]) - 1) < 0.07     # a tone's step is 7%: within one


def test_dry_stone_and_masonry_are_coursed_and_a_walls_top_is_its_coping():
    e, n, z = (v.ravel() for v in face(800, 80))
    d = cliffs.dry_stone(e, n, z)
    joint = (d == np.array(pal("relief", "drystone_joint"), float)).all(-1)
    assert 0.08 < joint.mean() < 0.3 and d[~joint, 0].min() > 100
    P = np.column_stack([e, n, z])
    nrm = np.tile([R2, -R2, 0.0], (len(e), 1))                 # an upright face
    m = cliffs.masonry(P, nrm)
    mj = (m == np.array(pal("relief", "masonry_joint"), float)).all(-1)
    assert 0.08 < mj.mean() < 0.3
    stone = m[~mj]
    assert abs(stone[:, 0] - stone[:, 2]).mean() < abs(d[~joint][:, 0] - d[~joint][:, 2]).mean()   # greyer than the rock
    top = cliffs.masonry(P[:50], np.tile([0.0, 0.0, 1.0], (50, 1)))
    assert (top == np.array(pal("relief", "coping"), float)).all()


def test_a_rock_face_is_rock_from_top_to_foot_and_a_ledge_stays():
    step = 0.5
    cls = np.zeros((200, 300), np.uint8)
    slope = np.zeros(cls.shape)
    cls[60:80, 40:260] = 2                                     # two bands of cliff, 10 m each ...
    cls[86:106, 40:260] = 2
    slope[60:106, 40:260] = 70
    cls[80:86, 40:260] = 1                                     # ... with steep ground between them
    slope[80:86, 100:112] = 10                                 # and a patch of lawn in the face: 3 m by 6 m
    cls[80:86, 100:112] = 0
    cls[70:76, 180:240] = 0                                    # a real ledge: 3 m by 30 m
    slope[70:76, 180:240] = 5
    cls[150:160, 40:80] = 1                                    # steep ground far from any cliff
    slope[150:160, 40:80] = 40
    zone = cliffs.rock_zone(cls, slope, step, 35.0)
    assert zone[60:106, 40:98].all()                           # the face, the steep strip between its bands with it
    assert zone[80:86, 100:112].all()                          # the patch of lawn is rock
    assert not zone[71:75, 185:235].any()                      # the ledge stays
    assert not zone[150:160, 40:80].any()                      # steep ground that is not at a cliff is not rock
    assert not zone[:50].any() and not zone[120:148].any()     # flat ground is not rock, and the open land is no "gap"


def test_a_low_face_is_told_from_a_cliff():
    step = 0.5
    z = np.zeros((80, 200))
    z[:, 60:] += 2.0                                           # a terrace's wall: 2 m
    z[:, 140:] += 12.0                                         # a cliff: 12 m
    h = cliffs.face_height(z, step)
    assert h[40, 60] < cliffs.LOW_FACE_M < h[40, 140]
    assert h[40, 20] < 0.01


def test_a_border_read_between_the_cells_is_a_smooth_line_and_a_narrow_face_is_kept():
    from v2.data.scene.grid import read_soft, soft_mask
    ii, jj = np.mgrid[0:80, 0:80]
    mask = jj > 20 + ii / 3.0                       # a slanted border: on the grid, a step every three cells
    mask[:, 70] = True; mask[:, 66:70] = False; mask[:, 71:] = False     # and a face one cell wide
    f = soft_mask(mask, 1.0)
    i = np.linspace(10, 70, 600)
    def border(read):                               # where the border is on each row, in cells
        j = np.linspace(15, 60, 1801)
        return np.array([j[np.argmax(read(np.full_like(j, a), j))] for a in i])
    rough = border(lambda a, b: mask[np.rint(a).astype(int), np.rint(b).astype(int)]) - (20 + i / 3.0)
    smooth = border(lambda a, b: read_soft(f, a, b)) - (20 + i / 3.0)
    assert np.ptp(rough) > 0.9 and np.ptp(smooth) < 0.25         # the staircase's teeth are gone
    assert abs(smooth.mean()) < 0.6                              # and the border has not moved
    assert read_soft(f, np.array([40.0]), np.array([70.0]))[0]   # the narrow face is still there
    assert not read_soft(f, np.array([40.0, -3.0]), np.array([67.5, 5.0])).any()   # ... no wider, and nothing off the grid


def test_a_short_piece_of_wall_left_beside_a_face_is_part_of_the_face():
    near = np.zeros(200, bool)                         # a wall of 100 m, sampled every half metre
    near[20:90] = True                                 # 35 m of it along a rock face
    near[110:120] = True                               # and 5 m more, 10 m further on
    out = cliffs.wall_on_face(near, 0.5)
    assert out[:120].all()                             # the 10 m before the face and the 10 m between: left-overs
    assert not out[120:].any()                         # the 40 m after it is a wall
    assert not cliffs.wall_on_face(np.zeros(12, bool), 0.5).any()     # a short wall nowhere near a face stays
