# Conventions

- **Coordinates.** Scene geometry is in LUREF (EPSG:2169) metres, E and N, with z in metres above sea level (the
  national LiDAR heights). Map pixels exist only through `v2/config/camera.py` (see camera.md).
- **Resolution.** 0.125 m per map pixel at the deepest zoom (v1: 0.25 m).
- **Tiles.** 512 × 512 px, one tile set per layer and channel group, zoom 0 = full resolution, each level halves
  (tiles-hosting.md). Colour: WebP, lossy q≈90 for painted/code colour, lossless for masks and ids,
  and lossless for layers 5-7 (phase 2: their detail loses more than C1c's 3/255 at q90). Depth: 16-bit
  (two 8-bit channels of a lossless WebP), centimetres of view depth relative to the tile's minimum, with the minimum
  in the tile index. Normals: octahedral, two 8-bit channels, lossless.
- **Depth.** "Depth" is `camera.depth(e, n, z)`: metres along the view ray, smaller is nearer the camera. Every
  layer that draws something ships its depth (principle 4).
- **Light.** No layer except 9 (light) and 10 (night) carries light: colour layers are albedo, evenly lit
  (principle 3).
- **Nothing that moves** is in any layer's input or output (principle 5): no vehicles, people, boats, birds.
- **Check ids.** `<part><n>` (for example P7, F3, L4.2). Severity "gate" fails the build; "report" is measured and
  shown only. Each check names its measurement, its threshold (from params.json) and up to eight failing examples.
- **Areas.** `test` (Grund, Pfaffenthal and the Bock) and `commune` (the City of Luxembourg, 24 quarters), as
  polygons in `v2/config/areas/`. Everything is built and approved on `test` first (principle 7).
