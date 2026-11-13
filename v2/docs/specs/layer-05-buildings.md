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
- **A, places of worship (owner, 13 Nov 2026):** the walls the facade layout marks as a church's (facades.md rules
  14-20) are drawn as a church, not as a house. Walls: stone (the kind "place_of_worship" of
  `v2/data/structures/landmark_styles.json`; a building's own entry there goes first), coursed ashlar, no cornice
  at floor lines, no banded ground floor. Windows: the layout's tall rectangle as an arched window, its outline the
  arch itself (round or pointed), a stone frame along the arch and a sill, a mullion between two lights, lead
  lines, dark glass with some stained panes. No shutters. Doors: planks under a round arch, in stone, no fanlight.
  No light in any of it. A building that is mostly church (half its footprint or more) is stone all over; where
  the church is a smaller part of a building, only its walls are.
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

**Checks.**
- L5.1 (gate) No baked shadows: on each building the mean luminance of the same material on sunlit and shadow
  sides (for the photo's sun) differs by ≤ 5%; the shadow detector finds nothing (brief 5).
- L5.2 (gate) Line score: building edges and window rows within 1 px of the 3D model's lines over 95% of their
  length (brief 6). Measured (`check_lines`, phase 2): every crease (surfaces meeting at 20° or more, or of
  different classes) and outline of the model, and the top and bottom of every window (of an arched church window,
  which has no straight top, the sill), sampled every 0.25 m where
  layer 5 shows that building; the drawn line is the luminance step (>= 12/255) across the projected line nearest
  to it, within 3 px; it must lie within 1 px. Building edges and window rows are scored separately, each >= 95%.
- L5.3 (gate) 0 pixels outside the outline + 2 px (cut rule); 0 building pixels missing inside it (> 99.5%).
- L5.4 (gate) No cars (vehicle detector on every input and output; brief 9).
- L5.5 (gate) Seams and layer-off checks.
- L5.6 (owner) The bake-off comparison at fixed views (G2).
- L5.7 (gate, `check_lines`) Places of worship: on the buildings that are a church all over (every wall), 0 shutter
  pixels, 0 shop front pixels, and 0 window glass pixels in a house window's colour.
