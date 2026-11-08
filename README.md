# Isometric Luxembourg

Luxembourg City as an explorable isometric map, drawn as an inked illustration and seen from the south-east.
It runs from the Pétrusse and Alzette gorges up to Kirchberg.

See it at **[isometric.lu](https://isometric.lu)**.

**Version 1** paints central Luxembourg City in summer, by day and by night. More of the city, the other seasons
and the moving life (traffic, trams, trains, planes, weather) are built and switched on locally, and will be
switched on publicly one by one (see [ROADMAP.md](ROADMAP.md)).

## What's in version 1

- **Time of day:** the map follows Luxembourg's real clock ("Live"). It cross-fades through golden hour into a
  painted night with lit windows and streets. The slider picks any hour.
- **Living details:** light glinting on the rivers, and a soft sea of cloud round the edges of the map.
- **Landmarks:** pins with labels, and cards with history, interiors and cutaway drawings, credited photos and, for
  many, a 3D model you can turn.
- **Streets:** a layer with the streets and their names.
- **Search and sharing:** search places, streets and addresses; every view has its own link, and the share button
  copies it.
- **Notes from visitors:** "Mark a spot" sends the author a private note about a place on the map.

Built and switched off in the public release for now: seasons (spring, autumn, winter, winter night), the Christmas
markets and other city events, traffic with emergency vehicles and signals, trams and trains on today's timetable,
famous statues, birds, planes, rain, snow, fog and wind, and tilt-shift. Every one of them has a feature switch;
see [Feature switches](#feature-switches).

## Run it locally

    cd web
    npm install
    npm run dev          # http://localhost:3000, every feature on
    npm run build        # the public release in web/dist, with the switches in .env.production
    npx vite preview     # serve that build

The map tiles (`web/public/tiles/`) are build output and are not kept in git. Either build them with the
pipeline below, or copy them from someone who has.

## Feature switches

All switches live in [`web/src/features.ts`](web/src/features.ts), each with a one-line comment, and are on by
default in development (except `perfHud`). The public release switches off the ones listed in
`web/.env.production`.

There are several ways to turn them off. Later ones in the table win:

| Where | How |
|---|---|
| Every build | edit `DEFAULTS` in `web/src/features.ts` |
| Public release only | `web/.env.production` (the dev server ignores it) |
| At build time | `VITE_FEATURES_OFF="christmas,transit" npm run build` (`VITE_FEATURES_ON` forces on) |
| In the browser, for testing | `?off=christmas,transit` or `?on=christmas` |

## Publish to GitHub Pages

The site is static. The map tiles are built locally and published together with the site, as one fresh commit on
the `gh-pages` branch, so the main branch's history never carries hundreds of MB of tiles.

    cd web
    npm run deploy                                        # the release domain, isometric.lu (CNAME=... to change)
    VITE_BASE=/isometric-luxembourg/ npm run deploy       # or https://<user>.github.io/isometric-luxembourg/

Then, in the repository settings under **Pages**, choose "Deploy from a branch" and select `gh-pages` / root.
For a custom domain, also point DNS at GitHub Pages: an `ALIAS`/`A` record for the apex, or a `CNAME` for a
subdomain. Then tick "Enforce HTTPS".

The build drops the local-only pages (`public/live`, `public/style-test`) and the files of switched-off features,
such as the other painted versions, the Christmas patches and the 3D models. It also refuses to publish more than
1 GB, which is the GitHub Pages limit. The first release is about 125 MB; with every feature on, it is about 470 MB. The whole city will be larger, so
its tiles will go to Cloudflare R2. Build with `TILES_URL=https://tiles.example` and serve them through the worker
in `web/worker/`.

## Notes from visitors

The `comments` switch adds a "Mark a spot" button (shortcut `M`). Visitors draw a box on the map and send the
author a private note. The notes go to a small Cloudflare Worker with D1 in `web/feedback-worker/`, protected
by Turnstile and rate limits. Only the author reads them, on the local-only page `web/public/admin/index.html`
(open it at `http://localhost:3000/admin/index.html`). The button shows only when the build knows the Worker's
address (`VITE_FEEDBACK_API`). See [web/feedback-worker/README.md](web/feedback-worker/README.md) for the endpoints, the security
layers and deployment.

## How the map is made

The pipeline lives in `pipeline/` (Python 3.11+, `uv venv && uv pip install -r pyproject.toml`).

1. **Geometry:** `parse_citygml.py`, `fetch_base.py`, `fetch_lidar.py`, `crop_lidar.py`, `build_terrain.py`
   and `build_bridges.py` produce the textured 3D city on real terrain, with bridges.
2. **Render:** `render.py` renders isometric frames. It also writes `--kinds` (ground, bridge, walls, roofs) and
   `--lines` (edges plus a window grid) passes, which guide the painter.
3. **Guides from map data:** `fetch_lines.py`, `fetch_parking.py`, `fetch_green.py` (OpenStreetMap),
   `make_hint.py` (true water, clean tracks, parked cars removed) and `layout.py` (a colour-coded layout map).
4. **Painting:** a style LoRA for Qwen-Image-Edit-2511, trained with ostris/ai-toolkit on drawings made for this
   map (`pipeline/style/`, `pipeline/gpu_train/`). It paints the map window by window with red-box infill and
   colour-drift correction (`gpu_train/tiles/tiler.py`). The work runs on rented GPUs (RunPod).
   `gpu_train/NOTES.md` and `RETRAIN_PLAN.md` hold the details.
5. **Night, golden hour and seasons:** a second LoRA (`luxembourg-light`, `pipeline/night/`) converts the painted
   day into each version (`gpu_train/variants.sh`).
6. **Events and landmarks:** `pipeline/events/` adds Christmas markets and cutaway interiors.
   `build_landmarks.py` builds the landmark cards from `research/`.
7. **Live layers:** `project_lines.py`, `export_visibility.py` and `build_transit.py` produce the data for the
   streets, cars, trams and trains. `build_drivable.py`, then `fit_roads.py`, fit the streets and tracks to the
   roads and rails as painted (the vehicles drive on the fitted lines). Run `fit_roads.py --remeasure` again whenever the day
   art changes or `project_lines.py` rewrites `lines.json`, then check with `node src/sim/roadfit.test.ts` in `web/`.
8. **Tiles:** `build_tiles.py` builds the day map. `build_variant_tiles.py <version> ...` builds each other version.

Checks: `water_check.py` compares the painted water with OpenStreetMap, `seam_check.py` finds visible tile seams,
and `fix_redbridge_deck.py` keeps the Red Bridge's deck grey.

## Data and credits

| Layer | Source | Licence |
|---|---|---|
| 3D buildings 2023 (LOD 2.2, textured) | Administration du Cadastre et de la Topographie | CC0 |
| Orthophoto 2023 | Administration du Cadastre et de la Topographie | CC0 |
| LiDAR terrain 2019 (bare earth) | data.public.lu | CC0 |
| Places, streets, addresses, rail, water, parking | © OpenStreetMap contributors | ODbL |
| Tram and train timetables (GTFS) | data.public.lu | CC BY 4.0 |
| Live weather | [Open-Meteo](https://open-meteo.com) | CC BY 4.0 |
| Landmark photos | Wikimedia Commons, credited on each card | per photo |

## Acknowledgements

This map stands on other people's work:

- **[isometric-nyc](https://github.com/cannoneyed/isometric-nyc)** by Andy Coenen: the viewer started as a fork of
  it (MIT, see `web/LICENSE.isometric-nyc`), and its idea of a whole city painted as one isometric illustration
  started this project.
- **[Pixel Singapore](https://www.yadongxie.com/blog/how-pixel-singapore-was-made)** by Yadong Xie: the painting
  method (the whole canvas painted in shifted windows), the foreground layer that hides vehicles behind buildings,
  and the ideas for traffic, water and trees.
- **isometricsf.com**: the quality we aim for.
- **Luxembourg's open data:** the Administration du Cadastre et de la Topographie (3D buildings, orthophoto,
  served through [geoportail.lu](https://www.geoportail.lu)) and [data.public.lu](https://data.public.lu)
  (LiDAR terrain, public transport timetables), with the surroundings' terrain from the
  [Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) on AWS Open Data.
- **[OpenStreetMap](https://www.openstreetmap.org/copyright) contributors**, read through the
  [Overpass API](https://overpass-api.de): places, streets, rail, water and parking.
- **[Open-Meteo](https://open-meteo.com):** the live weather.
- **[Wikimedia Commons](https://commons.wikimedia.org)** photographers, credited on each landmark card.
- **Painting:** [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511) by the Qwen team, with
  our own style and light LoRAs trained with [ostris/ai-toolkit](https://github.com/ostris/ai-toolkit), and the
  [Lightning](https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning) distillation by lightx2v for faster
  repaints; the GPUs are rented from [RunPod](https://www.runpod.io). The drawings the style was trained on, and the
  statues, were made with OpenAI's image API.
- **Viewer:** [OpenSeadragon](https://openseadragon.github.io) shows the map, [three.js](https://threejs.org) the 3D
  models, built with [React](https://react.dev) and [Vite](https://vite.dev).

## Licence

Code: [MIT](LICENSE). Art (the painted map and drawings): [CC BY-NC 4.0](LICENSE-ART.md). Data and photos keep
their own licences, listed above.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
