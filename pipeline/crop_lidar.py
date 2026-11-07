"""Cut the whole commune out of the national LiDAR terrain at 2 m, then the 27 GB source can go."""
import numpy as np
import pyvips
import tifffile
from common import RAW, WORK

SRC = RAW / "lidar" / "mnt.tif"
# Commune extent from the 3D data's envelope, with a margin.
E0, E1, N0, N1 = 72500.0, 82800.0, 69400.0, 80800.0
PICK = 4  # source is 0.5 m: average 4 x 4 pixels


def main():
    with tifffile.TiffFile(SRC) as t:
        p = t.pages[0]
        scale = p.tags["ModelPixelScaleTag"].value
        tie = p.tags["ModelTiepointTag"].value
        print("size", p.imagewidth, p.imagelength, "tiled", p.is_tiled, "compression", p.compression, "scale", scale[:2], "tie", tie[:6])
    x0 = tie[3] - tie[0] * scale[0]
    y0 = tie[4] + tie[1] * scale[1]
    left = int((E0 - x0) / scale[0]); top = int((y0 - N1) / scale[1])
    w = int((E1 - E0) / scale[0]); h = int((N1 - N0) / scale[1])
    im = pyvips.Image.new_from_file(str(SRC), access="random")
    crop = im.crop(left, top, w, h)
    a = np.ndarray(buffer=crop.write_to_memory(), dtype=np.float32, shape=(h, w))
    bad = (a < 100) | (a > 1000) | ~np.isfinite(a)
    print("crop", a.shape, "nodata share", float(bad.mean()), "z", float(a[~bad].min()), float(a[~bad].max()))
    a = np.where(bad, np.nan, a)
    hh, ww = h // PICK, w // PICK
    b = a[:hh * PICK, :ww * PICK].reshape(hh, PICK, ww, PICK)
    with np.errstate(invalid="ignore"):
        import warnings
        warnings.simplefilter("ignore")
        m = np.nanmean(b, axis=(1, 3))
    # Row 0 is north in the TIFF; the terrain grid runs south to north.
    np.savez(WORK / "lidar_2m.npz", z=m[::-1].astype(np.float32), e0=E0, n0=N1 - hh * 2.0, step=2.0)
    print("saved", m.shape)


if __name__ == "__main__":
    main()
