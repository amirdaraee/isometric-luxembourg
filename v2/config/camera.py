"""The v2 camera and map-pixel coordinate system (spec: v2/docs/specs/camera.md).

v1's camera is kept exactly: an orthographic 2:1 dimetric view from the south-east, looking north-west, 30 degrees
above the horizon, in LUREF (EPSG:2169) metres with the local origin (70000, 65000). Screen metres:

    sx = (le + ln) / sqrt(2)                              le, ln = E - 70000, N - 65000
    sy = (ln - le) / sqrt(2) * sin(30) + z * cos(30)      (y up)
    depth = (ln - le) / sqrt(2) * cos(30) - z * sin(30)   (smaller is nearer the camera)

Map pixels: px = (sx - sx0) / mpp, py = (sy1 - sy) / mpp, with v2's mpp = 0.125 m (v1: 0.25 m). v2's frame origin
(sx0, sy1) is v1's moved by whole v1 frames (2048 v1 px = 512 m) so the whole commune has positive pixels, which
makes the conversion to v1 pixels exact and simple:

    v1_px = v2_px / 2 - v1_offset_px        (v1_offset_px from camera.json, whole multiples of 2048)
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

import numpy as np

from v2.config import CONFIG

R = 1 / math.sqrt(2)


@lru_cache(maxsize=None)
def camera() -> dict:
    return json.loads((CONFIG / "camera.json").read_text())


def _c():
    c = camera()
    return c["origin_en"][0], c["origin_en"][1], math.radians(c["elevation_deg"]), c


def to_screen(e, n, z):
    """LUREF metres and height (m) to screen metres (sx, sy), y up."""
    oe, on, el, _ = _c()
    le, ln = np.asarray(e, float) - oe, np.asarray(n, float) - on
    sx = (le + ln) * R
    sy = (ln - le) * R * math.sin(el) + np.asarray(z, float) * math.cos(el)
    return sx, sy


def depth(e, n, z):
    """Distance along the view ray, in metres: smaller is nearer the camera."""
    oe, on, el, _ = _c()
    le, ln = np.asarray(e, float) - oe, np.asarray(n, float) - on
    return (ln - le) * R * math.cos(el) - np.asarray(z, float) * math.sin(el)


def en_to_px(e, n, z, mpp: float | None = None):
    """LUREF metres and height to v2 map pixels (float)."""
    c = camera()
    mpp = mpp or c["mpp"]
    sx, sy = to_screen(e, n, z)
    return (sx - c["frame"]["sx0"]) / mpp, (c["frame"]["sy1"] - sy) / mpp


def px_to_en(px, py, z):
    """Inverse of en_to_px for a known height."""
    oe, on, el, c = _c()
    sx = c["frame"]["sx0"] + np.asarray(px, float) * c["mpp"]
    sy = c["frame"]["sy1"] - np.asarray(py, float) * c["mpp"]
    f = (sy - np.asarray(z, float) * math.cos(el)) / math.sin(el)       # (ln - le) / sqrt(2)
    return (sx - f) * R + oe, (sx + f) * R + on


def v2_to_v1_px(px, py):
    c = camera()
    k = c["mpp"] / c["v1"]["mpp"]
    return np.asarray(px) * k - c["v1_offset_px"][0], np.asarray(py) * k - c["v1_offset_px"][1]


def v1_to_v2_px(x, y):
    c = camera()
    k = c["v1"]["mpp"] / c["mpp"]
    return (np.asarray(x) + c["v1_offset_px"][0]) * k, (np.asarray(y) + c["v1_offset_px"][1]) * k


def v1_px_to_en(x, y, ground):
    """v1 map pixels (on the ground) to LUREF metres, solving for the ground height with `ground(e, n)`.

    v1's pixels were made with v1's terrain, so pass v1's terrain sampler for exact round trips."""
    c = camera()
    v = c["v1"]
    sx = v["sx0"] + np.asarray(x, float) * v["mpp"]
    sy = v["sy1"] - np.asarray(y, float) * v["mpp"]
    oe, on, el, _ = _c()
    z = np.full(np.shape(sx), 300.0)
    for _ in range(30):
        f = (sy - z * math.cos(el)) / math.sin(el)
        e, n = (sx - f) * R + oe, (sx + f) * R + on
        z2 = ground(e, n)
        if np.all(np.abs(z2 - z) < 1e-3):
            break
        z = z2
    return e, n, z


def suggest_frame(bbox_en, zmin=150.0, zmax=480.0, tile_px=512):
    """The v2 frame for an extent: v1's origin moved by whole v1 frames so every pixel is positive."""
    v = camera()["v1"]
    e0, n0, e1, n1 = bbox_en
    E = np.array([e0, e1, e0, e1] * 2); N = np.array([n0, n0, n1, n1] * 2); Z = np.r_[[zmin] * 4, [zmax] * 4]
    sx, sy = to_screen(E, N, Z)
    step = v["frame_px"] * v["mpp"]                       # 512 m
    k = max(0, math.ceil((v["sx0"] - sx.min()) / step))
    j = max(0, math.ceil((sy.max() - v["sy1"]) / step))
    sx0, sy1 = v["sx0"] - k * step, v["sy1"] + j * step
    mpp = camera()["mpp"]
    w = math.ceil((sx.max() - sx0) / mpp / tile_px) * tile_px
    h = math.ceil((sy1 - sy.min()) / mpp / tile_px) * tile_px
    return {"sx0": sx0, "sy1": sy1, "width_px": w, "height_px": h,
            "v1_offset_px": [k * v["frame_px"], j * v["frame_px"]]}
