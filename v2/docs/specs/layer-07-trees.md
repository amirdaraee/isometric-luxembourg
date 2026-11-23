# Layer 7: Trees and greenery

**Purpose.** Every tree at its measured place and size, as part of the drawing, changing with the seasons.
**Made by:** code crowns (A, B) or an AI-painted canopy field (C), decided at the bake-off. Methods A and B: the
crown fills the measured height down to a trunk of a quarter of it (at least 2 m); its width follows the tree's
shape by species and age (rule 1); both draw the crown as leaf clumps (below; B has A's crowns by the owner's
decision of 10 Nov 2026). Method C uses the same code crowns unless a canopy is painted.

**Inputs.** Scene trees (`trees.npz`: LiDAR 2024 survey position, height, crown radius after thinning, type), the
palette (`trees.*`), terrain and buildings (depth).

**Output.** RGBA tiles, depth per pixel (each crown as a 3D shape on a trunk to the measured height), a crown mask
(for sway and seasons), id tiles.

**Crown shape and variety (phase 3; v1's trees, the owner, 23 Nov 2026).** A broadleaf crown is a dark core
(0.8 of the crown's radius and half-height) with leaf clumps all over its surface, one of them on top; a conifer is
three tiers narrowing upwards; a crown under 1.2 m radius stays one shape.
- **Clumps.** A clump is a spheroid of half the crown's radius (0.6 m at least, 2.4 m at most, never over 0.6 of
  the crown's), 0.85 as high as wide, each its own size (±30%). They are spread evenly over the measured crown's
  surface (golden angle, turned and jittered per tree), as many as cover it once with 1.3 of a clump's footprint
  each (8 at least): about 15 seen on a grown tree. No clump reaches beyond the tree's crown radius, above its
  measured top or below the crown's foot, and the top clump ends exactly at the measured top, so rule 1 holds (unit
  test `test_crown_lobes_stay_inside_the_measured_crown`).
- **Colours** (`art_a.crown_rgb`). A clump is the tree's light green, each clump its own tone (±11%), with a fine
  fleck of leaves (0.3 m, ±4%). The core, seen between clumps, is the foliage's dark. The underside of a clump,
  which sees no sky, goes to the dark across a ragged edge (0.45 m): at full strength on a clump of 1.3 m radius or
  more, fading to a third on the smallest, so a small tree is not striped. Each tree leans to a warmer or a cooler
  green (palette `summer_light_warm`, `summer_light_cool`).
- **Lines.** Ink (the foliage's dark at 0.55) at 0.9 where a crown meets anything else, and at 0.8 where two shapes
  of one crown meet (the nearer shape's edge), so every clump is drawn round.
- **Nothing follows the sun.** Clumps, colours and lines are hashes of the tree's index and of the place; the dark
  underside follows "up". What moves with the hour is the viewer's light on each clump's own normal (bright on the
  sunward side) and layer 9's cast shadows, from the same shapes.
- Before 23 Nov 2026 a crown was a core with five to seven large lobes, a mid green with a 0.8 m cell pattern.
  v1's foliage runs from [10, 23, 17] to [156, 176, 43] (5th to 95th percentile of luminance, three views); v2's
  ran from [33, 40, 24] to [120, 138, 68].

**Rules.**
1. Position and height come from the survey and are never changed. The crown's width is the survey's
   (0.85 × crown_mean), widened to the tree's shape by species and age (owner decision, 9 Nov 2026: the survey's
   crowns are 2–5 m wide on trees 15–25 m tall, which drew poplars):
   - width = height × a ratio; the ratio grows evenly from a young tree (6 m or less) to a mature one (20 m or
     more). Height stands in for age, as the survey has no age.
   - Broadleaf (green and red): 0.42 young, 0.52 mature, at most 13 m wide. Conifer: 0.28 to 0.30, at most 8 m.
     Other: 0.40 to 0.48, at most 12 m. The numbers are in `params.json` (`trees.crown_shape`).
   - At most 1.25 × the distance to the nearest tree on each side, so a stand stays a stand of separate crowns.
   - Never narrower than the survey's width.
   - Then thinned, as before, wherever more than 30% of the crown would lie over a building or water (scene rule).
2. Depth-tested per pixel against terrain, buildings and structures: a tree hides what is behind it, never what is
   in front.
3. No shadow in the layer (layer 9 casts crown shadows from the same crowns).
4. Seasons change only this layer's colour and foliage (layer 11), never its positions.

**Checks.**
- L7.1 (gate, as data checks TE6 and TE7) Crown size: no drawn crown wider than rule 1 allows for its species
  and height (or than the survey's width, where that is wider), and thinning only narrows. TE8 reports the median
  height over width (5.05 with the survey's widths, 2.19 with rule 1, on the test area). No tree is taller than
  measured (TE4).
- L7.2 (gate) 0 tree pixels in front of a nearer surface (depth test, per pixel).
- L7.3 (gate) Flat-share: no photo texture in crowns (the London check: share of near-flat 8×8 blocks within bounds).
- L7.4 (gate) Seams, layer-off and no-cars checks.
- Data checks TE1–TE4 (checks.md) gate the tree data.
