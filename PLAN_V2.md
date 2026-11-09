# Isometric Luxembourg v2: plan

Status: **approved by the owner on 9 November 2026.** Phase 0 started.

Inputs: the owner's brief and decisions (`research/v2/DECISIONS.md`), what went wrong in v1
(`research/v2/V1_RETRO.md`), and how the other illustrated city maps were made (`research/v2/OTHERS.md`).

---

## 1. What v2 is

The whole City of Luxembourg (all 24 quarters) as an isometric, hand-drawn-looking map, in v1's inked style with
more detail, launched with day, golden hour and night, all four seasons, moving traffic, trams and trains, events
and weather. It replaces v1 on isometric.lu only when it is better than v1 everywhere.

## 2. Why v1 went wrong, in one paragraph

v1 asked an image model for one finished picture holding everything: ground, roads, buildings, trees, light,
shadows, even cars. Everything live (vehicles, night, seasons, events) then had to be fitted onto that picture
after the fact. The model moved streets by up to 2 m and the whole image by 6.8 px, drew windows smaller than the
cells it thinks in, painted the shadows it was asked for and the cars it saw. The fixes were warps and repaints of
finished art, decided after the money was spent. The full account is in `V1_RETRO.md`.

## 3. Principles (the rules every step must follow)

1. **The data is the truth.** Geometry comes from ACT (3D buildings, terrain, LiDAR) and OpenStreetMap. Art is
   held to the geometry and is never moved, warped or fitted after it is made. There is no warp step in v2.
2. **Layers, not a picture.** Each part of the map is its own layer with its own job (section 5). A problem is
   fixed in the layer that made it, never patched on the composite.
3. **Light comes from code.** No layer has light or shadow drawn into it. Sun, shadows, golden hour, night and
   seasons are computed in the viewer from the 3D model.
4. **Every layer carries depth.** Vehicles, labels and effects are depth-tested per pixel against the real
   geometry, so tunnels, bridges and trees hide them correctly.
5. **Nothing that moves is in the art.** No cars, people or boats in any input, training image or output, checked
   automatically.
6. **Specs and checks first.** Every layer has a written spec and numbered pass/fail checks agreed before it is
   built. Checks are gates in the build (they fail the build), not reports.
7. **Prove it small, then scale.** Everything is built and approved on the test area before it touches the city.
   Production goes 10% first.
8. **Money is quoted and capped per goal.** One spend ledger for all providers; each paid step has a quote, a cap
   and the owner's OK; the billing is reconciled after each step.
9. **One build graph.** One command builds any area from raw data to tiles, reproducibly; every stage is
   resumable and its outputs are versioned. No one-off scripts on finished art.
10. **Keep the history.** Small commits from day one; decisions go in `research/v2/DECISIONS.md` with a date.

## 4. The test area

**Grund, Pfaffenthal and the Bock**, about 1.2 km × 1 km: old houses, the Alzette, cliffs and casemates, the
Pfaffenthal viaduct and lift, the rail line and the Clausen and Pulvermühle viaducts, tunnels, steep streets,
gardens and the Neumünster Abbey. It contains every hard case from v1 in one place. Exact polygon in
`v2/config/areas/test.geojson` (Phase 0).

## 5. The layer stack

From bottom to top. "Code" means drawn by our code from the data; "AI" means painted by an image model; "A/B/C"
means it depends on the bake-off (section 7).

