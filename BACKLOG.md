# Task list, 8 Nov 2026 (owner's request, in this order)
| # | Task | How | Cost | Status |
|---|---|---|---|---|
| T1 | Finish the paid repaints on RunPod (Modal is disabled): the 2 missing spring blocks (b13, b14), the painted-car repair (pilot, then full run, carried into the versions), the Pfaffenthal lift repaint | one pod for everything, deadline watchdog, delete after; then rebuild tiles, recomposite event patches, rebuild occlusion | cap $15 (RunPod balance $24.12) | running |
| T2 | Match the roads to the paintings (no repainting): vehicles and trains must run on the roads and tracks as painted | detect the painted asphalt and rails in the art, fit lanes and tracks to them, use those for driving; debug overlay | free | done (first pass, see below) |
| T3 | Refactoring, performance and tool bugs (time slider, season and event buttons, other controls) | audit, fix every reproducible bug with a test, simplify code, measure before/after | free | queued |
| T4 | Famous statues as a separate layer, no repainting: Gëlle Fra, Grand Duchess Charlotte, William II, Dicks–Lentz, Hämmelsmarsch fountain, Princess Amélie, Wenzel, John the Blind and others | small drawings in the ink style placed on their plinths at their true positions, hidden behind buildings like vehicles, linked to their landmark cards | cap $3 (OpenAI) | queued |

## T2 result (8 Nov)
- **Painter's offset, per block** (`pipeline/fit_roads.py`, kept in `data/work/roadfit/shifts.json`): by edges against
  the render, about (+0.1..+0.4, +6..+8) map px (the LAYERS_POC finding); by the roads themselves (cross-sections
  against painted asphalt, a 2D least-squares fit per block), (+1.0..+4.2, +8.8..+11.8) map px, residual 1-2 px. The
  road measure is used (roads sit about 3 px lower than the buildings say); four mostly unpainted blocks (b05, b07,
  b09, b14) take the median (+2.3, +10.0).
- **Local fit:** every street and track is moved sideways (up to 3 m) onto the painted asphalt and rail beds, found by
  colour per block; junctions stay joined. Output: `q`/`qi` in `lines.json`, `fit` in `transit.json`, `fx`/`fy` in
  `road_heights.json`, masks in `data/roadfit/`. Traffic builds its graph from the OSM lines and drives on `q`.
- **Guard:** a car off the road as painted (a street the painter left out, such as Rue du Fort Olisy on the Hollow
  Tooth cliff) fades out, on top of the drivable guard.
- **Measured** (`node src/sim/roadfit.test.ts 5 0.75`): cars on painted asphalt 79.1% before, 88.5% after the fit; with
  the guard 11% of car samples fade and 99.5% of the drawn ones are on painted road. Trams and trains on the painted
  rail bed 66.6% before, 94.4% after.
- **Look:** `?roaddebug` (masks, OSM lines red, fitted yellow, lanes cyan), `?nofit` (as before). Shots: the `t2-*`
  views in `web/scripts/shots.json`.
- **Re-run** after the day art changes (painted cars repaired) or after `project_lines.py`:
  `cd pipeline && .venv/bin/python fit_roads.py --remeasure` (1-2 minutes, 3.5 GB), then the check above.
- **Open:** the occlusion and drivable maps come from the render, which the painted art is offset from (same
  block offsets): rebuild them shifted for an exact cut; only about a quarter of road sections give a clear local
  match (the rest keep the block offset: hidden, unpainted, under trees); rail beds are hard to tell by colour (grass
  tram tracks on Kirchberg); bridges keep the block offset only; widths still come from `build_drivable.py`.

# Backlog: owner feedback, round 3 (7 Nov 2026)

Raised by the owner after looking at the local build with the whole map painted, the Christmas market, traffic and
the new controls. Each item says what is wrong, the likely cause, the approach, and where it fits. Items marked
"(screenshot)" came with a screenshot that is not stored in the repo yet; find the exact spot again (a share link
with `#x,y,z` is enough) before working on it. Numbers in brackets are the owner's original numbering.

Status key: **new** = not planned yet; **in plan** = already covered by PLAN_NEXT.md (the stream named).

## A. Vehicles, trains and trams

### B1. Vehicles still not exactly on the road [6, 9, 12] — in plan (Stream A, items 2 and 10), extend
- What: cars, trams and trains drift off the drawn roads and tracks; one car drives on a cliff (screenshot), a truck
  wanders off its road (screenshot).
