"""The transport graph on a synthetic valley: junctions, a bridge deck over it, a tunnel through a hill."""
import numpy as np

from v2.config import params
from v2.data.geo import en_to_lonlat
from v2.data.scene.grid import Grid
from v2.data.scene.transport import solve_graph, structure, ways_to_edges

P = params()["transport"]
C = params()["checks"]
E0, N0 = 77000.0, 75000.0


def way(wid, nodes, en, **tags):
    lon, lat = en_to_lonlat(np.array([p[0] for p in en]), np.array([p[1] for p in en]))
    return {"type": "way", "id": wid, "nodes": nodes, "tags": tags,
            "geometry": [{"lon": float(a), "lat": float(b)} for a, b in zip(lon, lat)]}


def grids():
    e = E0 + (np.arange(800) + 0.5); n = N0 + (np.arange(400) + 0.5)
    E, N = np.meshgrid(e - E0, n - N0)
    mnt = np.full(E.shape, 300.0)
    mnt[(E > 200) & (E < 400)] = 270.0                         # a 30 m deep valley, 200 m wide
    mnt[(E > 500) & (E < 700)] = 330.0                         # a 30 m high hill
    mns = mnt.copy()
    mns[(E > 200) & (E < 400) & (np.abs(N - 200) < 6)] = 300.0  # the deck over the valley
    return Grid(mnt.astype(np.float32), E0, N0, 1.0), Grid(mns.astype(np.float32), E0, N0, 1.0)


def network():
    y = N0 + 200
    pts = lambda xs: [(E0 + x, y) for x in xs]  # noqa: E731
    return [
        way(1, [1, 2], pts([50, 190]), highway="primary"),
        way(2, [2, 3], pts([190, 410]), highway="primary", bridge="viaduct", layer="1"),
        way(3, [3, 4], pts([410, 480]), highway="primary"),
        way(4, [4, 5], pts([480, 720]), highway="primary", tunnel="yes", layer="-1"),
        way(5, [5, 6], pts([720, 780]), highway="primary"),
        way(6, [4, 7], [(E0 + 480, y), (E0 + 480, y + 100)], highway="residential"),   # a junction at node 4
    ]


def solved():
    mnt, mns = grids()
    edges, boundary = ways_to_edges(network(), mnt, __import__("shapely").geometry.box(E0, N0, E0 + 800, N0 + 400), P)
    for ed in edges:
        ed["structure"] = structure(ed["el"]["tags"], P)
        ed["L"] = float(np.hypot(*np.diff(ed["en"], axis=0).T).sum())
    return solve_graph(edges, boundary, mnt, mns, P, C)


def test_split_at_junctions():
    nodes, edges, portals, unsolved = solved()
    assert len(edges) == 6
    deg = {n["id"]: n["deg"] for n in nodes}
    assert deg[4] == 3 and deg[2] == 2 and deg[1] == 1


def test_bridge_follows_the_deck_and_joins_its_approaches():
    nodes, edges, _, unsolved = solved()
    br = next(e for e in edges if e["structure"] == "bridge")
    z = np.array(br["z"])
    assert np.all(np.abs(z - 300.0) <= 0.31)                   # on the deck (kept 0.3 m over the ground at its ends), not in the valley (270)
    N = {n["id"]: n["z"] for n in nodes}
    for e in edges:
        assert abs(e["z"][0] - N[e["a"]]) < 1e-6 and abs(e["z"][-1] - N[e["b"]]) < 1e-6
    assert unsolved == 0


def test_tunnel_stays_under_the_hill_with_portals():
    nodes, edges, portals, _ = solved()
    tu = next(e for e in edges if e["structure"] == "tunnel")
    z, cov, d = np.array(tu["z"]), np.array(tu["cover"]), np.array(tu["tunnel_d"])
    need = P["clearance_m"]["road"] + C["tunnel_min_cover_m"]
    interior = (d >= C["portal_max_from_end_m"]) & (cov > 320)
    assert np.all(cov[interior] - z[interior] >= need - 0.05)
    assert np.all(np.abs(np.diff(z)) <= P["max_grade"]["road"] * 2.0 + 1e-6)
    assert len(portals) == 2 and all(p["found"] for p in portals)
    assert all(p["dist_m"] <= 40 for p in portals)
