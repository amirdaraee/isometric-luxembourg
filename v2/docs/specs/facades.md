# Facade layout

**Purpose.** Windows as known positions, straight by construction (PLAN_V2 section 6; brief 6): they drive the
drawn windows (A), the material windows (B), the line score of painted windows (C) and the night windows (layer 10).

**Inputs.** Every LoD2 wall polygon of the scene's buildings. Parameters: `params.json` facades.

**Rule** (code: `v2/data/scene/facades.py`):
1. **Wall frame.** u runs along the wall's base (left to right seen from outside), v up from the wall's lowest
   point; the outward normal points away from the footprint's centre. The wall's outline in (u, v) is its polygon.
2. **No windows** on walls shorter than 2.2 m, lower than 2.4 m, not planar (> 0.5 m off their plane), or **party
   walls**: another building's wall within 0.4 m, facing the other way, overlapping ≥ 50% of the shorter one.
3. **Floors.** Eave height H = the lowest top of the outline along the wall (a gable rises above it).
   floors = 1 + ⌊(H − 3.6) / 3.0 + 0.35⌋ for H ≥ 3.6 m, else 1 (ground floor 3.6 m, upper floors 3.0 m, capped at
   40). Floor k's floor line: v = 0, then 3.6 + 3.0 (k − 1).
4. **Bays.** n = ⌊(L − 2 × 0.6) / 2.7⌋ (one bay if the wall fits a single window); bays are centred on the wall,
   pitch (L − 1.2) / n.
5. **Windows.** 1.1 × 1.45 m, sill 0.9 m above the floor line, centred in each bay, on every floor; kept only if
   the rectangle grown by 0.2 m lies inside the wall outline (so gables, stepped walls and arcades lose the windows
   that do not fit).

## Doors and shop fronts (owner's decision at the G0 review, 9 Nov 2026)

Code: `v2/data/scene/entrances.py`; inputs: the walls above, the transport graph (streets) and OSM entrances, shops,
crafts and commercial amenities (`fetch_osm_pois`). Parameters: `params.json` facades.

6. **Street-facing walls.** Not a party wall, ≥ 2.2 m long, ≥ 2.4 m high, able to take a door somewhere along its
   bottom, with its middle within 15 m of a street a person can walk from (any road but motorways and trunks;
   pedestrian streets, footways, living streets, steps) and its outward normal pointing at it (cosine ≥ 0.5).
7. **OSM doors.** Every `entrance=*` (or `door=*`) node within 3 m of a building's outline is a door on that
   building's nearest wall (the next nearest when that is a party wall), at the node's position along it:
   1.2 m wide (1.6 m for `entrance=main`), 2.3 m high; `entrance=garage` a 2.6 m garage door.
8. **OSM shops.** A `shop=*`, `craft=*` or commercial `amenity` (restaurant, café, bar, bank, pharmacy, …) inside a
   building or within 5 m of it makes a shop front on the building's street-facing wall nearest it: the ground-floor
   bays within 4 m of it along the wall (at least one bay), merged into one front.
9. **Rule shop fronts.** A *commercial street* is a named road or pedestrian street at least 50 m long with at least
   3 such POIs within 20 m and at least 15 per km. Every street-facing wall onto it, ≥ 4 m long, gets a shop front
   across its ground-floor bays.
10. **Rule doors.** A building (≥ 2.4 m high, ≥ 15 m²) with a street-facing wall but no door on one gets a door on its
    longest street-facing wall, in the bay nearest the wall's middle. A building with no street-facing wall gets one
    on its longest outside wall (counted in the summary).
11. **At ground level, by construction.** A door or shop front stands on the bottom of the wall outline at its
    position (LoD2 walls follow the ground); a shop front is at most 3.0 m high, below the first floor line. Both
    must fit inside the outline. A door inside a shop front is the shop's door.
12. **Windows give way.** Ground-floor windows a door or shop front overlaps (with a 0.2 m gap) are removed.
13. **Dormers:** later (owner, G0 review).

