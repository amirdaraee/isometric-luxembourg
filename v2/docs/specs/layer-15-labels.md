# Layer 15: Labels, pins, search, hover

**Purpose.** Names, landmark pins and cards, search and hover, decluttered (Tehran-style priority by zoom). **Made
by:** code (v1's viewer pins, cards and search, kept and improved).

**Inputs.** Scene places (`places.json`: v1's 129 landmark cards and 1,035 places, now in LUREF with v2 pixels and
v1 pixels for links), layer 8 id tiles (hover), the graph (street names), quarters (`commune_quarters.geojson`).

**Output.** Label and pin lists per zoom (JSON), drawn by the viewer; no text in any art layer.

**Rules.**
1. Labels are never baked into tiles (OTHERS P8).
2. Priority by zoom with collision culling on the projected label box; landmarks first, then quarters, streets.
3. A pin stands at its place's v2 pixel at the terrain height; it is hidden when its ground point is behind a nearer
   surface (depth).
4. v1 links (`?x=&y=` in v1 pixels) keep working through `camera.v1_to_v2_px`.

**Checks.**
- L15.1 (gate) Every place round-trips to its v1 pixel (PL1, PL2a) so links carry over.
- L15.2 (gate) No two visible labels overlap at any zoom of the reference views.
- L15.3 (gate) Hover returns the right object on 50 fixed test points.
