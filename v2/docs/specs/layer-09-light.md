# Layer 9: Light — sun shading, cast shadows, sky grade

**Purpose.** Daylight that moves: shading from the surface direction, cast shadows from the 3D model for the sun's
real position, and the colour of the hour. **Made by:** code, in the viewer (WebGL), from layer 8.

**Inputs.** Layer 8 (depth, normal, height), the sun model (`v2/config/sun.py`: NOAA position for Luxembourg,
`direction_screen()` in the camera frame), shadow-map tiles (pre-rendered depth from the sun's direction for a set
of sun positions per season, or rendered in the viewer from the depth buffer for the visible area), palette
(`light.*`).

**Output.** A multiply/screen pass in the compositor; optional pre-baked shadow-map tiles per sun position.

**Rules.**
1. Lambert shading of albedo from the normal and sun direction, softened (wrap lighting) to stay "drawn".
2. Cast shadows: a pixel is in shadow when the shadow map from the sun sees a nearer surface; shadows are tinted
   (palette `shadow_tint`), never black.
3. Sky grade by sun elevation: golden hour 0–6°, blue hour −6–0°, night below −6° (sun.json presets). The numbers
   are `v2/config/light.json` "grade"; the viewer turns them into the light pass's inputs in
   `v2/web/src/gl/grade.ts`. Nothing of this is in any layer's tiles: layers 1–7 stay evenly lit (L5.1, L9.2).
4. **Day** (sun above 6°) is one constant: `sun.ambient` 0.58 of white sky light, `sun.direct` 0.62 of the sun's
   tint, hard cast shadows. The golden hour and the night change nothing here.
5. **Golden hour** (owner, 10 Nov 2026: brighter and warmer, long soft shadows, buildings readable). Full from 3.5°
   down to the horizon, easing into day between 3.5° and 6°:
   - the sun is orange (`golden_tint`) and 1.3 times as strong;
   - the sky light is warm (`golden_amb_tint`) and 1.5 times day's, so the shaded side of the valley is not murky;
   - a fill light (`golden_fill`, 0.28) comes from the sky opposite the sun, 35° up, so faces turned away from the
     sun still show their shape (most walls the camera sees at sunset are turned away from it);
   - cast shadows keep the sun's real direction and length, and fade with the distance to what casts them: full
     within 6 m, down to 15% of their strength from 70 m (`golden_shadow_soft`, `shadow_soft_m`). Without this a
     3° sun puts the whole valley in one shadow. The shadow mask the checks compare (V2, V3) is the unfaded one.
6. **Blue hour** (0° to −6°): the sun's own light is gone at the horizon; the warm sky cools to `blue_tint` by −3°
   and deepens to the night's by −6°. No value steps anywhere between day and night (unit test `grade.test.ts`).
7. **Night** (owner, 10 Nov 2026: readable, a deep blue and not black, moonlit): see layer 10 rule 4.

**Checks.**
- L9.1 (gate) Shadows move with `?hour`: the shadow direction measured from building edges matches the sun azimuth
  within 10° at 08:00, 13:00 and 19:00 (brief 5).
- L9.2 (gate) No ghost shadows: on the albedo layers, the mean brightness inside the 3D shadow mask for the
  orthophoto's sun is within 5% of the lit ground next to it.
- L9.3 (gate) Speed: lighting pass ≤ 4 ms per frame on a mid phone at the reference view.
- L9.4 (owner) Golden hour by code vs an AI-painted golden hour of the same view (G3).
- L9.5 (unit test, `v2/web/src/grade.test.ts`) Day is untouched by the golden-hour and night settings; golden hour
  is brighter and warmer than day's sky light; no value jumps by more than 0.012 per 0.01° from 8° to −9°.
