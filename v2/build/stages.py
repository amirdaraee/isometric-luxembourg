"""The stages of the v2 build graph, in dependency order. Specs: v2/docs/specs/ (scene, transport graph, checks).

Raw inputs v1 already downloaded (data/raw) are fingerprinted, so a new download rebuilds what depends on it.
"""
from __future__ import annotations

from v2.build.graph import Graph, Stage
from v2.config import params, raw_dir, v1_work, REPO
from v2.data.fetch import stages as fetch

GEO = ("v2.data.geo", "v2.config")
CAM = ("v2.config.camera",)


def _p(*keys):
    """Params from params.json sections (the stage key changes when they change)."""
    def f(area):
        out = {}
        for k in keys:
            out[k] = params()[k]
        return out
    return f


def _with(base, *keys):
    def f(area):
        d = base(area) if callable(base) else dict(base)
        for k in keys:
            d[k] = params()[k]
        return d
    return f


def graph() -> Graph:
    from v2.data.scene import buildings, facades, places, structures, terrain, transit, transport, trees, water, scene
    from v2.checks import data_checks as dc, repo_checks as rc
    from v2.build import report

    S = []
    # ---------------------------------------------------------------- fetches (shared by every area)
    S += [
        Stage("fetch_osm_transport", fetch.fetch_osm_transport, params=fetch.extent_params, code=GEO + ("v2.data.fetch.overpass", "v2.data.fetch.http"),
              kind="fetch", shared=True, doc="OSM roads, paths, rail, tram, bridges, tunnels (Overpass)"),
        Stage("fetch_osm_ground", fetch.fetch_osm_ground, params=fetch.extent_params, code=GEO + ("v2.data.fetch.overpass", "v2.data.fetch.http"),
              kind="fetch", shared=True, doc="OSM land use, water, walls, cliffs, squares, lamps (Overpass)"),
        Stage("fetch_trees", fetch.fetch_trees, params=fetch.trees_params, code=GEO + ("v2.data.fetch.gpkg_stream", "v2.data.fetch.http"),
              kind="fetch", shared=True, doc="ACT LiDAR 2024 tree survey, streamed and cut to the commune"),
        Stage("fetch_lidar", fetch.fetch_lidar, params=fetch.lidar_params, code=GEO + ("v2.data.fetch.cog", "v2.data.fetch.http"),
              kind="fetch", doc="ACT LiDAR 2024 MNT and MNS over the area (COG windows)"),
    ]
    # ---------------------------------------------------------------- the scene
    bati = lambda area: [raw_dir() / "bati3d" / "act2023v2-bati3d-luxembourg.zip"]  # noqa: E731
    S += [
        Stage("scene_terrain", terrain.build, deps=("fetch_lidar", "fetch_osm_ground"), params=_p("terrain"), code=GEO,
              doc="terrain and surface grids, slope, cliffs and walls"),
        Stage("scene_water", water.build, deps=("fetch_osm_ground",), code=GEO, doc="water polygons and river lines"),
        Stage("scene_buildings", buildings.build, deps=("scene_terrain",), params=_p("buildings"), raw=bati, code=GEO,
              doc="ACT LoD2 buildings: id, roof shape, heights, footprint, walls, mesh"),
        Stage("scene_facades", facades.build, deps=("scene_buildings",), params=_p("facades"), code=GEO,
              doc="facade layout per wall: floors and window grid"),
        Stage("scene_trees", trees.build, deps=("fetch_trees", "scene_buildings", "scene_water", "scene_terrain"),
              params=_p("trees"), code=GEO, doc="LiDAR trees, thinned over water and buildings"),
        Stage("scene_places", places.build, deps=("scene_terrain",), code=GEO + CAM,
              raw=lambda area: [REPO / "web/public/data/landmarks.json", REPO / "web/public/data/places.json",
                                v1_work() / "terrain.npz"],
              doc="v1's landmarks and places, back in LUREF metres"),
        Stage("scene_transport", transport.build, deps=("fetch_osm_transport", "scene_terrain", "scene_buildings"),
              params=_p("transport"), code=GEO + ("v2.data.scene.profile",),
              doc="roads, rail and tram graph with height profiles, bridges and tunnels"),
        Stage("scene_structures", structures.build, deps=("scene_transport", "scene_terrain", "fetch_osm_transport"),
              raw=lambda area: [REPO / "v2/data/structures/viaducts.json"], code=GEO,
              doc="the modelled viaducts (piers, arches, deck) as data"),
        Stage("scene_transit", transit.build, deps=("scene_transport",), params=_p("transit"),
              raw=lambda area: [raw_dir() / params()["transit"]["gtfs_dir"]], code=GEO,
              doc="GTFS trams and trains matched onto the rail graph"),
        Stage("scene", scene.build, deps=("scene_terrain", "scene_water", "scene_buildings", "scene_facades", "scene_trees",
                                          "scene_places", "scene_transport", "scene_structures", "scene_transit"),
              code=GEO + CAM, doc="the scene index: every part, its files, counts and extent"),
    ]
    # ---------------------------------------------------------------- checks (gates)
    chk = dict(kind="check", params=_p("checks"), code=GEO + ("v2.checks.framework",))
    S += [
        Stage("check_scope", dc.check_scope, deps=("scene",), **chk, doc="every part of the scene lies within the area"),
        Stage("check_terrain", dc.check_terrain, deps=("scene_terrain", "scene_buildings"), **chk, doc="terrain complete; buildings sit on it"),
        Stage("check_buildings", dc.check_buildings, deps=("scene_buildings",), **chk, doc="closed, valid, non-overlapping footprints"),
        Stage("check_facades", dc.check_facades, deps=("scene_facades", "scene_buildings"), **chk, doc="facade layout sanity"),
        Stage("check_trees", dc.check_trees, deps=("scene_trees", "scene_buildings", "scene_water"), **chk, doc="no trees inside buildings or water"),
        Stage("check_transport_profiles", dc.check_transport_profiles, deps=("scene_transport", "scene_terrain"), **chk,
              doc="continuous height profiles; tunnels below, decks above; portals"),
        Stage("check_transport_graph", dc.check_transport_graph, deps=("scene_transport",), **chk, doc="joined at junctions, connected"),
        Stage("check_structures", dc.check_structures, deps=("scene_structures", "scene_transport", "scene_terrain"), **chk,
              doc="viaducts: piers reach the ground, deck on the graph"),
        Stage("check_transit", dc.check_transit, deps=("scene_transit",), **chk, doc="trams and trains matched to rails"),
        Stage("check_places", dc.check_places, deps=("scene_places",), **chk, doc="places round-trip to v1 pixels"),
        Stage("check_no_patching", rc.check_no_patching, kind="check", params=_p("checks"), code=("v2.checks.framework", "v2.build.stages"),
              raw=lambda area: sorted((REPO / "v2").rglob("*.py")), doc="brief 1: no stage edits finished art (grep gate)"),
        Stage("check_ledger", rc.check_ledger, kind="check", code=("v2.ledger.ledger",),
              raw=lambda area: [REPO / "v2/ledger/budget.json", REPO / "v2/ledger/spend.jsonl"], doc="spend ledger valid, within caps"),
    ]
    checks = tuple(s.name for s in S if s.kind == "check")
    S += [
        Stage("previews", report.previews, deps=("scene",), code=GEO + CAM, kind="report", doc="preview images of the scene"),
        Stage("g0", report.g0, deps=checks + ("previews", "scene"), kind="report", doc="gate G0: all data checks, sizes, previews"),
    ]
    return Graph(S)
