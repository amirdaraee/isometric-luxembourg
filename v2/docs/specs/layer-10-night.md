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
4. The night's own light (owner, 10 Nov 2026; `light.json` "grade" and "night"), all in the viewer's light pass:
   - the sky light is a deep blue (`night_tint` × `night_level`: about 0.20, 0.25, 0.43 of an evenly lit colour), so
     nothing is black and every material keeps its place in the picture;
   - a moon gives the shapes: one soft light from a fixed place in the sky (`moon_az_el_deg`: south-south-west, 40°
     up; a drawn moon, not the real one's position), `moon_direct` 0.40, with cast shadows from the same height map
     as the sun's that take away 78% of it. It comes in as the sun goes from 1° to 6° below the horizon;
   - colours lose 22% of their saturation (`night_desaturate`), as they do by moonlight;
   - lit windows glow: each has a warm halo on its wall (`window_halo`, the rectangle grown by 1.4 times its size,
     fading out); lamps are larger and stronger (`lamp_radius_px` 44, `lamp_gain` 1.5).

5. **Places of worship** (owner, 13 Nov 2026): a church's arched windows are not lit like a flat's. A church is
   lit or dark as a whole building, as often as a home's window at that hour. Lit, each window shows a dim glow of
   stained glass inside its arch: panes in the palette's four stained colours (`buildings.stained_*`), dark lead
   lines between them, at `night.church_glow` (0.42) of a house window's strength, with no halo on the wall. Dark,
   nothing is drawn. A church's doors are not lit. In `windows.bin` a church window has kind 8 (round) or 9
   (pointed); kind 16 is a row that is never lit (it keeps the place of a window the house rule had on a church
   wall, so every other window's seed, its row number, stays the same).

**Checks.**
- L10.1 (gate) Every lit window lies on a window rectangle of the facade layout (straight rows by construction).
- L10.2 (gate) No light drawn at sun elevation > 0°.
- L10.3 (gate) Lamps hidden behind nearer surfaces per depth (0 lamp glow pixels over a nearer surface).
- L10.4 (owner) Code night vs AI-painted night of the same views (G3).
- L10.5 (unit test, `v2/web/src/grade.test.ts`) The night's sky light is blue (blue over 1.8 times red) and between
  0.2 and 0.45 of day's in luminance; the moon is up.
