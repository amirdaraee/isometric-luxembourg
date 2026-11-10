"""Tunnel view: the tubes from a tiny graph (a street, a tunnel through a hill, a passage), their geometry and the
casemate galleries, on synthetic inputs (no downloads)."""
import json
from types import SimpleNamespace

import numpy as np
from shapely.geometry import box

from v2.config import params
from v2.layers import tunnels as T
from v2.layers.common import project_local
from v2.layers.raster import raster_tris

P = params()["tunnels"]
O = (70000.0, 65000.0)


def edge(i, a, b, x0, x1, structure, n0=75000.0, z=280.0, **kw):
    xs = np.arange(x0, x1 + 1e-9, 2.0)
    e = {"id": f"e{i}", "a": a, "b": b, "mode": "road", "structure": structure, "width": 6.0, "clearance_m": 4.5,
         "en": [[float(x), n0] for x in xs], "s": [float(x - x0) for x in xs], "z": [z] * len(xs),
         "ground": [z] * len(xs)}
    e.update(kw)
    return e


def graph():
    """West to east: a street (77000-77100), a tunnel in two edges (77100-77200) under 20 m of hill, a street."""
    hill = lambda xs: [280.0 + min(x - 77100, 77200 - x, 20.0) for x in xs]          # noqa: E731
    t1 = edge(1, 2, 3, 77100, 77150, "tunnel", chain="c1")
    t2 = edge(2, 3, 4, 77150, 77200, "tunnel", chain="c1")
    for t in (t1, t2):
        xs = [p[0] for p in t["en"]]
        t["cover"] = hill(xs)
        t["tunnel_d"] = [min(x - 77100, 77200 - x) for x in xs]
    return {"nodes": [], "portals": [{"chain": "c1", "found": True, "dist_m": 6.0}, {"chain": "c1", "found": True, "dist_m": 4.0}],
            "edges": [edge(0, 1, 2, 77000, 77100, "ground"), t1, t2, edge(3, 4, 5, 77200, 77300, "ground"),
                      edge(4, 6, 7, 77000, 77040, "passage", n0=75100.0, mode="path", width=2.0, clearance_m=2.5),
                      edge(5, 8, 9, 77000, 77040, "passage", n0=75200.0, mode="path", width=2.0, clearance_m=2.5,
                           ground=[283.0] * 21)]}


def records():
    return T.tube_records(graph(), box(76900, 74900, 77400, 75300), P, 40.0, O)


def test_tubes_are_the_tunnel_edges_and_the_passages_that_run_underground():
    r = records()
    assert [t["id"] for t in r] == ["e1", "e2", "e5"]        # the passage at street level is not a tunnel
    assert [t["edge"] for t in r] == [1, 2, 5]
    t1, t2, p = r
    assert t1["ends"] == [T.PORTAL, T.OPEN] and t2["ends"] == [T.OPEN, T.PORTAL] and p["ends"] == [T.CLOSED, T.CLOSED]
    assert (t1["w"], t1["h"], t1["portal_m"]) == (6.0, 4.5, 6.0)          # the chain's portal: the farther one found
    assert t1["c"][0] == 0.0 and max(t1["c"]) == 20.0 and t2["c"][5] == 20.0      # cover minus the profile
    assert t1["d"][5] == 10.0 and t2["d"][-1] == 0.0
    assert p["c"] == [3.0] * 21 and p["portal_m"] == 40.0
    assert t1["p"][:2] == [7100.0, 10000.0]                   # relative to the camera origin
    assert t1["nodes"] == [2, 3] and t2["nodes"] == [3, 4]
    # outside the area: nothing
    assert T.tube_records(graph(), box(0, 0, 10, 10), P, 40.0, O) == []


def test_a_tube_has_its_width_and_ends_at_the_portal_face():
    t1, t2, _ = records()
    f = T.tube_frame(t1, P["portal_face_m"])
    assert np.isclose(f["P"][0, 0], 7100.0 - P["portal_face_m"]) and np.isclose(f["P"][-1, 0], 7150.0)
    assert np.allclose(np.linalg.norm(f["A"] - f["B"], axis=1), 6.0)
    assert np.allclose(f["A"][:, 1], 10003.0)                 # the left of a way heading east is north
    assert np.isclose(T.tube_frame(t2, P["portal_face_m"])["P"][-1, 0], 7200.0 + P["portal_face_m"])


