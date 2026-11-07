# Plan for the next round (written 7 Nov 2026)

This plan covers the owner's 13 requests after the whole city was painted by day. It sits next to PLAN.md (the
start-to-finish plan) and ROADMAP.md (status and open issues). When an item here is finished, update both of them.

Map positions below are in map pixels (0.25 m each). A view on the site is `#x,y,z` in the address (see
`readHash` in `web/src/App.tsx`). For example, `#7615,5801,1.2` is Place d'Armes at close zoom (the zoom stops at
1.25, `maxZoomPixelRatio` in `IsometricMap.tsx`).

## Contents
1. Ground rules for this round
2. Shared set-up first (step M0)
3. The 13 items, one by one
4. Three work streams: who owns which files, the order of work, dependencies and merging
5. Spending
6. Calendar

---

## 1. Ground rules for this round

These come from PLAN.md "Lessons" and CONTRIBUTING.md, and they apply to every item:

- **Approval before spending.** Before any paid run, give the owner the cost figure and the cap and wait for a yes.
  GPU work runs on Modal (H200 at about $4.54/h). `paint_city.py` and `modal_paint.py --max-hours` enforce caps
  through the function timeout. OpenAI image calls go through the `pipeline/events` / `pipeline/style` helpers.
  They log every call to `data/work/style/openai_spend.json` and take a cap as an argument. Keep both habits.
- **The base art leaves out anything that moves.** No cars, buses, trams, trains, people, birds, aircraft or
  lift cabins. Water is flat. Anything that moves is a live layer in the viewer.
- **Every new feature gets a switch** in `web/src/features.ts`, and every new switch is listed in
  `VITE_FEATURES_OFF` in `web/.env.production` until the owner has checked it on the live site (PLAN.md Phase 7).
  Bug fixes inside features that are already switched off (traffic, transit, christmas) don't need a new switch.
- **Load public files through `asset()`.** Convert positions through `map.current.toScreen()` or the
  `z, ox, oy` view that Overlay uses, never through the OpenSeadragon viewport.
- **Event patches belong to one version of the painted art** (issue I11). Whenever winter or winter night is
  repainted, the Christmas patches must be composited again.
- **Git:** no commits, pushes or merges unless the owner asks. Each stream works on its own branch in its own
  worktree, and the owner says when to merge.
- **Check before merging:** `npx tsc --noEmit`, `npm run build`, `node src/sim/traffic.test.ts`, and the
  screenshot set (M0.3) compared with the last run.

---

## 2. Shared set-up first (step M0, about half a day, done once before the streams start)

The three streams share a few files: `web/src/App.tsx`, `web/src/features.ts`, `web/.env.production`, and a little
of `web/src/components/sprites.ts` and `SceneControl.tsx`. To keep merge conflicts out of these, one small
set-up change goes in first. After that, each stream touches a shared file only in the lines this plan gives it.

### M0.1 Feature switches (all new, all off in `web/.env.production`)
Add these keys to `DEFAULTS` in `features.ts`, each `true` with a one-line comment, in three blocks headed
`// Vehicles and rail`, `// Art and events` and `// Performance, weather and sky`. Append all of them to
`VITE_FEATURES_OFF` in `web/.env.production` in the same change:

| Switch | Item | What it turns on |
|---|---|---|
| `liftCabin` | 6 | The moving cabin of the Pfaffenthal Panoramic Lift |
| `eventRides` | 7 | Moving rides and twinkling lights in event patches (Christmas first) |
| `events` | 13 | The event calendar and picker for events other than Christmas (master switch) |
| `newYear`, `nationalDay`, `schueberfouer`, `octave`, `emaischen`, `marathon`, `halloween`, `buergbrennen`, `musicStages` | 13 | One switch per event, so each one can be switched on publicly on its own |
| `fireworks` | 13 | Firework displays (National Day, Schueberfouer closing night, New Year's Eve) |
| `weather` | 5 | Rain, storm, wind and snow from the live weather or the picker |
| `fog` | 5 | Valley fog and haze (needs `weather`) |
| `planes` | 11 | Cargolux and Luxair aircraft over the city |
| `adaptiveQuality` | 3 | Automatically lowers the effect quality on slow devices |
| `perfHud` | 3 | Frame-time readout for testing. Its default is `false` everywhere, but list it anyway |

The fixes in items 1, 2, 8, 9 and 10 sit inside `traffic`, `transit` and `emergency`, which are already off
publicly, so they need no new switch.

### M0.2 Test parameters in the address (in `App.tsx`; development and headless tests only)
- `?hour=21.5` fixes the clock (sets `live` to false), `?season=winter`, and `?date=2026-08-25` (sets "today"
  for `christmasOn`, `seasonOf`, `luxDayMask` and the event calendar).
- `?weather=rain:0.8,wind:12@250` (read by stream C), `?event=schueberfouer` (read by stream B), `?seed=42`
  (traffic seed, read by stream A through `TrafficOptions.seed`).
- These parameters change nothing unless they are present. They are what makes every screenshot below
  repeatable.

### M0.3 Screenshot and timing harness
- `web/scripts/shots.mjs` (Playwright, as a new dev dependency). It reads `web/scripts/shots.json`, a list of
  `{name, hash, query, waitMs, size}`, loads each against `vite preview` of a build, and saves PNGs to
  `data/work/shots/<date>-<label>/`. With `--compare <older label>` it writes a side-by-side and a pixel-difference
  page.
- It starts with the views named in this plan (section 3), so every stream checks the same places.
- Stream C extends the same script with timing (item 3).

### M0.4 Stubs and small API changes
- `App.tsx` mounts empty components, so later streams need not edit App: `<EventLayer>` (stream B, file
  `web/src/components/EventLayer.tsx`), `<Sky>` (stream C, `web/src/components/Sky.tsx`: weather, fog and planes),
  and `<WeatherControl>` (stream C), passed to SceneControl as a new optional `extra` prop. Each gets
  `map`, `night`, `hour`, `season` and `date` as props.
- `sprites.ts`: `loadSprites(file = "/sprites/sprites.json")` takes an optional file. Stream C loads
  `/sprites/planes.json`, and stream B loads `/events/sprites.json`, with the same code.
- A frame-clock module `web/src/frame.ts` that exports `subscribe(fn, {fps?})`, which is just
  `requestAnimationFrame` for now. Stream C replaces its insides in item 3. Others only call `subscribe`.

---

## 3. The 13 items

Estimates: **S** is up to a day, **M** is 2 to 4 days, and **L** is 1 to 2 weeks of focused work (GPU waiting
time not counted).

### Item 1. "Cars' backlights are visible through the car itself"

**Root cause.** In `Overlay.tsx`, every car is drawn as its sprite (`drawVehicle`), and then `drawCarLights` draws
flat rectangles in the car's own rotated frame on top of it. The tail lights are `fillRect(-L/2 - 1, ...)` at the
rear ground edge, and the headlight beam is a gradient wedge ahead of the car. These are drawn after the sprite, at
ground level, with no depth. The sprite's body rises up the screen from its ground footprint (about 1.5 m, or 5
map px). So when the rear of the car faces away from the camera, the tail rectangles land inside the body's
silhouette and show through the roof and glass. When a car heads up the screen, the start of the beam lies over
the bonnet. The rectangles also ignore the lamp height (0.74 m in `build_sprites.py`, `TAIL`, part 902). Their
width (`Wd = width * z * 0.7`) isn't foreshortened, and brake lights show by day at any zoom over 6 px car length.

`build_sprites.py` already models the lamps (parts 901 head, 902 tail) and depth-tests them, so it knows exactly
which lamp pixels are visible in each of the 32 headings (`frame_image`, the `part` buffer).

**Approach.** Bake a lamp atlas next to each vehicle atlas, and light only the lamp pixels the camera can see.
Draw the headlight beam under the sprite, not over it.

**Steps.**
1. `build_sprites.py`: in `frame_image`, after the depth test, write a second RGBA frame for each heading. R is
   the visible tail-lamp pixels (part 902), G the visible headlamp pixels (901), and B a soft halo: R or G
   blurred by about 1.5 sprite px. Lay these out exactly like the colour atlas in `<type>_lamps.png`, and add
   `"lamps": "<type>_lamps.png"` to `sprites.json`. Do the same for the tram and train sections (their
   headlights and tail lights become parts 901/902 too).
2. Add a build check: for every type and heading, no lamp pixel may lie where the body is nearer the camera
   (depth). Also list the headings where the tail lamps are fully hidden, which must be the "rear faces away"
   half. The build fails if either check fails.
3. `sprites.ts`: load the lamp atlas when it is listed. Add `drawLamps(g, s, type, x, y, heading, zoom,
   {tail, brake, head})`, which draws the lamp frame with `globalCompositeOperation = "lighter"`. Tint it through
   a small cached canvas per type and colour (red for tail, brighter red for brake, warm white for head), with
   the halo channel at low alpha.
4. `Overlay.tsx`: remove the tail rectangles from `drawCarLights`. The beam becomes a ground pass drawn into
   the vehicle layer before the sprites of the same pass, so the body covers it and the occlusion cut trims it.
   Then sprites go on, then `drawLamps`. Brake lights by day only from z ≥ 0.6 and at 60% strength. At night,
   tail lights are always on and brake lights brighter.
5. `drawCarRect` (the fallback when sprites fail) keeps its rectangles. It is flat, so they are right there.
6. Trains and trams in `Transit.ts` use `drawLamps` too, replacing the warm ellipse "lit windows" with lit
   window pixels: add a third lamp class, part 903, for the glass bands of the tram and train models.

**Switch.** None (inside `traffic`/`transit`).
**Data.** Regenerated `web/public/sprites/*.png` plus `*_lamps.png` (about +30% size; keep under 1.5 MB total).
**Cost.** Free.
**Verify.**
- The build check in step 2.
- A dev view `?spritelab` (a component under `web/src/dev/`, mounted by M0) draws every type × 32 headings,
  night and braking, on a grey ground. Take a screenshot of it, and check that no red appears on roofs or glass
  in the frames heading down the screen (headings about π/4 to 3π/4).
- Shots at night: `#7025,5515,1.2?hour=22&on=traffic` (Hamilius and Boulevard Royal) and
  `#19074,6176,1.0?hour=22&on=traffic` (Kirchberg). Look at cars driving down the screen and away from the camera.
**Risks.** Lamps are one or two sprite pixels, and they can vanish below z of about 0.3. Below that, fall back to
a single soft dot per lamp at the right height.
**Estimate.** S.

### Item 2. "Cars go inside trees, the river and other objects; it needs refining"

**Root causes** (several, all in the files read):
1. **Tree canopy is detected poorly.** `build_occlusion.py::canopy_mask` finds crowns by colour (hue 30 to 95,
   saturation ≥ 60, value ≤ 150) in `data/work/city/art_half.png`, a half-resolution city image (commit e871587).
   Its grid is 1 occluder px = 4 map px = 1 m (`occluders.json` scale 4). Light, yellow-green, autumn and
   back-lit crowns are missed. A crown counts only where it reaches the road polyline buffer
   (`hit = canopy & road`, then grown upwards). A car on a lane offset 1.6 to 4.8 m from the centreline can sit
   under a crown that never touches the centreline buffer. A crown also hides a car fully or not at all (one
   8 m height, a hard 1 m edge), so cars appear half inside a tree.
