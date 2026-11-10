# Checks

Every check is a stage of the build graph with `kind="check"`; it returns numbered entries and the build fails
(exit 1) when a *gate* entry fails, after running the stages that do not depend on it (nothing downstream of a failed
check runs; `g0` needs every check). Framework: `v2/checks/framework.py`. Data checks: `v2/checks/data_checks.py`.
Build checks: `v2/checks/repo_checks.py`. Thresholds: `v2/config/params.json` "checks" and the section of the part.

## G0 data checks (built, run on the test area and the commune)

| Id | Gate | Rule |
|---|---|---|
| **Scope** | | |
| S1 | yes | No building whose footprint lies outside the area (representative point, 1 m tolerance) |
| S2 | yes | No tree outside the area |
| S3 | yes | No place outside the area |
| S4 | yes | Every transport edge touches the area + its margin |
| S5 | yes | The terrain grid covers the area and 90% of its margin |
| S6 | yes | The area (z 180–450 m, with its margin) lies inside the v2 pixel frame |
| **Terrain** | | |
| TR1 | yes | ≤ 0.1% of terrain cells had no data |
| TR2 | yes | No missing terrain after filling |
| TR3 | yes | Surface below ground by > 0.5 m on ≤ 0.1% of cells |
| TR4 | yes | Buildings sit on the terrain: median \|ACT ground − LiDAR ground\| ≤ 1.5 m |
| TR5–7 | report | 90th percentile of TR4; steep and cliff area; OSM walls measured |
| **Buildings** | | |
| B1 | yes | Every footprint ring closed |
| B2 | yes | No invalid or empty footprint |
| B3 | yes | ≤ 1% of buildings without a roof or with fewer than 3 walls (closed shells) |
| B4 | yes | No two buildings overlapping by > 1 m² and > 2% of the smaller |
| B5 | yes | Heights possible: 0 < h ≤ 150 m, ground ≤ eave ≤ ridge |
| B6 | yes | Ids unique |
| B7 | report | Roof shapes |
| B8 | report | ACT footprints repaired (self-touching rings after storing at 1 mm), with their reason |
| **Facades** | | |
| F1 | yes | Every window inside its wall outline |
| F2 | yes | Windows in a row ≥ 0.3 m apart |
| F3 | yes | Every window row on a floor line (straight rows) |
| F4 | yes | No windows on party walls |
| F5 | yes | Floor count fits the eave height |
| F6 | yes | ≥ 90% of buildings ≥ 5 m tall and ≥ 40 m² have a window |
| F7 | report | Walls, with windows, party walls, windows |
| F8 | yes | Every building with a street-facing wall has a door on one |
| F9 | yes | No door or shop front on a party (shared) wall |
| F10 | yes | Shop fronts only on the ground floor |
| F11 | yes | Doors and shop fronts inside their wall outline |
| F12 | yes | Doors and shop fronts stand on the bottom of their wall (the ground) |
| F13 | yes | No window overlaps a door or a shop front (rows stay straight: F3) |
| F14 | yes | ≥ 90% of OSM entrances at a building placed as doors |
| F15 | report | Doors and shop fronts by source (OSM or rule) |
| **Trees** | | |
| TE1 | yes | No tree standing inside a building |
| TE2 | yes | No tree standing in water |
| TE3 | yes | No crown more than 30% (+2%) over buildings or water |
| TE4 | yes | Heights within 2–50 m |
| TE6 | yes | No crown wider than its species' and age's shape allows (layer-07 rule 1), or than the survey's width where that is wider |
| TE7 | yes | Thinning only narrows a crown |
| TE8 | info | Median height over crown width |
| **Transport profiles** | | |
| P1 | yes | Every sample has a height |
| P2 | yes | Edge ends at their node's height (≤ 0.3 m): continuous across junctions |
| P3 | yes | Vehicle edges: no step between samples beyond the grade cap × spacing + 0.25 m (or 0.5 m) |
| P4 | yes | No vehicle edge needed its grade cap relaxed |
| P5 | yes | Vehicle bridge decks never below the ground (0.5 m) |
| P6 | yes | Vehicle bridge decks on the LiDAR surface (median ≤ 0.5 m, edges ≥ 10 m) |
| P7 | yes | Vehicle tunnels (in the area) a clearance + 1 m under their cover beyond 40 m from a portal |
| P8 | yes | Vehicle tunnels (in the area, past the 6 m portal mouth) never > 1 m above their cover |
| P9 | yes | Each portal of a vehicle tunnel ≥ 80 m long (ends in the area) found within 40 m of the tunnel end |
| P10–12 | report | Paths/steps with jumps or relaxed grade (stairs mapped as paths); median deck error; portals found |
| P13–15 | report | Bridges excepted (exceptions.json); approaches found on a structure past the OSM bridge tag; share of deck samples not observed |
| **Transport graph** | | |
| G1 | yes | Every edge's nodes exist |
| G2 | yes | No vehicle dead end within 0.5 m of another edge end (an unjoined junction) |
| G3 | yes | ≥ 97% of road length connected (to the main network or out of the area) |
| G4 | yes | ≥ 97% of rail and tram length connected |
| G5 | yes | No vehicle bridge or tunnel with a dead end (garage driveways, class service, excepted: G5b report) |
| G5c | report | Dead ends excepted (exceptions.json) |
| G6 | report | Length by mode |
| **Structures** | | V1–V7, see structures.md |
| **Transit** | | |
| TT1 | yes | ≥ 99% of GTFS tram and train track in the area matched onto the rail graph |
| TT2 | yes | ≥ 90% of GTFS samples within 17 m of their matched path (GTFS shapes are coarse) |
| TT3 | yes | Every shape in the area has a matched run |
| **Places** | | |
| PL1 | yes | 95th percentile round trip to v1 pixels ≤ 0.75 px |
| PL2a | yes | Largest round trip ≤ 4 px (v1 stored whole pixels; on cliff edges half a pixel moves a ray off a cell) |
| **Build** | | |
| N1, N2 | yes | No stage, stage function or module named like a fix on finished art (warp, repaint, fit_to_art, despeckle, …): brief 1 |
| L1–L3 | yes | Ledger valid; total within the owner's cap; Phase 0 spend = 0 |

