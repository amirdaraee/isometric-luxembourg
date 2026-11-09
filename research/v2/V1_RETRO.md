# Isometric Luxembourg v1: retrospective

Written 9 Nov 2026, to found a clean v2. Sources: README, PLAN, PLAN_NEXT, ROADMAP, BACKLOG, LAYERS_POC,
`pipeline/gpu_train/NOTES.md` and `RETRAIN_PLAN.md`, `research/`, CONTRIBUTING, the git log (115 commits, 7 to 8
Nov; everything from 5 to 7 Nov is squashed into the first commit `ca1b93a`), the spend logs in `data/work/`, the
paint-run logs in `data/work/city/`, the layered proof-of-concept status page (`web/public/poc/status.json`), and the
owner's session notes in memory.

## 1. Summary

v1 took about four days (5 to 8 Nov 2026). It made a good viewer and a painted map that looks right, but **the
painting was the only source of truth for everything you can see, and nothing in it was tied to the data.** The
image model was asked to paint everything in one image: ground, roads, buildings, trees, light and shadow. Then
every live layer (cars, trams, light, seasons, events) had to be fitted onto that picture after it was made. Most of
v1's problems come from this one decision:

| Symptom | Common cause |
|---|---|
| Shadows baked in, wrong at other hours | light was painted into the one image |
| Wobbly windows and lines | geometry was left to a diffusion model working below its own resolution |
| Roads and tracks off the data; T2/T2b warping | the painter moves things (6.8 px down, up to 2 m locally) and nothing stops it |
| Cars painted in, then repainted out | the input photo had cars, and the model and teachers added more |
| Tunnels and bridges break vehicles | there is no depth in a flat painting; occlusion was guessed from masks |
| Seams between blocks and versions | each block and version is a separate generation |
| Seasons and events drift, patches redone | each version is a full repaint of the full picture |

The result: of the 28 feature switches, **v1 ships with traffic, transit, seasons, events, statues, weather and
planes all switched off** (`web/.env.production`), because they don't sit well on the art. Most of the work on
"life on the map" is built but not shipped.

The **layered proof of concept** (LAYERS_POC.md, 7 Nov evening, old-town block b00, $2.23) showed the way out:
painted ground, buildings cut out by the 3D outline, trees painted from a LiDAR canopy, and exact ink lines in code,
with **0 pixels crossing their area** in automatic checks. It came after the whole city and six versions had been
painted, so v1 shipped the single-image map and fitted the data to it instead (T2b).