2. **Water never hides a car.** `Overlay.tsx::seen()` tests `visibility.png` (1 px = 8 map px = 2 m). Its value
   255 means "ground visible", and water counts as visible ground. Lanes are offset from the OSM centreline by
   `(idx + 0.5) * LANE_W` (3.2 m) on two-way streets (`traffic.ts`, step 4 "Lanes") whatever the real width. On
   the quays of the Grund, Clausen and Pfaffenthal, and on narrow streets, the outer lane lands on the river or
   in a facade. Bridge ways with no deck profile in `road_heights.json` are drawn at the straight interpolated
   height from `project_lines.py`, which can put them over the valley floor or the river.
3. **Buildings.** The visibility mask is 2 m and binary, and the cut uses one threshold per pass (1.6 m, 3.2 m
   and 4.5 m in `Overlay.tsx`). So edges are ragged, and a lane offset into a building footprint shows the car
   on the facade.
4. **Draw order.** The vehicles in each pass aren't sorted by screen y, so a car behind can be drawn over one in
   front.
5. **Art drift.** The painter didn't always put the road exactly on the OSM line, so a correctly offset lane can
   still be on the pavement.

**Approach.** Make one offline "drivable surface" map from the real data and the painted art. Size each street's
lanes to its real width. Rebuild the canopy at full resolution with soft edges. Add a runtime guard that fades out
any car whose drawn position isn't drivable. And measure all of this with a headless audit before and after.

**Steps.**
1. **Audit first** (to measure the problem). Write `web/src/sim/audit.ts`, a Node script like
   `traffic.test.ts`. It runs `Traffic` over the whole painted city for 10 simulated minutes and samples every
   car's drawn position once a second. It classifies each sample against a raw mask (step 2), counting how many
   are on water, inside a building, under a crown or off the road. It prints the share of car-seconds in each
   class and the 30 worst places as `#x,y,1.0` links, which go into `shots.json`.
2. **Drivable map**: a new `pipeline/build_drivable.py`. At 2 map px (0.5 m) per cell, near roads only, it uses:
   - the OSM road buffer at its estimated width: the `width` tag, else `lanes × 3.2 m`, else a default by kind;
   - ground visible (from `frames_kind`), excluding water (the painted water atlas from `build_water_mask.py`
     plus OSM water) and building footprints;
   - "road-coloured" pixels in the painted art (asphalt greys within the buffer), to follow the painter's drift.
   Output: `web/public/data/drivable/` tiles (PNG, values 0 none, 1 road, 2 bridge deck, 3 water, 4 building),
   plus a raw `.bin` for the Node audit.
3. **Road widths into lines.json**: `project_lines.py` gets a `w` field per road (metres). It is measured from
   the drivable map by sampling across the road every 10 m and taking the median, clamped to the tag value.
4. **Lane offsets** (`traffic.ts`, step 4): a two-way street with one lane each way puts each lane centre at
   `w/4`, not 1.6 m. With more lanes, they are spread across `w/2` per side. One-way streets are centred, as now.
   No lane centre may come within 1.1 m of the edge. Narrow two-way streets (`w` under 5 m) get one shared lane
   offset of 0.4 m, which is what drivers do.
5. **Canopy, again** (`build_occlusion.py`). Build `canopy_mask` from the 15 full block canvases
   (`data/work/city/b*/canvas_day_s8.png` through `painted.json`), not `art_half.png`. Use a 2 map px grid, with
   a classifier that adds local texture (crowns are busy, lawns smooth), the height pass ("not building, not
   road surface") and the layout map's green classes. Drop the "must touch the centreline" rule. Instead, a
   crown counts where it overlaps the lane band, meaning the drivable cells. Write a soft coverage value
   (feathered over about 0.75 m) into the unused **B channel** of `occluders.png`.
6. **Soft cut** (`occlusion.ts`): `cut()` also erases by the B channel as alpha, so cars fade into crowns rather
   than being chopped. Winter and winter night use B × 0.4, since the crowns are bare (pass the season in).
7. **Runtime guard** (`Overlay.tsx`): look up the drivable tile at each car's drawn position (with its sideways
   pull). If it is water or building, and the car is not on a deck from `deckAt`, fade the car out over 0.3 s
   and count it in `sim.stats`. In the dev HUD, the count should stay near zero.
8. **Bridges**: every bridge way that carries traffic gets a deck profile. Extend `deck_profiles` so it never
   skips a carrying bridge way, and fall back to the terrain at both ends with the deck straight between them.
   Then `deckLift` always lifts.
9. **Sort** each pass by screen y before drawing.
10. Run the audit again, compare, and repeat steps 4 to 7 until it passes the targets.

**Switch.** None (inside `traffic`).
**Data.** New `web/public/data/drivable/*` (target under 2 MB in total, loaded per tile near the view), and
`occluders.png` rebuilt with a B channel. Rebuild both after stream B's car repairs (item 4).
**Cost.** Free.
**Verify.**
- Audit targets: water 0.0% of car-seconds, buildings under 0.3%, cars visible over a crown 0 at the listed
  spots.
- Shots at `?hour=13&on=traffic&seed=42`:
  - quays: `#8694,6852,1.0` (Grund), `#11066,7033,1.0` (Clausen), `#9773,5948,1.0` (Pfaffenthal);
  - trees: `#7025,5515,1.0` (Boulevard Royal and Hamilius), `#19074,6176,0.8` (Kirchberg boulevard);
  - decks: `#6274,6194,1.0` (Pont Adolphe), `#10209,5252,1.0` (Red Bridge).
  Compare before and after side by side.
- `node src/sim/traffic.test.ts` still passes (no new overlaps or deadlocks).
**Risks.** The width estimate from the art can be fooled by grey roofs. Clamp it to the OSM tag and the kind
default (±50%). Fading many cars may thin traffic on narrow streets. If so, accept fewer cars there.
**Estimate.** L.

### Item 3. "We need a big task for performance"

**What costs time today** (from the code; to be confirmed by measurement):
- **Overlay draws twice per frame while the map moves.** `Overlay.tsx` draws in its own `requestAnimationFrame`
  loop and again in `map.onFrame` (`update-viewport`), which fires on every animated frame. The second call gets
  `dt ≈ 0`, but it still clears and redraws everything: streets, birds, snow, transit, every car, three cuts and
  the full-screen copy.
- The **vehicle layer** is a second full-screen canvas at device pixel ratio. It is cleared, cut three times
  (`occ.cut` with `destination-out` tile masks) and copied over the overlay every frame, even with only a few
  cars.
- The **occlusion mask** (`occlusion.ts::load`) decodes a 6656 × 3584 image and calls `getImageData`, about 95 MB
  at once, on start (issue I13). Its tile cache (`tiles` Map) grows without limit as you pan: one canvas per
  tile and threshold.
- **Three WebGL canvases and two 2D canvases** each run their own loop: Water (30 fps), Clouds (every frame
  while clouds are on screen), Overlay (60), plus Model3D when open. All are at full device pixel ratio.
- **CSS:** `.graded` puts a `filter` on the whole map when a grade is set (morning, blue hour). Tilt-shift is two
  `backdrop-filter: blur` bands over 44% of the screen. Every pin label has its own `backdrop-filter`. All of these
  are expensive on phones and in Safari.
- **OpenSeadragon** (5.0.1) keeps every map version it has added (up to 7 layers plus patches). Faded-out
  versions still hold tiles in memory and may still be drawn or updated.
- **Start-up:** `lines.json` (2 MB) is parsed and the whole-city traffic graph is built on the main thread,
  even when traffic is off. `visibility.png` and `occluders.png` are decoded on start.

**Approach.** Measure first, with a repeatable harness and a budget. Then fix the biggest costs, with one frame
clock for every layer, and an adaptive quality tier for slow devices.

**Steps.**
1. **HUD** (`?perfHud`, from `web/src/perf.ts`): fps, frame time p50/p95, and milliseconds per layer through
   `performance.mark/measure` around each layer's draw (overlay simulation, streets, transit, vehicles, cut,
   water, clouds, sky). Also cars alive, canvases, OSD items and tiles cached.
2. **Harness** (`web/scripts/perf.mjs`, built on the M0 shots script). Production build with `?on=` for every
   feature, at `#7615,5801,0.55?hour=21`. It idles for 10 s, runs a scripted pan from the old town to Kirchberg,
   zooms in and out, and does the same at noon. It records frame intervals, long tasks over 50 ms, JS heap,
   bytes and tiles loaded, and the HUD measures. It runs two profiles: desktop, and "mid phone" (390 × 844, DPR
   3, CPU slowed 4×). Output goes to `data/work/perf/<date>-<label>.json`, and `--compare` prints the
   differences. Headless Chrome draws WebGL in software, so GPU numbers come from a headed Chrome run on the
   Mac. The owner also checks a real phone by hand.
3. **Baseline**, before any fix, with numbers written into this file.
4. **Budgets:** desktop 60 fps (p95 frame under 20 ms) with every feature on. Mid phone 30 fps (p95 under
   40 ms). Main-thread work per frame under 6 ms desktop and 12 ms phone. First painted map under 2.5 s on a
   fast 4G profile. No long task over 200 ms after the first paint.
5. **Frame clock** (`web/src/frame.ts`, stream C): one `requestAnimationFrame` for everyone. Subscribers say
   their target fps, and the clock calls them at most once per frame. It merges the map's `update-viewport` into
   that frame (a "moved" flag, not a second call). It stops calling still layers when nothing moves, and stops
   everything when the tab is hidden.
6. **Stream A's part** (in `Overlay.tsx`, `occlusion.ts` and `traffic.ts`):
   - draw once per frame through the frame clock, with the simulation step on the clock tick only;
   - clear and copy only the vehicles' bounding box, and skip the cut and copy when no vehicle is on screen;
   - an LRU for occlusion tiles (about 150 canvases);
   - **I13**: split `occluders.png` into 512 px tiles at build time and load only those near the view (removes
     the 95 MB decode);
   - `cars()` fills a reused array instead of a generator of new objects;
   - streets as cached `Path2D` per road;
   - `lines.json` loaded only when streets or traffic are on;
   - the traffic graph built in idle time (`requestIdleCallback`, in slices), or once offline into a compact
     binary if the measurement shows it is slow.
7. **Stream C's part** (`IsometricMap.tsx`, `Water.tsx`, `Clouds.tsx`, `Pins.tsx`, `global.css`):
   - Clouds drawn at half resolution and scaled up, since the cloud is soft anyway;
   - Water at most DPR 1.5;
   - every canvas capped at DPR 2;
   - remove an OpenSeadragon version layer once its opacity has been 0 for 30 s (`world.removeItem`, added back
     lazily as now), and limit cross-fades to two versions at once;
   - try `drawer: "webgl"` in OpenSeadragon 5 and keep it only if opacity, patches and `setItemIndex` behave the
     same;
   - tune `imageLoaderLimit` and `maxImageCacheCount`;
   - pin labels with a solid background instead of `backdrop-filter` when more than about 20 show;
   - tilt-shift replaced by a cheaper mask (one gradient band, smaller blur), or off on the low tier;
   - if the harness shows the `.graded` filter is costly, make the grade a wash `div` with `mix-blend-mode`.
8. **Adaptive quality** (`adaptiveQuality`): after 3 s of frames, if p90 is over 22 ms, step down one tier at a
   time. Tier 1: tilt-shift off, clouds static, water 15 fps. Tier 2: DPR 1, half the cars (`maxCars`), birds
   off. Remember the tier for the session. `prefers-reduced-motion` keeps its present meaning.
