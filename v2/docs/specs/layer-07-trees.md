# Layer 7: Trees and greenery

**Purpose.** Every tree at its measured place, at 70% of its measured height (rule 1), drawn as its species
(below), as part of the drawing, changing with the seasons.
**Made by:** code crowns (A, B) or an AI-painted canopy field (C), decided at the bake-off. Methods A and B: the
crown fills the drawn height down to its species' bare trunk; its width follows the species' shape and the
tree's age (rule 1); both draw the crown as leaf clumps (below; B has A's crowns by the owner's
decision of 10 Nov 2026). Method C uses the same code crowns unless a canopy is painted.

**Inputs.** Scene trees (`trees.npz`: LiDAR 2024 survey position, height, crown radius after thinning, type), the
palette (`trees.*`), terrain and buildings (depth).

**Output.** RGBA tiles, depth per pixel (each crown as a 3D shape on a trunk to the measured height), a crown mask
(for sway and seasons), id tiles.

**Species (the owner, 24 Nov 2026: research the trees of Luxembourg and model those).** 23 species are drawn,
those the city's tree register counts most (Ville de Luxembourg, Service Parcs: 23,940 trees; maples 16.5%,
limes 10.8%, oaks 8.6%, ash 6.4%, planes 5.6%, hornbeam 4.5%, horse chestnut 4.2%, elm 4.2%, cherry 3.6%, pine
3.2%, beech 3.0%, birch 3.0%) and the ones with a shape of their own (columnar maple, oak and hornbeam, Lombardy
poplar, weeping willow, ginkgo, spruce, yew, copper beech, purple cherry plum). `v2/config/tree_species.json` holds
them; `v2/layers/tree_forms.py` reads it. A species sets:
- **the outline** (`forms`): round, egg, flame, column, spire, cone, pyramid, dome, vase or weeping. An outline is
  the crown's radius from its foot to its top: widest at a given height, and above and below it a superellipse
  (power 2 a round arc, 1 a straight taper, more a boxier side);
- **the bare trunk** under the crown, as a share of the tree's height (a pine's is half, a street tree's 2 m at
  least, a spruce, a yew and a willow reach the ground), its bark colour (a birch's white, a plane's pale, a
  beech's grey, a pine's red-brown) and its thickness;
- **the width** (rule 1): crown width over measured height, young and mature, and the widest crown;
- **the texture**: a clump's size against the crown's (large leaves and heavy boughs coarse, small leaves fine),
  the share of clumps left out (a see-through crown), how uneven the outline is, and whether the lower clumps hang
  (willow, birch);
- **the colours**: its lit green and its shade (palette `trees.sp_<species>_light`, `_dark`), set against v1's
  foliage: a horse chestnut and a yew dark, a plane and a willow yellow-green, a birch light, a spruce blue-green.
Which species a tree is comes from the scene (`scene.md`, "Tree species"): the city's register where it names the
tree, else a rule. A tree the scene gives no species is drawn as its type's (`by_type`).

**Crown shape and variety (phase 3; v1's trees, the owner, 23 Nov 2026).** A crown is a dark inside (five shapes
up the crown, together the outline at 0.8 of its size) with leaf clumps all over the outline's surface, one of them
on top; a crown under 1.2 m radius stays one shape.
- **Clumps.** A clump is its species' share of the crown's radius (a maple's half; 0.6 m at least, the species'
  most, never over 0.6 of the crown's, and no wider than the crown where it sits, so a cone keeps its tip), its
  species' height over width (0.85 on most), each its own size (±30%). They are spread evenly over the outline's
  surface (golden angle, turned and jittered per tree), as many as cover it once with 1.5 of a clump's footprint
  each (8 at least), so the dark inside shows between them.
- **Tufts** (closer to v1: the owner, 24 Nov 2026). A clump is drawn as five leaf tufts, spheroids of about half its
  radius that all lie inside it: one facing out of the crown, four around that one, each its own size. From
  outside a clump reads as a cluster of leaves with a lobed outline, as v1's foliage does, and not as a ball. No tuft
  reaches beyond the tree's crown radius, above its top or below the crown's foot, and the top clump's outward tuft
  ends exactly at the tree's top, so rule 1 holds for every species (unit tests
  `test_crown_lobes_stay_inside_the_measured_crown`, `test_every_species_crown_stays_inside_its_size_and_has_its_outline`).
