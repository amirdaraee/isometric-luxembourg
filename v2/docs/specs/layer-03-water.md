# Layer 3: Water

**Purpose.** The Alzette, the Pétrusse, ponds and pools, exactly where OSM has them, flat and still in the art and
animated in the viewer. **Made by:** code.

**Inputs.** Scene water (`water.json`: OSM water areas and river lines, culverts flagged), terrain (water level =
the lowest terrain along the bank, per reach), palette (`water.*`).

**Output.** RGBA tiles plus a lossless water mask (the viewer's animation mask), depth = the water surface.

**Rules.**
1. Water areas are filled flat (palette `river`), bank edge inked (`bank`), with a paler band of shallows 0.8 m
   wide along the banks (palette `shallow`, phase 3); no reflections or waves drawn (moving things are code in the
   viewer).
2. Culverted stretches (tunnel=culvert) are not drawn.
3. The water level of a reach is constant between weirs (the Grund lock) and never above the bank. **The water's
   edge is the area's own line** (the owner, 25 Nov 2026: "the rivers are not good"). The terrain the layers draw
   on holds the water's level on every 0.5 m cell whose centre is in the water or within a cell's diagonal of it
   (`render.hold_water`), so the ground read between the cells is flat at every point of the water area and the
   bank rises outside it. Held on the cells in the water only, as it was until 26 Nov 2026, the bank's rise began
   inside the area, and the water drawn on it showed the grid's steps as saw teeth up the far bank. In the test
   area this lowers the ground under 41 half-metre samples of paths' centre lines (those within 0.7 m of the
   water's line).
4. **A river has a stone edge** (the owner, 26 Nov 2026: of two samples, the one with a pale stone edge along
   every bank, as v1's river has). The outer 0.7 m of a river's area (`kind` river in `water.json`) is not water:
   it is the ground layer's class `quay`, plain pale stone on the water's level. The river's water is its area
   drawn in by that much, and the shallows lie inside that. The bank's line stays where OSM has it. Ponds, pools
   and basins have no stone edge: they are water to their own line. The data does not say which bank is walled
   and which is a meadow's, so every bank of a river gets the edge.

**Checks.**
- L3.1 (gate) 100% of the drawn water area inside the area (OSM's areas, a river's drawn in by its stone edge) is
  water in the mask, and no water pixel lies outside it (± 1 px).
- L3.2 (gate) No tree, building or road pixel is drawn *under* water depth (the water surface hides nothing above
  it).
- L3.3 (gate) Seams, layer-off and no-boats (vehicle detector on boats) checks. The detector looks at the water
  in its bed, over the ground layer: the water's outline is the land's, and where a bank stands in front of the
  water it cuts a gap in the layer that, alone on black, reads as a dark thing on the water (26 Nov 2026: the
  end of a 3 m bank at E 78017, N 74870 scored 0.108 as a boat; over the ground, under 0.03).
- Unit test (`v2/layers/tests/test_cliffs.py`): the ground read anywhere in a slanted water area is flat at the
  water's level, and the ground more than 1.5 m outside it is unchanged.
