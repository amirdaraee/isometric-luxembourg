# Roadmap

## Release 1.0 (7 Nov 2026): the old-town showcase
Done:
- Painted old town (Ville Haute, Grund and the Pétrusse valley around them) with style model v2,
  guided by a layout map from OpenStreetMap: true water, clean tracks, no parked cars.
- Time of day: live clock, golden hour, painted night without daytime shadows.
- Seasons: spring, summer, autumn, winter, plus winter night.
- Christmas markets on Place d'Armes, Place de la Constitution and Place Guillaume II, by day and by night.
- Cars on the real street network (only where the street is visible), and trams and trains on the GTFS timetable.
- 47 landmark cards with history, interiors, 10 cutaway drawings, 30 3D models and credited photos.
- Feature switches for every optional part (`web/src/features.ts`). GitHub Pages deploy.

## Next
The order of work, step by step, is in **[PLAN.md](PLAN.md)**, along with the rules learned so far:

| Phase | What | Cost | Status |
|---|---|---|---|
| 0 | Tidy up: fix label drift, cap zoom, height pass | free | done 7 Nov |
| 1 | New painter (`mdpaint.py`): whole-canvas painting with shifted windows, resume, patch repair | free | done 7 Nov |
| 2 | Showcase test on Modal: new painter vs today, 8 vs 25 steps | ~$4 spent | done 7 Nov: Lightning 8 steps chosen (sharper, 5 seam spots vs 52, $0.75 per block) |
| 3 | Whole city ready: renders, block plan, sparse tiles, Cloudflare R2, cost table | mostly free | done 7 Nov (R2 not needed yet: site is 153 MB) |
| 4 | Paint the city by day, block by block, live as each finishes | about $10 | done 7 Nov: 15 blocks, live on isometric.lu |
| 5 | Night (full resolution), golden hour, seasons for the whole city; Christmas regenerated | cap $60 approved | in progress 7 Nov: testing night (Lightning too light; trying 15 steps with guidance) |
| 6 | Life on the map: car hiding, water shimmer, swaying trees, better traffic, transit refresh, birds | free | done 7 Nov except swaying trees: traffic sim, sprites, occlusion, river water, trams/trains, weekday/weekend timetable, birds; access rules + emergency vehicles in progress |
| 7 | Switch features on publicly, one at a time | free | to do |
| 8 | isometric.lu | domain fee | done 7 Nov |
| 9 | More events, weather, clouds, easter eggs, height, historic mode | varies | clouds being redone; notes from visitors (API live, hidden) |

## Open issues
| ID | Issue | Type | Phase |
|---|---|---|---|
| I1 | ~~Place labels drift while the map moves~~ Fixed 7 Nov: labels move in the map's own redraw (`MapHandle.onFrame`); React only picks which show. | bug | 0, fixed |
| I2 | ~~http did not redirect to https~~ Fixed 7 Nov (redirect is live). | check | 0, fixed |
| I3 | Night is upscaled from a 4096 px preview after a pod stopped early. | quality | 5 (being repainted) |
| I4 | Buildings go soft at full zoom; windows are warped and facade lines aren't parallel. See "Building quality" below. | quality | 2, 4 |
| I5 | ~~Visible seams and colour drift~~ Fixed 7 Nov by the whole-canvas painter. | quality | closed |
| I6 | The painter sometimes invents trees over streets and small cars on station roads. | quality | 2 (patch repair) |
| I7 | ~~`transit.json` holds one service day~~ Fixed 7 Nov: weekday, Saturday, Sunday/holiday timetables. | data | closed |
| I8 | ~~The viewer zooms past the painted resolution~~ Already capped in 1.0 (`maxZoomPixelRatio: 1.25`). | bug | 0, closed |
| I9 | ~~Unpainted areas show the raw render~~ Fixed 7 Nov: a note says so, and the whole city is painted now. | UX | closed |
| I13 | The occlusion mask is one 6656 x 3584 image (1 m cuts); split it into tiles loaded on demand for finer cuts and less memory. | perf | 6 |
| I14 | The map covers the rendered pilot area (about lon 6.115-6.175, lat 49.597-49.637), not the whole commune: Merl, Belair, Cloche d'Or, Gasperich, Cessange, most of Hollerich, Rollingergrund, Beggen and Dommeldange are outside. Extending needs a wider render, new blocks (about 2-3x the area) and tiles on R2. | scope | 3, 4 |
| I15 | The background of the main menu and panels is not good (raised 7 Nov 2026): the dark blurred glass (`.glass`, `--glass` in `web/src/styles/global.css`) behind the search bar, scene control, layer buttons and cards, and the plain "Loading Luxembourg" splash. Design a better one in the map's inked, warm style (e.g. paper-toned panels with a fine ink border, or a painted vignette for the splash), checked by day and night and on phones. | design | later |
| I11 | Christmas patches belong to today's winter art and must be redone after any repaint. | process | 5 |
| I12 | ~~RunPod balance~~ Moved GPU work to Modal (7 Nov). | money | closed |

# Feature ideas

From the project owner. Status notes are as of 5 Nov 2026, with release 1.0 changes marked.

