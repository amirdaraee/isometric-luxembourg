# Landmark cutaways ("slice of cake")

**Status:** spec only (owner's decision, 9 Nov 2026). Built in Phase 3 on the test area; the AI interiors are paid
from the Phase 3 line ($8 cap), quoted in the ledger and approved by the owner before any spend.

**Purpose.** Famous buildings shown cut open in place on the map, not in a modal: the visitor sees a slice taken out
of the building, with its interior visible through the cut, at its real place and scale. First four: the Bock
casemates, Notre-Dame Cathedral, the Grand Ducal Palace and Neumünster Abbey (all four are inside the test area).

**Inputs.**
- The building's 3D model (ACT LoD2 in the scene; for the Bock casemates, the gallery data of tunnel-view.md).
- A cut: one or two vertical planes per landmark (data, `v2/data/structures/cutaways.json`: plane origin, normal and
  extent, chosen once by hand so the cut shows the best-known rooms: the cathedral's nave, the palace's state rooms,
  the abbey's cloister, the casemates' galleries).
- The interior: an AI-painted cutaway image per landmark, made from an unlit render of the cut model (the cut faces
  and the inside walls from the model, flat colours) with a reference of the real interior (public photos, used as
  reference only), in the inked style, unshadowed.
- The palette and the bake-off winner's style for the outside.

**Rules.**
1. **The cut comes from the model.** The removed slice is the model clipped by the cut planes; the cut faces are the
   model's section. Nothing is drawn where the model is not.
2. **The interior stays inside the cut.** The painted interior is masked to the cut's section and the inside faces
   it exposes (the 3D outline of the opening, the POC cut rule with 0 px growth); it never covers the outside of the
   building or the map around it.
3. **No baked light.** The interior is painted evenly lit, as layer 5; layer 9 lights it (the opening's own shadow is
   cast by code).
4. **Nothing that moves.** No people, cars or animals painted inside or outside (principle 5); the visitors and
   events are code layers.
5. **In place.** The cutaway replaces that building's pixels in layer 5 (or a small layer above it) with its own
   depth, so vehicles, labels and trees are depth-tested against it as against any building. A toggle (or a hover)
   shows it; off, the building is whole.
6. **Prove one, then three.** One landmark first (the cathedral); the other three only after the owner approves it.

**Checks** (phase 3, gates on the test area).
- **K1** The cut matches the 3D model: the drawn cut's outline is within 1 px of the projected section of the model by
  the cut planes over ≥ 95% of its length (the line score of brief 6); 0 cut pixels outside the model's outline.
- **K2** The interior stays inside the cut: 0 interior pixels outside the opening's mask; ≥ 99.5% of the mask
  covered.
- **K3** No baked shadows: the shadow detector of brief 5 on the interior (sunlit vs shadowed sides of the same
  material within 5%), and the opening's shadow moves with `?hour` (L9.1 on the cut).
- **K4** No cars or people: the vehicle detector (OWLv2, as #9) on every input, reference and output at
  threshold 0.1, plus a person query ("a person", "people"): 0 detections.
- **K5** Depth: the cutaway's depth equals the model's (cut faces and inside walls) per pixel (≤ 1 cm); vehicles and
  labels depth-tested against it (as C4).
- **K6** Off means off: with the cutaway off, the building's pixels equal layer 5's (0 differ).
- **K7** (owner) the four cutaways at fixed views.

**Cost.** Estimated in `v2/docs/PHASE2_QUOTE.md` as a separate Phase 3 item (not part of the bake-off total).
