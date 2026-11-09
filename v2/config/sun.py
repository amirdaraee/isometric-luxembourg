"""The sun's real position over Luxembourg, for code lighting (spec: v2/docs/specs/layer-09-light.md).

NOAA's solar position algorithm (the spreadsheet version of Meeus, "Astronomical Algorithms"): accurate to about
0.01 degree over 1800-2100, which is far below a pixel of shadow. Times are local Luxembourg time
(Europe/Luxembourg, with summer time) unless an aware datetime is given.

    position(datetime) -> (azimuth_deg clockwise from north, elevation_deg, with atmospheric refraction)
    direction_en(datetime) -> unit vector towards the sun in (E, N, up)
    direction_screen(datetime) -> the same vector in the v2 camera frame (screen right, screen up, towards camera)
"""
from __future__ import annotations

import datetime as dt
import json
import math
from zoneinfo import ZoneInfo

import numpy as np

from v2.config import CONFIG

SITE = json.loads((CONFIG / "sun.json").read_text())
TZ = ZoneInfo(SITE["timezone"])


def _jd(t: dt.datetime) -> float:
    t = t.astimezone(dt.timezone.utc)
    return t.timestamp() / 86400.0 + 2440587.5


def position(t: dt.datetime, lat: float | None = None, lon: float | None = None):
    lat = SITE["lat"] if lat is None else lat
    lon = SITE["lon"] if lon is None else lon
    if t.tzinfo is None:
        t = t.replace(tzinfo=TZ)
    jc = (_jd(t) - 2451545.0) / 36525.0
    gml = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360          # geometric mean longitude
    gma = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)                    # geometric mean anomaly
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    m = math.radians(gma)
    ctr = (math.sin(m) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) + math.sin(2 * m) * (0.019993 - 0.000101 * jc)
           + math.sin(3 * m) * 0.000289)
    true_long = gml + ctr
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    mean_obl = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    obl = mean_obl + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(obl)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(obl / 2)) ** 2
    l0 = math.radians(gml)
    eot = 4 * math.degrees(y * math.sin(2 * l0) - 2 * ecc * math.sin(m) + 4 * ecc * y * math.sin(m) * math.cos(2 * l0)
                           - 0.5 * y * y * math.sin(4 * l0) - 1.25 * ecc * ecc * math.sin(2 * m))   # minutes
    u = t.astimezone(dt.timezone.utc)
    minutes = u.hour * 60 + u.minute + u.second / 60 + u.microsecond / 6e7
    tst = (minutes + eot + 4 * lon) % 1440                                    # true solar time, minutes
    ha = tst / 4 - 180 if tst / 4 >= 0 else tst / 4 + 180                     # hour angle
    la, de, h = math.radians(lat), math.radians(decl), math.radians(ha)
    cz = math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(h)
    zen = math.degrees(math.acos(max(-1.0, min(1.0, cz))))
    sz = math.sin(math.radians(zen))
    if abs(sz) < 1e-9:
        az = 180.0
    else:
        a = (math.sin(la) * cz - math.sin(de)) / (math.cos(la) * sz)
        a = math.degrees(math.acos(max(-1.0, min(1.0, a))))
        az = (a + 180) % 360 if ha > 0 else (540 - a) % 360
    el = 90 - zen
    # atmospheric refraction (NOAA)
    if el > 85:
        r = 0.0
    elif el > 5:
        te = math.tan(math.radians(el))
        r = 58.1 / te - 0.07 / te ** 3 + 0.000086 / te ** 5
    elif el > -0.575:
        r = 1735 + el * (-518.2 + el * (103.4 + el * (-12.79 + el * 0.711)))
    else:
        r = -20.772 / math.tan(math.radians(el))
    return az, el + r / 3600


def direction_en(t: dt.datetime):
    az, el = position(t)
    a, e = math.radians(az), math.radians(el)
    return np.array([math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)])


def direction_screen(t: dt.datetime):
    """Sun direction in the camera frame: x = screen right (north-east), y = screen up, z = towards the camera."""
    from v2.config.camera import camera
    c = camera()
    el = math.radians(c["elevation_deg"])
    right = np.array(c["right_en"]); fwd = np.array(c["forward_en"])        # forward: into the screen, horizontal
    view = fwd * math.cos(el) + np.array([0, 0, -1.0]) * math.sin(el)        # the view ray (down into the scene)
    up = np.cross(right, view)                                              # = d(sy)/d(E, N, z) of camera.to_screen
    d = direction_en(t)
    return np.array([d @ right, d @ up, -(d @ view)])