| # | Layer | Made by | From | Notes |
|---|---|---|---|---|
| 1 | Ground colour (land cover, pavements, squares, parks, gardens, car parks, sports) | Code | OSM + ACT land use, orthophoto for classes only | Paper grain, palette colours; no cars possible |
| 2 | Relief: terrain and cliffs | Code (+ AI rock texture in C) | LiDAR terrain | Swiss-style relief shading, hatching on steep faces |
| 3 | Water | Code | OSM polygons, rivers, pools | Animated in the viewer |
| 4 | Roads, streets, paths, rail, tram tracks, markings | Code | OSM geometry, widths, lanes; ACT for bridges and tunnels | Exact by construction; tunnel portals drawn, tunnels hidden |
| 5 | Building colour (albedo) | A, B or C | ACT LoD2 buildings | Evenly lit, no cast shadows, cut to the exact 3D outline |
| 6 | Bridges and structures (viaducts, the lift, walls, casemates) | As layer 5 | ACT + hand-built models where ACT has no arches | Viaduct arches modelled once |
| 7 | Trees and greenery | Code (A, B) or AI canopy (C) | LiDAR tree survey (position, height, crown, type) | Size from LiDAR, so no oversized trees; seasons by colour/foliage |
| 8 | Geometry buffers: depth, surface direction (normals), heights, ids | Code (render) | All of the above | Not seen; drive light, shadow, occlusion, hover |
| 9 | Light: sun shading, cast shadows, sky grade | Code, in the viewer | Layer 8 + the sun's real position | Moves with the time of day |
| 10 | Night lights: windows, street lamps, glow | Code (+ thin AI lights layer if needed) | Windows from layer 5's facade layout; OSM lamps | |
| 11 | Seasons and weather: snow, autumn trees, rain, fog | Code | Layers 7, 8 | Snow on up-facing surfaces |
| 12 | Vehicles, trams, trains, planes | Code (v1 simulation, kept) | Exact road and track graph with 3D height profiles | Depth-tested against layer 8 |
| 13 | Events (Schueberfouer, Christmas markets, National Day…) | Code + small AI sprites | Event data (v1 research) | Placed objects, never patches of the map |
| 14 | Final look: one palette grade and ink pass over the composite | Code, in the viewer | Everything below | Makes code and AI layers read as one drawing |
| 15 | Labels, pins, search, hover | Code (v1 viewer, kept and improved) | Places, landmarks, id buffer | Decluttered like Tehran's |

**Resolution:** 0.125 m per map pixel (v1: 0.25), so a window is several pixels wide. The whole commune at this
resolution is large, so tiles are served from Cloudflare R2 rather than GitHub Pages (v1 already supports a tile
URL). Far zoom levels merge layers into one image to stay fast.

## 6. Data model (Phase 0)

One scene for the whole commune, built once and versioned:

- **Buildings:** ACT LoD2, each with id, parts, roof shape, height, and (for B/C) a facade layout: floors and window
  grid per wall, derived from height and wall length, so windows are known positions, straight by construction.
- **Terrain and relief:** LiDAR ground model, with cliffs and walls marked.
- **Transport graph:** roads, rail and tram as 3D polylines with width and lanes, **each with a height profile**
  (ground, bridge deck, tunnel), joined at junctions. Tunnels are segments marked underground; portals are where
  the profile crosses the terrain. Vehicles drive on this graph only.
- **Bridges and viaducts:** decks from ACT; arches and piers modelled for the ones ACT lacks (Pulvermühle, Clausen,
  Pfaffenthal), once, as data.
- **Trees:** LiDAR survey points with height, crown and type; thinned where they overlap water or buildings.
- **Places and landmarks:** v1's 129 landmark cards and places, kept.
- **Camera:** v1's south-east isometric view and map-pixel coordinate system, kept, so v1's viewer, links and
  simulation carry over.

## 7. The art bake-off: A, B and C

On the test area, each built fully (all layers, composited, graded), then shown side by side at the same views:

| | A: all code | B: code + AI materials | C: code + AI buildings |
|---|---|---|---|
| Buildings | Inked render: outlines, flat material colours, generated windows and roof tiles | Code render using AI-made materials (roof tiles, walls, windows, doors) from a small library; the 30–60 landmarks as AI-painted portraits cut to their 3D outline | AI paints each building from an unlit render, cut to its outline (unshadowed style model) |
| Look | Clean "game city" (Warsaw, Paris) | Hand-drawn feel from the materials, exact | Richest, most like v1 |
| Risk | Generic, less charm | Repetition; landmark portraits need care | Richness from unlit input unproven; lines rely on the model |
| GPU cost, test area | $0 | ≈ $3–5 (materials + test landmarks) | ≈ $8–12 (new unshadowed style training + test area) |
| GPU cost, whole city | $0 | ≈ $10–20 (all landmark portraits) | ≈ $40–60 |

