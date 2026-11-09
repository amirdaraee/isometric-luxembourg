# Layer 2: Relief — terrain and cliffs

**Purpose.** The shape of the land as a drawing: Swiss-style relief shading on slopes, hatching on cliffs and steep
faces, retaining and city walls drawn as walls. The Bock, the Alzette and Pétrusse valleys are the map's character.
**Made by:** code (phase 1); in bake-off C, AI rock texture inside the cliff mask only.

**Inputs.** Scene terrain: LiDAR 2024 ground model (0.5 m on the test area, 1 m on the commune), slope and class
(`cls`: 0 ground, 1 steep ≥ 35°, 2 cliff ≥ 60° with ≥ 2.5 m drop), `walls.json` (OSM retaining walls, city walls,
cliffs, embankments with their measured top and foot).

**Output.** RGBA tiles (a multiply layer over layer 1), depth = terrain depth; a cliff mask tile set (lossless).

**Rules.**
1. Relief shading is a *form* shading from a fixed north-west light, not the sun: it does not move with the time of
   day (layer 9 does that), and its strength is capped so flat ground is untouched.
2. Steep faces get hatching along the fall line, spacing from the slope; cliffs get rock hatching; walls are drawn
   as vertical faces between their measured top and foot, in stone colour, with an ink top edge.
3. Cliff and wall faces are seen only where the camera sees them (depth test against the terrain).

**Checks.**
- L2.1 (gate) Flat ground (slope < 3°) is unchanged by the layer (multiply factor 1.0 ± 0.01).
- L2.2 (gate) Every OSM wall in the area with a measured drop ≥ 1.5 m is drawn (wall pixels along ≥ 90% of its
  length).
- L2.3 (gate) The layer is identical at 08:00 and 19:00 (relief is not light; brief 5).
- L2.4 (gate) Seams, layer-off and no-cars checks as L1.3–L1.5.
- L2.5 (owner) The Bock, the Corniche and the Pfaffenthal cliffs read as cliffs at fixed views.
