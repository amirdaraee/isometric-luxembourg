# Palette

`v2/config/palette.json` is the one palette (OTHERS 7.3.1). Code layers draw with it; the bake-off's AI layers get
it as a reference image; layer 14 grades towards it.

- **Groups:** ink, ground classes, relief, water, transport, structures, buildings (for A's code buildings and B's
  materials), trees (summer, conifer and red-leaved, dark and light ends), cutaway (the placeholder interior of the
  landmark cutaways: section, inside wall, inside roof, floor, slab), light (shadow tint, golden, night sky).
- **Starting values** are v1's, each with its source (`draw_ground.py` FALLBACK, `v2_ink.py`, `v2_canopy.py`,
  `build_bridges.py`); new entries (rock, building materials, light) are marked "v2".
- **Tuning** happens once, at gate G3, on the test area, by the owner's eye at fixed views; then the values are
  frozen for production. A palette change rebuilds the code layers (it changes their stage keys) and never touches
  painted layers.

**Checks.** P-1 (gate, phase 1) every colour a code layer draws is a palette colour or a grain/blend of palette
colours (no stray constants in layer code; a grep gate on RGB literals in `v2/layers`).
