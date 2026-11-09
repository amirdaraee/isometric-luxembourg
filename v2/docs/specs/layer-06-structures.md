# Layer 6: Bridges and structures

**Purpose.** Viaducts, bridges, the Pfaffenthal lift, walls and casemate faces as objects with depth, so trains and
cars pass over and under them correctly. **Made by:** as layer 5 (bake-off winner), from geometry made in code.

**Inputs.** Scene structures (`structures.json`: the modelled viaducts' deck, piers and arches; every OSM bridge
outline in the area), bridge decks from the transport graph, the lift (OSM highway=elevator + v1's lift research),
walls from `walls.json`.

**Output.** RGBA tiles, depth per pixel, id tiles.

**Rules.**
1. Geometry is built from the data (deck = graph profile; piers to the LiDAR ground; arches from the documented
   spans), never fitted to a picture.
2. A deck's top surface is drawn by layer 4 (the road or track on it); this layer draws the deck's sides, parapets,
   piers and arches.
3. Albedo only, as layer 5.

**Checks.**
- L6.1 (gate) Every bridge edge of the graph in the area has its deck sides drawn (≥ 95% of its length), and
  every modelled viaduct its piers and arches.
- L6.2 (gate) Per-pixel depth test at every bridge in the area: a vehicle on the deck is drawn over the deck's
  sides; a vehicle under it is hidden by the deck and piers exactly where the depth says (brief 8).
- L6.3 (gate) Albedo, seams, layer-off and no-cars checks as layer 5.
- Data checks V1–V6 (checks.md) gate the structures data itself.
