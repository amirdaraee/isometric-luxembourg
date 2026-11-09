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
| **Facades** | | |
| F1 | yes | Every window inside its wall outline |
| F2 | yes | Windows in a row ≥ 0.3 m apart |
| F3 | yes | Every window row on a floor line (straight rows) |
| F4 | yes | No windows on party walls |
| F5 | yes | Floor count fits the eave height |
| F6 | yes | ≥ 90% of buildings ≥ 5 m tall and ≥ 40 m² have a window |
| F7 | report | Walls, with windows, party walls, windows |
| **Trees** | | |
| TE1 | yes | No tree standing inside a building |
| TE2 | yes | No tree standing in water |
| TE3 | yes | No crown more than 30% (+2%) over buildings or water |
| TE4 | yes | Heights within 2–50 m |
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
| **Transport graph** | | |
| G1 | yes | Every edge's nodes exist |
| G2 | yes | No vehicle dead end within 0.5 m of another edge end (an unjoined junction) |
| G3 | yes | ≥ 97% of road length connected (to the main network or out of the area) |
| G4 | yes | ≥ 97% of rail and tram length connected |
| G5 | yes | No vehicle bridge or tunnel with a dead end (garage driveways, class service, excepted: G5b report) |
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

## Brief checks (PLAN_V2 section 8), and where they live
| Brief | Check | Spec |
|---|---|---|
| 1 No patching | N1, N2 (built); every check reruns its own layer only | here |
| 4 Layers | layer-off pixel diff L1.3 (and in each layer) | layers 1–7 |
| 5 No baked shadows | L5.1, L9.1, L9.2, L1.2, L2.3 | layers 5, 9 |
| 6 Straight lines and windows | F1–F5 (built), L5.2, L4.5 | facades, layer 5 |
| 7 Roads and rails match | P1–P9, G1–G5, TT1–TT3 (built), L4.1, L4.2 | transport graph, layer 4 |
| 8 Tunnels and bridges | P5–P9 (built), L6.2, L12.1, L12.2 | layers 6, 12 |
| 9 No painted cars | L1.5 and every layer's no-cars check (v1's OWLv2 detector) | layers 1–7 |
| Seams | seam check in every tiled layer | conventions |
| Speed | L9.3, L14.3 and the viewer's budget | compositor |

## Unit tests
`python -m pytest v2` (31 tests, under a second, no downloads): build graph, profile solver, transport graph on a
synthetic valley, facades, camera and sun, ledger, check framework, the streaming SQLite reader.
