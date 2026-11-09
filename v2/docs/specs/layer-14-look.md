# Layer 14: Final look — grade and ink

**Purpose.** One palette grade and one ink pass over the composite, so code and AI layers read as one drawing
(OTHERS 7.3: Toronto's Grade B, Berlin's colour restore). **Made by:** code, in the viewer (shader).

**Inputs.** The composite of layers 1–13, layer 8 (depth and normal discontinuities for ink), the palette, the
hour (grade per time of day).

**Output.** The final pixel. No tiles.

**Rules.**
1. Grade: saturation, contrast and gamma towards the palette, the same on every layer (no per-layer tweaks).
2. Ink: edges found on layer 8's depth and normal discontinuities (not on colour) darkened to ink with a fixed
   weight at each zoom, so line weight is the same on code and painted pixels.
3. Paper grain and a slight edge wobble are allowed only if the line score (L5.2) still passes.

**Checks.**
- L14.1 (gate) Applying the pass twice changes nothing beyond rounding (it is a fixed transform, not a repaint).
- L14.2 (gate) No tone step at layer joins: LAB ΔE ≤ 3 across code/AI boundaries of the same material.
- L14.3 (gate) Speed: ≤ 3 ms per frame on a mid phone.
- L14.4 (owner) The test area reads as one drawing at fixed views (G3).