def test_the_portal_face_is_where_layer_4_draws_it():
    """The tubes end at `portal_face_m` out of the tunnel's end node: the offset of geometry.portal_mesh."""
    from v2.layers.geometry import portal_mesh
    g = graph()
    g["edges"] = g["edges"][:4]
    for e, d in ((g["edges"][1], -1), (g["edges"][2], 1)):          # turn the tunnel so that one mouth faces the camera
        e["en"] = [[77150.0 + d * (x - 77150.0) * 0.0, 75000.0 - (x - 77150.0)] for x, _ in e["en"]]
    M = portal_mesh(SimpleNamespace(graph=g))
    assert len(M["V"]) > 0
    south_end = np.array([77150.0, 74950.0])
    out = np.array([0.0, -1.0])                                # pointing out of the tunnel, towards the camera
    assert np.allclose((M["V"][:, :2] - south_end) @ out, P["portal_face_m"])


def test_a_corner_is_mitred():
    rec = {"p": [0, 0, 10, 0, 10, 10], "z": [0, 0, 0], "c": [5, 5, 5], "w": 6.0, "h": 3.0, "ends": [0, 0]}
    f = T.tube_frame(rec, 0.3)
    assert np.allclose(f["A"][1], [7, 3]) and np.allclose(f["B"][1], [13, -3])


def test_the_mesh_is_the_floor_and_the_far_wall_and_never_hides_what_is_in_the_tube():
    t1 = records()[0]
    V, tri, kind = T.tube_mesh(t1, P["portal_face_m"])
    seg = len(t1["z"])                                        # 26 points + the portal's = 26 segments
    assert (kind == T.FLOOR).sum() == 4 * seg and (kind == T.WALL).sum() == 2 * seg and (kind == T.CAP).sum() == 0
    wall = V[np.unique(tri[kind == T.WALL])]
    assert np.allclose(wall[:, 1], 10003.0)                   # the north wall: the camera looks north-west
    assert np.isclose(wall[:, 2].max(), 284.5) and np.isclose(V[:, 2].min(), 280.0)
    # a closed end is drawn only when its inside faces the camera
    closed = dict(t1, ends=[T.CLOSED, T.CLOSED])
    assert (T.tube_mesh(closed, 0.3)[2] == T.CAP).sum() == 2
    # every point inside the tube is nearer than the drawn faces behind it (the view ray of a point by the west
    # mouth leaves through the mouth: there nothing is behind it)
    px, py, d = project_local(V[:, 0], V[:, 1], V[:, 2])
    x0, y0 = np.floor(px.min()), np.floor(py.min())
    W, H = int(px.max() - x0) + 2, int(py.max() - y0) + 2
    zb, tb = np.full((H, W), np.inf), np.full((H, W), -1, np.int64)
    raster_tris(np.column_stack([px - x0, py - y0]), d, tri, W, H, zb, tb)
    rng = np.random.default_rng(0)
    q = np.column_stack([rng.uniform(7110, 7149, 400), rng.uniform(10000 - 2.9, 10000 + 2.9, 400), rng.uniform(280.3, 284.4, 400)])     # a pixel's centre
    # can be 0.2 m of view depth from the point, hence not from the floor itself
    qx, qy, qd = project_local(q[:, 0], q[:, 1], q[:, 2])
    behind = zb[(qy - y0).astype(int), (qx - x0).astype(int)]
    assert np.isfinite(behind).all() and (qd < behind).all()


