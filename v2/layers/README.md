# Layers (phase 1: built for the test area)

One module per layer of PLAN_V2 section 5, each a stage of the build graph that reads the scene (through
`scene/<key>/scene.json`) and writes its tile set with depth. The registry is `v2/config/layers.json`; each layer's
spec, with its numbered checks, is `v2/docs/specs/layer-NN-<id>.md`.

Rules for every module here: draw from the scene only (never from another layer's finished pixels), albedo only
for colour layers, colours from `config/palette.json`, and a layer's checks run as their own check stages. A
failing check is fixed here, in the layer that made it.

## Built in phase 1

| Module | What |
|---|---|
| `common.py` | camera frame in tiles, tile codings (depth against a per-row plane, octahedral normals, delta+zlib data tiles), the scene loader, palette |
| `raster.py` | the terrain seen through the camera (exact on the bilinear surface), triangles and crowns with a depth buffer |
| `geometry.py` | 3D geometry from the scene: buildings, facade openings, bridge decks, structures, viaducts, portals, walls |
| `render.py` | one function per colour layer (1 ground, 2 relief, 3 water, 4 transport; 5-7 plain code placeholders) |
| `tiles.py` | zoom 0 in parallel, the pyramid (geometry from the nearest surface, never averaged), index.json |
| `light.py` | layer 9's shadow height map and the Python reference of the viewer's shadow march |
| `data.py` | layer 10 (windows, lamps), 12 (roads, profiles, trams and trains on the graph), 15 (labels) |
| `stages.py` | the build stages (`layer_*`, `release`) |
| `tunnels.py` | phase 3, the tunnel view: the tunnels of the graph and the casemate galleries as tubes (`layer_tunnels`) |

Layers 5-7 are the bake-off's (PLAN_V2 section 7); phase 1 draws plain, evenly lit placeholders from the same
geometry so the compositor, the light and the vehicle checks have something real to work on.
