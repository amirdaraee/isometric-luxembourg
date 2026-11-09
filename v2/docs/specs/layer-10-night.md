# Layer 10: Night lights

**Purpose.** Night: lit windows, street lamps, vehicle lights and a soft glow. **Made by:** code; a thin AI lights
layer only if the owner prefers it at G3 (PLAN_V2 section 9).

**Inputs.** The facade layout (window positions per wall, `facades.json`), OSM street lamps (`highway=street_lamp`
in `fetch_osm_ground`), layer 8, the sun model (night = elevation < −6°).

**Output.** Point and quad lists (tiled JSON or binary per tile): windows with a lit probability, lamps with
height and colour; the viewer draws them with glow.

**Rules.**
1. A window is lit with a probability by building use and hour (homes evening, offices day), seeded per window so
   it is stable; some windows always dark.
2. Lamps at their OSM position and the terrain/deck height + 5 m; glow is depth-tested (a lamp behind a building
   is hidden).
3. Nothing is lit by day.

**Checks.**
- L10.1 (gate) Every lit window lies on a window rectangle of the facade layout (straight rows by construction).
- L10.2 (gate) No light drawn at sun elevation > 0°.
- L10.3 (gate) Lamps hidden behind nearer surfaces per depth (0 lamp glow pixels over a nearer surface).
- L10.4 (owner) Code night vs AI-painted night of the same views (G3).