## Places of worship (owner's decision, 13 Nov 2026: "Fix facades first")

Code: `v2/data/scene/worship.py` (which buildings), `v2/data/scene/facades.py` (`join_walls`, `church_layout`),
`v2/data/fetch/worship.py` (stage `fetch_osm_worship`). Parameters: `params.json` facades, keys `worship_*` and
`church_*`. How they are drawn: layer-05-buildings.md; by night: layer-10-night.md rule 5.

14. **Which buildings.** From the data, never from a place in the picture, so it carries to the whole city:
    - OSM outlines: a way or a multipolygon relation tagged `building=church|cathedral|chapel`, or
      `amenity=place_of_worship`. A scene building belongs to it when the outline covers at least half its
      footprint, or the building holds at least half the outline (ACT often models a church and the convent,
      abbey or hospital it is part of as one building).
    - The landmark list: a landmark card of category "church"; the building that holds its point, or the nearest
      within 10 m.
    - `v2/data/structures/landmark_styles.json`: a building entered with `"kind": "place_of_worship"` (for a church
      OSM maps only as a point, as it does the cathedral).
    - Not enough: an OSM node `amenity=place_of_worship` alone (prayer rooms in ordinary houses are mapped so), and
      a site relation (a list of buildings, not an outline).
    - **Exceptions** (owner, 13 Nov 2026): an OSM outline listed in `v2/data/structures/worship_exceptions.json`
      (its id, the reason, the date, the owner's words) makes no building a church; its buildings keep the house
      rule. One entry: relation 11371126, the building beside St Michael's, tagged `building=church` with the
      note "transformation into flats?" (the owner: "Back to a house").
15. **Which walls.** With an OSM outline that covers less than half the building's footprint, the walls whose
    middle stands in the outline grown by 1.5 m: the church part of a larger building. The rest of that building
    keeps the house rule. Without an outline, or where the outline covers half the footprint or more
    (`worship_whole_share`), every wall: a church's tower or porch often stands outside the mapped outline (St
    Michael's tower did, and had house windows).
16. **Walls are joined first.** ACT gives many church walls in pieces (triangles), and no tall window fits a
    triangle. The church's walls that lie in one plane (normals within 2 degrees, 0.15 m apart at most) and touch
    are joined into one wall: a record of its own after every other wall, with `merged`, the walls it is made
    of. Party walls and walls that are not planar stay out. The pieces keep their records, without windows.
17. **The church rule**, on each joined wall, in place of rules 4 and 5: one row of windows, laid out by rules 23
    and 24 (round two). One row per wall: every sill on one line, every top on one line. A window is kept only if
    its rectangle grown by 0.2 m lies inside the wall's outline, and gives way to a door.
18. **The head.** The rectangle is the whole window; its head is round, or pointed where the building's entry in
    `landmark_styles.json` says `"windows": "pointed"` (the cathedral). A round head rises half the window's
    width above its springing line, a pointed one 0.866 of it.
19. **No shop fronts** on a church's walls. **Doors** stay where rules 7 and 10 put them. No shutters and no
    balconies are drawn (layer 5).
20. **What the house rule had given** each church wall is kept as a count (`house_rule`: its windows, doors and
    shop fronts). A window's glass tone (layer 5) and a night window's seed (layer 10) go by the opening's place
    in the order of all openings; the count keeps every other building's windows exactly as they were.

## Places of worship, round two (owner's decision, 13 Nov 2026: "One more round")

Code: `v2/data/scene/church.py` (the layout), `v2/data/scene/facades.py` (`build`, which calls it). Parameters:
`params.json` facades, keys `church_*`. Everything follows from the walls' outlines, their heights and the
church's footprint; nothing is placed by hand, so it carries to the whole city.

21. **The outward side of a church wall** is the side that lies outside the building's footprint (tested 0.4 m
    either side of the wall at three points). Where that does not tell (both sides inside, as for a nave wall
    over its aisle), it points away from the centre of the church part (the footprint inside the mapped outline),
    not of the whole building. A wall whose frame pointed inward is turned round; its doors keep their place.
    (Rule 1's centre of the whole footprint had St Jean du Grund's nave wall facing into the abbey.)
