# Landmark cutaways ("slice of cake")

**Status:** built for three landmarks on the test area (Phase 3): the cuts as data, the slice geometry from the 3D
model, a small layer of tiles, the inputs of the painting, the viewer's toggle, and checks K0-K6 (stages
`layer_cutaways`, `check_cutaways`, `check_cutaways_view`). **The cathedral's interior is painted** (the second
run's `cathedral-open_1`, in the map since 13 Nov 2026 on the owner's eye, K7: see "The painted step"). The palace
and the abbey have a **code placeholder interior**; their paintings are not approved (paid from the Phase 3 line,
$8 cap, quoted in the ledger and approved by the owner before any spend). **The opening is lit by the sky only**
(the owner's decision of 13 Nov 2026: rule 3 and "In the viewer"). Not built: the Bock casemates.

**Purpose.** Famous buildings shown cut open in place on the map, not in a modal: the visitor sees a slice taken out
of the building, with its interior visible through the cut, at its real place and scale. First four: the Bock
casemates, Notre-Dame Cathedral, the Grand Ducal Palace and Neumünster Abbey (all four are inside the test area).

**Inputs.**
- The building's 3D model (ACT LoD2 in the scene; for the Bock casemates, the gallery data of tunnel-view.md).
- A cut: one or two vertical planes per landmark (data, `v2/data/structures/cutaways.json`: plane origin, normal and
  extent, chosen once by hand so the cut shows the best-known rooms: the cathedral's nave, the palace's state rooms,
  the abbey's cloister, the casemates' galleries).
- The interior: an AI-painted cutaway image per landmark, made from an unlit render of the cut model (the cut faces
  and the inside walls from the model, flat colours) with a reference of the real interior (public photos, used as
  reference only), in the inked style, unshadowed.
- The palette and the bake-off winner's style for the outside.

**Rules.**
1. **The cut comes from the model.** The removed slice is the model clipped by the cut planes; the cut faces are the
   model's section. Nothing is drawn where the model is not.
2. **The interior stays inside the cut.** The painted interior is masked to the cut's section and the inside faces
   it exposes (the 3D outline of the opening, the POC cut rule with 0 px growth); it never covers the outside of the
   building or the map around it.
3. **No baked light.** The interior is painted evenly lit, as layer 5; layer 9 lights it. **The opening is lit by
   the sky only** (the owner's decision of 13 Nov 2026, in the owner's words: "Light by sky only"): every pixel of
   the opening (the cut and the inside faces) gets the hour's sky light at one level, the same on every face. No
   cast shadow falls on it, from the building's own kept shell or from anything else, and no light comes by the
   face's direction (no sun, no golden-hour fill, no moon). The hour's colour stays: warm at golden hour, a deep
   blue at night, so the interior belongs to the scene. Nothing outside the opening changes, and nothing at all
   with the cutaway off. The no-baked-shadow rule of every other layer is untouched.
4. **Nothing that moves.** No people, cars or animals painted inside or outside (principle 5); the visitors and
   events are code layers.
5. **In place.** The cutaway replaces that building's pixels in layer 5 (or a small layer above it) with its own
   depth, so vehicles, labels and trees are depth-tested against it as against any building. A toggle (or a hover)
   shows it; off, the building is whole.
6. **Prove one, then three.** One landmark first (the cathedral); the other three only after the owner approves it.

**Checks** (phase 3, gates on the test area).
- **K1** The cut matches the 3D model: the drawn cut's outline is within 1 px of the projected section of the model by
  the cut planes over ≥ 95% of its length (the line score of brief 6); 0 cut pixels outside the model's outline.
- **K2** The interior stays inside the cut: 0 interior pixels outside the opening's mask; ≥ 99.5% of the mask
  covered.
- **K3** No baked shadows: the shadow detector of brief 5 on the interior (sunlit vs shadowed sides of the same
  material within 5%). In the viewer the opening is lit by the sky only (rule 3): every opening pixel is its unlit
  colour times one sky light, at 13:00, golden hour and night, and the rule changes 0 pixels outside the opening
  (K3v-sky, below). On a painted interior "the
  same material" is the face's own: the stone of a wall, not its windows' glass and not the ink drawn on it
  (owner, 13 Nov 2026; see "The painted step").
- **K4** No cars or people: the vehicle detector (OWLv2, as #9) on every input, reference and output at
  threshold 0.1, plus a person query ("a person", "people"): 0 detections.
- **K5** Depth: the cutaway's depth equals the model's (cut faces and inside walls) per pixel (≤ 1 cm); vehicles and
  labels depth-tested against it (as C4).
- **K6** Off means off: with the cutaway off, the building's pixels equal layer 5's (0 differ).
- **K7** (owner) the four cutaways at fixed views. The owner's eye is a gate of every painted interior: it is
  recorded per landmark with the owner's words and the date (`v2/data/structures/cutaway_acceptances.json`), and
  no painting is put into the map without it (see "The painted step").

**Cost.** Estimated in `v2/docs/PHASE2_QUOTE.md` as a separate Phase 3 item (not part of the bake-off total).

## Built (Phase 3, $0)

Code: `v2/layers/cutaways.py`. Data: `v2/data/structures/cutaways.json`. Checks: `v2/checks/cutaway_checks.py`.
Numbers: `params.json` "g3", keys `cutaway_*`. Colours: palette `cutaway.*`.

**The three cuts** (each documented in cutaways.json, with the reason):

| Landmark | Scene building | Planes | What it opens |
|---|---|---|---|
| Notre-Dame Cathedral | `ACT_e92ec91a…` | 2: along the nave's middle (facing east), across it 7 m short of the north front (facing south) | The east half of the nave, between the towers and the north front |
| Grand Ducal Palace | `ACT_78c0048b…` | 2: a quarter taken out towards the camera, its point in the main wing (facing east and south) | The main wing and the middle wing in section, with their floors |
| Neumünster Abbey | `ACT_221c9194…` | 2: along the middle of the church (facing the camera), and the side of a passage as wide as the court | The church lengthwise, the cloister's court and wing, the block in front in section |

A plane is an origin, a normal into the removed slice and an extent along it. The slice is what lies in front of
every plane, within every extent, above the floor. The buildings are found from the landmark's place (the footprint
that holds it, or the nearest within a stated distance); check K0 holds the list to that.

**Thickness.** ACT's model is a hollow shell, so a section would have no area. It gets a nominal thickness:
walls 0.8 m (in plan, from the footprint inwards), roofs 0.4 m (straight down), slabs 0.3 m at the facade layout's
floor lines (ground + 3.6 m, then every 3.0 m; none in the cathedral, none in the abbey's church). The floor is at
the landmark's floor level; below it the model is solid. Under a roof steeper than 80° (a spire) the model is solid.
A wall that stands on a lower roof (a tower's side above a nave) keeps ACT's one surface, without thickness.

**The layer.** One tile set per landmark, in the release's tile coding, above layer 5:
- colour: the kept outside exactly as layer 5 draws it (method A's materials); the cut faces and the inside faces in
  five flat palette colours with ink where surfaces meet. This is the placeholder a painting replaces;
- depth and normals of the cut model; ids (cut and inside faces have classes of their own, 40-44);
- `k`, what each pixel is: outside, cut, inside wall, inside roof, floor, slab, other building. The **opening mask**
  is cut + inside wall + inside roof + floor + slab;
- other buildings where they are nearer than the cut model or seen through the slice: layer 5 holds only the nearest
  building per pixel, so the cutaway brings what its landmark hid;
- `index.json`: per landmark the building ids it replaces, its planes, tiles and pixel counts.
Nothing is drawn outside the whole landmark's own silhouette.

**Paint inputs** (`paint/<name>.*`): the unlit render of the cut model alone on paper, 1024 × 1024 px at 0.125 m per
pixel (one image pixel per map pixel), the opening mask, the whole model's outline, the geometry behind every pixel,
and a JSON with the frame.

**Previews** (`v2/docs/img/test_cutaway_<name>_placeholder.jpg`): the whole building beside the cut one.

**Checks as built** (`python -m v2.build test check_cutaways`; all gates unless marked):

| Id | What is measured | Test area |
|---|---|---|
| K0 | The listed buildings are the scene's at the landmark's place | 3 of 3 |
| K1a | Line score of brief 6 on the model's section (raw ACT triangles cut by the slice's faces, every 0.25 m): drawn line within 1 px, >= 95% | 100%, 100%, 99.8% |
| K1b | Cut and inside pixels outside the whole model's outline (0 px growth): 0 | 0, 0, 0 |
| K2a, K2b | Interior pixels outside the opening mask: 0; mask covered >= 99.5% (the placeholder today, a painting later) | 0; 100% |
| K2c, K2d | The mask against the model worked out a second time, per pixel: mask pixels that are not an inside face or a section within 1 cm: 0; the model's own opening in the mask >= 99.5% | 0; 100%, 99.99%, 99.93% |
| K2e | Opening pixels of the tiles missing from the paint input's mask, or at another depth: 0 | 0, 0, 0 |
| K3 | Shadow detector on the interior: median luminance of one kind of face turned different ways, and to and away from the photo's sun, within 5%. A painted interior: on each face's own material only, and no side without enough of it to measure | 0% (flat colours) |
| K4 | OWLv2 on the paint inputs and the cutaway tiles: vehicles, then "a person", "people": 0 at 0.1 | 0; highest score 0.012 |
| K5a | Cut pixels: distance of the depth from the slice's faces <= 1 cm | 0.5 cm (the tiles store whole cm) |
| K5b | Cut and inside pixels not on the model's surface within 1 cm: 0 | 0, 0, 0 |
| K5c | Kept outside: depth differs from layer 5's by > 1 cm where layer 5 shows the same surface: 0 | 0 of 363,000 |
| K6a | Files of the cutaway layer in layer 5's folder: 0 (a layer of its own; no stage writes into layer 5) | 0 |
| K6b | Cutaway pixels where layer 5 shows neither a replaced building nor another building in front: 0 | 0, 0, 0 |
| K-ground (report) | Opening pixels the ground layer covers | 0, 0, 0 |

**On a painted landmark** the same stage runs the same gates on the painted tiles: K2a, K2b, K3 (on each face's
own material) and K4. K7 is recorded apart (below). The numbers of the painted cathedral:
`v2/docs/PHASE3_REPORT.md` section 9, "In the map".

## The painted step

Code: `v2/bakeoff/cutaway_paint.py` (inputs, checks, `adopt`), `v2/layers/cutaways.py` (`write_painting`,
`load_painting`, `paint_into`). Job K1 in `v2/bakeoff/jobs.py`. Both runs: `v2/docs/PHASE3_REPORT.md` section 9.

**Candidates.** Four per landmark: the cut render as built and the same render with its inside faces cleared to
paper (ink lines and the section kept), two seeds each, four seeds in all. The painter draws the whole frame; the
painting is cut to the opening mask (rule 2).

**Checks of a candidate** (`python -m v2.bakeoff check K1`; thresholds are the gate's own, `params.json` g3):

| Id | What is measured | Limit |
|---|---|---|
| K1 | Line score of the model's section on the painting cut into the render | >= 95% |
| K2a | Interior pixels outside the opening mask | 0 |
| K2b | Share of the mask the painter drew on. Unpainted: a pixel of paper's colour, or of the painting's own background, in a patch that holds a 7 x 7 px square | >= 99.5% |
| K3 | The gate's shadow detector on the painted interior, on each face's own material (a wall's stone, not its glass or ink). A side of a face with under 150 px of its material to measure fails | <= 5%; 0 sides |
| Lines kept | The cut's outline: the section's lines inside the opening (a cut face on either side) with a drawn step within 1 px. The placeholder's own construction lines (floor against wall, wall corners, roof against wall) are reported, not gated: a painted interior may stand a pew or a column in front of them | >= 95% of the section's |
| K4 | OWLv2 on the inputs, the paintings and the composites: vehicles, then people | 0 |
| Painted at all | The interior moved from the placeholder (share changed >= 25%, drawn detail >= 5%) | both |
| K7 | The owner's eye on this painting, recorded (below). Needed to put it into the map, not to pass the table above | recorded |

Reported with them, with its limit shown, **not a gate** (the owner's decision of 13 Nov 2026, below):

| What | What is measured | Limit shown |
|---|---|---|
| Light across a face | Per kind of face, on its surface: the largest fall of the level between two 16 px squares. A square's level is the lightest tenth of its material; where the face's surface tone shows in the square, what is drawn lighter than it is left out. A square at a neighbouring face's tone that joins that face is measured with it | 5% |

**K3 and the lines, corrected on 13 Nov 2026** (the owner's choice, "Correct both, free", made before the second
run; the limits are unchanged):
- K3 took the median of every pixel of a wall. Over half of each painted wall is window or ink, so it compared
  how much glass each wall has. It now measures the wall's material: the colour of the face's light pixels
  (brightness set aside), on pixels that are not ink (not darker than a neighbour by a line step). Stone in shade
  keeps its colour and stays in the measure, so a wall whose stone is darker than another's still fails. The
  every-pixel number is still reported.
- Lines kept gated every model line inside the opening, and so failed any interior with pews or columns in front
  of the shell's corners. The gate is now the cut's outline, K1's subject.

Tolerances of these checks (none loosens a limit above):
- K3 on a painting: "the same material" is chroma within 0.03 of the face's light pixels (the light check's own
  number); ink is a pixel darker than one of its eight neighbours by 12 (the build's line step). Limit: a shade
  drawn in another colour than the stone's is another material and is not measured; the light check and K7 remain.
- K2b: colour within 8 (RGB) of paper or of the painting's background; a patch narrower than 7 px (0.9 m) is a
  detail of the drawing, not a hole. Pixels outside the mask count as blank for the patch.
- Light: squares of 16 px every 4 px; "the same material" is chroma within 0.03 of the face's light pixels, on
  pixels that are not ink; a square is measured if two fifths of it is that colour; the lit level is the 90th
  percentile.
- Light, the surface tone: the luminance whose band of +-5% (the limit) holds the most of the face's material; of
  the two tones of a pattern the lighter, if it is at least half as common. The surface shows in a square if a
  tenth of its material is in that band.
- Light, limits: a shade narrower than about 2.5 m is not measured; a shade drawn in another colour than its
  surface counts as another material; a thing drawn within 5% of the surface's tone counts as the surface; on a
  pattern, a shade exactly as deep as the pattern's contrast reads as the pattern once it covers most of the
  face. K3 and K7 remain.

**The light check, corrected on 13 Nov 2026** (the owner's choice, "Investigate the check, free"; the limit is
unchanged; since the later decision of the same day, above, it is a reported number). It took the lightest tenth of every square as the surface's lit level. On `cathedral-open_1` the
lightest squares of the walls held a white sill, those of the vault its pale ribs, and the darkest squares of the
floor were the wall, drawn 2.5 m below the model's line. Lighter detail on a surface that shows its tone, and a
neighbouring face's surface across the model's line, are no longer read as light. A gradient, a cast shadow, a
dark corner and a darker wall are measured as before. No painting's verdict moved; none was within the limit
(`v2/docs/PHASE3_REPORT.md` section 9, "The light check looked into").

**The light check is a reported number; the owner's eye is the gate (13 Nov 2026).** Asked "The cleanest cathedral
painting (cathedral-open_1) still fails the corrected light check (6-10% against 5%) because of stone detail drawn
in several tones; its real shading on plain wall is 2-4%. Which way on?", the owner chose "Take it on my eye
(Recommended)": "Put cathedral-open_1 into the map, free. For painted cutaways the light check becomes a reported
number; wall tone (2.1%), outline and no-people checks stay as gates. I show you the viewer by day and night".
- For a painted cutaway interior, light across a face is still measured for every candidate and written to the
  results and to the adopted painting's record, with its 5% limit and whether it is within it. It no longer
  decides.
- The gates of a painting are K1 (the section's outline, and its lines kept), K2 (nothing outside the mask, the
  mask covered), K3 (the wall tone on the stone, 5%), K4 (no vehicles, no people), painted at all, then K5 and K6
  on the painted tiles, and K7.
- **K7 is recorded per landmark** in `v2/data/structures/cutaway_acceptances.json`: the job, the run, the candidate,
  the hash of that candidate's file as the run returned it, what was asked, the owner's words and the date.
- Nothing else changes: rule 3 stands, K3's limit stands, and the no-baked-shadow rule of every other layer
  (brief 5, L5.1) is untouched.

**Into the layer.** `python -m v2.bakeoff adopt K1` takes the candidate the owner accepted, cut to the mask, to
`v2/data/structures/cutaway_paintings/<name>.png` with its record: the frame, the file's hash, the job, the run, the
candidate and its seed, every gate, the light number with its limit, the owner's acceptance, and all the checks. It
is refused if the candidate fails a gate (an acceptance does not carry a painting past one), and if no acceptance
of that very painting is recorded (the same job and candidate, the same file by its hash). At the next build
`layer_cutaways` draws the painting where k is the opening and keeps depth, normals, ids and k; the paint inputs
stay the placeholder; `index.json` says per landmark whether its interior is painted. A record that does not say
"passed", or lacks the candidate, the run or the owner's acceptance of that candidate, a file that is not the
recorded one, or a painting that leaves an opening pixel of the tiles unpainted stops the build. Gates K1-K6 then
run on the painted tiles.

## In the viewer (Phase 3, $0)

Code: `v2/web/src/cutaways.ts`, `src/gl/compositor.ts`, `src/gl/shaders.ts`, `src/main.ts`. Checks:
`v2/checks/cutaway_view_checks.py` with `v2/web/scripts/cutaway_checks.mjs`; thresholds `params.json` "g3",
keys `cutview_*`.

**The toggle.** `?cutaway` turns every cutaway on, `?cutaway=cathedral,palace` those named; the panel's button
"Cutaways" turns all of them on or off and writes the choice to the address. Off, the viewer runs the same passes
with the same programs as before the feature.

**How it is drawn.** While a landmark's cutaway is on:
- layer 5's tiles that meet the landmark are drawn without the pixels of the buildings it replaces. They are told
  by their id (layer 5's id tiles, loaded only for those tiles);
- the cutaway's tiles are drawn right after, as layer 5, at their own depth with their own normals. So the light,
  the night, the seasons, the look pass and the ink treat the cut building as any building; vehicles are tested
  against its depth per pixel; structures and trees in front stay in front;
- the cutaway's tiles also hold the other buildings where they are nearer or seen through the slice. Where layer 5
  shows the same building, both have the same depth and colour, and the later one is kept: nothing changes. Where
  layer 5 showed the landmark, its pixel is gone and the cutaway's is the only one. K2v checks the whole view;
- night windows of a replaced building that stood in its slice are not lit (the slice's planes go to the window
  pass); the others are, as before;
- labels and the pointer meet the cutaway's depth where layer 8 shows a replaced building.

**With other switches.** `?off=buildings` switches the cutaways off too (they are layer 5). In tunnel view
(`?xray`) the cut building is part of the faded city: it shows through the fade as the whole building did.
From zoom 2 out, the merged far tiles give way to the separate layers while a cutaway is on (the far tiles have no
ids to cut by), and come back when it is off.

**The opening's light: the sky only (rule 3; the owner's decision of 13 Nov 2026).** Before it, the opening was lit
as any building. The shadow height map holds the whole building, so the opening stood in its own shell's shade
whenever the sun cast one: on the painted cathedral, half its painted brightness at 13:00 (lit level 0.48 against
0.85 for the outside stone), 0.80 at golden hour, 0.28 at night. The owner chose to light it by the sky only.
- **Where.** The viewer's light pass (`LIGHT_CUT_FS` in `src/gl/shaders.ts`, used only while a cutaway is on). The
  opening's pixels are told by the cutaway tiles' own `k` (layer 5 with a class of the opening mask: cut, inside
  wall, inside roof, floor, slab). The tiles are unchanged: nothing is baked.
- **What an opening pixel gets.** Its unlit colour times `sun.ambient` times the hour's sky colour (the grade's,
  `src/gl/grade.ts`) times a level (`light.json` "cutaway"). Nothing else: no cast shadow (the march's result is
  not used), no shadow tint, no sun, fill or moon term, so no face is darker than another. At night the colours
  lose saturation as everywhere (`night_desaturate`).
- **The levels** (`light.json` "cutaway": `sky_day` 1.47, `sky_golden` 1.08, `sky_night` 1.22). Each is set so that
  the interior is about as bright as the kept outside stone at that hour, whose median lit level on the cathedral
  on 24 June was 0.85 at 13:00, 0.84 at 21:18 and 0.31 at 23:15. Day: 0.58 x 1.47 = 0.85. Golden hour: the sky light
  there is 0.78 (0.58 x 1.5, warm), x 1.08 = 0.84. Night: 0.25 (deep blue), x 1.22 = 0.31. Between them the level
  moves as the sky's colour does, without a step (unit test `grade.test.ts`).
- **Off.** With no cutaway on, the viewer uses the plain light pass, untouched. `?off=cutlight` lights the opening
  as any building again (for the checks: the frame with the rule against the frame without it).
- **Not done, and no longer wanted:** the opening's own cast shadow moving with `?hour`. The opening takes no cast
  shadow. The kept shell still casts the whole building's shadow on the map around it.

**Checks in the browser** (`python -m v2.build test check_cutaways_view`; all gates). What the viewer must show is
worked out from the release's tiles: per map pixel the nearest surface, ties to the later layer, with the replaced
buildings' pixels of layer 5 left out and the cutaway's tiles in place. Frames are read at one screen pixel per map
pixel (1600 x 1200), so they compare pixel for pixel.

| Id | What is measured | Test area |
|---|---|---|
| K6v-off | A view that never had the cutaway on against the same view after on and off: pixels that differ, at 13:00 and 23:00, per landmark and at the far zoom | 0 in all 7 |
| K6v-on | Pixels the cutaway changes when on (it must show) | 31,570; 37,012; 59,224 |
| K6v-layer5 | Layer 5 pixels drawn with layer 5 off and the cutaway on | 0 |
| K6v-xray | In tunnel view the cutaway shows through the fade; after off, and after the tunnel view is off too, pixels that differ from the plain frame | shows; 0 |
| K2v | Interior pixels drawn outside the tiles' opening mask | 0 of 31,208; 32,416; 43,691 |
| K2v-frame | Pixels of the view whose layer, or class in layer 5, is not the tiles' nearest surface | 0 of 1,920,000 each |
| K2v-colour | Layer 5 pixels whose colour is not the tiles' | 0 |
| K5v-vehicles | Probe cars on a 4 m grid at the floor's level, through and round the landmark: pixels where the viewer's depth test disagrees with the tiles (silhouettes apart, at most 1%, as C4) | 0 of 174,232; 173,820; 384,210 (4, 4 and 24 on silhouettes) |
| K5v-labels | Label points on and 3 m behind the cutaway's surfaces that the viewer hides or shows against the tiles | 0 of 4,248; 3,116; 5,038 |
| K3v-sky-even | At 13:00, 21:18 and 23:15 on 24 June, with the look pass and the night lights off: opening pixels that are not their unlit colour times the one sky light the viewer gave the opening (by more than 1 of 255). One light on every pixel means no shadow and no light by direction | 0 in all 9 |
| K3v-sky-outside | The same frames against the same with `?off=cutlight`: pixels the rule changes outside the opening | 0 in all 9 |
| K3v-sky-levels (report) | Lit level of the interior with the rule, without it, and of the kept outside stone, at the three hours | `v2/docs/PHASE3_REPORT.md` section 10 |

Checked once by hand (`v2/web/scripts/compare_viewers.mjs`): the viewer with the feature, toggle off, against the
viewer before it, on the same release, at the three landmarks at 13:00 and 23:00, and the whole area in tunnel view: 0 pixels differ in all 7 frames.

**Previews:** `v2/docs/img/test_cutaway_<name>_viewer.jpg` (placeholders); the painted cathedral:
`test_cutaway_cathedral_map.jpg`, `test_cutaway_cathedral_map_wide.jpg`.

**Known limits.** The opening's light is flat by rule (above): no sun patch on its floor, no shade under its vault. The inside is a hollow shell with nominal walls: no rooms, vaults or columns until it is painted. A painting's windows are colour, not night windows: they do not glow.
Walls on lower roofs have no thickness. Windows are not openings in the inside faces.
