# Isometric Luxembourg v2: owner decisions

Decided on 9 November 2026, before the research and the plan. The plan (PLAN_V2.md) builds on these; changing
one is a decision for the owner, written here with its date.

## Goals (the owner's brief)

1. Do it properly: no patching and moving forward. A failing result goes back to the layer that made it.
2. Learn from the other isometric city maps first (research/v2/OTHERS.md).
3. Luxembourg is small, so aim for higher quality than v1.
4. Build on the layered proof of concept (LAYERS_POC.md): every part of the map is its own layer.
5. No shadows baked into the paintings.
6. Windows and straight lines must be straight.
7. Roads, streets, train and tram tracks in the art must match the data exactly.
8. Tunnels (and bridges) must be right for vehicles.
9. No cars painted into the art.
10. Understand what went wrong in v1 (research/v2/V1_RETRO.md) so no step is repeated.

## Decisions

| Topic | Decision |
|---|---|
| Area | The whole City of Luxembourg (all 24 quarters of the commune). |
| Art method | Layers, with AI only where it does best: ground, roads, rails, water, shadows, lights and vehicles drawn by code from the data in the hand-drawn style; buildings (and possibly trees and cliffs) painted by AI on clean, unshadowed inputs with transparent backgrounds; all composited. |
| Look | Keep the inked style of v1, with more detail and crisper lines. |
| Code home | Same repo and site; v2 built in a fresh structure on a `v2` branch, reusing only what passes review. v1 stays live until v2 is better. |
| Shadows | Computed from the 3D model for the sun's real position, moving through the day, a separate layer. |
| GPU budget | Up to about $100 in total, each step quoted and approved separately. |
| Launch scope | Day, golden hour and night; moving traffic, trams and trains; all four seasons; events and weather. |
| Process | Spec with acceptance checks first, then every layer on one small test area, owner approval, then the whole city. |
| Night, golden hour, seasons | Relit by code from the 3D model's normals and depth over evenly lit art (no repainting), with window glow, lamps and lights as code layers. Compared on the test area with an AI-painted version; AI only for a thin lights layer if code falls short. |
| Art method bake-off (9 Nov) | On the test area, compare side by side: **A** everything drawn by code; **B** code draws the map, AI only makes reusable materials (roofs, walls, windows, trees) and portraits of the 30–60 landmarks; **C** code layers plus AI-painted buildings. The owner picks from the results; the plan must work for any winner. This replaces the earlier fixed choice of C. |
| Plan approved (9 Nov) | PLAN_V2.md approved; Phase 0 starts. |
| Test area (9 Nov) | Grund, Pfaffenthal and the Bock. |
| Far zoom (9 Nov) | Exact at normal zoom; gentle simplification far out (small clutter dropped, main streets slightly emphasised). |
| G0 review: test area (9 Nov) | Keep the larger test area as drawn: 1.29 x 1.61 km (1.57 km2), `v2/config/areas/test.geojson`. |
| G0 review: facades (9 Nov) | Add doors and shop fronts before the bake-off: from OSM entrances and shop/amenity POIs where mapped (on the nearest street-facing wall), else a rule (at least one door on each building's street-facing wall; shop fronts on the ground floor along commercial streets). Ground-floor windows give way to them. Numbered checks in the facades spec. Dormers can wait. |
| G0 review: commune checks (9 Nov) | Fix the four failing commune check stages (TR3, B2, P5-P9, G5) before G1, at their causes; no threshold is loosened to pass. Genuine exceptions go per feature, with a reason, in a short data file. |
| G0 review: accepted as built (9 Nov) | Tunnel clearances road 4.5 m, rail 5.5 m, tram 4.5 m, + 1 m cover; 40 m portal zone and 6 m portal mouth; garage-driveway exemption from the dead-end check; path and step slopes recorded, not gated. |
| G0 review: still open (9 Nov) | Viaduct arch counts, the funicular schedule, the R2 bucket, the GTFS licence version; the commune terrain stays at 1 m for now. |
| G1 review: accepted (9 Nov) | Gate G1 passed. Accepted: raised approaches drawn as decks, far zoom from zoom 2, the viewer's own navigation, and the new check methods of the Phase 1 report. Phone speed waits for Phase 5 (R2 hosting). |
| Red bridge (9 Nov) | "The red bridge is not connected to the road": fixed at its cause in Phase 2 (ways whose profile leaves the cut-away terrain at an abutment are drawn at their profile, per stretch); new gate L4.6, bridge ends continuous in the drawn surface. |
| Tunnel view (9 Nov) | Phase 3, test area, $0, code only: a toggle (or held key) fades the city layers so the tunnels show at their real path and depth from the transport graph, with vehicles moving inside them by depth; the Bock casemates may be shown the same way. Spec: `v2/docs/specs/tunnel-view.md`. |
| Landmark cutaways (9 Nov) | Phase 3, test area: famous buildings shown cut open in place on the map ("slice of cake"), not in a modal. The cut comes from the 3D model; the interior is an AI-painted cutaway cut exactly to the slice. First four: the Bock casemates, Notre-Dame Cathedral, the Grand Ducal Palace and Neumünster Abbey. Paid from the Phase 3 line ($8 cap), quoted first. Spec: `v2/docs/specs/landmark-cutaways.md`. |
