# Plan: from the 1.0 showcase to the whole city

Written 7 Nov 2026. This is the single start-to-finish plan. ROADMAP.md holds the status, the open issues and
the idea list, and points here for the order of work. Update both when a phase finishes.

## Goals
1. The whole of Luxembourg City painted in the inked style, at isometricsf.com quality: sharp buildings, no seams,
   true water.
2. Time of day (live clock, golden hour, painted night without daytime shadows) and four seasons plus winter night,
   for the whole city.
3. Landmarks with history, interiors, cutaways, 3D models and photos.
4. Events: Christmas markets first, then Schueberfouer and National Day.
5. Life on the map: cars, trams, trains, water and trees that move, birds.
6. A public site on isometric.lu where every feature is switched on, one by one, once checked.

## Where we are (7 Nov 2026)
- Release 1.0 is live at https://luxembourg.amirdaraee.com: summer day only, old town painted
  (6000 × 6000 px of a 26,624 × 14,336 px map, about 10%), landmark cards, search, street names.
- Built locally but switched off publicly: time of day, seasons, Christmas, snow, traffic, transit, 3D models.
- Painter: `pipeline/gpu_train/tiles/tiler.py`, window by window with red-box infill and colour-drift correction.
  Seams and drift are its main weakness.
- RunPod balance: $4.44.

## Lessons: rules so we don't repeat mistakes
Each of these cost us a run or a day once.

**GPU pods**
- A pod script that ends with "grace period, then stop the pod" also kills any later job on that pod. Create
  `/workspace/KEEP` before starting a second job, or give each job its own pod.
- Stopping a pod wipes the container disk (`/venv`, `/hf`). Only `/workspace` survives. Every pod script must
  reinstall what it needs if it is missing.
- Every long job saves its state often, and never writes two jobs' output to the same path. The old tiler
  overwrote `live/canvas_full.png` and the full-resolution night was lost.
- Hugging Face downloads stalled on Asian data centres. Use `--country-code US` and `HF_XET_HIGH_PERFORMANCE=1`.
- Every pod has a deadline watchdog. Delete pods after use and confirm they are gone.
- Get approval with a cost figure before any paid run. Warn when the balance falls under about $3.

**Training**
- ai-toolkit scans dataset folders recursively. Keep control images outside the dataset folder, or the model
  learns to copy its input.
- Run a tiny overfit test (2 images, about 150 steps) before any full training run.

**Art**
- The base art leaves out anything that moves: no cars, trams, trains, people or birds. Water is flat, trees are
  summer, and daytime shadows are baked in.
- Feed the painter OpenStreetMap water, with parked cars removed (`make_hint.py`). Otherwise it paints fake water
  and frozen cars.
- Check the Red Bridge by eye: its deck is grey and only its sides are red.
- Christmas patches and other event patches belong to one version of the painted art. Regenerate them whenever that
  art is repainted.

**Viewer and release**
- Event patches must stay above the season layers (`setItemIndex` after layers change).
- Every new feature gets a switch in `web/src/features.ts`. Load files with `asset()`.
- GitHub Pages: 1 GB limit. Pushes with a private email are refused, so use the noreply address. If the HTTPS
  certificate stalls, remove the custom domain and set it again.
- Never print or commit keys. They live in `pipeline/.env` and `~/.runpod/config.toml`.

## Phase 0: tidy up (free, about 1 day)
1. Fix the place labels sliding while the map moves (issue I1). Move them in OpenSeadragon's `update-viewport`
   handler by writing `transform` directly, and re-render React only when the zoom level changes.
3. Cap the maximum zoom at the painted resolution (I8).
4. Confirm `http://` redirects to `https://` on the live site (I2).
5. Add a height pass to `render.py`: surface height per pixel, in centimetres across two channels, saved next to
   the existing kind and line passes. Phase 2 uses it for patch repair and Phase 6 for car hiding, tree sway and
   water.

Done when: labels stay pinned while dragging, the zoom stops at the painted detail, and the height pass exists for
the showcase.

## Phase 1: the new painter (free, on the laptop, about 2 to 3 days)
New script `pipeline/gpu_train/tiles/mdpaint.py`. It keeps the model (Qwen-Image-Edit-2511), the style LoRA, the
prompt and the inputs (render plus layout map), and changes how the windows are combined. The method comes from
Pixel Singapore (see References).

1. **One image for the whole area.** Start one noise latent the size of the area being painted. For the showcase
   that is 6000 px, or 750 × 750 latents, which is small.
2. **Windows that share every step.** At each step, cut the latent into overlapping 1024 px windows with a 768 px
   stride. Run the model on each window, conditioned on its crop of the render and layout map. Blend the
   predicted velocities with a weight that is flat in the middle and falls to zero at the edges. Take one scheduler
   step for the whole latent.
3. **Shifted grid.** On every other step, shift the window grid by 384 px, so no window edge stays in one place.
4. **Decode in overlapping pieces** and blend them in pixel space.
5. **Resume.** Save the latent, step number and settings after every step to `/workspace/md_state/<job>/`. On start,
   continue from the last saved step. This also makes cheaper interruptible GPUs usable.
6. **Patch repair and neighbours** (replaces `repaint.py`). Take a mask of known pixels. At each step, re-noise the
   known pixels to that step's noise level and hold them fixed, as RePaint does, adapted to flow matching. Leave a
   64 px free band at the boundary and feather it back at the end. Skip windows that are fully known. The same code
   paints a new block next to finished ones.
7. **Options:** `--steps` (25 now; 8 with a Lightning LoRA, tested in Phase 2), `--lora` (style or light, for the
   versions), `--max-usd` with a deadline watchdog.
