# Layers (phase 1)

One module per layer of PLAN_V2 section 5, each a stage of the build graph that reads the scene (through
`scene/<key>/scene.json`) and writes its tile set with depth. The registry is `v2/config/layers.json`; each layer's
spec, with its numbered checks, is `v2/docs/specs/layer-NN-<id>.md`.

Rules for every module here: draw from the scene only (never from another layer's finished pixels), albedo only
for colour layers, colours from `config/palette.json`, and a layer's checks run as their own check stages. A
failing check is fixed here, in the layer that made it.
