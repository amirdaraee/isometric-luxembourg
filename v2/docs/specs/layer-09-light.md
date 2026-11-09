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
3. Sky grade by sun elevation: golden hour 0–6°, blue hour −6–0°, night below −6° (sun.json presets).

**Checks.**
- L9.1 (gate) Shadows move with `?hour`: the shadow direction measured from building edges matches the sun azimuth
  within 10° at 08:00, 13:00 and 19:00 (brief 5).
- L9.2 (gate) No ghost shadows: on the albedo layers, the mean brightness inside the 3D shadow mask for the
  orthophoto's sun is within 5% of the lit ground next to it.
- L9.3 (gate) Speed: lighting pass ≤ 4 ms per frame on a mid phone at the reference view.
- L9.4 (owner) Golden hour by code vs an AI-painted golden hour of the same view (G3).
