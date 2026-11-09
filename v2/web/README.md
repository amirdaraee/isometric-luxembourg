# v2 viewer (phase 1)

The v2 viewer starts from v1's shell (`web/`: OpenSeadragon navigation, feature switches, frame clock, test
parameters, screenshot and speed harness, traffic simulation, transit, landmark cards, visitors' notes) and adds
the WebGL layer compositor (`v2/docs/specs/compositor.md`), reading tiles from R2
(`v2/docs/specs/tiles-hosting.md`). Map pixels are v2's (0.125 m); v1 links convert with
`v2/config/camera.py` (`v1_to_v2_px`). Nothing here yet in Phase 0.
