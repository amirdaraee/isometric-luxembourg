"""Remove the magenta specks the light model sometimes leaves on lawns and fields in a painted version.

Strong magenta (hue 280-340 degrees, saturated, not dark) never belongs in this map, so those pixels are grown by a
couple of pixels and filled in from their surroundings (OpenCV inpainting). Everything else is left untouched.
Usage: despeckle.py <in.png> <out.png>
"""
import sys

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None


def main(src, out):
    rgb = np.asarray(Image.open(src).convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    magenta = (h >= 140) & (h <= 170) & (s >= 90) & (v >= 70) & (r > g + 40) & (b > g + 40)
    n = int(magenta.sum())
    if n == 0:
        Image.fromarray(rgb).save(out)
        print("no magenta")
        return
    m = cv2.dilate(magenta.astype(np.uint8) * 255, np.ones((5, 5), np.uint8))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(bgr, m, 5, cv2.INPAINT_TELEA)
    Image.fromarray(cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)).save(out)
    print(f"magenta px {n} ({n / magenta.size * 100:.3f}%) filled")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
