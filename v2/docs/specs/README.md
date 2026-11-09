# v2 specs

One short spec per part, each with numbered pass/fail checks. A check is a gate: the build stage that runs it fails
(non-zero exit) when it fails. Check ids are stable; a spec change that alters a check is a decision for the owner
at the next gate. Thresholds live in `v2/config/params.json`, not in the specs, so they are changed in one place.

Status of each check: **built** (implemented and run in Phase 0), **phase N** (written now, built with its layer).

| Spec | What |
|---|---|
| [conventions.md](conventions.md) | Words, units, tile format and the check numbering used by every spec |
| [camera.md](camera.md) | Projection and map-pixel coordinates (kept from v1) |
| [scene.md](scene.md) | The scene: terrain, water, buildings, trees, places |
| [facades.md](facades.md) | Facade layout: floors and windows per wall |
| [transport-graph.md](transport-graph.md) | Roads, rail and tram graph with height profiles; transit matching |
| [structures.md](structures.md) | Bridges and the modelled viaducts |
| [checks.md](checks.md) | The checks framework and every G0 data check |
| [palette.md](palette.md) | The one palette |
| [tiles-hosting.md](tiles-hosting.md) | Tile sets, versions and R2 hosting |
| [compositor.md](compositor.md) | The viewer's WebGL layer compositor |
| [ledger.md](ledger.md) | The spend ledger |
| [layer-01-ground.md](layer-01-ground.md) … [layer-15-labels.md](layer-15-labels.md) | The 15 layers of PLAN_V2 section 5 |
