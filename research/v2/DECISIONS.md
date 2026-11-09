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