## The map
1. **Clouds at the map's edges.** Clouds where the map ends, instead of a hard edge.
2. **Event changes to the map.** *(Christmas markets done in 1.0.)* Christmas markets, Schueberfouer, the Grand Duke's birthday (National Day), and others. Also Halloween.
3. **Weather changes.**
4. **Daytime changes.** Includes night. *(Done in 1.0.)*
5. **Shadows.**
6. **Height above sea level.** Real ups and downs in the map. The current captures already use LiDAR terrain, so the gorges are in the geometry; showing height to the visitor is still to do.
7. **Famous buildings and monuments.** *(Cards, interiors, cutaways and 3D done in 1.0.)* Details and info, plus a 3D shape to explore further, and even see inside. Exterior 3D data exists for most buildings; interiors would need another source.
8. **Moving cars that show traffic.** *(Done in 1.0.)*
9. **Easter eggs.** Hidden surprises around the map.
10. **Seasons.** *(Done in 1.0 as painted versions.)* Trees change with the season: autumn colours, bare winter trees, snow. Planned as layers over the summer base art: recolouring trees in the browser from a tree mask, or a generated version per season, as isometric-nyc did for snow.
11. **Moving trains and birds.** *(Trains and trams done in 1.0; birds to do.)* Real CFL trains as animated sprites on the tracks. Reference from the owner: CFL double-deck units have a white body, a red nose, red doors and a red lower band, with a long dark window band.

## What the base art leaves out (decided 5 Nov 2026)
Everything that will move, change or be animated is left out of the base art, so the live layers don't clash with frozen copies:
- No cars, buses, trams, trains, people or birds. Roads and tracks are empty.
- Water is drawn flat and calm, ready for an animated water layer.
- Trees are summer only; seasons come later as layers.
- Daytime shadows stay in the art. Night is a separate layer.
- Night and time of day without repainting: render a shadow mask from the 3D buildings at the aerial photos'
  sun position, so the baked-in shadows are known exactly. Night lifts those areas to match their surroundings
  before darkening (no ghost shadows), then adds window, street and bridge lights from 3D/OSM data. The same mask
  deepens or softens shadows for golden hour and noon. A painted night map stays an option if this falls short.

## Art direction
The first style test (Isometric NYC's trained style) was judged not beautiful, colourful or detailed enough. The target is more beautiful, more colourful and more detailed, at the level of isometricsf.com in quality.

Chosen look (5 Nov 2026): option I on the style comparison page, the inked illustration with fine outlines, rich colour and deep shadows (the `ink` brief in `pipeline/style/draw_openai.py`). Pixel, painted, calm and in-between versions were tried and passed over.

## Reference to study
tinytoronto.ca already has several ideas from this list: illustrated clouds over the map's edges, live time and weather, moving transit vehicles and a "0 / 10" counter that looks like a collectible (not confirmed).

## Later: building quality (raised 6 Nov 2026)
Buildings look soft and smudgy in most areas. Likely causes, to check in this order:
1. Scale: each painted window covers 300 m in 1024 px (~0.29 m/px), so a facade gets only a few pixels per window;
   the model invents rather than draws them. Test painting at 450 or 300 src px per cell (finer, 1.8-4x more GPU).
2. Input: the 3D model's facade textures are low-resolution photos, often blurry or stretched, and the painter
   copies that softness. Option: sharpen/clean facades in the render, or give windows a clean procedural grid.
3. Training: only 40 drawings, at the same coarse scale; add close-up building examples (old town, Kirchberg).
4. Final step: an upscale/detail pass on finished tiles (super-resolution tuned on our drawings).
Also: windows distorted and facade lines not parallel. Image models don't enforce geometry; soft/warped 3D facade
textures and tiny windows make it worse. Plan: (a) render a clean line pass from the 3D model (edges, ridges, eaves,
and a regular window grid per wall from its real size) and blend it faintly into the input; (b) stronger: train the
style LoRA with that line pass as a second control image (Qwen-Image-Edit-2511 takes several), ControlNet-style;
(c) finer painting scale for dense quarters; (d) retrain with close-up building examples. Test (a)+(c) on the Place
d'Armes block first (~$0.50).
Example: old town around Place d'Armes / Hôtel de Ville (6 Nov). Also cap the viewer's max zoom at
the painted resolution (~0.29 m/px) so it never shows upscaled mush.

## Fixed in 1.0: cars on rooftops
The Traffic layer draws cars on roads hidden behind buildings (seen on old-town roofs). Fix: export the render's
visibility pass (frames_kind) as a low-res "road visible" mask for the viewer and only draw cars where it is set.

## Later: faster GPU runs (before the full-city paint)
Folded into PLAN.md Phases 1 to 3. The new painter's per-step resume also allows cheaper interruptible GPUs.
- Network volume with the base model + venv cached (~80 GB, ~$5-6/month): pod setup ~1 min instead of ~8.
  Ties pods to that volume's data centre.
- Parallel GPUs for big jobs: independent blocks per GPU, then one seam pass between blocks.
- Lightning LoRA for Qwen-Image-Edit-2511: 4-8 steps instead of 25 (3-6x faster/cheaper); quality test first.
- Whole city at finer scale (~3,600 windows): ~27 h / ~$110 today; ~2.5 h / ~$40 with Lightning on 4 GPUs.
