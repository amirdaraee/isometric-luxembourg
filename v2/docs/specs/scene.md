# The scene

One scene per area, built once from raw data and versioned by the build graph (`python -m v2.build <area> scene`).
`scene/<key>/scene.json` indexes the parts (each a stage output with its own manifest). Data sources: DATA.md.

## Terrain (`scene_terrain`)
- **Inputs:** LiDAR 2024 ground (MNT) and surface (MNS) models, read as windows of ACT's national COGs: 0.5 m on
  the test area, 1 m on the commune (`params.json` areas.*.terrain_step_m), over the area's bounding box + margin.
- **Rules:** cells without data are filled from their nearest neighbour and counted; slope in degrees;
  class 1 *steep* where slope ≥ 35°, class 2 *cliff* where slope ≥ 60° and the drop over 3 m ≥ 2.5 m. OSM
  retaining walls, city walls, walls, cliffs and embankments are kept as lines with their top and foot measured on
  the terrain 1.5 m either side (`walls.json`).
- **Output:** `terrain.npz` (mnt, mns, slope, cls, e0, n0, step), `walls.json`.
- **Checks:** TR1–TR7.

## Water (`scene_water`)
OSM natural=water, waterway=riverbank, landuse=reservoir/basin and outdoor pools as polygons; rivers, streams and
canals as lines (culverts flagged). Output `water.json`. Used by trees (thinning) and checks.

## Buildings (`scene_buildings`)
- **Inputs:** ACT LoD2.2 3D buildings 2023 v2 (CityGML, CC0), streamed. The file stores northing, easting, height.
- **Kept:** buildings whose footprint (union of GroundSurfaces) has its representative point in the area and is
  ≥ 2 m².
- **Per building:** ACT id (gml:id), creation date, measured height, ground/eave/ridge heights, footprint rings,
  roof planes (slope, azimuth, area, z range), **roof shape**, walls (3D rings with their surface id), **parts**
  (the BuildingInstallations: dormers, chimneys, porches; the file has no BuildingPart elements), terrain height at
  the footprint.
- **Roof shape rule:** planes with slope ≤ 8° are flat. If sloped planes cover < 15% of the roof area: *flat*.
  Otherwise the sloped area is binned into 4 quadrants around the largest plane's azimuth (a quadrant counts when it
  holds > 8%): one quadrant *shed*, two opposite *gable*, three or four *hip* (*mansard* when four with both
  > 55° and < 45° slopes), else *complex*; prefixed *mixed:* when sloped planes cover < 80%.
- **Mesh:** every surface triangulated (earcut in its plane), vertices relative to the camera origin, with kind
  (0 ground, 1 roof, 2 wall, 3 installation) and building index (`mesh.npz`).
- **Checks:** B1–B7, TR4.

## Facades (`scene_facades`)
See facades.md. Checks F1–F7.

## Trees (`scene_trees`)
- **Input:** ACT LiDAR 2024 tree survey (CC0, crown centroids with height, crown widths and type), cut to the
  commune while streaming (`fetch_trees`).
- **Rules:** keep trees in the area 2–50 m tall (taller are survey spikes: cranes, masts); drop trees centred in a
  building footprint or in water; a trunk cannot stand on the face of a wall or a cliff (owner, 25 Nov 2026):
  the survey's point is the crown's top, which can hang over a face, so a tree whose point is on a cliff cell
  gets its trunk on the nearest ground that is not one, within its measured crown's radius plus 1 m (1.5 to 4 m):
  above the point if there is such ground, else below it; its top keeps its height above the sea, so its own
  height is its top above its new foot; a tree with no such ground in reach is left out (`trees.off_faces`); crown radius = 0.85 × crown_mean / 2 (the POC's "measured crowns read too big"),
  widened to the tree's shape by species and age (layer-07 rule 1, by the measured height), then
  reduced (bisection) until ≤ 30% of the crown disc lies over buildings or water; base height = LiDAR terrain;
  drawn height = 0.7 × the measured height (layer-07 rule 1; owner, 24 Nov 2026).
- **Output:** `trees.npz` (e, n, base_z, height as drawn, height_measured, crown_r, crown_r_shape,
  crown_r_measured, type, type_survey, uuid, species, species_names, species_rule, species_rules).
- **Checks:** TE1–TE13.

### Tree species (`v2/data/scene/tree_species.py`, `v2/config/tree_species.json`)

The survey says only green broadleaf, red-leaved, conifer or other for a tree. Each tree is given one of the 23
drawn species (layer-07, "Species"); the first of these that applies decides:

0. **register**: the city's tree register (`fetch_city_trees`: Ville de Luxembourg, Service Parcs, 23,940 trees
   with Latin name and cultivar). A register tree names the surveyed tree nearest to it, within 4 m (the register's
   point is the trunk, the survey's the crown's top); where several are near one surveyed tree, the nearest. Its
   species is drawn as the nearest of the 23 (`assign.cultivars`, then `assign.genus`: an alder as a hornbeam, a
   pear as a columnar hornbeam, a cedar as a pine). Such a tree takes its type from its species. The register
   states no licence; it is used by the owner's decision of 25 Nov 2026 (`DECISIONS.md`).
