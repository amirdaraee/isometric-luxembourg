# v2 Phase 1 report: code layers on the test area

9 November 2026. Branch `v2-phase1`, into `v2`. Spend: **$0** (no GPU rented, no paid API; the vehicle detector ran
on this Mac from the local model cache, offline).

**Gate G1 status: passed on the test area.** Every G1 check (#4, #5, #7, #8, #9, seams) passes, every check is a build gate (a failure exits 1), no threshold was changed and no exception was added. Speed was measured on this Mac only.

## 1. What was built

| Part | Where | What it does |
|---|---|---|
| Renderer | `v2/layers/raster.py`, `render.py`, `geometry.py` | Every layer is drawn by casting the view ray through each pixel: the terrain exactly on its bilinear surface (a column scan that also catches crests between samples), triangles and tree crowns with a depth buffer. Draped content (ground, water, the ways on the ground) is looked up in a plan canvas of the tile. |
| Layer 1, ground | `render.Renderer.ground` | 13 OSM land classes by the spec's priority, palette colours, ±3% paper grain fixed per map pixel, 1 px soft ink at class borders. No light. |
| Layer 2, relief | `Renderer.relief` | A multiply layer: form shading from a fixed north-west light (never the sun), exactly 1.0 on ground under 3°, fall-line hatching on steep ground and cliffs, every OSM wall with a measured drop of 1.5 m or more as a stone face with an ink top. |
| Layer 3, water | `Renderer.water` | OSM water flat in the river colour, inked banks; each water area held at the lowest bank level near it (flat between weirs). |
| Layer 4, transport | `Renderer.transport` | Every road, path, step, rail and tram track as a ribbon of its width: on the terrain on the ground, at its profile on decks (bridges, and approaches the profile holds on a structure); casings, lane dashes, rails with sleepers, tram grooves, treads; tunnels not drawn, a dark arch at each portal. A drivable id per pixel. |
| Layers 5-7, placeholders | `Renderer.buildings`, `structures`, `trees` | **Not the art** (that is the bake-off's). Plain, evenly lit code: ACT LoD2 buildings in flat palette colours with straight outlines on every plane edge and the facade layout's windows, doors and shop fronts; bridge sides, parapets, the three viaducts' slab, arches and piers, the lift; every surveyed tree as a flat-coloured crown of its measured size on a trunk. No baked light or shadow anywhere. |
| Layer 8, buffers | `stages.layer_buffers` | Depth, normal, height above the terrain, object id + class and the nearest layer, per pixel. |
| Layer 9, light | `light.py`, viewer `gl/shaders.ts` | A shadow height map (0.5 m, by source: terrain, buildings, crowns and structures with their undersides) marched towards the sun's real position (NOAA, `sun.ts` = `sun.py`) in the viewer; Lambert shading from the normals; tinted, never black shadows; a sky grade for golden hour, blue hour and night. |
| Layer 10, night | `data.night_data`, viewer | 19,727 windows, doors and shop fronts facing the camera, lit by hour and use (seeded per window, a family's floor together), 108 OSM street lamps with glow; all depth-tested. Nothing lit with the sun up. |
| Layer 11, seasons | viewer | Spring, summer, autumn and winter colour the crowns and green ground only; winter crowns go bare; snow on up-facing surfaces not under a crown, deck or roof (`?snow`). |
| Layer 12, vehicles | `v2/web/src/sim/traffic.ts`, `transit.ts`, `vehicles.ts` | v1's traffic simulation and transit kept (changes marked `v2:`), fed the v2 graph's roads in the plan; every car takes its road's height profile, across a junction box from one road's height to the next; trams and trains run the GTFS timetable on their matched runs (2,663 trip runs) at their track's profile. Boxes in the G-buffer, depth-tested per pixel. |
| Layer 14, look | viewer | Grade as a projection (channels clamped, saturation capped: applying it twice changes nothing) and ink from depth steps and creases of the geometry, never from colour. |
| Layer 15, labels | `data.labels_data`, `labels.ts` | 400 labels (landmarks, places, quarters, streets) decluttered by priority and zoom, hidden behind nearer surfaces (layer 8 on the CPU); hover names what is under the pointer. |
| Far zoom | `stages.layer_far` | From zoom 2 out, the colour layers merged by depth into one tile set (tiles-hosting.md "Far zoom", decided here by measurement: zoom 2); used only while every colour layer is on. |
| Compositor | `v2/web/src/gl/compositor.ts`, `shaders.ts` | WebGL2: G-buffer of the layers by their own depth (ties to the later layer), vehicles, light pass, night pass, look pass; draws on change; falls back to a coarser tile while one loads; any layer off with `?off=`. |
| Tiles | `common.py`, `tiles.py` | 512 px tiles numbered in the commune's frame; colour WebP; depth stored against a per-row plane (√3·sy) in 16-bit cm so it fits at every zoom; octahedral normals; data tiles row-delta + zlib, decoded exactly in the browser. Pyramid by the nearest surface. |
| Build stages | `v2/build/stages.py` `phase1()` | `layer_*`, `release`, seven check stages and the `g1` report; each output keyed by code, parameters, palette, light config and inputs. |
| Viewer server | `python -m v2.view test` | Serves the current release with the viewer (section 4). |

The whole test area builds from the scene in about 8 minutes on this laptop (3 worker processes), about 570 MB of
tiles and data under `data/v2/test/` (gitignored).

## 2. Gate G1 checks

| Brief | Check | Result |
|---|---|---|
| #4 Layers independent | 504 re-renders without each other layer's inputs identical; in the viewer every layer off leaves 0 pixels and casts no shadow | **pass** |
| #5 No baked shadows | 0 of 349 materials differ in the photo-sun's shadow by > 5%; ground classes north vs south slopes 0.06% (≤ 2%); shadow direction error 7.7° / 9.8° / 7.6° at 08, 13, 19 h (≤ 10°); viewer shadows = reference 98.7-99.6%, move with `?hour` (43% of pixels change 10 h → 16 h) | **pass** |
| #7 Roads and rails match | 100% of 63,132 centre-line samples inside the drawn surface; cars on drawn road 99.94% (≥ 99.5%), trams and trains on track 100% | **pass** |
| #8 Tunnels and bridges | 0 vehicle pixels inside tunnels past portals (5,628 samples); 0 disagreements of 12.5 M probe pixels at 39 portals, 30 bridges, 40 under-crossings; largest height step between frames 0.33 m cars, 0.05 m trains (≤ 0.5) | **pass** |
| #9 No painted cars | OWLv2: 0 detections ≥ 0.1 on 979 colour tiles of 7 layers (highest score of any box 0.14, all outside the 3-14 m vehicle size) | **pass** |
| Seams | largest step at a tile border vs a render across it: 2.8 ΔE (≤ 3); depth steps at borders = those inside tiles (ratio 1.05) | **pass** |
| Speed | first view 0.10 s warm / 0.15 s cold; pan 95-120 fps (desktop) | **pass** (desktop); phone not measured |

All 49 build stages pass (`python -m v2.build test g1`, exit 0), including the 12 G0 data checks re-run. Full results:
`v2/docs/results/g1_test.json`.

<details><summary>Every numbered entry</summary>

**#4 layers** (`check_independence`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| C1a | layer tiles that change when another layer's inputs are removed (504 renders, 12 tiles x 7 layers x 6 others) | 0 | <= 0 | pass |
| C1b | built tiles whose geometry differs from the renderer's | 0 | <= 0 | pass |
| C1c | mean colour difference of a built tile from the renderer (lossy WebP q90 coding) | 2.97 | <= 3.0 | pass |
| C1d | layer off in the viewer: no pixel of it, no shadow of it (check_viewer V1, V2) | see check_viewer |  | info |

**#5 no baked shadows** (`check_shadows`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| L9.0 | the released shadow height map is the scene's | None |  | pass |
| L5.1/L9.2 | materials darker or lighter in the 3D shadow of the photo's sun (2024-06-15T11:00:00+02:00) than lit next to it by > 5% (median luminance inside surfaces; of 349 compared) | 0 | <= 0 | pass |
| L5.1b | worst relative difference by layer | ground: 0.003, buildings: 0.0104, water: 0.0, structures: 0.0132, transport: 0.0129 |  | info |
| L9.1-08 | shadow direction vs the sun at 08:00 on 2026-06-21 (az 78.3, el 21.3): median angle error over 863 buildings (deg; 90th pct 23.1) | 7.71 | <= 10.0 | pass |
| L9.1-13 | shadow direction vs the sun at 13:00 on 2026-06-21 (az 161.0, el 62.8): median angle error over 435 buildings (deg; 90th pct 43.4) | 9.82 | <= 10.0 | pass |
| L9.1-19 | shadow direction vs the sun at 19:00 on 2026-06-21 (az 279.1, el 23.6): median angle error over 836 buildings (deg; 90th pct 25.2) | 7.63 | <= 10.0 | pass |
| L2.3 | the relief layer is identical for a morning and an evening sun | None |  | pass |

**#7 roads (L4.x) and the layers' own checks** (`check_layers`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| L1.1 | ground pixels of the area without a class (of 50443085) | 0 | <= 0 | pass |
| L1.2 | no shading: worst relative luminance difference of a ground class, north vs south slopes | 0.0004 | <= 0.02 | pass |
| L2.1 | flat ground changed by the relief (of 13027164 flat pixels) | 0 | <= 0 | pass |
| L8.1 | pixels where a layer's depth differs from layer 8's by > 1.0 cm (of 51217481) | 0 | <= 0 | pass |
| L8.2 | normals not unit or facing away from the camera (of 51217481) | 0 | <= 0 | pass |
| L8.3 | ids not in the scene | 0 | <= 0 | pass |
| L8.3b | buildings with at least one pixel in layer 8 | 1099 of 1135 |  | info |
| L2.2 | walls (drop >= 1.5 m, in the area, in view) drawn along < 90% of their visible length (of 331) | 0 | <= 0 | pass |
| L3.1 | OSM water pixels not drawn as water, and water pixels outside OSM water (+- 1 px; 1467950 water pixels) | 0 | <= 0 | pass |
| L4.1 | road, rail and tram centre-line samples (every 0.5 m) inside the drawn surface (of 63132; 4183 behind the terrain; 183 within 1 px of the surface's edge) | 1.0 | >= 1.0 | pass |
| L4.3 | drawn pixels of tunnel ways (portals are drawn, tunnels are not) | 0 | <= 0 | pass |
| P-1 | colour literals in the layer code (every colour comes from palette.json) | 0 | <= 0 | pass |

**#7, #8 vehicles, tunnels, bridges** (`check_vehicles`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| V0 | audit: samples over a simulated day | car_samples: 901179, transit_samples: 30106, every_s: 20, audit_s: 84.6 |  | info |
| V0b | vehicle samples in the area behind the terrain (not in view) | 21979 |  | info |
| V0c | vehicle samples under another way's deck (not in view) | 3096 |  | info |
| L4.2 | car samples on drawn road (of 558942 in the area, out of tunnels) | 0.9994 | >= 0.995 | pass |
| L12.4 | tram and train samples on drawn track (of 18860) | 1.0 | >= 0.995 | pass |
| L12.3 | share of car samples the v1 fade guard would act on (off the drawn road) | 0.0006 | <= 0.001 | pass |
| L12.1a | vehicle pixels drawn inside tunnels past their portals (5628 samples in tunnels) | 0 | <= 0 | pass |
| C4a | probed: tunnel portals, bridge edges, ways under a deck; probe vehicles | portals: 39, bridges: 30, under_crossings: 40, probes: 3262 |  | info |
| C4 | probe pixels where the viewer's depth test disagrees with the exact geometry (of 12516108; 1793 more on silhouettes, within 1 px of an edge) | 0 | <= 0 | pass |
| C4b | share of probe pixels on silhouettes (edge rounding) | 0.0001 | <= 0.01 | pass |
| C4c | probe pixels hidden (under decks or past portals) | deck_and_under: 1552760, portals: 2117473 |  | info |
| L12.2a | largest height change of a car between two frames (m; 34309718 car-frames) | 0.332 | <= 0.5 | pass |
| L12.2b | largest height change of a tram or train section between frames (m; 29546655) | 0.046 | <= 0.5 | pass |
| V9 | seconds | 229.5 |  | info |

**#9 no painted cars** (`check_no_cars`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| D0 | detector | model: google/owlv2-base-patch16-ensemble, device: mps, images: 979, seconds: 381.5, queries: ['a car', 'a parked car',  |  | info |
| D-ground | ground: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D-relief | relief: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D-water | water: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D-transport | transport: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D-buildings | buildings: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D-structures | structures: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D-trees | trees: detections >= 0.1 of a vehicle 3.0-14.0 m long | 0 | <= 0 | pass |
| D9 | highest score of any query on any tile (below the threshold) | 0.1428 |  | info |

**seams** (`check_seams`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| S-ground | ground: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 375 chunks) | 2.477 | <= 3.0 | pass |
| S-ground-v1 | ground: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 3073 | borders: 18, middles: 6.0 |  | info |
| S-relief | relief: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 350 chunks) | 0.0 | <= 3.0 | pass |
| S-relief-v1 | relief: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 3077 | borders: 14, middles: 7.0 |  | info |
| S-water | water: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 66 chunks) | 1.502 | <= 3.0 | pass |
| S-water-v1 | water: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 38 | borders: 0, middles: 0.0 |  | info |
| S-transport | transport: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 55 chunks) | 2.21 | <= 3.0 | pass |
| S-transport-v1 | transport: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 100 | borders: 0, middles: 0.0 |  | info |
| S-buildings | buildings: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 187 chunks) | 1.295 | <= 3.0 | pass |
| S-buildings-v1 | buildings: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 741 | borders: 10, middles: 3.0 |  | info |
| S-structures | structures: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 16 chunks) | 1.209 | <= 3.0 | pass |
| S-structures-v1 | structures: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 54 | borders: 3, middles: 0.0 |  | info |
| S-trees | trees: largest LAB step of a 64 x 4 px band beside a border (its mean colour), built tiles vs one render across the border (24 borders, 82 chunks) | 2.804 | <= 3.0 | pass |
| S-trees-v1 | trees: v1's seam rule, flagged chunks at the borders and (control) through the tiles' middles, of 136 | borders: 0, middles: 0.0 |  | info |
| L8.4 | depth: share of border pixels with a step on one surface, over the share across the tiles' middle lines (1435 of 193055 vs 1338 of 188348; a seam would make it larger) | 1.046 | <= 1.5 | pass |