**Spend that we know of:** OpenAI $37.31 (600 calls, `openai_spend.json`); Modal about $71 metered for the month
(`modal billing summary` in the run logs; only $0.26 of it is in `modal_spend.json`); RunPod $10.36 for the T1
session plus the training runs (about $2.50 for run 1, about $9 for the full style run, and the v2 and light runs,
which aren't logged), so **roughly $130 to $150 in total**, against the plans' "about $10" for the city by day and a
$60 cap for the versions.

## 2. The problems, one by one

Each entry gives: what happened (evidence), the root cause, what we tried, the cost, and **v2: a principle and an
acceptance test**.

### P1. Shadows baked into the paintings
- **What:** the day art has deep shadows cast from the upper left. Golden hour and night are separately painted
  versions that the viewer cross-fades between (`sceneMix` in `App.tsx`), so at 08:00 and at 13:00 the shadows fall
  the same way. The layered POC's moving shadows didn't help either: "the painted buildings still carry their own
  painted light, so at evening the walls do not darken" (`status.json`, step 5).
- **Root cause:** shadows came from three places, and all three were asked for or allowed:
  1. The style brief asks for them: "Deep, dark, flat shadows cast from the upper left" (`INK`/`INK2` in
     `pipeline/style/draw_openai.py`). The LoRA learned this from 100 teacher drawings.
  2. The input is a render of textured CityGML on terrain draped with the 2023 orthophoto. The photo has its own
     real shadows, and the painter copies them ("the painted ground carries the photo's own shadows", POC V2.6).
  3. The decision of 5 Nov: "Daytime shadows stay in the art. Night is a separate layer" (ROADMAP, "What the base
     art leaves out"). The plan to fix this, a shadow mask from the 3D model at the photo's sun position to lift
     baked shadows, was written down but never built.
- **Tried:** night painted "with no sun shadows" by the light LoRA (this works for night only); a code shadow layer
  in the POC (it moves, but the buildings' own shading doesn't).
- **Cost:** structural. Moving light was never possible on v1 art.
- **v2 principle:** **light is a layer, not paint.** Paint albedo only: flat, shadow-free colour from ambient light.
  Shading and cast shadows come from the 3D model and the sun position in code (a normal or shading buffer plus a
  shadow map), or are painted as separate light passes that are combined at run time.
- **Acceptance test:** render the same tile at 08:00, 13:00 and 19:00. The shadow direction measured from building
  edges must match the sun azimuth within 10 degrees. On the albedo layer, the mean brightness of the 3D shadow mask
  at the photo's sun must be within 5% of the lit ground next to it (no ghost shadows).

### P2. Wobbly windows and straight lines
- **What:** I4 (open since 6 Nov): "windows are warped and facade lines aren't parallel", "buildings go soft at full
  zoom". RETRAIN_PLAN set a "line score" target, but no line score was ever coded (it appears only in
  `RETRAIN_PLAN.md`).
- **Root cause:**
  1. **Scale is below what the model can resolve.** The day map is painted at `src_cell 600`, about 0.29 m per
     model px (`mdpaint.py`), then stretched to the 0.25 m/px map. Qwen's VAE latent cell is 8 px, about 2.3 m. A
     window (about 1.2 m) is smaller than one latent cell, so the model can't place it. It can only suggest it.
  2. **The input is blurry:** the CityGML facade textures are low-resolution, stretched photos.
  3. **The v1 brief said "Do not tidy, straighten, regularise"** (`INK`), so the first LoRA learned to keep the wobble.
     `INK2` added "walls straight... windows in regular rows", and the v2 LoRA got a layout map with a line guide
     (`layout.py`: edges black, windows dark). But that is a soft hint, and the diffusion model has no hard
     geometric constraint.
  4. The v2 LoRA in use is the **step-2000 checkpoint of a planned 3,500**: the pod stopped at step 2019
     (`lora_v2/pull.log`, "pod gone 03:45 7 Nov"). RETRAIN_PLAN's checkpoint comparison (2000/2500/3000/3500) never
     happened. `paint_city.py` hard-codes `luxembourg-ink-v2_000002000`.
- **Tried:** the INK2 brief and the layout map with the line guide (helped somewhat). The finer-scale test (450/300
  src px) was planned in Phase 2 and never run.
- **v2 principle:** **geometry comes from code, not from the model.** Building edges, eaves, ridges and window grids
  are drawn (or used as a hard mask) from the 3D model at full resolution. The model adds material and texture
  within a structure it can't move. Paint at a scale where the smallest thing that must be straight covers at least
  two latent cells (in practice 0.1 to 0.125 m per model px for facades), or paint facades as separate rectified
  textures.
- **Acceptance test:** an automatic line score. Take the 3D model's projected edges in a band of ±2 px. On 20 fixed
  test buildings, at least 90% of the painted strong edges must fall inside the band, and the straight-line fit
  residual on long eaves must be 1 px or less. The test runs on every pilot before any paid run gets bigger.

### P3. Painted roads, rails and tram tracks don't match the data
- **What:** B1 and B6 (owner round 3, with screenshots): a car on the Hollow Tooth cliff, cars on the Pfaffenthal
  embankment, trains off the rails. T2: 79.1% of cars on painted asphalt before the fit. Trams and trains on the
  painted bed: 66.6%.
- **Root cause:**
  1. **The painter moves the picture.** It shifts the whole output about 6.8 px (1.7 m) down. This was found only
     during the layers POC on the evening of 7 Nov, after the city was painted (`status.json`, step 2). It also
     redraws some streets up to 2 m from the ground around them, and the ground sits about 1.5 px lower than the
     roofs (T2b result).
  2. **The vehicles come from a different source than the paint:** OSM centrelines with a fixed lane rule. The
     paint follows the photo plus a soft hint of OSM. The two only agree as far as the model chooses to agree.
  3. GTFS rail shapes are coarse straight lines (PLAN_NEXT item 10).
- **Tried:** A3, map-matching GTFS onto the OSM rails (good, keep it). T2, block offsets plus a sideways colour fit
  of up to 3 m, which gave 88.5% of cars on asphalt. T2b, a dense NCC flow field that warps lines, drivable map,
  occluders and decks onto the painting (`flow_field.py`, `flowfield.py`, `fit_to_art.py`; about 50 min, 4.7 GB, to
  be re-run after every repaint), which gave 94.7% of cars and 93.3% of trains. **The 97% target was not reached.**
  `roadfit.test.ts` defaults to `--min 98`, and CONTRIBUTING lowers it to 95.
- **Why it only partly worked:** it fixes the symptom (data follows the paint) and makes the data wrong, warping
  correct OSM geometry onto a painting's mistakes. It must be redone after every repaint. It can't help where the
  painter covered a street with a house, a tree or a cliff.
- **Cost:** about 1 day of work (T2 plus T2b), and an extra 50-minute step after every repaint, for good.
- **v2 principle:** **the data is the truth, and the art is made to fit it, never the other way round.** Roads,
  rails, tram tracks and water edges are drawn from data in their own layer (as POC V2.2), or held fixed as known
  pixels while painting. Correct the painter's systematic offset at the source (measure it once per model and
  undo it in `mdpaint`).
