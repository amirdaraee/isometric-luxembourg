"""Shared by tiler.py and repaint.py: colour-drift measurement/correction and soft pasting.

Seam test by construction: in every window the model also redraws the already-painted context it was shown.
Those pixels should come back unchanged, so the colour difference there (CIELAB, dE) measures how far this
generation drifted. A drift we can measure we can undo: the new region is colour-matched (per-channel mean and
spread) from the model's context back to the true context before it is pasted.
"""
import numpy as np
import cv2
from PIL import Image

FEATHER = 32
BG = np.array([16, 24, 40])


def _lab(a):
    lab = cv2.cvtColor(a, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab[..., 0] *= 100 / 255
    lab[..., 1:] -= 128
    return lab


def _rgb(lab):
    l = lab.copy()
    l[..., 0] *= 255 / 100
    l[..., 1:] += 128
    return cv2.cvtColor(np.clip(l, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


def drift_correct(inp: Image.Image, out: Image.Image, box, context_mask: np.ndarray):
    """Return (corrected output, drift dE before, drift dE after). context_mask: True where inp holds painted
    pixels the model should have kept (excluding a margin around the red outline)."""
    a, b = np.asarray(inp.convert("RGB")), np.asarray(out.convert("RGB"))
    ctx = context_mask & (np.abs(a.astype(int) - BG).sum(axis=2) > 30)
    if ctx.sum() < 15000:
        return out, None, None
    la, lb = _lab(a), _lab(b)
    mi, si = la[ctx].mean(0), la[ctx].std(0) + 1e-3
    mo, so = lb[ctx].mean(0), lb[ctx].std(0) + 1e-3
    before = float(np.linalg.norm(mo - mi))
    ratio = np.clip(si / so, 0.85, 1.15)
    fixed = (lb - mo) * ratio + mi
    after = float(np.linalg.norm(fixed[ctx].mean(0) - mi))
    return Image.fromarray(_rgb(fixed)), round(before, 2), round(after, 2)


def context_mask(box, painted_px: np.ndarray, margin=16):
    """painted_px: 1024x1024 bool, True where the input holds already-painted pixels."""
    m = painted_px.copy()
    x0, y0, x1, y1 = box
    m[max(y0 - margin, 0):y1 + margin, max(x0 - margin, 0):x1 + margin] = False
    return m


def paste_soft(canvas: Image.Image, out: Image.Image, box, wx, wy, sides):
    """Paste out[box] at window origin (wx, wy), reaching FEATHER px into the painted neighbours on the given
    sides ('l','t','r','b') and fading in, so the join is a blend, not a cut."""
    F = FEATHER
    x0 = box[0] - (F if "l" in sides else 0); y0 = box[1] - (F if "t" in sides else 0)
    x1 = box[2] + (F if "r" in sides else 0); y1 = box[3] + (F if "b" in sides else 0)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, out.width), min(y1, out.height)
    m = np.ones((y1 - y0, x1 - x0), np.float32)
    # Fade only across the band reaching into the neighbours; the new region itself is pasted fully (the canvas
    # under it may still hold the raw render).
    l, t, r, b = box[0] - x0, box[1] - y0, x1 - box[2], y1 - box[3]
    if l > 0: m[:, :l] *= np.linspace(0, 1, l, dtype=np.float32)[None]
    if t > 0: m[:t] *= np.linspace(0, 1, t, dtype=np.float32)[:, None]
    if r > 0: m[:, -r:] *= np.linspace(1, 0, r, dtype=np.float32)[None]
    if b > 0: m[-b:] *= np.linspace(1, 0, b, dtype=np.float32)[:, None]
    canvas.paste(out.crop((x0, y0, x1, y1)), (wx + x0, wy + y0), Image.fromarray((m * 255).astype(np.uint8)))
