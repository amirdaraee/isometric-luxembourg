# Layer 13: Events

**Purpose.** The Schueberfouer, Christmas markets, National Day and the other events of v1's research, as placed
objects that come and go with the calendar. **Made by:** code placement + small AI sprites (painted once, unlit,
like layer 5).

**Inputs.** v1's event research (23 events: places, dates, rides and stalls), the scene (terrain heights, places),
the calendar.

**Output.** Sprite placements (position, height, footprint, depth) per event and date; sprites as small RGBA sheets.

**Rules.**
1. Events are objects keyed to geometry (positions in LUREF), never patches of a map version's pixels (V1_RETRO P7).
2. Every object stands on the terrain or a deck and is depth-tested like vehicles.
3. Sprites follow layer 5's rules (albedo, no shadow, no cars or people).

**Checks.**
- L13.1 (gate) Event layers render identically before and after any rebuild of the base layers (they depend on
  geometry only).
- L13.2 (gate) Every placed object is inside its event's area polygon and on visible ground or deck.
- L13.3 (gate) No cars, people (beyond the drawn crowd style decided at G3) or shadows in sprites.
