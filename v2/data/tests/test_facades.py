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


# ------------------------------------------------------------------------------------------------ places of worship
def test_a_church_wall_gets_few_tall_windows_sized_to_it_in_one_straight_row():
    from v2.data.scene.church import row, window_width
    poly = Polygon([(0, 0), (20, 0), (20, 12), (0, 12)])
    bays, wins, base = row(poly, 20.0, 12.0, P)
    h = 12 - P["church_top_m"] - P["church_sill_m"]
    w = window_width(h, 20.0, P)
    assert base == 0 and len(wins) == bays == int((20 - 2 * P["edge_margin_m"]) // max(P["church_bay_m"], w + P["church_pier_m"]))
    _, _, house = layout(poly, 20.0, 12.0, P)
    assert len(wins) < len(house) / 4                     # few
    assert {(x[1], x[3], x[4]) for x in wins} == {(P["church_sill_m"], 12 - P["church_top_m"], "traceried")}    # one sill line, one top line
    for x in wins:
        assert abs(x[2] - x[0] - w) < 2e-3 and w > 1.5 * P["window_w_m"] and x[3] - x[1] > 3 * P["window_h_m"]   # wide and tall
        assert poly.buffer(-P["inset_m"] + 1e-6).contains(box(*x[:4]))
    # a very tall narrow wall: the window stops at its greatest height and is no wider than the wall's share
    _, wins, _ = row(Polygon([(0, 0), (6, 0), (6, 40), (0, 40)]), 6.0, 40.0, P)
    assert [round(x[3] - x[1], 3) for x in wins] == [P["church_window_max_h_m"]]
    assert abs(wins[0][2] - wins[0][0] - P["church_window_wall_share"] * 6.0) < 6e-3


def test_a_buttressed_church_wall_gets_one_window_between_each_pair_of_buttresses():
    from v2.data.scene.church import row
    from v2.data.scene.facades import clear_spans
    # a nave wall 30 m long and 14 m to the eave; four buttresses 1 m wide stand in front of it up to 12 m
    notches = [box(u, -1, u + 1.0, 12.0) for u in (5.0, 11.5, 18.0, 24.5)]
    poly = Polygon([(0, 0), (30, 0), (30, 14), (0, 14)])
    for n in notches:
        poly = poly.difference(n)
    spans = clear_spans(poly, 30.0, 2.4, 13.2, P["inset_m"])
    assert [(round(a, 1), round(b, 1)) for a, b in spans] == [(0.0, 4.8), (6.2, 11.3), (12.7, 17.8), (19.2, 24.3), (25.7, 30.0)]
    bays, wins, _ = row(poly, 30.0, 14.0, P)
    assert bays == len(wins) == 5
    assert {(x[1], x[3]) for x in wins} == {(P["church_sill_m"], 14 - P["church_top_m"])}
    for x, (a, b) in zip(wins, spans):
        assert a < x[0] and x[2] < b and poly.buffer(-P["inset_m"] + 1e-6).contains(box(*x[:4]))


def test_a_low_church_wall_gets_a_small_window_a_lower_one_round_windows_and_the_lowest_none():
    from v2.data.scene.church import row
    # 6 m: a lancet in proportion, its sill lower than a nave's
    _, wins, _ = row(Polygon([(0, 0), (6, 0), (6, 6), (0, 6)]), 6.0, 6.0, P)
    assert [x[4] for x in wins] == ["lancet"] and P["church_sill_min_m"] <= wins[0][1] < P["church_sill_m"]
    assert wins[0][3] - wins[0][1] >= P["church_window_min_h_m"]
    # 4.5 m: too low for a window that tall: round windows, not tiny arches
    _, wins, _ = row(Polygon([(0, 0), (12, 0), (12, 4.5), (0, 4.5)]), 12.0, 4.5, P)
    assert wins and {x[4] for x in wins} == {"oculus"}
    assert all(abs(x[2] - x[0] - P["church_oculus_d_m"]) < 2e-3 and abs((x[3] - x[1]) - (x[2] - x[0])) < 2e-3 for x in wins)
    assert len({(x[1], x[3]) for x in wins}) == 1
    # 3 m: nothing
    assert row(Polygon([(0, 0), (6, 0), (6, 3.0), (0, 3.0)]), 6.0, 3.0, P)[1] == []


def test_a_church_wall_standing_on_a_lower_roof_starts_its_windows_there():
    from v2.data.scene.church import row
    # the wall's lowest point is the ground at one end; under its bays it stands on an aisle roof 6 m up
    poly = Polygon([(0, 0), (0.5, 0), (0.5, 6), (12, 6), (12, 16), (0, 16)])
    _, wins, base = row(poly, 12.0, 16.0, P)
    assert wins and base == 6 and {x[1] for x in wins} == {6 + P["church_sill_m"]}


def test_a_churchs_wall_given_in_triangles_is_joined_into_one_wall():
    from v2.data.scene.church import row
    from v2.data.scene.facades import join_walls
    cen = np.array([1010.0, 2010.0])
    tris = [[(0, 0, 0), (18, 0, 0), (18, 0, 11), (0, 0, 0)], [(0, 0, 0), (18, 0, 11), (0, 0, 11), (0, 0, 0)]]
    members = []
    for i, t in enumerate(tris):
        o, u, n, poly, L, z0, flat = wall_frame([[x + 1000, y + 2000, z + 300] for x, y, z in t], cen)
        alone = row(poly, L, eave_height(poly, L), P)[1]                      # a triangle holds no full-height window
        assert all(x[3] - x[1] < 11 - P["church_top_m"] - P["church_sill_m"] - 1 for x in alone)
        members.append({"o": o, "u": u, "n": n, "poly": poly, "L": L, "z0": z0, "i": i})
    # a wall of the same building in another plane stays apart
    o, u, n, poly, L, z0, flat = wall_frame(wall(5, 11)[:0] + [[1018, 2000, 300], [1018, 2006, 300], [1018, 2006, 311], [1018, 2000, 311],
                                                              [1018, 2000, 300]], cen)
    members.append({"o": o, "u": u, "n": n, "poly": poly, "L": L, "z0": z0, "i": 2})
    joined = join_walls(members)
    assert sorted(sorted(g["members"]) for g in joined) == [[0, 1], [2]]
    g = next(g for g in joined if len(g["members"]) == 2)
    assert abs(g["L"] - 18) < 1e-6 and abs(g["z0"] - 300) < 1e-6 and abs(g["poly"].area - 18 * 11) < 0.05
    assert g["n"][1] < -0.99                                                  # still facing away from the building
    _, wins, _ = row(g["poly"], g["L"], eave_height(g["poly"], g["L"]), P)
    assert len(wins) == 3 and {x[1] for x in wins} == {P["church_sill_m"]}


# ---------------------------------------------------------------------------------------------- round two
def _joined(o, u, n, L, H, z0=300.0, gable=0.0, i=0):
    pts = [(0, 0), (L, 0), (L, H)] + ([(L / 2, H + gable)] if gable else []) + [(0, H)]
    return {"o": np.array(o, float), "u": np.array(u, float), "n": np.array(n, float), "poly": Polygon(pts), "L": float(L),
            "z0": z0, "members": [i]}


def _church(tower=True, door_on=None):
    """A nave 30 x 12 m along E, 10 m to the eave, with gables at both ends, and a tower 6 x 6 m, 26 m high, at its
    west end: the joined walls, the pieces' frames and records, and the footprint."""
    gs = [_joined((1000, 2000), (1, 0), (0, -1), 30, 10, i=0),                 # south
          _joined((1030, 2012), (-1, 0), (0, 1), 30, 10, i=1),                 # north
          _joined((1030, 2000), (0, 1), (1, 0), 12, 10, gable=5, i=2),         # east gable
          _joined((1000, 2012), (0, -1), (-1, 0), 12, 10, gable=5, i=3)]       # west gable
    fp = box(1000, 2000, 1030, 2012)
    if tower:
        gs += [_joined((994, 2009), (0, -1), (-1, 0), 6, 26, i=4),             # the tower's west face
               _joined((994, 2003), (1, 0), (0, -1), 6, 26, i=5),
               _joined((1000, 2009), (-1, 0), (0, 1), 6, 26, i=6)]
        fp = fp.union(box(994, 2003, 1000, 2009))
    walls = [dict(g) for g in gs]
    recs = [{"doors": [], "street": None} for _ in gs]
    if door_on is not None:
        recs[door_on]["doors"] = [[14.0, 0.0, 15.6, 2.3, "osm:node/7", "door"]]
    return gs, walls, recs, fp


def test_the_entrance_front_is_the_tower_end_and_gets_a_portal_and_the_tower_a_belfry():
    from v2.data.scene import church
    gs, walls, recs, fp = _church()
    out = church.plan(gs, walls, recs, fp, set(), P)
    assert out["front"]["how"] == "the tower end" and out["front"]["portal"] and abs(out["main_eave"] - 310) < 1e-6
    fronts = [g for g in gs if g["portal"]]
    assert fronts == [gs[4]]                                                  # one front: the outermost wall of that end
    p0 = gs[4]["portal"]
    assert p0[1] == 0 and abs((p0[0] + p0[2]) / 2 - 3.0) < 2e-3               # on the ground, in the middle
    assert [g["tower"] for g in gs] == [False] * 4 + [True] * 3
    for g in gs[4:]:
        bell = [x for x in g["windows"] if x[4] == "belfry"]
        assert len(bell) == 2 and len({(x[1], x[3]) for x in bell}) == 1      # a pair, on one line
        assert min(x[1] for x in bell) + 300 > out["main_eave"] and max(x[3] for x in bell) <= 26 - P["church_belfry_top_m"] + 1e-6
        assert all(x[3] < bell[0][1] for x in g["windows"] if x[4] != "belfry")          # the row stays under them
        assert g["buttresses"] == []                                          # never on a tower
    assert not any(x[4] == "belfry" for g in gs[:4] for x in g["windows"])    # belfry openings only on the tower
    # the long nave walls: a row of traceried windows with a buttress between each pair and a string course under the sills
    for g in gs[:2]:
        tall = sorted(x for x in g["windows"] if x[4] == "traceried")
        assert len(tall) >= 3 and len(g["buttresses"]) >= len(tall) - 1
        assert len({b[3] for b in g["buttresses"]}) == 1 and all(abs(b[2] - b[0] - P["church_buttress_w_m"]) < 2e-3 for b in g["buttresses"])
        for b in g["buttresses"]:
            assert all(b[2] + P["church_buttress_gap_m"] <= x[0] + 1e-6 or b[0] - P["church_buttress_gap_m"] >= x[2] - 1e-6 for x in tall)
        assert g["courses"] == [round(tall[0][1] - P["church_course_under_sill_m"], 3)]


def test_without_a_tower_the_front_is_told_from_the_main_entrance_or_the_apse_and_gets_a_rose():
    from v2.data.scene import church
    # an OSM main entrance on the south wall goes before everything else; the portal stands where the door was
    gs, walls, recs, fp = _church(tower=False, door_on=0)
    out = church.plan(gs, walls, recs, fp, {"node/7"}, P)
    assert out["front"]["how"] == "the OSM main entrance" and gs[0]["portal"] and recs[0]["doors"] == []
    assert gs[0]["portal_src"] == "osm:node/7"                                # the portal is that OSM door
    assert abs((gs[0]["portal"][0] + gs[0]["portal"][2]) / 2 - 14.8) < 2e-3
    assert sum(1 for g in gs if g["portal"]) == 1
    assert all(x[0] >= gs[0]["portal"][2] or x[2] <= gs[0]["portal"][0] for x in gs[0]["windows"] if x[4] != "rose")
    # no tower, no main entrance: the east end narrows to an apse, so the front is the west gable, with a rose over the portal
    gs, walls, recs, fp = _church(tower=False)
    apse = Polygon([(1030, 2000), (1036, 2004), (1036, 2008), (1030, 2012)])
    out = church.plan(gs, walls, recs, fp.union(apse), set(), P)
    assert out["front"]["how"] == "opposite the apse" and gs[3]["portal"] and out["front"]["rose"]
    rose = [x for x in gs[3]["windows"] if x[4] == "rose"]
    assert len(rose) == 1 and abs((rose[0][3] - rose[0][1]) - (rose[0][2] - rose[0][0])) < 2e-3
    assert rose[0][1] >= gs[3]["portal"][3] + P["church_rose_over_portal_m"] - 1e-6
    assert abs((rose[0][0] + rose[0][2]) - (gs[3]["portal"][0] + gs[3]["portal"][2])) < 4e-3      # on the portal's axis
    assert gs[3]["poly"].contains(box(*rose[0][:4]))


def test_a_church_wall_is_free_where_no_neighbour_covers_it_and_faces_out_of_the_footprint():
    from shapely import STRtree
    from shapely.geometry import LineString
    from v2.data.scene import church
    # a nave wall 30 m long and 18 m high; a house 12 m long and 8 m high stands against its middle
    nave = {"b": 0, "o": np.array([1000.0, 2000.0]), "u": np.array([1.0, 0.0]), "n": np.array([0.0, -1.0]),
            "poly": Polygon([(0, 0), (30, 0), (30, 18), (0, 18)]), "L": 30.0, "z0": 300.0}
    house = {"b": 1, "o": np.array([1021.0, 2000.0]), "u": np.array([-1.0, 0.0]), "n": np.array([0.0, 1.0]),
             "poly": Polygon([(0, 0), (12, 0), (12, 8), (0, 8)]), "L": 12.0, "z0": 300.0}
    segs = [LineString([(1000, 2000), (1030, 2000)]), LineString([(1021, 2000), (1009, 2000)])]
    cover = church.covered(0, [nave, house], segs, STRtree(segs), P["party_wall_tol_m"])
    assert abs(cover.area - 12 * 8) < 1e-6 and cover.bounds == (9.0, 0.0, 21.0, 8.0)
    free = church.free_parts(nave["poly"], cover, P["church_free_min_area_m2"])
    assert len(free) == 1 and abs(free[0].area - (30 * 18 - 12.6 * 8.3)) < 0.5        # all but the house, with a margin
    _, wins, _ = church.row(free[0], 30.0, 18.0, P)
    assert wins and all(not box(*x[:4]).intersects(box(9, 0, 21, 8)) for x in wins)
    # the outward side: out of the footprint, wherever the building's centre lies
    fp = box(1000, 2000, 1030, 2012).union(box(1000, 1900, 1010, 2000))      # an L: its centre lies south of this wall
    seg = LineString([(1012, 2000), (1030, 2000)])
    assert church.points_out(seg, np.array([0.0, -1.0]), fp, fp.centroid.coords[0])
    assert not church.points_out(seg, np.array([0.0, 1.0]), fp, fp.centroid.coords[0])
    # turning a wall round keeps its doors in place
    wall_ = dict(nave, base=[[1000, 2000, 300], [1030, 2000, 300]])
    rec = {"base": [[1000, 2000, 300], [1030, 2000, 300]], "normal": [0, -1], "outline": [[0, 0], [30, 0], [30, 18], [0, 18], [0, 0]],
           "doors": [[2.0, 0.0, 3.2, 2.3, "rule:street door", "door"]], "house_rule": {"windows": [], "doors": 1, "shopfronts": 0}}
    church.flip(wall_, rec)
    assert rec["doors"][0][:4] == [26.8, 0.0, 28.0, 2.3] and rec["normal"] == [0.0, 1.0] and rec["base"][0][:2] == [1030, 2000]
    assert rec["house_rule"]["outline"][1] == [30, 0]


def test_a_listed_exception_is_not_a_place_of_worship():
    from v2.data.scene import worship
    ex = worship.load_exceptions()
    assert {"relation/11371126"} <= {x["osm"] for x in ex} and all(x["reason"] and x["date"] and x["owner"] for x in ex)
    sq = [{"lat": 49.61, "lon": 6.13}, {"lat": 49.61, "lon": 6.1302}, {"lat": 49.6102, "lon": 6.1302}, {"lat": 49.6102, "lon": 6.13},
          {"lat": 49.61, "lon": 6.13}]
    el = {"type": "way", "id": 5, "tags": {"building": "church"}, "geometry": sq}
    assert len(worship.outlines({"elements": [el]})) == 1 and worship.outlines({"elements": [el]}, {"way/5"}) == []


def _worship_json(elements):
    return {"elements": elements}


def test_places_of_worship_come_from_the_data():
    from shapely.geometry import Polygon as Pg
    from v2.data.geo import en_to_lonlat
    from v2.data.scene import worship

    def way(i, ring, tags):
        lon, lat = en_to_lonlat(np.array([p[0] for p in ring]), np.array([p[1] for p in ring]))
        return {"type": "way", "id": i, "tags": tags, "geometry": [{"lon": float(a), "lat": float(b)} for a, b in zip(lon, lat)]}
    sq = lambda x, y, s: [(x, y), (x + s, y), (x + s, y + s), (x, y + s), (x, y)]          # noqa: E731
    blds = [{"id": f"B{i}"} for i in range(6)]
    fps = [Pg(sq(77000, 75000, 20)),        # 0: a church, mapped as building=church
           Pg(sq(77100, 75000, 60)),        # 1: a convent with a chapel in one corner of it
           Pg(sq(77300, 75000, 20)),        # 2: a house with a prayer room (a node, not fetched as an outline)
           Pg(sq(77400, 75000, 20)),        # 3: a church on the landmark list only
           Pg(sq(77500, 75000, 20)),        # 4: a church in landmark_styles.json only
           Pg(sq(77021, 75000, 20))]        # 5: the first church's neighbour, 1 m from it
    osm = _worship_json([way(1, sq(77000.5, 75000.5, 20), {"building": "church", "name": "Saint A"}),
                         way(2, sq(77100, 75000, 15), {"building": "chapel"}),
                         {"type": "relation", "id": 3, "tags": {"type": "site", "amenity": "place_of_worship"},
                          "members": [{"type": "way", "role": "", "geometry": way(0, sq(77300, 75000, 20), {})["geometry"]}]}])
    places = [{"source": "landmark", "category": "church", "slug": "c", "name": "C", "e": 77410.0, "n": 75010.0},
              {"source": "landmark", "category": "culture", "slug": "m", "name": "M", "e": 77310.0, "n": 75010.0}]
    styles = {"B4": {"name": "D", "kind": "place_of_worship"}, "B2": {"name": "house", "facade": "facade_white"}}
    found = worship.find(blds, fps, osm, places, styles, P)
    assert sorted(found) == [0, 1, 3, 4]
    assert found[0]["source"] == "osm:way/1" and found[0]["share"] > 0.9
    assert found[1]["source"] == "osm:way/2" and found[1]["share"] < 0.1          # the chapel is a small part of it
    assert found[3]["source"] == "landmark:c" and found[3]["area"] is None and found[4]["source"] == "landmark_styles"
    # only the walls standing in the mapped outline are the chapel's
    from shapely.geometry import LineString
    assert worship.wall_in(found[1]["area"], LineString([(77100, 75000), (77115, 75000)]), P["worship_wall_tol_m"])
    assert not worship.wall_in(found[1]["area"], LineString([(77130, 75060), (77160, 75060)]), P["worship_wall_tol_m"])
    assert worship.wall_in(None, LineString([(0, 0), (1, 0)]), P["worship_wall_tol_m"])
