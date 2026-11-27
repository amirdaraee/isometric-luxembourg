# Layer 5: Building colour (albedo)

**Purpose.** The buildings' colour, evenly lit, with no cast shadows, cut to the exact 3D outline.
**Made by:** the bake-off winner (A all code, B code + AI materials and landmark portraits, C AI-painted buildings).
Chosen by `params.json` art.method (or `V2_ART`); each method builds into its own stage folders.
- **A (built, phase 2, `v2/layers/art_a.py`):** per building a facade colour (palette `buildings.facade_*`, or
  sandstone), a roof (slate, dark slate, tile, old tile; flat roofs gravel); walls with a sandstone plinth, a cornice
  line at each floor line of the facade layout, an eave cornice and, on some buildings, quoins; roofs with courses
  parallel to the eave and staggered joints; windows with a white frame, glazing bars and a sill line, shutters on
  some buildings where they fit the wall; doors with panels and a fanlight; garage doors; shop fronts with glazing
  bars and a striped awning band. All of it computed per pixel from the pixel's place on its surface, so it is fixed
  to the 3D model; ink outlines where surfaces meet.
- **A, richer (phase 3, after gate G2 chose A):** every building in its own tone of its colour; 13 facade colours
  and 7 roof colours; coursed ashlar on stone buildings, a banded ground floor on some rendered ones, a faint mottle
  on render; a stone surround with a lintel, keystone and sill round every window and a surround and lintel round
  every door; windows with a cross or six panes, each window's glass its own tone; gravel on flat roofs. All of it
  per pixel from the pixel's place on its wall, straight by construction.
