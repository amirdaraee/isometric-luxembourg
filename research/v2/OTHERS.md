# How other illustrated city maps were made

Research for Isometric Luxembourg v2, written 9 November 2026. It covers what other people built, how they built it,
how good it got, and what v2 should copy or avoid. It goes with `DECISIONS.md` (the owner's brief) and `V1_RETRO.md`
(what went wrong in v1).

**How to read the claims.** Each fact links to its source. Where I conclude something the source does not say, it is
marked **(inferred)**. "Not stated" means I looked in the primary source and the point is not there. Sources are
listed at the end, and the short labels used in the text are defined there ([NYC-W], [SG], and so on).

---

## 1. Summary

1. **Nearly every AI map since January 2026 uses one recipe.** Render Google Photorealistic 3D Tiles with one
   orthographic camera. Have a strong closed model (Nano Banana / Gemini 3 Pro Image) restyle a few dozen to a few
   thousand frames: this is the "teacher". Train a LoRA on Qwen-Image-Edit or Qwen-Image-2.1-Turbo: this is the
   "student". Paint the whole city with the student. Serve the result as a Deep Zoom pyramid in OpenSeadragon.
   Projects using it: [NYC-W], [LON], [SG], [SF], [ISO], [BER].
2. **Seams are solved.** Denoising the whole canvas as one latent (MultiDiffusion with shifted windows), and pinning
   finished neighbours the RePaint way, removes seams by construction: [LON], [SG], [BER]. v1 already does this.
3. **None of the AI maps solved light, straight lines, or matching the data.** Every one of them bakes in the
   shadows of its 3D-tiles input. Roads, water and trees are whatever the model painted. Their fixes come afterwards:
   OSM checks for water, repainting patches, and fitting vehicles to the painted asphalt.
4. **The only projects whose art matches the data exactly are drawn in code** (three.js or canvas, from OSM, LiDAR
   and LoD2 data): Isometric Warsaw [WAW], Isometric Paris/Rome [IC-P], Pixel Sydney [SYD]. They get real sun,
   seasons, night, trams on real tracks and no seams. The price is a "game city" look that is far less rich than
   the painted maps (see [TOR] §6 for a direct comparison).
5. **Tiny Toronto is the closest to our v2 thinking:** "the painting is a skin over the data" [TOR]. Its lessons
   come from failures and are concrete. The input decides accuracy, not the prompt. Grade the look in code after
   painting. When the model invents something, fix it in code. Never ask a model to continue its own painting.
   Hover uses an id-map tile pyramid.
6. **For v2, take the mix.** Use code where the data is the truth: ground, roads, rails, water, shadows, lights,
   vehicles and labels. Use AI only for material and texture inside geometry it cannot move: buildings, roofs, tree
   crowns, cliffs. Run one shared grade-and-ink pass over the composite, so code layers and painted layers read as
   one drawing.

---

## 2. What v1 did (for comparison)

From `README.md`, `LAYERS_POC.md` and `V1_RETRO.md` in this repo:

- **Input:** our own render of textured ACT CityGML LoD2.2 on LiDAR terrain, draped with the 2023 orthophoto, plus
  OSM-based layout and line guides.
- **Painter:** Qwen-Image-Edit-2511 with our own style LoRA (trained with ai-toolkit on OpenAI-drawn targets),
  Lightning in 8 steps, whole-canvas shifted-window painting (`mdpaint`). Night and seasons come from a second
  "light" LoRA that repaints the day. The viewer is OpenSeadragon.
- **Known problems:** the ones listed in the brief (P1 to P6 in `V1_RETRO.md`).
- **The layered POC (`LAYERS_POC.md`, 7 Nov) already tried code ink lines, cut-out buildings and per-tree canopy.**
  The owner's verdict: buildings and exact roads good; trees like cardboard, cliffs flat, greenery missing.

v1 is in the same family as the maps below. It is not behind them: it already has whole-canvas painting, OSM water
and data-driven traffic. Its weak points are the same ones every AI map has.

---

## 3. The projects

### 3.1 isometric.nyc (Andy Coenen, January 2026)

| | |
|---|---|
| URL | https://isometric.nyc · code https://github.com/cannoneyed/isometric-nyc (MIT) · write-up [NYC-W] |
| Area / size | NYC (Staten Island left out [HN-NYC]); about 32k generated 512 px "quadrants" [NYC-DATA]; the write-up estimated 40k tiles [NYC-W] |
| Input | Started from CityGML "whitebox" renders over satellite imagery. The two didn't match, so he switched to Google 3D Tiles rendered with an orthographic camera in the browser [NYC-W] |
| Camera | Tilted 45°, turned 15° (stated by [LON], which copied it) |
| Model | Nano Banana made the targets; on its own it was consistent "at best" 50/50 [NYC-W]. Production used a Qwen-Image-Edit LoRA trained on oxen.ai on about 40 pairs, about 4 h and about $12 [NYC-W]. Inference on rented H100s, under $3/h, more than 200 generations/h [NYC-W]. Served with true_cfg 2.0, 14 steps [NYC-INF] |
| Tiling / seams | One call paints a 2×2 block of quadrants (1024 px). The model is trained for "omni infill": part of the frame is already-painted pixels and the rest is the raw render inside a red outline. Rules forbid painting anything that would create a seam. Planning tools for strips and rectangles set the order [NYC-W], [NYC-GEN]. Prompt: "Fill in the outlined section with the missing pixels corresponding to the <isometric nyc pixel art> style…" [NYC-INF] |
| Layers | One painted image. Night ("dark mode") and snow are separate whole-tile repaints by Gemini 3 Pro Image (`generate_dark_mode.py`, `generate_layer_snow.py`) [NYC-REPO]. Whether they shipped on the live site is not stated in the write-up; a snow version was covered in the press in February [GMM-SNOW] |
| Shadows | Baked; whatever the 3D tiles carry (inferred: not discussed in [NYC-W]) |
| Water / trees | The hardest parts: "the model could NOT learn how to reliably generate trees or water no matter how much data" [HN-NYC]. Fixed with a water classifier, a colour-picker water fix, "fill water", and hand edits in Affinity [NYC-W]. The water shader was dropped because the shore-distance masks couldn't be made reliably [HN-NYC], [NYC-WATER] |
| Vehicles / animation | None |
| Post-processing | The repo has an `unfake` pixel-art cleanup with grid snap and a single fixed palette for the whole city [NYC-PP]. Whether it was used on the live tiles is not stated |
| Viewer | React + OpenSeadragon; tiles on Cloudflare R2; DZI and PMTiles exporters [NYC-REPO] |
| Effort | "Well over 200 hours", mostly manual auditing of the generations [HN-NYC] |
| Complaints | "Not pixel art", "incoherent slop when you examine it closely" [HN-NYC]; mistakes between water and concrete [HN-NYC]; the author: "once you see the AI it's hard to unsee" [HN-NYC]. No model, not even the largest, could judge seams or bad trees, so QA stayed manual [NYC-W] |

**Copy:** a single camera for everything; infill-trained LoRA; small training sets are enough to fix a style.
**Avoid:** tile-by-tile painting with hand-driven QA; relying on the model for water and trees.

### 3.2 Pixel Singapore (Yadong Xie, published 7 November 2026)

| | |
|---|---|
| URL | https://www.yadongxie.com/lab/singapore (listed in [IC]) · write-up [SG] |
| Area / size | About 8 × 6 km of the Central Area; 31,744 × 16,384 px (about 520 MP); 0.25 m/px [SG] |
| Input | Google 3D Tiles via Cesium ion, rendered with three.js in a headless browser. Orthographic camera, turned 15° west of north and tilted 45°. A grid of 2048 px shots (512 m) that line up exactly. A **height pass** stores surface height in cm in the R and G channels [SG] |
| Model | Qwen-Image-2.1-Turbo with a style LoRA, conditioned on the render. Prompt: "Redraw this aerial view as detailed isometric pixel art." How the LoRA was trained is not stated [SG] |
| Painting | MultiDiffusion with one latent for the whole canvas. Windows of 1024 px on a 768 px stride; every other step uses a grid shifted by 384 px; flat-topped weights over the middle 512 px; 8 steps. Five blocks of 16,384 × 10,240 px with 1,024 px overlaps. Each new block is seeded from finished neighbours with RePaint (known pixels re-noised to each step's level, a 64 px free band, feathered back in) [SG] |
| Compute | One RTX 5080. About 104 min per block (20 min conditioning, 67 min sampling, 17 min decoding); 14.84 GB peak VRAM [SG] |
| Layers | One painted base. Animation is added on top from the **height pass and masks**, not from separate art layers [SG] |
| Occlusion | **Foreground layer:** the map's own pixels are copied into a layer drawn *above* vehicles wherever the height pass shows a surface higher than the vehicle's side (4.4 m for a double-decker). Green pixels near roads are added to cover invented tree crowns. Stored as lossless WebP [SG] |
| Bridges / viaducts | Cars shook because height samples jumped between surfaces. Fix: **one lowest-cost height profile per road**, from −8 to 70 m in 0.5 m steps, slope capped at 1 in 8 [SG] |
| Vehicles | About 14,000 OSM road edges sampled every 4 m, with lanes placed "on the asphalt found in the render" (OSM can be metres off) [SG]. How the asphalt is detected is not stated. Intelligent Driver Model, two-phase lights on a 70 s cycle, junction boxes, deadlock removal. Sprites from 3D boxes at 32 headings, "lit with the same sun" [SG] |
| Trees / water | A transparent WebGL2 canvas moves the map's *own* pixels through masks. Canopy = green pixels 2.5 to 45 m above ground, split into crowns by watershed; crowns near buildings stay still. Water = flat (within 0.4 m over 10 m) and teal/blue, with patches recoloured six times a second from a swell pattern [SG] |
| Shadows / time of day / labels | Not stated; shadows are baked from the photogrammetry (inferred) |
| Viewer | OpenSeadragon, a sparse DZI of 512 px WebP tiles at q60 (189 MB; 321 MB with the animation data). Crisp pixels above 1.25× zoom. Versioned URLs cached for a year. Animated layers wait for the sharp base tile. Tilt-shift with stacked `backdrop-filter` [SG] |
| Known problems | Mosaic artefacts (wedges in the sea, hazy rectangles), partly fixed by repainting a patch with everything else pinned. Outdated source data [SG] |

**Copy:** height pass + foreground layer for occlusion; one height profile per road for viaducts; animate the map's
own pixels through masks rather than overlaying sprites.
**Avoid:** fitting the simulation to whatever the model painted (v1 did the same with `fit_roads.py`; v2's brief
wants the art to match the data instead).

### 3.3 tiny.london (Boris Starkov, launched 13 October 2026)

The most rigorous write-up. It is the reference for whole-canvas painting at scale.

| | |
|---|---|
| URL | https://tiny.london · write-up [LON] (plain text: https://tiny.london/llms-full.txt) |
| Area / size | Greater London, 1,591 km². Canvas 221,184 × 135,168 px (29.9 GP), of which about 14.2 GP is London; 0.293 m/px; a terraced house is about 17 px wide [LON] |
| Input | Andy's three.js renderer of Google 3D Tiles, driven by Playwright. **One camera** at 51.507 N, 0.106 W for all 3,570 shots of 2048 px; the frustum is shifted by whole steps; a 45-shot mosaic matched one big render in 99.7% of pixels. Projection: WGS84 → ECEF → ENU → isometric view (a flat approximation is off by 50 to 70 px at the edge) [LON] |
| Teacher | Gemini 3 Pro Image made 7,277 calls. Automatic checks against the render (structure) and OSM (water) rejected 31% of attempts. One check catches "photo copies": the share of pixels whose 3×3 neighbourhood is flat (good redraws 0.42 to 0.55, half-copies 0.18 to 0.35) [LON] |
| Coverage | 12,264 frames embedded with DINOv2 and clustered into 64 "look groups", sampled by the square root of group size. Plus 230 hard places from OSM, 56 water frames and 95 landmarks with zoomed quarters ("on a quarter of a dense frame, the teacher redraws instead of copying") [LON] |
| Prompt lesson | "Prompts that describe content get content." A prompt that named London materials invented towns on farmland and roads through parks. The final prompt says *how* to draw: "FIDELITY COMES FIRST… Add nothing that is not in the render…". Each frame also gets one OSM sentence about its water ("WATER IN THIS VIEW: none…"), which stopped pitches being painted as ponds [LON] |
| Student | LoRA rank 32 on int8 Qwen-Image-2.1-Turbo with ai-toolkit: 6,326 examples, 8,000 steps, lr 1e-4, 3 h 50 min on one H100. Input = the render with a 2 px red outline and Andy's infill prompt [LON]. Four versions; Turbo cut a central-London run from 110 to 27 min [LON] |
| Painting | Joint MultiDiffusion as in Singapore (1024 windows, 768 stride, second grid shifted 384, tent weights), with RePaint pinning. Blocks of 12,288 px read a 1,024 px pinned margin of their neighbours and run in four parity phases. 125 blocks, 31 GPU-hours. About 70 H100-hours across all experiments. Every stage resumable, with a latent checkpoint after every step [LON] |
| Seam metric | Ratio of the colour jump across tile borders to the jump everywhere else: pilot 0.93, render 1.0 [LON]. In the August tile-by-tile attempt, a third of boundaries had seams, and hand-written seam metrics agreed with graders at only r = 0.09 to 0.21 [LON] |
| Errors | Water: the LoRA drew a second Tower Bridge and a second Parliament in empty Thames. Found by OSM water polygons (reservoirs raised by their shore height, 2.4 px per metre) where the render is flat and empty but the map is not. Repaired with no model: mask, fill with nearby water texture, **Poisson solve** so the patch meets the map with no seam [LON] |
| Block-edge bug | A 6 to 10 px dark stripe where the VAE decoder leaves a rim on an un-overlapped canvas edge. Fixed with a per-offset tone ramp; the main run had avoided it by redrawing a strip of each neighbour [LON] |
| Vehicles | None: "the later style drops all vehicles" [LON] |
| Shadows / night / seasons | Baked shadows from the 3D tiles (inferred); no night or seasons |
| Clouds | Drawn by Gemini with a map tile as the style reference, cut into single clouds, stored as **distance fields** so their edges stay sharp at any zoom. A harmonic field keeps every cloud pixel outside London. "Next to a hand-drawn map, clouds made from procedural noise read as marble or camouflage" [LON] |
| Labels | None in the art. Search covers 3,180 OSM places plus TfL stations and postcodes, using the generator's own projection; fare-zone and borough overlays [LON] |
| Viewer | React + OpenSeadragon, DZI of 512 px WebP on Cloudflare R2, 10 levels; immutable versioned folders; patch layers holding only changed tiles. First view in 0.3 s: 16 tile requests per frame, tile list worked out by an inline script, only the sharpest level loaded. Two coarser levels kept loaded to avoid blocks on zoom-out. Nearest-neighbour above 1:1, smooth below [LON] |
| Timeline | Tile-by-tile attempt 22–23 August, then stopped. Restart 8 October; live 13 October; clouds 15 October [LON] |

**Copy:** "describe how to draw, not what"; OSM truth sentences in prompts; automatic target checks against ground
truth; DINOv2 coverage sampling; Poisson repairs; distance-field clouds; immutable versioned tiles; the
first-view loading tricks.
**Avoid:** trusting vision-model judges ("the weakest link" [LON]); decoding a block's edge with no overlap.

### 3.4 isometricsf.com (Justin Chavez, write-up 4 November 2026)

The owner calls this the quality v1 aimed for.

| | |
|---|---|
| URL | https://isometricsf.com · write-up [SF] (the author calls it a preview; a fuller technical write-up "with code fixes, evals, color corrections, and seam handling" is promised). Earlier demo: "North Beach Isometric", September 2026 [IC] |
| Area | "The Bay Area in pixel art" [SF-SITE]; the area and pixel size are not stated |
| Data | Google Photorealistic 3D Tiles, OSM, ESA WorldCover 2021 land cover, Copernicus WorldDEM-30 elevation, Wikivoyage place names [SF-SITE] |
| Teacher | 45 Google renders restyled by Nano Banana 2. Each target used in 5 fill-in examples, giving 225 [SF] |
| Model | **Qwen-Image-Edit-2511 + LoRA** (the same base as ours) on those 225 examples, with Lightning at 4 steps. Then a **second distillation**: Qwen painted 1,460 places, which trained **FLUX.2 Klein 4B** ("a fifth its size", nearly 4× faster) on 4,380 examples with 3 colour variants each. Klein made about 177,000 paintings [SF] |
| Stitching | "Only the center of each painting is kept, and it fades into its neighbor across a thin band" (the "hem"); then a colour correction evens each painting against its neighbours [SF]. So: per-tile painting with overlap and colour matching, not joint denoising |
| Compute / cost | About 172 H100-hours on Modal, about 119 of them for the map; LoRA training under 6 h over four versions. Three H100s went from 29 to about 68 images/min at 1536 px with `.spawn()` queues. A guard script stopped the app at a set dollar amount. Painting the whole Bay with Nano Banana 2 would have cost about $7,000 [SF] |
| Edge cases mentioned | "A bridge being drawn as water" [SF] |
| Layers / shadows / vehicles / night / labels / viewer | Not stated in the preview |

**Copy:** the two-stage distillation (big LoRA, then a small fast student) if the area grows; a hard dollar guard on
GPU apps (it matches our approval rule).
**Unknown:** how it reaches its quality. The written evidence suggests mostly data volume (about 177k paintings at
1536 px) and many evaluation rounds, not a different architecture (inferred).

### 3.5 Isopolis San Francisco (Vivek Aithal, August 2026)

| | |
|---|---|
| URL | https://sf.isopolis.city · write-up [ISO] · Show HN [HN-ISO] |
| Area / size | About 121 km², about 22 GP [ISO] |
| Input | Google 3D Tiles, three.js, Playwright worker pool; 440 blocks of 1024². Camera azimuth 22.5°, elevation 30°. "The tile textures already have baked lighting", so no relighting [ISO] |
| Training | Nano Banana targets with 8 frozen style references; 101 approved pairs; each split into 4 quadrants × 15 context masks, giving 1,515 samples. Qwen-Image-Edit-2511 LoRA rank 16, 2,000 steps, about $10–15 per run; the 100-pair run beat the 60-pair run [ISO] |
| Painting | Sliding 1024² window, half a frame at a time, grown by a greedy seam planner; true CFG 4.0, 24 steps. A guard rejects a generation that differs too much from a baseline run [ISO] |
| Water | Detected mask → flat water colour; mostly-ocean windows are skipped and stamped [ISO] |
| Viewer | Custom canvas engine ("Mercator libraries cannot index this dimetric frame"), CARTO tiles warped underneath at 45% alpha, GeoJSON annotations, S3 + CloudFront [ISO] |
| Complaints | "Soulless, blurry, not pixel art"; roads turned into lakes; square ponds; houses invented on Alcatraz; flat terrain despite SF's hills; no street names or transit [HN-ISO]. Known residual seams, palette drift, Golden Gate Bridge out of distribution (about half rebuilt with Nano Banana) [ISO] |

**Lesson:** sliding-window painting without joint denoising still leaves seams and palette drift. Landmarks outside
the training distribution need their own handling.

### 3.6 Tiny Toronto (Ahmed Nadar, write-up 2 November 2026)

The project most like our v2 plan, and the most useful set of failures.

| | |
|---|---|
| URL | https://tinytoronto.ca · write-up [TOR] |
| Idea | "The painting sits on top of a 3D model of the real city": hover a building and it names it [TOR] |
| Area / size | The core is 1.57 × 1.16 km (840 buildings, 90 views), plus the east side, the north and Shops at Don Mills; the joined sheet is 30,730 × 22,166 px; renders at 0.125 to 0.37 m/px [TOR] |
| Data | OSM shapes; Ontario 2023 LiDAR for heights (OSM was off by more than 5 m on 21 of 51 buildings); the City's lots, addresses and 3D Massing [TOR] |
| Experiments on own data (v1–v11) | (1) Plain box render → the model invented NYC water tanks and turned glass to brick. (2) Material-coloured render with a colour legend → better, but the model filled empty ground with an invented neighbourhood; fixed by a **geometry mask** (keep paint only where real geometry is). (3) **AI-painted texture kit** (7 tiling textures) wrapped on the data live in the browser, with lane dashes from OSM lane counts, crossings and tree points → exact and sharp at any zoom, but "it looked like a new game city". (4) Orthophoto draped on roofs and ground → real roof gardens and markings, but walls were guesses. Verdict: **"The input decides accuracy, not the prompt"** [TOR] |
| Final input | A photo-real 3D tile view rendered under their own camera in their own local metres; the ground fitted to 177 road points; zero px offset at 0.37 m/px, 4–5 px at 0.25 m/px [TOR] |
| Painting | A closed "main model" through a Batch API (not named), one view at a time, 2K–4K. **Seams:** "Asking the model to continue a painted part does not work" (mean gap 27.9). Instead each view is painted alone and **the overlap is cut along streets and open ground, avoiding buildings**, with a 3 px feather (later 12 px); the cut crosses buildings on 6% of columns. Finally a smooth vertical warp fitted in the overlaps aligns neighbours to about 0 px [TOR] |
| Prompt "px-2" | "Redraw this render as detailed isometric pixel art… Draw exactly what the render shows… flat fills of solid colour… A crisp dark outline one or two pixels wide around every roof and wall edge… Road surfaces are drawn dark grey with crisp white painted markings" [TOR] |
| Patch tool | Repaint one building at 2.5–4× detail and paste it back inside its exact outline (left a faint halo on the cathedral spire) [TOR] |
| Student test | LoRA on an open edit model, 71 pairs at 1024 × 683, 1,000 steps: kept the geometry, but came out paler and softer, lost tree crowns and roof shadows, added green patches. "Parked" [TOR] |
| Grade in code | "Grade B": saturation ×0.78, contrast ×1.2, gamma 1.2, dark surfaces sink further, **strong edges 35% darker so they read as ink**. Same on every pixel of every view; adjustable without repainting; not applied to night [TOR] |
| Vehicles | A model asked to draw all vehicles invented a red streetcar on tracks that don't exist: "painted vehicles only where the photo has them, and real streetcars come later from live data, not from paint" [TOR]. The site ships car sprites with day and night variants and transit path files (seen in the site's asset manifest, `life_car_*`, `ttc_paths`) |
| Night | A shader that found and lit windows in the day painting found about half of them and hit roofs a fifth of the time: kept only as dusk. **Real night = a repaint** with a "how to draw" prompt; 91.2% of night edges within 2 px of day edges. The model kept putting towns on the lake at night, so water was recoloured from the day water with a fitted colour map [TOR] |
| Ink from data | "I tried drawing ink outlines from the id map first. They did not sit on the painted edges… the lines looked like a mistake" [TOR] |
| Hover / labels | **Id tiles:** every pixel carries a 24-bit building id in RGB, rendered from the same camera into the same pyramid; lossless, nearest-neighbour downsampling. The core's id pyramid is 2.4 MB; the page fell from 10.22 MB / 113 MB JS memory to 3.12 MB / 7.3 MB. The highlight runs in the tile shader (×1.2 brightness, ×1.5 saturation, pale rim) [TOR] |
| Viewer | three.js + 3d-tiles-renderer; its own DZI-like pyramid, WebP q90; zoom capped at 1.3 screen px per painted px; **draws only when a state key changes** (idle draw calls in 3 s went from 2,700 to 30); weather on a separate 2D canvas so it never wakes the map renderer [TOR] |

**Copy:** id tiles; the code grade with ink edges; draw-on-change; the geometry mask that throws away invented
paint; data-first hover; no painted vehicles.
**Avoid:** painting views separately and stitching them (fine for them, but our joint painter is better); ink lines
drawn from data on top of paint that doesn't share that geometry.

### 3.7 Pixel Berlin (Rupert Hoffschmidt-McDonnell)

| | |
|---|---|
| URL | https://pixelberlin.com · write-up [BER] |
| Area / size | 891 km²; each picture covers 300 m; about 0.30 m/px [BER] |
| Method | Google 3D Tiles, 45° / 15° camera. Qwen-Image-Edit LoRA trained on fal.ai on pairs of renders and "gray hand-drawn versions", plus a 4-step speed adapter. 76 blocks of 12 × 12 tiles, each painted as one image in overlapping 1024 windows; four checkerboard rounds, finished edges pinned [BER] |
| Fixes | The style model drained colour from trees and meadows, so a colour step brings back a soft green and a final grade warms the greys. Lakes got invented buildings or horizons, so an automatic second pass detects and repaints them. Blurry renders (a coarse LOD left in the browser) are detected by measuring fine detail and re-rendered [BER] |
| Labels | None in the drawing; browser search over 375,519 addresses [BER] |
| Viewer | OpenSeadragon, about 10,000 tiles [BER] |
| Cost / time | About 50 A100-hours on Vast.ai (about $58) plus about $40 on fal.ai: **about $100 in total**; the city painted in under a day [BER] |

**Lesson:** a whole city at good quality fits in about $100 when the pipeline is joint painting with Turbo/Lightning
steps. Colour restoration and grading in code are part of the pipeline, not an afterthought.

### 3.8 Isometric Warsaw (Bedirhan Yildirim, October 2026): drawn entirely in code

| | |
|---|---|
| URL | https://bedirhanyildirim.com/warsaw-izo/ · write-up [WAW] |
| Area | 517 km² in 659 squares of 1 km, loaded as they come into view; 197,000 buildings, 1.9 million trees, 46,873 street lamps [WAW] |
| Method | A three.js scene rendered at half resolution, with a limited palette, dark outlines where depth jumps, and pixels snapped to a grid. **No image AI, no tiles, no seams**; "water sits where the data places it" [WAW] |
| Data | OSM; GUGiK LoD2 buildings with roof shapes (131,686); 1 m LiDAR terrain; the **orthophoto used only to sample roof colours**; GUGiK 3D tree models; GTFS timetables; Open-Meteo [WAW] |
| Life | Trams and trains on real routes and timetables; about 370 flights a day on the runway the day's wind picks; cars left out on purpose (barely visible at this scale, and slow) [WAW] |
| Time / season | A date/time picker drives the **real sun position**, seasons (leaves, snow, frozen ponds) and events; night lights lamps, windows and aviation lights; the Vistula's level follows the date [WAW] |
| Landmarks | About 240 hand-built from Wikimedia Commons photos [WAW] |
| Fixes after feedback | Churches looked like office towers, so more than 380 got brick or stone walls, arched windows and bell towers. Car parks got open decks. A building-assembly rule had hidden 34 large buildings. Demolished halls from outdated 3D data were filtered against the official register [WAW] |
| Performance | Centre load from 7.6 s to about 1.8 s; a compact binary format, Brotli, and one throttled render loop that runs only while content is visible [WAW] |
| Cost / time | Free; the first version in about two days; 258 commits in the first week [WAW] |

**Lesson:** everything the owner's brief asks for (moving shadows, straight lines, exact roads, tunnels, no baked
cars, seasons) is easy in code. What code alone does not give is the rich hand-drawn look. Warsaw's per-type
building rules (churches, car parks) show how much hand work a code look needs.

