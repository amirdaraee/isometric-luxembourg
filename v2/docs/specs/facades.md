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

**Output.** `facades.json`: the rule's parameters and per wall: building id, wall id, base (two 3D points), normal,
length, eave height, outline, floors, bays, party flag, reason for no windows, and window rectangles (u0, v0, u1,
v1). `facades.window_world()` turns a rectangle into its four world corners.

**Checks.** F1 windows inside the outline · F2 gaps ≥ 0.3 m · F3 every window row on a floor line (straight rows) ·
F4 no windows on party walls · F5 floor count fits the eave · F6 ≥ 90% of buildings ≥ 5 m tall and ≥ 40 m² have a
window (the rule is not too strict) · F7 counts (report).

**Known limits** (Phase 1 / bake-off): shop fronts and doors on ground floors, dormer windows on roofs (the
installations are there), churches and towers (landmark portraits in B/C), irregular historic rows. The rule is a
layout, not a survey: it gives straight, plausible windows; the owner judges the look at G2.
