# v2 Phase 0 report: Foundation

9 November 2026. Branch `v2-phase0`, into `v2`. Spend: **$0**. No GPU and no paid service was used (the ledger's
Phase 0 line is capped at $0 and check L3 gates it).

**Gate G0 status:**
- **Test area (Grund, Pfaffenthal and the Bock): all 28 stages pass, including every data check.**
- **Commune (where cheap):** the whole scene is built for all 24 quarters. 8 of 12 check stages pass. The four that
  fail (terrain, buildings, transport profiles, transport graph) are listed below. They are real data cases outside
  the test area, and they are Phase 4 work: the plan's gate is the test area. All checks were left unchanged, so
  these show up as failures.

## 1. What was built

| Part | Where | What it does |
|---|---|---|
| Folder structure | `v2/` (PLAN_V2 section 12) | config, data, layers, checks, build, web, docs, ledger, with `v2/README.md` |
| Build graph | `v2/build/graph.py`, `stages.py`, `python -m v2.build <area> [stage]` | 28 stages. Each output folder is keyed by its code, params, deps and raw inputs (`<data>/v2/<area>/<stage>/<key>/` with `manifest.json`). It resumes, keeps old versions, and check stages fail the build with exit 1 and block what depends on them. Small and dependency-free (no framework). |
| Config | `v2/config/` | Areas `test` (1.57 km²) and `commune` (OSM relation 407489, 51.7 km², 24 quarters). Camera = v1's, at 0.125 m/px, with an exact v1 ↔ v2 pixel conversion. Sun = NOAA position for Luxembourg. Palette from v1's colours. The layer registry. `params.json` holds every threshold. |
| Data | `v2/data/fetch/`, `docs/DATA.md` | Reuses v1's ACT 3D buildings, GTFS and landmarks. Fetches OSM with node ids (Overpass), LiDAR 2024 terrain and surface (windowed reads of ACT's national COGs: 0.5 m test, 1 m commune) and the LiDAR 2024 tree survey (the 3.9 GB GeoPackage is streamed and its SQLite pages decoded on the fly, so only the commune's 1.1 M trees are kept). Downloads took about 7 minutes, one at a time. |
| Scene | `v2/data/scene/`, `docs/specs/scene.md` | Terrain with slope, steep and cliff classes and the measured OSM walls; water; buildings (ACT id, roof planes, roof shape, heights, footprint, walls, installations as parts, triangle mesh); facade layout; trees (thinned over water and buildings); places (v1's 129 cards and 1,035 places back in metres) |
| Facade layout | `facades.py`, `docs/specs/facades.md` | Floors from eave height and bays from wall length, windows in straight rows, none on party walls, kept only inside the wall outline |
| Transport graph | `transport.py`, `profile.py`, `docs/specs/transport-graph.md` | OSM roads, paths, rail, tram and funicular, split at junctions. Each segment has a height profile: a grade-capped L1 solve on the LiDAR terrain, on the LiDAR surface for bridge decks, and under the terrain or the built cover for tunnels, with portals found. Node heights come from two passes, so segments meeting at a junction share one height. |
| Transit | `transit.py` | v1's HMM matching (reviewed, kept), now on the unwarped OSM geometry |
| Viaducts as data | `v2/data/structures/viaducts.json`, `structures.py`, `docs/specs/structures.md` | Pulvermühl, Clausen and Pfaffenthal: deck from the graph, arches and piers from documented spans and lengths, with every assumption marked |
| Checks | `v2/checks/`, `docs/specs/checks.md` | Framework plus 73 numbered entries (gates and reported facts): scope, terrain, buildings, facades, trees, profiles, graph, structures, transit, places, no patching (brief 1), ledger |
| Specs | `v2/docs/specs/` | Conventions; layers 1–15; scene; facades; transport graph; structures; camera; checks; palette; tiles and R2 hosting; compositor; ledger |
| Spend ledger | `v2/ledger/` | `budget.json` (PLAN section 10 lines: $0 / $0 / ≤ $17 / ≤ $8 / ≤ $60 / ≤ $3, owner cap $100), append-only `spend.jsonl`, and `ledger.py`. It refuses a run that has no owner-approved quote, that would go over its goal's cap, or whose provider's billing has not been reconciled. |
| Tests | `*/tests/`, `python -m pytest v2` | 31 unit tests, under a second, no downloads; added as a CI job |
| Previews and results | `v2/docs/img/`, `v2/docs/results/` | Published by the report stages |

## 2. Check results

### Test area: all pass (`results/g0_test.json`, `results/checks_test.json`)

| Group | Results |
|---|---|
| Scope | S1–S6 pass. Area 1.566 km², inside the v2 frame. |
| Terrain | No holes. Buildings sit on the LiDAR ground with a median difference of 1.04 m (90th percentile 3.8 m, on slopes). 24.5 ha steep, 7.4 ha cliff. 761 OSM walls/cliffs measured (46 km). |
| Buildings | 1,135 buildings, all closed, valid and non-overlapping, ids unique. Roofs: 342 gable, 271 hip, 121 mansard, 120 flat, 51 shed, the rest mixed. |
| Facades | 22,544 walls, 4,421 party walls, 40,473 windows on 6,329 walls. No window outside its wall, every row on a floor line. 99.7% of buildings ≥ 5 m and ≥ 40 m² have windows. |
| Trees | 12,414 trees. None stand in a building or in water, no crown is more than 30% over them, heights 2.3–44.5 m. 125 crowns thinned, 7 survey spikes dropped. |
| Profiles | 3,158 edges, 2,581 nodes. No missing heights. Edge ends meet their node heights. No vehicle jumps. No relaxed grade on vehicle ways. Decks on the LiDAR surface (median 0.01 m). Tunnels are a clearance + 1 m under their cover. All portals of long tunnels were found within 40 m. 96 of 103 portals were found in all. |
| Graph | No unjoined junctions. 99.1% of road length and 100% of rail/tram connected. No dangling vehicle bridges or tunnels (3 garage driveways reported). |
| Structures | All 3 viaducts modelled. Decks on the graph, piers on the ground. Lengths 259 / 200 / 274 m against documented 242 / 208 / 257 m (within 15%). |
| Transit | 35 shapes (6 tram, 29 train). 100% of GTFS track in the area matched onto the rail graph. |
| Places | 338 places (62 landmarks). Round trip to v1 pixels: 95th percentile 0.03 px, worst 2.0 px (on a cliff edge). |
| Build | No stage or module named like a fix on art. Ledger valid, $0 spent. |

### Commune (`results/checks_commune.json`)

Built: 23,373 buildings, 2.5 M triangles, 406,531 walls, 758,881 windows, 475,977 trees, 1,161 places, and
33,051 transport edges (691 km road, 107 km rail, 30 km tram, 746 km paths). Transit matched 99.8% (73 shapes).
Scope, facades, trees, structures, transit, places and ledger pass. The failures:

| Check | Value | What it is |
|---|---|---|
| TR3 | 0.57% of cells where the surface model is > 0.5 m below the terrain | probably water surfaces and the edges of cut-out bridges in the 1 m overview; to inspect |
| B2 | 1 invalid footprint (`ACT_38d27a01-…`) | a self-touching ACT ground surface; fix: repair (`buffer(0)`) in `scene_buildings` |
| P5, P6 | 2 decks below ground, 22 decks off the surface (e.g. Passerelle du Neudorf 11 m, Autoroute d'Arlon 0.5 m) | bridges under other bridges or under trees (the surface model sees the upper one), and motorway decks at 1 m |
| P7, P8, P9 | 18 tunnels too shallow, 2 above their cover, 12 portals not found | long road tunnels (Kirchberg, motorway) where the cover is a building or deck outside the footprints used, or the tunnel tag starts in a cutting |
| G5 | 2 vehicle bridges/tunnels with a dead end (`w727209075`, `w1510587817`) | OSM data ends; to check one by one |

None of these are in the test area. They are the commune's production work (Phase 4), now found automatically and
before any money is spent.

## 3. Data sizes

| | Stored |
|---|---|
| Shared fetches (OSM transport 12.7 MB, OSM ground 13.8 MB, trees 61 MB) | 84 MB |
| Test area (LiDAR 0.5 m 46 MB; scene 87 MB: terrain 64, buildings 10, facades 9, transport 3.5) | 205 MB (all versions) |
| Commune (LiDAR 1 m 704 MB; terrain 907, buildings 161, facades 174, transport 46, trees 25) | 2.1 GB (all versions) |
| In git: config (areas 0.4 MB), specs, code, previews (9 JPEGs, each < 1 MB, 5.0 MB total) | ~6 MB |

## 4. Previews (`v2/docs/img/`)

| Image | Shows |
|---|---|
| `test_buildings_height.jpg` | the test area's buildings coloured by height, over the relief, with the area polygon |
| `test_transport_height.jpg` | the transport graph coloured by profile height; bridge decks cased, tunnels dashed, portals boxed, viaduct piers |
| `test_rail_profile.jpg` | every track's height along the line, with ground under it, the tunnels and the modelled piers and arches of the three viaducts |
| `test_trees_relief.jpg` | 12,414 LiDAR trees by type and crown size, cliffs in orange |
| `test_iso_buildings.jpg`, `test_iso_grund_windows.jpg` | the buildings through the v2 camera (south-east, 30°, v2 pixels) with the facade layout's windows, depth-sorted. Flat test shading only, not art. |
| `commune_buildings_height.jpg`, `commune_transport_height.jpg`, `commune_trees_relief.jpg` | the same for all 24 quarters |

## 5. Open questions for G0 (the owner's decisions)

1. **Test area size.** The polygon is 1.29 × 1.61 km (1.57 km²) instead of about 1.2 × 1 km. That is what it takes
   to include everything named: the station tunnel's north portal, the Pulvermühl viaduct, the Clausen and
   Pfaffenthal viaducts, Pfaffenthal-Kirchberg station and funicular, and the Red Bridge's east end. Keep it or
   trim it?
2. **Viaduct arches.** The Clausen and Pfaffenthal arch counts are assumptions (15 m spans, giving 11 and 15
   arches); no source gave the counts. For Pulvermühl, OSM says arch but the French article describes reinforced-
   concrete piers and a metal deck, so it is modelled as 5 arches. A photo count would settle both; only
   `viaducts.json` would change.
3. **Facade rule.** Floors are 3.6 m then 3.0 m, bays 2.7 m, windows 1.1 × 1.45 m on a 0.9 m sill. There are no
   doors, shop fronts or dormers yet. Accept as the layout for the bake-off?
4. **Tunnels and portals.** Clearances are road 4.5 m, rail 5.5 m, tram 4.5 m, plus 1 m of cover; the portal zone
   is 40 m and the portal mouth 6 m. Garage driveways (class service) are excepted from the dead-end gate. Agree?
5. **Paths and steps.** These are measured but not gated on grade (stairs and lifts are often mapped as footways):
   about 46 relaxed in the test area. Agree?
6. **Commune terrain resolution.** The commune uses 1 m (the COG overview, 0.9 GB) and the test area 0.5 m. Full
   0.5 m for the commune would be ~3.6 GB, fetched per batch in Phase 4 if the relief layer needs it.
7. **Funicular timetable.** The Pfaffenthal funicular is not in the GTFS feed (0 shapes). Layer 12 needs a
   schedule for it (from CFL's published interval), or it runs on a fixed loop.
8. **Commune check failures** (section 2). Fix them in Phase 4 batch by batch, as planned, or now before G1?
9. **R2.** The bucket and account for tiles, and the immutable-release scheme in `specs/tiles-hosting.md`.
10. **Licences.** GTFS is credited "CC BY" as in v1; please confirm the exact version for the credits page.

## 6. How to reproduce

```sh
uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r v2/requirements.txt
export ISOLUX_DATA=/path/to/repo/data
.venv/bin/python -m v2.build test            # ~10 min from nothing (downloads included), then seconds
.venv/bin/python -m v2.build commune         # ~15 min
.venv/bin/python -m v2.build.report commune  # publish check results and previews even when a gate fails
.venv/bin/python -m pytest v2
```
