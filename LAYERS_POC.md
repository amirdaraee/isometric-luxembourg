# Layered map: proof of concept on the old town

Written 7 Nov 2026 after a brainstorm with the owner. Goal: replace the single painted image with separate layers,
drawn partly in code and partly by the image model, so every part of the map can be controlled, fixed, animated and
changed per season on its own. Test ground: the old-town block b00 (map px x 5500–11500, y 3700–9700), as at the start
of the project. Nothing in the live site changes until the owner approves the result.

## Why
Today the whole map is one painting. Vehicles drive on OpenStreetMap lines that do not match the painted roads, trees
and cars are baked into the art, seasons need a full repaint, and every fix means repainting a block. With layers:
- roads, rivers and tracks are exact, so vehicles, trains and boats are always on them;
- buildings have exact outlines, so vehicles hide behind them correctly and nothing is baked into them;
- trees are placed individually from real data, change per season by swapping drawings, and can sway in the wind;
- shadows follow the real sun, so time of day becomes real;
- any layer can be redone alone (a season, an event, a fix).

## The layers, bottom to top
| # | Layer | Made by | Notes |
|---|---|---|---|
| L1 | Ground and land cover (terrain, grass, fields, vineyards, parks, squares, pavements, car parks, sports grounds) | code | from terrain (LiDAR) and OSM land use |
| L2 | Relief: cliff faces, slopes, retaining and fortification walls | code (+ model touch-up if needed) | the old town's character: Bock, Pétrusse and Alzette valleys |
| L3 | Water: Alzette, Pétrusse, ponds | code | exact OSM water; the animated water effect sits on this mask |
| L4 | Roads, paths, rail and tram tracks | code | exact OSM geometry and widths; vehicles drive on exactly these |
| L5 | Bridges and viaducts | code shape + model paint | above L3/L4; trains and cars pass over or under |
| L6 | Shadows | code | cast by buildings and trees from the 3D model and the sun position; time of day; none at night |
| L7 | Buildings | image model | painted on a flat backdrop, then cut out (see "Cutting") |
| L8 | Trees | image model library, placed by code | single painted trees, depth-sorted with buildings (see "Trees") |
| L9 | Night lights | code (+ model for lit windows) | street lamps, lit windows; only at night |
| — | Moving things (vehicles, trains, boats, birds, weather) | viewer | as today, now drawn between the right layers |

### Drawing style for the code layers
Code-drawn layers must look like the same inked illustration, not a vector map. Two options, both tested in step 1:
- **A. Inked rendering in code:** warm flat colours from the current art's palette, a light paper texture, fine dark
  ink outlines on edges (road edges, water banks, field borders), hatching on slopes and cliffs, lane markings on roads.
- **B. Code draft + light model pass:** draw the layer in code, let the model repaint it lightly in the trained style
  (low strength), then put the exact road and water edges back on top so the geometry stays exact.

### Cutting buildings (L7) without losing parts
The model draws details the 3D model does not have (chimneys, dormers, eaves, balconies) and its outlines can sit a
pixel or two outside the true edge. So the buildings are painted on a known flat backdrop colour (the render with the
ground replaced by a single colour), and a pixel is kept when:
1. it is inside the building outline from the 3D model, grown by a few pixels of slack; and
2. it is not the backdrop colour.
Edges get a one-pixel soft alpha. Anything the model invents in courtyards or streets is backdrop or outside the
outline, so it is removed. Building shadows go in L6, not in this layer.

### Trees (L8): a painted library placed by code
- **Data:** tree positions and crown sizes from the City of Luxembourg tree register (data.public.lu) if available,
  otherwise from classified LiDAR (vegetation points: first return minus ground), otherwise OSM `natural=tree` and
  wood areas. Step 0 decides which.
- **Library:** single trees painted by the model on a flat backdrop and cut out, in the map's projection and light:
  several species (lime, plane, chestnut, maple, birch, conifer, fruit tree), 3 sizes, 3–4 variants each, and each in
  four seasons (spring blossom/fresh green, summer, autumn colour, bare winter with optional snow). Plus "canopy mass"
  pieces (clusters, forest edges) for dense woods on the slopes, so forests don't look like scattered lollipops.
- **Placement:** each tree at its real base point, scaled to its crown size, with a random variant and a slight colour
  jitter; never mirrored (it would flip the light).
- **Depth:** trees and buildings are combined by depth (each tree has a base point; buildings have the height pass),
  so a tree behind a building is hidden and one in front covers it. Vehicles pass under crowns.
- **Shadows:** each tree has a matching shadow shape in L6.
- **Motion:** each tree sways with the live wind (weather feature).
- **Speed:** trees that don't move are merged into the tiles at build time; only near zoom draws them live.

## Steps
0. **Data check (free, ~½ day).** Tree data (register or LiDAR vegetation), OSM land use and paths for the old town,
   terrain heights for cliffs. Decide the tree source. Output: `data/work/layers/b00/inputs/`.
1. **Code layers L1–L4 (free, ~1–2 days).** `pipeline/layers/draw_ground.py` renders ground, relief, water and roads
   for b00 in the map projection at full resolution, in style A; then a style-B variant through mdpaint at low
   strength with exact edges restored. Compare both with today's art. Output: one PNG per layer.
2. **Buildings L7 (~$1 on Modal, ~½ day).** Render buildings only on a flat backdrop (`render.py` option), paint with
   the trained style and mdpaint, cut out by the two rules. Check edges at full zoom on 10 spots (chimneys, eaves,
   courtyards). Output: RGBA layer plus its depth (from the height pass).
3. **Bridges L5 (~$0.50).** Adolphe Bridge, Red Bridge's west end, the Passerelle and the Clausen viaduct: deck shapes
   from code, painted like buildings, cut out, joined exactly to the roads in L4.
4. **Tree library L8 (~$1–2, ~1 day).** A trial library of about 20 trees (4 species x 2 sizes, summer and spring)
   plus 4 canopy-mass pieces; place them on b00 from the chosen data.
5. **Shadows L6 (free, ~½ day).** From the 3D model and tree crowns at a given sun position; a midday and an evening
   version to show it moves.
6. **Compose in the viewer (free, ~1 day).** A local-only `?layers` mode that stacks L1–L9 for b00 with depth sorting,
   vehicles between ground and buildings, and the layer switches visible in a debug panel.
7. **Compare and decide.** Side by side with today's old town on the compare page, by day and in spring; check the
   problem spots from the owner's screenshots (cliff car, Pfaffenthal embankment, Red Bridge, spring trees).

## Success criteria
- Looks as rich and as "inked" as today's painting (owner's judgement); no "pasted sticker" look or halos.
- Vehicles and trains are exactly on roads and tracks everywhere in b00.
- No building parts lost at the cut (spot checks), no invented objects left.
- Spring is a tree swap, not a repaint; trees sway; shadows move with the sun.
- Viewer stays smooth (60 fps on a laptop) with the extra layers.

## Cost and time
About $3–4 in total (Modal for buildings and bridges, OpenAI or Modal for the tree library), and about a week of
work. If it succeeds, the whole map is redone layer by layer: roughly 2–3x today's painting cost for buildings, but
seasons and night become much cheaper afterwards.

## Risks
- Code-drawn layers may look flat next to painted buildings: mitigated by trying both styles A and B.
- Cut-outs may look pasted on: mitigated by shared light direction, contact shadows and soft edges.
- Tree data may be incomplete: fall back to LiDAR or painted canopy mass for woods.
- More tile layers to load: merge layers into one image at far zoom levels.
