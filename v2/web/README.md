# v2 viewer (phase 1)

The layer compositor of `v2/docs/specs/compositor.md`, in WebGL2, over the tiles of a built release.

```sh
python -m v2.build test release     # build the test area's layers and the viewer's data (once; ~10 min)
python -m v2.view test              # serve it: http://localhost:5174/  (installs the Node packages the first time)
```

`python -m v2.view` runs this folder's Vite dev server, which serves the release from
`$ISOLUX_DATA/v2/<area>/release/<current>/` under `/data/` (`vite.config.ts`). Equivalent by hand:
`cd v2/web && npm ci --ignore-scripts && ISOLUX_DATA=/path/to/data npx vite`.

## What is where

| File | What |
|---|---|
| `src/main.ts` | navigation (drag, wheel, pinch), the clock, the panel, labels and hover, test hooks (`window.__v2`) |
| `src/gl/compositor.ts`, `src/gl/shaders.ts` | the passes: G-buffer of the layers by depth, vehicles, light (sun, cast shadows, sky grade, seasons, snow), night lights, look (grade, ink); with the tunnel view on, the city faded and the tunnels over it |
| `src/tunnels.ts` | tunnel view (`v2/docs/specs/tunnel-view.md`): the tubes of `tunnels.json` as a mesh, and which vehicles are in a tunnel |
| `src/data.ts` | the release index and the tile codings (`v2/layers/common.py`) |
| `src/sun.ts` | the NOAA sun, line for line `v2/config/sun.py` (`sun.test.ts` compares them) |
| `src/sim/traffic.ts`, `src/sim/transit.ts` | v1's traffic simulation and transit, kept; changes marked `v2:` |
| `src/vehicles.ts` | layer 12: the simulation on the v2 graph, lifted to each edge's height profile |
| `src/labels.ts` | layer 15: decluttered labels and pins |
| `scripts/audit.ts` | the headless audit of layer 12 for the gate checks (a simulated day) |
| `scripts/viewer_checks.mjs`, `scripts/previews.mjs`, `scripts/shot.mjs` | headless Chromium (Playwright): the viewer's checks, the report's previews, one screenshot |
| `scripts/xray_checks.mjs`, `scripts/xray_audit.ts` | the tunnel view's checks X1-X8: its frames at every tunnel, and its vehicles over a simulated day |

## Test parameters (`src/params.ts`)

`?hour=13.5&date=2026-06-21` the clock · `?season=winter&snow` · `?off=trees,buildings,light,...` any layer off ·
`?x=&y=&z=` the view (v2 map pixels, scale) · `?v1x=&v1y=` a v1 link · `?debug=albedo|layer|shadow|depth|normal` ·
`?nosim` still vehicles · `?seed=` the traffic seed · `?noui` no panel · `?xray` the tunnel view on (also the panel's
button, or X held down); `?off=casemates` leaves the Bock casemates out of it; `?debug=xid|xdepth` its checks' frames.

## Tests

`node --experimental-strip-types --test src/*.test.ts` (no packages needed) and `npx tsc --noEmit`; both run in CI.
