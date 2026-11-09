# Layer 4: Roads, streets, paths, rail, tram tracks, markings

**Purpose.** Every road, street, path, step, rail and tram track, drawn from the transport graph, exactly where the
vehicles drive. **Made by:** code.

**Inputs.** The transport graph (`graph.json`: 3D polylines with width, lanes, structure and a height profile),
OSM area:highway and pedestrian areas, the palette (`transport.*`).

**Output.** RGBA tiles, depth = the profile's depth per pixel (decks at deck height, tunnels not drawn), plus a
lossless "drivable" id tile set (edge id per pixel) for the vehicle check.

**Rules.**
1. Each edge is drawn as a ribbon of its width, centred on its polyline, at its profile height (so bridge decks sit
   on their bridges and ramps on their slopes).
2. Tunnels are not drawn; a portal is drawn at each found portal (`portals`), on the cliff face.
3. Markings: lane dashes from `lanes`, rails as two ink lines with sleepers, tram tracks as grooved lines, steps as
   treads across the width.
4. Draw order is by depth, so a bridge deck covers the road it crosses (no OSM `layer` guessing).

**Checks.**
- L4.1 (gate) 100% of road, rail and tram centre lines inside their drawn surface (brief 7, by construction).
- L4.2 (gate) Vehicles on drawn road ≥ 99.5% of samples over a simulated day (brief 7).
- L4.3 (gate) No drawn pixel along a tunnel between its portals.
- L4.4 (gate) Seams, layer-off and no-cars checks.
- L4.5 (gate) Line score: drawn edges deviate from the projected graph by ≤ 1 px over 95% of their length (brief 6).
