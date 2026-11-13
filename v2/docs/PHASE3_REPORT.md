# v2 Phase 3 report: richer code art, tunnel view, cutaway prep

10 November 2026. Branch `v2-phase3`, into `v2`. Test area only. **Spent: $0.** No pod was created.

## 1. The short version

- **Gate G2 is recorded:** method A (all code) for the whole city, in the owner's words "A, enrich in code
  (Recommended)". B and C are stopped. (`research/v2/DECISIONS.md`, `PLAN_V2.md` section 7.)
- **A is richer.** The Bock and the valley cliffs are now bedded sandstone, walls are coursed stone, the ground has
  paving, setts, lawns and garden flowers, trees are lobed crowns in many greens, and buildings have more colours,
  stone surrounds round every window and door, ashlar and banded ground floors. All of it is code, from the data or
  from seeded rules. It is closer to v1 but not at v1's richness yet (section 6).
- **Every gate passes:** 56 of 56 build stages, 248 gate entries (247 before the painted cathedral; the new one is
  K3's "no side too small to measure"). No threshold was changed.
- **Tunnel view is built** (`?xray`, a button, or X held): X1–X8 pass.
- **Landmark cutaways are built** for the cathedral, the palace and the abbey: the cut from the 3D model, shown
  in place in the viewer (`?cutaway`). The cathedral's interior is painted (since 13 November, section 9, "In the
  map"); the palace and the abbey have a placeholder interior. The Bock casemates' cutaway is not built.
- **Two quotes are in the ledger, not approved:** q0012 (cathedral, at most $0.54) and q0013 (the other three, at
  most $0.90). (q0013 was dropped on 13 November, unspent: section 10.)
- **Added 13 November:** the cathedral's painting was tried once, for $0.43. The interior style works; no painting
  passed the checks. Section 9 has the run, the free fixes and the new quote q0015 (not approved).
- **Added later on 13 November:** q0015 ran ($0.47, four paintings, none passes). The light check was then looked
  into at $0 and corrected; the best painting still fails it. The placeholder stays (section 9).
- **Added last on 13 November: the cathedral's painting is in the map.** The owner took `cathedral-open_1` by
  eye ("Take it on my eye (Recommended)"). For painted cutaways the light check is now a reported number; the other
  checks stay gates, and the owner's eye (K7) is recorded per landmark. $0. Section 9, "In the map".
- **Added after that on 13 November, three decisions of the owner (section 10):** a cutaway's opening is lit by
  the sky only; churches have church facades, in code; quote q0013 is dropped. $0, no pod. 57 of 57 stages, 273
  gate entries, 0 fail, no threshold changed.
- `data/v2/test/release/current.json` points at the final A build (`cc4d856c63d4`), which holds the painted
  cathedral cutaway, the sky light rule's settings and the church facades.

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
| Speed: first view / panning (desktop) | **0.096 s / 91 fps** (13 Nov build; 0.086 s / 95 fps on 10 Nov) | ≤ 0.5 s / ≥ 60 | 0.094 s / 94 fps |
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
cut) and `..._viewer.jpg` (in the map). The cathedral's two show its placeholder, as it was until 13 November; the
painted cathedral in the map is `test_cutaway_cathedral_map.jpg` and `..._map_wide.jpg` (section 9).

- **Built for three:** Notre-Dame Cathedral, the Grand Ducal Palace, Neumünster Abbey. The cuts are data
  (`v2/data/structures/cutaways.json`); the slice, the cut faces and the inside faces come from the 3D model; the
  interior is a plain code placeholder (the palace and the abbey) or the adopted painting (the cathedral, since
  13 November); the inputs for a painting are written by the build.
- **Checks:** K0–K6 on the tiles, 46 gates pass; in the browser, 42 gates pass. The table is of 10 November
  (placeholders); the painted cathedral's numbers are in section 9, "In the map".

| Check | Cathedral | Palace | Abbey |
|---|---|---|---|
| K1 cut outline within 1 px (≥ 95%) | 100% | 100% | 99.78% |
| K1 cut pixels outside the model | 0 | 0 | 0 |
| K2 interior pixels outside the opening; mask covered | 0; 100% | 0; 100% | 0; 100% |
| K5 depth vs the model (≤ 1 cm) | 0.5 cm | 0.5 cm | 0.5 cm |
| K5 vehicles and labels depth-tested in the viewer | 0 wrong | 0 wrong | 0 wrong |
| K6 off means off (pixels differing) | 0 | 0 | 0 |
| K4 no cars or people on the inputs | 0 | 0 | 0 |

- K2 and K3 pass trivially on a placeholder, because it is flat colour inside its own mask. On the painted
  cathedral they are real tests (K3 2.0%).
- **Not done:**
  - **The Bock casemates' cutaway** (a cut through rock). Its gallery data exists.
  - **The opening's own shadow** (the `?hour` part of K3). The shadow map still holds the whole building, so the
    opened interior is in shade at every hour. It was left out rather than faked. (Since 13 November the opening
    is lit by the sky only and takes no cast shadow: section 10.)
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
  without bays. The cathedral and other churches got house windows and shutters from the facade rule; since
  13 November they have church facades (section 10).
- **Palette, grade and ink:** one small change so far (saturation cap). The owner's eye at fixed views is the tuning.
- **Code vs AI night and golden hour comparison** (plan section 9): not done; no AI version exists.
- **Seasons:** the viewer has them from Phase 1 (`?season=`, `?snow`). Not tuned or reviewed in Phase 3.
- **Events as objects:** not started.
- **Cutaways:** the palace's and the abbey's paintings (no quote: q0013 was dropped, a fresh one comes later), the
  casemates' cutaway. The cathedral's painting is in the map, lit by the sky only (section 10).
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
    (Answered on 13 November: "Light by sky only", section 10.)
11. **Cutaways:** while one is on, far zoom switches from the merged tiles to separate layers for the whole view.
    Accept, or switch cutaways off when zoomed far out?