- **Acceptance test:** after painting, the flow-field residual between the render and the painting is 0.5 px
  (median) or less on every block, and no correction is applied downstream. Cars on painted road reach 99% or more,
  and trains on the painted bed reach 99% or more, with **no fitting step**. `fit_to_art.py` must not exist in v2.

### P4. Tunnels, bridges and occlusion break the vehicles
- **What:** item 9 ("trains don't go under bridges and tunnels"), item 2 (cars inside trees, the river and
  facades), B2 (lights showing through the car body), "cars on rooftops" (fixed in 1.0 with a visibility mask).
  Overlay.tsx is the second most changed file (18 commits).
- **Root cause:** the map is a flat picture with no depth. Vehicles are 2D sprites drawn over it. Hiding was
  rebuilt from approximations:
  - `visibility.png` at 2 m, binary;
  - `occluders.png` at 1 m, with a few fixed cut heights (1.6, 3.2 and 4.5 m);
  - a canopy found by colour on a half-resolution image;
  - tunnel portals from OSM ways that don't meet the painted portal;
  - bridge decks interpolated straight where `road_heights.json` had no profile.

  On top of that, the painting is offset from the render all these masks come from (P3), so every cut was off by
  1 to 3 m until T2b warped the occluders.
- **Tried:** tiled occluders with a soft canopy channel (A6, A2), deck lift and tunnel clipping (A4), a drivable map
  and a runtime fade guard, a lamp atlas. Each fixed a class of cases. The guard hides cars it can't place (1.4% to
  11% of car samples were faded).
- **v2 principle:** **depth comes with the art.** Every painted layer ships with a per-pixel height or depth buffer
  from the same 3D render, aligned exactly because the art is held to the geometry (P3). Vehicles are depth-tested
  per pixel against it, not cut at fixed thresholds. Tunnels and decks are part of the network data (a z per
  vertex), not guessed in the viewer.
- **Acceptance test:** a headless audit over a simulated day. 0 vehicle pixels drawn over a nearer surface. 0
  sections drawn inside a tunnel. Every deck section lifted. The fade guard is never needed (fewer than 0.1% of
  samples).

### P5. Cars (and other moving things) painted into the art
- **What:** I6 and item 4: "I can see cars painted in the art". 1,000 painted car spots were found
  (`find_vehicles.py`, OWLv2). The repaint (T1) removed lone cars only. **About 560 of the 1,000 spots, in dense car
  parks, still have their painted cars** (PLAN_NEXT item 4 status). All six versions copied the cars from the day
  art.
- **Root cause:**
  1. The input render is draped with an orthophoto full of parked and moving cars. `make_hint.py` removed only
     compact blobs inside OSM buffers, so it missed dark cars, rows of cars and car parks missing from OSM.
  2. The model invents small cars on station roads (NOTES.md: "a few tiny cars drawn on station roads").
  3. The other briefs in `draw_openai.py` (`PROMPT`, `BLEND`) say "Only a few small cars on existing roads". The
     chosen INK brief forbids cars, but this shows the rule was not enforced as a check on the training set.
  4. Versions are derived from the day art, so any defect spreads to every version.
- **Tried:** a free Poisson fill (smears in car parks); the painter's repair with tight masks (good for lone cars;
  in car parks it redraws a blank wall or a road); `--init-from` at strength 0.5 and 0.65 (blocky); carrying the
  fix into the versions by colour transfer (winter and night look slightly flat).
