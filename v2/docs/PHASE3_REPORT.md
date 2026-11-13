# v2 Phase 3 report: richer code art, tunnel view, cutaway prep

10 November 2026. Branch `v2-phase3`, into `v2`. Test area only. **Spent: $0.** No pod was created.

## 1. The short version

- **Gate G2 is recorded:** method A (all code) for the whole city, in the owner's words "A, enrich in code
  (Recommended)". B and C are stopped. (`research/v2/DECISIONS.md`, `PLAN_V2.md` section 7.)
- **A is richer.** The Bock and the valley cliffs are now bedded sandstone, walls are coursed stone, the ground has
  paving, setts, lawns and garden flowers, trees are lobed crowns in many greens, and buildings have more colours,
  stone surrounds round every window and door, ashlar and banded ground floors. All of it is code, from the data or
  from seeded rules. It is closer to v1 but not at v1's richness yet (section 6).
- **Every gate passes:** 56 of 56 build stages, 247 gate entries. No threshold was changed.
- **Tunnel view is built** (`?xray`, a button, or X held): X1–X8 pass.
- **Landmark cutaways are prepared** for the cathedral, the palace and the abbey: the cut from the 3D model, shown
  in place in the viewer with a placeholder interior (`?cutaway`). The Bock casemates' cutaway is not built.
- **Two quotes are in the ledger, not approved:** q0012 (cathedral, at most $0.54) and q0013 (the other three, at
  most $0.90).
- **Added 13 November:** the cathedral's painting was tried once, for $0.43. The interior style works; no painting
  passed the checks. Section 9 has the run, the free fixes and the new quote q0015 (not approved).
- `data/v2/test/release/current.json` points at the final A build (`619f7c040341`).

## 2. What changed in the look

Before/after sheets, each at day, golden hour and night (top row before, bottom row after), under 1 MB each:

| Place | File |
|---|---|
| Grund | `v2/docs/img/test_phase3_grund.jpg` |
| The Bock | `v2/docs/img/test_phase3_bock.jpg` |
| Neumünster Abbey | `v2/docs/img/test_phase3_abbey.jpg` |
| Facade close-up (2:1) | `v2/docs/img/test_phase3_facade.jpg` |

Made with `python -m v2.build.sheets <before release> <after release>`: screenshots of the real viewer, so the code
lighting is what is shown.

| Layer | Added | Code |
|---|---|---|
| 1 Ground | A **rock** class on the scene's cliff cells: level sandstone beds with ledges, joints and a tone per block. Stone slabs on paved land, setts on squares, gravel on car parks and rail ground, patchy lawns with flecks, flowers in gardens, mown stripes on pitches. | `v2/layers/detail.py`, `render.py` |
| 2 Relief | Cliffs keep only the form shading (the rock is drawn in layer 1). Built walls are coursed masonry; OSM cliffs and embankments are bedded rock. | `render.py` |
| 3 Water | A paler band of shallows, 0.8 m wide, along the banks. Water stays flat. | `render.py` |
| 4 Transport | Setts on pedestrian streets, paths and steps; a fine grain on asphalt. | `render.py` |
| 5 Buildings | Each building in its own tone. 13 facade colours (was 8), 7 roof colours (was 4). Ashlar on stone buildings, a banded ground floor on some, a faint mottle on render. A stone surround, lintel with keystone and sill at every window; a surround and lintel at every door. Windows with a cross or six panes, each window's glass its own tone. Gravel on flat roofs. The cathedral, palace and abbey get their real materials from a small data file. | `art_a.py`, `v2/data/structures/landmark_styles.json` |
| 7 Trees | Broadleaf crowns are a core with five to seven lobes and one on top; conifers are three tiers. Each tree has its own depth of green and leans warm or cool. A lighter ink line where lobes meet. | `render.py` (`crown_lobes`) |
| 14 Look | The saturation cap went from 0.62 to 0.68, so the richer colours are not flattened. Ink is unchanged. | `v2/config/light.json` |

