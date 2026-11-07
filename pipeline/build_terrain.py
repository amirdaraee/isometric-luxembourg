"""Terrain for the pilot: open 30 m elevation, pulled to true ground height with each building's surveyed ground level."""
import math
import numpy as np
from PIL import Image
from scipy import ndimage
from common import RAW, WORK, PILOT_LONLAT, ORIGIN_E, ORIGIN_N, lonlat_to_en, en_to_lonlat

Z = 14
STEP = 2.0  # metres per terrain vertex
MARGIN_M = 150.0


def merc_xy(lon, lat, z):
    t = 2 ** z * 256
    return (lon + 180) / 360 * t, (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * t


def main():
    files = sorted((RAW / "terrarium" / str(Z)).glob("*.png"))
    xs = [int(f.stem.split("_")[0]) for f in files]
    ys = [int(f.stem.split("_")[1]) for f in files]
    x0, y0 = min(xs), min(ys)
    W, H = (max(xs) - x0 + 1) * 256, (max(ys) - y0 + 1) * 256
    dem = np.zeros((H, W), np.float32)
    for f, x, y in zip(files, xs, ys):
        a = np.asarray(Image.open(f).convert("RGB"), np.float32)
        dem[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768

    w, s, e, n = PILOT_LONLAT
    cs = [lonlat_to_en(a, b) for a in (w, e) for b in (s, n)]
    e0 = min(c[0] for c in cs) - MARGIN_M; e1 = max(c[0] for c in cs) + MARGIN_M
    n0 = min(c[1] for c in cs) - MARGIN_M; n1 = max(c[1] for c in cs) + MARGIN_M
    ge = np.arange(e0, e1, STEP); gn = np.arange(n0, n1, STEP)
    E, N = np.meshgrid(ge, gn)
    lon, lat = en_to_lonlat(E, N)
    mx, my = merc_xy(lon, lat, Z)
    base = ndimage.map_coordinates(dem, [my - y0 * 256, mx - x0 * 256], order=1, mode="nearest")
    base = ndimage.gaussian_filter(base, 3)

    # Residual between surveyed building ground and the coarse DEM, spread by normalised convolution.
    b = np.load(WORK / "buildings.npz")["bld_ground"]
    b = b[np.isfinite(b[:, 0])]
    bx = ((b[:, 0] + ORIGIN_E - e0) / STEP); by = ((b[:, 1] + ORIGIN_N - n0) / STEP)
    keep = (bx >= 0) & (bx < len(ge) - 1) & (by >= 0) & (by < len(gn) - 1)
    bx, by, bz = bx[keep], by[keep], b[keep, 2]
    res = bz - base[by.astype(int), bx.astype(int)]
    print("buildings used", len(bz), "residual m: median", float(np.median(res)), "p5", float(np.percentile(res, 5)), "p95", float(np.percentile(res, 95)))
    num = np.zeros_like(base); den = np.zeros_like(base)
    np.add.at(num, (by.astype(int), bx.astype(int)), res)
    np.add.at(den, (by.astype(int), bx.astype(int)), 1)
    sum_num, sum_den = 0, 0
    for sigma, weight in ((6, 1.0), (15, 0.25), (40, 0.05)):
        sum_num = sum_num + weight * ndimage.gaussian_filter(num, sigma)
        sum_den = sum_den + weight * ndimage.gaussian_filter(den, sigma)
    corr = sum_num / (sum_den + 1e-4)
    z = ndimage.gaussian_filter(base + corr, 2)
    lidar_path = WORK / "lidar_2m.npz"
    if lidar_path.exists():
        # Surveyed bare earth wins wherever it exists; the fitted surface only fills its gaps.
        l = np.load(lidar_path)
        lz = l["z"]
        ly = (N - float(l["n0"])) / float(l["step"])
        lx = (E - float(l["e0"])) / float(l["step"])
        valid = np.isfinite(lz)
        sampled = ndimage.map_coordinates(np.where(valid, lz, 0), [ly, lx], order=1, mode="nearest")
        ok = ndimage.map_coordinates(valid.astype(np.float32), [ly, lx], order=1, mode="constant") > 0.99
        print("lidar coverage", float(ok.mean()), "mean abs difference from fitted surface m", float(np.abs(sampled - z)[ok].mean()))
        z = np.where(ok, sampled, z)
    print("terrain z", float(z.min()), float(z.max()))
    np.savez(WORK / "terrain.npz", z=z.astype(np.float32), e0=e0, n0=n0, step=STEP)


if __name__ == "__main__":
    main()