- **Cost:** $4.54 of jobs inside a $10.36 pod session, plus about 0.5 day of detection and review. Still not done.
- **v2 principle:** **clean the input, not the output.** Build the input from data with nothing that moves in it:
  ground from the orthophoto with vehicles removed (detect on the photo, where cars are easy to see), or code-drawn
  car parks with empty bays. Each layer is painted on its own, so a car can't appear inside the building or tree
  layer.
- **Acceptance test:** `find_vehicles.py` on every painted block and version finds 0 cars of 0.1 score or more on
  roads, car parks and visible ground before the art is accepted. The training set passes the same check before
  training.

### P6. Visible edges and seams between blocks and versions
- **What:** I5 was closed on 7 Nov ("fixed by the whole-canvas painter"), then B3 reopened it the same evening:
  "straight edges visible in almost all scenarios". These were the borders between blocks already painted in a
  version and blocks only colour-graded from the day. They were fixed with a 600 px fade (`d5a53ff`), which hides
  the edge but doesn't remove it.
- **Root cause:** each of the 15 blocks and each version is a separate generation. The viewer showed versions while
  they were still being painted. Blocks with no paint in a version fall back to a graded copy of the day art. The
  painter's colour varies from run to run (water was recoloured after the fact, `water_tone.py`).
- **v2 principle:** **a version is published only when it is complete and seam-checked.** Paint each version over
  the whole area in one pass, with the neighbours held. Never mix painted and graded tiles.
- **Acceptance test:** `seam_check.py` over the whole stitched map for every version. No block border with a LAB
  ΔE step above 3 across a 64 px band, run in CI before tiles are built.

### P7. Seasons and versions drift; events must be patched again
- **What:**
  - B4: spring is "acid yellow-green".
  - I3: the full-resolution night was lost because the old tiler overwrote `live/canvas_full.png`, so the night was
    upscaled from a 4096 px preview.
  - Magenta specks from the light model (`despeckle.py`).
  - I11: Christmas and event patches belong to one version of the art, so they were composited again after T1
    (`7d5e269`).
  - The Ferris wheel's painted A-frame had to be removed with a masked edit before the live wheel could be drawn.
  - The Pfaffenthal lift went from live structure to a painted repaint (`655706b`), so `lift.json`'s structure is
    now false.
- **Root cause:** every version is a full repaint of the whole picture by a second LoRA (the light LoRA, trained on
  348 OpenAI "transform" pairs, $21.51) from the painted day. Its colours are learned from teacher drawings, not
  set. Events are pixel patches on one version, so any repaint below them breaks them.
- **v2 principle:** **seasons change only what changes.** Swap the tree layer and the ground cover per season (POC
  V2.3b: "spring is only a tree swap", $0.33). Snow is a layer. Events are separate sprite or patch layers keyed to
  the geometry, not to a version's pixels.
- **Acceptance test:** for every season, the pixels outside the tree, ground-cover and snow layers are identical to
  summer (diff = 0). The mean hue and saturation of the canopy stay within set bounds per season (for spring, no
  more than +10% saturation over summer). Event layers render the same before and after a base repaint.

### P8. The painted area is only the pilot area (I14)
- **What:** "whole city" in PLAN.md meant the rendered pilot box (lon 6.115 to 6.175, lat 49.597 to 49.637). Merl,
  Belair, Cloche d'Or, Gasperich, Cessange, most of Hollerich, Rollingergrund, Beggen and Dommeldange are outside.
  This was found on 7 Nov at 17:07 (`90d9645`), after the "whole city" day painting was done.
- **Root cause:** the scope was never written as a boundary. The render extent was fixed early for a pilot, and
  "whole city" was taken to mean "whole render".
- **v2 principle:** **scope is a polygon in the repo** (the commune boundary from OSM), checked by code.
- **Acceptance test:** the share of the commune polygon covered by painted tiles is printed by the tile build. A
  release that claims "the whole city" needs 100%.

