# Layer 1: Ground colour

**Purpose.** The colour of the land: pavements, squares, parks, gardens, lawns, woods, fields, car parks, sports
grounds, rail ground, building sites, under everything else. **Made by:** code (phase 1).

**Inputs.** Scene terrain (`terrain.npz`), OSM land use (`fetch_osm_ground`: landuse, leisure, natural, amenity,
place=square, area:highway), the palette (`ground.*`), paper grain. The orthophoto may be used to *classify* only
(lawn vs paving where OSM is silent), never as colour, so no car or shadow in the photo can reach the layer.

**Output.** RGBA tiles, 0.125 m/px, at the terrain's height (depth = terrain depth). Alpha 0 under buildings is not
needed (layer 5 covers them), but the ground is complete under them so a building can be switched off.

**Rules.**
1. One class per pixel, from OSM areas in a fixed priority (water > pitch > wood > scrub > meadow > garden >
   cemetery > grass > square > parking > rail ground > building site > paved); unclassified land: paved inside the
   built-up area, meadow outside.
2. Colour = the class's palette colour, with paper grain (±3% luminance, fixed seed per tile position, seamless).
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
