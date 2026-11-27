# The viewer's layer compositor

**Purpose.** Draw the 15 layers as one map in the browser: tiled colour layers with their depth, lit by code,
with vehicles and labels depth-tested, at 60 fps on desktop and ≥ 30 fps on a mid phone (PLAN_V2 section 8).
**Built in phase 1** in `v2/web/`, from v1's viewer shell (OpenSeadragon navigation, feature switches, frame clock,
test parameters `?hour`, `?season`, `?seed`, screenshot and speed harness).

**Design.**
1. One WebGL2 canvas over the navigation; for the visible tiles of each layer, colour and depth textures in an atlas.
2. Per pixel: the nearest of layers 1–7 by depth (ties by layer order), then light (layer 9) from layer 8's normal
   and the shadow map, night (10), seasons (11), the look (14).
3. Vehicles (12) and events (13): sprites with a depth per sprite pixel, tested against layer 8's depth in the same
   pass; labels and pins (15) as DOM/canvas over it, hidden when their ground point is behind a nearer surface.
4. Draw only on change (TOR); one frame clock (v1); nearest-neighbour above 1:1.
5. Every layer can be switched off (`?off=trees` etc.), which is how the layer-off checks run.
6. Every file of the release is loaded through one queue (`src/loadq.ts`): at most 32 at a time, in the order
   asked. A tile whose turn comes when no frame has asked for it in 8 frames is not loaded (the view moved on). A
   request the network fails is made again (three times, 0.25 s and 0.5 s apart); a tile that still fails is asked
   for again by the next frame that needs it after 1 s, then 2 s, doubling to 30 s. Why: a 2552 x 1278 window at two
   device pixels a pixel asks for 1,947 files in its first view; asked all at once, Chrome refused 549 of them
   (`net::ERR_INSUFFICIENT_RESOURCES`), the tiles were never asked for again, and because the shadow map waits for
   the first whole view, the view also had no shadows (the owner's picture of the Corniche, 27 Nov 2026).

**Checks.**
- C1 (gate) Switching any layer off leaves no trace of it (pixel diff against the composite rendered without it).
- C2 (gate) Speed: first view < 0.5 s on a mid phone; pan ≥ 60 fps desktop, ≥ 30 fps mid phone, all layers on.
- C3 (gate) Same pixels as an offline reference render of the same view (± rounding), so what is checked offline is
  what is seen.
- C4 (gate) Depth test at every portal and bridge of the test area (brief 8; with L12.1).
- C5 (gate) A large window's first view (2552 x 1278 at two device pixels a pixel, zoom 0.5 over the old town): no
  request refused or failed, every tile of the view loaded, the shadow map loaded.
