# Layer 3: Water

**Purpose.** The Alzette, the Pétrusse, ponds and pools, exactly where OSM has them, flat and still in the art and
animated in the viewer. **Made by:** code.

**Inputs.** Scene water (`water.json`: OSM water areas and river lines, culverts flagged), terrain (water level =
the lowest terrain along the bank, per reach), palette (`water.*`).

**Output.** RGBA tiles plus a lossless water mask (the viewer's animation mask), depth = the water surface.

**Rules.**
1. Water areas are filled flat (palette `river`), bank edge inked (`bank`), no reflections or waves drawn (moving
   things are code in the viewer).
2. Culverted stretches (tunnel=culvert) are not drawn.
3. The water level of a reach is constant between weirs (the Grund lock) and never above the bank.

**Checks.**
- L3.1 (gate) 100% of OSM water area inside the area is water in the mask, and no water pixel lies outside it
  (± 1 px).
- L3.2 (gate) No tree, building or road pixel is drawn *under* water depth (the water surface hides nothing above
  it).
- L3.3 (gate) Seams, layer-off and no-boats (vehicle detector on boats) checks.
