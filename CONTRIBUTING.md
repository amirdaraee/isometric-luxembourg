# Contributing

Thanks for helping draw Luxembourg. Issues and pull requests are welcome. Small fixes can go straight to a pull
request. For bigger changes, such as a new layer, a new event or a pipeline change, please open an issue first so
we can agree on the approach.

## Layout

| Folder | What | In git |
|---|---|---|
| `web/` | The viewer: React, Vite, OpenSeadragon, plus three.js for the 3D models | yes |
| `web/public/data`, `events`, `landmarks` | Small data the viewer loads (places, streets, transit, landmark cards) | yes |
| `web/public/tiles/` | The map tiles: build output, hundreds of MB | no |
| `web/public/live`, `style-test` | Local work-in-progress pages, never published | no |
| `web/worker/` | Cloudflare Worker for serving tiles from R2 (whole-city release) | yes |
| `pipeline/` | Python: 3D render, map guides, GPU painting, checks, tile building | code only |
| `research/` | Notes and sources about landmarks, interiors, events and history | text only |
| `data/` | Raw downloads and work files (about 30 GB) | no |

## Working on the viewer

    cd web
    npm install
    npm run dev                 # http://localhost:3000
    npx tsc --noEmit            # type-check before a pull request
    npm run build               # production build in web/dist

You need the tiles in `web/public/tiles/` to see the map. Build them with the pipeline (see the README).

- **New optional features need a switch.** Add a key to `DEFAULTS` in `web/src/features.ts` with a one-line
  comment, and check it with `on("yourFeature")` where the feature is drawn. Test it with `?off=yourFeature`.
- **Load public files through `asset()`** from `web/src/config.ts`, never as a bare `"/data/..."` path. That way
  the site also works under a sub-path such as `https://<user>.github.io/isometric-luxembourg/`.
- Map positions are in map pixels (the full mosaic). Convert to the screen through the base image, with
  `map.current.toScreen()`, not through the OpenSeadragon viewport. The viewport stops working once extra map
  versions are layered on.
- Keep the UI accessible: real buttons, `aria-pressed` on toggles, and labels on icon buttons.

## Working on the pipeline

    cd pipeline
    uv venv && uv pip install -r pyproject.toml

- **GPU work runs on rented machines (RunPod).** Every pod script has a deadline watchdog that stops the pod.
  Keep that pattern. Painting and training scripts are in `pipeline/gpu_train/`, and `NOTES.md` there records
  what went wrong before and why.
- **Paid API calls** (the drawing service in `pipeline/style`, `night` and `events`) log their cost to
  `data/work/style/openai_spend.json` and take a spending cap as an argument. Keep the cap.
- **Base art rules:** nothing that moves is painted in (no cars, trams, trains, people or birds). Water is flat,
  trees are summer, and daytime shadows are baked in. Night and the seasons are separate painted versions, and
  moving things are live layers in the viewer.
- After painting, run `water_check.py` and look at the seams. Check bridges by eye: the Red Bridge's deck is grey
  and only its sides are red.

## Secrets

API keys live in `pipeline/.env` (OpenAI) and `~/.runpod/config.toml` (RunPod). Both are outside git. Never
paste a key into code, docs, logs or an issue. If one leaks, rotate it.

## Licences and credits

All map data must have an open licence that allows redistribution. Credit it in the README table and in the
viewer's "About and credits" panel. Landmark photos must come with author, licence and source, which the card
shows. Don't add photos without a clear licence.

## Commits and pull requests

- One topic per pull request, with a short description of what changed and how you checked it. Add a screenshot
  for anything visible.
- Don't commit tiles, renders, datasets, model weights or anything from `data/`.
