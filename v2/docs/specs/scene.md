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
  building footprint or in water; crown radius = 0.85 × crown_mean / 2 (the POC's "measured crowns read too big"),
  reduced (bisection) until ≤ 30% of the crown disc lies over buildings or water; base height = LiDAR terrain.
- **Output:** `trees.npz` (e, n, base_z, height, crown_r, crown_r_measured, type, uuid).
- **Checks:** TE1–TE5.

## Places (`scene_places`)
v1's 129 landmark cards and 1,035 places, streets and pins, from v1 pixels back to LUREF by the ray inversion on
v1's own terrain (camera.md), then given the LiDAR 2024 height and v2 pixels; v1 pixels are kept for links.
Card contents stay in v1's files (joined by slug). **Checks:** PL1, PL2a.

## Transport graph, transit, structures
See transport-graph.md and structures.md.

## Scope
Every part is cut to the area polygon (S1–S5); the area's extent in v2 pixels is in scene.json.
