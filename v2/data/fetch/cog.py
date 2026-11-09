"""Windowed reads of the national LiDAR 2024 rasters (Cloud Optimised GeoTIFFs on data.public.lu, CC0).

Only the tiles that cover the window are downloaded, one request per row of tiles, so a 1.5 km test area at 0.5 m
costs tens of MB and the whole commune at 1 m a few hundred, instead of the 40 GB national files.
"""
from __future__ import annotations

import numpy as np
import tifffile

from .http import RangeFile, get_range

MNT_2024 = ("https://download.data.public.lu/resources/bd-l-lidar2024-releve-3d-du-territoire-luxembourgeois/"
            "20241223-093912/MNT_Lidar2024.tif")
MNS_2024 = ("https://download.data.public.lu/resources/bd-l-lidar2024-releve-3d-du-territoire-luxembourgeois/"
            "20241223-093912/MNS_Lidar2024.tif")


def read_window(url: str, e0: float, n0: float, e1: float, n1: float, step: float, log=print):
    """Heights (float32, NaN for no data) on a grid of `step` metres covering [e0, e1) x [n0, n1), row 0 = south.

    Uses the COG level whose pixel size equals `step` (0.5 m full resolution, 1 m, 2 m, ...). Returns
    (z, grid) with grid = {"e0", "n0", "step"}: z[i, j] is the height at the centre of the cell (e0 + (j + .5) step,
    n0 + (i + .5) step).
    """
    f = RangeFile(url)
    t = tifffile.TiffFile(f)
    p0 = t.pages[0]
    sx, sy = p0.tags["ModelPixelScaleTag"].value[:2]
    tie = p0.tags["ModelTiepointTag"].value
    x0, y0 = tie[3] - tie[0] * sx, tie[4] + tie[1] * sy          # top-left corner of the raster
    nodata = float(p0.tags["GDAL_NODATA"].value) if "GDAL_NODATA" in p0.tags else None
    level = None
    for i, p in enumerate(t.pages):
        ps = sx * round(p0.shape[1] / p.shape[1])                 # overviews halve the size, rounding up
        if abs(ps - step) < 1e-6 * step:
            level, page = i, p
            break
    if level is None:
        raise ValueError(f"no COG level with {step} m pixels")
    # pixel window (row 0 = north in the TIFF)
    c0 = int(np.floor((e0 - x0) / ps)); c1 = int(np.ceil((e1 - x0) / ps))
    r0 = int(np.floor((y0 - n1) / ps)); r1 = int(np.ceil((y0 - n0) / ps))
    tw, th = page.tilewidth, page.tilelength
    tiles_across = (page.shape[1] + tw - 1) // tw
    out = np.full((r1 - r0, c1 - c0), np.nan, np.float32)
    offsets, counts = page.dataoffsets, page.databytecounts
    got = 0
    for tr in range(r0 // th, (r1 - 1) // th + 1):
        tcs = list(range(c0 // tw, (c1 - 1) // tw + 1))
        idx = [tr * tiles_across + tc for tc in tcs]
        lo = min(offsets[i] for i in idx if counts[i])
        hi = max(offsets[i] + counts[i] for i in idx if counts[i])
        blob = get_range(url, lo, hi - 1)
        got += len(blob)
        for tc, i in zip(tcs, idx):
            if not counts[i]:
                continue
            seg = blob[offsets[i] - lo: offsets[i] - lo + counts[i]]
            data, _, shape = page.decode(seg, i)
            a = np.asarray(data, np.float64).reshape(shape[-3], shape[-2])  # (th, tw)
            # place the tile into the window
            ty0, tx0 = tr * th, tc * tw
            ya, yb = max(ty0, r0), min(ty0 + th, r1)
            xa, xb = max(tx0, c0), min(tx0 + tw, c1)
            out[ya - r0:yb - r0, xa - c0:xb - c0] = a[ya - ty0:yb - ty0, xa - tx0:xb - tx0]
        log(f"tile row {tr - r0 // th + 1}/{(r1 - 1) // th - r0 // th + 1}, {got / 1e6:.0f} MB")
    if nodata is not None:
        out[out == nodata] = np.nan
    out[(out < -100) | (out > 5000)] = np.nan
    grid = {"e0": x0 + c0 * ps, "n0": y0 - r1 * ps, "step": ps, "level": level, "bytes": got + f.fetched}
    return out[::-1].copy(), grid