9. **Weight:** run Lighthouse on the production build, check the bundle (three.js stays lazy), and check that
   tile WebP sizes aren't larger than needed.
10. Repeat the harness after each fix and keep a table of before and after in this file.

**Switch.** `adaptiveQuality` and `perfHud` (new). The rest are plain improvements.
**Data.** Tiled occluders (stream A).
**Cost.** Free.
**Verify.** The harness numbers against the budgets, and `shots.mjs --compare` showing no visual change (beyond
the expected small softening of the clouds).
**Risks.** The OpenSeadragon WebGL drawer is newer and may break patch layering. Keep the canvas drawer as the
default if in doubt. Half-resolution clouds may show steps at the map edge, so test at `#26000,7000,0.2`.
**Estimate.** L (harness M, fixes L, split between streams A and C).

**Measurements** (`web/scripts/perf.mjs`; each run's full numbers are in `data/work/perf/<date>-<label>.json` and
`.md`). How to measure a change: `cd web && node scripts/perf.mjs --build --label <name> --compare baseline --port <yours>`.
The readout is `?on=perfHud` (`web/src/perf.ts`); `?perftest` collects the same numbers without showing it.
Layers time themselves with `span("name")` or `time("name", fn)` from `perf.ts`, and add numbers to the readout
with `gauge("name", fn)`. Stream A: please wrap the overlay's parts (simulation, streets, transit, vehicles, cut)
in spans, so they show next to `map`, `water`, `clouds` and `pins`. `raf` is every animation-frame callback
together (the overlay's loop, the water and the clouds), and `mapFrame` is the work done inside the map's own
redraw (everything that redraws with `map.onFrame`).

Headless Chrome on the M2 Pro draws WebGL on the GPU here (ANGLE Metal), so these numbers include the GPU. Its
animation frames come at 120 Hz, so an idle page shows about 120 fps. The "mid phone" is the same machine with the
CPU slowed four times, so it shows main-thread costs, not a phone's GPU.

*Baseline, 7 Nov 2026 (commit 2f72685 plus the harness), every feature on, 21:00 then noon, autumn:*

| Profile | Phase | fps | p50 ms | p95 ms | max ms | main thread ms/frame | long tasks | JS heap MB | KB loaded | tiles |
|---|---|---|---|---|---|---|---|---|---|---|
| desktop | start-up: FCP 352 ms, first tile 638 ms, **first view 14.5 s** | | | | | | 39 (max 100 ms) | | 15330 | 126 |
| desktop | night idle | 118 | 8.3 | 9.2 | 17.5 | 1.0 | 0 | 28 | 0 | 0 |
| desktop | night pan | **35** | 25 | **57.8** | 91.6 | **22.5** | 5 | 36 | 30420 | 384 |
| desktop | night zoom | 58 | 16 | 42.4 | 67.4 | 10.3 | 1 | 48 | 8767 | 225 |
| desktop | noon idle | 120 | 8.3 | 9.0 | 9.4 | 0.8 | 0 | 43 | 0 | 0 |
| desktop | noon pan | 60 | 15.8 | 33.5 | 150 | 11.7 | 6 | 33 | 3424 | 276 |
| desktop | noon zoom | 84 | 8.4 | 25.7 | 58.9 | 6.3 | 0 | 33 | 3658 | 184 |
| phone | start-up: FCP 384 ms, first tile 1.1 s, **first view 8.0 s** | | | | | | 3 (max 487 ms) | | 6309 | 45 |
| phone | night idle | 120 | 8.3 | 9.2 | 24.2 | 1.6 | 0 | 29 | 0 | 0 |
| phone | night pan | **28** | 8.8 | **108** | 159 | **34.0** | 1 | 33 | 19754 | 222 |
| phone | night zoom | 74 | 8.4 | 58.5 | 366 | 10.2 | 1 | 32 | 5757 | 87 |
| phone | noon idle | 120 | 8.3 | 9.2 | 25.3 | 1.5 | 0 | 29 | 0 | 0 |
| phone | noon pan | 39 | 8.7 | 75.5 | 108 | 24.3 | 0 | 26 | 3638 | 190 |
| phone | noon zoom | 78 | 8.4 | 59.0 | 125 | 9.6 | 0 | 38 | 627 | 66 |

Every moving phase is over budget; idle is well inside it. What the baseline shows:
- **Panning is the problem, not drawing.** The layers' own draw times are small (desktop pan: map 0.4, mapFrame
  0.9, all animation-frame callbacks 0.5 ms a frame), yet the main thread spends 22 ms a frame. A CPU profile of
  the night pan puts **two thirds of all main-thread time in one call**: OpenSeadragon's WebGL drawer tests every
  new tile for cross-origin taint with `getImageData` on a 2D canvas, which stalls for a GPU read-back each time.
- **Every map version under a full-opacity one is still loaded and drawn.** At 21:00 in autumn the base day map,
  the autumn version and the night version are all at full opacity: three sets of tiles (30 MB in an 8 s pan).
- **Map versions are stacked in the order they were first needed**, not in their meaning: at 21:00 in autumn the
  autumn day version is added after the night one and covers it, so the evening shows the day art (shot
  `c-perf-old-town-evening`).
- **Start-up:** 15 MB before the first view is complete on desktop (11.4 MB of tiles at device pixel ratio 2, then
  `occluders.png` 1.5 MB, the cloud texture 0.65 MB, `lines.json` 0.5 MB, the water mask 0.4 MB). The map's
  first view takes 14.5 s on fast 4G, against a budget of 2.5 s.

*Stream C's fixes (C2), measured step by step:*
1. `c2-osd`: OpenSeadragon's taint test skipped (every image is loaded with `crossOrigin="anonymous"`, so none can
   be tainted), and the map canvas capped at device pixel ratio 2.
2. `c2-fixes`: map versions stacked by meaning (base, season, golden hour, night, event patches) and a version
   under a fully opaque, loaded one hidden, so its tiles are neither fetched nor drawn (at start-up, before
   anything is on screen, it is never fetched at all); versions at 0 for 30 s removed from the map; at most 100
   cached tiles on touch screens; water at most 1.5 device pixels per CSS pixel; clouds at half the CSS
   resolution, with their 650 KB texture fetched only when a cloud can show; pin labels without `backdrop-filter`
   when more than 20 show; water and clouds on the one frame clock (`src/frame.ts`), called in the map's own frame
   when it moves, so they are drawn once per frame.
3. `c2-adaptive`: the same with adaptive quality on (the others were measured with `--off adaptiveQuality`).

| Profile | Phase | Baseline p95 / main ms | After (`c2-fixes`) p95 / main ms | Budget p95 / main |
|---|---|---|---|---|
| desktop | night pan | 57.8 / 22.5 (35 fps) | **16.7 / 2.7** (110 fps) | 20 / 6 |
| desktop | night zoom | 42.4 / 10.3 | **16.7 / 2.8** | 20 / 6 |
| desktop | noon pan | 33.5 / 11.7 | **16.6 / 3.1** | 20 / 6 |
| desktop | noon zoom | 25.7 / 6.3 | **16.7 / 3.3** | 20 / 6 |
| phone | night pan | 108 / 34.0 (28 fps) | **24.2 / 7.2** (97 fps) | 40 / 12 |
| phone | night zoom | 58.5 / 10.2 | **16.1 / 4.9** | 40 / 12 |
| phone | noon pan | 75.5 / 24.3 | **34.0 / 10.8** | 40 / 12 |
| phone | noon zoom | 59.0 / 9.6 | **16.8 / 5.8** | 40 / 12 |

| Start-up (fast 4G, cache off) | Baseline | After | Budget |
|---|---|---|---|
| desktop: first view complete | 14.5 s, 15.3 MB, 126 tiles, 39 long tasks | **6.4 s, 5.3 MB, 44 tiles, 1 long task** | 2.5 s |
| phone: first view complete | 8.0 s, 6.3 MB, 45 tiles | **3.7 s, 2.8 MB, 17 tiles** | 2.5 s |
| night pan, bytes loaded | 30.4 MB, 384 tiles | **7.1 MB, 140 tiles** | |

Every moving phase is now inside its budget on both profiles. Start-up is still over: what is left is mostly the
tiles themselves (3 MB on desktop) and data loaded on start for the vehicle layer (`lines.json`, `transit.json`,
`visibility.png`, the sprites), which is stream A's part (I13, lazy `lines.json`). The phone profile slows only the
CPU, so the GPU savings of the lower quality tiers do not show in it; with adaptive quality on, the phone profile
steps down to tier 2 during the pans (tile decoding is the main-thread work left), and desktop stays at tier 0.
Left for stream A, from a CPU profile of the pan: `luxDayMask` in `Transit.ts` is called every frame (about 2% of
the main thread in development), and the overlay's draw has no spans yet.
Not done yet: Lighthouse, and a cheaper tilt-shift (it is only switched off on the lower tiers); the `.graded`
filter is only set for the morning grade, so it was not measured.

*The rest of item 3 (C4a, stream C, after streams A and B merged):* the overlay is drawn by the frame clock alone
(`subscribe(draw, {name: "overlay"})`; the map's `onFrame` call and the 40 ms guard are gone), at most 2 device pixels
per CSS pixel (1 on tier 2), with spans `sim`, `streets`, `birds`, `transit`, `vehicles` and `cut`; tier 2 halves the
cars and hides the birds; `luxDayMask` is worked out once a minute instead of every frame. The occlusion cut draws
only the mask tiles under each pass's vehicles (`occ.cut` takes a list of rectangles, each tile once), instead of
every tile in the box round all of them. The snow block left the overlay: `Sky.tsx` draws snow (weather snow, or
winter with `snow` when the weather is off). Birds turn into the wind, drift back with it, and thin out from 6 m/s to
3 flocks above 10 m/s; with reduced motion they are not drawn.
Whole app, every feature on, `c5-before` (main after the stream A and B merges) against `c5-cut` (these changes):

| Profile | Phase | Before p95 / main ms (fps) | After p95 / main ms (fps) | Budget p95 / main |
|---|---|---|---|---|
| desktop | night pan | 16.8 / 3.15 (105) | 16.7 / 3.02 (108) | 20 / 6 |
| desktop | night zoom | 16.9 / 5.12 (88) | 17.0 / **3.42** (104) | 20 / 6 |
| desktop | noon pan | 16.7 / 3.39 (108) | 16.7 / 3.39 (109) | 20 / 6 |
| desktop | noon zoom | 18.0 / 5.05 (94) | 16.6 / **3.36** (109) | 20 / 6 |
| phone | night pan | 26.8 / 8.92 (86) | 25.4 / 8.22 (91) | 40 / 12 |
| phone | night zoom | 18.3 / 5.39 | 17.8 / 5.54 | 40 / 12 |
| phone | noon pan | 41.8 / 12.63 (66) | 42.1 / 13.57 (65) | 40 / 12 |
| phone | noon zoom | 25.1 / 6.42 | 24.7 / 6.57 | 40 / 12 |
| both | idle, main ms | 0.91 to 1.58 | 0.71 to 1.30 | |

Start-up: desktop first view 5.9 s (5.9 MB, 44 tiles), phone 3.5 s (3.3 MB, 17 tiles), unchanged within noise; JS
heap 24 to 75 MB across phases (it varies with the collector more than with these changes). The cut fell from 1.7 to
0.1 ms a frame while zooming on desktop. The phone's noon pan stays at the edge of its budget, before and after (it
was 34 to 42 ms in earlier runs too): the overlay is 1.4 ms of its 13 ms, and the rest is the map decoding and drawing
the larger noon tiles, which the CPU-slowed profile magnifies. Runs: `data/work/perf/2026-11-07-c5-*`; shots
`data/work/shots/2026-11-07-c5-a` and `-c5-a-vehicles` (vehicles unchanged against `a6-after`).