## Exceptions

`v2/data/exceptions.json` lists per-feature exceptions to a check, each with its place and reason (owner's rule, G0
review: fix causes, never loosen a threshold; the list stays short). A check skips only the listed OSM ways and
reports them (P13, G5c). Today: one structure at Howald that the LiDAR 2024 surface model does not contain (P5, P6),
and two yard sidings that end at buffer stops inside tunnels (G5).

## Brief checks (PLAN_V2 section 8), and where they live
| Brief | Check | Spec |
|---|---|---|
| 1 No patching | N1, N2 (built); every check reruns its own layer only | here |
| 4 Layers | layer-off pixel diff L1.3 (and in each layer) | layers 1–7 |
| 5 No baked shadows | L5.1, L9.1, L9.2, L1.2, L2.3 | layers 5, 9 |
| 6 Straight lines and windows | F1–F5 (built), L5.2, L4.5 | facades, layer 5 |
| 7 Roads and rails match | P1–P9, G1–G5, TT1–TT3 (built), L4.1, L4.2, L4.6 | transport graph, layer 4 |
| 8 Tunnels and bridges | P5–P9 (built), L6.2, L12.1, L12.2 | layers 6, 12 |
| 9 No painted cars | L1.5 and every layer's no-cars check (v1's OWLv2 detector) | layers 1–7 |
| Seams | seam check in every tiled layer | conventions |
| Speed | L9.3, L14.3 and the viewer's budget | compositor |

## Unit tests
`python -m pytest v2` (31 tests, under a second, no downloads): build graph, profile solver, transport graph on a
synthetic valley, facades, camera and sun, ledger, check framework, the streaming SQLite reader.

## G1 checks (built in phase 1, run on the test area)

Stages of the build graph (`python -m v2.build test g1`), each a gate; thresholds in `params.json` "g1".

| Stage | Checks | Brief |
|---|---|---|
| `check_layers` (`v2/checks/layer_checks.py`) | L1.1, L1.2, L2.1, L2.2, L3.1, L4.1, L4.3, L4.6, L8.1-L8.3, P-1 | 7 |
| `check_independence` (`g1_checks.py`) | C1a every layer re-rendered without each other layer's own inputs is identical; C1b/C1c the tiles are the renderer's | 4 |
| `check_shadows` | L5.1/L9.2 shadow detector (median luminance of a material in the 3D shadow of the photo's sun vs lit next to it), L9.0, L9.1 (08, 13, 19 h), L2.3 | 5 |
| `check_seams` | v1's seam rule per colour layer at the tiles' scale; L8.4 depth across borders against the tiles' middle lines | seams |
| `check_vehicles` | L4.2, L12.4 on drawn road/track over a simulated day; L12.1a none drawn in a tunnel past its portal; C4 probes at every portal, bridge and way under a deck vs the exact geometry; L12.2 heights between frames; L12.3 | 7, 8 |
| `check_no_cars` (`owl_detect.py`) | OWLv2 (v1's detector, local cache, offline) on every colour layer tile: 0 vehicles >= 0.1 | 9 |
| `check_viewer` (`v2/web/scripts/viewer_checks.mjs`) | V1 layer off leaves no pixel; V2 no shadow of a layer that is off; V3 viewer shadows = Python reference at 10, 13, 16 h and they move; V4 no light by day; V5 seasons only on their masks; V6 labels never overlap; V7 look pass idempotent; C2 speed | 4, 5, speed |

Exceptions: none were needed for G1 (`v2/data/exceptions.json` is unchanged).

## G3 checks (phase 3, run on the test area)

Thresholds in `params.json` "g3".

| Stage | Checks |
|---|---|
| `check_tunnel_view` (`v2/checks/tunnel_checks.py`, `v2/web/scripts/xray_checks.mjs`, `xray_audit.ts`) | X1-X8 of [tunnel-view.md](tunnel-view.md): tubes in place and at depth against the graph, vehicles in tunnels only, the fade, the layer toggles, portals, casemates, speed |
