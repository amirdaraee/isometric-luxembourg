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


def test_a_well_known_building_gets_its_own_materials():
    from v2.layers.art_a import landmark_styles
    known = landmark_styles()
    assert known and all(set(v) <= {"name", "stone", "facade", "roof", "kind", "windows"} for v in known.values())
    assert all(v.get("kind", "place_of_worship") == "place_of_worship" and v.get("windows", "round") in ("round", "pointed")
               for v in known.values())
    assert landmark_styles("kinds")["place_of_worship"]["stone"] is True
    for bid, k in known.items():
        st = Style(bid, "gable", k)
        assert st.roof_name == k["roof"] and st.stone == bool(k.get("stone"))
        assert "facade" not in k or (st.facade == k["facade"] and k["facade"] in FACADES)


# ------------------------------------------------------------------------------------------------ places of worship
def _scene(walls, worship=None, n_buildings=3):
    """The least of a scene the art needs: buildings by id and the facade layout."""
    from types import SimpleNamespace
    return SimpleNamespace(buildings=[{"id": f"B{i}", "roof_shape": "gable"} for i in range(n_buildings)],
                           facades={"walls": walls, "worship": worship or {}})


def _wall(b, e0, windows, doors=(), **more):
    w = {"building": f"B{b}", "wall": f"w{e0}", "base": [[e0, 0.0, 300.0], [e0 + 12.0, 0.0, 300.0]], "normal": [0.0, -1.0],
         "length": 12.0, "height": 12.0, "outline": [[0, 0], [12, 0], [12, 12], [0, 12], [0, 0]], "floors": 3,
         "windows": [list(x) for x in windows], "doors": [list(x) for x in doors], "shopfronts": []}
    w.update(more)
    return w


def _art(scene):
    from v2.layers.art_a import ArtA
    empty = {"V": np.zeros((0, 3)), "T": np.zeros((0, 3), np.int64), "kind": np.zeros(0, np.int64), "obj": np.zeros(0, np.int64)}
    return ArtA(scene, empty)


def test_an_arched_window_is_the_layouts_rectangle_with_a_round_or_a_pointed_head():
    from shapely.geometry import Polygon
    from v2.layers.art_a import POINTED, arch_outline, head_height
    for pointed in (False, True):
        pts = arch_outline(2.0, 3.0, 3.3, 10.0, pointed)
        poly = Polygon(pts)
        assert poly.is_valid and poly.exterior.is_ccw and abs(poly.convex_hull.area - poly.area) < 1e-9    # convex: a fan
        x0, y0, x1, y1 = poly.bounds
        assert (round(x0, 6), round(y0, 6), round(x1, 6), round(y1, 6)) == (2.0, 3.0, 3.3, 10.0)       # never outside it
        assert abs(head_height(1.3, pointed) - (1.3 * POINTED if pointed else 0.65)) < 1e-12
        top = [p for p in pts if abs(p[1] - 10.0) < 1e-9]
        assert len(top) == 1 and abs(top[0][0] - 2.65) < 1e-9                                         # one apex, in the middle
    assert Polygon(arch_outline(0, 0, 1.3, 9, True)).area < Polygon(arch_outline(0, 0, 1.3, 9, False)).area