- **Colours** (`art_a.crown_rgb`). A clump is the tree's light green, each clump its own tone (±11%), each tuft a
  little its own (±5%), with a fine fleck of leaves (0.3 m, ±4%). A tuft is in three flat tones by how far its
  surface faces up, across ragged edges (0.45 m): light on top, a mid green on its side, the foliage's dark
  underneath. A tuft that sees little sky (low on its clump, or on a clump low on the crown) is darker. The core,
  seen between clumps, is the foliage's dark. The light and the dark are the species'; within a species each tree
  leans a little to a warmer or a cooler green (0.45 of the lean of palette `summer_light_warm`,
  `summer_light_cool`). On a tuft taller than wide (a hanging one) the tones go by how far up the tuft a point is.
- **Lines.** Ink (the foliage's dark at 0.55): 0.9 where foliage meets anything that is not foliage; 0.75 where two
  clumps meet, whether of one tree or of two, so a wood is drawn as one mass of clumps and not as a row of crowns;
  0.15 between the tufts of one clump.
- **Nothing follows the sun.** Clumps, colours and lines are hashes of the tree's index and of the place; the dark
  underside follows "up". What moves with the hour is the viewer's light on each clump's own normal (bright on the
  sunward side) and layer 9's cast shadows, from the same shapes.
- Before 23 Nov 2026 a crown was a core with five to seven large lobes, a mid green with a 0.8 m cell pattern.
  v1's foliage runs from [10, 23, 17] to [156, 176, 43] (5th to 95th percentile of luminance, three views); v2's
  ran from [33, 40, 24] to [120, 138, 68].

**Rules.**
1. Position comes from the survey; it is changed only to take a trunk off the face of a wall or a cliff (scene.md,
   Trees; TE13). **Height: every tree is drawn at 0.7 of its measured
   height** (`params.json` `trees.drawn_height_scale`; owner decision, 24 Nov 2026). The measured heights are right
   (they agree with the LiDAR surface to 1.7 m at the median) and the trees here are tall (median 16.8 m against
   13.4 m to the ridge for the median building), but drawn so they were too big beside the buildings. Of three
   sizes shown beside v1 (as measured; 80% of height and width; 70% of height with the width kept) the owner chose
   the last. `trees.npz` keeps both heights; the width below follows the measured one. The crown's width is the survey's
   (0.85 × crown_mean), widened to the tree's shape by species and age (owner decision, 9 Nov 2026: the survey's
   crowns are 2–5 m wide on trees 15–25 m tall, which drew poplars):
   - width = height × a ratio; the ratio grows evenly from a young tree (6 m or less) to a mature one (20 m or
     more). Height stands in for age, as the survey has no age.
   - The ratios and the widest crown are the species' (`tree_species.json`, `width`; from the register's mean
     height and crown width by genus, and nursery figures for the cultivars): a maple 0.50 young, 0.58 mature,
     at most 14 m; an oak 0.54 to 0.64, 18 m; a columnar oak 0.26 to 0.31, 6 m; a spruce 0.30 to 0.33, 8 m.
   - At most 1.25 × the distance to the nearest tree on each side, so a stand stays a stand of separate crowns.
   - Never narrower than the survey's width.
   - Then thinned wherever more than 30% of the crown would lie over a building, but never under half its shaped
     radius (scene rule). Water does not thin a crown: a tree on a bank hangs over the river.
2. Depth-tested per pixel against terrain, buildings and structures: a tree hides what is behind it, never what is
   in front.
3. No shadow in the layer (layer 9 casts crown shadows from the same crowns).
4. Seasons change only this layer's colour and foliage (layer 11), never its positions.

**Checks.**
- L7.1 (gate, as data checks TE6 and TE7) Crown size: no drawn crown wider than rule 1 allows for its species
  and height (or than the survey's width, where that is wider), and thinning only narrows. TE8 reports the median
  height over width (5.05 with the survey's widths, 2.19 with rule 1 at the measured height, on the test area).
  Every tree is drawn at exactly the stated share of its measured height, none taller than measured (TE9).
- L7.2 (gate) 0 tree pixels in front of a nearer surface (depth test, per pixel).
- L7.3 (gate) Flat-share: no photo texture in crowns (the London check: share of near-flat 8×8 blocks within bounds).
- L7.4 (gate) Seams, layer-off and no-cars checks.
- Data checks TE1–TE4 (checks.md) gate the tree data.