- Likely cause: vehicles follow OpenStreetMap centrelines, but the painted roads are where the image model drew
  them, which can be a few metres off (see B6); lanes are offset by a fixed rule; the drivable-surface guard from
  Stream A item 2 only removes cars it catches, it does not steer them.
- Approach: (1) snap every lane to the road as actually painted: detect asphalt in the painted day art (colour and
  texture, limited to a band around each OSM road), fit a centreline per carriageway, and replace the OSM geometry
  for driving; (2) same for tracks (rails in the art) for trams and trains, building on item 10's matching;
  (3) a hard per-pixel "drivable" test in the simulation so no vehicle can ever stand on a cliff, roof, tree or
  water pixel; (4) a debug overlay (`?roaddebug`) showing painted road vs OSM vs lanes.
- Owner's wish: "a good AI system for them" — this is the planner behind it; keep the IDM following and junction
  logic, improve the geometry they run on.

### B2. Head- and tail-lights wrong when a car faces the viewer [4] — in plan (Stream A item 1), reopen
- What: lights show through the body, both for cars driving away and towards the viewer.
- Approach: lamps belong to the sprite itself: render lit lamp pixels into a second atlas in `build_sprites.py`
  (depth-tested, so only visible lamps exist for each of the 32 headings) and draw that atlas over the body at
  night/braking, instead of drawing lamp shapes in the viewer. Check every heading in the sprite lab.

## B. The painted map

### B3. Visible edges in the map [3, 7] (screenshots) — new, high priority
- What: straight edges visible "in almost all scenarios".
- Likely causes, to check in this order: (a) block borders between the 15 painted blocks (each block was painted
  separately, overlapping by 1,200 px, then pasted with a hard edge); (b) borders of the painted versions where some
  blocks are painted and neighbours are only colour-graded; (c) tile borders from the version builders.
- Approach: (1) find them: run `seam_check.py` over the whole stitched day map and every version, and list edges by
  position; (2) paste blocks with a wide feathered blend across the full 1,200 px overlap instead of a hard edge
  (cheap, no GPU); (3) where colour still differs, repaint a band along the border with mdpaint repair mode (holds
  both sides, repaints a 512 px strip; about $0.10 per border, ~25 borders); (4) re-check after the versions finish.

### B4. Spring trees too bright and vivid [2] — new
- Approach: the spring version is a light-model repaint; tone it with a colour pass limited to tree canopy (desaturate
  and darken foliage greens towards the summer art, keep blossom accents). Free, local. Check against summer and
  autumn side by side in the compare page.

### B5. Red Bridge should be one with the road [14] (screenshot) — new
- What: the bridge deck does not join the road on both ends.
- Approach: repair the two bridge ends with mdpaint repair mode using the render plus a road guide drawn across the
  joint; keep `fix_redbridge_deck.py` (grey deck, red sides). About $0.20.

### B6. Roads not always painted on the real roads [11, 13] (screenshot) — new
- What: some painted roads sit off their real position, or are drawn wrong.
- Approach: measure it: compare detected asphalt in the art with OSM roads (same detector as B1) and list places
  off by more than ~3 m; repair the worst with mdpaint repair mode using the layout map (roads drawn in) as guide.
  Where the art is right and OSM is coarse, B1 makes vehicles follow the art instead.

### B7. Separate layers for ground, buildings and trees — new, design idea (see "Layered art" below) [15, 16]

## C. Interface

### B8. Time slider and season buttons have many bugs [8] — new, high priority
- To do first: reproduce and list every bug (dragging, live mode switching back, season buttons with Christmas,
  date/season mismatch, night cross-fade jumps, test parameters `?hour`/`?season` vs the controls). Then fix in
  `SceneControl.tsx` / `scene.ts` with a small test for each.

## D. Events and life

### B9. Christmas Ferris wheel animation not good [5] — done (Stream B)
- Approach: replace the rotating flat image with a proper wheel drawn in the map's projection (an ellipse in the
  isometric view, gondolas hanging straight down while the rim turns), slow and smooth, lit at night.
- Done: the painted face-on A-frame was taken out of the Constitution drawings (`xmas_v2.py unframe`, a masked
  edit, $0.12), and the whole wheel, supports included, is drawn live by `web/src/components/ferrisWheel.ts`: its
  plane on a map axis, so the rim is a tilted ellipse; 24 gondolas hang from their pins; one turn in 150 s from the
  clock (no frames, so no cross-fade); at night lit rims, spokes and windows.