The owner picks by looking. The rest of the plan works for any winner (only layers 5–7 change). A mix is allowed,
for example B for the city and C for landmarks.

**Straight windows in C:** the research's best idea (untested anywhere) is to paint each facade front-on, then
project it onto its 3D wall, which keeps lines straight by construction. It is tried on ~10 buildings in the
bake-off; if it fails, C falls back to painting at 0.125 m/px with the facade layout as a guide and a line check.

## 8. Acceptance checks for the owner's brief

Each check is automatic unless marked "owner". They run on the test area at Gate 1–3 and on every 10% batch in
production; the build fails if one fails.

| Brief item | Check |
|---|---|
| 1. No patching | The build graph has no step that edits finished art; `grep` gate for warp/repaint stages; any failed check reruns its layer only |
| 3. Higher quality | Owner review of the bake-off and every production batch at fixed views; 0.125 m/px |
| 4. Layers | Each layer is a separate tile set; turning any layer off leaves no traces of it in the others (pixel check) |
| 5. No baked shadows | Building and ground layers: luminance on sunlit vs shadowed sides of the same material within a set tolerance (shadow detector on layers 1–7 finds nothing); shadows move with `?hour` |
| 6. Straight lines and windows | Line score: building edges and window rows deviate from the 3D model's lines by ≤ 1 px at 0.125 m/px over 95% of their length |
| 7. Roads and rails match | 100% of road, rail and tram centre lines inside their drawn surface (by construction in code; checked); vehicles on drawn road ≥ 99.5% |
| 8. Tunnels and bridges | Vehicles hidden in tunnels and under decks and trees exactly per depth (per-pixel test at every portal and bridge in the test area); smooth height on viaducts (no jumps > 0.5 m between frames) |
| 9. No painted cars | Vehicle detector (v1's OWLv2 check) on every input, training image and output: zero detections above threshold |
| Seams | No edge or tone step at block or layer joins (v1's seam check, as a gate) |
| Night, golden hour, seasons | Owner compares code relighting with an AI-painted version of the same views (section 9) |
| Speed | First view under 0.5 s on a mid phone, panning at 60 fps on desktop and ≥ 30 on a mid phone, with all layers on |

## 9. Night, golden hour and seasons by code

Buildings and ground are evenly lit, so the viewer can light them: sun shading from the normals, cast shadows from
a shadow map of the 3D model for the sun's real position, and a sky colour grade. Night adds window glow from the
facade layout (some windows dark, varying), OSM street lamps, vehicle lights and a soft glow. Seasons change tree
colour and foliage, add snow on up-facing surfaces, and grade the light.

Tiny Toronto found a code-only night looked flat and a painted night worked. So at Gate 3 the owner compares code
night and golden hour with an AI-painted version of the same views. If code falls short, AI makes only a thin
lights layer (window glow and halos) over the code-lit map, not repainted buildings.

## 10. Phases and gates

Each phase ends at a gate: the owner reviews and approves before the next phase starts.

| Phase | Work | GPU cost | Gate |
|---|---|---|---|
| **0. Foundation** | v2 folder structure and build graph; data for the whole commune; the scene (section 6) including the transport graph with height profiles and modelled viaducts; camera; checks framework; spend ledger; specs for every layer with their checks | $0 | **G0:** owner approves the specs and checks; scene and transport graph pass their data checks on the test area |
| **1. Code layers on the test area** | Layers 1–4, 8–12, 14–15 in code; viewer compositor (WebGL, several tiled layers); v1 simulation on the new graph | $0 | **G1:** brief checks 4, 5, 7, 8, 9 pass; owner sees the test area with plain code buildings |
| **2. Bake-off** | A, B and C on the test area | ≤ $17 (quote first) | **G2:** owner picks the method |
| **3. Lock the look** | Palette, grade and ink pass tuned; code vs AI night/golden comparison; seasons; events as objects; landmark portraits if B/C | ≤ $8 | **G3:** owner signs off the test area as "v2 quality"; all checks pass |
| **4. The city, 10% first** | Production for the whole commune in batches; 10% pilot, then the rest; checks gate every batch | ≤ $60 (by winner; quoted) | **G4:** owner reviews the pilot batch, then the whole city |
| **5. Launch** | Tiles on R2, performance pass, feature switches, landing on isometric.lu, v1 kept at a `/v1` link | ≈ $0 (R2 storage ≈ $1–3/month) | **G5:** owner approves the switch |

**Budget:** total ≤ $100 (owner's cap); planned ≈ $35–85 depending on the winner. Each paid step is quoted, capped
in code and reconciled. If a step would need more than its line, it stops and asks.

## 11. What carries over from v1, and what is left behind

**Kept (reviewed before reuse):** the viewer shell, feature switches, frame clock, test parameters and screenshot
and speed harness; the traffic simulation and the GTFS-to-rail matching; the whole-canvas painter with its hold and
repair mode (for C and landmark portraits); spend guards and pod watchdogs; landmark cards and research; the
visitors' notes; deploy, analytics and Sentry; the layered test's code (`pipeline/layers/v2_*`); raw data and
parsed geometry; the LiDAR tree survey; checks (seam, water, vehicle detector, flow field as a check only).

**Left behind:** the painted v1 city as production art (reference only); `fit_roads.py`, `fit_to_art.py` and all
warp outputs; `repaint.py`, `tiler.py`, `despeckle.py`, `water_tone.py`, `fix_redbridge_deck.py`,
`carry_to_versions`, per-version event patches; the `q`/`fit` fields in `lines.json`; style training data with
painted shadows (C needs new unshadowed targets).

## 12. Repository layout

v2 lives on a `v2` branch in this repo, in a new `v2/` folder, so v1 keeps working on `main` until the switch:

```
v2/
  config/        areas (test, commune), palette, camera, sun, layer specs
  data/          fetch + scene build (buildings, terrain, transport graph, trees)   -> data/v2/ (gitignored)
  layers/        one module per layer (ground, relief, water, transport, buildings, trees, buffers, …)
  checks/        one module per acceptance check; all are build gates
  build/         the build graph: one command per area and stage, resumable
  web/           the v2 viewer (from v1's shell) with the layer compositor
  docs/          specs per layer, how to run, decisions
  ledger/        spend ledger and quotes
```

Tests run in CI on every commit (small fixtures); the full checks run on the test area.

## 13. Risks

| Risk | What we do |
|---|---|
| Code and AI layers don't look like one drawing | One palette, one grade and ink pass on the composite; contact shading; decided at G3 on the test area |
| Unlit input gives poorer paintings (C) | Measured in the bake-off before any city spend |
| The whole commune at 0.125 m/px is very large | R2 hosting; merged far-zoom levels; batch builds; measured at G1 |
| Launch scope (all versions, vehicles, events, weather) is big | Code lighting and seasons keep it affordable; anything not passing its checks waits behind a feature switch rather than shipping broken |
| Viaducts and tunnels need hand-built data | Done once in Phase 0 as data, checked at G0 |
| Spend creep | Per-goal caps in code, quotes, reconciliation, stop and ask |

## 14. Settled before Phase 0

- Plan approved; test area Grund, Pfaffenthal and the Bock.
- Far zoom: exact at normal zoom, gentle simplification far out (small clutter dropped, main streets slightly
  emphasised). Recorded in `research/v2/DECISIONS.md`.
