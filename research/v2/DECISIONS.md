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
| Bake-off quotes approved (9 Nov) | All Phase 2 bake-off quotes approved in chat: q0001–q0008 (B1, B2, C1p, C1, C2p, C2, C3, C4). Expected $14.14, worst case $16.94, under the $17 `phase2_bakeoff` cap. Recorded in the ledger as owner approvals. Provider: RunPod, community cloud H100 SXM at the quoted $2.69/h. |
| Trees in method A (9 Nov) | Make crowns rounder: keep the measured height, but widen crowns sensibly by species and age so they no longer look like poplars. Update the layer-07 spec, rebuild A, and keep every gate passing. |
| Phase 2 checks accepted (9 Nov) | Accepted: checks L4.6 and L5.2, the Stierchen footbridge exception, and lossless tiles for layers 5–7. |
| Bake-off paused (9 Nov) | Paused by owner 9 Nov 2026 after no job ran (before B1). No pod was started and $0 was spent. The approvals q0001–q0008 stay recorded but unused. |
| Bake-off resumed (9 Nov) | Resumed by owner 9 Nov 2026 ("resume"). The paid jobs run through `python -m v2.bakeoff run <job> --go` in the runner's order, pilots first; a pilot that fails its checks stops its branch, with no new quote. Results: `v2/docs/PHASE2_RESULTS.md`. |
| Bake-off, second round (10 Nov) | After the results of 10 Nov (`v2/docs/PHASE2_RESULTS.md`): rerun B's materials, try the facade front-on idea on its own, keep the rest of C stopped, and fix the code lighting. The six rows below are that decision. |
| B1 rerun (10 Nov) | Rerun B1 (AI materials) on a new quote with a worst case of at most $2.18. Approved in chat on 10 Nov 2026: "Rerun B materials + facade trial, about $3 more". Recorded as q0009 ($2.15) with the owner's approval. |
| C4 alone (10 Nov) | Run C4, the facade front-on trial, on its own: paint about 10 buildings' facades flat, project them onto their 3D walls. It uses v1's style model (HF `amirdaraee/isometric-ink-style`, `luxembourg-ink-v2`) in place of the model C2 never trained. Its approved quote q0008 ($0.94) stands. The runner lets C4 run without C2; every other refusal stays. |
| C1, C2p, C2, C3 (10 Nov) | They stay stopped. Their unspent approvals (q0004–q0007, $10.49) are released in the ledger (a new event, `release`), so they no longer count as committed and can no longer run. |
| GPU listing (10 Nov) | A cheaper listing of the same chip (H100 NVL, or SXM) at or below the quoted hourly price is fine. |
| Code lighting (10 Nov) | Fix it now, at $0: golden hour brighter and warmer, with long soft shadows and buildings still readable; night readable, a deep blue rather than black, with building shapes visible, stronger window and lamp glow and a moonlit feel. Day stays as it is. All in the viewer's light and look passes (`v2/config/light.json`, the shaders), no light baked into any layer. Specs: `layer-09-light.md` rules 3–7, `layer-10-night.md` rule 4. |
| B's trees (10 Nov) | B uses A's leaf-clump crowns. |
| B1 and C4 again (10 Nov) | q0009 and q0008 were used up by a setup fault on a new pod ($0.12, nothing made). Asked "Approve the two new quotes to rerun them: B materials at most $2.07 and the facade trial at most $0.86?", the owner answered in chat on 10 Nov 2026: "Approve both". Recorded as approvals of q0010 and q0011. If setup fails with nothing made, the job is fixed and restarted in place on the same quote, and the other job is not started on a failed pod. |
| **Gate G2: the art method (10 Nov)** | The owner picked the method on 10 Nov 2026, in their words: "A, enrich in code (Recommended)". **Method A** (all code, `v2/layers/art_a.py`, layers 5–7) is the art method for the whole city. **B (AI materials) and C (AI-painted buildings, with the C4 facade trial) are stopped**; their code stays in the repo as the record of the bake-off and is not built. The richness the owner asks for (beautiful, colourful, detailed, v1's look as the bar) is added in code in Phase 3. AI is used only for the interiors of the four landmark cutaways. |
| Material colour rule (10 Nov) | Kept: an AI material must be within 45 (RGB distance) of the palette colour it was asked for, or it is not used. It applies to any AI material made later. |
| `current.json` (10 Nov) | The build moves `release/current.json` back by itself: every stage's `current.json` names the output of the build last asked for, also when the stage was already up to date (`v2/build/graph.py`). No hand edits. |
| Night's moon (10 Nov) | The moon stays at a fixed place in the sky (south-south-west, 40° up: `v2/config/light.json` `grade.moon_az_el_deg`), not the real moon's. |
| Cathedral cutaway test approved (10 Nov) | Asked "Approve quote q0012: paint the cathedral cutaway interior on RunPod as a test (expected $0.24, worst case $0.54, from Phase 3's $8 line)?", the owner answered on 10 Nov 2026: "Approve q0012 (Recommended)". q0013 (the other three landmarks) is not approved. |
| Cathedral cutaway GPU (10 Nov) | No H100 was free on RunPod's community cloud. Asked which GPU the cathedral test should run on, the owner answered on 10 Nov 2026: "A100 SXM, secure (Recommended)". q0012 was released unspent; q0014 (A100 SXM, secure cloud, $1.79/h, worst case $0.45) replaced it with the owner's approval. It ran once: $0.4256, three of four paintings, none passing its checks (`v2/docs/PHASE3_REPORT.md` section 9). |
| Cathedral interior style (13 Nov) | The owner looked at the three candidates (`v2/docs/img/test_cutaway_cathedral_candidates_run1.jpg`) on 13 Nov 2026 and said the interior style "looks good". The owner also chose to have the free fixes done and a new quote brought for a second cathedral run. That quote is q0015 (expected $0.57, worst case $0.99), not approved. No painting is in the map until one passes its checks. |
| Cutaway checks corrected (13 Nov) | Asked how to handle the two cutaway checks that mis-measure painted interiors (the wall-tone check compares window area; the lines-kept check fails any interior with pews or columns), the owner answered on 13 Nov 2026: "Correct both, free (Recommended)". K3 on a painted interior is measured on the wall's stone only, not its glass or ink. Lines kept gates only the cut's outline (the section's lines) and reports the placeholder's own lines. The limits stay the same (5%, 95%). Done and committed before the second cathedral run. Spec: `v2/docs/specs/landmark-cutaways.md`, "The painted step". |
| Second cathedral run approved (13 Nov) | Asked "Quote q0015: second cathedral cutaway run on RunPod, A100 SXM secure, 4 candidates, expected $0.57, worst case $0.99 (Phase 3 has $7.57 of $8 left). Approve it?", the owner answered on 13 Nov 2026: "Approve, run after the check fixes (Recommended)". This approves q0015 only; q0013 (palace, abbey, casemates) is not approved. It ran once after the check fixes were committed: $0.4672, four paintings, none passing (all four fail the light-across-a-face check, two also K3). The placeholder stays in the map (`v2/docs/PHASE3_REPORT.md` section 9). |
| Cutaway light check looked into (13 Nov) | Asked what should happen next after the second cathedral run, the owner answered on 13 Nov 2026: "Investigate the check, free (Recommended)", described as "I measure where the light check differs on this painting. If it is drawn detail, I fix the check at its cause and put the painting in the map; if it is real shading, I report back." Done at $0. On `cathedral-open_1` the check was reacting to drawn detail (a white sill, pale ribs, a highlight) and to the wall drawn below the model's floor line. The check was corrected at those causes; the 5% limit stays. The corrected check still fails the painting (8.5% / 6.0% / 9.9%), so it is not in the map and the placeholder stays. No verdict of the seven paintings moved (`v2/docs/PHASE3_REPORT.md` section 9, "The light check looked into"). |
