"""Turn a redrawn image into true pixels: one grid, a limited palette, no smoothing."""
import sys
from pathlib import Path
from PIL import Image, ImageEnhance


def pixelate(im, grid=4, colours=64):
    w, h = im.size
    small = im.convert("RGB").resize((w // grid, h // grid), Image.BOX)
    small = ImageEnhance.Contrast(ImageEnhance.Color(small).enhance(1.12)).enhance(1.05)
    q = small.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    return q.resize((q.width * grid, q.height * grid), Image.NEAREST)


if __name__ == "__main__":
    pixelate(Image.open(sys.argv[1])).save(sys.argv[2])
