# v2 Phase 0 report: Foundation

9 November 2026. Branch `v2-phase0`, into `v2`. Spend: **$0**. No GPU and no paid service was used (the ledger's
Phase 0 line is capped at $0 and check L3 gates it).

**Gate G0 status (after the owner's G0 review, section 7):**
- **Test area (Grund, Pfaffenthal and the Bock): all 29 stages pass, including every data check.**
- **Commune (all 24 quarters): all 29 stages pass.** The four check stages that failed at the first review (TR3, B2,
  P5–P9, G5) were fixed at their causes; no threshold was loosened. Three features are excepted, each with its reason,
  in `v2/data/exceptions.json` (section 7).

## 1. What was built

| Part | Where | What it does |
|---|---|---|
| Folder structure | `v2/` (PLAN_V2 section 12) | config, data, layers, checks, build, web, docs, ledger, with `v2/README.md` |
| Build graph | `v2/build/graph.py`, `stages.py`, `python -m v2.build <area> [stage]` | 29 stages. Each output folder is keyed by its code, params, deps and raw inputs (`<data>/v2/<area>/<stage>/<key>/` with `manifest.json`). It resumes, keeps old versions, and check stages fail the build with exit 1 and block what depends on them. Small and dependency-free (no framework). |
| Config | `v2/config/` | Areas `test` (1.57 km²) and `commune` (OSM relation 407489, 51.7 km², 24 quarters). Camera = v1's, at 0.125 m/px, with an exact v1 ↔ v2 pixel conversion. Sun = NOAA position for Luxembourg. Palette from v1's colours. The layer registry. `params.json` holds every threshold. |
| Data | `v2/data/fetch/`, `docs/DATA.md` | Reuses v1's ACT 3D buildings, GTFS and landmarks. Fetches OSM with node ids (Overpass), LiDAR 2024 terrain and surface (windowed reads of ACT's national COGs: 0.5 m test; 1 m commune, reduced from the 0.5 m tiles), OSM entrances and shops and the LiDAR 2024 tree survey (the 3.9 GB GeoPackage is streamed and its SQLite pages decoded on the fly, so only the commune's 1.1 M trees are kept). Downloads took about 7 minutes, one at a time. |
| Scene | `v2/data/scene/`, `docs/specs/scene.md` | Terrain with slope, steep and cliff classes and the measured OSM walls; water; buildings (ACT id, roof planes, roof shape, heights, footprint, walls, installations as parts, triangle mesh); facade layout; trees (thinned over water and buildings); places (v1's 129 cards and 1,035 places back in metres) |
| Facade layout | `facades.py`, `entrances.py`, `docs/specs/facades.md` | Floors from eave height and bays from wall length, windows in straight rows, none on party walls, kept only inside the wall outline. Doors and shop fronts: from OSM entrances and shops where mapped, else one street door per building and shop fronts along commercial streets; ground-floor windows give way |
| Transport graph | `transport.py`, `profile.py`, `docs/specs/transport-graph.md` | OSM roads, paths, rail, tram and funicular, split at junctions. Each segment has a height profile: a grade-capped L1 solve on the LiDAR terrain, on the LiDAR surface for bridge decks, and under the terrain or the built cover for tunnels, with portals found. Node heights come from two passes, so segments meeting at a junction share one height. |
| Transit | `transit.py` | v1's HMM matching (reviewed, kept), now on the unwarped OSM geometry |
| Viaducts as data | `v2/data/structures/viaducts.json`, `structures.py`, `docs/specs/structures.md` | Pulvermühl, Clausen and Pfaffenthal: deck from the graph, arches and piers from documented spans and lengths, with every assumption marked |
| Checks | `v2/checks/`, `docs/specs/checks.md`, `v2/data/exceptions.json` | Framework plus 86 numbered entries (gates and reported facts): scope, terrain, buildings, facades, trees, profiles, graph, structures, transit, places, no patching (brief 1), ledger |
| Specs | `v2/docs/specs/` | Conventions; layers 1–15; scene; facades; transport graph; structures; camera; checks; palette; tiles and R2 hosting; compositor; ledger |
| Spend ledger | `v2/ledger/` | `budget.json` (PLAN section 10 lines: $0 / $0 / ≤ $17 / ≤ $8 / ≤ $60 / ≤ $3, owner cap $100), append-only `spend.jsonl`, and `ledger.py`. It refuses a run that has no owner-approved quote, that would go over its goal's cap, or whose provider's billing has not been reconciled. |
| Tests | `*/tests/`, `python -m pytest v2` | 31 unit tests, under a second, no downloads; added as a CI job |
| Previews and results | `v2/docs/img/`, `v2/docs/results/` | Published by the report stages |

## 2. Check results

### Test area: all pass (`results/g0_test.json`, `results/checks_test.json`)

Re-run after the G0 review fixes; the numbers below are current.

| Group | Results |
|---|---|
| Scope | S1–S6 pass. Area 1.566 km², inside the v2 frame. |
| Terrain | No holes. Buildings sit on the LiDAR ground with a median difference of 1.04 m (90th percentile 3.8 m, on slopes). 24.5 ha steep, 7.4 ha cliff. 761 OSM walls/cliffs measured (46 km). |
| Buildings | 1,135 buildings, all closed, valid and non-overlapping, ids unique. Roofs: 342 gable, 271 hip, 121 mansard, 120 flat, 51 shed, the rest mixed. |
| Facades | 22,544 walls, 4,421 party walls, 37,786 windows on 6,216 walls (2,687 ground-floor windows gave way to doors and shop fronts). 3,170 street-facing walls; 1,135 doors (73 from OSM entrances, 1,062 by rule) and 823 shop fronts (288 from OSM shops, 535 along 43 commercial streets). Every building with a street-facing wall has a door on one; none on a shared wall; shop fronts only at ground level; no window overlaps them; rows still straight. 94% of OSM entrances placed (5 not: party walls or no wall in reach, listed). |
| Trees | 12,414 trees. None stand in a building or in water, no crown is more than 30% over them, heights 2.3–44.5 m. 125 crowns thinned, 7 survey spikes dropped. |
| Profiles | 3,157 edges, 2,580 nodes. No missing heights. Edge ends meet their node heights. No vehicle jumps. No relaxed grade on vehicle ways. Decks on the LiDAR surface (median 0.01 m; 12% of deck samples not observed: under buildings, crowns or higher bridges). Tunnels are a clearance + 1 m under their cover. All portals of long tunnels were found within 40 m; 99 of 103 portals in all. 83 m of approach road found on a structure past the OSM bridge tag. |
| Graph | No unjoined junctions. 99.2% of road length and 100% of rail/tram connected. No dangling vehicle bridges or tunnels (3 garage driveways reported). |
| Structures | All 3 viaducts modelled. Decks on the graph, piers on the ground. Lengths 259 / 200 / 274 m against documented 242 / 208 / 257 m (within 15%). |
| Transit | 35 shapes (6 tram, 29 train). 100% of GTFS track in the area matched onto the rail graph. |
| Places | 338 places (62 landmarks). Round trip to v1 pixels: 95th percentile 0.03 px, worst 2.0 px (on a cliff edge). |
| Build | No stage or module named like a fix on art. Ledger valid, $0 spent. |

### Commune: all pass (`results/g0_commune.json`, `results/checks_commune.json`)

Built: 23,373 buildings, 2.5 M triangles, 406,531 walls, 729,407 windows, 22,281 doors (722 from OSM, 21,559 by
rule), 4,594 shop fronts (1,684 from OSM shops, 2,910 along 148 commercial streets), 475,977 trees, 1,161 places,
and 32,956 transport edges (691 km road, 107 km rail, 30 km tram, 746 km paths). Transit matched 99.8% (73 shapes).
Buildings sit on the LiDAR ground with a median difference of 0.71 m. 97% of OSM entrances placed. 98.4% of
rail/tram and 99.7% of road length connected. 367 of 383 portals found.

The four failures of the first review, fixed at their causes (the checks and thresholds are unchanged):

| Check | Was | Cause | Fix |
|---|---|---|---|
| TR3 | surface below terrain on 0.57% of cells | ACT's 1 m COG overviews of the terrain and the surface model are not made the same way (never at 0.5 m) | the 1 m grids are built from the 0.5 m tiles, terrain by the mean of 2 × 2 blocks, surface by their max (2.3 GB download, streamed): 0 cells |
| B2 | 1 invalid footprint | an ACT ground outline that crossed itself once rounded to 1 mm | footprints are snapped to the 1 mm grid keeping topology; any that would still be invalid is repaired with `make_valid` and listed with its reason (B8: none left) |
| P5, P6 | 2 decks below ground, 22 off the surface | the surface model seen through: decks under trees, buildings, higher bridges and car-park roofs; and ACT's bridge cut running past OSM's bridge tag, so the abutment took the cut-out ground; a footbridge under construction mapped as a road | surface samples under a building, a survey crown or a higher bridge, on covered bridges, or a vehicle's clearance above the rest of the deck are not observations; an abutment takes the deck's level wherever the deck's end is seen; an approach still on the structure follows the surface model; `highway=construction` is not drivable. 2 exceptions (below) |
| P7–P9 | 18 shallow tunnels, 2 above cover, 12 portals missed | all car-park aisles (`service=parking_aisle`) held to a 4.5 m road clearance; tunnel nodes between portals interpolated without regard to the cover; the portal search stopped at the first branch | clearance from OSM `maxheight` where tagged, else a car park's 2.5 m for service roads underground (else the accepted 4.5 / 5.5 / 4.5 m); tunnel nodes held under their cover, then within the grade caps; portals searched through every branch |
| G5 | 2 dead-end rail tunnels | yard sidings ending at buffer stops inside tunnels | 1 exception (below) |

## 3. Data sizes

| | Stored |
|---|---|
| Shared fetches (OSM transport 12.7 MB, OSM ground 13.8 MB, OSM POIs, trees 61 MB) | ~90 MB |
| Test area (LiDAR 0.5 m 46 MB; scene ~90 MB: terrain 64, buildings 10, facades ~10, transport 3.5) | 390 MB on disk incl. superseded versions |
| Commune (LiDAR 1 m 541 MB; terrain 742, buildings 161, facades ~180, transport 46, trees 25) | 3.9 GB on disk incl. superseded versions (current ≈ 1.8 GB) |
| In git: config (areas 0.4 MB), specs, code, previews (10 JPEGs, each < 1 MB, 5.2 MB total) | ~7 MB |

Superseded versions stay in `data/v2` until cleaned (the build never overwrites a version).

## 4. Previews (`v2/docs/img/`)

| Image | Shows |
|---|---|
| `test_buildings_height.jpg` | the test area's buildings coloured by height, over the relief, with the area polygon |
| `test_transport_height.jpg` | the transport graph coloured by profile height; bridge decks cased, tunnels dashed, portals boxed, viaduct piers |
| `test_rail_profile.jpg` | every track's height along the line, with ground under it, the tunnels and the modelled piers and arches of the three viaducts |
| `test_trees_relief.jpg` | 12,414 LiDAR trees by type and crown size, cliffs in orange |
| `test_iso_buildings.jpg`, `test_iso_grund_windows.jpg` | the buildings through the v2 camera (south-east, 30°, v2 pixels) with the facade layout, depth-sorted. Flat test shading only, not art. |
| `test_iso_grund_doors.jpg` | **new:** the Grund close up: doors (brown), shop fronts (teal) and windows on the walls facing the camera |
| `commune_buildings_height.jpg`, `commune_transport_height.jpg`, `commune_trees_relief.jpg` | the same for all 24 quarters |

## 5. Questions for G0 and the owner's answers (review of 9 Nov 2026)

1. **Test area size** — *keep* the 1.29 × 1.61 km area as drawn.
2. **Viaduct arches** — *still open* (Clausen and Pfaffenthal counts are assumptions; Pulvermühl arch or beam).
3. **Facade rule** — *add doors and shop fronts before the bake-off* (done, section 2 and `specs/facades.md`);
   dormers later.
4. **Tunnels and portals** — *accepted as built*: clearances road 4.5, rail 5.5, tram 4.5 m + 1 m cover; 40 m portal
   zone; 6 m portal mouth; garage-driveway exemption. Added since, for car parks: OSM `maxheight`, else 2.5 m for
   service roads underground (section 7).
5. **Paths and steps** — *accepted*: slopes recorded, not a hard check.
6. **Commune terrain** — *stays at 1 m*, now reduced consistently from the 0.5 m tiles.
7. **Funicular timetable** — *still open*.
8. **Commune check failures** — *fix before G1* (done, section 2).
9. **R2** — *still open*.
10. **GTFS licence version** — *still open*.

All recorded in `research/v2/DECISIONS.md`.

## 6. How to reproduce

```sh
uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r v2/requirements.txt
export ISOLUX_DATA=/path/to/repo/data
.venv/bin/python -m v2.build test            # ~10 min from nothing (downloads included), then seconds
.venv/bin/python -m v2.build commune         # ~20 min
.venv/bin/python -m v2.build.report commune  # publish check results and previews even when a gate fails
.venv/bin/python -m pytest v2
```

## 7. For the owner: what to look at

- **Exceptions** (`v2/data/exceptions.json`, 3 entries, 9 OSM ways):
  1. Howald, tram and service bridges over the railway (5 ways): the LiDAR 2024 surface model shows no deck over the
     whole span, so the structure is not in the survey; the deck heights come from the abutments (P5, P6).
  2. Gasperich, a 17 m service bridge (1 way): a structure the 3D model lacks stands over the whole span, so the
     deck is never seen (P5, P6).
  3. Two yard sidings ending at buffer stops inside tunnels (G5).
- **A new clearance for car parks** (2.5 m for service roads in tunnels without `maxheight`). This is a model of
  what the data describes (parking aisles), not a loosened check: road, rail and tram tunnels keep the accepted
  clearances. Say if you want it reviewed.
- **Doors by rule** are 97% of all doors (OSM maps few entrances). Shop fronts on commercial streets are by rule
  where no shop is mapped; the 43 commercial streets of the test area are listed in `facades.json`.
