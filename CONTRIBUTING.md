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
    npm run dev                 # http://localhost:3000, every feature switched on
    npm run build               # the public release in web/dist (switches from .env.production)
    npx vite preview --port 3001   # check that build: no buttons or rows for switched-off features

You need the tiles in `web/public/tiles/` to see the map. Build them with the pipeline (see the README).

Before a pull request, run the checks (Node 22.6 or newer runs the TypeScript tests directly):

    npx tsc --noEmit -p .
    node src/scene.test.ts                      # time, season, Christmas and event controls
    node src/calendar.test.ts                   # event dates
    node src/sim/traffic.test.ts                # traffic simulation
    node src/components/transit.test.ts         # trams and trains
    node src/sky/weatherCore.test.ts            # weather
    node src/sky/flights.test.ts                # planes
    node src/sim/roadfit.test.ts 5 0.75 --min 95   # cars on the painted roads (needs the road masks)

Useful test parameters in the address (see `web/src/testParams.ts`): `?hour=21.5`, `?season=winter`,
`?date=2026-12-24`, `?weather=rain:0.8`, `?event=schueberfouer`, `?seed=42`, `?roaddebug`, and `?on=perfHud` for a
frame-time readout. `npm run perf` measures start-up and frame times on a desktop and a phone profile.

- **New optional features need a switch.** Add a key to `DEFAULTS` in `web/src/features.ts` with a one-line
  comment, and check it with `on("yourFeature")` where the feature is drawn. Test it with `?off=yourFeature`.
  A feature that is not ready for the public goes into `VITE_FEATURES_OFF` in `web/.env.production`.
- **Animate through the frame clock** (`web/src/frame.ts`, `subscribe`), not your own `requestAnimationFrame`
  loop, and don't put per-frame state in React state: the map moves sixty times a second.
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

## Reporting a problem

Open an issue on [GitHub](https://github.com/amirdaraee/isometric-luxembourg/issues) with what you saw, what you
expected, and a link to the view: every view has its own address (`#x,y,zoom`), so the share button gives the
exact spot. Add the browser and device, and a screenshot for anything visible. On the site itself, "Mark a spot"
sends a private note about a place on the map.

## Licences and credits

Code is MIT. The art (the painted map, the drawings and the statues) is CC BY-NC 4.0 ([LICENSE-ART.md](LICENSE-ART.md)):
contributions to the art are accepted under the same licence, and the art may not be used commercially.

All map data must have an open licence that allows redistribution. Credit it in the README table and in the
viewer's "About and credits" panel. Landmark photos must come with author, licence and source, which the card
shows. Don't add photos without a clear licence.

## Commits and pull requests

- One topic per pull request, with a short description of what changed and how you checked it. Add a screenshot
  for anything visible.
- Don't commit tiles, renders, datasets, model weights or anything from `data/`.
