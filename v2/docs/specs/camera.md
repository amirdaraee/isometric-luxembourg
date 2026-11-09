# Camera and coordinates

**Kept from v1** (`pipeline/common.py`, `data/work/mosaic.json`, `web/src/components/IsometricMap.tsx`), so v1's
viewer, links and simulation carry over. Config: `v2/config/camera.json`; code: `v2/config/camera.py`.

**Projection.** Orthographic 2:1 dimetric view from the south-east, looking north-west, 30° above the horizon.
With LUREF metres relative to the local origin (le, ln) = (E − 70000, N − 65000):

    sx    = (le + ln) / √2                         screen right = north-east
    sy    = (ln − le) / √2 · sin 30° + z · cos 30°  screen up
    depth = (ln − le) / √2 · cos 30° − z · sin 30°  along the view ray; smaller is nearer

**Map pixels.** `px = (sx − sx0) / mpp`, `py = (sy1 − sy) / mpp`, mpp = 0.125 m (v1: 0.25 m).
v2's frame origin is v1's moved by whole v1 frames (2048 v1 px = 512 m): 11 frames left and 5 up, so the whole
commune (its bounding box + 300 m, at heights 150–480 m) has positive pixels:

| | sx0 | sy1 | size (px) |
|---|---|---|---|
| v1 | 10373.3037 | 2774.1113 | 26 624 × 14 336 at 0.25 m |
| v2 | 4741.3037 | 5334.1113 | 121 856 × 66 048 at 0.125 m |

Conversion, exact: `v1_px = v2_px / 2 − (22528, 10240)`; `v2_px = (v1_px + (22528, 10240)) · 2`
(`camera.v2_to_v1_px`, `v1_to_v2_px`). v1 links (`?x=&y=`) map to v2 pixels with this.

**Inverse.** `px_to_en(px, py, z)` for a known height. For a pixel on the ground, `v1_px_to_en` scans the view ray
from the camera side for the first meeting with the terrain (and prefers an exact root where a stepped terrain
jumps), refined by bisection.

**Sun.** `v2/config/sun.py`: NOAA solar position for the Place d'Armes (one site serves the commune: < 0.1°
difference), `direction_en` and `direction_screen` (in this camera's frame: right, up, towards the camera).

**Checks.** S6 (the area lies inside the v2 frame), PL1/PL2a (places round-trip to v1 pixels), and the unit tests
in `v2/data/tests/test_camera_sun.py` (formula identical to v1's; pixel round trips; v1 ↔ v2 conversion; ray
inversion on a cliff; solstice sun heights).