- Nothing is baked: every pattern is a function of the pixel's place on its surface and a hash, never of the sun.
- No shape of a crown goes beyond the tree's measured width or height (unit test).
- Nothing that moves is drawn.
- Day light: the light pass is unchanged. The pictures differ because the art changed.

**One change to how roofs are drawn, forced by a gate.** With the new roof colours one tiled roof failed the
no-baked-shadows gate (6.5% against 5%). The cause was the roof lines, not light: at 0.125 m a pixel, tile rows of
0.34 m filled more than half the pixels of a roof face, so a face seen square on came out darker than one seen at a
grazing angle. Roof courses are now 0.45 m (tile) and 0.5 m (slate) and fade out on faces too foreshortened to hold
them. The worst building is now at 4.0% (Phase 2: 4.97%).

**Tile coding.** Ground and transport tiles are lossy WebP at quality 96 (was 90), because they now carry fine
detail. Their bytes grow about 1.5 times. Layers 5–7, relief and water stay lossless.

## 3. Gates

From `v2/docs/results/g3_test.json` (`python -m v2.build test g3`). Thresholds are the build's own.

| Brief or check | Result | Limit | Phase 2 (A) |
|---|---|---|---|
| Build | **56 of 56 stages** | all | 50 of 50 |
| #5 No baked shadows (L5.1): materials over 5% | **0 of 226**; worst 4.0% (buildings), ground 1.4%, structures 2.7% | 0 | 0; worst 4.97% |
| L1.2 ground, north vs south slopes | **0.8%** | ≤ 2% | 0.04% |
| #6 Line score, building edges (L5.2) | **96.33%** | ≥ 95% | 98.05% |
| #6 Line score, window rows | **99.84%** | ≥ 95% | 99.30% |
| #9 No cars (OWL), all 7 layers | **0 detections** | 0 | 0 |
| Seams, layers 5–7 and relief | **0.0** | ≤ 3 | 0.0 |
| Seams, ground / water / transport | **2.65 / 1.50 / 1.40** | ≤ 3 | 2.48 / 1.50 / 1.75 |
| #4 Layer independence (C1a, C1b) | **0, 0** | 0 | 0, 0 |
| C1c built tile vs renderer | **2.21** | ≤ 3 | 2.62 |
| Layer checks L1.1, L2.1, L2.2, L3.1, L4.1, L4.3, L4.6, L8.1–L8.3, P-1 | **all pass** (L4.1 100%) | | pass |
| #7 Cars on drawn road / transit on track | **99.974% / 100%** | ≥ 99.5% | pass |
| #8 Depth test at portals and bridges (C4) | **0 mismatches** | 0 | 0 |
| Vehicle height jumps | **0.33 m, 0.05 m** | ≤ 0.5 m | pass |
| Viewer: layer off leaves no trace (7 layers) | **0 pixels** each | 0 | 0 |
| Viewer: shadows match the reference at 10:00, 13:00, 16:00 | **98.6%, 99.6%, 97.2%** | ≥ 97% | pass |
| Look pass applied twice (V7) | **0** | ≤ 1 | 0 |
| Speed: first view / panning (desktop) | **0.086 s / 95 fps** | ≤ 0.5 s / ≥ 60 | 0.094 s / 94 fps |
| Data checks, no patching, ledger | **all pass** | | pass |

Three numbers moved towards their limits and are worth knowing:
- **Building edges, 98.05% to 96.33%.** It fell when the roof lines became soft (98.2% to 96.7% between two
  builds that differed only in that). I did not find out why in detail. It passes with 1.3 points to spare.
- **Shadows at 16:00, 97.2% against 97%.** The viewer's shadows are compared with a reference; lobed crowns have
  more edge. It passes with little room.
- **Ground seams, 2.65 against 3.** This is the lossy coding, not a seam in the drawing.

## 4. Tunnel view (X1–X8)

`?xray` in the address, the "Tunnel view" button, or X held. The city fades to 35% and the tunnels show at their
real path and depth from the transport graph, darker per 10 m of depth, with vehicles moving inside.
Spec as built: `v2/docs/specs/tunnel-view.md`. Pictures: `v2/docs/img/test_xray_day.jpg`, `test_xray_night.jpg`,
`test_xray_casemates.jpg`. 193 tubes, 5.2 km: 166 tunnel edges, 1 passage, 26 casemate galleries.