### P9. Cost overruns and spending surprises (Modal)
- **What:**
  - Plans said: Phase 4, city by day, "about $10"; Phase 5, versions, a "$60 cap approved"; PLAN_NEXT, "about $14
    to $19".
  - The logs show Modal metered at $30.10 when the first versions pass started, $65.17 after the second, and $71.14
    after the third (`run_versions*.log`).
  - The first versions pass (`run_versions.sh`) ran about 3 hours and painted only b00 and b03 per version. b01,
    b02 and b04 failed on time caps that were too tight, and b10 to b14 "can't start". It was re-run three times,
    with cap fixes (`b3cf29d`, `0362b51`).
  - `paint_city.py --budget` caps each *invocation*, not the total. The runs were looped per version and repeated,
    so a $30 cap ran up to six times. Only `run_versions2.sh` added a real cap on the monthly total (`CAP=75`).
  - `modal_spend.json` holds 2 entries ($0.26). Most Modal spend isn't in any log.
  - Modal ended up disabled (BACKLOG T1). The provider switched three times in two days: RunPod, then Modal (I12),
    then RunPod again (`e801449`).
  - On RunPod, the T1 jobs add up to about $6, but the pod session cost $10.36 (setup, model download, gaps).
- **Root cause:** the caps measured wall time per job, not money per account. The time per window was a guess
  (`--sec-per-window`). There was no ledger that adds up every provider. Approval was asked per run, not for the
  total.
- **v2 principle:** **one ledger, one cap per goal.** Every paid call writes to one `spend.jsonl` (provider, job,
  measured cost). A run won't start unless the ledger total for the goal plus the run's worst case is under the
  approved cap. Before each batch, the provider's real billing is read back and reconciled.
- **Acceptance test:** the ledger matches the providers' billing within 5% after every session. Any batch over $5
  starts with a pilot of at most 10% of the blocks, whose measured cost per block sets the cap for the rest.

### P10. Work that was redone

| Item | First version | Redone because | Evidence |
|---|---|---|---|
| Style LoRA run 1 | 500 steps, copied its input | control images inside the dataset folder (ai-toolkit walks folders recursively) | NOTES.md, $2.53 |
| Tiler (window by window) | seams and drift, lost night | replaced by whole-canvas `mdpaint` | PLAN Phase 1, I3, I5 |
| Night | 4096 px preview, upscaled | output overwritten | I3 |
| Versions | 2 of 15 blocks per pass | caps too tight | `run_versions.log` |
| Clouds | illustrated sprites (13:29) | replaced by a cloud sea (14:01) | `b9157ee`, `bc0a700` |
| Road fit | T2 block offsets | T2b dense warp, the same day | BACKLOG T2/T2b |
| Painted cars | painted in | detection, 3 pilot methods, repaint, carry to versions | item 4 |
| Lift | live structure | painted in, live structure dropped | `d1967d7`, `655706b` |
| Layered POC | v1 (cardboard trees, flat cliffs) | v2 (painted ground and canopy) | LAYERS_POC |
| Occlusion and drivable | from the render | warped through the field after T2b | `714f446` |

### P11. Fragile one-off scripts and "patch and move forward"
- **What:** 143 Python and shell files, about 19,700 lines, in `pipeline/`. Many are fixes applied to an output:
  `fix_redbridge_deck.py` (the model keeps painting the deck red), `despeckle.py`, `water_tone.py` (which turned
  b07 into NaN colours on an empty mask, `9b9c618`), `carry_to_versions`, `finalize.py`, `fit_roads.py`,
  `fit_to_art.py`. There are near-duplicate names (`flow_field.py` and `flowfield.py`), two guard scripts
  (`guard.sh`, `guard2.sh`), the old `tiler.py` and `repaint.py` next to `mdpaint`, and many `run_*.sh`, `ab`,
  `fix` and `sync` shell files.
- **Root cause:** each defect in the art was fixed downstream, so the pipeline grew one correction per symptom. The
  order of steps lives in prose ("re-run X after any repaint, then Y, then Z": README step 7, T2b, I11), not in a
  build graph.
- **v2 principle:** **one build graph, no post-fixes on the art.** A make-style DAG (inputs, layers, checks,
  tiles) where every step declares its inputs. A repaint marks its dependants out of date automatically. A defect
  is fixed in the input or the layer that caused it.
- **Acceptance test:** `make release` from a clean data folder rebuilds everything, and every check passes. No
  script edits a painted canvas in place.

### P12. Test gaps
- **Viewer:** good unit tests (scene, calendar, traffic, transit, weather, flights, roadfit). T3 found 12 bugs in the
  time slider and the season and event controls (B8). These were bugs in integration and state, which the tests
  didn't cover until `scene.test.ts`.