### 3.9 Other code-drawn ("open data" / "3D diorama") maps

- **Isometric Paris / Rome / Vienna / Barcelona / Singapore** (isometriccities.com): drawn from OSM footprints,
  with about two in three buildings at their mapped height and the rest given an estimated 4–7 floors. The Eiffel
  Tower was "modelled by hand from its published dimensions" [IC-P].
- **Pixel Sydney** and its siblings (Grigory Frolov): "a hand-built canvas engine"; OSM footprints extruded to
  their storeys; streets "with real lane markings"; windows light up after the real sunset [SYD].
- **tiny.paris** (woza.ink): OSM + IGN BD TOPO data with **Kenney** low-poly models, toggles for buses, Vélib' and
  garbage trucks, and a "Painted" vs "Whole map" switch [TPAR]. So it is a hybrid with some painted part; how it
  works is not stated.
- **nyc.infinite.games** ("all five boroughs, drawn in code"; NYC Open Data + 2017 LiDAR + OSM) [NYCIG];
  **tiny.brussels** (an EU-quarter diorama with live time and weather, a labels toggle and 45° rotation) [BRU].
  Neither says how it was made.
- Directory of 82 such maps, tagged AI-drawn / open data / 3D diorama: [IC]. About two thirds are AI-drawn
  (inferred from the counts in the list).