**#4, #5 in the viewer; speed** (`check_viewer`: PASS)

| Id | Check | Value | Threshold | |
|---|---|---|---|---|
| V0 | browser and GPU | renderer: ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version), ua: Mozilla/5.0 (Macintosh; Intel Mac  |  | info |
| V0b | page errors | 0 | <= 0 | pass |
| V1-ground | ?off=ground: pixels still showing layer ground | 0 | <= 0 | pass |
| V1-relief | ?off=relief: pixels still showing layer relief | 0 | <= 0 | pass |
| V1-water | ?off=water: pixels still showing layer water | 0 | <= 0 | pass |
| V1-transport | ?off=transport: pixels still showing layer transport | 0 | <= 0 | pass |
| V1-buildings | ?off=buildings: pixels still showing layer buildings | 0 | <= 0 | pass |
| V1-structures | ?off=structures: pixels still showing layer structures | 0 | <= 0 | pass |
| V1-trees | ?off=trees: pixels still showing layer trees | 0 | <= 0 | pass |
| V3-10 | shadows at 10:00 on 2026-06-21 match the Python reference (share of pixels; 16.9% in shadow) | 0.9872 | >= 0.97 | pass |
| V3-16 | shadows at 16:00 on 2026-06-21 match the Python reference (share of pixels; 34.7% in shadow) | 0.9768 | >= 0.97 | pass |
| V3-13 | shadows at 13:00 on 2026-06-21 match the Python reference (share of pixels; 10.1% in shadow) | 0.9962 | >= 0.97 | pass |
| V2 | ?off=buildings: the viewer's shadows equal the reference without buildings (share of pixels) | 0.9891 | >= 0.97 | pass |
| V3b | share of pixels whose shadow changes between 10:00 and 16:00 (shadows move with ?hour) | 0.4296 | >= 0.02 | pass |
| V4 | pixels changed by the night layer at 13:00 (no light by day, L10.2) | 0 | <= 0 | pass |
| V5 | pixels changed by the season outside the tree and green-ground masks (L11.1) | 0 | <= 0 | pass |
| V6 | overlapping labels at the reference views (L15.2) | 0 | <= 0 | pass |
| V7 | the look pass applied again to the viewer's output: largest channel change (L14.1, in 1/255) | 1 | <= 1 | pass |
| C2 | speed (desktop, this machine's GPU) | first_view_cold_s: 0.149, first_view_warm_s: 0.09630000001192093, pan_fps: 94.74763130935845, viewport: 1600x1000 CSS px |  | info |
| C2a | first view, warm (s) | 0.096 | <= 0.5 | pass |
| C2b | panning, desktop (frames per second, all layers on, vehicles moving) | 94.7 | >= 60 | pass |
| C2c | mid phone: not measured on a device (see the report); 4x CPU throttle | cpu_slowdown: 4 |  | info |

G0 data checks re-run on the same build: check_scope pass, check_terrain pass, check_buildings pass, check_facades pass, check_trees pass, check_transport_profiles pass, check_transport_graph pass, check_structures pass, check_transit pass, check_places pass, check_no_patching pass, check_ledger pass

</details>


Exceptions: none were needed; `v2/data/exceptions.json` is unchanged. No threshold was changed.

How some checks are measured (they are new; please look at these choices):
- **#4 layers.** Two halves. Offline: every colour layer is re-rendered on 12 tiles with each other layer's own inputs
  removed (504 renders) and must be identical, and the built tiles must be the renderer's. In the viewer: with any
  layer off no pixel of it remains, and it casts no shadow (the viewer's shadows then equal the reference without it).
- **#5 no baked shadows.** The shadow detector takes the 3D shadow (and the faces turned away from the sun) of the
  orthophoto's sun (15 June 2024, 11:00) and compares, per material (a ground class; one object and its class), the
  median luminance inside surfaces in shadow with the same material lit next to it: within 5%. Ink lines at surface
  edges are left out (they are the drawing, not light). Shadows move with `?hour`: the cast-shadow direction matches
  the sun's azimuth within 10° (median over buildings) at 08:00, 13:00 and 19:00 on 21 June, and the viewer's shadows
  match the Python reference pixel for pixel (≥ 97%) at 10:00, 13:00 and 16:00.
- **#7 roads and rails.** Centre lines inside the drawn surface to the pixel (183 of 63,000 samples needed the
  pixel next to them, on a surface's edge); vehicles over a simulated day (every 20 s, 0.9 M car samples) on drawn
  road. Samples hidden behind a hill or under another way's deck are not counted as on or off the road (they are
  not in view; C4 checks their hiding).
- **#8 tunnels and bridges.** Every vehicle sample inside a tunnel past its portal draws no pixel; 3,262 probe
  vehicles at all 39 portals, 30 bridge edges and 40 ways passing under a deck: the viewer's depth test against
  layer 8's tiles must say exactly what the scene's geometry rendered at full precision says, pixel by pixel (the
  1 in 10,000 pixels on an edge, where rounding decides, are counted apart). Heights between frames (1/30 s) for
  every car over a busy hour and every tram and train section over the day.
- **#9 no painted cars.** v1's OWLv2 detector (google/owlv2-base-patch16-ensemble, from the local cache, offline, on
  the Mac's GPU) on every colour tile of every layer, at v1's scale (a car about 60 px at the model's input), boxes of
  3-14 m: none at ≥ 0.1.
- **Seams.** v1's seam rule on every border between tiles, against the same rule on lines through the tiles' middles
  (v1's control run): a seam would make the borders worse than the middles. Depth: steps across borders against
  steps across the middle lines.

## 3. Speed

Measured by `check_viewer` with headless Chromium 145 on this Mac (Apple M2 Pro GPU through ANGLE/Metal), the
viewer served by the local dev server, 1600 x 1000 px, all layers on, vehicles moving:

| | Result | Target |
|---|---|---|
| First view, cold (empty cache) | 0.15 s | < 0.5 s (mid phone) |
| First view, warm | 0.10 s | |
| Panning, whole test area (far-zoom set) | 120 fps (the headless frame cap) | 60 fps desktop |
| Panning at 1:1 (all seven layers, 80+ textures) | 95 fps | 60 fps desktop |
| One full frame on the GPU (all passes, blocking) | 0.2-0.4 ms | 4 + 3 ms on a mid phone (L9.3, L14.3) |
| Panning at 1:1 with the CPU slowed 4x | 120 fps | 30 fps mid phone |

Before the far-zoom set the first view took 0.54 s (315 tile requests through HTTP/1.1); merging layers 1-7 from
zoom 2 out brought it to 0.10 s. **Not measured:** a real mid-range phone, and loading from R2 over HTTP/2. The CPU
throttle does not slow the GPU, so it says little about a phone. The shadow height map (12.8 MB for the test area)
loads after the first view; shadows appear a moment later.

## 4. How to run it locally

```sh
uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r v2/requirements.txt   # once
export ISOLUX_DATA=/path/to/repo/data
.venv/bin/python -m v2.build test release     # the layers and the viewer's data (~10 min the first time)
.venv/bin/python -m v2.view test              # then open http://localhost:5174/  (needs Node 22+; Ctrl-C stops it)
.venv/bin/python -m v2.build test g1          # every G1 check and the previews (another ~35 min)
```

In the viewer: drag to pan, wheel or pinch to zoom; the panel sets the hour, the season, snow and every layer.
Address parameters for repeatable views: `?hour=16&date=2026-06-21`, `?season=winter&snow`, `?off=trees,buildings`,
`?x=62600&y=34400&z=0.6` (v2 map pixels), `?v1x=&v1y=` (a v1 link), `?debug=layer|shadow|albedo`, `?nosim`.

## 5. Previews (`v2/docs/img/`)

All are screenshots of the viewer itself (code lighting), JPEGs under 1 MB.

| Image | Shows |
|---|---|
| `test_g1_day_1300.jpg` | the whole test area, 24 June 13:00 |
| `test_g1_golden_hour.jpg` | the same at 21:19 (sun 3° up) |
| `test_g1_night.jpg`, `test_g1_night_grund.jpg` | 23:15: the area, and the Grund close up with lit windows and street lamps |
| `test_g1_shadows_1000.jpg`, `test_g1_shadows_1600.jpg`, `test_g1_shadows_pair.jpg` | the Grund at 10:00 and 16:00: the shadows move with the sun |
| `test_g1_portal_vehicles.jpg` | a train leaving the main line's tunnel north of the station, cut by the hillside at the portal; cars on the road |
| `test_g1_viaduct_vehicles.jpg` | a train on the Pulvermühl viaduct (the timetabled 8:06 service) |
| `test_g1_layer_toggles.jpg` | one view six ways: all layers; light off (the layers' own, unshadowed colour); buildings off (their shadows go too); trees off; only ground, relief and water; the nearest layer per pixel |

## 6. For the owner

**Open questions**
1. **The placeholders are not the art.** Layers 5-7 are plain code so the light, shadows and vehicle checks have real
   geometry; the bake-off replaces them. The trees in particular look like lollipops: the LiDAR crown radii (×0.85,
   thinned near buildings) are narrow for their measured heights, so trunks show. Fine for G1?
2. **Phone speed** has not been measured on a device (only this Mac, plus a CPU throttle). Can you open the viewer on
   your phone (same Wi-Fi: start it with `npx vite --host` in `v2/web`), or should that wait for R2 hosting (Phase 5)?
3. **New check methods to approve** (thresholds are the specs', the measuring is new):
   - seams compare the built tiles with one render across the border (v1's statistical seam rule flags straight
     content edges along borders as often as along tile middles; it is still reported);
   - the shadow detector uses each material's median luminance inside its surfaces (ink lines at edges left out);
   - vehicles hidden behind a hill or under a deck are not counted on or off the road (C4 checks they are hidden);
   - L4.1 accepts the pixel next to a centre line on a surface's edge (183 of 63,132 samples);
   - L14.1 "the look applied twice changes nothing": the grade is a projection and ink a fixed colour, measured on
     the viewer's own output (largest change 1/255).
4. **Approaches drawn as decks.** A way not tagged bridge whose profile runs more than 1 m above the terrain (the
   graph found 83 m of such approaches in Phase 0) is drawn at its profile, like a bridge deck. Agree?
5. **Far zoom from zoom 2** (tiles-hosting.md asked for this to be decided at G1): one merged colour set from zoom 2
   out while every layer is on; with a layer switched off the viewer falls back to the per-layer tiles.
6. **Navigation** is the viewer's own (drag, wheel, pinch, `?x=&y=&z=`, v1 links with `?v1x=&v1y=`) instead of
   OpenSeadragon: OpenSeadragon draws into its own canvas and cannot feed the compositor's depth buffer.

**Still open from G0:** viaduct arch counts, the funicular timetable (no funicular trips matched the graph in the
test area's GTFS), R2, the GTFS licence version.

**Known limits (nothing fails):**
- The terrain at 0.5 m is rounded at sharp cliff edges; OSM walls are drawn as faces on top of it.
- The shadow height map is one 0.5 m texture for the test area; the commune needs it tiled (Phase 4).
- Shadows of 2.5D: light passes under crowns, decks and arches (their undersides are stored), but not through
  windows or between a dormer and its roof.
- Code night (G3 compares it with a painted night): windows lit by a seeded rule (homes in the evening, shops until
  20:00), 108 OSM street lamps.
- 1,099 of 1,135 buildings have a visible pixel; the rest are hidden behind others from this camera.
- The release is about 570 MB on disk for the test area (`data/v2/test`, gitignored); tiles are WebP colour and
  zlib data, not yet sized for R2.
