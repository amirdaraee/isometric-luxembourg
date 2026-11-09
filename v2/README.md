# Isometric Luxembourg v2

The whole City of Luxembourg as a layered isometric map, built from the data: ACT's 3D buildings, terrain and
LiDAR and OpenStreetMap are the truth, art is held to them, light comes from code (PLAN_V2.md). v1 keeps running
on `main` until v2 is better everywhere. This folder is Phase 0, "Foundation": the build graph, the data, the scene
and transport graph with their checks, the specs and the spend ledger. No GPU and no paid service is used.

## Layout (PLAN_V2 section 12)

```
v2/
  config/     areas (test, commune, the 24 quarters), camera, sun, palette, layer registry, params (every threshold)
  data/       fetch/ (downloads), scene/ (terrain, water, buildings, facades, trees, places, transport graph,
              transit, structures), structures/ (the hand-modelled viaducts, as data)  -> <data>/v2/ (gitignored)
  layers/     one module per layer (phase 1)
  checks/     the checks framework and every check; all are build gates
  build/      the build graph (graph.py), its stages (stages.py), the command (python -m v2.build), reports
  web/        the v2 viewer with the layer compositor (phase 1)
  docs/       specs/ (one per layer and part), DATA.md (sources and licences), PHASE0_REPORT.md, img/, results/
  ledger/     spend ledger: budget.json, spend.jsonl, ledger.py
```
Tests sit next to what they test (`*/tests/`); `pytest.ini` makes `python -m pytest v2` find them all.

## Running

```sh
uv venv .venv -p 3.12 && uv pip install -p .venv/bin/python -r v2/requirements.txt
export ISOLUX_DATA=/path/to/repo/data       # where data/raw (v1's downloads) lives; v2 writes data/v2
.venv/bin/python -m v2.build test           # build the test area to gate G0: fetch, scene, checks, previews
.venv/bin/python -m v2.build test --list    # every stage, its status and its output folder
.venv/bin/python -m v2.build commune scene_transport check_transport_profiles
.venv/bin/python -m pytest v2               # unit tests (no downloads, about a second)
.venv/bin/python -m v2.ledger.ledger status
.venv/bin/python -m v2.build test g1         # phase 1: the code layers, the viewer's data and every G1 check
.venv/bin/python -m v2.view test            # the viewer: http://localhost:5174/ (Node 22+; installs its packages once)
```

## The build graph

`python -m v2.build <area> [stage ...]` builds the stages and everything they need, in order (default target:
`g0`). Each stage's output folder is `<data>/v2/<area>/<stage>/<key>/` (shared downloads: `<data>/v2/_shared/`),
where the key hashes the stage's code, its parameters (from `config/params.json`), its dependencies' keys and the
fingerprints of the raw files it reads. So:
- **versioned:** a changed input makes a new folder; old versions stay until cleaned;
- **resumable:** a stage whose folder holds a manifest with status "ok" is skipped; work happens in a temporary
  folder renamed when complete;
- **manifests:** every folder has `manifest.json` (inputs hash, code hash and git version, params, deps, raw inputs,
  files, bytes, seconds, summary);
- **gates:** a check stage that fails is recorded as "failed", nothing downstream of it runs, and the command exits
  1. Fix the layer or data that made the failure; there is no stage that edits finished outputs (check N1–N2).

Heavy stages run one at a time and use at most `params.json` "workers" (or `V2_WORKERS`) cores.

## Areas

- `test`: Grund, Pfaffenthal and the Bock, 1.57 km² (PLAN_V2 section 4), drawn around every hard case:
  `config/areas/test.geojson`.
- `commune`: the City of Luxembourg's administrative boundary (OSM relation 407489, 51.7 km²) and its 24 quarters:
  `config/areas/commune.geojson`, `commune_quarters.geojson` (written by `python -m v2.data.fetch.boundary`).

## Where things are explained

- Plan and principles: `PLAN_V2.md`; owner decisions: `research/v2/DECISIONS.md`; v1's lessons: `research/v2/V1_RETRO.md`.
- Specs and checks: `docs/specs/README.md`. Data sources and licences: `docs/DATA.md`.
- What Phase 0 built and the gate G0 results: `docs/PHASE0_REPORT.md` and `docs/results/g0_<area>.json`.
