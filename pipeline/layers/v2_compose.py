"""Layered map v2: stack the layers and make the comparison pictures for the progress page.

Stack, bottom to top: painted ground, ink lines, contact darkening under trees, [sun shadows], buildings and
bridges (version 1's cut), vegetation (already depth-tested against the buildings).

  v2_compose.py stack [--tag spring] [--clear] [--shadow midday] --out x.png
  v2_compose.py sheets [--tag spring]     layers alone, whole block today / v1 / v2, close-ups of the spots
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw

from layers_common import LAYERS, POC_IMG, block, preview, today
from v2_ground import PAINT, v2_dir

V1 = LAYERS / "b00"
K = PAINT / 6000
SPOTS = {  # full-res block px (x, y, size)
    "grund": (2600, 2400, 1400),
    "bock": (3700, 2300, 900),
    "hollowtooth": (3700, 2600, 800),
    "pfaffenthal": (4000, 1500, 1100),
    "redbridge": (4150, 950, 1150),
    "petrusse": (900, 2300, 1300),
    "cathedral": (1760, 2180, 800),
    "neumunster": (3140, 2830, 800),
    "grund_gardens": (3100, 3100, 900),
}
NAMES = {"grund": "Grund", "bock": "Bock cliffs", "hollowtooth": "Hollow Tooth road", "pfaffenthal": "Pfaffenthal",
         "redbridge": "Red Bridge", "petrusse": "Pétrusse woods", "cathedral": "Cathedral",
         "neumunster": "Neumünster Abbey", "grund_gardens": "Grund gardens and terraces"}


def rgba(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)


def over(img, layer):
    a = layer[..., 3:] / 255
    return img * (1 - a) + layer[..., :3] * a


def stack(tag="", clear=False, shadow=None, only=None):
    on = set(only.split(",")) if only else {"ground", "ink", "contact", "objects", "veg"}
    img = np.asarray(Image.open(v2_dir("ground") / "L1_ground.png").convert("RGB")).astype(np.float32)
    if "ground" not in on:
        img[:] = 240
    if "ink" in on:
        img = over(img, rgba(v2_dir("ink") / "L2_ink.png"))
    if "contact" in on and (v2_dir("veg") / "contact.png").exists():
        img = over(img, rgba(v2_dir("veg") / "contact.png"))
    if shadow:
        a = np.asarray(Image.open(V1 / "shadows" / f"L6_shadow_{shadow}.png")).astype(np.float32)[..., None] / 255 * 0.42
        img = img * (1 - a) + np.array((38, 44, 86), np.float32) * a
    if "objects" in on:
        img = over(img, rgba(V1 / "objects" / "L7_buildings.png"))
        img = over(img, rgba(V1 / "objects" / "L5_bridges.png"))
    vd = v2_dir("veg" + (f"_{tag}" if tag else ""))
    vp = vd / ("L3_veg_clear.png" if clear else "L3_veg.png")
    if "veg" in on and vp.exists():
        img = over(img, rgba(vp))
    return img.clip(0, 255).astype(np.uint8)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 10 + 7 * len(text), 22), fill=(255, 255, 255))
    d.text((5, 5), text, fill=(20, 20, 20))
    return im


def panels(ims, labels, out, width=1600):
    n = len(ims)
    w = (width - 10 * (n - 1)) // n
    ims = [label(Image.fromarray(np.asarray(i)).convert("RGB").resize((w, round(np.asarray(i).shape[0] * w / np.asarray(i).shape[1])),
                                                                     Image.LANCZOS), t) for i, t in zip(ims, labels)]
    sheet = Image.new("RGB", (width, ims[0].height), (255, 255, 255))
    for j, im in enumerate(ims):
        sheet.paste(im, (j * (w + 10), 0))
    preview(sheet, out, size=width)


def checker(shape, n=16):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    c = (((yy // n) + (xx // n)) % 2)[..., None]
    return np.where(c > 0, 236, 250).astype(np.float32) * np.ones(3, np.float32)


def sheets(tag):
    b = block("b00")
    T = np.asarray(today(b, K))
    V1s = np.asarray(Image.open(V1 / "composite_midday_summer.png").convert("RGB"))
    V2s = stack(tag)
    Image.fromarray(V2s).save(LAYERS / "b00_v2" / f"stack{'_' + tag if tag else ''}.png")
    pre = f"v2_{tag}_" if tag else "v2_"
    panels([T, V2s], ["Today", "Version 2"], POC_IMG / f"{pre}whole_today.jpg")
    panels([V1s, V2s], ["Version 1", "Version 2"], POC_IMG / f"{pre}whole_v1.jpg")
    for s, (x, y, w) in SPOTS.items():
        bx = [int(v * K) for v in (x, y, x + w, y + w)]
        cr = lambda a: a[bx[1]:bx[3], bx[0]:bx[2]]  # noqa: E731
        panels([cr(T), cr(V1s), cr(V2s)], [f"Today, {NAMES[s]}", "Version 1", "Version 2"], POC_IMG / f"{pre}spot_{s}.jpg")
    if not tag:
        # each layer alone (checkerboard = transparent)
        x, y, w = SPOTS["grund"]
        bx = [int(v * K) for v in (x, y, x + w, y + w)]
        cr = lambda a: a[bx[1]:bx[3], bx[0]:bx[2]]  # noqa: E731
        g = np.asarray(Image.open(v2_dir("ground") / "L1_ground.png").convert("RGB"))
        alone = []
        for p in (v2_dir("ink") / "L2_ink.png", v2_dir("veg") / "L3_veg.png", V1 / "objects" / "L7_buildings.png"):
            L = rgba(p)
            alone.append(over(checker(L.shape), L).clip(0, 255).astype(np.uint8))
        panels([g, alone[0], alone[1], alone[2]], ["1 Painted ground", "2 Ink lines", "3 Painted trees", "Buildings (v1)"],
               POC_IMG / "v2_layers_whole.jpg")
        panels([cr(g), cr(alone[0]), cr(alone[1]), cr(alone[2])], ["1 Painted ground", "2 Ink lines", "3 Painted trees",
                                                                 "Buildings (v1)"], POC_IMG / "v2_layers_grund.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--tag", default="")
    ap.add_argument("--clear", action="store_true")
    ap.add_argument("--shadow")
    ap.add_argument("--only")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.cmd == "stack":
        Image.fromarray(stack(a.tag, a.clear, a.shadow, a.only)).save(a.out)
    elif a.cmd == "sheets":
        sheets(a.tag)
