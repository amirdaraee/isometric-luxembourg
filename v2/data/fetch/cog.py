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


def read_window(url: str, e0: float, n0: float, e1: float, n1: float, step: float, log=print, aggregate=None):
    """Heights (float32, NaN for no data) on a grid of `step` metres covering [e0, e1) x [n0, n1), row 0 = south.

    Uses the COG level whose pixel size equals `step` (0.5 m full resolution, 1 m, 2 m, ...). Returns
    (z, grid) with grid = {"e0", "n0", "step"}: z[i, j] is the height at the centre of the cell (e0 + (j + .5) step,
    n0 + (i + .5) step).

    aggregate ("mean", "max" or "min"): build the `step` grid from the full-resolution level instead of the COG's own
    overview, reducing k x k blocks (k = step / full resolution) as each row of tiles arrives. ACT's overviews of
    the terrain and the surface model are not made consistently (at 1 m the surface model lies below the terrain on
    0.6% of the commune, never at 0.5 m), so two rasters that must agree are reduced here the same way: the
    terrain by its mean, the surface by its max (a surface is never below the ground under it).
    """
    f = RangeFile(url)
    t = tifffile.TiffFile(f)
    p0 = t.pages[0]
    sx, sy = p0.tags["ModelPixelScaleTag"].value[:2]
    tie = p0.tags["ModelTiepointTag"].value
    x0, y0 = tie[3] - tie[0] * sx, tie[4] + tie[1] * sy          # top-left corner of the raster
    nodata = float(p0.tags["GDAL_NODATA"].value) if "GDAL_NODATA" in p0.tags else None
    k = 1
    if aggregate:
        k = int(round(step / sx))
        assert abs(k * sx - step) < 1e-9, "step must be a whole multiple of the full resolution"
        step = sx
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
    if k > 1:   # whole k x k blocks, aligned on the raster's corner
        c0, r0 = c0 // k * k, r0 // k * k
        c1, r1 = -(-c1 // k) * k, -(-r1 // k) * k
    tw, th = page.tilewidth, page.tilelength
    tiles_across = (page.shape[1] + tw - 1) // tw
    out = np.full(((r1 - r0) // k, (c1 - c0) // k), np.nan, np.float32)
    red = {"mean": np.nanmean, "max": np.nanmax, "min": np.nanmin}.get(aggregate)
    offsets, counts = page.dataoffsets, page.databytecounts
    got = 0
    assert k == 1 or th % k == 0
    for tr in range(r0 // th, (r1 - 1) // th + 1):
        tcs = list(range(c0 // tw, (c1 - 1) // tw + 1))
        ty0 = tr * th
        sa, sb = max(ty0, r0), min(ty0 + th, r1)
        strip = np.full((sb - sa, c1 - c0), np.nan, np.float32)
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
            # place the tile into this row of tiles
            tx0 = tc * tw
            xa, xb = max(tx0, c0), min(tx0 + tw, c1)
            strip[:, xa - c0:xb - c0] = a[sa - ty0:sb - ty0, xa - tx0:xb - tx0]
        if nodata is not None:
            strip[strip == nodata] = np.nan
        strip[(strip < -100) | (strip > 5000)] = np.nan
        if k > 1:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)          # all-NaN blocks stay NaN
                strip = red(strip.reshape(strip.shape[0] // k, k, strip.shape[1] // k, k), axis=(1, 3))
        out[(sa - r0) // k:(sa - r0) // k + strip.shape[0]] = strip
        log(f"tile row {tr - r0 // th + 1}/{(r1 - 1) // th - r0 // th + 1}, {got / 1e6:.0f} MB")
    grid = {"e0": x0 + c0 * ps, "n0": y0 - r1 * ps, "step": ps * k, "level": level, "aggregate": aggregate,
            "bytes": got + f.fetched}
    return out[::-1].copy(), grid