22. **A church wall is free where no other building's wall stands against it.** The outlines of other buildings'
    walls on its line (within 0.4 m, parallel, sharing 0.5 m or more) are cut out of its outline, grown by 0.3 m;
    what is left (parts of 4 m² or more) takes part in rule 16. So a nave wall that rises over a lower neighbour
    keeps its upper part, and a long wall with a short neighbour keeps the rest of its length. This replaces
    rule 2's party-wall test for church walls only. The piece keeps `party` and gets `party_free`, the share of
    it that is free.
23. **The row is sized to the wall.** The wall's bottom is the bottom of its outline that gives the row the most
    windows (a nave wall above its aisle starts on the aisle's roof). The free height Hf runs from there to the
    eave. The sill is 0.3 Hf above the bottom, at least 1.2 m and at most 2.6 m; the top is 1.0 m under the eave;
    a window is at most 12 m tall.
    - **A tall window** where that leaves 2.6 m or more: 0.26 of its height wide, at least 1.0 m, at most 2.6 m
      and at most 0.35 of the wall's length. Bays of 4.5 m, or the window's width plus 2.8 m if that is more,
      centred in each clear span, one window each. It is **traceried** (a mullion, two lights, a top light) from
      1.5 m wide and 4.5 m tall; narrower or lower it is a **lancet**.
    - **A round window** (oculus, 1.1 m across, its centre at 0.6 Hf) where the wall is too low for that but its
      free height is 3.4 m or more.
    - **None** on a lower wall. No small arches.
24. **Towers.** The church's main eave is the median height of its walls' tops, weighted by their length. A wall
    is a tower's when its top stands 8 m or more above that, it is at most 14 m long, and it is slender (twice as
    high as long) or stands on the roofs (its bottom no more than 2 m under the main eave) and is at least as
    high as long. A tower wall gets **belfry openings** near its top: 0.2 of the wall wide (0.7 to 1.5 m), 0.8
    of the wall's length tall (1.8 to 4.5 m), their top 1.2 m under the eave, never starting less than 0.5 m
    above the main eave; one, or a pair 0.7 m apart on a wall 5 m long or more. The wall's row stays 1.5 m under
    them. No clock.
25. **The entrance front**, one per church, told from the data in this order:
    1. the wall that holds an OSM door tagged `entrance=main`;
    2. the end of the footprint's long axis where a tower stands, if only one end has one;
    3. the end opposite the apse: the end where the footprint narrows (its width at 90 to 98% of the half
       length against its greatest width), if one end narrows by 0.15 more than the other;
    4. the end with a wall onto a street, if only one end has one;
    5. the largest wall that holds any door.
    At an end (2 to 4) it is the outermost wall that faces out along the axis (cosine 0.7 or more), lies in the
    outer 30% of the length, and can hold the portal. `facades.json` records how it was told for each church.