### 3.10 Hand-drawn and professional cartography (for the look, not the pipeline)

- **Hand-drawn illustrated maps** take months per city: "a few months from the first strokes to the complete map"
  [NJ]. Jenni Sparks' hand-drawn London is one known example [JS]. Rod Hunt makes detailed isometric city
  illustrations [RH]. Isometric Tokyo illustration work exists (e.g. city-isometric.jp, named in search results),
  but I found no published workflow. These maps generalise freely: they enlarge landmarks, drop clutter and
  simplify blocks. That is the opposite of "match the data exactly", so v2 has to choose where to sit (see §7).
- **Apple Maps** replaced 213 landmark models with new artist-made ones in its 2021 redesign. The surrounding city
  is drawn as simpler 3D, with "climate-appropriate trees", road markings and walkways from data [APL]. The same
  split again: hand-made heroes, code-drawn context.
- **Swiss relief shading:** U-Net networks trained on swisstopo's manual relief shadings reproduce hand-drawn
  shading from a DEM in seconds. They learn to drop unneeded detail and to adjust the light locally to bring out
  landforms. 18 experts rated the results highly [JEN]. A commercial tool, **Eduard**, came out of this work
  [JEN-2]. Relevant to our cliffs and gorges layer (L2): the shading can be computed from LiDAR in a hand-drawn
  style, with no image model, and moved with the sun (inferred).
