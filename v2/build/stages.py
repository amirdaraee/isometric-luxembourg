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
    from v2.data.scene import buildings, entrances, facades, places, structures, terrain, transit, transport, trees, water, scene
    from v2.data.fetch import worship as fetch_worship
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
        Stage("fetch_osm_pois", entrances.fetch_osm_pois, params=fetch.extent_params,
              code=GEO + ("v2.data.fetch.overpass", "v2.data.fetch.http"), kind="fetch", shared=True,
              doc="OSM entrances, shops, crafts and amenities (Overpass)"),
        Stage("fetch_osm_worship", fetch_worship.fetch_osm_worship, params=fetch.extent_params,
              code=GEO + ("v2.data.fetch.overpass", "v2.data.fetch.http"), kind="fetch", shared=True,
              doc="OSM places of worship with their outlines (Overpass)"),
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
        Stage("scene_facades", facades.build, deps=("scene_buildings", "scene_transport", "fetch_osm_pois", "fetch_osm_worship",
                                                     "scene_places"), params=_p("facades"),
              code=GEO + ("v2.data.scene.entrances", "v2.data.scene.worship"),
              raw=lambda area: [REPO / "v2/data/structures/landmark_styles.json"],
              doc="facade layout per wall: floors, windows, doors and shop fronts; the church rule on places of worship"),
        Stage("scene_trees", trees.build, deps=("fetch_trees", "scene_buildings", "scene_water", "scene_terrain"),
              params=_p("trees"), code=GEO, doc="LiDAR trees, thinned over water and buildings"),
        Stage("scene_places", places.build, deps=("scene_terrain",), code=GEO + CAM,
              raw=lambda area: [REPO / "web/public/data/landmarks.json", REPO / "web/public/data/places.json",
                                v1_work() / "terrain.npz"],
              doc="v1's landmarks and places, back in LUREF metres"),
        Stage("scene_transport", transport.build, deps=("fetch_osm_transport", "scene_terrain", "scene_buildings", "fetch_trees"),
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
    chk = dict(kind="check", params=_p("checks"), code=GEO + ("v2.checks.framework",),
               raw=lambda area: [REPO / "v2/data/exceptions.json"])
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
    S += phase1(checks)
    S += phase3_cutaways()
    S += phase3()
    from v2.build import report3
    S.append(Stage("g3", report3.g3, deps=("g1", "check_tunnel_view", "check_cutaways", "check_cutaways_view"), code=("v2.build.report3",),
                   params=_art, kind="report", doc="gate G3 so far: gate G1's suite again, the tunnel view and the cutaways"))
    return Graph(S)


LAYER_CODE = GEO + CAM + ("v2.layers.common", "v2.layers.raster", "v2.layers.geometry", "v2.layers.render", "v2.layers.detail",
                          "v2.layers.tiles", "v2.layers.light", "v2.layers.data", "v2.data.scene.facades",
                          "v2.layers.art_a", "v2.layers.bakeoff", "v2.config.art")


def _art(area):
    """The art method (PLAN_V2 section 7) is part of every stage that draws or reads layers 5-7, so each bake-off
    option builds into its own folders (V2_ART=b python -m v2.build test release)."""
    from v2.config.art import art_method
    return {"art": art_method()}


def _layer_raw(area):
    from v2.config import CONFIG
    return [CONFIG / "palette.json", CONFIG / "light.json", CONFIG / "camera.json"]


def _art_raw(area):
    """As _layer_raw, for the stages that draw or read layers 5-7. For bake-off methods B and C that adds the
    paintings (and the composer that reads them), so a new painting or pick makes a new build of that method's own
    stages only; layers 1-4 are shared by every method."""
    from v2.config import v2_data
    from v2.config.art import art_method
    out = _layer_raw(area) + [REPO / "v2/data/structures/landmark_styles.json"]
    art = art_method()
    if art in ("b", "c"):
        d = v2_data() / area / "bakeoff" / art
        out += [REPO / "v2/bakeoff/compose.py"] + [p for p in (d / "painted.json", d / "picked.json", d / "painted") if p.exists()]
    return out


def phase1(g0_checks) -> list:
    """Phase 1 (PLAN_V2 section 10): the code layers on the test area, the viewer's data and the gate G1 checks."""
    from v2.layers import stages as L
    from v2.checks import layer_checks as lc, g1_checks as gc, line_checks as lic
    from v2.build import report1
    base = ("scene", "fetch_osm_ground", "fetch_osm_transport")
    lay = dict(code=LAYER_CODE, raw=_layer_raw)
    art = dict(lay, params=_art, raw=_art_raw)
    S = [Stage(f"layer_{n}", L.colour_layer(n), deps=base, doc=f"layer {i + 1}: {n}" + (" (by the art method)" if i >= 4 else ""),
               **(art if i >= 4 else lay))
         for i, n in enumerate(L.COLOUR_LAYERS)]
    S += [
        Stage("layer_buffers", L.layer_buffers, deps=base, doc="layer 8: depth, normal, height, ids of the nearest surface", **art),
        Stage("layer_light", L.layer_light, deps=base, doc="layer 9: the shadow height map", **art),
        Stage("layer_night", L.layer_night, deps=base, doc="layer 10: windows, doors, shop fronts, street lamps", **art),
        Stage("layer_vehicles", L.layer_vehicles, deps=("scene",), params=_p("transit"), code=LAYER_CODE,
              raw=lambda area: _layer_raw(area) + [raw_dir() / params()["transit"]["gtfs_dir"]],
              doc="layer 12: roads and profiles for the simulation; trams and trains on the graph"),
        Stage("layer_labels", L.layer_labels, deps=base, doc="layer 15: labels and pins", **art),
        Stage("layer_far", L.layer_far, deps=tuple(f"layer_{n}" for n in L.COLOUR_LAYERS), code=LAYER_CODE,
              doc="far zoom: the colour layers merged by depth, from zoom 2 out"),
    ]
    layers = tuple(s.name for s in S)
    S.append(Stage("release", L.release, deps=("scene",) + layers + ("layer_tunnels", "layer_cutaways"), code=LAYER_CODE, raw=_layer_raw,
                   doc="the viewer's folder: every layer behind one index.json"))
    web = lambda area: sorted(p for p in (REPO / "v2/web/src").rglob("*.ts")) + [REPO / "v2/web/index.html"]  # noqa: E731
    chk = dict(kind="check", params=_with(_art, "checks", "g1"), code=LAYER_CODE + ("v2.checks.framework", "v2.checks.layer_checks",
                                                                            "v2.checks.g1_checks", "v2.checks.line_checks"),
               raw=lambda area: _layer_raw(area) + [REPO / "v2/data/exceptions.json"])
    S += [
        Stage("check_layers", lc.check_layers, deps=("release",) + base, **chk,
              doc="layers 1-4 and 8: coverage, no shading, relief and walls, water, centre lines, alignment, palette"),
        Stage("check_independence", gc.check_independence, deps=("release",) + base, **chk,
              doc="brief 4: every layer re-rendered without each other layer's inputs is identical"),
        Stage("check_shadows", gc.check_shadows, deps=("release",) + base, **chk,
              doc="brief 5: no baked shadows in the colour layers; cast shadows follow the sun"),
        Stage("check_seams", gc.check_seams, deps=("release",) + base, **chk, doc="no edge or tone step at tile borders"),
        Stage("check_vehicles", gc.check_vehicles, deps=("release",) + base, **{**chk, "raw": lambda area: chk["raw"](area) + web(area)},
              doc="briefs 7 and 8: vehicles on drawn road; hidden in tunnels, under decks and trees; smooth heights"),
        Stage("check_lines", lic.check_lines, deps=("release", "scene"), **chk,
              doc="brief 6: the line score of layer 5, building edges and window rows within 1 px of the 3D model's"),
        Stage("check_no_cars", gc.check_no_cars, deps=("release",), **chk,
              doc="brief 9: the vehicle detector finds no car in any colour layer"),
        Stage("check_viewer", gc.check_viewer, deps=("release",) + base, **{**chk, "raw": lambda area: chk["raw"](area) + web(area)},
              doc="the viewer: layers off leave no trace, shadows move with ?hour, speed"),
    ]
    g1c = tuple(s.name for s in S if s.kind == "check")
    S.append(Stage("g1", report1.g1, deps=g1c + g0_checks + ("release",), code=("v2.build.report1", "v2.config.art"),
                   params=_art, kind="report",
                   doc="gate G1: every phase 1 check, speed, previews"))
    return S


def phase3_cutaways() -> list:
    """Phase 3, the landmark cutaways (PLAN_V2 section 9.1, specs/landmark-cutaways.md): the cut models as a small
    layer of its own above layer 5, with a code placeholder interior and the inputs of the later painting, and their
    checks K0-K6. Nothing here is painted or paid for."""
    from v2.layers import cutaways as cw
    from v2.checks import cutaway_checks as cc, cutaway_view_checks as cv

    def check_params(area):
        g1 = params()["g1"]
        return dict(cw.stage_params(area), g1={k: g1[k] for k in ("shadow_photo_sun", "detector_queries", "detector_score",
                                                                 "detector_box_m")})
    # a painted interior (python -m v2.bakeoff adopt) is an input: a new painting makes a new build of the layer
    raw = lambda area: (_layer_raw(area) + [cw.CUTS, REPO / "v2/data/structures/landmark_styles.json"]  # noqa: E731
                        + (sorted(p for p in cw.PAINTINGS.iterdir() if p.is_file()) if cw.PAINTINGS.is_dir() else []))
    return [
        Stage("layer_cutaways", cw.layer_cutaways, deps=("scene",), params=cw.stage_params, code=LAYER_CODE, raw=raw,
              doc="landmark cutaways: the cut models' tiles (placeholder interior), opening masks and paint inputs"),
        Stage("check_cutaways", cc.check_cutaways, deps=("layer_cutaways", "layer_buildings", "layer_ground", "scene"),
              kind="check", params=check_params, raw=raw,
              code=LAYER_CODE + ("v2.layers.cutaways", "v2.checks.framework", "v2.checks.line_checks"),
              doc="K0-K6: the cut matches the model, the interior stays in its mask, flat light, depth, off means off"),
        Stage("check_cutaways_view", cv.check_cutaways_view, deps=("release", "scene"), kind="check",
              params=lambda area: {**_art(area), "g3": {k: v for k, v in params()["g3"].items() if k.startswith("cutview_")}},
              raw=lambda area: (sorted((REPO / "v2/web/src").rglob("*.ts")) + [REPO / "v2/web/index.html", REPO / "v2/web/scripts/shot.mjs",
                                                                              REPO / "v2/web/scripts/cutaway_checks.mjs"]),
              code=("v2.layers.common", "v2.checks.framework", "v2.checks.g1_checks"),
              doc="the cutaways in the viewer: off means off, the frame is the tiles', vehicles and labels against the cut building"),
    ]


def phase3() -> list:
    """Phase 3 (PLAN_V2 sections 9.1 and 10): the tunnel view's tubes and its gate, checks X1-X8."""
    from v2.layers import tunnels as T
    from v2.checks import tunnel_checks as tc
    web = lambda area: (sorted(p for p in (REPO / "v2/web/src").rglob("*.ts")) + [REPO / "v2/web/index.html"]  # noqa: E731
                        + sorted((REPO / "v2/web/scripts").glob("xray_*")) + [REPO / "v2/web/scripts/shot.mjs"])
    return [
        Stage("layer_tunnels", T.layer_tunnels, deps=("scene",), code=GEO + CAM + ("v2.layers.common", "v2.layers.raster"),
              params=lambda area: {"tunnels": params()["tunnels"], "portal_max_from_end_m": params()["checks"]["portal_max_from_end_m"]},
              raw=lambda area: [T.CASEMATES], doc="tunnel view: the tunnels of the graph and the casemates as tubes"),
        Stage("check_tunnel_view", tc.check_tunnel_view, deps=("release", "scene"), kind="check",
              params=lambda area: {**_art(area), "g3": params()["g3"], "tunnels": params()["tunnels"],
                                   "portal_max_from_end_m": params()["checks"]["portal_max_from_end_m"]},
              code=LAYER_CODE + ("v2.layers.tunnels", "v2.checks.framework", "v2.checks.layer_checks", "v2.checks.g1_checks"),
              raw=lambda area: _layer_raw(area) + [T.CASEMATES] + web(area),
              doc="tunnel view (x-ray): tubes in place and at depth, vehicles in tunnels only, the fade, toggles, portals, speed"),
    ]