- **A, v1's cartoon look (owner, 26 Nov 2026: "can't we move toward the cartoonish style of v1?", and of four
  samples of the cathedral the one closest to v1).** This replaces the colours and the surface texture of the two
  entries above; the drawing (plinths, cornices, surrounds, windows, doors) stays.
  - A house's colour (owner, 26 Nov 2026, seeing the area all in v1's cream: "bring back diffrent bulding colors
    as well", "other colors can be more cartoonish", "but the art style remains"): one of the 13 facade colours by
    the building's id, as before the cartoon look, each stronger (`buildings.facade_*`), in the building's own
    tone. No data says what colour a house is (the photo is from above), so this stays a rule. A well-known
    building keeps the colour its entry in `landmark_styles.json` names. The first cartoon build's family of seven
    creams (`FACADE_SHARES`) is gone.
  - A roof's covering is the one the orthophoto shows (owner, 26 Nov 2026, asked why all roofs were grey: "Real,
    from the photo"; scene.md, "Roofs"): slate in four shades, bright or brown tile, a flat roof grey, under gravel
    or planted. A roof the photo does not read is slate by rule; a well-known building's own roof wins over the
    photo. In the test area 3 of 999 pitched roofs read are tile: the real roofs are slate. Slate is v1's, measured
    in v1's art (106, 115, 129 lit): darker and bluer than the first cartoon build's (owner: "Darker and bluer, as
    v1").
  - Roofs carry v1's lines: a light stroke down the slope every 0.9 m (`ROOF_STROKE`), drawn by coverage as the
    courses are and fading out on a face too small to hold them, so no face of a roof differs in tone from another
    (L5.1); the courses parallel to the eave stay, fainter; the staggered joints are gone.
  - Fills are clean (`GRAIN` 0): no paper grain, no mottle on render, no stone-to-stone or slate-to-slate tone, on
    buildings and on structures' stone. Ashlar keeps its joints, fainter.
  - Window glass is v1's dark blue (`buildings.window`); frames, cornices and quoins a warm white (`trim`).
- **A, places of worship (owner, 13 Nov 2026):** the walls the facade layout marks as a church's (facades.md rules
  14-20) are drawn as a church, not as a house. Walls: stone (the kind "place_of_worship" of
  `v2/data/structures/landmark_styles.json`; a building's own entry there goes first), coursed ashlar, no cornice
  at floor lines, no banded ground floor. Windows: the layout's rectangle drawn by its kind, its outline the
  arch itself (round or pointed) or a circle, with a stone frame along it. No shutters. Doors: planks under a
  round arch, in stone, no fanlight. No light in any of it. A building that is mostly church (half its footprint
  or more) is stone all over; where the church is a smaller part of a building, only its walls are.
- **A, a part in sheet metal (owner, 23 Nov 2026: the cathedral's central spire is copper gone green, "do it"):**
  a well-known building's entry in `landmark_styles.json` may list `clad` parts: a name, the centre and radius of
  an upright cylinder, the altitude it starts at, and a palette colour (`roof_copper`). Whatever the model has of
  that building inside the cylinder, walls and roofs alike, is that one colour with the paper's grain: no slate
  courses, no ashlar. It is a material of its own (class trim), so the shadow detector compares it with itself and
  a painting's colours do not reach it. The cathedral's central spire and its lantern are the one entry; its two
  tower spires are slate, as they are.
- **A, a rendered church (owner, 23 Nov 2026: the three churches' real wall colours, "yes"):** a church whose
  own entry in `landmark_styles.json` gives a `facade` colour is rendered in that colour with a faint mottle,
  not stone: Saint-Michel cream, Sainte-Cunégonde white, Neumünster Abbey with Saint-Jean du Grund ochre (the
  whole building, wings and church alike, as it is). An entry may name `stone_parts`: each a name and its outline
  on the ground; the building's walls that stand in it stay coursed sandstone (Sainte-Cunégonde's tower). It may
  set `quoins` true or false where the photographs show corner stones or none (Saint-Michel: true). Chosen by
  hand from the photographs named in `landmark_facades.json`; nothing else about the walls changes.
- **A, places of worship, round two (owner, 13 Nov 2026, "One more round"):** what the layout's rules 21 to 30
  place is drawn so (`church_rgb` and `walls_rgb` in `v2/layers/art_a.py`):
  - *lancet:* a sill, leaded glass, a lead line up the middle;
  - *traceried window:* a stone mullion 0.2 m wide, two lights with their own heads springing where the window's
    does, and a round top light that touches them and the arch;
  - *rose:* a wheel: a hub, 8 spokes (12 from 3.4 m across) to a stone ring, and as many between them from the
    ring to the frame; *oculus:* a round window with a cross of stone bars;
  - *belfry opening:* wooden louvres in a stone frame, a stone mullion from 1.2 m wide; no glass;
  - *portal:* two orders of stone round the arch, a tympanum over a lintel, two plank leaves;
  - *walls:* a string course under the sills, a corbel table under the eave of a wall 5 m high or more, and the
    buttresses: the wall's own stone a little lighter, between dark upright lines, with a set-off at 55% of their
    height and a narrower upper stage. A buttress is drawn, not built: it casts no shadow.
  - *stained glass by day:* seven panes in ten are stained, in the palette's four colours at 85% strength, and
    every pane is scaled to the plain glass's brightness. Colour varies, brightness does not, so L5.1 measures
    one glass whichever way a wall faces. The gate and its limit are as they were.
- **A, landmarks as they are (owner, 23 Nov 2026):** an opening of a described wall (facades.md rules 31 to 35)
  says its own head, where a rule's opening has its church's: pointed, round, or flat. A flat head is a lintel:
  the opening is its rectangle, with the same stone frame, sill, leaded glass and lead line as a lancet. Nothing
  else is drawn differently: a described two-light window is the traceried window above.
- **B, C (stopped at G2, 10 Nov 2026):** `v2/layers/bakeoff.py`, `v2/bakeoff/` (kept as the bake-off's record).

**Inputs.** Scene buildings (ACT LoD2: footprint, walls, roof planes, roof shape, installations; `mesh.npz`),
the facade layout (`facades.json`), the palette (`buildings.*`). For B and C: unlit renders of the mesh (flat
material colours, ambient light only, no orthophoto drape).

**Output.** RGBA tiles; alpha = the mesh's coverage; depth = the mesh's depth per pixel; an id tile set (building
index) for hover.

**Rules.**
1. Albedo only: no sun shading, no cast or contact shadows painted or rendered in (layer 9 lights it).
2. Every pixel is inside the building's projected 3D outline grown by ≤ 2 px (the POC cut rule); anything outside
   is removed by the cut, never by a later patch.
3. Windows sit at the facade layout's positions (A: drawn; B: material windows placed there; C: painted, then
   held to them by the line score).
4. AI layers are painted on unshadowed input at ≤ 0.125 m per model px so a window covers ≥ 2 latent cells.

- **Walls down to the ground (owner, 27 Nov 2026: "building is floating").** ACT's walls end at the model's own
  ground surface, one height per building. Where the LiDAR ground at the outline lies lower, the building stood in
  the air (in the test area 91 buildings by more than 0.5 m, 16 by more than 2 m). For every outline edge whose
  ground (sampled every 0.5 m along the edge and 0.5 m outside it) is more than 0.1 m under the base, the wall is
  continued by one face from the base to 0.5 m under the lowest ground along that edge
  (`geometry.wall_skirts`, params `buildings.skirt`). The face lies in its wall's plane, so it is drawn as that
  wall's base course (the plinth's stone).

**Checks.**
- L5.1 (gate) No baked shadows: on each building the mean luminance of the same material on sunlit and shadow
  sides (for the photo's sun) differs by ≤ 5%; the shadow detector finds nothing (brief 5).
- L5.2 (gate) Line score: building edges and window rows within 1 px of the 3D model's lines over 95% of their
  length (brief 6). Measured (`check_lines`, phase 2): every crease (surfaces meeting at 20° or more, or of
  different classes) and outline of the model, and the top and bottom of every window (of an arched church window,
  which has no straight top, the sill; of a round one, nothing), sampled every 0.25 m where
  layer 5 shows that building; the drawn line is the luminance step (>= 12/255) across the projected line nearest
  to it, within 3 px; it must lie within 1 px. Building edges and window rows are scored separately, each >= 95%.
- L5.3 (gate) 0 pixels outside the outline + 2 px (cut rule); 0 building pixels missing inside it (> 99.5%).
- L5.4 (gate) No cars (vehicle detector on every input and output; brief 9).
- L5.5 (gate) Seams and layer-off checks.
- L5.6 (owner) The bake-off comparison at fixed views (G2).
- L5.7 (gate, `check_lines`) Places of worship: on the buildings that are a church all over (every wall), 0 shutter
  pixels, 0 shop front pixels, and 0 window glass pixels in a house window's colour.
- L5.8 (gate, `check_lines`) Church tracery is straight: the mullion of every traceried window (its centre line
  from over the sill to under the springing), sampled every 0.25 m and scored as L5.2's lines are, >= 95% (the
  same limit, `line_score_share`).
- L5.9 (gate, `check_lines`) No building stands in the air: 0 buildings whose base is more than 0.1 m over the
  lowest ground at their outline and whose walls do not reach that ground.
