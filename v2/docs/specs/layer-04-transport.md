# Layer 4: Roads, streets, paths, rail, tram tracks, markings

**Purpose.** Every road, street, path, step, rail and tram track, drawn from the transport graph, exactly where the
vehicles drive. **Made by:** code.

**Inputs.** The transport graph (`graph.json`: 3D polylines with width, lanes, structure and a height profile),
OSM area:highway and pedestrian areas, the palette (`transport.*`).

**Output.** RGBA tiles, depth = the profile's depth per pixel (decks at deck height, tunnels not drawn), plus a
lossless "drivable" id tile set (edge id per pixel) for the vehicle check.

**Rules.**
1. Each edge is drawn as a ribbon of its width, centred on its polyline, at its profile height (so bridge decks sit
   on their bridges and ramps on their slopes). A ground way is draped on the terrain, except on every stretch where
   its profile stands more than 1 m over the drawn terrain (grown along the way while it stays more than 0.1 m over
   it, and from any bridge end it leaves): there it is a deck at its profile, so an approach the terrain model has
   cut away (ACT cuts bridges out past OSM's bridge tag) meets its bridge with no gap or step, and meets the terrain
   where the road does (`geometry.deck_mask`; phase 2, after the owner's "red bridge not connected" report).
   A way's surface is at the way's own height: on the scene's cliff cells (the face of a cliff or a wall) it is
   drawn only where the ground is within 1.0 m of the ground under the nearest point of the way's centre line
   (owner, 25 Nov 2026: weird patches on cliffs), and always within 0.5 m of a centre line, so a way that itself
   climbs a face keeps its line (L4.1). Where a road's width in plan reaches over a face, the face stays rock;
   steps and paths cut into a face are at their own height and stay.
2. Tunnels are not drawn; a portal is drawn at each found portal (`portals`), on the cliff face.
3. Markings: lane dashes from `lanes` (drawn 0.25 m wide, so they read at 0.125 m a pixel), rails as two ink lines
   with sleepers, tram tracks as grooved lines, steps as treads across the width.
   Crossings: a way the graph marks (`crossing`: "zebra", from OSM, see transport-graph.md) is striped where it lies
   on a carriageway: bars of 0.5 m with gaps of 0.5 m along the walking line, each as long as the way is wide (3 m at
   least), in the lane dash's colour. Nothing is striped off the asphalt, and a crossing OSM calls unmarked gets
   nothing.
   Surfaces on the ground carry drawn detail (phase 3): setts on pedestrian streets, paths and steps; on asphalt a
   soft wash, its tone drifting by a few per cent over 3 m and 11 m with no grain from pixel to pixel
   (`detail.asphalt`), from each pixel's place on the ground. Bridge decks carry the same wash.
   Kerbs: a street (every road but driveways, car park aisles and tracks: OSM service and track) has a kerbstone of
   0.3 m outside its carriageway, in `transport.kerb`, inside the ink outline. The carriageway keeps the width the
   graph gives it. Where a path meets the street, the path's surface cuts the kerb.
   The asphalt wash, the wider lane dashes, the kerbs and the crossings are v1's road, which the owner asked for
   (23 Nov 2026). v1's asphalt colour, measured where it is clean and lit, is the palette's `road` within 3%, so
   the colour did not change.
4. Draw order is by depth, so a bridge deck covers the road it crosses (no OSM `layer` guessing).

**Checks.**
- L4.1 (gate) 100% of road, rail and tram centre lines inside their drawn surface (brief 7, by construction).
- L4.2 (gate) Vehicles on drawn road ≥ 99.5% of samples over a simulated day (brief 7).
- L4.3 (gate) No drawn pixel along a tunnel between its portals.
- L4.4 (gate) Seams, layer-off and no-cars checks.
- L4.6 (gate) Bridge ends continuous: at every abutment in the area (a node joining a bridge and a ground way),
  along the bridge's last 6 m and the first 6 m of every way leaving it (every 0.25 m), the transport layer draws the
  way (a surface at the way's profile or on the terrain, within 2 px of height; the pixel next to it accepted on a
  surface's edge), and its drawn height never changes faster than both the profile and the terrain by more than
  2 px, in a change that stays (medians of 1 m either side), along a way or between the ways meeting at the node.
  Samples hidden by a nearer surface (a deck over it, a way drawn over it at a junction, a hill) or whose top is seen
  edge-on or not at all are counted apart. Exceptions per way in `v2/data/exceptions.json`. Phase 2 (the owner's
  report "the red bridge is not connected to the road": 54 of the test area's 121 bridge ends failed it before the
  fix, 0 after).
- L4.7 (gate) Every crossing the graph marks, with 2 m or more on a carriageway, is striped on 20% or more of that
  length (bars and gaps are equal, so about half). L4.7b (info): the crossings, their metres on a carriageway and
  the share striped.
- L4.5 (gate) Line score: drawn edges deviate from the projected graph by ≤ 1 px over 95% of their length (brief 6).
