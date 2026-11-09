# v2 Phase 1 report: code layers on the test area

9 November 2026. Branch `v2-phase1`, into `v2`. Spend: **$0** (no GPU rented, no paid API; the vehicle detector ran
on this Mac from the local model cache, offline).

**Gate G1 status: @@STATUS@@**

## 1. What was built

| Part | Where | What it does |
|---|---|---|
| Renderer | `v2/layers/raster.py`, `render.py`, `geometry.py` | Every layer is drawn by casting the view ray through each pixel: the terrain exactly on its bilinear surface (a column scan that also catches crests between samples), triangles and tree crowns with a depth buffer. Draped content (ground, water, the ways on the ground) is looked up in a plan canvas of the tile. |
| Layer 1, ground | `render.Renderer.ground` | 13 OSM land classes by the spec's priority, palette colours, ±3% paper grain fixed per map pixel, 1 px soft ink at class borders. No light. |
| Layer 2, relief | `Renderer.relief` | A multiply layer: form shading from a fixed north-west light (never the sun), exactly 1.0 on ground under 3°, fall-line hatching on steep ground and cliffs, the 331 measured OSM walls as stone faces with an ink top. |
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

The whole test area builds from the scene in about 12 minutes on this laptop (3 worker processes), about 700 MB of
tiles and data under `data/v2/test/` (gitignored).

## 2. Gate G1 checks

@@TABLE@@

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

@@SPEED@@

## 4. How to run it locally

```sh
uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r v2/requirements.txt   # once
export ISOLUX_DATA=/path/to/repo/data
.venv/bin/python -m v2.build test release     # the layers and the viewer's data (~12 min the first time)
.venv/bin/python -m v2.view test              # then open http://localhost:5174/  (needs Node 22+; Ctrl-C stops it)
.venv/bin/python -m v2.build test g1          # every G1 check and the previews (another ~25 min)
```

In the viewer: drag to pan, wheel or pinch to zoom; the panel sets the hour, the season, snow and every layer.
Address parameters for repeatable views: `?hour=16&date=2026-06-21`, `?season=winter&snow`, `?off=trees,buildings`,
`?x=62600&y=34400&z=0.6` (v2 map pixels), `?v1x=&v1y=` (a v1 link), `?debug=layer|shadow|albedo`, `?nosim`.

## 5. Previews (`v2/docs/img/`)

@@PREVIEWS@@

## 6. For the owner

@@OWNER@@