8. **Laptop tests** with a stand-in model that predicts a known velocity, since the real model doesn't fit a laptop:
   - The window weights sum to 1 everywhere.
   - A flat-colour input gives a flat-colour output with no grid pattern.
   - A run killed at step 5 and resumed equals an uninterrupted run.
   - Repair mode leaves known pixels unchanged outside the free band.
9. **Pod script** `pipeline/gpu_train/md_on_pod.sh`. It reinstalls if needed, honours `KEEP`, writes to its own
   output folder, and has a watchdog.

Done when: all four laptop tests pass and the pod script passes a shell lint.

## Phase 2: showcase test (GPU, about $10 to $15, needs approval)
Settle every open painting question in one GPU session.

1. Repaint the showcase with `mdpaint.py` at 25 steps.
2. Repaint it at 8 steps with the Lightning LoRA, if one is published for Qwen-Image-Edit-2511.
3. Repaint the Place d'Armes block at a finer scale (450 or 300 render px per cell) for building quality (I4).
4. Measure seconds per window-step, peak memory and cost for each.
5. Checks: `seam_check.py`, `water_check.py`, the Red Bridge, invented trees and cars.
6. Side-by-side page in the viewer (local only), with a slider between today's art and each test.

**Decision gate (yours):** which painter, how many steps, and which scale for the city. If the new painter isn't
better, keep `tiler.py` and add only the per-step resume.

## Phase 3: get the whole city ready (mostly free, 2 to 3 days)
1. Check that renders, kind, line and height passes, and layout maps exist for the whole map. Render what is
   missing.
2. Split the city into blocks of about 6000 × 6000 px with 1024 px overlap. Order them outward from the old town:
   Gare, Bonnevoie, Kirchberg, Limpertsberg, Belair, then the edges.
3. **Sparse tiles:** a manifest lists the finished blocks. The viewer shows painted tiles where they exist and a
   marked "still being painted" render elsewhere.
4. **Cloudflare R2** for the tiles, served through `web/worker/`, built with `TILES_URL`. The whole city and its
   versions are well past GitHub Pages' 1 GB. Use versioned file names, so files can be cached for a year.
5. A cost table from the Phase 2 measurements: blocks × windows × steps × seconds × price per hour.

Done when: the block plan, the cost table and a test upload of the showcase to R2 work end to end.

## Phase 4: paint the city by day (GPU, cost from Phase 3, needs approval)
For each block:
1. Paint it with `mdpaint.py`, conditioned on the finished neighbours (repair mode).
2. Run the checks. Repair the bad patches with the same tool.
3. Build its tiles, upload them to R2 and add the block to the manifest. It is live in minutes.

Run blocks in parallel on several GPUs when the price per hour is the same. Neighbouring blocks still need to be
painted one after the other.

## Phase 5: the versions for the whole city (GPU, needs approval)
1. Night at full resolution (also fixes I3), then golden hour, winter, winter night, autumn and spring. Each uses
   the light LoRA with the same painter, from the painted day art.
2. Rebuild `build_variant_tiles.py` output per block.
3. Regenerate the Christmas markets on the new winter and winter-night art (`xmas_v2.py`, about $0.40).

## Phase 6: life on the map (free, viewer work)
Each item has its own switch. Do them in this order.
1. **Car hiding:** cars behind buildings and under trees are hidden using the height pass.
2. **Water shimmer:** a WebGL layer that moves the map's own water pixels. Use the OpenStreetMap water mask.
3. **Swaying trees:** split the tree canopy into crowns from the height pass, then sway them with gusts.
4. **Better traffic:** cars follow each other realistically and stop at traffic lights. Lanes come from the
   painted roads, and cars drive on the right.
5. **Trams and trains** across the whole city. Refresh the timetable on a schedule, for example a monthly GitHub
   Action that rebuilds `transit.json` from the latest GTFS (I7).
6. **Birds** over the Pétrusse and Alzette valleys, and an optional tilt-shift blur.

## Phase 7: switch on publicly, one at a time
Turn each feature on by removing it from `web/.env.production`, deploying, and checking the site on desktop and
phone.
1. Time of day.
2. Seasons and snow.
3. Christmas, before Winterlights opens in late November.
4. Trams and trains.
5. Traffic.
6. 3D models.

## Phase 8: the domain
1. Buy isometric.lu (EuroDNS, Gandi, OVH or Netim).
2. Point DNS at GitHub Pages (or the R2 worker), deploy with `CNAME=isometric.lu`, and enforce HTTPS.
3. Redirect luxembourg.amirdaraee.com to it.

## Phase 9: more
Schueberfouer (late August to mid September) and National Day (23 June) as event versions, weather, clouds at the
map's edges, easter eggs, showing height above sea level, and a historic mode from `research/`.

## GPU provider
Both RunPod and Modal are used (decided 7 Nov 2026). The painter is the same Python code on both. Only the launcher
differs:
- **Modal** (`pipeline/gpu_train/modal_paint.py`): serverless, billed per second, with about $30 of free compute
  each month. Model weights and painter state live on a Modal Volume, so a stopped job resumes. Good for tests and
  for blocks that fit in one function run.
- **RunPod** (`md_on_pod.sh`): long jobs on a pod with a watchdog. Good for big batches.
Other providers worth checking later:
- **Vast.ai and Novita:** lower listed H100 and H200 prices, often interruptible. They become a safe choice once
  the painter resumes after every step.
Prices move often. Check the providers' own pricing pages on the day.

## References
- Pixel Singapore, how it was made: https://www.yadongxie.com/blog/how-pixel-singapore-was-made (whole-canvas
  painting with shifted windows, RePaint-style blocks, sparse tiles, height pass, traffic, water and tree effects).
- isometric-nyc: https://github.com/cannoneyed/isometric-nyc (the viewer this project started from).
- isometricsf.com: the quality target.