1. **osm**: an OpenStreetMap tree with a species or genus within 3 m.
2. **named**: a street or square whose trees are known (`assign.named`: Place d'Armes and Place Guillaume II
   planes, Montée du Grund limes, Montée de Pfaffenthal horse chestnuts, Boulevard Royal maples, and others).
3. **type**: a conifer is a pine, a spruce or a yew; a red-leaved tree a copper beech or a purple cherry plum.
4. **water**: within 9 m of a river or a pond: the riverside mix.
5. **street**: within 9 m of a street's centre line and not in a wood: one species per named street (drawn from
   the street mix), but for 15% of its trees.
6. **wood**: in an OSM wood or forest, or with 6 trees within 9 m: the wood mix, in patches of 28 m.
7. **park**: the rest: the park mix, in groups of 18 m.

A mix is weighted by the register's shares unless it gives its own weights; a species is only given to a tree
whose measured height is within the species' range. Every draw is a hash of the tree's place: the same tree gets
the same species in every build and in every area. **Rules 3 to 7 are plausible, not true tree by tree**; TE11
reports how many trees each rule set.

## Ground cover (`scene_groundcover`)

Vegetated ground where OSM classes nothing (owner, 23 Nov 2026: v1's ground; layer-01 rule 1). The orthophoto
(2023, the tiles v1 downloaded, about 0.39 m a pixel) classes the land; it is never a colour.

1. A grid of 0.5 m over the area. A cell is *readable* where the photo has a tile and shows ground that can be
   told: not under a building's footprint, not within 1.5 m of a surveyed tree's measured crown, not in deep
   shadow.
2. A readable cell is *green* where its excess green, (2g − r − b) / (r + g + b), is over 0.07.
3. A cell is *vegetated* where the green share of the readable land within about 5 m (a Gaussian) is 35% or
   more. A cell with no readable land in reach takes the nearest decided cell's answer. So a lawn keeps its dry
   patches, a square keeps its planter, and a street tree's crown does not turn its pavement into lawn.
4. Patches and holes under 20 m² are dropped.

`groundcover.npz`: `veg`, `photo` (a tile there), `e0`, `n0`, `step`. `vegetated(grid, e, n)` reads a patch's
border as a smooth line between the cells (layer-01-ground.md rule 2), not cell by cell. Limits: the photo is of a dry summer, so a
straw-coloured lawn is not told from paving and stays paved; the photo on disk covers v1's extent, not yet the
whole commune (GC1 fails where it does not).

## Roofs (`scene_roofs`)

Each building's roof covering, read from the orthophoto (`v2/data/scene/roofs.py`; the owner, 26 Nov 2026: the
real roofs, not a share by rule). The 3D buildings give a roof's shape, not what covers it. The photo classes the
roof and never colours it: a roof gets one of the palette's roof colours, so no shadow and nothing lying on a roof
can reach a layer.

1. The photo is read at a grid of 0.4 m inside the footprint drawn in by 1.2 m, not within 1 m of a surveyed
   tree's crown and not in deep shadow. A roof with fewer than 20 such points is not read; the art's rule decides.
2. A point's warmth is (r − b) / (r + g + b): fired clay is red over blue, slate and zinc blue over red.
3. A pitched roof is tile where its median warmth and half its points reach 0.07 (bright tile from 0.15, else
   brown); every other pitched roof is slate, in the shade the photo shows: dark under a median luminance of 117,
   else blue at −0.048 or less, warm grey at −0.022 or more, else plain.
4. A flat roof is planted where its median excess green is 0.07 or more, under gravel where its warmth is 0.03 or
   more, else grey.

The tile threshold lies in an empty stretch of the test area's roofs (three pitched roofs at 0.09 and over, the
next at 0.03); the slate shades' thresholds are the quartiles of what the photo shows there. Test area: of 1,135
buildings 1,111 are read; slate 996 (plain 407, warm 240, dark 233, blue 116), tile 3, flat grey 84, gravel 25,
planted 3.

Checks (`check_roofs`, in G0): RF0 every building has a record; RF1 the photo reads at least 85% of the roofs; RF2
a flat roof never gets slate or tile, a pitched one never a flat roof's covering; RF3 every covering is a palette
colour. Unit tests: `v2/data/tests/test_roofs.py`.

Not known: whether the photo's roofs are moved off their footprints by the building's height (the photo is not
stated to be a true orthophoto). The inset and the median guard against it; on the 40 warmest roofs looked at, the
footprint's centre lay on the roof.

## Places (`scene_places`)
v1's 129 landmark cards and 1,035 places, streets and pins, from v1 pixels back to LUREF by the ray inversion on
v1's own terrain (camera.md), then given the LiDAR 2024 height and v2 pixels; v1 pixels are kept for links.
Card contents stay in v1's files (joined by slug). **Checks:** PL1, PL2a.

## Transport graph, transit, structures
See transport-graph.md and structures.md.

## Scope
Every part is cut to the area polygon (S1–S5); the area's extent in v2 pixels is in scene.json.
