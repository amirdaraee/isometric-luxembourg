# Layer 5: Building colour (albedo)

**Purpose.** The buildings' colour, evenly lit, with no cast shadows, cut to the exact 3D outline.
**Made by:** the bake-off winner (A all code, B code + AI materials and landmark portraits, C AI-painted buildings).

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
  length (brief 6).
- L5.3 (gate) 0 pixels outside the outline + 2 px (cut rule); 0 building pixels missing inside it (> 99.5%).
- L5.4 (gate) No cars (vehicle detector on every input and output; brief 9).
- L5.5 (gate) Seams and layer-off checks.
- L5.6 (owner) The bake-off comparison at fixed views (G2).
