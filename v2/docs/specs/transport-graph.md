# Transport graph

**Purpose.** The one network vehicles, trams and trains move on, drawn by layer 4 and depth-tested by layer 12:
3D polylines with width, lanes and a height profile per segment, joined at junctions, with bridges, tunnels and
portals (PLAN_V2 section 6). Code: `v2/data/scene/transport.py`, `profile.py`, `transit.py`.

## Edges
- **Ways:** OSM highway (not area=yes, not proposed/abandoned/razed/platform), railway rail, light_rail, subway,
  narrow_gauge, preserved, disused, tram, funicular. Unwarped: positions are OSM's, in LUREF.
- **Splitting:** at every node shared with another way (a junction) and at way ends; ways are cut where they leave
  the terrain grid (those ends are *boundary* nodes, as are nodes whose other edges lie outside the selection).
  Edges are kept when they touch the area + half its margin.
- **Attributes:** mode (road, path, steps, rail, tram, funicular, elevator), class, name, ref, width (OSM width,
  else lanes × 3.25 m for roads with a lanes tag, else a per-class default), lanes (OSM lanes or tracks, else a
  default), oneway, OSM layer, structure: *ground*, *bridge* (bridge=* other than no), *tunnel* (tunnel=yes,
  culvert, avalanche_protector), *passage* (tunnel=building_passage, covered=yes: at ground level), *indoor*
  (corridors), *elevator*.
- **Samples:** every ≤ 2 m along the edge (both ends kept), with the ground (median of the LiDAR terrain at the
  centre and ±¼ width) and, on bridges, the deck observation (median of the LiDAR surface at the centre and ±(½ width
  − 0.35 m)).

## Height profile
The profile of an edge is the lowest-cost height path through its observations with the grade capped
(`profile.solve`: dynamic programming over height bins, L1 cost, so a lorry on a deck or a wall beside a road is
ignored; Pixel Singapore's method, OTHERS 6 P4). Caps (`params.json` transport): road 24%, path 60%, steps 120%,
rail 4.5%, tram 8%, funicular 80%; on decks road 10%, rail 3.5%, tram 7%. The step between two samples is a whole
number of bins, so the cap is exact.

0. **What the surface model cannot see.** A deck sample (each of the three across the deck) is not an observation
   where something stands over it: a building footprint, a tree crown of the LiDAR survey (half its widest crown +
   0.5 m) or a bridge of a higher OSM layer; nor anywhere on a covered bridge (`bridge=covered`: car-park decks,
   galleries, where the surface model shows the roof); nor a reading more than a vehicle's clearance above the rest
   of the deck (something over it that the 3D model lacks). ACT also cuts a bridge out of the terrain model past where OSM ends the
   bridge tag: from an abutment, while the surface model continues the deck's level (within 1 m at the abutment, then
   smoothly within the grade cap), stands > 1 m over the terrain and nothing covers it, the approach road follows the
   surface model.
1. **Pass 1, free ends.** Ground-level edges against the terrain, bridges against the deck observation (kept ≥ 0.3 m
   over the ground). Ground samples within 6 m of an abutment or a portal carry no weight (ACT cuts bridges out of
   the terrain and the cut and the OSM node rarely agree; above a portal the terrain is the cliff); there the
   profile holds the approach's level.
2. **Node heights.** Each node takes the median of its incident edges' free ends — vehicle ways only when the node
   has any (a footpath leaving a bridge down a stair must not pull the road with it). Abutments (ground + bridge)
   take the deck's level wherever the surface model sees the deck's end (an observed sample within 6 m of it),
   else the approach's; portal nodes the approach's. Tunnel nodes have no observation: they are interpolated along the tunnel graph
   (harmonic, by length). Finally every node is projected into the band its vehicle edges' grade caps allow
   (with 10% headroom).
   Tunnel nodes are then held under their cover by their tunnels' clearance + 1 m (+ 0.5 m margin), ramped in over
   40 m from the portals, and projected back within the grade caps.
3. **Pass 2, pinned.** Each edge's profile is solved again between its two node heights, so edges meeting at a node
   share its height exactly. Tunnels have no observation: they run as straight as the cap allows, softly held below
   their *cover* by the edge's clearance + 1 m (+ 0.5 m margin), ramped in
   over the first 40 m from a portal. The cover is the terrain, or the surface model where a building or a bridge
   deck stands over the tunnel. Elevators run straight between their landings. If the pins and the cap cannot be
   met, the cap is doubled until they can and the edge is flagged (`solved` = "…+grade_x2"; check P4).
4. **Portals.** From each portal node (a tunnel node touching an open edge), walking into the tunnel network (every
   branch, nearest first, up to 500 m), the first sample where the vehicle is a full clearance under its cover.

**Clearance per edge.** The OSM `maxheight` when tagged (1.5–7 m: the signed headroom); else, for service roads in a
tunnel (car-park aisles and ramps), a car park's 2.5 m; else the mode's (road 4.5 m, rail 5.5 m, tram 4.5 m: accepted
at G0). Stored per edge as `clearance_m`; P7–P9 use it.

## Output
`graph.json`: nodes (OSM id, e, n, z, kind ground/abutment/deck/tunnel/mixed, degree, boundary), edges (as above,
plus `en`, `s`, `z`, `ground`, `deck_obs` on bridges, `cover`, `tunnel_d`, chain id and length on tunnels, and how
the profile was solved), portals (node, edge, found, distance from the tunnel end, position, cover).

## Transit (`scene_transit`)
GTFS (national feed, CC BY) trams, trains and funiculars for a weekday, a Saturday and a Sunday; each shape that
touches the area is matched onto the rail/tram/funicular edges with v1's HMM (`build_transit.py`, kept): a sample
every 20 m, candidates within 40 m, emission = distance from the point moved 2 m to the running side (trams right,
CFL trains left), transition = |graph distance − straight distance| / 25 m; a run with an impossible step is
matched in halves rather than lost. Output `transit.json`: per shape its lines, trips per day type, matched edge
runs and coverage (a sample is covered when the matched path passes within 17 m, or it is part of a matched run).

## Checks
P1–P12 (profiles), G1–G6 (graph), TT1–TT4 (transit): see checks.md. Unit tests: `v2/data/tests/test_profile.py`,
`test_transport.py` (a synthetic valley with a bridge and a hill with a tunnel).