def test_a_junction_is_open():
    """Where tubes join at a node, a wall is left out as far as it runs inside another of them."""
    t1, t2, _ = records()
    J = P["junction"]
    assert T.wall_trims([t1, t2], P["portal_face_m"], J) == [[[0.0, 0.0], [0.0, 0.0]]] * 2      # straight on: whole walls
    branch = dict(t1, id="b", w=4.0, p=[7150.0, 10000.0, 7150.0, 10002.0, 7150.0, 10030.0], z=[280.0] * 3, c=[9.0] * 3,
                  s=[0.0, 2.0, 30.0], d=[0.0, 2.0, 30.0], nodes=[3, 9], ends=[T.OPEN, T.CLOSED])
    tr = T.wall_trims([t1, t2, branch], P["portal_face_m"], J)
    assert all(2.75 <= v <= 3.0 for v in tr[2][0]) and tr[2][1] == [0.0, 0.0]       # the branch leaves the tunnel (3 m)
    assert 1.75 <= tr[0][1][0] <= 2.0 and 1.75 <= tr[1][0][0] <= 2.0                # the north wall opens for it (2 m)
    assert tr[0][1][1] == 0.0 and tr[1][0][1] == 0.0 and tr[0][0] == [0.0, 0.0]     # the south wall is whole
    V, tri, kind = T.tube_mesh(t1, P["portal_face_m"], tr[0])
    wall = V[np.unique(tri[kind == T.WALL])]
    assert np.isclose(wall[:, 0].max(), 7150.0 - tr[0][1][0]) and np.isclose(wall[:, 0].min(), 7100.0 - P["portal_face_m"])
    assert np.isclose(V[np.unique(tri[kind == T.FLOOR])][:, 0].max(), 7150.0)       # the floor is whole


def test_prisms_and_the_depth_range_hold_every_tube():
    r = records()
    pr = T.tube_prisms(r[0], P["portal_face_m"])
    assert pr.shape == (len(r[0]["z"]), 8, 3) and np.isclose(pr[:, 4:, 2].max(), 284.5)
    lo, hi = T.depth_range_cm(r, P["portal_face_m"])
    for t in r:
        V = T.tube_mesh(t, P["portal_face_m"])[0]
        d = project_local(V[:, 0], V[:, 1], V[:, 2])[2] * 100
        assert lo < d.min() and d.max() < hi


def test_casemate_galleries_are_tubes_under_the_terrain():
    doc = {"id": "bock", "galleries": [
        {"id": "main", "width_m": 4.0, "height_m": 3.5, "z": 270.0, "ends": ["closed", "closed"], "en": [[77000, 75000], [77011, 75000]]},
        {"id": "b1", "width_m": 2.5, "height_m": 2.5, "z": [270.0, 271.0], "ends": ["open", "closed"], "en": [[77005, 75002], [77005, 75007]]}]}
    terrain = lambda e, n: 276.0 + 0 * np.asarray(e) - 0.5 * np.maximum(np.asarray(n) - 75004.0, 0)        # noqa: E731
    r = T.casemate_records(doc, terrain, 2.0, None, O)
    main, b1 = r
    assert main["id"] == "casemate/main" and main["kind"] == "casemate" and main["edge"] == -1
    assert len(main["z"]) == 7 and np.diff(main["s"]).max() <= 2.0 + 1e-9 and main["s"][-1] == 11.0
    assert main["c"] == [6.0] * 7 and main["ends"] == [T.CLOSED, T.CLOSED] and b1["ends"] == [T.OPEN, T.CLOSED]
    assert b1["z"] == [270.0, 270.33, 270.67, 271.0]
    # the least rock over the top, over the gallery's whole width
    assert np.isclose(T.rock_over(doc["galleries"][0], terrain), 2.5)
    assert np.isclose(T.rock_over(doc["galleries"][1], terrain), 276.0 - 1.5 - (271.0 + 2.5))


def test_the_casemates_file_reads_and_has_its_parts():
    doc = json.loads(T.CASEMATES.read_text())
    assert "approximate" in doc["about"] and "not a survey" in doc["about"]
    ids = [g["id"] for g in doc["galleries"]]
    assert len(ids) == len(set(ids)) == 26 and ids[0] == "main"
    main = doc["galleries"][0]
    assert np.isclose(np.linalg.norm(np.subtract(*main["en"])), 110.0, atol=0.05)
    for g in doc["galleries"]:
        assert g["width_m"] > 0 and g["height_m"] > 0 and len(g["en"]) >= 2 and len(g["ends"]) == 2