- **Not found:** "Jan Rieckhoff" gave no results under any query I tried (English or German). I did not research
  Cities: Skylines-style renders separately; the 3D-diorama maps above cover that approach.

---

## 4. Comparison table

| Project | Area / pixels | m/px | Input | Painter | Whole-canvas? | Layers | Shadows | Vehicles | Night / seasons | Viewer | Cost / effort |
|---|---|---|---|---|---|---|---|---|---|---|---|
| isometric.nyc [NYC-W] | NYC, ~32k × 512² | not stated | Google 3D Tiles | Qwen-Image-Edit LoRA (40 pairs) | No: 2×2 infill tiles | No (night/snow repaints in repo) | Baked | None | Repaints by Gemini (repo) | OSD | ~$12 training; 200+ h of human time |
| Pixel Singapore [SG] | 8×6 km, 520 MP | 0.25 | Google 3D Tiles + height pass | Qwen-Image-2.1-Turbo LoRA | Yes: MultiDiffusion + RePaint | Base + foreground + motion masks | Baked | Code sim, foreground occlusion | Not stated | OSD | One RTX 5080, ~9 h |
| tiny.london [LON] | 1,591 km², 29.9 GP | 0.293 | Google 3D Tiles, one camera | Gemini teacher → Turbo LoRA | Yes: same | Base + clouds + overlays | Baked | None | No | OSD, R2 | ~70 H100-h; 5 days |
| isometricsf.com [SF] | Bay Area | not stated | Google 3D Tiles (+DEM, land cover) | NB2 → Qwen-Edit-2511 LoRA → FLUX.2 Klein 4B | No: tiles + "hem" + colour match | Not stated | Baked (inferred) | Not stated | Not stated | Not stated | ~172 H100-h |
| Isopolis [ISO] | 121 km², 22 GP | not stated | Google 3D Tiles | Qwen-Edit-2511 LoRA (101 pairs) | No: sliding window | Water stamps | Baked (stated) | Banner planes (HN comments) | No | Custom canvas | ~$30 |
| Tiny Toronto [TOR] | ~3 km² + island, 30k×22k | 0.125–0.37 | Photo-real 3D tiles in own camera | Closed model, per view | No: per view, cut along streets | Paint + id map + weather | Baked ("hard shadows" kept) | Sprites from data | Night repaint + code dusk | three.js | Batch API; not stated |
| Pixel Berlin [BER] | 891 km² | ~0.30 | Google 3D Tiles | Qwen-Edit LoRA + 4-step | Yes: blocks + pinned edges | No | Baked (inferred) | No | No | OSD | ~$100 |
| Isometric Warsaw [WAW] | 517 km² | n/a (live 3D) | LoD2, LiDAR, OSM, ortho colours | None (three.js) | n/a | Fully live | **Real sun** | Trams, trains, planes | **Real** sun, seasons, night | three.js | Free; days |
| v1 Luxembourg (repo) | pilot area | 0.25 | ACT LoD2.2 textured + ortho | Qwen-Edit-2511 LoRA, Lightning | Yes | Base + night/season repaints | Baked | Code sim fitted to paint | Repaints (light LoRA) | OSD | Day about $15; night/seasons cap $60 (ROADMAP.md) |