- **Pipeline:** one test file (`tiles/test_md_core.py`, 6 tests with a stand-in model). There are no tests for
  `render`, `layout`, `make_hint`, the occlusion, the drivable map or the tiles, and no regression checks of the art:
  line score, painter offset, vehicles, seams, colour bounds. The checks that exist (`seam_check`, `water_check`,
  `find_vehicles`) are run by hand and don't gate anything.
- **Tool bugs found late:**
  - ai-toolkit's recursive scan;
  - pod scripts with "grace, then stop" kill later jobs on the same pod;
  - stopping a pod wipes `/venv` and `/hf`;
  - Hugging Face downloads stall in Asian data centres;
  - one output path shared by two jobs.

  All of these are in PLAN.md "Lessons".
- **v2:** every check in this document is a script with a pass/fail exit code, run in CI on a small fixed test area,
  and run as a gate before every paid batch.

### P13. Process: late decisions, missing specs, unclear acceptance criteria
- **Order of work:** the city and six versions were painted (7 Nov, about $70) before the questions that decide how
  to paint were answered: layers or not, the painter's offset, scope, shadows. The layered idea (B7) and the 6.8 px
  shift both came on 7 Nov evening, after the paint.
- **Acceptance criteria were set after the work**, or as "owner's eye". The 97% roads target came after T2. "As rich
  as today" was the POC's success test. The plans have "Verify" lists, but few of them are automatic gates.
- **A calendar of weeks was done in hours.** PLAN_NEXT planned three streams to January. The agents finished most
  of it in about a day, with merges of parallel worktrees. That is fast, but nobody looked at each result before the
  next one was built on it. For example, T2b was built on T2's output while T1 was repainting the art underneath
  both.
- **History:** 5 to 7 Nov is squashed into one commit, so the early decisions survive only in prose.
- **v2:** a short spec per layer with numbered acceptance tests (the ones above), written and agreed before the
  first paid run. Decision gates with the owner happen at the pilot, not after the city. Keep the commit history
  from day one.

## 3. What worked and should be kept

| Kept | Why | Where |
|---|---|---|
| Viewer on OpenSeadragon, map px as the one coordinate system, `toScreen()` | smooth, simple, works on phones | `web/src/components/IsometricMap.tsx` |
| Feature switches with per-release off-lists and `?on`/`?off` | let v1 ship safely with half the features dark | `web/src/features.ts`, `.env.production` |
| One frame clock, no per-frame React state | perf: phone pan 9.6 to 8.2 ms per frame | `web/src/frame.ts`, T3 |
| Test parameters in the address (`?hour`, `?season`, `?seed`, `?roaddebug`) and the screenshot/perf harness | repeatable checks | `testParams.ts`, `web/scripts/shots.mjs`, `perf.mjs` |
| Occlusion idea (vehicles in their own canvas, cut by a foreground) | right idea; it needs true depth (P4) | `occlusion.ts` |
| Traffic sim: IDM following, signals, access rules, emergency corridors, with tests | solid logic, independent of the art | `web/src/sim/traffic.ts` |
| GTFS to OSM rail map-matching (HMM), timetables by day type | correct, data-driven | `build_transit.py`, `transit.test.ts` |
| Whole-canvas painter with shifted windows, resume, hold/repair, laptop tests | the right painter; the hold mode is what layers need | `gpu_train/tiles/md_core.py`, `mdpaint.py` |
| Spend guards: caps as arguments, the OpenAI spend log, pod deadline watchdogs, delete-and-confirm | no runaway pods; extend this to one ledger (P9) | `guard2.sh`, `backend.py`, `openai_spend.json` |
| The overfit-before-train rule | caught the run-1 bug cheaply | PLAN "Lessons" |
| Layered POC v2: painted ground, cut-out buildings, LiDAR canopy painted in place, ink lines in code, per-pixel depth, boundary checks | the base for v2 | `pipeline/layers/v2_*.py`, LAYERS_POC.md |
| Flow-field registration (as a **check**, not a fix) | measures how far the painter moved things | `flow_field.py`, `validate.json` |
| Notes from visitors (Worker, D1, Turnstile, rate limits, admin page) | done and live | `web/feedback-worker/` |
| Deploy: static gh-pages with a 1 GB guard; Sentry, cookieless analytics | cheap and reliable | `web/scripts/deploy-pages.sh` |
| Landmark cards (129) with sources and credited photos; the research collection | valuable content, independent of the art | `research/`, `build_landmarks.py` |
| Docs habit: "Lessons" lists, plans with root causes, costs and verify steps | made this retro possible | PLAN.md, PLAN_NEXT.md |

