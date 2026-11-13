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
def test_a_church_wall_gets_few_tall_windows_in_one_straight_row():
    from v2.data.scene.facades import church_layout
    poly = Polygon([(0, 0), (20, 0), (20, 12), (0, 12)])
    bays, wins = church_layout(poly, 20.0, 12.0, P)
    assert bays == int((20 - 2 * P["edge_margin_m"]) // P["church_bay_m"]) and len(wins) == bays
    _, _, house = layout(poly, 20.0, 12.0, P)
    assert len(wins) < len(house) / 4                     # few
    assert {(w[1], w[3]) for w in wins} == {(P["church_sill_m"], 12 - P["church_top_m"])}    # one sill line, one top line
    for w in wins:
        assert abs(w[2] - w[0] - P["church_window_w_m"]) < 2e-3 and w[3] - w[1] > 3 * P["window_h_m"]     # tall
        assert poly.buffer(-P["inset_m"] + 1e-6).contains(box(*w))
    # a very tall wall (a tower): the window stops at its greatest height
    _, wins = church_layout(Polygon([(0, 0), (6, 0), (6, 40), (0, 40)]), 6.0, 40.0, P)
    assert [round(w[3] - w[1], 3) for w in wins] == [P["church_window_max_h_m"]]


def test_a_buttressed_church_wall_gets_one_window_between_each_pair_of_buttresses():
    from v2.data.scene.facades import church_layout, clear_spans
    # a nave wall 30 m long and 14 m to the eave; four buttresses 1 m wide stand in front of it up to 12 m
    notches = [box(u, -1, u + 1.0, 12.0) for u in (5.0, 11.5, 18.0, 24.5)]
    poly = Polygon([(0, 0), (30, 0), (30, 14), (0, 14)])
    for n in notches:
        poly = poly.difference(n)
    spans = clear_spans(poly, 30.0, 2.4, 13.2, P["inset_m"])
    assert [(round(a, 1), round(b, 1)) for a, b in spans] == [(0.0, 4.8), (6.2, 11.3), (12.7, 17.8), (19.2, 24.3), (25.7, 30.0)]
    bays, wins = church_layout(poly, 30.0, 14.0, P)
    assert bays == len(wins) == 5
    assert {(w[1], w[3]) for w in wins} == {(P["church_sill_m"], P["church_sill_m"] + P["church_window_max_h_m"])}
    for w, (a, b) in zip(wins, spans):
        assert a < w[0] and w[2] < b and poly.buffer(-P["inset_m"] + 1e-6).contains(box(*w))


def test_a_low_chapel_wall_takes_the_house_sill_and_a_wall_too_low_gets_no_window():
    from v2.data.scene.facades import church_layout
    _, wins = church_layout(Polygon([(0, 0), (6, 0), (6, 4.5), (0, 4.5)]), 6.0, 4.5, P)
    assert [w[1] for w in wins] == [P["sill_m"]] and wins[0][3] - wins[0][1] >= P["church_window_min_h_m"]
    assert church_layout(Polygon([(0, 0), (6, 0), (6, 3.0), (0, 3.0)]), 6.0, 3.0, P)[1] == []


def test_a_church_wall_standing_on_a_lower_roof_starts_its_windows_there():
    from v2.data.scene.facades import church_layout
    # the wall's lowest point is the ground at one end; under its bays it stands on an aisle roof 6 m up
    poly = Polygon([(0, 0), (0.5, 0), (0.5, 6), (12, 6), (12, 16), (0, 16)])
    _, wins = church_layout(poly, 12.0, 16.0, P)
    assert wins and {w[1] for w in wins} == {6 + P["church_sill_m"]}


def test_a_churchs_wall_given_in_triangles_is_joined_into_one_wall():
    from v2.data.scene.facades import church_layout, join_walls
    cen = np.array([1010.0, 2010.0])
    tris = [[(0, 0, 0), (18, 0, 0), (18, 0, 11), (0, 0, 0)], [(0, 0, 0), (18, 0, 11), (0, 0, 11), (0, 0, 0)]]
    members = []
    for i, t in enumerate(tris):
        o, u, n, poly, L, z0, flat = wall_frame([[x + 1000, y + 2000, z + 300] for x, y, z in t], cen)
        alone = church_layout(poly, L, eave_height(poly, L), P)[1]            # a triangle holds no full-height window
        assert all(w[3] - w[1] < 11 - P["church_top_m"] - P["church_sill_m"] - 1 for w in alone)
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
    _, wins = church_layout(g["poly"], g["L"], eave_height(g["poly"], g["L"]), P)
    assert len(wins) == 3 and {w[1] for w in wins} == {P["church_sill_m"]}


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
