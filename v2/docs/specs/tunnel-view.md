# Tunnel view (x-ray)

**Status:** built in Phase 3 on the test area (owner's decision, 9 Nov 2026), $0, code only. The gate is the build
stage `check_tunnel_view`; "How it is built" and "The checks as built" below say what the code does.

**Purpose.** Let a visitor see what runs underground: a toggle (button, or a held key) fades the city layers so the
tunnels show at their real place and depth, with the trains, trams and cars moving inside them. The Bock casemates
may be shown the same way.

**Made by:** code, in the viewer (compositor.md), from data the build already has.

**Inputs.**
- The transport graph (`graph.json`): every edge with `structure = tunnel` (and `indoor` / `passage` where they are
  underground), its 3D polyline and height profile, width, clearance (`clearance_m`) and portals.
- The vehicles (layer 12): the simulation already drives them through tunnels at the tunnel's profile; today they are
  hidden there by the depth test (L12.1).
- The Bock casemates, if shown: a hand-modelled set of galleries as data (`v2/data/structures/casemates.json`, Phase 3,
  from published plans), like the viaducts in Phase 0. Optional; the toggle works without them.
- Layer 8 (depth) and the layer toggles (`?off=`).

**Rules.**
1. **Geometry from the graph only.** Each tunnel is drawn as a tube (or box) of its width and clearance around its
   profile, from portal to portal; nothing is placed by eye. Casemates likewise from their data.
2. **A separate layer.** The tunnels are their own tile-less layer (meshes drawn in the viewer, or a small built
   tile set): no colour layer changes. Turning the view off leaves the map pixel-identical to before.
3. **The fade.** With the view on, layers 1–7 are drawn at a fixed opacity (default 0.35) over a neutral ground
   colour; light, night and the look pass still apply to them. Tunnels are drawn after them, unlit, in one ink-and-
   colour style (palette `tunnel.*`), with their depth below the surface shown by a darker tone per 10 m.
4. **Vehicles in tunnels.** With the view on, vehicles inside a tunnel past its portal are drawn (depth-tested
   against the tunnel meshes only, so a train behind another tunnel is still hidden by it); vehicles on the surface
   are drawn faded like the city. With the view off, L12.1 holds as before.
5. **Works with the toggles.** Every `?off=` layer stays off in tunnel view; the toggle state is in the address
   (`?xray`), so views are repeatable.
6. Nothing painted: the view is code only and costs nothing.

**Checks** (phase 3, gates on the test area).
- **X1** Tunnels in the right place: every tunnel edge's drawn centre line is within 1 px of the projection of its
  graph profile over ≥ 99% of its length (the line-score method of brief 6).
- **X2** Right depth: at every sample, the tunnel's drawn depth equals the profile's depth (≤ 1 cm in the depth
  buffer); its depth below the terrain (terrain − profile) matches the graph's cover to ±0.5 m.
- **X3** Vehicles only inside tunnels: in tunnel view, every vehicle pixel drawn at full opacity belongs to a vehicle
  whose position is on a tunnel edge past a portal; 0 others. Over a simulated day (as V0), every vehicle sample in a
  tunnel is drawn (none lost) and none sticks out of its tube (all its pixels inside the tube's screen footprint).
- **X4** The fade leaves no artefacts: with the view off, the frame equals the frame before the view was ever turned
  on (0 pixels differ); with the view on, layers 1–7 differ from the faded reference render (same views, offline) by
  ≤ 1/255 per channel; no seams at tile borders (seam check on the faded frame).
- **X5** Works with the layer toggles: for each `?off=` layer, tunnel view shows no pixel of that layer (as V1) and
  the tunnels and their vehicles are unchanged.
- **X6** Portals agree: where a tunnel leaves the open, its tube ends at the portal drawn by layer 4 (within 1 px).
- **X7** (if casemates are shown) every casemate gallery from its data, inside the Bock's rock (its top ≥ 1 m under
  the terrain), and drawn only in tunnel view.
- **X8** Speed: turning the view on or off takes ≤ 1 frame; panning in tunnel view ≥ 60 fps on desktop (as C2).

## How it is built

- **Data.** Stage `layer_tunnels` (`v2/layers/tunnels.py`) writes `tunnels.json` into the release: one *tube* per
  tunnel edge of the graph that touches the area (and per indoor or passage edge whose clearance lies under the
  ground on half its samples or more: one in the test area). A tube is the edge's own polyline and profile, its
  width and clearance, its depth under the surface per sample (the graph's cover minus the profile), and how far each
  sample is into the tunnel. The casemate galleries of `v2/data/structures/casemates.json` are tubes of the same
  shape. `release` links the file and names it in `index.json` (`tunnels`).
- **Mesh** (the same rule in `v2/layers/tunnels.py` and `v2/web/src/tunnels.ts`). Per segment: the floor, and each
  wall whose inside faces the camera; nothing nearer is drawn, so what is in a tube is seen in it. A tube ends at
  the face of the portal layer 4 draws (0.3 m out of the end node). Where tubes join at a node, a wall is left out as
  far as it runs inside another of them, so a junction is open.
- **Viewer** (`v2/web/src/gl/compositor.ts`). With the view on, the look pass writes the city at opacity 0.35 over
  the neutral colour `tunnel.ground`; then the tubes are drawn unlit with their own depth buffer (fill, darker far
  wall, ink on the edges, the profile as a centre line; one step darker per 10 m under the surface, 6 steps at most);
  then the vehicles that are in a tunnel past its portal, tested against the tubes' depth only. The vehicles of the
  surface are in the city's frame as before, so they fade with it. With the view off none of this runs: the frame is
  the frame of before.
- **Controls.** `?xray` in the address, the button "Tunnel view" in the panel (it writes `?xray` into the address),
  or X held down (it shows the other state while held). `?off=casemates` leaves the casemates out.
- **Constants.** `v2/config/light.json` `xray` (opacity, depth steps, line widths); colours `tunnel.*` in
  `v2/config/palette.json`; thresholds in `v2/config/params.json` `g3`; build parameters in `tunnels`.

## The casemates (rule 1, X7)

`v2/data/structures/casemates.json` is an approximate hand model, to be reviewed, not a survey: the main gallery
(110 m, published) and 25 gun branches (12 north, 13 south, published), on one level. Their place, level and section
are assumptions, listed in the file; each branch stops where 1 m of rock still covers its top. The transport graph
also holds the casemates' passages as OpenStreetMap maps them (84 path tunnels, 694 m): the tunnel view draws both.

## The checks as built

`python -m v2.build test check_tunnel_view` (`v2/checks/tunnel_checks.py`, with `v2/web/scripts/xray_checks.mjs` and
`xray_audit.ts`). The viewer runs headless at views that together hold every tube at 1 screen px per map px; its
debug frames (`?debug=xid`: class, depth step and tube per pixel; `?debug=xdepth`: the tubes' depth buffer) are
compared with the graph itself.

| Check | What is measured |
|---|---|
| X0a, X0d | every tunnel edge of the area has its tube, with the edge's width and clearance; the viewer's mesh is the reference mesh |
| X1 | per tunnel edge, samples of its graph profile every 0.5 m: the drawn centre line within 1 px, over >= 99% of the samples seen (not behind a nearer tube, not where two floors meet) |
| X2 | at the same samples: the depth buffer against the depth, at that pixel, of the floor built on the graph's profile (<= 1 cm); X2b the tube's depth under the surface against the graph's cover (<= 0.5 m); X2c the drawn tone is that cover's step |
| X3a | still frames at two hours: every vehicle pixel of the tunnel pass lies on a vehicle that is in a tunnel past its portal |
| X3b, X3c | a simulated day, every 20 s: the vehicles the viewer draws in tunnels are exactly those the graph puts past a portal (0 others, 0 lost) |
| X3d | the same day: 0 pixels of those vehicles outside the tubes' footprint on screen. X3e (reported): pixels behind a tunnel face |
| X4a | view off after it was on = the frame before it was ever on (0 pixels), day and night |
| X4b, X4c | view on: city pixels = the plain frame faded offline (<= 1/255); no step added at tile borders |
| X5 | per `?off=` layer in tunnel view: 0 pixels of that layer; tubes and vehicles unchanged; the city is the faded frame without it |
| X6 | per portal layer 4 draws: the drawn tube ends at the portal's face, and layer 4's portal pixels lie in that face (<= 1 px) |
| X7 | casemates: as X1 and X2 from their data; >= 1 m of rock over every gallery; 0 pixels with the view off or `?off=casemates` |
| X8 | turning the view on or off: 1 frame; panning in tunnel view >= 60 fps (desktop) |
