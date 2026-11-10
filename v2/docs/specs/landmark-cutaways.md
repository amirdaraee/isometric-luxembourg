# Landmark cutaways ("slice of cake")

**Status:** the free part is built for three landmarks on the test area (Phase 3): the cuts as data, the slice
geometry from the 3D model, a small layer of tiles with a **code placeholder interior**, the inputs of the later
painting, and checks K0-K6 as far as they run without paintings (stages `layer_cutaways`, `check_cutaways`). Not
built yet: the painted interiors (paid from the Phase 3 line, $8 cap, quoted in the ledger and approved by the owner
before any spend), the viewer's toggle, and the Bock casemates (they wait for the gallery data of tunnel-view.md).

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

## Built (Phase 3, $0)

Code: `v2/layers/cutaways.py`. Data: `v2/data/structures/cutaways.json`. Checks: `v2/checks/cutaway_checks.py`.
Numbers: `params.json` "g3", keys `cutaway_*`. Colours: palette `cutaway.*`.

**The three cuts** (each documented in cutaways.json, with the reason):

| Landmark | Scene building | Planes | What it opens |
|---|---|---|---|
| Notre-Dame Cathedral | `ACT_e92ec91a…` | 2: along the nave's middle (facing east), across it 7 m short of the north front (facing south) | The east half of the nave, between the towers and the north front |
| Grand Ducal Palace | `ACT_78c0048b…` | 2: a quarter taken out towards the camera, its point in the main wing (facing east and south) | The main wing and the middle wing in section, with their floors |
| Neumünster Abbey | `ACT_221c9194…` | 2: along the middle of the church (facing the camera), and the side of a passage as wide as the court | The church lengthwise, the cloister's court and wing, the block in front in section |

A plane is an origin, a normal into the removed slice and an extent along it. The slice is what lies in front of
every plane, within every extent, above the floor. The buildings are found from the landmark's place (the footprint
that holds it, or the nearest within a stated distance); check K0 holds the list to that.

**Thickness.** ACT's model is a hollow shell, so a section would have no area. It gets a nominal thickness:
walls 0.8 m (in plan, from the footprint inwards), roofs 0.4 m (straight down), slabs 0.3 m at the facade layout's
floor lines (ground + 3.6 m, then every 3.0 m; none in the cathedral, none in the abbey's church). The floor is at
the landmark's floor level; below it the model is solid. Under a roof steeper than 80° (a spire) the model is solid.
A wall that stands on a lower roof (a tower's side above a nave) keeps ACT's one surface, without thickness.

**The layer.** One tile set per landmark, in the release's tile coding, above layer 5:
- colour: the kept outside exactly as layer 5 draws it (method A's materials); the cut faces and the inside faces in
  five flat palette colours with ink where surfaces meet. This is the placeholder a painting replaces;
- depth and normals of the cut model; ids (cut and inside faces have classes of their own, 40-44);
- `k`, what each pixel is: outside, cut, inside wall, inside roof, floor, slab, other building. The **opening mask**
  is cut + inside wall + inside roof + floor + slab;
- other buildings where they are nearer than the cut model or seen through the slice: layer 5 holds only the nearest
  building per pixel, so the cutaway brings what its landmark hid;
- `index.json`: per landmark the building ids it replaces, its planes, tiles and pixel counts.
Nothing is drawn outside the whole landmark's own silhouette.

**Paint inputs** (`paint/<name>.*`): the unlit render of the cut model alone on paper, 1024 × 1024 px at 0.125 m per
pixel (one image pixel per map pixel), the opening mask, the whole model's outline, the geometry behind every pixel,
and a JSON with the frame.

**Previews** (`v2/docs/img/test_cutaway_<name>_placeholder.jpg`): the whole building beside the cut one.

**Checks as built** (`python -m v2.build test check_cutaways`; all gates unless marked):

| Id | What is measured | Test area |
|---|---|---|
| K0 | The listed buildings are the scene's at the landmark's place | 3 of 3 |
| K1a | Line score of brief 6 on the model's section (raw ACT triangles cut by the slice's faces, every 0.25 m): drawn line within 1 px, >= 95% | 100%, 100%, 99.8% |
| K1b | Cut and inside pixels outside the whole model's outline (0 px growth): 0 | 0, 0, 0 |
| K2a, K2b | Interior pixels outside the opening mask: 0; mask covered >= 99.5% (the placeholder today, a painting later) | 0; 100% |
| K2c, K2d | The mask against the model worked out a second time, per pixel: mask pixels that are not an inside face or a section within 1 cm: 0; the model's own opening in the mask >= 99.5% | 0; 100%, 99.99%, 99.93% |
| K2e | Opening pixels of the tiles missing from the paint input's mask, or at another depth: 0 | 0, 0, 0 |
| K3 | Shadow detector on the interior: median luminance of one kind of face turned different ways, and to and away from the photo's sun, within 5% | 0% (flat colours) |
| K4 | OWLv2 on the paint inputs and the cutaway tiles: vehicles, then "a person", "people": 0 at 0.1 | 0; highest score 0.012 |
| K5a | Cut pixels: distance of the depth from the slice's faces <= 1 cm | 0.5 cm (the tiles store whole cm) |
| K5b | Cut and inside pixels not on the model's surface within 1 cm: 0 | 0, 0, 0 |
| K5c | Kept outside: depth differs from layer 5's by > 1 cm where layer 5 shows the same surface: 0 | 0 of 363,000 |
| K6a | Files of the cutaway layer in layer 5's folder: 0 (a layer of its own; no stage writes into layer 5) | 0 |
| K6b | Cutaway pixels where layer 5 shows neither a replaced building nor another building in front: 0 | 0, 0, 0 |
| K-ground (report) | Opening pixels the ground layer covers | 0, 0, 0 |

**Left for the viewer step:** the toggle; K3's shadow of the opening moving with `?hour`; K5's vehicles and labels
depth-tested against the cutaway; K6 in the browser (off: the picture equals layer 5's). **Left for the painted
step:** K2a, K2b, K3 and K4 on the paintings and their reference photos (the same functions); K7.

**Known limits.** The inside is a hollow shell with nominal walls: no rooms, vaults or columns until it is painted.
Walls on lower roofs have no thickness. Windows are not openings in the inside faces.
