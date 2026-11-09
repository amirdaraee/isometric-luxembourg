# Layer 7: Trees and greenery

**Purpose.** Every tree at its measured place and size, as part of the drawing, changing with the seasons.
**Made by:** code crowns (A, B) or an AI-painted canopy field (C), decided at the bake-off. Methods A and B: the
crown fills the measured height down to a trunk of a quarter of it (at least 2 m), its width the survey's (L7.1);
method A adds leaf clumps (a 0.8 m cell pattern on the crown's surface, lighter and darker clumps, darker gaps).

**Inputs.** Scene trees (`trees.npz`: LiDAR 2024 survey position, height, crown radius after thinning, type), the
palette (`trees.*`), terrain and buildings (depth).

**Output.** RGBA tiles, depth per pixel (each crown as a 3D shape: an ellipsoid of the crown radius on a trunk to
the measured height), a crown mask (for sway and seasons), id tiles.

**Rules.**
1. Size comes from the survey: crown radius = 0.85 × crown_mean / 2, thinned where more than 30% of the crown would
   lie over a building or water (scene rule); no tree bigger than measured.
2. Depth-tested per pixel against terrain, buildings and structures: a tree hides what is behind it, never what is
   in front.
3. No shadow in the layer (layer 9 casts crown shadows from the same crowns).
4. Seasons change only this layer's colour and foliage (layer 11), never its positions.

**Checks.**
- L7.1 (gate) Crown size: no drawn crown wider than its measured crown_max (brief: no oversized trees).
- L7.2 (gate) 0 tree pixels in front of a nearer surface (depth test, per pixel).
- L7.3 (gate) Flat-share: no photo texture in crowns (the London check: share of near-flat 8×8 blocks within bounds).
- L7.4 (gate) Seams, layer-off and no-cars checks.
- Data checks TE1–TE4 (checks.md) gate the tree data.
