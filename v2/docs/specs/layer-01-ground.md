# Layer 1: Ground colour

**Purpose.** The colour of the land: pavements, squares, parks, gardens, lawns, woods, fields, car parks, sports
grounds, rail ground, building sites, under everything else. **Made by:** code (phase 1).

**Inputs.** Scene terrain (`terrain.npz`), the scene's ground cover (`groundcover.npz`), OSM land use (`fetch_osm_ground`: landuse, leisure, natural, amenity,
place=square, area:highway), the palette (`ground.*`), paper grain. The orthophoto may be used to *classify* only
(lawn vs paving where OSM is silent), never as colour, so no car or shadow in the photo can reach the layer.

**Output.** RGBA tiles, 0.125 m/px, at the terrain's height (depth = terrain depth). Alpha 0 under buildings is not
needed (layer 5 covers them), but the ground is complete under them so a building can be switched off.

**Rules.**
1. One class per pixel, from OSM areas in a fixed priority (water > pitch > wood > scrub > meadow > garden >
   cemetery > grass > square > parking > rail ground > building site > paved); unclassified land: inside the
   built-up area a lawn (class grass) where the orthophoto shows vegetated ground (`scene_groundcover`, scene.md
   "Ground cover"; owner, 23 Nov 2026) and paved elsewhere; meadow outside. Two classes are not from OSM (phase 3; the owner, 26 Nov 2026), whatever the land use says of
   them and except under water:
   - **rock**, a rock face from its top to its foot (`cliffs.rock_zone`): the scene's cliff cells (terrain class 2:
     60° or steeper with a drop of 2.5 m or more), the steep cells (35° or more) within 2.5 m of them, and the gaps
     between them smaller than 60 m². The owner: "the green patches are not good": a patch of lawn inside a face
     is rock; a real ledge stays what it is.
   - **drystone**, a low face on it (the terrain's range within 2.5 m is under 3.5 m: a terrace's or a garden's
     wall).
   A rock face is one thing. A first build (26 Nov 2026) also drew the built walls that stand on a face as bands
   of stonework, from the OSM wall lines and their measured heights, and the ways' raised sides and surfaces
   hung over it; shown the Bock drawn so, the owner said: "which does not make sense", and: "simplify it and not
   stick to reality because you don't have enough data on the reality". So on or within 5 m of a rock face no
   wall is drawn (layer 2), no side of a raised way hangs down it (layer 6), and a way's surface is not painted
   down it (layer 4): the face is rock.
   - **quay**, a river's stone edge: the outer 0.7 m of the river's own area, along every bank (layer 3 rule 4;
     the owner, 26 Nov 2026). It is plain pale stone (`ground.quay`), on the water's level.
2. Colour = the class's palette colour, with paper grain (±3% luminance, fixed seed per tile position, seamless),
   and the class's drawn detail (phase 3, `v2/layers/detail.py`): stone slabs on paved land, setts on squares,
   gravel on car parks, rail ground and building sites, patchy lawns with flecks of blades, flowers in gardens, mown
   stripes on pitches. Every pattern is a function of the pixel's place on the terrain (E, N, height) and a hash,
   never of the slope's direction or the sun, with tones even about the class colour.
   Rock and dry stone are drawn by `v2/layers/cliffs.py` in their own colours (`relief.rock_1` to `rock_3`,
   `rock_cleft`, `drystone_*`). The rock is drawn from a photo of the Bock's south-east face (from Neumünster
   Abbey; Paul Braun, Wikimedia Commons, CC BY 4.0), flat, as a cartoon: one pale gold face in three near tones
   in broad patches; a big dark cleft about every 11 m across the screen, wandering, opening and closing up the
   face, 0.5 to 1.5 m wide, its screen-right side a tone darker; faint bedding as short level strokes; faint
   stains. No blocks, no joints and no ink. (A rock of stacked blocks in v1's manner, chosen first from samples,
   was turned down once seen on the Bock: "no noo, what is this? find a real photo of this cliff and compare";
   of the redraw from the photo the owner said "looks good", 26 Nov 2026.) Dry stone is level courses of small
   stones, patchy. Nothing green is drawn on a face by rule: plants are where the ground's classes and the tree
   survey put them.
   **The casemates' openings** (the owner, 26 Nov 2026: of two samples, the openings without the wall on top).
   The photo shows a row of dark openings in the Bock's face. An opening is drawn on a rock face where the line
   of a gun branch of the casemates' hand model (`v2/data/structures/casemates.json`: 25 branches, 13 facing
   south, as published) comes out of the rock: an arched hole 1.8 m wide, its sill 0.4 m over the branch's floor,
   2.1 m high at its middle, in one dark brown (`relief.casemate_opening`), looked for from 3 m before the
   branch's outer end to 12 m beyond it (`cliffs.gun_branches`, `cliffs.openings`). The model is placed by hand,
   not surveyed, so an opening is about where a real one is, not exactly. The grey wall on top of the Bock in the
   photo is not drawn: no data says where it is, and placed by rule it came out thin and uneven.
   **A border is a smooth line** (the owner, 26 Nov 2026, of a cliff's saw-toothed top: "what about the rough
   edges"). Where a class comes from a grid (the rock face and the low face from the terrain's 0.5 m cells, the
   photo's vegetated ground from its cells), the grid is read as a smooth field between its cells and cut at a
   half (`grid.soft_mask`, `grid.read_soft`: smoothed over 0.5 m for rock, one cell for vegetated ground), not
   cell by cell, which drew the cells' staircase as saw teeth. A part narrower than three cells keeps its cells.
3. Class borders are ink lines of 1 px at the class's edge (soft, 40% ink).
4. No light: the same class has the same colour on every slope and side.

**Checks.**
- L1.1 (gate) Every pixel of the area has a class; no transparent ground pixel inside the area.
- L1.2 (gate) No shading: the mean luminance of one class on north- and south-facing slopes differs by ≤ 2%
  (brief 5).
- L1.3 (gate) Turning the layer off leaves no trace of it in the other layers (brief 4: per-pixel diff of the
  composite of the others, with and without it, is 0).
- L1.4 (gate) Seams: no LAB ΔE step above 3 across any tile border (64 px band).
- L1.5 (gate) Vehicle detector (v1's OWLv2) finds 0 cars ≥ 0.1 score (brief 9).
- L1.6 (report) Area by class within the area polygon.
- Unit tests (`v2/layers/tests/test_cliffs.py`): the rock is the same however its pixels are split between
  calls; it is pale, mostly flat tone, with no ink and with clefts few and far apart (a median of over 8 m
  along a level line), each opening and closing up the face; a face is rock from top to foot and a ledge stays;
  a low face is told from a cliff; a border read between the cells has no teeth, has not moved, and a face one
  cell wide is kept; a casemate's opening is an arch on its branch's line at its floor's height, and nowhere
  else.
- Unit test (phase 3): each pattern keeps its class's median within 3% of the class colour and is the
  same on every call (`test_drawn_detail_is_even_and_knows_no_side`). L1.2 and the shadow detector gate the result.