## 4. Assets reusable in v2

| Asset | Where | Quality / caveat |
|---|---|---|
| 3D buildings (LOD 2.2, CC0), orthophoto 2023, LiDAR, terrain tiles, OSM, GTFS | `data/raw/` (5.2 GB) | good; cars in the orthophoto must be removed |
| Parsed geometry: `buildings.npz`, `terrain.npz`, `lidar_2m.npz`, `bridges.npz` | `data/work/` | good; bridges have piers but no arches (Clausen and Pulvermühle viaducts) |
| Render passes: colour, kinds, lines, heights (16-bit) | `data/work/frames*` | good; the extent covers the pilot box only (I14) |
| LiDAR tree survey 2024 (position, height, crown, type) | layers inputs | very good; about 32k trees in b00; thin it over rivers and gardens |
| Style LoRA v1 `luxembourg-ink-2511` (2,500 steps) | `data/work/style/lora_full/` | works; trained on "do not straighten" drawings |
| Style LoRA v2 (step 2000 of 3,500) | `data/work/style/lora_v2/` | used for the city; checkpoint never compared; finish or retrain |
| Light LoRA `luxembourg-light-v1` | `data/work/night/lora_light/` | night is good; spring is too vivid; it paints shadows too |
| Lightning 8-step LoRA settings | `backend.py` | good: $0.75 per block, fewer seams than 25 steps |
| Training drawings: 40 INK and 59 INK2 views, plus 348 transform pairs | `data/work/style`, `data/work/night` | good style; they contain painted shadows, so v2 albedo needs new targets or a de-lighting step |
| Painted city: day plus six versions, 15 blocks | `data/work/city/b*/canvas_*.png` (6.8 GB) | v1 look; baked shadows, about 560 car spots left, offset; reference only |
| Layered b00 v2 (ground, ink, canopy, depth) | `data/work/layers/b00_v2/` | the best v2 starting point |
| Viewer code (`web/src`, about 9,700 lines) | `web/` | keep the shell, switches, clock, sim, transit, landmarks, notes; rewrite the overlay and occlusion on top of depth layers |
| Vehicle, plane and statue sprites, lamp atlas | `web/public/sprites`, `build_sprites.py`, `build_statues.py` | good |
| `lines.json` (OSM with widths), `transit.json` (matched), `road_heights.json` | `web/public/data/` | the unwarped OSM version is the truth; the `q`/`fit` fields are v1 warps and should be dropped |
| Checks: `seam_check`, `water_check`, `find_vehicles` (OWLv2), `roadfit.test`, `v2_checks` | `pipeline/`, `web/src/sim` | useful; turn them into gates |
| Research: 129 landmarks, interiors, tunnels, eras, 23 events, quarters and easter eggs | `research/` | very good; licences listed per file |
| Notes Worker and D1, Cloudflare zone, isometric.lu | `web/feedback-worker/` | live |

**Leave behind:** `tiler.py`, `repaint.py`, `fit_roads.py`, `fit_to_art.py` and the warp outputs,
`fix_redbridge_deck.py`, `despeckle.py`, `water_tone.py`, `carry_to_versions`, and the per-version event patches.
Each one patches a symptom that v2's layers should prevent.

## 5. v2 rules in one list
1. The data is the truth. Art is held to the geometry and never moved after it is painted. No warp step.
2. Paint layers, not a picture: ground albedo, buildings (cut by the 3D outline), trees (from LiDAR), and lines and
   water in code.
3. Light and shadow come from code and the sun. Painted layers carry no cast shadows.
4. Every layer ships with depth or height. Vehicles are depth-tested per pixel.
5. Nothing that moves is in any input or output. This is checked automatically, including the training data.
6. Scope is a polygon. Each version is complete and seam-checked before it is published.
7. One spend ledger, one cap per goal, a pilot at 10% first, and the billing reconciled.
8. One build graph. Every check is a gate with an exit code. Acceptance tests are agreed before the first paid run.
