# Layer 6: Bridges and structures

**Purpose.** Viaducts, bridges, the Pfaffenthal lift, walls and casemate faces as objects with depth, so trains and
cars pass over and under them correctly. **Made by:** as layer 5 (bake-off winner), from geometry made in code. Method A: ashlar courses (0.5 m) and
staggered joints (0.9 m) on stone faces, a tone per block; railings and the lift as bars.

**Inputs.** Scene structures (`structures.json`: the modelled viaducts' deck, piers and arches; the other bridges'
rows of arches and the Red Bridge's girder and legs; every OSM bridge outline in the area), bridge decks from the transport graph, the lift (OSM highway=elevator + v1's lift research),
walls from `walls.json`.

**Output.** RGBA tiles, depth per pixel, id tiles.

**Rules.**
1. Geometry is built from the data (deck = graph profile; piers to the LiDAR ground; arches from the documented
   spans), never fitted to a picture.
2. A deck's top surface is drawn by layer 4 (the road or track on it); this layer draws the deck's sides, parapets,
   piers and arches.
3. Albedo only, as layer 5.
4. A raised approach (a ground way drawn as a deck, layer 4 rule 1) stands on an abutment: its two sides from the
   deck's edges down into the terrain, in stone; not on or within 5 m of a rock face, where a side would hang down
   the cliff as a sheet of masonry (the owner, 26 Nov 2026: "does not make sense"; layer 1 rule 1). A tunnel portal under a deck is cut to the deck's underside (layer 4).

5. No bridge stands in the air (the owner, 27 Nov 2026). Under every bridge that has no model of its own stand
   stone arches on piers, and under the Red Bridge its red girder and four slanted legs on concrete footings, as
   the scene gives them (structures.md rules 6 to 10; `geometry.supports_mesh`). Steel has no joints.
6. A viaduct's deck is a gravel bed (`structures.ballast`, flecked stone by stone) between solid stone parapets
   0.5 m thick under a pale coping (`structures.coping`); layer 4 draws the tracks on it (the owner, 27 Nov 2026:
   "top surface of bridges for train tracks seems wrong"). A parapet in stone is masonry like the wall under it;
   only a railing is drawn as bars.

**Checks.**
- L6.1 (gate) Every bridge edge of the graph in the area has its deck sides drawn (≥ 95% of its length), and
  every modelled viaduct its piers and arches.
- L6.2 (gate) Per-pixel depth test at every bridge in the area: a vehicle on the deck is drawn over the deck's
  sides; a vehicle under it is hidden by the deck and piers exactly where the depth says (brief 8).
- L6.3 (gate) Albedo, seams, layer-off and no-cars checks as layer 5.
- L6.4 (gate, `check_lines`) Every arch and pier of the scene's supports, and every leg of a frame, is in this
  layer's mesh.
- Data checks V1–V11 (checks.md) gate the structures data itself.