| Check | Result | Limit |
|---|---|---|
| X1 Tunnels in the right place | 0 edges under 99% within 1 px | 0 |
| X2 Right depth | 0.51 cm; cover matches the graph (0.0 m) | ≤ 1 cm; ± 0.5 m |
| X3 Vehicles only inside tunnels | 0 wrong pixels; over a simulated day 0 others drawn, 0 lost, 0 outside their tube | 0 |
| X4 The fade | off after on: 0 pixels differ; faded city vs reference 0.65/255; seams 0.08 | 0; ≤ 1; ≤ 3 |
| X5 Layer toggles | 0 pixels of each of the 7 layers; tunnels unchanged (0.6/255) | 0; ≤ 1 |
| X6 Portals agree | 0.49 px over 36 portals | ≤ 1 px |
| X7 Casemates | from their data; at least 1.02 m of rock above; 0 pixels outside tunnel view | ≥ 1 m; 0 |
| X8 Speed | 1 frame to toggle; 94.5 fps panning | ≤ 1; ≥ 60 |

- With `?xray` absent, the viewer's frame is identical to before the feature (0 pixels at 5 views, day and night).
- **Reported, not gated (X3e):** 555 vehicle samples are partly behind their own tube's floor. A vehicle is a level
  box, and the René Konen tunnel's profile dips steeply (about 18%) at one place.
- **The casemates are an approximate hand model**, not a survey (`v2/data/structures/casemates.json`): one main
  gallery of 110 m and 25 side galleries, from published descriptions.
- X8 was measured on this laptop, headless. No phone was measured.

## 5. Landmark cutaways (free part) and the quotes

Spec as built: `v2/docs/specs/landmark-cutaways.md`. `?cutaway` (or `?cutaway=cathedral,palace`), or the
"Cutaways" button. Pictures: `v2/docs/img/test_cutaway_<cathedral|palace|abbey>_placeholder.jpg` (whole beside
cut) and `..._viewer.jpg` (in the map).

- **Built for three:** Notre-Dame Cathedral, the Grand Ducal Palace, Neumünster Abbey. The cuts are data
  (`v2/data/structures/cutaways.json`); the slice, the cut faces and the inside faces come from the 3D model; the
  interior is a plain code placeholder; the inputs for the later painting are written by the build.
- **Checks:** K0–K6 on the tiles, 45 gates pass; in the browser, 42 gates pass.

| Check | Cathedral | Palace | Abbey |
|---|---|---|---|
| K1 cut outline within 1 px (≥ 95%) | 100% | 100% | 99.78% |
| K1 cut pixels outside the model | 0 | 0 | 0 |
| K2 interior pixels outside the opening; mask covered | 0; 100% | 0; 100% | 0; 100% |
| K5 depth vs the model (≤ 1 cm) | 0.5 cm | 0.5 cm | 0.5 cm |
| K5 vehicles and labels depth-tested in the viewer | 0 wrong | 0 wrong | 0 wrong |
| K6 off means off (pixels differing) | 0 | 0 | 0 |
| K4 no cars or people on the inputs | 0 | 0 | 0 |

- K2 and K3 pass trivially today, because the placeholder is flat colour inside its own mask. They become real
  tests when there is a painting.
- **Not done:**
  - **The Bock casemates' cutaway** (a cut through rock). Its gallery data exists.
  - **The opening's own shadow** (the `?hour` part of K3). The shadow map still holds the whole building, so the
    opened interior is in shade at every hour. It was left out rather than faked.
  - K7 is the owner's.

**Quotes (not approved, nothing committed, no pod):**

| Quote | Job | Expected | Worst case |
|---|---|---|---|
| q0012 | Cathedral interior, the first, alone: 1 view × 4 candidates | $0.24 | **$0.54** |
| q0013 | Palace, abbey and casemates, only after the cathedral is approved: 3 views × 4 candidates | $0.35 | **$0.90** |
| Total | | $0.59 | **$1.44** |

