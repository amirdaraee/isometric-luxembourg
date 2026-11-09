# Layer 8: Geometry buffers

**Purpose.** The invisible layer that makes the map behave like 3D: depth, surface direction, height above ground
and object ids for every pixel, from the same scene and camera as the art. It drives light, shadows, occlusion of
vehicles, snow and hover. **Made by:** code (a renderer of the scene).

**Inputs.** The whole scene: terrain, buildings mesh, structures, transport decks, tree crowns, water.

**Output.** Tile sets, lossless:
- `depth`: 16-bit view depth (conventions.md), nearest surface per pixel;
- `normal`: octahedral 2 × 8 bit, world normal of that surface;
- `height`: 16-bit height above the terrain (cm), for "is this a roof or a road";
- `id`: 24-bit object id (building index, edge id, tree index, place) + 8-bit class.
At far zooms, buffers are down-sampled by the nearest surface (min depth), never averaged.

**Rules.** One render, one camera (camera.md), the same 0.125 m pixel grid as the colour layers; every colour
layer's own depth must equal this buffer where that layer is the nearest surface.

**Checks.**
- L8.1 (gate) Alignment: for every colour layer, its depth equals layer 8's depth within 1 cm wherever it is the
  nearest surface (no offset between art and geometry; v1's 6.8 px shift cannot recur).
- L8.2 (gate) Normals are unit length (±1%) and face the camera.
- L8.3 (gate) Every id in the id tiles exists in the scene, and every scene object in view has ≥ 1 id pixel.
- L8.4 (gate) Seams: depth continuous across tile borders where the surface is.
