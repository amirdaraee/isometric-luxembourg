# Isometric Luxembourg

Luxembourg City as an explorable isometric map, drawn as an inked illustration and seen from the south-east.
It runs from the Pétrusse and Alzette gorges up to Kirchberg.

**Release 1.0** paints the old town in full. The rest of the city still shows the 3D data underneath and will be
painted next (see [ROADMAP.md](ROADMAP.md)).

## What's in it

- **Time of day:** the map follows Luxembourg's real clock. It cross-fades through golden hour into a painted night
  with lit windows and streets, and the daytime shadows go away. A slider lets you pick any hour.
- **Seasons:** painted spring, summer, autumn and winter versions. Winter includes snow, and winter night is painted too.
- **Christmas markets:** a toggle that adds the Winterlights markets to Place d'Armes, Place de la Constitution
  and Place Guillaume II, by day and by night.
- **Traffic:** cars drawn on the real street network, plus trams and trains moving on today's real timetable (GTFS).
- **Landmarks:** 47 cards with history, interiors and cutaway drawings. Many have a 3D model you can turn and
  credited photos.
- **Search and sharing:** search places, streets and addresses, or press "Surprise me". Every view has its own
  link.

Every optional feature can be switched off. See [Feature switches](#feature-switches). The public release at
**[isometric.lu](https://isometric.lu)** starts small, with the summer day map, landmark
cards, search and street names. Time of day, seasons, Christmas, traffic, trams, trains and the 3D models are
switched on locally and will be switched on publicly one by one.

## Run it locally

    cd web
    npm install
    npm run dev          # http://localhost:3000

The map tiles (`web/public/tiles/`) are build output and are not kept in git. Either build them with the
pipeline below, or copy them from someone who has.

## Feature switches

All switches live in [`web/src/features.ts`](web/src/features.ts) and are on by default:
`timeOfDay`, `seasons`, `christmas`, `snow`, `traffic`, `transit`, `streets`, `pins`, `search`, `surprise`,
`share`, `landmarks`, `interiors`, `models3d`, `photos`, `previewBadge`.

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
(open it at `http://localhost:3000/admin/index.html`). The switch is off in the public release until the Worker is
deployed. See [web/feedback-worker/README.md](web/feedback-worker/README.md) for the endpoints, the security
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
   streets, cars, trams and trains.
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
| Landmark photos | Wikimedia Commons, credited on each card | per photo |

The viewer started as a fork of [isometric-nyc](https://github.com/cannoneyed/isometric-nyc) by Andy Coenen (MIT,
see `web/LICENSE.isometric-nyc`). The map is shown with [OpenSeadragon](https://openseadragon.github.io) and the
3D models with [three.js](https://threejs.org).

## Licence

Code: [MIT](LICENSE). Art (the painted map and drawings): [CC BY-NC 4.0](LICENSE-ART.md). Data and photos keep
their own licences, listed above.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