### B10. Famous statues as separate drawn objects on top [1] — new
- What: monuments are too small or missing in the art (Gëlle Fra, the Grand Duchess Charlotte monument, the
  William II equestrian statue, the Dicks–Lentz monument, the Hämmelsmarsch fountain, Princess Amélie, the
  Wenzel statue, Jean the Blind…).
- Approach: draw each as a small high-detail sprite (OpenAI drawing in the ink style from photos, cut out, a few
  dollars) placed on its plinth at its true position, over the map art, with occlusion like vehicles; link each to its
  landmark card.

### B11. Farm machinery in the right season [10] — new
- What: tractors in spring (ploughing, sowing), combines and harvesters in summer (July–August), tractors with
  trailers in autumn, on the farm fields at the map's edges (Kirchberg plateau, Cents, Hamm).
- Approach: fields from OSM (`landuse=farmland`), vehicles as sprites (box models like the cars), moving in passes
  across the field with a dust trail, only by day, density by date. New feature switch `farming`.

## Layered art: can ground, buildings and trees be painted as separate layers? [15, 16]

Yes, and it would give the control the owner wants (trees per season, buildings cut out for occlusion, roads
editable on their own). The image model paints whole images, not transparent layers, but we have exact masks from
the 3D render, so we can paint each layer separately and cut it out:

1. **Ground layer:** render the city with buildings and bridges hidden (terrain, roads, water, fields only) and paint
   it as today. This is the base everything else sits on. Roads and tracks are drawn here, so B1/B6 become easier.
2. **Building layer:** paint the normal view (as today), then cut buildings out with the render's kind pass (walls
   and roofs), feathered by a pixel. Gives every building its own alpha: no more painted cars or trees inside the
   building layer, and exact occlusion for vehicles.
3. **Tree layer:** trees are not in the 3D model, so take crowns from LiDAR (first-return minus ground, the vegetation
   heights) or OSM/municipal tree data, paint a tree-only pass (trees on a flat neutral background, guided by the
   crown map), and cut out by the crown mask. Seasons then only repaint this layer (spring blossom, autumn colour,
   bare winter trees) — much cheaper, and B4 is solved at the source.
4. **Stack in the viewer:** ground → (vehicles) → trees → buildings, with shadows baked into the layer below.
   Vehicles pass under trees and behind buildings naturally.

Costs and risks: about 2–3x today's painting cost per version (roughly $25–35 for the whole map by day with the fast
painter), the model may draw shadows or edges that don't match between layers (needs a pilot), and the lighting
must stay consistent. Plan: pilot on the old-town block (~$2–3): ground + building + tree layers, compare with today's
single image, then decide.

## Findings from the owner's screenshots (7 Nov, evening)
- **Visible edges (B3):** the straight edges at night in Kirchberg and in spring by Villa Pauly were the borders between
  blocks already painted in that version and blocks still only colour-graded from the day map. Fixed the same evening:
  `build_variant_tiles.py` fades painted blocks over 600 map px. They disappear entirely once every block of a version
  is painted (night: all 15 done; golden hour, winter, winter night, autumn and spring still running).
- **Spring trees (B4):** confirmed, the painted spring canopy is a saturated yellow-green with pink blossom clumps.
- **Red Bridge (B5):** the deck ends at the Kirchberg-side abutment without joining the road above; cars ride on the
  deck up to the edge.
- **Vehicles off the road (B1):** a car on the Hollow Tooth cliff (Bock), cars on the Pfaffenthal rail embankment and on
  bare sand beside the road, and a van parked against a house in Pfaffenthal. All are places where OSM lanes and the
  painted road disagree; the drivable-surface work must use the painted road.
- **Streets layer:** at night a blue outline is drawn round a water polygon near d'Coque that is not visible water;
  only draw water outlines where the water mask has water.

## Order proposed
1. B3 visible edges and B8 slider bugs (most visible, mostly free).
2. Layered-art pilot (decides how B1, B4, B6 and future seasons are done).
3. B1/B2 vehicles on the painted roads (with Stream A).
4. B5 Red Bridge, B6 roads, B4 spring trees.
5. B9 Ferris wheel (before Winterlights, 20 Nov), B10 statues, B11 farming.
