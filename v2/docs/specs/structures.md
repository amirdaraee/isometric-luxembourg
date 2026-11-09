# Bridges and the modelled viaducts

**Purpose.** ACT's 3D model has buildings only, and v1's bridges had piers but no arches. The viaducts the test
area is built around are modelled once, as data, so layer 6 can draw them and layer 12 can hide trains under them.
Data: `v2/data/structures/viaducts.json` (in git, with sources). Code: `v2/data/scene/structures.py`.

| Viaduct | OSM outline | Documented | Spans used | Source of spans |
|---|---|---|---|---|
| Pulvermühl (Biisserbréck), lines 1 and 3 | way 576297593 | 242 m long, up to 37 m high; 2 + 2 tracks since 2019 | 5 equal | en.wikipedia: two abutments, four intermediate supports |
| Clausen (Clausener Viaduc), line 1 | way 583203779 | 208 m, 44 m high, largest span 15 m, 2 tracks | 15 m (11 arches) | fr/lb.wikipedia: span 15 m; count from length (assumption) |
| Pfaffenthal (Pafendaller Viaduc), line 1 | way 1512745574 | 257 m (lb: ~260 m), 32 m high | 15 m (15 arches) | assumption: same builders (Waring Brothers, 1859–62) as Clausen |

**Rules.**
1. **Axis and width:** the long axis of the OSM bridge outline (man_made=bridge) and its short side.
2. **Deck:** the transport graph's rail/tram bridge edges over the outline (the LiDAR surface model of the deck,
   solved with the grade cap), binned every metre along the axis; stretches no edge covers take the nearest
   covered height.
3. **Arches:** `count` equal spans, or spans of `span_m` with count = round((L + pier) / (span + pier)), piers 3 m
   thick (assumption). A semicircular arch's crown = deck − 1.6 m (assumption); springing = crown − radius, never
   below the ground at that point; an arch within 1.5 m of the ground is solid (abutment).
4. **Piers** between arches from the lowest LiDAR ground under them to the springing; none where the deck is less
   than 1 m above the ground (embankment).
5. Every OSM bridge outline in the area is listed (name, layer, structure) for layer 6.

**Checks.** V1 every viaduct in the area modelled · V2 its deck on the graph (median ≤ 0.3 m) · V3 pier feet on the
ground (≤ 0.5 m above) · V4 piers between ground + 1 m and the deck · V5 arches below the deck · V6 modelled length
within 15% of the documented length · V7 modelled vs documented height (report).

**Open (owner, G0).**
- Arch counts and spans of the Clausen and Pfaffenthal viaducts are assumptions (no source found giving them);
  a photo count would settle them, and only `viaducts.json` changes.
- Pulvermühl: OSM says *arch*, the French article describes hollow reinforced-concrete piers and a composite
  metal deck (the rebuilt structure); modelled as 5 arches. Beam would be `"structure": "beam"`.
- Documented heights (37, 44, 32 m) are higher than the LiDAR deck-to-ground (34, 33, 31 m); the documents probably
  measure from the foundations or the river bed. The model uses the LiDAR.
- The Passerelle (24 arches, 290 m) and Pont Adolphe are outside the test area; they are added the same way for
  the commune.