OSD = OpenSeadragon. Cost for Isopolis = two training runs at $10–15 plus about $4 of images.

---

## 5. Patterns worth knowing

1. **Google 3D Tiles is the common input, and it is why every AI map bakes in shadows and photo noise.** Isopolis
   says so directly [ISO]. Tiny Toronto found that boxes and orthophotos give guessed walls [TOR]. Luxembourg has
   something most cities lack: an open, textured LoD2.2 city model (ACT, CC0). We can render it *without* its photo
   textures (albedo or material colour only), so we control the light. Nobody else could do that (inferred).
2. **Teacher → student is standard** [LON], [SF], [NYC-W], [ISO], [BER]. The teacher's frame-to-frame
   inconsistency doesn't matter, because every training pair stands alone [LON].
3. **Prompt fidelity rules** ("add nothing, remove nothing; little detail means plain drawing") cut down invention
   [LON], [TOR]. They don't stop it on empty water: both London and Toronto still got invented towns and needed code
   fixes [LON], [TOR].
4. **Ground-truth checks beat model judges** [LON], [NYC-W], [HN-NYC]. Every successful QA step compared against the
   render or against OSM.
5. **The look comes partly from code.** Berlin restores green and warms the greys [BER]. Toronto's Grade B adds the
   ink [TOR]. NYC has a fixed city-wide palette [NYC-PP]. London's clouds are model-drawn but code-placed [LON].
