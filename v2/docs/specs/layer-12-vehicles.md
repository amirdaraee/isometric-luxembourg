# Layer 12: Vehicles, trams, trains, planes

**Purpose.** Moving traffic, trams and trains on the real network and timetable, hidden in tunnels and under decks
and trees exactly. **Made by:** code (v1's simulation, kept: IDM following, signals, access rules; GTFS timetable
with v1's HMM matching, now on the unwarped graph).

**Inputs.** The transport graph (edges with profiles, lanes, oneway, access), the matched transit
(`transit.json`: shapes as runs over graph edges, trips per day type), layer 8 depth.

**Output.** Sprites drawn by the viewer per frame, each at its edge's profile height, depth-tested per pixel against
layer 8.

**Rules.**
1. Vehicles move only on graph edges; position (e, n, z) comes from the edge's polyline and profile, never from the
   art.
2. Per-pixel depth test of every sprite pixel against layer 8 (a car under the Red Bridge is hidden by the deck;
   one on the deck is not).
3. In a tunnel past its portal, a vehicle is not drawn.

**Checks.**
- L12.1 (gate) Headless audit over a simulated day: 0 vehicle pixels drawn over a nearer surface; 0 vehicles drawn
  inside a tunnel beyond its portal (brief 8).
- L12.2 (gate) Smooth height on viaducts: no jump > 0.5 m between frames for any vehicle (brief 8; data side: P3).
- L12.3 (gate) The fade guard of v1 is not needed (< 0.1% of samples).
- L12.4 (gate) Vehicles on drawn road ≥ 99.5% (L4.2); trams and trains on drawn track ≥ 99.5%.
- Data checks P1–P9, G1–G5, TT1–TT3 (checks.md) gate the graph and the matching.
