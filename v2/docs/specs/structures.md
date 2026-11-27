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

## The other bridges

**Purpose.** Every bridge of the transport graph that is not one of the viaducts above was a deck with sides and
nothing under it (the owner, 27 Nov 2026: "where are the legs of the bridge?", "bridge is floating"). Shown two
samples each, the owner chose stone arches for the bridges and slanted legs for the Red Bridge.
Data: `v2/data/structures/bridges.json` (in git; every number not from a source is marked as an assumption).
Code: `v2/data/scene/structures.py` (`bridges`, `arcade`, `frame`). Output: `structures.json` `supports` and
`frames`.

**Rules.**
6. **One bridge, one row of arches.** Bridge ways joined end to end are one line (OSM cuts a way where it likes).
   Lines that run side by side (within their half widths and 2.5 m, over 80% of the shorter) are one bridge: a
   road and its footways, two tracks. Its deck is the longest line moved to the middle of them all, as wide as
   them all.
7. **Where arches stand.** The deck's underside is 1 m under the way (the slab layer 6 draws). Where it is more
   than 1.5 m over the ground for 4 m or more, arches stand under it; where it is lower, its sides go down to the
   ground.
8. **Arches.** The span follows the height: half the greatest height over the ground, between 6 and 15 m; piers
   0.2 of the span thick, between 1 and 3 m; equal spans fill the stretch. A round arch where there is room for
   one; a lower one where the ground is near (it rises over 0.8 of the room under its crown, 0.3 m under the slab).
9. **No pier on a way.** Of the layouts with the rule's count of arches, one more, one fewer and two more, the
   first whose piers stand on no road, track or path passing under the bridge is taken; if none is free, the one
   with the fewest (reported: V12).
10. **Frames.** A bridge named in `frames` is modelled by hand instead. The Red Bridge (Grand Duchess Charlotte
    Bridge) is a steel girder on two pairs of slanted legs: its axis is the line through its ways; its feet stand
    on the terrain 234 m apart; each leg leans toward the middle 0.8 m per metre it rises; the girder is 3.5 m
    deep and 3 m deeper over the legs. All of these numbers are assumptions (the span from memory, the rest read
    off the research photos).

**Checks.** V8 every bridge way of the area is in a viaduct, a frame or a row of arches · V9 no stretch standing
clear of the ground without an arch · V10 arches rise between 0.5 m and half their span, pier feet on the ground ·
V11 every frame of the area modelled with four legs standing on the ground, its length within 15% of the
documented one · V12 counts, and the piers left standing on a way (report) · V13 the frames' measures (report).

**Open.**
- OSM does not say what most bridges are made of: a modern concrete bridge gets stone arches like an old one.
- The Red Bridge's span and the lean of its legs are not from a source. A source or a measured photo changes only
  `bridges.json`.
- A pier does not know about a building or another bridge under its deck.

## Checks of the viaducts

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