- Under the Phase 3 line ($8 cap, $0 spent). The earlier estimate was $1.21 expected, $1.88 worst case, for two
  views per landmark. There is one camera, so there is one view.
- Expected cost uses Phase 2's measured times: about 4 minutes of setup and 19 seconds a painting on one H100.
- **A risk to weigh before approving:** in Phase 2, v1's style model returned flat facades almost as it was given
  them. A cutaway interior asks the same model to invent rooms from a flat render. The cathedral alone ($0.54 at
  most) is the test of that.

## 6. What is left for G3

- **Richness against v1.** Closer, not there. Still plainer than v1: roofs (no chimneys or dormer windows beyond
  ACT's shapes, faint courses), no balconies or signs, flat-roof detail, bridges and viaducts unchanged, car parks
  without bays. The cathedral and other churches get house windows and shutters from the facade rule.
- **Palette, grade and ink:** one small change so far (saturation cap). The owner's eye at fixed views is the tuning.
- **Code vs AI night and golden hour comparison** (plan section 9): not done; no AI version exists.
- **Seasons:** the viewer has them from Phase 1 (`?season=`, `?snow`). Not tuned or reviewed in Phase 3.
- **Events as objects:** not started.
- **Cutaways:** the paintings (after approval), the casemates' cutaway, the opening's shadow.
- **Owner checks:** L2.5, L14.4, K7.

## 7. Open questions for the owner

1. **The look.** Is this the right direction, and what is most missing against v1?
2. **Rock** is drawn wherever the terrain is a cliff (60° or steeper with a 2.5 m drop), whatever OSM says. Right?
3. **Roof courses are larger than life** (0.45–0.5 m) and fade on foreshortened faces, to keep the shadow gate
   honest. Acceptable?
4. **Tile quality 96** for ground and transport: about 1.5 times their bytes. Fine for hosting?
5. **Landmark materials** are a hand-made data file (three buildings so far). Extend it to all landmarks?
6. **Tunnel view:** the graph's own Bock passages from OSM and the hand-modelled casemates are both drawn and
   disagree in height by up to 9 m. Show both, one, or align them?
7. **Tunnel view:** is the René Konen dip real, or an artefact of the graph's profile? Buses sink into the floor
   there.
8. **Tunnel view:** tubes are drawn whole, also beyond the area's outline. Clip them?
9. **Cutaways:** are the three cuts the right ones? The palace and abbey slices are large.
10. **Cutaways:** the interior is in shade at every hour until the opening's shadow is solved. Accept for now?
11. **Cutaways:** while one is on, far zoom switches from the merged tiles to separate layers for the whole view.
    Accept, or switch cutaways off when zoomed far out?
12. **Quotes q0012 and q0013:** approve the cathedral first?

New tolerances added inside the new checks (none loosens a spec threshold; each is listed in its spec):
- Tunnel view: samples within 5 cm of a depth-tone step or of the portal line are set aside; vehicle boxes are
  grown by 1 px for edge rounding.
- Cutaways: pixels within 1 cm of the building's outside are neither required nor forbidden in the mask check; the
  mask probe is 7 cm; thicknesses are nominal (walls 0.8 m, roofs 0.4 m, slabs 0.3 m).

## 8. How to look

```sh
export ISOLUX_DATA=/Users/amirdaraee/00/projects/isometric-luxembourg/data
.venv/bin/python -m v2.view test          # http://localhost:5174/   (Ctrl-C stops it)
# add ?xray for the tunnel view, ?cutaway for the cutaways, ?hour=21.3 or ?hour=23.25 for golden hour and night
```

## 9. The cathedral cutaway: first painting test (10 November), free fixes (13 November)

Branch `v2-phase3-cathedral`, into `v2`. **Spent: $0.4256** (the first run). The fixes cost $0.

### The first run

- **Quotes.** q0012 (an H100, community cloud) was approved, but no H100 was free. Asked which GPU to use, the
  owner answered "A100 SXM, secure (Recommended)". q0012 was released unspent. q0014 replaced it: A100 SXM, secure
  cloud, $1.79/h, cap 0.25 h, worst case $0.45. The owner approved it.
- **Pod** `0r548l7stsvho6`, terminated. Ledger spend **$0.4256** (846 s). RunPod's balance fell by about $0.38; its
  billing line was not yet published, so the run is not reconciled yet.
- **Times, measured:** ssh after 128 s; setup done 497 s after the pod was created (the 56 GB model download is
  most of it); model loaded in 267 s; 23 s per painting.
- **The pod reached its time cap after 3 of 4 paintings.** `cathedral-open_1` was never painted. The quote had
  assumed Phase 2's 4 minutes of setup, measured on a pod that already held the model.
- Paintings: `<data>/v2/test/bakeoff/cutaways/painted_run1/`. Numbers: `v2/docs/results/cutaway_K1_run1.json`.
  Sheets: `v2/docs/img/test_cutaway_cathedral_candidates_run1.jpg` (the three candidates) and
  `test_cutaway_cathedral_paint_input_run1.jpg` (what the painter was given).

### What came back

- **The model paints a real interior** in the ink style: Gothic arches, stained glass, pews, a chequered floor. The
  Phase 2 risk (it returns the flat render as given) did not happen.
- The owner looked at the candidates on 13 November 2026 and said the interior style "looks good".
- **No candidate passes.** The table gives each check as first measured and as measured after the fixes below.

| Check (limit) | cathedral_0 | cathedral_1 | cathedral-open_0 |
|---|---|---|---|
| K1 section outline within 1 px (≥ 95%) | 98.8% | 98.4% | 99.2% |
| K2 interior pixels outside the mask (0) | 0 | 0 | 0 |
| K2 mask covered (≥ 99.5%), first measure | 97.5% | 99.7% | 95.8% |
| K2 mask covered, corrected measure | **99.997%** | **100%** | **99.97%** |
| K3 faces of one kind, turned different ways (≤ 5%) | 18.2% | 34.6% | 19.5% |
| Light across a face (≤ 5%), first measure | 96% | 213% | 281% |
| Light across a face, corrected: walls / roof / floor | 32% / 15% / 11% | 28% / 20% / 6% | 36% / 18% / 13% |
| Lines kept (≥ 95%; not in the spec) | 91.8% | 93.0% | 91.4% |
| of these, the section's lines | 99.9% | 98.6% | 97.3% |
| of these, the placeholder's own lines | 84.5% | 88.1% | 86.1% |
| K4 cars or people | 0 | 0 | 0 |

### What failed, why, and what was changed

1. **Coverage (K2).** The reported cause, unpainted strips at the opening's edge, was wrong. I measured where the
   "uncovered" pixels are: in `cathedral_0`, 819 of 900 are on the floor, half of them more than 23 px from the
   edge, and 10 are within 3 px of it. They are the **light squares of the chequered floor**, whose colour is within
   the tolerance of paper. The check called a pale floor slab unpainted.
   - Fix: a blank is a patch, not a pixel. A mask pixel is unpainted if it has the colour of paper, or of the
     painting's own background (two of the three paintings came back on white, not on paper), and lies in such a
     patch that holds a 7 × 7 px square (0.9 m). Pixels outside the mask count as blank for the patch, so a blank
     strip along the edge is found at any width.
   - The 99.5% limit is unchanged. All three paintings now pass K2.
   - One input was also changed: the "opening cleared" input now keeps the section (the cut faces), so the
     opening's rim is given to the painter. In `cathedral-open_0`, 99 section pixels had been left pale.
   - New tolerance: the 7 px patch. A pale slab lying on the very edge of the opening still counts as blank
     (0.2% in the unit test's worst case).
2. **Light across a face.** The old check fitted a plane to a face's luminance. A chequered floor, pews on one
   side or a window read as light.
   - Fix: light is measured on one material. The face's material is the colour of its light pixels, brightness
     set aside. In every 16 px square (2 m, every 4 px) that is at least two fifths that material, the lit level is
     the 90th percentile of the material's luminance. The result is the largest fall of that level between two
     squares. The limit stays 5%, K3's own.
   - Proved on synthetic images (`test_light_across_a_face_measures_light_not_what_is_drawn_on_it`): a flat face,
     a chequer, a navy chequer, lozenges, joints and a soft-edged chequer measure under 1%, also with pews
     standing on them. Every one of them fails with a gradient (40% and 10% from side to side) and with a cast
     shadow (6.5 m and 3.5 m across).
   - On the three real paintings it still fails all three. `cathedral_1` fails on the floor (5.7%), the roof
     (20%) and the walls (28%).
   - **Limits, stated in the code:** a shadow narrower than about 2.5 m is not measured (a thin shadow beside a
     pew). A shadow drawn in another colour than its surface (blue on cream stone) counts as another material.
     In `cathedral_1` the dark floor is navy, so this check does not catch it as shade; the prompt now forbids it.
   - The floors of `cathedral_0` and `cathedral-open_0` look evenly lit and still measure 11% and 13%. In
     `cathedral_0`, nine tenths of the floor's squares lie within 3.5% of each other. The extremes are where the
     painter drew the foot of the wall on what the model calls floor (a darker stone of the same colour), and
     beside pews. So this check can still fail an evenly lit floor for what is drawn at its edges.
   - The walls measure 28–36%. I did not look into each wall square; the painter draws arches and vaults in
     several tones of stone.
   - New tolerances: the 16 px square, the 4 px step, chroma within 0.03, the two-fifths share, the 90th
     percentile. No painting's verdict depends on them: all three fail at every setting I tried.
3. **K3** (unchanged, not loosened). It compares the median luminance of the inside walls turned different ways.
   In these paintings the median wall pixel is dark (about 90 of 255; the stone is about 210): more than half of
   each wall is window or ink. So K3 measures how much glass each wall has. The prompt now asks for narrow
   windows and the same pale sandstone on every wall.
4. **The prompt** (`v2/bakeoff/cutaway_paint.py`). It now asks for the interior "as a flat colour drawing", "lit
   evenly from every side, like a diagram", a pale floor "from edge to edge, also under and beside the pews and
   the columns", and "No cast shadows, no dark floor, no dark corners, no beams of light". Its effect is not known
   until a run.
5. **Lines kept.** This check is not in the spec. The lines that go missing are not the section's (97–100% kept;
   K1 covers them and passes). They are the placeholder's own construction lines: the floor against the wall
   (66–69% kept, the pews stand in front of it), wall corners (87–97%), the roof against the wall (82–92%). The
   placeholder is a hollow shell with nominal walls, so a painted interior legitimately covers these.
   - Not changed. The rule still fails all three. The numbers are now reported apart. See open question 13.
6. **Time.** The job is planned again from the measured times: 128 s to ssh, 62 s preflight and uploads, 307 s
   more of setup, 289 s model load, 4 × 23 s painting, 30 s to bring the results back and terminate: **908 s
   (15.1 min)**. The new cap is 0.45 h (27 min), 75% over that.
   - Still four candidates: two inputs × two seeds. In the first run the same seed gave nearly the same painting
     from both inputs, so the four now have four different seeds (1867–1870).
7. **The compose step.** `python -m v2.bakeoff adopt K1` puts the best passing candidate, cut to the mask, into
   `v2/data/structures/cutaway_paintings/`. The cutaway layer then draws it in place of the placeholder at the
   next build, and gates K1–K6 run on the painted tiles.
   - Refused while no candidate passes, so the placeholder stays today.
   - Only colour inside the opening changes. Depth, normals, ids and the mask stay the model's.
   - Tested with a synthetic painting on the real cathedral: 33,325 of 33,325 opening pixels painted, each from
     its own map pixel; 0 pixels changed outside the opening; 0 changes to depth, normals, ids or kinds; the
     painter's input stays the placeholder. Not looked at in the browser.

### The new quote (not approved, nothing run)

| Quote | Job | Expected | Worst case |
|---|---|---|---|
| q0015 | Cathedral interior, second run: 1 view × 4 candidates, A100 SXM, secure cloud | $0.57 | **$0.99** |

- The A100 SXM's secure price is **$2.19/h** today (read 13 November; it was $1.79 on 10 November).
- Expected: 0.26 h. Worst case: the 0.45 h cap.
- Phase 3 line: $8 cap, $0.4256 spent, q0013 ($0.90) and q0015 quoted and not approved.
- **A risk to weigh:** the walls failed K3 and the light check by a wide margin, and the only lever tried is the
  prompt. A second run may bring better candidates and still no pass.

### Gates after the change

The cutaway layer's code changed, so its stage and everything after it were built again on the test area:
see `v2/docs/results/g3_test.json`. The tiles are identical to the build before (only `index.json` gained a field).

### Open questions added

13. **Lines kept:** make the gate "the section's lines" (K1, the spec's own check) and only report the
    placeholder's lines? Today's rule would fail any interior with pews or columns in front of a wall.
14. **K3 on a painted wall** compares medians, so it measures window area. Keep it as it is and ask the painter
    for less glass (done in the prompt), or define K3's "material" for paintings as the stone?
15. **The light check's limits:** it misses thin shadows and shadows drawn in another colour, and it can fail an
    evenly lit floor for a wall's foot or a pew drawn at its edge. Accept it as a gate with K7 (your eye) as the
    last check, or make it a reported number?
16. **GPU for the second run:** the secure A100 SXM is now $2.19/h. The community A100 SXM is $1.39/h (worst case
    about $0.63) if one is free. Quote q0015 is for the secure one, as last time.
17. **The chequered floor and the pews** are the painter's invention from my prompt, not from a reference of the
    real cathedral. Keep them?

### The two checks corrected (13 November, $0, before the second run)

The owner's answer to questions 13 and 14, on 13 November 2026: "Correct both, free (Recommended)". Both were
changed and committed before the second run, so the run is judged by definitions fixed in advance.

- **K3 on a painting measures the wall's stone only.** The material of a face is the colour of its light pixels,
  brightness set aside. Glass is another colour and is left out. Ink is left out: a pixel darker than one of its
  eight neighbours by a line step (12). Stone in shade keeps its colour and stays in. The limit is still 5%.
  - A side of a wall with under 150 px of stone to measure fails, so a wall cannot escape by having no stone.
  - Proved on synthetic walls (`test_k3_on_a_painting_measures_the_stone_not_the_glass_or_the_ink`): one wall 70%
    glass, the other 20%, the stone evenly lit: the old measure gives over 15%, the new one under 1%, a pass. The
    stone of one wall darker by 10%, 20% or 40%: fails, at that number. A whole wall in shade: fails. 3%: passes.
  - Limit: a shade drawn in another colour than the stone's is another material and is not measured here.
  - The built gate (`check_cutaways`, K3) uses the same measure on a landmark whose interior is painted. On the
    placeholders it is unchanged; all three still measure 0%.
- **Lines kept gates the cut's outline.** The gate is the share of the section's lines with a drawn step within
  1 px, at 95%. The placeholder's own lines (floor against wall, wall corners, roof against wall) are reported.
- Not changed: the light-across-a-face check, K1, K2, K4, the no-baked-light rule.

The three paintings of the first run, measured again (`v2/docs/results/cutaway_K1_run1.json`):

| Check (limit) | cathedral_0 | cathedral_1 | cathedral-open_0 |
|---|---|---|---|
| K3, every pixel of the wall (the old measure) | 18.2% | 34.6% | 19.5% |
| K3, the stone only (≤ 5%) | **12.2%** | **13.8%** | **10.7%** |
| Share of the wall that is stone | 21% | 27% | 21% |
| Lines kept, the section's (≥ 95%) | 99.9% | 98.6% | 97.3% |
| Lines kept, the placeholder's (reported) | 84.5% | 88.1% | 86.1% |
| Light across a face: walls / roof / floor (≤ 5%) | 32% / 15% / 11% | 28% / 20% / 6% | 36% / 18% / 13% |

- The lines gate now passes on all three.
- K3 still fails on all three, by less. The stone of the short wall that faces south-east is darker than the
  other two walls' (about 175 to 180 of 255 against 185 to 200). That is a painted tone difference between walls, which
  is what K3 is for.
- So no first-run painting passes with the corrected checks: K3 and the light check both fail.
