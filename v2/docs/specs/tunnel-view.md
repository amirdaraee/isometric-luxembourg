# Tunnel view (x-ray)

**Status:** spec only (owner's decision, 9 Nov 2026). Built in Phase 3 on the test area, $0, code only.

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