def test_a_church_has_arched_windows_no_shutters_and_keeps_every_other_walls_window_numbers():
    from v2.layers.art_a import OPEN_KIND
    house = [(1.0, 0.9, 2.1, 2.35), (4.0, 0.9, 5.1, 2.35), (7.0, 0.9, 8.1, 2.35)]
    door = [(9.5, 0.0, 10.7, 2.3, "rule:street door", "door")]
    before = _art(_scene([_wall(0, 0, house, door), _wall(1, 20, house, door), _wall(2, 40, house, door)])).openings_mesh()
    # building 1 becomes a church: its wall keeps what the house rule had as a count, and gets one tall window
    church = _wall(1, 20, [(5.35, 2.6, 6.65, 11.0)], door, worship="pointed",
                   house_rule={"windows": [list(x) for x in house], "doors": 1, "shopfronts": 0})
    A = _art(_scene([_wall(0, 0, house, door), church, _wall(2, 40, house, door)],
                    {"B1": {"source": "osm:way/1", "name": "x", "share": 1.0, "walls": 1}}))
    after = A.openings_mesh()

    def numbers(M, b):
        on = M["open_bld"] == b
        return sorted(set(zip(M["open_kind"][on].tolist(), M["tone"][on].tolist())))
    assert numbers(after, 0) == numbers(before, 0) and numbers(after, 2) == numbers(before, 2)
    assert before["tone"].tolist() == (np.arange(len(before["T"])) // 2).tolist()      # the numbers the art always used
    k1 = after["open_kind"][after["open_bld"] == 1]
    assert set(k1.tolist()) == {OPEN_KIND["church"], OPEN_KIND["portal"]}             # no house window, no shutter
    assert (after["tone"][after["open_bld"] == 1] < 0).all()
    assert (after["head"][after["open_kind"] == OPEN_KIND["church"]] == 2).all()
    assert A.styles[1].church and A.styles[1].stone and not A.styles[1].rustic
    # the arched window's triangles stay inside the layout's rectangle and reach its top and bottom
    V = after["V"][after["T"][after["open_kind"] == OPEN_KIND["church"]]].reshape(-1, 3)
    assert V[:, 0].min() >= 25.35 - 1e-9 and V[:, 0].max() <= 26.65 + 1e-9
    assert abs(V[:, 2].min() - 302.6) < 1e-9 and abs(V[:, 2].max() - 311.0) < 1e-9


def test_church_glass_and_doors_are_their_own_materials_without_light():
    from v2.layers.art_a import OPEN_KIND
    from v2.layers.common import CLASS, pal
    church = _wall(1, 20, [(5.35, 2.6, 6.65, 11.0)], [(9.5, 0.0, 10.7, 2.3, "rule:street door", "door")], worship="round",
                   house_rule={"windows": [], "doors": 1, "shopfronts": 0})
    A = _art(_scene([church], {"B1": {"source": "osm:way/1", "name": "x", "share": 1.0, "walls": 1}}))
    O = A.openings_mesh()
    for kind, lo, hi in (("church", (25.35, 302.6), (26.65, 311.0)), ("portal", (29.5, 300.0), (30.7, 302.3))):
        ti = np.flatnonzero(O["open_kind"] == OPEN_KIND[kind])
        xs, zs = np.meshgrid(np.linspace(lo[0] + 0.01, hi[0] - 0.01, 60), np.linspace(lo[1] + 0.01, hi[1] - 0.01, 200))
        P = np.column_stack([xs.ravel(), np.full(xs.size, -0.05), zs.ravel()])
        rgb, cls = A.openings_rgb(O, np.full(len(P), ti[0]), P, np.full(len(P), 1))
        names = {int(c) for c in set(cls.tolist())}
        if kind == "church":
            assert names == {CLASS["window"], CLASS["trim"]}
            glass = rgb[cls == CLASS["window"]]
            house = pal("buildings", "window")
            assert np.abs(glass - house).max(1).min() > 8                       # nowhere the house window's glass
            assert len(np.unique(np.round(glass), axis=0)) >= 4                 # leaded panes in several colours
            lum = glass @ np.array([0.2126, 0.7152, 0.0722])
            panes = lum > 0.8 * lum.max()                                       # the panes, without the lead lines
            assert panes.mean() > 0.7 and np.ptp(lum[panes]) < 0.02 * lum.max()  # every pane as light as the next
            assert (cls.reshape(xs.shape)[:2] == CLASS["trim"]).all()           # a stone sill at its foot
        else:
            assert names == {CLASS["door"], CLASS["trim"]} and CLASS["window"] not in names     # no fanlight
        # the same picture whatever the wall's direction: nothing here knows a sun
        rgb2, cls2 = A.openings_rgb(O, np.full(len(P), ti[0]), P, np.full(len(P), 1))
        assert (rgb == rgb2).all() and (cls == cls2).all()


def test_church_window_kinds_tracery_rose_and_belfry_are_drawn_in_stone_glass_and_wood_without_light():
    """Round two (13 Nov 2026): a traceried window has a straight stone mullion, a rose is a circle with stone
    spokes, a belfry opening has louvres and no glass, the portal is stone and wood; stained panes differ in colour
    and not in brightness."""
    from v2.layers.art_a import OPEN_KIND
    from v2.layers.common import CLASS
    from v2.layers.data import NIGHT_CHURCH
    wins = [(1.0, 2.6, 3.2, 11.0, "traceried"), (5.0, 6.0, 8.0, 9.0, "rose"), (9.0, 7.0, 10.0, 10.0, "belfry")]
    church = _wall(1, 20, wins, [(5.4, 0.0, 7.6, 4.0, "rule:church portal", "portal")], worship="pointed", merged=["a"],
                   house_rule={"windows": [], "doors": 0, "shopfronts": 0}, buttresses=[[3.6, 0.0, 4.5, 8.0]], courses=[2.25])
    A = _art(_scene([church], {"B1": {"source": "osm:way/1", "name": "x", "share": 1.0, "walls": 1}}))
    O = A.openings_mesh()
    assert set(O["open_kind"].tolist()) == {OPEN_KIND[k] for k in ("traceried", "rose", "belfry", "entrance")}
    assert set(O["head"][O["open_kind"] == OPEN_KIND["rose"]].tolist()) == {3}             # a circle
    V = O["V"][O["T"][O["open_kind"] == OPEN_KIND["rose"]]].reshape(-1, 3)
    assert np.hypot(V[:, 0] - 26.5, V[:, 2] - 307.5).max() <= 1.5 + 1e-9                   # inside its square's circle

    def draw(kind, lo, hi):
        ti = np.flatnonzero(O["open_kind"] == OPEN_KIND[kind])
        xs, zs = np.meshgrid(np.linspace(lo[0] + 0.01, hi[0] - 0.01, 111), np.linspace(lo[1] + 0.01, hi[1] - 0.01, 201))
        P = np.column_stack([xs.ravel(), np.full(xs.size, -0.05), zs.ravel()])
        rgb, cls = A.openings_rgb(O, np.full(len(P), ti[0]), P, np.full(len(P), 1))
        return rgb.reshape(xs.shape + (3,)), cls.reshape(xs.shape), xs, zs
    lumw = np.array([0.2126, 0.7152, 0.0722])
    # traceried: the mullion is stone all the way up its centre line to the springing; glass either side of it
    rgb, cls, xs, zs = draw("traceried", (21.0, 302.6), (23.2, 311.0))
    mid = xs.shape[1] // 2
    below = zs[:, 0] < 311.0 - 0.866 * 2.2 - 0.1
    assert (cls[below, mid] == CLASS["trim"]).all() and (cls[below][:, mid - 12] == CLASS["window"]).mean() > 0.9
    glass = rgb[cls == CLASS["window"]] @ lumw
    panes = glass > 0.8 * glass.max()
    assert np.ptp(glass[panes]) < 0.02 * glass.max() and len(np.unique(np.round(rgb[cls == CLASS["window"]]), axis=0)) >= 5
    # rose: stone spokes and glass between them, the same count on every ring of pixels round the hub
    rgb, cls, xs, zs = draw("rose", (25.0, 306.0), (28.0, 309.0))
    r = np.hypot(xs - 26.5, zs - 307.5)
    assert (cls[r < 0.15] == CLASS["trim"]).all() and (cls[(r > 0.3) & (r < 0.8)] == CLASS["window"]).mean() > 0.6
    # belfry: louvres of wood in a stone frame, no glass
    rgb, cls, xs, zs = draw("belfry", (29.0, 307.0), (30.0, 310.0))
    assert set(cls.ravel().tolist()) == {CLASS["door"], CLASS["trim"]}
    wood = rgb[cls == CLASS["door"]]
    assert len(np.unique(np.round(wood), axis=0)) == 2                                     # slats and the dark between them
    # the portal: stone orders and a tympanum, plank leaves, no glass
    rgb, cls, xs, zs = draw("entrance", (25.4, 300.0), (27.6, 304.0))
    assert set(cls.ravel().tolist()) == {CLASS["door"], CLASS["trim"]} and (cls[:60, mid - 20] == CLASS["door"]).all()
    assert (cls[-12:] == CLASS["trim"]).all()
    # the wall: the string course is stone trim, straight
    n = 400
    u, v = np.linspace(0.05, 11.95, n), np.full(n, 2.25)
    P = np.column_stack([20 + u, np.zeros(n), 300 + v])
    cl = np.full(n, CLASS["building"])
    A.tri_wall = np.zeros(1, np.int64)
    A.walls_rgb(np.full(n, 1), np.zeros(n, np.int64), P, np.zeros(n), np.zeros(n), cls_out=cl)
    assert (cl[(u < 3.6) | (u > 4.5)] == CLASS["trim"]).all()                              # the course, up to the buttress
    v = np.linspace(1.0, 7.9, n)
    P = np.column_stack([np.full(n, 20 + 4.05), np.zeros(n), 300 + v])
    cl = np.full(n, CLASS["building"])
    face = A.walls_rgb(np.full(n, 1), np.zeros(n, np.int64), P, np.zeros(n), np.zeros(n), cls_out=cl)
    P[:, 0] = 20 + 3.66
    line = A.walls_rgb(np.full(n, 1), np.zeros(n, np.int64), P, np.zeros(n), np.zeros(n))
    P[:, 0] = 20 + 5.2
    wall = A.walls_rgb(np.full(n, 1), np.zeros(n, np.int64), P, np.zeros(n), np.zeros(n))
    # the buttress: the wall's own stone a little lighter, between two dark upright lines, bottom to top
    assert (cl[np.abs(v - 2.25) > 0.3] == CLASS["building"]).all()
    low = (v < 4.0) & (np.abs(v - 2.25) > 0.3)                                             # its lower stage, off the course
    assert (line @ lumw)[low].mean() < 0.75 * (wall @ lumw)[low].mean()
    assert 1.0 < np.median(face @ lumw) / np.median(wall @ lumw) < 1.08
    # by night: glass kinds have a row, a belfry opening has none
    assert NIGHT_CHURCH[("traceried", "pointed")] == 11 and NIGHT_CHURCH[("rose", "round")] == 12 and ("belfry", "round") not in NIGHT_CHURCH


def test_a_church_wall_turned_round_keeps_the_night_rows_the_house_rule_had():
    """A window's seed in the viewer is its row number. A church wall whose frame was turned round (its normal had
    pointed into the building) keeps the dark rows it had when it faced the camera in the house rule's frame, and
    gives none when it did not: every other building's rows stay where they were."""
    from types import SimpleNamespace
    from v2.layers.data import NIGHT_DARK, night_data
    house = [(1.0, 0.9, 2.1, 2.35), (4.0, 0.9, 5.1, 2.35)]
    hr = {"windows": [list(x) for x in house], "doors": 1, "shopfronts": 0}
    out = [[0, 0], [12, 0], [12, 12], [0, 12], [0, 0]]
    glass = [(5.0, 2.6, 7.0, 11.0, "traceried"), (9.0, 7.0, 10.0, 10.0, "belfry")]

    def rows(walls):
        sc = _scene(walls, {"B1": {"source": "osm:way/1", "name": "x", "share": 1.0, "walls": 1}})
        win, _ = night_data(SimpleNamespace(scene=sc, ground_osm_path=None))
        return win
    before = rows([_wall(0, 0, house), _wall(1, 20, house), _wall(2, 40, house)])          # all three face the camera
    assert before[:, 6].tolist() == [0, 0, 1, 1, 2, 2]
    # building 1 is a church; its wall faced the camera and still does: dark rows in place, its glass at the end
    same = rows([_wall(0, 0, house), _wall(1, 20, glass, worship="round", house_rule=hr), _wall(2, 40, house)])
    assert same[:, 7].tolist() == [0, 0, NIGHT_DARK, NIGHT_DARK, NIGHT_DARK, 0, 0, 10]      # no row for the belfry opening
    assert (same[[0, 1, 5, 6]] == before[[0, 1, 4, 5]]).all()
    # the wall was turned round and now faces away: the dark rows stay, no glass is seen
    away = rows([_wall(0, 0, house), _wall(1, 20, glass, worship="round", normal=[0.0, 1.0], house_rule=dict(hr, outline=out)),
                 _wall(2, 40, house)])
    assert away[:, 7].tolist() == [0, 0, NIGHT_DARK, NIGHT_DARK, NIGHT_DARK, 0, 0]
    # it had faced away and was turned to the camera: no dark rows (it had none), its glass at the end
    to = rows([_wall(0, 0, house), _wall(1, 20, glass, worship="round", house_rule=dict(hr, outline=out)), _wall(2, 40, house)])
    assert to[:, 7].tolist() == [0, 0, 0, 0, 10] and (to[:4] == before[[0, 1, 4, 5]]).all()