12. **Quotes q0012 and q0013:** approve the cathedral first? (q0012 ran as q0014 and q0015, section 9; q0013 was
    dropped on 13 November, section 10.)

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
# the painted cathedral: http://localhost:5174/?cutaway=cathedral&x=60290&y=32990&z=2&hour=13&date=2026-06-24
```

## 9. The cathedral cutaway: first painting test (10 November), free fixes, second run, the light check, and into the map (13 November)

Branches `v2-phase3-cathedral` to `v2-phase3-cathedral4`, into `v2`. **Spent: $0.4256** (the first run) **and
$0.4672** (the second). Everything else cost $0. **The second run's `cathedral-open_1` is in the map since
13 November, taken on the owner's eye** (the last part of this section, "In the map"). The parts before it are
kept as they were written, when no painting had passed.

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

### The new quote (approved and run on 13 November: see "The second run")

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

### The second run (13 November)

- **Approval.** Asked "Quote q0015: second cathedral cutaway run on RunPod, A100 SXM secure, 4 candidates, expected
  $0.57, worst case $0.99 (Phase 3 has $7.57 of $8 left). Approve it?", the owner answered on 13 November 2026:
  "Approve, run after the check fixes (Recommended)". q0013 is not approved.
- **Before the pod:** the check fixes were committed (`9d01ea9`); the live price was $2.19/h, as quoted; the cap was
  1,592 s, which at $2.2105/h (GPU and disk) is $0.98.
- **Pod** `1zj2z6jzs0dz39`, terminated. It ran once, finished, and made all four paintings.
- **Spend: $0.4672** (761 s), against $0.57 expected and $0.99 worst case.
- **Reconciled.** RunPod's line for the first run is now published: $0.4258 billed, $0.4256 in the ledger. The
  second run's line is not published yet; RunPod's balance fell by $0.4663 for it. All pods together: $4.6062 by
  the balance, $4.6088 in the ledger. Recorded in the ledger.
- **Times, measured:** ssh after 23 s (128 s last time); model loaded in 279 s; 21.8 s per painting; 12.7 minutes
  in all (15.1 planned).
- Paintings: `<data>/v2/test/bakeoff/cutaways/painted/`. Numbers: `v2/docs/results/cutaway_K1.json`. Sheets:
  `v2/docs/img/test_cutaway_cathedral_candidates.jpg` (the four candidates) and
  `test_cutaway_cathedral_paint_input.jpg`.

**No candidate passes.** All four fail the light-across-a-face check; two also fail K3.

| Check (limit) | cathedral_0 | cathedral_1 | cathedral-open_0 | cathedral-open_1 |
|---|---|---|---|---|
| Seed | 1867 | 1868 | 1869 | 1870 |
| K1 section outline within 1 px (≥ 95%) | 99.2% | 98.8% | 99.2% | 97.7% |
| K2 interior pixels outside the mask (0) | 0 | 0 | 0 | 0 |
| K2 mask covered (≥ 99.5%) | 100% | 99.997% | 100% | 100% |
| K3, the stone only (≤ 5%) | **11.9%** | 3.5% | **24.8%** | 2.1% |
| K3, every pixel (the old measure, reported) | 27.6% | 33.9% | 3.5% | 45.1% |
| Light across a face, walls (≤ 5%) | **40.1%** | **23.5%** | **45.5%** | **15.8%** |
| Light across a face, roof (≤ 5%) | **11.5%** | **20.5%** | **40.3%** | **13.2%** |
| Light across a face, floor (≤ 5%) | **10.7%** | **7.9%** | **12.2%** | **17.7%** |
| Lines kept, the section's (≥ 95%) | 97.5% | 97.5% | 99.5% | 99.9% |
| Lines kept, the placeholder's (reported) | 86.1% | 81.2% | 95.2% | 87.5% |
| K4 cars or people (0) | 0 | 0 | 0 | 0 |
| An interior was painted | yes | yes | yes | yes |
| Verdict | fail | fail | fail | fail |

- The two check corrections did what they were for. The lines gate passes on all four. K3 passes on two, and on
  those two the old measure would have said 34% and 45%.
- What stops every candidate is the light check, by a factor of 1.6 to 9 over its limit.

**What I see in each** (looked at one by one, at four times the size):

- `cathedral_0`: pointed arches, tall blue windows with plain panes, a pale chequered floor, two blocks of
  brown pews. The arches are drawn in two tones of stone. No cast shadows on the floor, no dark floor, no people.
  The pews at the lower edge are cut through by the opening's edge.
- `cathedral_1`: the weakest. The walls are shaded: a darker ochre inside each arch and under the vault. There is
  a dark arched doorway. The pews are a jumble of dark red blocks with near-black gaps, and the floor is broken
  paving, not a chequer. No people.
- `cathedral-open_0`: bright stained glass in red, cyan and orange, a clean pale chequer, few pews. The left wall
  is a visibly darker yellow than the right one, which is what K3 measures (24.8%). No people.
- `cathedral-open_1`: the cleanest. Even cream walls and vault drawn in line, navy windows with coloured panes, a
  red door, two blocks of pews, a regular pale chequer from edge to edge. I see no cast shadow, no dark corner
  and no shading from one side. A slightly darker band runs along the foot of the walls. No people.
- No painting has a dark floor, a beam of light, a person or a vehicle. The new prompt removed the navy floor of
  the first run. Odd objects: the dark doorway in `cathedral_1`, the red door in `cathedral-open_1` (neither is in
  the model).
- Outside the opening the painter again drew what it was not asked for (pews spilling past the wall in
  `cathedral_0`, a beige ground slab in `cathedral_1`). The mask cuts all of it away.

**Not in the map.** `python -m v2.bakeoff adopt K1` refuses ("the placeholder stays"). Nothing was rebuilt, and no
viewer screenshot was taken, because there is nothing new to show. `release/current.json` is the A build
`e1f764e945d7`, unchanged.

**The light check is now the open point.** `cathedral-open_1` passes every other check and looks evenly lit to
me, yet measures 13% to 18%. I did not look into where its squares differ, and did not change the check: its
definition was fixed before the run. Its known limits are in question 15, which is still open.

### Open questions after the second run

13 and 14 are answered (the corrections above). 15, 16 and 17 stay open. New:

18. **The light check** (question 15 again, now the only thing between `cathedral-open_1` and the map): look at
    `cathedral-open_1` yourself. If it is evenly lit to your eye, should the light check become a reported number,
    with K3 and your eye (K7) as the gates? I would first measure, at $0, where it differs on this painting.
19. **q0013** (palace, abbey, casemates, $0.90 worst case): I recommend not approving it yet. Its quote is for an
    H100 on the community cloud at Phase 2's times, and no painting has passed for the cathedral, which the spec
    asks for first (rule 6).
20. **A third cathedral run** is not quoted. It makes sense only after question 18 is settled: the prompt has
    done what it can for floors and shadows, and two of four candidates already pass K3.

### The light check looked into (13 November, $0)

Branch `v2-phase3-cathedral3`. **Spent: $0.** No pod, no quote. **The painting is not in the map.**

The owner's choice on 13 November 2026, asked what should happen next: "Investigate the check, free
(Recommended)", described as "I measure where the light check differs on this painting. If it is drawn detail, I
fix the check at its cause and put the painting in the map; if it is real shading, I report back."

**The short answer.** On `cathedral-open_1` the light check was reacting to drawn detail and to one misplaced
region, not to light. I fixed the check at those causes. The corrected check still fails the painting (walls
8.5%, vault 6.0%, floor 9.9%; limit 5%), so it is not adopted. What is left is mostly detail the check still
cannot tell from the surface, plus a small real shade on one wall that is under the limit by itself.

**What the old numbers were** (`v2/docs/img/test_cutaway_cathedral_light_open1.jpg`, left panel; levels are
luminance, 0 to 255):

| Face | Old result | Darkest squares | Lightest squares | Kind |
|---|---|---|---|---|
| Walls | 15.8% | 203: the plain panel of the short wall | 242 and 238: squares that hold a white window sill | drawn detail |
| Vault | 13.2% | 200 to 202: plain webs | 231 and 223: squares that hold the pale ribs | drawn detail |
| Floor | 17.7% | 206: the wall under the left window, drawn about 20 px (2.5 m) below the model's floor line | 250: a highlight at a pew's edge | misplaced region, drawn detail |

- The old check took the lightest tenth of each square as the surface's lit level. That is right for a pattern
  (a chequer shows its light tile in every square). It is wrong where something lighter than the surface is drawn
  on it in some squares only: a sill, a moulding, a rib.
- On the floor, 88% of the squares were already within 5% of the lightest one. The chequer itself is even.

**What I measured apart from the check**, on plain wall only (pixels inside a fill, away from every line):

| Place | Luminance |
|---|---|
| Short wall between the two shafts, top | 203 |
| Short wall, middle | 206 |
| Short wall, foot | 207 |
| Long wall, first bay and the band under the windows | 211 (208 to 212) |

- **This is real shading, and it is small.** The short wall is 2% darker than the long wall (K3 measured 2.1%),
  and it darkens by 2% from its foot to its top. Its darkest patch against the long wall is 3.9%. All under 5%.
- I found no cast shadow, no dark corner and no dark floor.

**The check, corrected** (`light_across` in `v2/bakeoff/cutaway_paint.py`; the limit is still 5%):

- **The surface tone.** Per face, the luminance that most of its material is drawn in (within 5%). On a
  two-tone pattern it is the lighter tone, if that is at least half as common as the darker.
- **Lighter detail.** In a square where at least a tenth of the material is at the surface tone, what is lighter
  than that tone's band is a thing drawn on the surface. The square's level is the lightest tenth of the rest.
- **A square without the surface tone** is measured as before, by its lightest tenth. So a gradient, a cast
  shadow, a dark corner or a wall in a darker tone is measured as before.
- **A wall drawn past the model's line.** A square that does not hold its own face's tone, is at the
  neighbouring face's tone, and joins that face, is measured with that face.
- **Ink is left out**, as in K3: a pixel darker than a neighbour by a line step.
- New tolerances: the tone band is the limit itself (5%); "a tenth" is the same tenth as the lit level's; "half
  as common" for the lighter tone of a pattern.

**Its power, on synthetic images** (`v2/bakeoff/tests/test_bakeoff.py`):

- All earlier cases hold: six patterns evenly lit measure under 1%; each fails with a gradient of 40% or 10% and
  with cast shadows 6.5 m and 3.5 m across.
- New, passing: a wall with pale shafts, a white sill and a darker plinth band; a vault with pale ribs; a wall
  drawn 0.75 m and 2.5 m below the model's line. The old measure reads over 5% on the first two.
- New, failing: each of those with a gradient (40%, 10%, across or down), a cast shadow, half the wall 12%
  darker, a beam of light; the wall's foot strip darker than the wall (7%, 15%, 30%); the wall's tone on the floor
  away from the wall; a floor fading to the wall's tone at its foot (a dark corner).
- **Limits, stated in the code and tested:**
  - A thing drawn in a tone within 5% of the surface's (a pilaster 4% paler than its wall) is not told from the
    surface, and counts.
  - On a pattern, a shade exactly as deep as the pattern's contrast (within 5%) is measured while it covers the
    lesser part of the face. It reads as the pattern when it covers most of it (four fifths in the test).
  - As before: a shade narrower than 2.5 m, and a shade in another colour, are not measured.

**All seven paintings, old and corrected** (walls / vault / floor; limit 5%):

| Painting | Old | Corrected | Light check | Other failing checks | Verdict |
|---|---|---|---|---|---|
| Run 1 `cathedral_0` | 32% / 15% / 11% | 27.6% / 21.9% / 7.6% | fails | K3 12.2% | fail |
| Run 1 `cathedral_1` | 28% / 20% / 6% | 27.6% / 24.5% / 3.9% | fails | K3 13.8% | fail |
| Run 1 `cathedral-open_0` | 36% / 18% / 13% | 29.5% / 22.2% / 8.3% | fails | K3 10.7% | fail |
| Run 2 `cathedral_0` | 40.1% / 11.5% / 10.7% | 36.4% / 6.4% / 9.0% | fails | K3 11.9% | fail |
| Run 2 `cathedral_1` | 23.5% / 20.5% / 7.9% | 23.4% / 21.6% / 7.9% | fails | none | fail |
| Run 2 `cathedral-open_0` | 45.5% / 40.3% / 12.2% | 47.6% / 9.1% / 9.0% | fails | K3 24.8% | fail |
| Run 2 `cathedral-open_1` | 15.8% / 13.2% / 17.7% | **8.5% / 6.0% / 9.9%** | fails | none | fail |

- **No verdict moved.** The visibly shaded paintings fail as before, on their walls, by 23% to 48%.
- Two single faces moved a lot, and I checked why:
  - Run 1 `cathedral_1`, floor, 6% to 3.9%: the old excess was a highlight. Its dark floor is navy, another
    colour, which this check never measured (a known limit). Its walls and vault still fail, and K3 fails.
  - Run 2 `cathedral-open_0`, vault, 40.3% to 9.1%: the dark ochre squares in the vault's region are now
    measured with the walls, whose surface tone in that painting is that ochre. The walls measure 47.6%.

**What still fails `cathedral-open_1`** (the right panel of the image):

| Face | Corrected | Darkest | Lightest | What it is |
|---|---|---|---|---|
| Walls | 8.5% | 204: the short wall's panel | 222 to 223: shafts and jambs drawn 4% to 5% paler than the wall | detail within 5% of the wall's tone (the first limit above), on top of the short wall's real 2% to 4% |
| Vault | 6.0% | 199: two webs | 211 to 212: other webs, next to the ribs | webs drawn in slightly different tones |
| Floor | 9.9% | 223 to 231: a handful of squares at the foot of the left wall that mix wall, pew and a little floor | 247: the lightest tiles | the misplaced wall again, where a square holds a little floor; 90% of the floor's squares are within 3.5% |

- I stopped here. Passing this painting would need one more rule (a thing narrower than a square is detail even
  when its tone is near the surface's). I could not define that rule without also weakening the check on
  chequers, whose tiles are as narrow as a shaft. Adding it only to pass this painting would be tuning.
- Seventeen squares in the floor's region are now measured with the wall, as intended (green in the image).

**Nothing else changed.** No painting was adopted (`python -m v2.bakeoff adopt K1` still refuses). The cutaway
layer was not rebuilt. No viewer screenshot was taken. `release/current.json` is the A build `e1f764e945d7`.
Results: `v2/docs/results/cutaway_K1.json` and `cutaway_K1_run1.json` (both measured again with the corrected
check).

**Still not verified for a painted cutaway:** the compose step in the browser, night windows on the cut
building, and the interior under the viewer's light. They need a painting in the layer.

**The painter's inventions in `cathedral-open_1`**, not in the model: a red door in the long wall, two blocks of
pews, the chequered floor, shafts and capitals, stained glass.

### Open questions after the light check

15, 16 and 17 stay open. 18 is now this:

21. **`cathedral-open_1`:** by direct measure its plain walls differ by 2% to 4%, under the limit. The corrected
    check still reads 6% to 10%, from pale shafts, webs and a handful of squares at a wall's foot. Three ways on:
    - keep the check as the gate and paint again (a third run is not quoted; the prompt could ask for shafts and
      walls in one tone);
    - make the light check a reported number for this landmark and gate on K3 (2.1%) and your eye (K7);
    - have me try the width rule, with the risk named above.
22. **The short wall's shade** (2% darker, 4% at its top): acceptable in the map if the painting is taken?


### In the map (13 November, $0)

Branch `v2-phase3-cathedral4`. **Spent: $0.** No pod, no quote. **The painting is in the map.**

**The owner's decision** (question 21), 13 November 2026. Asked "The cleanest cathedral painting
(cathedral-open_1) still fails the corrected light check (6-10% against 5%) because of stone detail drawn in
several tones; its real shading on plain wall is 2-4%. Which way on?", the owner answered: "Take it on my eye
(Recommended)". That option read: "Put cathedral-open_1 into the map, free. For painted cutaways the light check
becomes a reported number; wall tone (2.1%), outline and no-people checks stay as gates. I show you the viewer by
day and night".

**The rule, as changed. Nothing wider.**

- For a painted cutaway interior, light across a face is a reported number. It is still measured for every
  candidate and written to the results and to the adopted painting's record, with its 5% limit.
- The gates stay: K1 (the section's outline and lines), K2 (nothing outside the mask, the mask covered), K3 (wall
  tone on the stone, 5%), K4 (no vehicles, no people), K5, K6.
- **K7, the owner's eye, is now a recorded gate.** `v2/data/structures/cutaway_acceptances.json` holds, per
  landmark: the job, the run, the candidate, the hash of that candidate's file, the question, the owner's words
  and the date.
- `python -m v2.bakeoff adopt K1` takes the candidate the owner accepted. It refuses a candidate that fails a gate,
  and one without a recorded acceptance of that very file. The build refuses a painting whose record lacks the
  candidate, the run or the acceptance.
- The no-baked-shadow rule of every other layer is untouched (L5.1: 0 of 226 materials over 5%, worst 4.0%, as
  before).
- **One consequence to know.** Without the light check, the second run's `cathedral_1` also passes the gates
  (K3 3.5%). It is the visibly shaded one (light 23.4%). Only K7 keeps it out: `adopt K1 --candidate cathedral_1`
  is refused because no acceptance of it is recorded.

**Adopted:** `cathedral-open_1` of the second run (q0015, seed 1870, pod `1zj2z6jzs0dz39`), cut to the mask:
`v2/data/structures/cutaway_paintings/cathedral.png` (99 KB) and `cathedral.json` (its record).

| Check of the candidate | `cathedral-open_1` | Limit | Kind |
|---|---|---|---|
| K1 section outline within 1 px | 97.7% | ≥ 95% | gate |
| K2 interior pixels outside the mask | 0 | 0 | gate |
| K2 mask covered | 100% | ≥ 99.5% | gate |
| K3 wall tone, the stone only | 2.05% | ≤ 5% | gate |
| K3 sides too small to measure | 0 | 0 | gate |
| Lines kept, the section's | 99.9% | ≥ 95% | gate |
| K4 vehicles, people | 0, 0 | 0 | gate |
| An interior was painted | yes | yes | gate |
| K7 the owner's eye | "Take it on my eye (Recommended)", 13 Nov 2026 | recorded | gate |
| Light across a face: walls / vault / floor | 8.5% / 6.0% / 9.9% | 5% shown | **reported** |

**Rebuilt** for the test area: the cutaway layer, the release and every check after them (`python -m v2.build test
g3`). **56 of 56 stages, 248 gates, 0 fail.** No threshold was changed. Release `f39c120ae255`.

| Gate on the painted tiles (cathedral) | Result | Limit | With the placeholder |
|---|---|---|---|
| K1a cut outline within 1 px | 97.2% | ≥ 95% | 99.07% |
| K1b cut and inside pixels outside the model | 0 | 0 | 0 |
| K2a painted interior pixels outside the opening mask | 0 | 0 | 0 |
| K2b mask covered | 100% | ≥ 99.5% | 100% |
| K2c, K2d, K2e the mask against the model and the paint input | 0; 99.997%; 0 | 0; ≥ 99.5%; 0 | the same |
| K3 wall tone on the stone | 2.0% | ≤ 5% | 0% |
| K3 sides too small to measure (new gate) | 0 | 0 | not run |
| K4 vehicles / people, on 6 paint inputs and cutaway tiles | 0 / 0 (highest score 0.014 / 0.008) | 0 | 0 / 0 |
| K5a, K5b, K5c depth | 0.5 cm; 0; 0 | ≤ 1 cm; 0; 0 | the same |
| K6b cutaway pixels where layer 5 shows another surface | 0 | 0 | 0 |
| In the browser: K6v off after on, 13:00 and 23:00 | 0, 0 | 0 | 0, 0 |
| K2v interior pixels outside the tiles' mask | 0 of 31,208 | 0 | 0 of 31,208 |
| K2v-frame, K2v-colour | 0 of 1,920,000; 0 of 788,607 | 0 | the same |
| K5v vehicles, labels | 0 of 174,232; 0 of 4,248 | 0 | the same |

- Every other number of the g3 set is the same as before, to the last digit, apart from the three speed
  measurements (first view 0.096 s, panning 91 fps and 92 fps in tunnel view).
- K1a fell from 99.07% to 97.2%: the painter's line along the cut is a little softer than the code's.

**Looked at in the viewer** (headless Chrome on this laptop, 1600 × 1000, 24 June). Sheets:
`v2/docs/img/test_cutaway_cathedral_map.jpg` (day, golden hour, night, and the cutaway off) and
`test_cutaway_cathedral_map_wide.jpg` (in place in the map, tunnel view, far zoom).

| What | Result |
|---|---|
| Cutaway off, this build against the build before (`e1f764e945d7`): pixels that differ | **0 of 1,600,000** in each of 6 frames: day and night at 1:1 and 2:1, far zoom, tunnel view |
| Opening pixels in view (1:1, unlit colours) | 35,545 |
| of these, exactly the painting's colour at its own map pixel | 31,208 |
| of these, hidden by a tree or a nearer building (same as with the cutaway off) | 4,337 |
| of these, anything else (a gap, a wrong colour) | **0** |
| The painting moved by 1 px any way: pixels that still match | under 2,400 (so it is not off by one) |
| Pixels the cutaway changes outside the cathedral's own outline (halo, bleed onto neighbours) | **0** |
| Pixels it changes outside the opening, inside the outline | 344: the ink line of the cut's rim on the kept shell, within 2 px of the opening. The placeholder had the same |
| Tunnel view with the cutaway on: pixels the cutaway changes | 31,564; it shows through the fade |

**The light on the interior** (lit level against the unlit colour, pale stone only):

| Hour | Walls | Vault | Floor | Kept outside stone, median |
|---|---|---|---|---|
| Day, 13:00 | 0.48 | 0.48 | 0.49 | 0.85 |
| Golden hour, 21:18 | 0.80 | 0.75 | 0.82 | 0.84 |
| Night, 23:15 | 0.28 | 0.24 | 0.30 | 0.31 |

- **By day the interior is in full shade**, at half its painted brightness. The cream stone reads grey-mauve and
  the pale chequer reads grey. It is legible, but dull beside the sunlit towers, and in the wide shot the opening
  is a dark hole. This is the missing shadow of the opening (question 10), not the painting.
- **At golden hour it is as bright as the outside** and warm. This is the hour at which it reads best. The earlier
  statement "in shade at every hour" is true of the sun's shadow; at 21:18 there is almost no direct sun left, so
  inside and outside are lit alike.
- **By night** it is a dim blue room, as dark as the walls outside. Nothing in it glows.
- **Night windows.** The windows that stood in the removed slice are not lit. The kept ones (towers, apse, the
  wings) are lit as before. The painted stained glass does not glow: it is colour, not a window of layer 10.

**What looks wrong, said plainly:**

- **Outside and inside disagree.** The kept outside of the cathedral has the facade rule's house windows with red
  shutters, lit like a block of flats at night. Next to it the interior shows tall pointed stained-glass windows.
  This is the most visible fault, and it is the outside's (section 6), not the painting's.
- **The pews are too big.** Each block is four or five benches, each several metres long and about as tall as a storey
  of the houses beside it. A nave of this size would hold many more, smaller rows.
- **The red door** is not in the model. In the map a tree stands in front of it; a few red pixels show.
- **Trees hide the lower right** of the opening: one block of pews and the door. About 2,100 of the opening's
  pixels are behind trees, 2,200 behind nearer buildings.
- **The interior is softer than the code art.** Its lines are smoothed where the code's are hard-edged. At 2:1
  it shows; at 1:1 it does not.
- **The opening is small:** 27 m by 20 m of one nave bay, seen from the east. No columns, no aisles, no choir.
- **Far zoom.** With the cutaway on, the view leaves the merged far tiles for the separate layers (question 11):
  914,742 of 1,600,000 pixels change, most by 4 of 255, and 31,816 by more than 30, nearly all outside the
  cathedral. The cathedral itself reads as a dark notch with blue windows.
- Seams: none found. The cut's red-brown rim is continuous, and the painting meets it without a gap.
- Not from this change: at the area's west edge a red-roofed block stands half outside the area with a dark sliver
  above it. It is there with the cutaway off too.

**Stopped afterwards:** both viewers and the browser. Nothing is left running.

**Not verified:** on a phone or with a real GPU window (headless only); with the simulation running (frames were
taken with `nosim`); the other seasons and snow on the painted interior; the palace's and the abbey's cutaways
beside it, beyond the gates.

### Open questions after the painting went in

21 is answered (taken on the owner's eye). 22 is answered by the same choice (the short wall's 2% to 4% shade is
in the map). 15, 16 and 17 no longer decide anything for the cathedral.

23. **K7 at fixed views.** You accepted the painting from its sheet. Look at it in the viewer by day, golden
    hour and night (section 8). If it does not hold up, removing `cutaway_paintings/cathedral.*` and the
    acceptance brings the placeholder back at the next build.
24. **The interior in shade by day** (question 10 again, now with a painting): accept, or have the opening lit?
    A cheap honest option is to light the opening's faces by the sky only (no sun shadow) at every hour, which is
    what golden hour looks like now. It needs your decision, since it is a light rule.
25. **The cathedral's outside** (house windows, shutters): fix it in code before the other landmarks are painted?
    It is free, and it is the most visible fault next to the painted interior.
26. **q0013** (palace, abbey, casemates): still not approved, and it should not be approved as written. It is
    quoted for a community H100 at Phase 2's times. A correct quote would be for the A100 SXM on the secure cloud
    ($2.19/h and $0.02/h disk when last read; the live price is read again first), at the second run's measured
    times: 23 s to ssh, about 6 minutes of setup, 279 s to load the model, 22 s a painting. For the palace and the
    abbey, 2 views × 4 candidates: about 14 minutes, expected about $0.52, worst case about $0.91 at the same
    75% margin. The casemates cannot be in it: their cutaway and paint input are not built. Each landmark also
    needs its own prompt (only the cathedral's exists), and both have floor slabs, which the painter has not been
    tried on. I recommend deciding 23 to 25 first. Phase 3 has $7.11 of $8 left.


## 10. Sky light in cutaways, church facades, q0013 dropped (13 November, $0)

Branch `v2-phase3-facades`, into `v2`. **Spent: $0.** No pod, no quote made, none approved.

The owner decided three things on 13 November 2026. Each is done as decided and nothing wider.

| Question | The owner's words | Done |
|---|---|---|
| 24 (and 10): the interior in shade by day | "Light by sky only" | The opening is lit by the sky only |
| 25: the cathedral's outside | "Fix facades first" | Places of worship have church facades, in code |
| 26: quote q0013 | "Drop q0013, requote later" | Released in the ledger, unspent; no new quote |
| 23: K7 at fixed views | The owner merged PR #10 after seeing its screenshots | Closed |

**Rebuilt** for the test area (`python -m v2.build test g3`): **57 of 57 stages, 273 gate entries, 0 fail** (248
before; the 25 new ones are F16 to F19, L5.7 and K3v-sky). No threshold was changed. Release `cc4d856c63d4`.

### 10.1 The opening is lit by the sky only

**The rule.** For the pixels inside a cutaway's opening (the cut and the inside faces): the hour's sky light at one
level, the same on every face. No cast shadow, from the building's own kept shell or from anything else. No sun,
no golden-hour fill and no moon by the face's direction. The hour's colour stays, and the night takes its share of
colour out as everywhere. Spec: `v2/docs/specs/landmark-cutaways.md` rule 3 and "In the viewer".

**Where.** In the viewer's light pass (`LIGHT_CUT_FS`, `v2/web/src/gl/shaders.ts`), which is used only while a
cutaway is on. The opening is told by the cutaway tiles' own `k`. No tile changed for it: nothing is baked.

**The numbers chosen** (`v2/config/light.json` "cutaway"). The light is the sky light (`sun.ambient` 0.58 times
the hour's sky colour) times a level:

| Hour | Sky light | Level | Light on the opening | Why |
|---|---|---|---|---|
| Day | 0.58, white | **1.47** | **0.85** | The kept outside stone's median at 13:00 was 0.85 (section 9). The plain sky light, 0.58, is still the shade's level |
| Golden hour | 0.78, warm | 1.08 | 0.84 | The outside stone's level at 21:18 |
| Night | 0.25, deep blue | 1.22 | 0.31 | The outside stone's level at 23:15 |

Between them the level moves with the sky's colour, without a step (unit test).

**Measured** (gate `check_cutaways_view`, 24 June, 1:1, with the look pass and the night lights off so that a pixel
is its colour times its light; lit level is lit over unlit luminance, pale surfaces, median):

| Cathedral | Interior, before | Interior, now | Kept outside stone |
|---|---|---|---|
| Day, 13:00 | 0.494 | **0.853** | 0.835 |
| Golden hour, 21:18 | 0.824 | **0.845** | 0.843 |
| Night, 23:15 | 0.304 | **0.306** | 0.270 |

- The palace's and the abbey's placeholder interiors measure the same (0.854, 0.844, 0.305 and 0.854, 0.843,
  0.309) beside outside levels of 0.89 / 0.86 / 0.29 and 0.90 / 0.86 / 0.29.
- At the cathedral view at 2:1 the interior's level by day lies between 0.851 and 0.854 for 90% of its pale
  pixels: one light. The outside stone in that tighter view measures 0.755 by day (more of it is turned from the
  sun), 0.843 at golden hour, 0.261 at night.
- The outside level differs from section 9's 0.85 / 0.84 / 0.31 because these frames have no window glow and no
  look pass, and frame another part of the building.

| Gate | What | Result |
|---|---|---|
| K3v-sky-even, 3 landmarks x 3 hours | Opening pixels that are not their unlit colour times the one sky light, by more than 1 of 255 | **0** of 31,208, 32,416 and 43,691 |
| K3v-sky-outside, 3 x 3 | Pixels the rule changes outside the opening (the same frame with `?off=cutlight`) | **0** in all 9 |
| K6v-off, 7 views | A view after the cutaway was on and off against one that never had it on | 0 |
| By hand, cathedral view at 2:1, day, golden hour, night, with and without the look pass | Pixels the rule changes outside the opening | **0** in all 6; it changes 112,671 to 124,832 inside |

Sheets: `v2/docs/img/test_cutaway_cathedral_skylight.jpg` (before and after at day, golden hour, night) and
`test_cutaway_cathedral_skylight_wide.jpg` (in the map at 1:2, and the cutaway off).

### 10.2 Church facades

**Which buildings**, from the data (`v2/data/scene/worship.py`; spec `v2/docs/specs/facades.md` rules 14 to 20):
OSM outlines tagged `building=church`, `cathedral` or `chapel`, or `amenity=place_of_worship` (a new fetch,
`fetch_osm_worship`, 52 elements over the commune); the landmark list's cards of category "church"; an entry in
`landmark_styles.json` with `"kind": "place_of_worship"`. Ten in the test area:

| Building | Source | Share of the ACT building | Church windows | House windows replaced |
|---|---|---|---|---|
| Notre-Dame Cathedral | `landmark_styles.json` (OSM maps it as a point only) | all | 65 | 259 |
| Sainte-Cunégonde, Clausen | OSM way 48994118 | 97% | 24 | 84 |
| Saint-Alphonse | OSM way 48995724 | 94% | 30 | 155 |
| Saint-Mathieu, Pfaffenthal | OSM way 51071557 | 91% | 15 | 61 |
| A church beside St Michael's, no name | OSM relation 11371126, `building=church` | 90% | 41 | 175 |
| Al Kapell, Rham plateau | OSM way 48994393, `building=chapel` | 97% | 14 | 64 |
| St Michael's | OSM way 48994777 | 69% | 9 | 40 |
| Trinity Church | OSM way 52469831 | 38% | 19 | 158 |
| St Jean du Grund (the abbey's church) | OSM way 32858724 | 14% of the abbey's building | 23 | 73 |
| The hospice's church, Pfaffenthal | OSM way 162041608 | 8% | 9 | 58 |

- 873 walls are church walls. 1,127 house windows and 20 shop fronts went; 249 church windows came.
- Where the church is part of a larger ACT building (the last four), only the walls in the OSM outline changed.
- Not taken: OSM nodes (prayer rooms in houses are mapped so) and one site relation (the abbey's cultural centre,
  tagged `amenity=place_of_worship`: a list of buildings, not an outline).
- The Saint-Quirin chapel has no ACT building.

**What they get.**
- **Windows:** one row of tall arched windows per wall, 1.3 m wide, from 2.6 m above the wall's bottom to 1 m
  under the eave, 9 m at most; one per bay of 4.5 m, and between buttresses one per gap. Round-headed; pointed on
  the cathedral (its entry in `landmark_styles.json`). Leaded dark glass with some stained panes, a stone frame.
  No shutters.
- **Walls:** stone (the kind "place_of_worship" in `landmark_styles.json`); the abbey's church keeps the abbey's
  white, its own entry. No floor cornices, no banded ground floor.
- **Doors:** planks under a round arch, no fanlight. No shop fronts.
- **Night:** a church is lit or dark as a whole. Lit, its windows show a dim stained-glass glow (0.42 of a house
  window's strength, no halo). On the three churches that are a church all over, the light the night pass adds
  went from a mean (87, 70, 43) of 255, warm, over 37,983 pixels to (54, 46, 42) over 9,392.
- ACT gives many church walls as triangles, which hold no tall window. A church's walls in one plane are joined
  first (489 joined walls).

**Gates.** F16 to F19 on the layout, L5.7 on the drawn tiles: 0 shutter pixels, 0 shop front pixels and 0 window
glass pixels in a house window's colour on the buildings that are a church all over (3 buildings, 258,160 pixels,
10,607 of them church glass). F3 (straight rows) holds on church walls: one sill line, one top line.

**Every other pixel is as it was.** Measured against the build before (`f39c120ae255`):

| What | Result |
|---|---|
| Tile files of ground, relief, water, transport, structures and trees, all zooms | all identical, byte for byte |
| Layer 5 tile files without a church pixel | 228 of 228 identical |
| Layer 5 tile files that differ | 50, every one holds a church |
| Viewer, cutaway off, day and golden hour: 16 frames at 1:2 to 2:1 (the churches, Grund, the Bock, the facade view, tunnel view) | 3,874 to 176,832 pixels differ per frame; **all on church buildings**, 0 elsewhere |
| The same by night: 13 frames | all on church buildings but for 0 to 701 pixels per frame within 3 m of one (the halos of the house windows that are gone); 0 further away |
| Night window list (`windows.bin`) | 19,318 of 19,727 rows unchanged at the same place; the 409 changed rows are all on a building with a church part; 97 church windows added at the end |
| Far zoom (the whole area, merged tiles) | 263,172 pixels differ by day; 12,222 on a church, the rest by 19 of 255 at most |

- The far zoom's merged tiles are lossy: 16 of them hold a church and were coded again, so their other pixels
  moved by a few levels. The 17 merged tiles without a church are identical.
- To keep it so, each church wall remembers how many openings the house rule had given it. A window's glass tone
  and a night window's seed go by the opening's place in the order of all openings; without the count every
  later window in the map would have changed tone and every later night window its chance to be lit.

Sheets: `v2/docs/img/test_church_facades.jpg` (the cathedral, St Michael's, St Jean du Grund; day and night, before
and after) and `test_church_facades_others.jpg` (the other five that the camera sees well).

### 10.3 q0013 is dropped

- Released in the ledger on 13 November, unspent and never approved. No replacement quote was made. A fresh quote
  for the palace and the abbey comes only after the church facades and the light rule are settled.
- **One change to the ledger's rule, needed for it.** `release` took only approved quotes; q0013 was never
  approved, and the command refused. It now also takes an unapproved quote: the quote can then no longer be
  approved or run. It cannot make a spend possible. Unit test and `v2/docs/specs/ledger.md` updated.
- Ledger: valid. Phase 3 line: $8 cap, $0.8928 spent, $0 committed, $7.1072 left.

### 10.4 Gates, with the numbers near their limits

| Check | Before | Now | Limit |
|---|---|---|---|
| Build stages | 56 of 56 | **57 of 57** (the new fetch) | all |
| Gate entries, failing | 248, 0 | **273, 0** | 0 |
| Line score, building edges | 96.33% | **96.35%** | ≥ 95% |
| Line score, window rows | 99.84% | 99.84% | ≥ 95% |
| Shadows at 10:00, 13:00, 16:00 | 98.6%, 99.63%, 97.18% | the same | ≥ 97% |
| Seams, ground / water / transport | 2.645 / 1.502 / 1.395 | the same | ≤ 3 |
| No baked shadows, worst material | 4.0% | 4.0% | ≤ 5% |
| K1a cathedral cut outline; K3 wall tone | 97.2%; 2.0% | the same | ≥ 95%; ≤ 5% |
| First view; panning | 0.096 s; 90.6 fps | 0.092 s; 92.2 fps | ≤ 0.5 s; ≥ 60 |

- The first build of this change failed the no-baked-shadows gate on one material: the glass of Saint-Alphonse,
  0.48 in shade against lit. The cause was the drawing, not light: stained panes were lighter and darker than
  plain ones, and a wall's few panes gave another median than the next wall's. Every pane is now as light as the
  plain glass and differs in colour only. The limit was not touched.
- The window-row score samples the sill of an arched window, not its top: an arch has no straight top.

### 10.5 What still looks wrong

- **The church windows are a rule, not the buildings' own.** Every wall gets the same tall window. The cathedral
  has no rose window, no tracery, no portals; its towers have one slit a side and no belfry openings. Low walls
  get small arched windows that read as oddly small beside the tall ones.
- **Stained glass by day is muted.** Every pane has the plain glass's brightness, to keep the shadow gate honest,
  so amber reads as brown. Inside the cutaway the painted glass is far brighter than the outside's.
- **Blank church walls.** Saint-Alphonse's upper nave wall and some of St Michael's walls are flagged as party
  walls and get nothing. St Michael's own walls show few church windows to the camera.
- **St Jean du Grund's nave windows do not glow at night.** That wall's outward direction is taken from the
  centre of the whole abbey building, which lies on the other side, so the night list leaves it out. The same
  was true of its house windows.
- **The unnamed church beside St Michael's** (OSM relation 11371126, noted there as "transformation into
  flats?") was a pink house and is now a stone church with tall windows. It is what the data says; it may be wrong.
- **Mixed buildings.** Trinity Church and the hospice's church are stone only on their church walls; the join
  with the rest of the building is abrupt.
- **Night:** at 23:15 about half the churches are dark by chance; the glow is in square panes and reads as
  coloured tiles at 2:1.
- **The interior's light is flat.** By day it is as bright as sunlit stone on every face, so the opening has no
  depth beyond the painting's own lines; at golden hour it is strongly yellow.
- From section 9, unchanged: the pews are too big, the red door, trees over the lower right, the soft painting.

### 10.6 Not verified

- On a phone or with a real GPU window (headless Chrome on this laptop only).
- With the simulation running (frames were taken with `nosim`).
- Other seasons and snow on the lit opening and on the church facades.
- The church rule outside the test area: the commune was not built.
- Whether each tagged building is a church in fact (no photographs were consulted).

### 10.7 Open questions

23 to 26 are closed (above). New:

27. **The unnamed church beside St Michael's** (OSM relation 11371126): keep it as a church, or enter it in a
    small exceptions list as a house?
28. **St Jean du Grund** keeps the abbey's white. Stone, as the other churches, or white?
29. **Stained glass by day:** muted so that the shadow gate holds. Accept, or give church glass its own measure
    in that gate so the panes can be bright?
30. **Night:** a church is lit as often as a home's window (55% in the evening, 18% late). Always lit, always
    dark, or as it is?
31. **The night level of the opening** (0.31, the outside's level) leaves the nave a dim blue room. Brighter at
    night, as if lit from inside?
32. **Window numbering.** Glass tones and night seeds go by an opening's place in the order of all openings,
    which is why church walls must remember the house rule's count. At Phase 4 the whole city is built anew: key
    them by building and wall then, and drop the count? Every window's tone would change once.
33. **Other landmarks' facades** (the palace and the rest of the landmark list) are not covered by this rule and
    were not touched. Which next, if any?
34. **A fresh quote for the palace and the abbey:** say when.
