# Layer 11: Seasons and weather

**Purpose.** Spring, summer, autumn and winter; snow, rain and fog. **Made by:** code in the viewer.

**Inputs.** Layers 7 (crown mask, tree types), 8 (normals, depth), 1 (ground classes), the date (season), live or
test weather.

**Output.** Colour transforms of layer 7 and layer 1's green classes per season; a snow pass on up-facing
surfaces; rain and fog as screen effects with depth.

**Rules.**
1. Seasons change only trees and green ground: spring fresh green and blossom, autumn colours by tree type
   (deciduous_red redder), winter bare (crowns thinned to branches) — positions never change.
2. Snow on surfaces whose normal is within 40° of up, not under crowns or decks (depth).
3. Fog by depth (nearer is clearer).

**Checks.**
- L11.1 (gate) For every season, pixels outside the tree, green-ground and snow masks are identical to summer
  (diff = 0).
- L11.2 (gate) Canopy hue and saturation stay within the per-season bounds (spring ≤ +10% saturation over summer:
  v1's "acid green").
- L11.3 (gate) No snow on walls (normal > 40° from up) or under decks.