### Item 4. "I can see cars painted in the art"

**Root cause.** Two sources:
1. **Cars left in the painter's input.** `make_hint.py` empties roads only inside an OSM buffer
   (`LANES_M` by kind) and parking polygons from `lines.json`, and only where the ground is visible and not
   green. It replaces only compact blobs that differ from a 31 px median by more than 60. So it misses dark and
   grey cars close to the asphalt tone, cars on driveways, in courtyards and on car parks missing from OSM, cars
   near or under trees, and long rows outside OSM parking.
2. **The painter invents cars** on station roads and car parks (issue I6), even from a clean input.

All six versions (night, golden, winter, winter night, autumn, spring) are made from the day art with the light
model (`paint_city.py --version`), so they copy every painted car.

**Approach.** Find painted vehicles in the finished day art. Have them reviewed. Remove them with the painter's own
patch repair, in a pilot first. Then carry the fix into the six versions without a GPU, by local colour transfer.

**Steps.**
1. **Find** (laptop, free): `pipeline/repair/find_vehicles.py`.
   - (a) The `make_hint.py` blob rules, run on the painted art instead of the render, inside a wider mask:
     roads, parking, service ways, plus any visible ground within 15 m of a road.
   - (b) An open-vocabulary detector (OWLv2 through `transformers`, on the Mac's GPU) on 1024 px crops, with the
     queries "car", "van", "bus", "truck", "train", "person". Keep boxes of 3 to 14 m.
   - Join (a) and (b). Write `data/work/repair/vehicles_<block>.json` (boxes in map px, score, source) and
     contact sheets.
2. **Review**: a local page, `web/public/live/review.html` (local only, never published), shows each candidate's
   crop with keep and reject buttons, and saves the decisions to `data/work/repair/decisions.json`. The owner (or
   a quick pass by the stream) clears the false alarms, such as kiosks, skylights and bus shelters.
3. **Masks**: one mask per block. Each accepted box is grown by 1.5 m, with lane markings kept out of the mask
   where the line pass shows them.
4. **Pilot (needs approval, about $1):** on one block with many cars (b04, around the Gare quarter, which holds
   `#4950,6904`), try two methods on the same spots:
   - (a) free: classic inpainting (OpenCV `xphoto` FSR, or a patch-based fill, guided by the median asphalt and
     re-inked kerb lines);
   - (b) the painter's repair: `mdpaint.py --known <block canvas> --keep <not the mask> --band 32` with the day
     model, the Lightning 8-step settings, and `src` = the block's `src.png` with the spots cleaned again by a
     stricter `make_hint.py`. `md_core` skips windows that are fully known, so only windows with spots run.
   - Compare them side by side on the comparison page (`web/public/compare`, local).
   **Decision gate (owner):** method (a), (b), or (a) for single cars and (b) for car parks.
5. **Run** the chosen method on all 15 blocks (cap below). Check that the spots are now empty with a second
   `find_vehicles.py` pass. Then run `seam_check.py` and `water_check.py`.
6. **Versions without a GPU** (`pipeline/repair/carry_to_versions.py`): for each spot, take the repaired day
   pixels. Match their colour to the version using LAB mean and standard deviation measured on a ring 1 to 3 m
   around the spot, in both day and version. Write the result into the version's block canvas. At night, mask
   out the lit pixels in the ring, such as street lamps. Do this after the current version run has finished,
   and don't stop that run.
7. **Rebuild** the day tiles (`build_tiles.py`) and each version (`build_variant_tiles.py <variant>
   data/work/city/patches_<variant>.json`). Composite the Christmas patches again (item 12 makes this free).
   Then ask stream A to rebuild `occluders.png` and the drivable map, since the art changed.
8. **Prevention:** make the stricter `make_hint.py` the default for any future repaint, and add
   `find_vehicles.py` to the post-paint checks in CONTRIBUTING.md.

**Switch.** None (it is base art).
**Data.** New `pipeline/repair/`, and the repaired `data/work/city/b*/canvas_*.png` (keep the originals as
`*_pre_repair.png`).
**Cost.** Pilot about $1. Full day repair expected $6 to $11 at Lightning 8 steps (at most $0.75 per block if
every window has a spot, from Phase 2), with Modal start-up time on top. **Cap $16.** Versions free. If the owner
picks method (a), the full run is free.
**Verify.**
- The second detection pass finds fewer than 5% of the first count.
- Before-and-after shots at `?hour=13&off=traffic,transit`: `#4950,6904,1.0` (Gare), `#16330,8986,1.0`
  (Cents-Hamm), `#23547,6428,0.8` (Luxexpo car parks), `#8974,4151,0.8` (Glacis car park, also the Schueberfouer
  site), and the same at `?hour=22` for night.
- Also check `#7615,5801,1.0`, because the old town must not change outside the spots.
**Risks.**
- The painter may draw cars again in repair mode. Then use the stricter input and a higher band, or method (a).
- Colour transfer can leave a flat patch at night. Then use the GPU for the night version only: one more
  approval, about $5.
- Detection misses dark cars in shadow. The review sheet sorts by score, so look at the low-score end too.
**Estimate.** L.

### Item 5. "We need a task for rain, storm and wind, or fog"

**Today.** Snow is the only weather: 260 screen-space dots in `Overlay.tsx` when the season is winter
(`winter && on("snow")`). Clouds drift at a fixed wind (`WIND_LOW`, `WIND_HIGH` in `Clouds.tsx`). Nothing reads
the real weather.

**Approach.** One weather state, shared by every layer. It comes from the live forecast for the city
(Open-Meteo: free, no key, CORS-friendly, CC BY 4.0), from a picker, or from the `?weather=` parameter. Then
one sky layer draws precipitation, lightning and planes, and one WebGL layer draws fog that fills the valleys.

**Steps.**
1. `web/src/weather.ts`: a state of `{kind: clear | cloudy | rain | storm | snow | fog, intensity 0..1, wind:
   {speed m/s, from degrees}, cloud 0..1, visibilityKm}`, with a tiny subscribe API.
   - Live source: `api.open-meteo.com/v1/forecast?latitude=49.61&longitude=6.13&current=weather_code,precipitation,wind_speed_10m,wind_direction_10m,cloud_cover,visibility`,
     every 15 minutes and cached in `sessionStorage`. WMO weather codes are mapped to kinds.
   - Easing: changes blend over about 20 s, so rain starts softly.
2. `WeatherControl.tsx` (through SceneControl's `extra` slot): Live, Clear, Rain, Storm, Fog and Snow buttons,
   and a wind slider. Real buttons with `aria-pressed`, as CONTRIBUTING.md asks.
3. **Rain and storm** (`Sky.tsx`, a 2D canvas above the clouds, below the pins):
   - streaks slanted by the wind, projected to the screen (east-north to screen as in `project_lines.py`:
     x ∝ e + n, y ∝ (n − e)/2);
   - the drop count scales with intensity and the screen area, with a hard cap so the layer stays under 1.5 ms;
   - small splash rings on the ground only when z ≥ 0.6, inside painted areas;
   - at night, streaks near lamps catch warm light.
   - **Storm** adds lightning: a short brightening of the map (a white wash with low opacity, two pulses of
     80 ms) every 8 to 25 s. Never more than 3 flashes in any second (WCAG 2.3.1), and none at all with
     `prefers-reduced-motion`.
4. **Wet and overcast look:** a wash `div` (not a CSS `filter`, see item 3) dims and cools the map a little.
   Water glints in `Water.tsx` grow stronger in rain and calmer in fog.
5. **Wind:** `Clouds.tsx` takes the drift from the wind (direction and speed, clamped). Rain slant follows it.
   Overlay's birds turn into the wind and are fewer above 10 m/s (a small change by stream A at merge point M2).
   Swaying trees (PLAN.md Phase 6.3) stay a later task, since they need the crowns split first.
6. **Fog** (`fog`):
   - `pipeline/build_fog_mask.py` writes `web/public/data/fog.png` (1 px = 16 map px). R is the visible
     surface's height above sea level from `data/work/frames_height` (200 to 420 m, scaled to 0..255). G is
     "water nearby", since fog forms over the rivers first.
   - `Fog.tsx` (WebGL, like `Water.tsx`): fog density rises below a fog line that the weather sets. Valley fog
     sits at about 260 m, so the Alzette and Pétrusse fill while the old town rises above them. General haze
     comes from low visibility. Slow noise drifts with the wind, and a little parallax when panning gives it
     depth.
   - In live mode, fog appears for WMO codes 45 and 48 or visibility under 1 km. Morning valley fog is likely
     from October to February.
7. **Snow** moves into the weather layer: it falls when the weather says snow, or under the present rule
   (winter season with `snow` on) when the weather is off. Stream A removes the snow block from `Overlay.tsx` at
   M2, and the `snow` switch keeps its meaning.
8. **Credit** Open-Meteo in the About panel (one line in `App.tsx`, done by whoever merges at M3).

**Switch.** `weather`, `fog` (new). `snow` stays.
**Data.** `fog.png` (under 300 KB).
**Cost.** Free. Open-Meteo is free for non-commercial use. Check its terms on the day, and keep the request rate
at one per 15 minutes per visitor.
**Verify.**
- Shots with `?weather=rain:0.8,wind:12@250`, `?weather=storm:1`, `?weather=fog:0.9` and
  `?weather=snow:0.7&season=winter`, at `#8694,6852,0.55` (Grund valley, for fog) and `#7615,5801,0.8`. Do each
  at noon and at `?hour=21`.
- Harness timing with rain on, which must stay inside the item 3 budgets.
- A unit test of the WMO mapping.
**Risks.** Full-screen effects can make the map hard to read, so keep intensity moderate by default. Fog may hide
pins and labels: draw it under the pins (z-index 1) and lower its density at close zoom.
**Estimate.** L.

**Done (C3, stream C, 7 Nov 2026).** `web/src/weather.ts` (state, live Open-Meteo every 15 min kept in
`sessionStorage`, blends of 20 s live and 3 s from the picker), `web/src/sky/weatherCore.ts` (kinds, `?weather=`
text, WMO mapping, amounts; checks in `weatherCore.test.ts`, run with `node src/sky/weatherCore.test.ts`),
`WeatherControl.tsx` (Live, Clear, Rain, Storm, Fog, Snow and a wind slider with Auto), `Sky.tsx` (overcast wash,
rain with splashes at z >= 0.6 and warm streaks at night, snow, lightning as two 80 ms pulses every 8 to 25 s and
none with reduced motion), `Fog.tsx` with `pipeline/build_fog_mask.py` (`fog.png` 197 KB, 1 px = 32 map px), the
clouds' drift from the wind, and the water's glints from rain and fog. Shots: `data/work/shots/2026-11-07-c3d`.
Timing with `?weather=rain:0.8,wind:12@250` against the same build with the weather off (`c3-rain3` against
`c3-control`; the machine was busy with other runs, so both are slower than `c2-fixes`): the sky layer costs 0.1 to
0.4 ms a frame (p95 under 1 ms), the fog layer under 0.1 ms, and the phases differ by no more than the noise
between runs.
Left for the merge points:
- *Done in C4a:* the snow block left `Overlay.tsx` and `Sky.tsx` draws all snow; birds turn into the wind and are
  fewer above 10 m/s.
- **M3:** credit Open-Meteo (CC BY 4.0) in the About panel.

### Item 6. "The Pfaffenthal Panoramic Lift needs a redesign and repaint, and a 3D lift moving up and down"

**Today.** The lift is a landmark (`pfaffenthal-panoramic-lift`, pin at `9293,5432`, 3D model
`/landmarks/pfaffenthal-panoramic-lift/model.bin`). In the base art it is whatever the painter made of the 3D
city model: a slim glass tower, an open footbridge and a glass-floored platform, which the model data barely
describes. So the painting doesn't read as the real lift. Nothing moves.

**Approach.** Give the painter an accurate input for this one spot: a clean, hand-built model of the tower, shaft,
footbridge and platform, drawn into the render with the map's own camera. Repaint only that area with the
painter's patch repair, by day and then for each version. Leave the shaft empty, then add a live cabin that runs
up and down it.

**Steps.**
1. **Facts:** collect them from the research notes, `research/01-landmarks/images/pfaffenthal-lift__*.jpg`,
   the Wikipedia article and vdl.lu: height (about 60 to 71 m), number of cabins, ride time (about 30 s), opening
   hours, and the shape of the footbridge and platform. Write the facts with sources into
   `research/01-landmarks/README.md`.
2. **Model:** `pipeline/events/lift_model.py`. Boxes and prisms in the same style as `build_sprites.py`
   (import its `Renderer`, `project` and `rotate`), placed at the lift's real coordinates
   (49.61559, 6.13065) and heights from the height pass. It outputs a render-scale RGB crop of the lift as the
   3D city would look with it modelled cleanly (an empty shaft, glass as a light blue-grey tint with mullions),
   and a mask.
3. **Input:** paste the model over `data/work/city/<block>/src.png` for a 1200 × 1200 render px crop round the
   lift (block b00 covers `9293,5432`). Also make the matching layout crop.
4. **Repaint by day (needs approval):** `mdpaint.py` on Modal on that crop, with `--known` the day canvas crop,
   `--keep` everything outside the lift mask grown by 6 m, and `--band 48`, at the Lightning day settings. Try
   two or three seeds and let the owner choose on the comparison page.
5. **Versions:** for each of the six versions, the light model makes that version from the new day crop
   (`--src-cell 512`, 15 steps, `--known` the version crop, the same keep mask). Do this only after the current
   version run is finished.
6. **Paste and rebuild:** paste each crop back into its block canvas (keeping `*_pre_lift.png`), then rebuild the
   day and version tiles. Do this together with the item 4 rebuild to save a pass.
7. **Cabin sprite:** `pipeline/events/build_event_sprites.py` (stream B, importing the `build_sprites.py`
   renderer). It makes the glass cabin, one heading (the tower doesn't turn), by day and lit at night with a
   lamp mask as in item 1. It also makes a "front of shaft" overlay (mullions and the frame in front of the
   cabin), so the cabin reads as inside the glass. Output goes to `web/public/events/sprites.json` and PNGs.
8. **Path:** `web/public/events/lift.json` holds the bottom and top ground anchors in map px. The vertical travel
   on screen is metres × 0.866 / 0.25 map px, about 210 to 245 px for 60 to 71 m. It also holds the timing:
   about 30 s ride, a wait of 20 to 40 s at each end, and two cabins out of step if there are two. The position
   comes from the clock, like the trams, so every visitor sees the same thing. There is no service at night
   outside the opening hours, when the cabin stays parked at the bottom, lit.
9. **Drawing:** `EventLayer.tsx` draws the cabin (when `liftCabin` is on), then the shaft front overlay, from
   z ≥ 0.3. The cabin sits inside the painted art's shaft, so no occlusion is needed beyond the overlay.
10. **3D card (optional, after the rest):** if `model.bin` has the cabin as its own mesh, move it up and down in
    `Model3D.tsx` too. If not, leave the card as it is.

**Switch.** `liftCabin` (new). The repaint is base art and needs no switch.
**Data.** The lift model script, 7 repainted crops, `lift.json`, and the cabin sprites (under 100 KB).
**Cost.** Day crop at about 4 windows × 8 steps, 3 seeds: about $0.50 with start-up. Six versions at 15 steps:
about $2. **Cap $5.**
**Verify.**
- Shots at `#9293,5350,1.2`, `#9293,5350,0.6` and `#9600,5600,0.35`, by day, at `?hour=22`, and
  `?season=winter`. Compare before and after.
- The cabin's travel in a 40 s screen recording (Playwright video) at `#9293,5350,1.0?on=liftCabin`.
- `seam_check.py` on the crop edges.
**Risks.** The painter may still soften a thin glass tower. If so, also blend the model's clean line pass into
the input (ROADMAP "Building quality", option a). The cabin must line up with the painted shaft to within 1 to
2 px, so place the anchors by eye in a local helper page and store them.
**Estimate.** L.

### Item 7. "The merry-go-round and other Christmas things need animation"

**Today.** The three Christmas patches (`web/public/events/xmas/*_day.webp`, `*_night.webp`, `xmas.json`, made
by `pipeline/events/xmas_v2.py`) are still images. They hold a carousel and a big tree on Place Guillaume II
(Knuedler), a Ferris wheel of about 32 m and a Christmas pyramid on Place de la Constitution, and the chalet
ring on Place d'Armes.

**Approach.** The moving parts become live sprites in the same inked style, and the patches show only what doesn't
move (bases, supports, the wheel's A-frame). Lights twinkle at night. This depends on regenerating the patches
anyway (item 12).

**Steps.**
1. **Patches without moving parts:** in `xmas_v2.py` (rewritten in item 12), change the site prompts. The wheel
   becomes "its white steel A-frame support and a round boarding platform, with no wheel rim, spokes or
   gondolas". The carousel becomes "a round wooden platform with a flat round canopy roof on a central pole"
   (the roof stays painted). The pyramid becomes "the tall wooden pyramid with its top fan blades left out".
   This is one OpenAI run for both day and night, shared with item 12.
2. **Ride models** in `build_event_sprites.py` (stream B):
   - **Ferris wheel:** a rim, 24 spokes and 24 gondolas. It looks the same after one gondola step (15°), so only
     12 frames are needed, played at about 1 rpm.
   - **Carousel:** horses and poles under a rotating canopy rim. With 8 horses it repeats every 45°, so 12
     frames.
   - **Pyramid blades:** 8 frames.
   - All are drawn by day and at night (lit bulbs as a lamp mask, as in item 1), in the map's own camera.
3. **Placement:** `web/public/events/xmas/rides.json` gives, per ride, the site, kind, ground anchor (map px),
   scale and frame rate. Place each anchor by eye with a local helper page that drags the sprite over the patch
   at full zoom.
4. **Twinkling lights:** from each night patch, find the bright warm points (string lights, chalet lamps) and
   store them as a point list `*_lights.json`. `EventLayer.tsx` makes them twinkle slowly with `lighter`
   compositing at night, under `eventRides`.
5. **Drawing:** `EventLayer.tsx` draws rides and lights above the patches and below Overlay, from z ≥ 0.25.
   Rides stop with `prefers-reduced-motion`.
6. The same rides code serves Schueberfouer later (item 13: big wheel, chair-o-planes, drop tower).

**Switch.** `eventRides` (new; needs `christmas`).
**Data.** `rides.json`, the ride sprite atlases (target under 400 KB), and `*_lights.json`.
**Cost.** Shared with item 12 (OpenAI, about $1, cap $3).
**Verify.**
- Shots `#7052,6150,1.2?event=winterlights&on=eventRides` (wheel and pyramid), `#7880,6112,1.2` (carousel) and
  `#7615,5801,1.0` (Place d'Armes lights), by day and at `?hour=19`.
- A short Playwright video of each to check the speed and the frame loop: no jump where the loop restarts.
**Risks.**
- The drawing service may still paint a wheel. Then retry with a firmer prompt (the cap allows 3 tries) or
  mask the painted wheel and inpaint its spokes from the sky behind.
- Sprite and painting styles may differ. Use the same ink weight (1 px, `INK`) and shading as the vehicles,
  which already sit well on the map.
**Estimate.** M.

### Item 8. "Cars will move out of the way of emergency vehicles"

**Today** (`traffic.ts`):
- `emergencyStep` marks cars up to 70 m ahead of a siren on its lane, and on the next lane of its route, with
  `yieldUntil = t + 1.5`.
- `accel` then caps their speed at 45% of the limit if the street has more than one lane their way, or 85%
  otherwise.
- The step function eases a drawn sideways `pull` to 0.9 m.
- The siren overtakes only by `changeLane` to a free parallel lane.
- So on single-lane streets the siren still queues behind slowed cars, and cars barely move aside.

**Approach.** A proper "aside" state:
- On roads with two or more lanes in the siren's direction, an emergency corridor (left lane to the left, the
  others to the right).
- On single-lane streets, a full pull-over to the kerb and a stop.
- Oncoming cars on narrow roads slow and keep right.
- The siren may pass a car that is aside when the road is wide enough, or use the free oncoming lane. Cars rejoin
  after it has passed.

**Steps.**
1. Use the street width `w` from item 2 (step 3). The lateral room is `w/2 − lane centre − car width/2 − 0.3 m`.
2. **Corridor** (two or more lanes): cars ahead within 120 m, in the siren's direction, move aside, with the
   leftmost lane drawn to the left and the others to the right, by up to 1.2 m each, and slow to 30%. The siren
   drives along the lane boundary (a drawn offset of half a lane). Its leader search ignores cars that are aside
   on both lanes. Check Luxembourg's emergency-corridor rule in the *Code de la route* and note the source in a
   comment.
3. **Pull-over** (one lane): within 60 m, the car pulls to the kerb (drawn offset to the room in step 1) and
   stops over about 2 s. If `w ≥ siren width + car width + 0.6 m`, the siren treats it as no obstacle, and the
   two overlap only in the sideways sense. If the room is too small, the siren overtakes by the oncoming lane
   when it is clear for its passing distance (about `v × 4 s + 20 m`), and oncoming cars within 50 m stop.
4. **Narrow one-way streets** (old town, no room): cars keep going at the limit and turn off at the next
   junction if their route allows, choosing an exit away from the siren's `route`.
5. **At red lights:** cars queued in front of a siren at a red light stay put. The siren uses the oncoming lane
   or the corridor to reach the stop line, then crosses at `RED_CREEP`, as now. Cross traffic already gives way
   ("a siren coming up to this box on another approach goes first").
6. **Rejoining:** after the siren is 20 m past, each car waits 0.5 to 2 s (random), eases `lat` back to 0 and
   carries on. No car stays aside more than 12 s after the siren has gone.
7. **Drawing:** `Overlay.tsx` already adds `lat + pull` in `cars()`. Set `pull` from the new state, and keep
   blue-light flashing as it is.
8. **Tests** (`traffic.test.ts`, new scenarios on the real roads, with `seed`):
   - a busy two-lane road (Boulevard Royal near `7025,5515`);
   - a single-lane two-way street;
   - an old-town one-way street;
   - a signalled junction.
   For each, measure the siren's mean speed as a share of the free-flow speed (target ≥ 70% on two lanes, ≥ 50%
   on one lane), cars passed, overlaps (only "aside pass-through" allowed), cars still aside 15 s later (0), and
   deadlocks (no increase over the baseline).
9. A dev parameter `?siren=<street name>` calls `spawnEmergency` on that street (in `Overlay.tsx`), for videos.

**Switch.** None (inside `emergency`).
**Data.** None beyond `w` from item 2.
**Cost.** Free.
**Verify.** The scenario tests, plus Playwright videos at `#7025,5515,0.9?on=traffic,emergency&seed=7&siren=Boulevard%20Royal`
and on a single-lane street in Limpertsberg (`#9458,3413,1.0`).
**Risks.** Pass-through needs care, so other cars never use the gap the siren opens. Mark the gap as for
emergency vehicles only. Complex junction boxes can deadlock with cars aside, so the existing deadlock removal
stays as the backstop.
**Estimate.** M. Item 2 (road widths) must come first.

### Item 9. "Trains don't go under bridges and tunnels"

**Root cause** (`Transit.ts::drawTransit`, called from `Overlay.tsx`):
- Trams and trains are drawn straight onto the main overlay canvas, not into the vehicle layer, so `occ.cut` is
  never applied. Nothing hides a train passing under a road bridge, behind a building or behind a tree, although
  `build_occlusion.py` already fills the rail band (`road_band` covers `rail`).
- The only test is `visible(x, y)` on the section centre against `visibility.png`, so whole 26 m coaches pop in
  and out.
- GTFS shapes carry no tunnel flag. `lines.json` has 50 rail tunnel ways (for example between `6375,7876` and
  `7861,7551`, and the Bonnevoie and Hollerich tunnels), but the transit data never sees them.
- Deck heights on viaducts come from `build_transit.py::to_px`, which snaps each GTFS point to the nearest OSM
  rail vertex within 25 m (for z only). Bridge decks there are a straight line between the ends. `deckAt`, which
  `occlusion.ts` provides for exactly this case, isn't used.

**Approach.** After item 10, every transit shape vertex knows its OSM way and its distance along it. Then trains
are drawn like cars: into the vehicle layer, lifted onto decks with `deckLift`, cut against the foreground at
their real height, and clipped at tunnel portals.

**Steps.**
1. Item 10 makes the shapes carry `[wayId, s]` per vertex (or per run of vertices).
2. In `Transit.ts`, return the sections as drawables (type, screen position, heading, way id, s, flags) instead
   of drawing them. `Overlay.tsx` puts them into the passes: ground trains with buses at 4.6 m (cut "ground"),
   and deck trains lifted by `occ.deckLift(id, s)` into the deck pass (cut "deck"). Sort by screen y with the
   road vehicles.
3. **Tunnels:** sections whose way is a tunnel aren't drawn. At a portal, the section that straddles it is
   clipped: after drawing, erase (`destination-out`) the tunnel way's buffer (3.5 m), extruded up by the
   train's height (4.6 m × 3.46 px per m), on the vehicle layer. The coach then slides into the hillside
   cleanly.
4. **Under bridges:** the "ground" cut with a 4.6 m threshold now hides the train where a road deck crosses
   over. Check the three places where road bridges cross the line in the valley (Pfaffenthal, Pulvermühle,
   Hamm).
5. The tram on the Red Bridge and on Avenue JFK gets its deck lift from the same profiles.
6. The warm night glow becomes lit window pixels (item 1 step 6), so it is cut with the body too.

**Switch.** None (inside `transit`).
**Data.** `transit.json` with way references (item 10). `road_heights.json` must include every rail bridge
(already its intent; check the count against the 31 rail bridges in `lines.json`).
**Cost.** Free.
**Verify.**
- A headless check (`web/src/components/transit.test.ts`, Node): over a full simulated day, no section is drawn
  while its way is a tunnel, and every deck section has a non-zero lift.
- Shots and short videos at `?hour=8.2&on=transit` (busy morning):
  - `#7632,7573,1.0` and `#6375,7876,1.0` (tunnel portals);
  - `#8625,7575,0.8` (Pulvermühle viaduct);
  - `#9999,7060,0.8` and `#10116,6588,0.8` (Clausen and Pafendall viaducts);
  - `#15445,11122,0.8` (Hamm viaduct);
  - `#10816,5131,1.0` (Pfaffenthal-Kirchberg station under the Red Bridge).
**Risks.** Tunnel ways in OSM may not quite meet the portal in the painted hillside. Nudge the clip start by up to
10 m to the painted portal by eye, and store the offsets.
**Estimate.** M. Item 10 must come first.

### Item 10. "Trains don't go exactly along the tracks"

**Root cause** (`pipeline/build_transit.py`): positions come straight from the GTFS `shapes.txt` lon/lat, run
through `to_px` with only the height snapped to OSM. GTFS rail shapes from the national feed are coarse (often
straight lines between stops) and don't follow the real alignment or the right track. The painted tracks, though,
were drawn from the OSM rail lines (`make_hint.py` step 2b). So trains drift off the painted rails, mostly on
curves and in the station throat. Stop distances are taken from the nearest shape vertex in unscaled lon/lat,
which adds jumps.

**Approach.** Match each GTFS shape onto the OSM rail network, and use the OSM geometry from `lines.json` as the
shape. That is the same line the painting followed. Then recompute stop distances along the new shape.

**Steps.**
1. In `build_transit.py`, make a rail graph from `lines.json` `rail` (kinds rail, tram and light_rail, tunnels
   included), joining ways at shared end points.
2. **Map matching:** for each shape, take a point every 20 m and keep candidate graph positions within 40 m.
   Run a Viterbi pass (an HMM, whose emission is the distance to the GTFS point and whose transition is the
   difference between graph distance and straight distance). The result is a path of `[wayId, from s, to s]`
   pieces.
3. **Track side:** where there are parallel tracks, prefer the track on the running side for the direction of
   travel. Luxtram runs on the right. For CFL lines, check the running side line by line (Luxembourg is believed
   to run on the left, as in Belgium and France), and keep a table in the script.
4. **Shapes from OSM:** write the shape as the concatenated OSM geometry in map px, with a parallel array of way
   ids and distances (for item 9). Keep the height logic as it is, or drop it, since deck heights now come from
   `road_heights.json`.
5. **Stops:** project each stop onto the matched path (the nearest point along the path, not the nearest
   vertex), and keep them in order along it.
6. **Timing** (`Transit.ts`): the ease between stops stays. Add a check that the speed never exceeds 160 km/h for
   trains and 70 km/h for trams. If a matched path is much longer than the GTFS one, that is a sign of a bad
   match: fail the build for that shape and print it.
7. `pipeline/transit_check.py`: draw matched shapes (green) and GTFS shapes (red) over the painted art crops at
   the stations and viaducts, like `overlay_check.py`.
8. Add the monthly GTFS refresh (PLAN.md Phase 6.5): a GitHub Action that runs `build_transit.py` on the newest
   feed. It needs `lines.json`, which is in git.

**Switch.** None (inside `transit`).
**Data.** A new `transit.json` (shapes are longer, so expect about 0.8 to 1 MB; store the coordinates as deltas
if it is larger).
**Cost.** Free.
**Verify.**
- The check images at Gare (`4950,6904`), Pfaffenthal-Kirchberg (`10816,5131`), Pulvermühle (`8625,7575`) and
  Cents-Hamm (`16330,8986`).
- A headless test: for 99% of the samples along all shapes, the distance to the nearest OSM rail line is under
  0.5 m, and the trains' mean speed between stops is plausible.
- Shots `#4950,6904,1.0?hour=8.2&on=transit` (station throat).
**Risks.** OSM may lack a siding or platform track that a train really uses. Then the HMM picks the nearest main
track, which is fine visually. Check the matched lengths for outliers.
**Estimate.** M.

### Item 11. "We need Cargolux 747s and Luxair planes moving in the sky"

**Setting.** Findel (ELLX) lies just east of the map. Its reference point projects to about `26792,11350`, beyond
the right edge at x = 26624. The single runway is 06/24, about 064°/244°. With the usual south-west winds,
runway 24 is in use: departures climb out towards the west-south-west, which on this map runs from the lower
right towards the upper left across the city. With east winds, runway 06 is in use: arrivals come in low on a 3°
glide path over the city from the west. A plane at altitude h is drawn h × 3.46 map px up the screen from its
ground point.

**Approach.** Pre-render low-poly aircraft in the map's camera, as with the vehicles. Fly them on simple departure
and arrival tracks with an altitude profile, choosing the runway from the live wind (item 5). Use a believable
daily schedule computed from the date. Optionally add live positions later.

**Steps.**
1. **Facts and liveries:** Cargolux 747-8F and 747-400F; Luxair 737-800 and MAX 8, De Havilland Dash 8-400, and
   the E195-E2 if Luxair flies it now (check). Get each livery from reference photos on Wikimedia Commons. Note
   each source in `research/06-city-details/README.md` under a new "Findel" heading.
2. **Models:** `pipeline/build_plane_sprites.py` (stream C). It imports the `build_sprites.py` renderer and builds
   custom triangle lists (tapered fuselage, swept wings, engines, fin and tailplane), because boxes alone won't
   do. 32 headings at a level attitude, plus a nose-up set at 8° for the climb. Navigation lights (red left,
   green right, white tail), red beacons and white strobes go in a lamp atlas as in item 1. The output is
   `web/public/sprites/planes.json` and its atlases. Draw at real size: a 747-8F is 76 m long, so 304 map px.
3. **Tracks:** `pipeline/build_flights.py`.
   - Runway ends come from OSM (`aeroway=runway` at ELLX, fetched with the other OSM data). Elevation is
     376 m.
   - Departures 24: climb at about 7% to 3000 ft, then a gentle turn north or south.
   - Arrivals 06: a 3° final from about 15 km out, which passes over the city.
   - Departures 06 and arrivals 24 mostly stay off the map. Show them only where they cross it.
   - Each track is projected with the same formula as `project_lines.py` (z = elevation + altitude) and written
     to `web/public/data/flights.json`.
4. **Schedule** (`web/src/sky/flights.ts`): a seeded daily plan from the date. Luxair has about 40 departures and
   40 arrivals from 06:00 to 23:00. Cargolux has about 10 to 14 movements, many in the evening and at night,
   within the airport's night rules (check these). The runway in use comes from the wind in `weather.ts`, or 24
   by default. Positions come from the clock, like the trains, so every visitor sees the same planes.
5. **Drawing** (`Sky.tsx`): planes above the cloud sea and below the pins, at most 3 on screen.
   - A shadow on the ground only below 400 m altitude, faint and blurred, offset by the sun.
   - At night, navigation and strobe lights, plus landing lights on final.
   - Planes are never cut by buildings, since they are always higher.
6. **Optional live mode (later, owner's choice):** real positions from ADS-B through the existing Cloudflare
   Worker (`web/worker/`) as a cached proxy (60 s). Check the provider's terms first (OpenSky needs an account,
   and its terms are non-commercial).

**Switch.** `planes` (new).
**Data.** `planes.json` and atlases (target under 600 KB), and `flights.json` (small).
**Cost.** Free.
**Verify.**
- A unit test that the schedule is the same for the same date and that the first and last flights are in hours.
- Shots at `#16000,8000,0.15?on=planes&hour=10.25&date=2026-11-10`, picked by the test to have a departure on
  screen.
- An east-wind case `?weather=clear,wind:6@80` at `#12000,7000,0.25`, with an arrival on final.
- A night shot `?hour=22`.
**Risks.** Flat-shaded swept wings may alias at 32 headings. If they look stepped, render 64 headings for planes.
The model must stay recognisable (a 747's hump and four engines, Luxair's tail colours), so the owner checks
it by eye.
**Estimate.** M.

**Done (C4b, stream C, 8 Nov 2026).** `pipeline/build_plane_sprites.py` builds four low-poly aircraft with the
vehicle renderer (lofted fuselages, swept wings, engines, fins; 0.5 m per sprite px, with its own inking thresholds
for that scale): Cargolux 747-8F, Luxair 737-800, E195-E2 and Dash 8-400, each at 32 headings level and 8 degrees
nose up, plus a soft ground shadow, and per heading the visible navigation, beacon, strobe and landing lights
(`web/public/sprites/planes.json` and four atlases, 227 KB). `pipeline/build_flights.py` takes runway 06/24 from OSM
and writes four tracks (`web/public/data/flights.json`, 6 KB): departures 24 turning north or south, arrivals 06 on a
3 degree final over the city, and a downwind for arrivals 24 north of the city. `web/src/sky/flights.ts` holds the
seeded daily plan, the runway from the wind and the positions (checks: `node src/sky/flights.test.ts`; `--find`
lists the moments with an aircraft in the shots' views). `Planes.tsx`, mounted by `Sky.tsx` behind `planes`: at most
three aircraft, above the clouds and below the rain and the pins, drawn no smaller than at zoom 0.28 so that they
still read zoomed far out; a shadow below 400 m; lights at night; nothing flashes with reduced motion. Facts and
sources: `research/06-city-details/README.md`, "Findel".
Shots `data/work/shots/2026-11-07-c5-planes3`: the views' hours were picked with `--find` (15.8183 Cargolux departure,
9.9542 Luxair departure, 22.3053 night departure), with `weather=clear` so that the live wind cannot change the
runway, and the east-wind view moved to `#12000,8700,0.25`, where the final runs.
Timing: the planes layer costs 0.01 to 0.05 ms a frame (its canvas is hidden while no aircraft is on screen). The
machine was heavily loaded by other work during these runs (load average 5 to 8), so whole-app numbers swung by 2 to
3 times between identical runs; alternating quick phone runs with planes on and off (`c5-ab-on1/off1/on2/off2`)
show no difference beyond that noise.
Open: the owner's check of the models and liveries by eye; the Luxair aircraft are small and pale at zoom 0.15;
departures 06 are not drawn (they leave eastwards, off the map); live ADS-B positions not done (optional).

### Item 12. "Christmas markets have a highlight on their edge, which is not good"

**Root cause** (`pipeline/events/xmas_v2.py`):
1. **The mask keeps a ring of redrawn map.** The kept area is the changed region dilated by 31 px, then blurred
   (σ = 9) and stretched by 1.4. The drawing service redraws the whole crop slightly differently: line weight,
   snow tone and sharpness, after a resample from 760 to 1024 and back. So the soft band blends two different
   drawings, and that shows as a light, blurry halo round each market.
2. **Colour is matched globally** (LAB mean and standard deviation over all unchanged pixels), which can't fix
   local differences. At night the market's glow also spills into the band.
3. **The base is out of date** (issue I11). The patches were cut from an earlier winter and winter-night canvas,
   and those versions are being painted again now. The ring then carries old art over new.
4. **The cross-fade is doubled.** `App.tsx` gives the day patch alpha 1 − n and the night patch alpha n, while the
   map versions under them also cross-fade. Halfway through, about 25% of the base shows through the patches,
   which lightens the edge during dusk.
5. **Resampling:** each 1024 px patch image is drawn into 760 map px (`addSimpleImage` width), which softens it
   against the crisp tiles. Lossy WebP alpha adds fringes.

**Approach.** Make the halo impossible by construction: wherever the patch is partly transparent, its colour is
the current map's own colour. Keep the patch pixels only on the market's objects, with a feather of 2 or 3 px.
Fix the cross-fade, and work at the map's scale.

**Steps.**
1. Split `xmas_v2.py` into two steps:
   - **draw:** the paid call. It keeps caching the raw output as now.
   - **composite:** free, and re-runnable whenever the winter art changes (so I11 becomes a free rerun). Put it
     in a shared module `pipeline/events/patchlib.py`, for item 13 too.
2. **Composite:**
   - Resize the raw image to the crop at map scale: 760 × 760, the native map px. The patch is now 1:1 with
     the tiles.
   - Build the object mask from the differences, as now, then refine it at the edges with a guided filter on the
     raw image. No 31 px dilation. Grow by 2 px and feather 3 px.
   - Inside the feather, set the RGB to the **current** base pixel for the part outside the objects, so blending
     changes nothing there.
   - Match colour locally (in tiles of about 64 px, smoothed) on a 6 to 20 px ring just outside the mask, not
     globally.
   - Save as lossless WebP for alpha (`lossless=True`, or `alpha_quality=100` with `quality=90`).
3. Base crops come from the newest `canvas_winter_s15.png` and `canvas_winter_night_s15.png` of the block that
   holds the square, b00, not a fixed file. Read the path from `city_blocks.py` state.
4. **Cross-fade** (stream B's lines in `App.tsx`): the day patch at alpha 1 whenever Christmas is on, and the
   night patch at alpha n over it. Then the base never shows through mid-fade.
5. **A check script**, `pipeline/events/patch_check.py`: composite each patch over the current tiles. Measure the
   mean absolute difference from the base in a ring 4 to 40 px outside the object mask (target under 1.5 levels),
   and the brightness step across the mask edge. Write a contact sheet.
6. **Regenerate** the drawings only if the new prompts are needed for item 7. That is one run, shared.

**Switch.** None (inside `christmas`).
**Data.** New `web/public/events/xmas/*.webp` and `xmas.json` with `w = h = 760` (unchanged placement).
**Cost.** The composite is free. The new drawings for item 7 are 3 sites × day and night × up to 3 tries at about
$0.06 each (from `openai_spend.json`), so about $1. **Cap $3**, passed to the script.
**Verify.**
- `patch_check.py` numbers.
- Shots at `#7615,5801,1.2`, `#7052,6150,1.2` and `#7880,6112,1.2` with `?event=winterlights&season=winter`, at
  `hour=13`, `hour=17.2` (mid-fade) and `hour=21`. The edge must be invisible at every zoom down to 0.3.
**Risks.** If the winter versions change again after the composite, rerun the composite (free). Lossless WebP
patches are larger (about 300 to 600 KB each), which is acceptable for 6 files.
**Estimate.** S.

### Item 13. "Can we have other events as well as Christmas?"

**Material.** `research/05-events/events.json` lists 23 events with rules, 2026 and 2027 dates, places and
`layer_idea`. "Rock um Knuedler" (July, Place Guillaume II) isn't in it yet. Research it and add it with the same
fields first.

**Approach.** One small event framework (manifest, calendar and picker), with patch generation shared with
Christmas (the item 12 composite) and live effects (fireworks, runner streams, bonfire flicker, bats) that cost
nothing. Then add events one at a time, by visual impact and by the date they come round next.

**Steps.**
1. **Calendar** (`web/src/scene.ts`, stream B): `activeEvents(date)` returns the events on that day from rules
   ported from `events.json` (Easter-relative ones use the `easter()` already in `Transit.ts`, moved to a shared
   place). `christmasOn` becomes one of them. A unit test checks each rule against `dates_2026` and
   `dates_2027`.
2. **Manifest:** `web/public/events/events.json` replaces `xmas.json` (keep reading the old file until the
   change is merged). Each event has an id, a switch, sites (patch rectangle, files per variant: day, night,
   and a season if the event belongs to one), rides, lights, effects (fireworks shows, runner routes, bonfires,
   flags) and an optional time window (fireworks at 23:00).
3. **Viewer:** `App.tsx` (stream B's lines) generalises the Christmas patch code to "patches of every active
   event whose switch is on". The season follows the event when the person picks it (Christmas → winter,
   Schueberfouer → summer, Octave → spring). `SceneControl.tsx` (stream B) gets an "Events" button that lists
   today's events, plus all events when `events` is on, so any event can be previewed out of season. The
   `?event=` and `?date=` parameters drive the same state.
4. **Patch generation:** `pipeline/events/event_patch.py <event> <site> <day|night> <variant canvas> <cap>`
   generalises `xmas_v2.py`, using the prompts from `layer_idea` and the halo-free `patchlib.py`. It has the same
   spending log and cap.
5. **Live effects** (`EventLayer.tsx`):
   - **Fireworks:** a particle system (rockets, bursts, sparkles fading) launched from a point and height in the
     manifest. National Day: 22 June 23:00 from Pont Adolphe (`5962,6105` at deck height), 17 minutes.
     Schueberfouer closing: 22:00 from the Red Bridge. New Year's Eve: light scattered sparkles at midnight (the
     city bans private fireworks, so keep it light, per the research notes). Respect reduced motion, and don't
     flash brightly.
   - **Runners** (marathon): a stream of small light dots along a route polyline from the organiser's map,
     hand-drawn into the manifest. These are live, not painted, which suits the base-art rule.
   - Bonfire flicker for Buergbrennen, bats over the Alzette for Halloween, and flags waving (a 4-frame sprite
     on flagpoles) for National Day.
6. **Order of events** (each is S to M, and each has its own switch):

   | # | Event | Date it comes round next | What | Paid art |
   |---|---|---|---|---|
   | 1 | New Year's Eve (`newYear`) | 31 Dec 2026 | Christmas still up, light sparkles at midnight | none |
   | 2 | National Day (`nationalDay`, `fireworks`) | 22 and 23 Jun 2027 | Fireworks over the Pétrusse, flags on public buildings, torches along the procession route at night | flags patch for the old town (optional), about $0.50 |
   | 3 | Schueberfouer (`schueberfouer`) | 20 Aug to 8 Sep 2027 | The Glacis car park (`8974,4151`) full of rides and stalls (one large patch, day and night), a big wheel and chair-o-planes as live rides, closing fireworks | about $1 (bigger crop, 2 tiles) |
   | 4 | Octave and Mäertchen (`octave`) | 17 Apr to 2 May 2027 | Stalls and a covered terrace on the Knuedler (spring day and night) | about $0.50 |
   | 5 | Éimaischen (`emaischen`) | 29 Mar 2027 | Pottery and craft stalls on the Fëschmaart (spring day) | about $0.30 |
   | 6 | ING Night Marathon (`marathon`) | May 2027 (date not yet published) | Glowing runner stream over the Red Bridge, Ville Haute and the Gare quarter; arches as small patches | about $0.30 |
   | 7 | Halloween (`halloween`) | 23 to 31 Oct 2027 | Pumpkins, orange-lit Neimënster at night, bats | about $0.50 |
   | 8 | Buergbrennen (`buergbrennen`) | 13 and 14 Feb 2027 | Bonfires at dusk at Cents, Bonnevoie and the Pétrusse, with smoke | about $0.30 |
   | 9 | Fête de la Musique and Rock um Knuedler (`musicStages`) | June and July 2027 | Stages with lighting rigs on the old-town squares | about $0.50 |

   Carnival is held outside the city (Diekirch, Pétange), so it is only a possible easter egg later.
7. **Base-art rule:** event patches show no people and no vehicles, as the Christmas prompt says ("No people, no
   vehicles"). Crowds, if ever wanted, are live dots, like the runners.

**Switch.** `events` (master) and one per event, listed in M0.1, plus `fireworks`.
**Data.** `events.json`, the patches per event and variant, ride sprites (shared with item 7), and the routes.
**Cost.** About $4 for the table above, at about $0.06 per drawing with retries. **Cap $6.**
**Verify.**
- Calendar unit tests.
- For each event, shots at its site with `?date=<a day of the event>&event=<id>`, by day and at night, and
  `patch_check.py` on its patches.
- National Day fireworks: a 20 s video at `#5962,6105,0.4?date=2027-06-22&hour=23.05&on=events,nationalDay,fireworks`.
**Risks.**
- Summer patches must sit on the summer day art (`day`) and `night`. Spring events sit on `spring` and `night`.
  Regenerate them if those versions change (the composite step makes this free).
- The Schueberfouer site is big, so check the patch size against GitHub Pages' total.
**Estimate.** L (the framework is M, then each event S to M).

---

## 4. Three work streams

### Stream A: vehicles and rail
Items **1, 2, 10, 9, 8**, plus stream A's part of **3**.

**Owns:**
- `web/src/components/Overlay.tsx`, `Transit.ts`, `sprites.ts` (after M0), `occlusion.ts`;
- `web/src/sim/traffic.ts`, `traffic.test.ts`, the new `audit.ts`, and `web/src/components/transit.test.ts`;
- `web/src/dev/SpriteLab.tsx`;
- `pipeline/build_sprites.py`, `build_occlusion.py`, `build_transit.py`, `project_lines.py`, the new
  `build_drivable.py` and `transit_check.py`;
- `web/public/sprites/sprites.json` and the vehicle atlases, `web/public/data/{lines,transit,occluders,road_heights}.*`
  and `drivable/`.

**Order:**
1. A0, item 3 part (S): draw once per frame (with a temporary guard until `frame.ts` lands), sort passes by y,
   and the `cars()` array. This makes every later measurement honest.
2. A1, item 1 lamps (S).
3. A2, item 2 placement: audit, drivable map, widths, lanes, canopy, guard (L).
4. A3, item 10 map matching (M).
5. A4, item 9 trains in the vehicle layer, tunnels and decks (M).
6. A5, item 8 emergency pull-over (M; needs A2's widths).
7. A6, item 3 part (M): frame clock adoption, dirty-rectangle vehicle layer, occlusion LRU and tiles (I13), lazy
   `lines.json`, graph build in idle time. Remove the snow block when stream C's weather lands (M2), and make
   birds follow the wind.

**Contract with others:** keep `build_sprites.py`'s `Renderer`, `project`, `rotate`, `frame_image`, `MPP` and the
camera unchanged in signature. Streams B and C import them. If they must change, tell both streams before
merging.

### Stream B: art and events
Items **12, 7, 4, 6, 13**.

**Owns:**
- `pipeline/events/*` (with the new `patchlib.py`, `event_patch.py`, `patch_check.py`, `build_event_sprites.py`
  and `lift_model.py`);
- `pipeline/repair/*` (new);
- `pipeline/make_hint.py`, `city_blocks.py`, `build_tiles.py`, `build_variant_tiles.py`;
- `pipeline/gpu_train/{paint_city.py, modal_paint.py, tiles/mdpaint.py}`: only if a repair option is missing. They
  are shared with the version run now in progress, so don't change them while it runs.
- `web/public/events/*`, `research/05-events/*`, and the lift facts in `research/01-landmarks/README.md`;
- `web/src/scene.ts`, `web/src/components/SceneControl.tsx` (but not the `extra` slot's contents), and the new
  `EventLayer.tsx`;
- in `App.tsx`, only the event patch lines (today lines 61 to 62 and 137 to 147) and the event state;
- the local review and helper pages under `web/public/live/` (never published).

**Order** (set by the Winterlights opening on Friday 20 Nov 2026):
1. B1, item 12 halo (S). Use the newest winter and winter-night art when it is ready. If the version run isn't
   finished by Thursday 12 Nov, use the present art, then rerun the composite (free) when it is.
2. B2, item 7 rides and lights (M), sharing one paid drawing run with B1. **Ready for the owner's check by
   Wednesday 18 Nov.**
3. B3, item 4 painted cars (L): detect and review, pilot, gate, full run, carry to the versions, rebuild tiles.
4. B4, item 6 Pfaffenthal lift (L). Its tile rebuild joins B3's.
5. B5, item 13 events (L): the framework, then the events in the order of the table.

### Stream C: performance, weather and sky
Items **3** (harness and its own files), **5**, **11**.

**Owns:**
- `web/src/frame.ts`, `perf.ts`, `weather.ts`, and the new `web/src/sky/*`;
- `web/src/components/{IsometricMap.tsx, Water.tsx, Clouds.tsx, Pins.tsx, LandmarkPanel.tsx, Model3D.tsx}`, and the
  new `Sky.tsx`, `Fog.tsx` and `WeatherControl.tsx`;
- `web/src/styles/global.css`;
- `web/scripts/{shots.mjs, perf.mjs, shots.json}` (others add entries to `shots.json` freely: it is a list, so
  append only);
- `web/vite.config.*` and `web/package.json` (dev dependencies);
- `pipeline/build_fog_mask.py`, `build_plane_sprites.py`, `build_flights.py`, `build_clouds.py`,
  `build_water_mask.py`;
- `web/public/sprites/planes.json` and the plane atlases, `web/public/data/{fog.png, flights.json}`.

**Order:**
1. C1, item 3 harness, HUD and baseline (M). Done in the first days, so streams A and B can measure their own
   changes.
2. C2, item 3 fixes in stream C's files, the frame clock and adaptive quality (L).
3. C3, item 5 weather and fog (L).
4. C4, item 11 planes (M). Uses C3's wind for the runway choice.

### Rules for the shared files
- **`features.ts` and `.env.production`:** every new switch is added in M0. After that, only the owner (or the
  person merging at their request) edits `.env.production`, to switch something on publicly (PLAN.md Phase 7).
  The streams don't touch either file. If a stream truly needs a new switch, it asks the person merging to add
  it at the next merge point.
- **`App.tsx`:** M0 mounts every new component and the test parameters. Afterwards stream B owns only the event
  lines, and the About panel credit (Open-Meteo) is added at the final merge. Any other change goes through the
  merge points, in one small commit.
- **`sprites.ts`:** stream A, except for the M0 `file` parameter.
- **`shots.json`:** append only. Keep entries sorted by stream and name, so merges stay trivial.
- **Tiles and big data under `web/public/tiles` and `data/`:** not in git. Only stream B rebuilds tiles. Stream A
  rebuilds occlusion and drivable data after stream B's art changes.

### Dependencies between streams
| From | To | What | Handled by |
|---|---|---|---|
| C1 harness | A, B | Measuring changes | C1 first. A0 runs before and after |
| C2 `frame.ts` | A6, B (`EventLayer`), C3/C4 | One frame clock | M0 stub with the same API. Real version at M2 |
| A1 lamp atlas | B (rides, cabin), C4 (plane lights) | The lamp format in sprite JSON | A1 defines the format at M1. B and C follow it |
| `build_sprites.py` renderer | B, C | Imports | Signature freeze (stream A contract) |
| B3/B4 art changes | A2 canopy, drivable map | Data rebuild | A reruns `build_occlusion.py` and `build_drivable.py` after B's tile rebuild (free, about 30 min) |
| A2 road widths | A5 emergency | `w` in `lines.json` | Same stream, in order |
| A3 map matching | A4 tunnels | Way ids in `transit.json` | Same stream, in order |
| C3 weather | A6 (snow, birds), C4 (runway), Water/Clouds (C) | `weather.ts` API | C3 publishes `weather.ts` early (M2) with a fixed "clear" state |
| Version run (in progress) | B1, B3, B4 | The newest winter and versions | B waits for it to finish before touching versions. Never edits its files while it runs |

### Merging
- Each stream works on its own branch (`stream-a`, `stream-b`, `stream-c`) in its own git worktree, branched from
  main after M0.
- **Merge points:**
  - **M1** (Wed 11 Nov): A0 and A1, B1 (composite), C1.
  - **M2** (Wed 18 Nov): B2 (Christmas ready for the switch-on check), A2 and A3, C2's `frame.ts` and the
    `weather.ts` API.
  - **M3** (about 2 Dec): A4 and A5, B3, C3.
  - **M4** (about 16 Dec): A6, B4 and the first events, C4.
  - The rest of the events follow one by one.
- **Order at each merge point:** C first (the infrastructure), then A, then B. Each rebases onto main before
  merging, so the later ones solve any conflicts in their own files.
- **Before each merge:** type check, build, traffic tests, the new unit tests, the shots set compared with the
  last merge, and the perf harness compared with the baseline (no budget newly broken).
- Merge only when the owner asks (global rule). Public switch-on stays a separate step per feature.

---

## 5. Spending

| Item | Where | Expected | Cap (needs approval) |
|---|---|---|---|
| 4 Painted cars: pilot | Modal H200 | about $1 | $2 (part of the $16) |
| 4 Painted cars: day repair, 15 blocks | Modal H200 | $6 to $11 (free if the classic method wins) | $16 total for item 4 |
| 6 Pfaffenthal lift: day and 6 versions | Modal H200 | about $2.50 | $5 |
| 7 and 12 Christmas drawings | OpenAI images | about $1 | $3 |
| 13 Other events (9 events) | OpenAI images | about $4 | $6 |
| 1, 2, 3, 5, 8, 9, 10, 11 | laptop, free APIs | $0 | $0 |
| **Total** | | **about $14 to $19** | **$30** |

Notes:
- Modal's free monthly credit (about $30, PLAN.md "GPU provider") may cover most of the GPU part, but plan as if
  it didn't.
- Every paid run is shown to the owner with its own cap first.
- If colour transfer for the versions fails at night (item 4 risks), a night-only GPU repair is one more request,
  about $5.

---

## 6. Calendar (from Saturday 7 Nov 2026)

| When | Stream A | Stream B | Stream C |
|---|---|---|---|
| 7 to 8 Nov | M0 set-up (shared, half a day) | | |
| 9 to 11 Nov | A0 draw once, A1 lamps | B1 halo composite (current art) | C1 harness and baseline |
| **M1, 11 Nov** | merge | merge | merge |
| 12 to 18 Nov | A2 placement, A3 map matching | B1 rerun on new winter art, B2 rides (paid run, approval) | C2 perf fixes, `frame.ts`, `weather.ts` API |
| **M2, 18 Nov** | merge | merge: Christmas ready to check before **20 Nov** | merge |
| 19 Nov to 2 Dec | A4 trains under bridges and in tunnels, A5 emergency | B3 painted cars (pilot, gate, run) | C3 weather and fog |
| **M3, about 2 Dec** | merge | merge | merge |
| 3 to 16 Dec | A6 perf part 2 | B4 Pfaffenthal lift, B5 framework and New Year's Eve | C4 planes |
| **M4, about 16 Dec** | merge | merge (New Year's Eve ready by 31 Dec) | merge |
| From January | upkeep | the other events, in the order of the table | adaptive quality tuning, optional live flights |
