import datetime as dt
import math

import numpy as np

from v2.config.camera import camera, depth, en_to_px, px_to_en, to_screen, v1_px_to_en, v1_to_v2_px, v2_to_v1_px
from v2.config.sun import direction_screen, position


def test_v1_camera_kept():
    c = camera()
    assert c["origin_en"] == [70000.0, 65000.0] and c["elevation_deg"] == 30.0 and c["mpp"] == 0.125
    # the same formula as pipeline/common.py to_screen
    e, n, z = 78000.0, 75500.0, 280.0
    le, ln = e - 70000, n - 65000
    R = 1 / math.sqrt(2)
    sx, sy = to_screen(e, n, z)
    assert abs(sx - (le + ln) * R) < 1e-9
    assert abs(sy - ((-le + ln) * R * 0.5 + z * math.cos(math.radians(30)))) < 1e-9


def test_px_round_trip_and_v1_pixels():
    e, n, z = np.array([77500.0, 78300.0]), np.array([75100.0, 76000.0]), np.array([250.0, 310.0])
    px, py = en_to_px(e, n, z)
    e2, n2 = px_to_en(px, py, z)
    assert np.allclose(e, e2) and np.allclose(n, n2)
    # v1 pixels: same projection at 0.25 m with v1's origin
    v = camera()["v1"]
    sx, sy = to_screen(e, n, z)
    x1, y1 = (sx - v["sx0"]) / v["mpp"], (v["sy1"] - sy) / v["mpp"]
    a, b = v2_to_v1_px(px, py)
    assert np.allclose(a, x1) and np.allclose(b, y1)
    c, d = v1_to_v2_px(x1, y1)
    assert np.allclose(c, px) and np.allclose(d, py)


def test_depth_nearer_is_smaller():
    # a point further south-east (towards the camera) and higher is nearer
    assert depth(78000, 75000, 300) < depth(77900, 75100, 300)
    assert depth(78000, 75000, 310) < depth(78000, 75000, 300)


def test_v1_pixel_inversion_on_a_cliff():
    def ground(e, n):          # a 20 m cliff running north-south at E = 78000 (stepped, like v1's sampler)
        return np.where(np.asarray(e) < 78000, 300.0, 280.0)
    v = camera()["v1"]
    for e in (77990.0, 78010.0):
        z = ground(e, 0)
        sx, sy = to_screen(e, 75000.0, z)
        x, y = (sx - v["sx0"]) / v["mpp"], (v["sy1"] - sy) / v["mpp"]
        e2, n2, z2 = v1_px_to_en(x, y, ground)
        assert abs(float(z2[0]) - float(ground(e2, n2)[0])) < 0.05


def test_sun_solstices_at_solar_noon():
    # solar noon elevation = 90 - latitude +/- 23.44 (refraction adds ~0.05 in winter)
    az, el = position(dt.datetime(2026, 6, 21, 13, 36))
    assert abs(el - (90 - 49.6112 + 23.44)) < 0.15 and abs(az - 180) < 2
    az, el = position(dt.datetime(2026, 12, 21, 12, 36))
    assert abs(el - (90 - 49.6112 - 23.44)) < 0.2


def test_sun_screen_frame():
    d = direction_screen(dt.datetime(2026, 6, 21, 13, 36))
    assert abs(np.linalg.norm(d) - 1) < 1e-9
    assert d[1] > 0.5                       # high summer sun: up on the screen
    _, el = position(dt.datetime(2026, 11, 9, 23, 0))
    assert el < -6                          # night