6. **Night by code didn't work (Toronto); night by repaint did** [TOR]. Warsaw's night is real because the whole
   scene is code [WAW].
7. **Nobody published a layered AI map with code-drawn roads under painted buildings.** Singapore comes closest
   from the other side: one painting, but with code-derived height and foreground layers [SG]. Toronto tried code
   ink over paint and dropped it because the edges didn't line up [TOR]. Our POC is ahead of the field here, and
   so are its risks.

---

## 6. Techniques ranked against our v1 problems

Higher in each list = more likely to fix the problem, given what others reported. ★ = proven by a source; ☆ =
plausible but untested by anyone cited (inferred).

### P1. Shadows baked into the paintings
1. ★ **Light computed from 3D data at run time** [WAW]: a real sun, shadows and night. For us: a shadow map from the
   LoD2 model + LiDAR + tree crowns, as a separate layer (already the v2 decision).
2. ☆ **Paint from an unlit input:** render the LoD2 model with flat material colours or delit textures and ambient
   light only, and train the LoRA on unshadowed pairs. Do not drape the orthophoto (its shadows get copied; see
   `V1_RETRO.md` P1). Toronto's material-coloured render is the nearest precedent, and it held the shapes [TOR].
3. ☆ **A normal / shading buffer from the 3D model** to darken walls by sun angle, so walls darken at evening (the
   POC's gap: "the painted buildings still carry their own painted light").
4. ★ Night as a repaint of the day art with a "how to draw" prompt [TOR]. Keep it for lit windows, but on unshadowed
   art.

### P2. Wobbly windows and straight lines
1. ☆ **Paint facades rectified, then project them in code.** Paint each facade (or facade strip) front-on at a high
   resolution (0.05–0.1 m/px), then map it onto its 3D face. In an orthographic view a flat facade maps affinely, so
   every straight line in the painting stays straight on the map. This is the only option where straightness is
   guaranteed by construction rather than hoped for. Toronto's texture kit shows the risk: generic tiling textures
   look like a game [TOR]. The fix would be one painting *per facade*, from that facade's own photo or geometry,
   not a shared kit (inferred).
2. ★ **Paint at higher resolution per building** [TOR] (patch tool at 2.5–4×), and keep geometry inside the exact
   outline. `V1_RETRO.md` P2 sets the target: the smallest straight thing must cover at least two latent cells.
3. ☆ **Snap after painting:** a grid snap like the `unfake` cleanup in the NYC repo [NYC-PP], or a warp that pulls
   strong painted edges onto the projected 3D edges, scored by the line test in `V1_RETRO.md`.
4. ★ **Draw windows in code** [WAW], [SYD]: always straight, but it reads as a game (Toronto §6) [TOR].
5. ✗ **Ink lines from the data over paint that doesn't follow the same edges:** tried by Toronto and it "looked
   like a mistake" [TOR]. It only works when the paint was made inside those exact edges.

### P3. Painted roads and rails don't match the data
1. ★ **Draw roads, rails, tram tracks and water in code from the data** [WAW], [SYD] (and our POC v2 ink layer).
2. ★ **OSM truth in the teacher prompt and checks** [LON], so the paint at least doesn't contradict the data.
3. ★ Fit the simulation to the painted asphalt [SG] (v1's approach). It hides the mismatch rather than fixing it,
   so it fails the brief.

### P4. Tunnels and bridges break the vehicles
1. ★ **One height profile per road** (a lowest-cost path through the sampled heights, slope capped) [SG], combined
   with OSM `bridge` / `tunnel` / `layer` tags.
2. ★ **Foreground occlusion from a height pass** [SG]: pixels taller than the vehicle at that point are drawn over
   it.
3. ☆ In a layered map, **per-pixel depth for every layer** (buildings, bridge decks, tree crowns), with vehicles
   depth-tested against it. This generalises Singapore's single foreground layer and handles a car on a bridge with
   a road beneath it (inferred; `LAYERS_POC.md` L5/L7 already plans this).

### P5. Cars painted into the art
1. ★ **Don't give the painter a layer that has roads.** If ground and roads are code, cars cannot appear there
   (inferred, but it follows from the layer split).
2. ★ **Remove vehicles from the inputs and the training targets**; London's style "drops all vehicles" [LON].
   Toronto refused painted vehicles after the model invented a streetcar [TOR].
3. ★ Detect leftovers by comparing against ground truth (London-style "the render is empty here, so the map should
   be too") [LON].

### P6. Visible seams and edges
1. ★ **Joint MultiDiffusion with shifted grids and RePaint pinning** [LON], [SG], [BER]. v1 already has it. Keep it
   for any layer painted as a continuous field (ground texture, canopy, cliffs).
2. ★ **Redraw a strip of each finished neighbour** so no VAE decode edge goes un-overlapped [LON].
3. ★ **Poisson-blended local repairs** [LON].
4. ☆ For per-building painting, seams *between* buildings don't exist, but **style drift between buildings** does.
   Use a shared LoRA, the same seed policy, a style reference, and the global code grade [TOR], [BER].
5. Toronto's cut along streets [TOR] is a fallback when joint painting isn't possible.

### P7. Inconsistent trees and greenery
1. ★ **Canopy from data:** Singapore splits crowns by watershed on a height pass [SG]. Warsaw places 1.9M tree
   models from the national register [WAW]. Our LiDAR gives the same.
2. ☆ **Paint the canopy as one continuous field** (joint painting over the whole canopy mask, crowns depth-tested),
   not as sprites. The owner judged our sprite trees "cardboard" (`LAYERS_POC.md`), and NYC found trees "almost a
   perfect pathological use case" for per-tile models [NYC-W]. POC v2 already does this. Then restore colour in code
   (Berlin had to put green back [BER]).
3. ★ **The flat-share check** catches photo texture left in tree crowns [LON].
4. ★ Sway by moving the map's own pixels through a crown mask [SG], not by animating separate sprites.

### P8. Label clutter
1. ★ **No labels in the art; hover via id tiles** [TOR]. Search instead of always-on labels [LON], [BER].
2. ★ **Toggles for label layers** [BRU]; landmark pins with cards [WAW] (as v1 does).
3. ☆ Priority by zoom, with collision culling on the projected label box (standard cartographic practice, not from
   these sources).

---

## 7. Recommendations for a layered v2

### 7.1 What to draw in code
| Layer | How | Why (source) |
|---|---|---|
| Ground, land cover, pavements, squares | Code fills from OSM + ACT data, in the v1 palette, with paper grain; optionally a low-strength joint paint pass with the edges put back exactly (POC style B) | Exact data, no cars [WAW], `LAYERS_POC.md` |
| Relief, cliffs, slopes | Swiss-style relief shading from LiDAR (neural U-Net or a hand-tuned hillshade with local light adjustment), hatching on steep faces; AI only for rock texture inside the cliff mask | [JEN] |
| Water | Exact OSM polygons; animation by recolouring through masks | [SG], [LON] |
| Roads, rails, tram tracks, markings | Code ink from OSM geometry and widths, lane counts, crossings | [TOR] §6 (exact), [WAW] |
| Shadows and shading | Shadow map + normal buffer from LoD2 + LiDAR + crowns, for the real sun; cast-shadow colour from the palette, not black | [WAW]; brief P1 |
| Night lights | Code lamps from OSM; window glow from a night repaint of the *unshadowed* buildings, masked to wall pixels | [TOR] (code-only night failed), [WAW] |
| Vehicles, trams, trains | Code simulation on the exact data; per-road height profile; depth test against every layer | [SG] |
| Labels, hover | Id tiles (building, street, landmark) from the same camera; search; pins | [TOR], [LON] |
| Clouds and edges | Model-drawn cloud sheets, stored as distance fields | [LON], [TOR] |

### 7.2 What to paint with AI
| Layer | How |
|---|---|
| Buildings and bridges | Input: the LoD2 model rendered **unlit, untextured or delit**, flat material colours, on a flat backdrop colour, at ≤0.125 m/px. Paint with a LoRA trained on unshadowed pairs and a "how to draw" fidelity prompt. Cut out with the geometry mask (POC rule) [TOR]. Optionally put facades on rectified paintings (§6 P2.1) once a pilot proves it |
| Tree canopy | One continuous joint-painted canopy field over a LiDAR crown mask, depth-tested; a colour restoration step; season by repainting this layer only (POC v2) [SG], [BER] |
| Rock / cliff texture | Inside the relief mask only |
| Landmarks out of distribution | Hand-guided or individually painted, like Apple's artist-made heroes [APL] and Isopolis' Golden Gate [ISO] |

### 7.3 Keeping one hand-drawn look across code and AI layers
1. **One palette, defined once,** used by the code layers and given to the teacher as a reference (NYC kept one
   palette for the whole city [NYC-PP]).
2. **Train the style on what the code layers will look like.** Make teacher targets for buildings *on top of* a
   code-drawn ground, so the LoRA learns to match it (inferred).
3. **One final grade in code on the composite,** Toronto's Grade B style: saturation, contrast, gamma, and strong
   edges darkened to read as ink [TOR]. It works the same on code and painted pixels, can be changed without
   repainting, and leaves no tone steps at joins.
4. **The same ink rule everywhere:** an edge-darkening pass on the composite rather than separate ink in each
   layer, so line weight matches across layers (inferred from [TOR]'s failed id-map ink).
5. **Paper grain and a slight edge wobble** on code layers, so they don't look like vectors (`LAYERS_POC.md`
   style A). Keep it small: line wobble is the problem being fixed.
6. **Contact shading** where painted cut-outs meet code ground (ambient occlusion from the 3D model), so buildings
   don't look pasted on (POC risk; inferred).
7. **Check with contact sheets against the render** [LON], [TOR], and with the line score from `V1_RETRO.md`.

### 7.4 Process lessons to adopt
- **Look at every input before painting it.** Toronto painted its blank renders and its own hover outline [TOR].
- **Use ground-truth checks, not model judges** [LON].
- **Make every stage resumable** with a checkpoint each step; make every published tile version immutable, and ship
  patches as layers holding only the changed tiles [LON].
- **Keep the GPU spend capped in code** [SF]; quote each step before running it (our rule).
- **Viewer:** draw only on change [TOR]; a first view under 0.5 s [LON]; nearest-neighbour above 1:1; lossless
  WebP for masks and ids [SG], [TOR]. Several stacked layers means a custom WebGL compositor, or OpenSeadragon's
  WebGL drawer with several tiled sources. Merge layers into one image at far zoom (`LAYERS_POC.md`).

---

## 8. Open questions

1. **Can an unlit or delit LoD2 render give paintings as rich as v1?** Every rich map in this survey painted from
   photo-real input with its light in it. Toronto found that boxes give guessed walls [TOR]. Our CityGML textures
   are photos too, so delighting them (or using material colours only) is untested. **This needs the first pilot.**
2. **Rectified facade painting:** does it keep the inked look and roof-wall continuity, or does it look like Toronto's
   "game city" kit? Needs a pilot on about 10 old-town buildings.
3. **How much does the global grade-and-ink pass hide the difference between code and painted layers?** Nobody has
   published a layered AI map to compare against.
4. **What did isometricsf.com do for quality?** Its full write-up (seams, colour correction, evals) has not been
   published yet [SF]. Re-check later.
5. **Generalisation vs exactness:** hand-drawn maps enlarge landmarks and drop clutter [NJ], [APL]. The brief asks
   for exact data. Do we allow any generalisation (wider streets, simplified courtyards) at far zoom?
6. **Tree canopy:** a joint-painted field (POC v2) or a mix of painted crowns and code shadows? What is the
   acceptance test for "consistent greenery"?
7. **Swiss relief shading:** the neural U-Net [JEN] (are weights available, and under what licence?) or a
   hand-tuned hillshade? Eduard is commercial [JEN-2].
8. **Google 3D Tiles terms:** the AI maps above scrape them, and Isopolis warns this may break Google's terms [ISO].
   v2 uses only ACT and OSM data, so this doesn't touch us, but keep it that way.
9. **Unverified leads:** "Jan Rieckhoff" (not found); isometric Tokyo illustrators' methods (none published);
   tiny.paris' "Painted" mode (how it works is not stated) [TPAR].

---

## Sources

| Label | Source |
|---|---|
| NYC-W | Andy Coenen, "isometric nyc" write-up: https://cannoneyed.com/projects/isometric-nyc |
| NYC-REPO | https://github.com/cannoneyed/isometric-nyc (README; `src/isometric_nyc/generation/generate_dark_mode.py`, `generate_layer_snow.py`, `export_dzi.py`) |
| NYC-DATA | `docs/data.md` and `docs/models.md` in the repo |
| NYC-GEN | `docs/generation.md` in the repo |
| NYC-INF | `inference/README.md` in the repo |
| NYC-PP | `src/isometric_nyc/generation/pixel_art_postprocess.py` in the repo |
| NYC-WATER | `docs/water_shader.md` in the repo |
| HN-NYC | Show HN thread: https://news.ycombinator.com/item?id=46721802 (read through the HN Algolia API) |
| GMM-SNOW | https://googlemapsmania.blogspot.com/2026/02/isometric-nyc-snow.html |
| SG | Yadong Xie, "How Pixel Singapore was made": https://www.yadongxie.com/blog/how-pixel-singapore-was-made |
| LON | Boris Starkov, "tiny.london: how it was made": https://tiny.london/how/ (text: https://tiny.london/llms-full.txt; facts: https://tiny.london/llms.txt) |
| SF | Justin Chavez, "Isometric SF": https://justinchavez.com/blog/isometric-sf/ |
| SF-SITE | https://isometricsf.com (credits) |
| ISO | Isopolis developer notes: https://sf.isopolis.city/dev.html |
| HN-ISO | Show HN: Isopolis (mirror): https://hn.nuxt.dev/item/49149966 |
| TOR | Ahmed Nadar, "How tinytoronto was made, one block at a time": https://tinytoronto.ca/articles/how-tinytoronto-was-made |
| BER | Pixel Berlin, "How it was made": https://pixelberlin.com/how.html |
| WAW | Bedirhan Yildirim, "Isometric Warsaw": https://bedirhanyildirim.com/pixel-art-map-of-warsaw/ |
| IC | Directory of isometric city maps: https://isometriccities.com/ |
| IC-P | Isometric Paris: https://isometriccities.com/maps/paris/ |
| SYD | Pixel Sydney: https://pixelsydney.com/blog/pixel-sydney-map |
| TPAR | https://tiny.paris (footer credits) |
| NYCIG | https://nyc.infinite.games |
| BRU | https://tiny.brussels |
| JEN | Jenny et al., "Cartographic Relief Shading with Neural Networks" (IEEE VIS 2020): https://arxiv.org/abs/2010.01256 |
| JEN-2 | Eduard and follow-up work: https://ica-abs.copernicus.org/articles/10/73/2025/ica-abs-10-73-2025.pdf, https://cartogis.org/docs/autocarto/2022/docs/abstracts/Session3_Jenny_0293.pdf |
| APL | Apple Maps landmark models: https://justinobeirne.com/full-list-of-custom-3d-landmarks-redesigned-apple-maps, https://gizmodo.com/apple-maps-boston-detailed-city-google-immersive-view-1850238515 |
| NJ | "How I hand draw an illustrated map": https://nickjonesillustrations.blogspot.com/2023/02/how-i-hand-draw-illustrated-map.html |
| JS | Jenni Sparks' hand-drawn London: https://transportdesigned.com/hand-drawn-maps-of-london-by-jenni-sparks/ |
| RH | Rod Hunt: https://rodhunt.com/isometric-city-illustration-inc-differnt-neighbourhoods |
| OXEN | Oxen.ai on isometric.nyc: https://ghost.oxen.ai/isometric-nyc/ |