26. **The portal** stands on the ground in the middle of the entrance front (on the door's place for rule 25.1):
    0.28 of the wall wide, 1.6 to 3.4 m, and no wider than lets it be half the wall's height; 1.8 times as
    high as wide; it must fit the outline and stand no more than 3 m above the church's lowest wall bottom. It is
    a door of kind `portal` on the joined wall. A door it covers is dropped: the portal is that door and keeps its
    source (an OSM entrance stays placed). Windows within 0.5 m give way.
27. **The rose** stands over the portal, on its axis: the largest circle from 5.0 m across (and 0.4 of the wall)
    down to 2.2 m whose square fits the outline 1.0 m or more above the portal and 0.6 m under the top; placed
    in the middle of where it fits. No rose where none of 2.2 m fits.
28. **Buttresses** stand between the bays of a row of three tall windows or more, and half a bay outside its end
    windows, on a wall that is not a tower and is 6 m high or more: strips 0.9 m wide from the wall's bottom to
    three quarters up the windows, kept only where the strip lies in the outline, 0.4 m clear of every opening.
    Where ACT models the buttresses itself, each gap is a span of one bay and none is added.
29. **String course.** Every wall with tall windows has one 0.35 m under their sills; a wall without, 5 m high or
    more, has one where the sills would be.
30. **Windows carry their kind**: `[u0, v0, u1, v1, kind]`, kind one of lancet, traceried, oculus, rose, belfry.
    A round window's rectangle is the square round its circle.

**Output.** `facades.json`: the rule's parameters and per wall: building id, wall id, base (two 3D points), normal,
length, eave height, outline, floors, bays, party flag, reason for no windows, window rectangles (u0, v0, u1, v1),
the street it faces (or none), doors (u0, v0, u1, v1, source "osm:node/…" or "rule:…", kind door/garage) and shop
fronts (u0, v0, u1, v1, source); a church's walls also `worship` (round or pointed), `house_rule` and, on a joined
wall, `merged`, `tower`, `front`, `buttresses` (u0, v0, u1, v1) and `courses` (heights); plus the OSM entrances that could not be placed, with the reason, the commercial streets, and
`worship`: the places of worship by building id (source, name, the share of the footprint that is church, walls,
windows by kind, tower walls, buttresses, the main eave, and `front`: how the entrance front was told, portal,
rose); and `worship_exceptions`, the list of rule 14. `facades.window_world()` turns any rectangle into its four world corners.

**Checks.** F1 windows inside the outline · F2 gaps ≥ 0.3 m · F3 every window row on a floor line (straight rows,
still true with doors) · F4 no windows on party walls · F5 floor count fits the eave · F6 ≥ 90% of buildings ≥ 5 m
tall and ≥ 40 m² have a window · F7 counts (report) ·
(F3 on a church's wall: one row, every sill on one line and every top on one line) ·
**F8** every building with a street-facing wall has a door on one · **F9** no door or shop front on a party (shared)
wall · **F10** shop fronts only on the ground floor (≤ 3.2 m above the wall's bottom) · **F11** doors and shop fronts
inside their wall outline · **F12** doors and shop fronts stand on the bottom of their wall (the ground) · **F13** no
window overlaps a door or a shop front · **F14** ≥ 90% of the OSM entrances at a building are placed as doors (the
rest listed with their reason) · F15 doors and shop fronts by source (report) · **F16** every window on a church
wall is the church rule's (its kind's width for its height and wall) · **F17** none lower than its kind's least
height, none reaching into the eave ·
**F18** no shop front on a church wall · **F19** every church wall belongs to a listed place of worship, and every
listed place has a church wall · F20 places of worship by source, church walls and windows, house windows replaced
(report) · **F21** one entrance front per church, the rose only over its portal · **F22** belfry openings only on
tower walls, above the main eave · **F23** buttresses upright, one width, one top line, inside the outline, clear
of openings, never on a tower · **F24** no church wall's normal points into the footprint · F25 per church: how
the front was told, windows by kind, towers, buttresses, exceptions (report). On layer 5: **L5.7**, **L5.8**
(layer-05-buildings.md).

**Known limits** (bake-off): dormer windows on roofs (the installations are there), irregular historic rows, shop
signs. Churches: the rule is a layout, not a survey. It knows no nave, aisle or choir: a wall is a tower's or not,
and every other wall is laid out by its own height and length. The entrance front is told from an OSM main
entrance where there is one, else guessed from the tower, the apse and the street; a church whose door is in its
side is given a portal at an end. The rose, the tracery and the buttresses are one pattern for every church. A
buttress is drawn on the wall, not built: it has no depth and casts no shadow. Short facets of a round apse
(under 2.2 m) get no window. A church OSM does not map as a building, and that no list names, stays a house. The
rule gives straight, plausible openings; the owner judges the look.
